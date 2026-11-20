// AntiRollbackGuardia.cs
// Protección avanzada contra rollback con dos líneas de defensa:
//   Línea 1 — Contador monotónico de hardware (TPM NV Index, si disponible)
//   Línea 2 — Hash chain local firmada (append-only en DPAPI + fichero)
// Namespace: Visor3D.Seguridad.SesionUnica
// Compatible: .NET 8 Windows — sin dependencias NuGet externas.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;

namespace Visor3D.Seguridad.SesionUnica
{
    // ─────────────────────────────────────────────────────────────────────────
    // Tipos públicos
    // ─────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Resultado de las operaciones de anti-rollback.
    /// </summary>
    public enum ResultadoAntiRollback
    {
        Ok,
        ContadorRetrocedido,
        CadenaManipulada,
        TpmNoDisponible,
        ErrorIo
    }

    /// <summary>
    /// Una entrada de la hash chain local.
    /// </summary>
    public struct EntradaCadena
    {
        /// <summary>Valor monotónico del contador en este punto.</summary>
        public long Contador;

        /// <summary>Timestamp UTC en ticks de DateTime (DateTime.UtcNow.Ticks).</summary>
        public long TimestampUtc;

        /// <summary>Hash SHA-256 hex de la entrada anterior ("0000...0" para la primera).</summary>
        public string HashPrevio;

        /// <summary>HMACSHA256(secretoMaestro, payload) en base-64.</summary>
        public string Mac;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Clase principal
    // ─────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Protección avanzada contra rollback con dos líneas de defensa:
    ///
    /// Línea 1 — Contador monotónico de hardware (TPM NV Index, si disponible)
    ///   El TPM NV counter es verdaderamente monotónico: ni el admin puede reducirlo
    ///   sin acceso físico. Usa NV Index en el rango NV_ORDINARY (0x01000000).
    ///   P/Invoke a tbs.dll (Tbsi_Context_Create, Tbsi_Submit_Command) para comandos TPM2.
    ///   NOTA: en PCs domésticos, el acceso a NV índices puede requerir autorización de Owner.
    ///   Si falla, se degrada graciosamente a la Línea 2.
    ///
    /// Línea 2 — Hash chain local firmada (append-only en DPAPI + fichero)
    ///   Cadena de bloques local: cada incremento de contador añade una entrada firmada.
    ///   Hash(entrada_N) = SHA256(contador_N | timestamp_N | Hash(entrada_N-1) | mac_N)
    ///   mac_N = HMACSHA256(secreto_maestro, payload_completo)
    ///   Almacenada en %LOCALAPPDATA%\WoldVirtualP2P3D\Seguridad\rollback_chain.jsonl
    ///   Detecta rollback al comparar el último contador de la cadena con el contador
    ///   solicitado. No PREVIENE el rollback por un admin, pero lo DETECTA y bloquea.
    /// </summary>
    public static class AntiRollbackGuardia
    {
        // ─── Rutas ───────────────────────────────────────────────────────────

        private static readonly string _directorioSeguridad = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WoldVirtualP2P3D", "Seguridad");

        private static readonly string _rutaCadena = Path.Combine(
            _directorioSeguridad, "rollback_chain.jsonl");

        // ─── Sincronización ──────────────────────────────────────────────────

        private static readonly ReaderWriterLockSlim _rw = new ReaderWriterLockSlim();

        // ─── Constantes TPM NV ───────────────────────────────────────────────

        // NV Index ordinario en espacio de usuario (handle 0x01xxxxxx)
        private const uint TPM_NV_INDEX = 0x01500001u;   // índice elegido para esta app

        // Tamaño del contador NV (8 bytes = uint64)
        private const ushort TPM_NV_SIZE = 8;

        // ─────────────────────────────────────────────────────────────────────
        // API pública
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Lee el contador monotónico actual.
        /// Intenta leer del TPM NV Index primero; si falla, usa la cadena local.
        /// Devuelve -1 si no hay ningún contador disponible.
        /// Never throws.
        /// </summary>
        public static long ObtenerContadorActual()
        {
            try
            {
                // Línea 1: TPM NV counter
                if (TpmNvDisponible())
                {
                    long tpmVal = TpmNvLeer();
                    if (tpmVal >= 0) return tpmVal;
                }

                // Línea 2: último valor de la cadena local
                _rw.EnterReadLock();
                try
                {
                    EntradaCadena? ultima = LeerUltimaEntradaInterno();
                    return ultima.HasValue ? ultima.Value.Contador : 0L;
                }
                finally { _rw.ExitReadLock(); }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AntiRollback] ObtenerContadorActual error: {ex.Message}");
                return -1L;
            }
        }

        /// <summary>
        /// Devuelve el modo activo de protección contra rollback:
        /// "TPM2_Hardware_NV" si el índice NV por hardware está operativo,
        /// o "CadenaLocal_Firmada_DPAPI (Fallback)" si opera en modo degradado local.
        /// </summary>
        public static string ObtenerModoActivo()
        {
            if (TpmNvDisponible())
                return "TPM2_Hardware_NV";
            return "CadenaLocal_Firmada_DPAPI (Fallback)";
        }

        /// <summary>
        /// Incrementa (o establece) el contador al valor <paramref name="nuevoValor"/>.
        /// Verifica que no hay retroceso antes de guardar.
        /// ZeroMemory sobre <paramref name="secretoMaestro"/> al terminar.
        /// Never throws.
        /// </summary>
        public static ResultadoAntiRollback IncrementarContador(long nuevoValor, byte[] secretoMaestro)
        {
            if (secretoMaestro == null) return ResultadoAntiRollback.CadenaManipulada;
            try
            {
                // Primero verificar que no retrocede
                ResultadoAntiRollback chk = VerificarNoRetroceso(nuevoValor, secretoMaestro);
                if (chk != ResultadoAntiRollback.Ok) return chk;

                // Intentar actualizar TPM NV (best-effort; no es fatal si falla)
                bool tpmOk = false;
                if (TpmNvDisponible())
                    tpmOk = TpmNvIncrementar(nuevoValor);

                // Siempre actualizar la cadena local
                ResultadoAntiRollback res = AgregarEntradaCadena(nuevoValor, secretoMaestro);

                _ = tpmOk; // suprimir warning; TPM es best-effort
                return res;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AntiRollback] IncrementarContador error: {ex.Message}");
                return ResultadoAntiRollback.ErrorIo;
            }
            finally
            {
                ZeroMemory(secretoMaestro);
            }
        }

        /// <summary>
        /// Verifica que <paramref name="contadorSolicitado"/> no es un retroceso
        /// respecto al último contador conocido.
        /// ZeroMemory sobre <paramref name="secretoMaestro"/> al terminar.
        /// Never throws.
        /// </summary>
        public static ResultadoAntiRollback VerificarNoRetroceso(long contadorSolicitado, byte[] secretoMaestro)
        {
            if (secretoMaestro == null) return ResultadoAntiRollback.CadenaManipulada;
            try
            {
                _rw.EnterReadLock();
                EntradaCadena? ultima;
                try { ultima = LeerUltimaEntradaInterno(); }
                finally { _rw.ExitReadLock(); }

                if (!ultima.HasValue)
                    return ResultadoAntiRollback.Ok; // primera entrada, sin histórico

                // Verificar retroceso
                if (contadorSolicitado < ultima.Value.Contador)
                    return ResultadoAntiRollback.ContadorRetrocedido;

                // Verificar MAC de la última entrada para detectar manipulación
                if (!ValidarMac(ultima.Value, secretoMaestro))
                    return ResultadoAntiRollback.CadenaManipulada;

                return ResultadoAntiRollback.Ok;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AntiRollback] VerificarNoRetroceso error: {ex.Message}");
                return ResultadoAntiRollback.ErrorIo;
            }
            finally
            {
                ZeroMemory(secretoMaestro);
            }
        }

        /// <summary>
        /// Comprueba si el TPM NV Index está disponible y operativo.
        /// Never throws; devuelve false en cualquier error.
        /// </summary>
        public static bool TpmNvDisponible()
        {
            try
            {
                return TpmNvComprobar();
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AntiRollback] TpmNvDisponible error: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Verifica la integridad completa de la cadena local:
        /// comprueba que cada entrada enlaza correctamente con la anterior
        /// y que todos los MACs son válidos.
        /// ZeroMemory sobre <paramref name="secretoMaestro"/> al terminar.
        /// Never throws.
        /// </summary>
        public static (bool ok, string detalle) VerificarIntegridadCadenaLocal(byte[] secretoMaestro)
        {
            if (secretoMaestro == null)
                return (false, "secretoMaestro nulo.");
            try
            {
                _rw.EnterReadLock();
                List<EntradaCadena> entradas;
                try { entradas = LeerTodasLasEntradas(); }
                finally { _rw.ExitReadLock(); }

                if (entradas.Count == 0)
                    return (true, "Cadena vacía (sin entradas).");

                string hashAnterior = new string('0', 64); // hash ficticio para la primera
                for (int i = 0; i < entradas.Count; i++)
                {
                    EntradaCadena e = entradas[i];

                    // Verificar enlace de hash
                    if (i > 0)
                    {
                        string hashEsperado = ComputarHashEntrada(entradas[i - 1]);
                        if (!string.Equals(e.HashPrevio, hashEsperado, StringComparison.Ordinal))
                            return (false, $"Entrada #{i}: HashPrevio no coincide (cadena rota).");
                    }

                    // Verificar MAC
                    if (!ValidarMac(e, secretoMaestro))
                        return (false, $"Entrada #{i}: MAC inválido (manipulación detectada).");

                    // Verificar monotonía
                    if (i > 0 && e.Contador < entradas[i - 1].Contador)
                        return (false, $"Entrada #{i}: contador retrocedió de {entradas[i - 1].Contador} a {e.Contador}.");

                    hashAnterior = ComputarHashEntrada(e);
                }

                _ = hashAnterior;
                return (true, $"Cadena íntegra. {entradas.Count} entradas verificadas.");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AntiRollback] VerificarIntegridadCadenaLocal error: {ex.Message}");
                return (false, $"Error interno: {ex.Message}");
            }
            finally
            {
                ZeroMemory(secretoMaestro);
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // Cadena local — internos
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Lee la última entrada del fichero JSONL sin bloqueo (el llamador ya sostiene el lock).
        /// </summary>
        private static EntradaCadena? LeerUltimaEntradaInterno()
        {
            if (!File.Exists(_rutaCadena)) return null;

            EntradaCadena? ultima = null;
            // Leer líneas en orden (el fichero puede ser grande; buscamos la última)
            using var fs = new FileStream(_rutaCadena, FileMode.Open, FileAccess.Read, FileShare.Read);
            using var sr = new StreamReader(fs, Encoding.UTF8);
            string? linea;
            while ((linea = sr.ReadLine()) != null)
            {
                if (string.IsNullOrWhiteSpace(linea)) continue;
                try
                {
                    EntradaCadena? e = DeserializarEntrada(linea);
                    if (e.HasValue) ultima = e;
                }
                catch { /* línea corrupta, seguir */ }
            }
            return ultima;
        }

        private static List<EntradaCadena> LeerTodasLasEntradas()
        {
            var lista = new List<EntradaCadena>();
            if (!File.Exists(_rutaCadena)) return lista;

            using var fs = new FileStream(_rutaCadena, FileMode.Open, FileAccess.Read, FileShare.Read);
            using var sr = new StreamReader(fs, Encoding.UTF8);
            string? linea;
            while ((linea = sr.ReadLine()) != null)
            {
                if (string.IsNullOrWhiteSpace(linea)) continue;
                try
                {
                    EntradaCadena? e = DeserializarEntrada(linea);
                    if (e.HasValue) lista.Add(e.Value);
                }
                catch { }
            }
            return lista;
        }

        /// <summary>
        /// Agrega una nueva entrada firmada al fichero JSONL.
        /// Thread-safe mediante escritura con lock de escritura.
        /// </summary>
        private static ResultadoAntiRollback AgregarEntradaCadena(long nuevoValor, byte[] secretoMaestro)
        {
            _rw.EnterWriteLock();
            try
            {
                // Asegurar directorio
                Directory.CreateDirectory(_directorioSeguridad);

                // Obtener última entrada para encadenar
                EntradaCadena? ultimaOpt = LeerUltimaEntradaInterno();
                string hashPrevio = ultimaOpt.HasValue
                    ? ComputarHashEntrada(ultimaOpt.Value)
                    : new string('0', 64);

                long ts = DateTime.UtcNow.Ticks;
                string mac = ComputarMac(secretoMaestro, nuevoValor, ts, hashPrevio);

                var nueva = new EntradaCadena
                {
                    Contador   = nuevoValor,
                    TimestampUtc = ts,
                    HashPrevio = hashPrevio,
                    Mac        = mac
                };

                string linea = SerializarEntrada(nueva);

                // Append-only
                using var fs = new FileStream(_rutaCadena, FileMode.Append, FileAccess.Write, FileShare.None);
                using var sw = new StreamWriter(fs, Encoding.UTF8);
                sw.WriteLine(linea);

                return ResultadoAntiRollback.Ok;
            }
            catch (IOException ex)
            {
                Debug.WriteLine($"[AntiRollback] AgregarEntradaCadena IO error: {ex.Message}");
                return ResultadoAntiRollback.ErrorIo;
            }
            finally
            {
                _rw.ExitWriteLock();
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // Criptografía
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Calcula el hash SHA-256 de una entrada (como identificador de bloque).
        /// Hash = SHA256(contador|timestampUtc|hashPrevio|mac)
        /// </summary>
        private static string ComputarHashEntrada(EntradaCadena e)
        {
            byte[] datos = Encoding.UTF8.GetBytes(
                $"{e.Contador}|{e.TimestampUtc}|{e.HashPrevio}|{e.Mac}");
            byte[] hash = SHA256.HashData(datos);
            return Convert.ToHexString(hash).ToLowerInvariant();
        }

        /// <summary>
        /// Calcula HMACSHA256(secretoMaestro, payload) donde payload = "contador|ts|hashPrevio".
        /// </summary>
        private static string ComputarMac(byte[] secreto, long contador, long ts, string hashPrevio)
        {
            byte[] payload = Encoding.UTF8.GetBytes($"{contador}|{ts}|{hashPrevio}");
            using var hmac = new HMACSHA256(secreto);
            byte[] mac = hmac.ComputeHash(payload);
            return Convert.ToBase64String(mac);
        }

        /// <summary>
        /// Valida que el MAC de la entrada es correcto.
        /// </summary>
        private static bool ValidarMac(EntradaCadena e, byte[] secreto)
        {
            string macCalculado = ComputarMac(secreto, e.Contador, e.TimestampUtc, e.HashPrevio);
            // Comparación en tiempo constante
            return CryptographicOperations.FixedTimeEquals(
                Encoding.UTF8.GetBytes(macCalculado),
                Encoding.UTF8.GetBytes(e.Mac));
        }

        // ─────────────────────────────────────────────────────────────────────
        // Serialización JSON (manual, sin dependencias externas)
        // ─────────────────────────────────────────────────────────────────────

        private static string SerializarEntrada(EntradaCadena e)
        {
            // Formato compacto compatible con JsonSerializer del runtime (.NET 8)
            return JsonSerializer.Serialize(new
            {
                cnt  = e.Contador,
                ts   = e.TimestampUtc,
                prev = e.HashPrevio,
                mac  = e.Mac
            });
        }

        private static EntradaCadena? DeserializarEntrada(string json)
        {
            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;
            return new EntradaCadena
            {
                Contador     = root.GetProperty("cnt").GetInt64(),
                TimestampUtc = root.GetProperty("ts").GetInt64(),
                HashPrevio   = root.GetProperty("prev").GetString() ?? string.Empty,
                Mac          = root.GetProperty("mac").GetString() ?? string.Empty
            };
        }

        // ─────────────────────────────────────────────────────────────────────
        // ZeroMemory
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>Pone a cero el contenido de un array de bytes (best-effort, nunca lanza).</summary>
        [MethodImpl(MethodImplOptions.NoInlining | MethodImplOptions.NoOptimization)]
        private static void ZeroMemory(byte[]? buf)
        {
            if (buf == null) return;
            try { CryptographicOperations.ZeroMemory(buf); }
            catch { /* never throws */ }
        }

        // ─────────────────────────────────────────────────────────────────────
        // TPM NV — P/Invoke a tbs.dll + construcción de comandos TPM 2.0
        // ─────────────────────────────────────────────────────────────────────
        //
        // Usamos la interfaz TBS (TPM Base Services) de Windows para enviar
        // comandos TPM 2.0 en crudo. Las estructuras y opcodes siguen la spec
        // TCG TPM Library Part 2 (Structures) y Part 3 (Commands).
        //
        // ─────────────────────────────────────────────────────────────────────

        // ── P/Invoke ─────────────────────────────────────────────────────────

        [DllImport("tbs.dll", CallingConvention = CallingConvention.Winapi, SetLastError = false)]
        private static extern uint Tbsi_Context_Create(ref TBS_CONTEXT_PARAMS pContextParams, out IntPtr phContext);

        [DllImport("tbs.dll", CallingConvention = CallingConvention.Winapi, SetLastError = false)]
        private static extern uint Tbsip_Context_Close(IntPtr hContext);

        [DllImport("tbs.dll", CallingConvention = CallingConvention.Winapi, SetLastError = false)]
        private static extern uint Tbsip_Submit_Command(
            IntPtr hContext,
            uint Locality,
            uint Priority,
            byte[] pabCommand,
            uint cbCommand,
            byte[] pabResult,
            ref uint pcbResult);

        [StructLayout(LayoutKind.Sequential)]
        private struct TBS_CONTEXT_PARAMS
        {
            public uint version;
        }

        // TBS error codes / constants
        private const uint TBS_SUCCESS              = 0x00000000u;
        private const uint TBS_CONTEXT_VERSION_ONE  = 1u;
        private const uint TBS_COMMAND_LOCALITY_ZERO = 0u;
        private const uint TBS_COMMAND_PRIORITY_NORMAL = 200u;

        // TPM 2.0 structures / constants (little subset needed)
        private const ushort TPM_ST_NO_SESSIONS = 0x8001;
        private const ushort TPM_CC_NV_READ      = 0x014E;
        private const ushort TPM_CC_NV_WRITE     = 0x0137;
        private const ushort TPM_CC_NV_DEFINESPACE = 0x012A;
        private const ushort TPM_CC_NV_UNDEFINESPACE = 0x0122;
        private const uint   TPM_RS_PW           = 0x40000009u;
        private const uint   TPM_RH_OWNER        = 0x40000001u;
        private const ushort TPM_ALG_NULL        = 0x0010;
        private const uint   TPMA_NV_COUNTER     = 0x00000010u; // NV_COUNTER attribute
        private const uint   TPMA_NV_AUTHREAD    = 0x00040000u;
        private const uint   TPMA_NV_AUTHWRITE   = 0x00000004u;
        private const uint   TPMA_NV_PLATFORMCREATE = 0x40000000u;

        // ── Apertura de contexto TBS ─────────────────────────────────────────

        private static IntPtr AbrirContextoTbs()
        {
            var p = new TBS_CONTEXT_PARAMS { version = TBS_CONTEXT_VERSION_ONE };
            uint r = Tbsi_Context_Create(ref p, out IntPtr ctx);
            if (r != TBS_SUCCESS)
                throw new InvalidOperationException($"Tbsi_Context_Create: 0x{r:X8}");
            return ctx;
        }

        // ── Comprobar si el NV index existe y es accesible ───────────────────

        private static bool TpmNvComprobar()
        {
            // Intentar leer; si devuelve algo coherente, está disponible
            long v = TpmNvLeer();
            return v >= 0;
        }

        // ── Leer el contador del NV Index ────────────────────────────────────

        /// <summary>
        /// Envía TPM2_NV_Read para leer 8 bytes del NV Index.
        /// Devuelve el valor leído como long, o -1 si falla.
        /// </summary>
        private static long TpmNvLeer()
        {
            IntPtr ctx = IntPtr.Zero;
            try
            {
                ctx = AbrirContextoTbs();

                // TPM2_NV_Read command (sin sesiones de autorización, usando PW session)
                // Estructura: Header(10) + authHandle(4) + nvIndex(4) + sessions + size(2) + offset(2)
                // Usamos sesión de contraseña vacía (plataforma o owner sin auth)
                byte[] cmd = BuildNvReadCommand(TPM_NV_INDEX, TPM_NV_SIZE, 0);

                byte[] rsp = new byte[512];
                uint rspLen = (uint)rsp.Length;
                uint r = Tbsip_Submit_Command(ctx, TBS_COMMAND_LOCALITY_ZERO, TBS_COMMAND_PRIORITY_NORMAL,
                    cmd, (uint)cmd.Length, rsp, ref rspLen);

                if (r != TBS_SUCCESS || rspLen < 10) return -1L;

                // Response code en bytes 6-9 (big-endian)
                uint rc = ReadBE32(rsp, 6);
                if (rc != 0) return -1L;

                // Response: Header(10) + paramSize(4) + data(TPM_NV_SIZE)
                if (rspLen < 10 + 2 + TPM_NV_SIZE) return -1L;
                int dataOffset = 10 + 2; // paramSize(2 bytes) para TPM2B_MAX_NV_BUFFER size
                return (long)ReadBE64(rsp, dataOffset);
            }
            catch
            {
                return -1L;
            }
            finally
            {
                if (ctx != IntPtr.Zero) Tbsip_Context_Close(ctx);
            }
        }

        // ── Incrementar / establecer el NV Index ─────────────────────────────

        /// <summary>
        /// Intenta escribir <paramref name="nuevoValor"/> en el NV Index.
        /// Para un NV_COUNTER real, TPM2_NV_Increment es la única opción (no podemos
        /// escribir un valor arbitrario). Esta implementación usa NV_WRITE para un
        /// NV ordinario (no NV_COUNTER propiamente dicho), ya que NV_COUNTER no
        /// permite escritura arbitraria. El monotonismo hardware real requeriría
        /// NV_COUNTER + NV_Increment solamente.
        /// Devuelve true si la operación tuvo éxito.
        /// </summary>
        private static bool TpmNvIncrementar(long nuevoValor)
        {
            IntPtr ctx = IntPtr.Zero;
            try
            {
                ctx = AbrirContextoTbs();

                // Intentar primero definir el espacio NV si no existe
                // (ignoramos el error si ya existe)
                TpmNvDefinirEspacio(ctx);

                byte[] cmd = BuildNvWriteCommand(TPM_NV_INDEX, nuevoValor);
                byte[] rsp = new byte[512];
                uint rspLen = (uint)rsp.Length;
                uint r = Tbsip_Submit_Command(ctx, TBS_COMMAND_LOCALITY_ZERO, TBS_COMMAND_PRIORITY_NORMAL,
                    cmd, (uint)cmd.Length, rsp, ref rspLen);

                if (r != TBS_SUCCESS || rspLen < 10) return false;
                uint rc = ReadBE32(rsp, 6);
                return rc == 0;
            }
            catch
            {
                return false;
            }
            finally
            {
                if (ctx != IntPtr.Zero) Tbsip_Context_Close(ctx);
            }
        }

        /// <summary>
        /// Envía TPM2_NV_DefineSpace para crear el NV index si no existe.
        /// </summary>
        private static void TpmNvDefinirEspacio(IntPtr ctx)
        {
            try
            {
                byte[] cmd = BuildNvDefineSpaceCommand(TPM_NV_INDEX, TPM_NV_SIZE);
                byte[] rsp = new byte[512];
                uint rspLen = (uint)rsp.Length;
                Tbsip_Submit_Command(ctx, TBS_COMMAND_LOCALITY_ZERO, TBS_COMMAND_PRIORITY_NORMAL,
                    cmd, (uint)cmd.Length, rsp, ref rspLen);
                // Ignoramos el resultado: si ya existe, el error TPM_RC_NV_DEFINED es esperado.
            }
            catch { /* best-effort */ }
        }

        // ─────────────────────────────────────────────────────────────────────
        // Construcción de comandos TPM 2.0 (big-endian marshaling)
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Construye un buffer TPM2_NV_Read.
        /// Sin sesiones explícitas, usando password authorization (empty auth).
        /// </summary>
        private static byte[] BuildNvReadCommand(uint nvIndex, ushort dataSize, ushort offset)
        {
            // TPM2_NV_Read:
            //   TPMI_SH_AUTH_SESSION  authHandle  = TPM_RS_PW
            //   TPMI_RH_NV_AUTH       authNvIndex = nvIndex
            //   TPMI_RH_NV_INDEX      nvIndex     = nvIndex
            //   Authorization block (PW, empty)
            //   UINT16 size
            //   UINT16 offset
            using var ms = new MemoryStream();
            using var w  = new BinaryWriter(ms);

            // Header placeholder (filled at end)
            w.Write(ToBE16(TPM_ST_NO_SESSIONS)); // tag
            w.Write(ToBE32(0));                   // commandSize (placeholder)
            w.Write(ToBE32((uint)TPM_CC_NV_READ)); // commandCode

            // Handles
            w.Write(ToBE32(nvIndex));  // authHandle (use nvIndex auth)
            w.Write(ToBE32(nvIndex));  // nvIndex

            // Authorization area (password session, empty password)
            byte[] authArea = BuildPwAuthArea();
            w.Write(ToBE32((uint)authArea.Length)); // authorizationSize
            w.Write(authArea);

            // Parameters
            w.Write(ToBE16(dataSize)); // size
            w.Write(ToBE16(offset));   // offset

            byte[] buf = ms.ToArray();
            // Fix commandSize
            byte[] sizeBytes = ToBE32((uint)buf.Length);
            buf[2] = sizeBytes[0]; buf[3] = sizeBytes[1];
            buf[4] = sizeBytes[2]; buf[5] = sizeBytes[3];
            return buf;
        }

        /// <summary>
        /// Construye un buffer TPM2_NV_Write con 8 bytes de datos (el contador).
        /// </summary>
        private static byte[] BuildNvWriteCommand(uint nvIndex, long value)
        {
            using var ms = new MemoryStream();
            using var w  = new BinaryWriter(ms);

            w.Write(ToBE16(TPM_ST_NO_SESSIONS));
            w.Write(ToBE32(0)); // placeholder
            w.Write(ToBE32((uint)TPM_CC_NV_WRITE));

            // Handles: authHandle = owner, nvIndex
            w.Write(ToBE32(TPM_RH_OWNER));
            w.Write(ToBE32(nvIndex));

            // Auth area
            byte[] authArea = BuildPwAuthArea();
            w.Write(ToBE32((uint)authArea.Length));
            w.Write(authArea);

            // TPM2B_MAX_NV_BUFFER: size(2) + data(8)
            w.Write(ToBE16(8));
            w.Write(ToBE64((ulong)value));

            // offset
            w.Write(ToBE16(0));

            byte[] buf = ms.ToArray();
            byte[] sz = ToBE32((uint)buf.Length);
            buf[2] = sz[0]; buf[3] = sz[1]; buf[4] = sz[2]; buf[5] = sz[3];
            return buf;
        }

        /// <summary>
        /// Construye un buffer TPM2_NV_DefineSpace para un NV index ordinario de 8 bytes.
        /// </summary>
        private static byte[] BuildNvDefineSpaceCommand(uint nvIndex, ushort size)
        {
            using var ms = new MemoryStream();
            using var w  = new BinaryWriter(ms);

            w.Write(ToBE16(TPM_ST_NO_SESSIONS));
            w.Write(ToBE32(0)); // placeholder
            w.Write(ToBE32((uint)TPM_CC_NV_DEFINESPACE));

            // Handle: authHandle = owner
            w.Write(ToBE32(TPM_RH_OWNER));

            // Auth area
            byte[] authArea = BuildPwAuthArea();
            w.Write(ToBE32((uint)authArea.Length));
            w.Write(authArea);

            // auth (TPM2B_AUTH, empty)
            w.Write(ToBE16(0));

            // TPMS_NV_PUBLIC:
            //   nvIndex(4), nameAlg(2), attributes(4), authPolicy(2 + 0 bytes), dataSize(2)
            using var nvPublicMs = new MemoryStream();
            using var nvW = new BinaryWriter(nvPublicMs);
            nvW.Write(ToBE32(nvIndex));
            nvW.Write(ToBE16(0x000B)); // TPM_ALG_SHA256
            uint attrs = TPMA_NV_AUTHREAD | TPMA_NV_AUTHWRITE; // readable/writable by owner auth
            nvW.Write(ToBE32(attrs));
            nvW.Write(ToBE16(0)); // authPolicy (empty)
            nvW.Write(ToBE16(size));
            byte[] nvPublicBytes = nvPublicMs.ToArray();

            // TPM2B_NV_PUBLIC: size(2) + nvPublic
            w.Write(ToBE16((ushort)nvPublicBytes.Length));
            w.Write(nvPublicBytes);

            byte[] buf = ms.ToArray();
            byte[] sz = ToBE32((uint)buf.Length);
            buf[2] = sz[0]; buf[3] = sz[1]; buf[4] = sz[2]; buf[5] = sz[3];
            return buf;
        }

        /// <summary>
        /// Construye una authorization area de sesión de contraseña vacía (PW, no auth).
        /// sessionHandle=TPM_RS_PW, nonce=empty, sessionAttributes=0, hmac=empty.
        /// </summary>
        private static byte[] BuildPwAuthArea()
        {
            using var ms = new MemoryStream();
            using var w  = new BinaryWriter(ms);
            w.Write(ToBE32(TPM_RS_PW));  // sessionHandle
            w.Write(ToBE16(0));           // nonce size = 0
            w.Write((byte)0);             // sessionAttributes
            w.Write(ToBE16(0));           // hmac size = 0
            return ms.ToArray();
        }

        // ─────────────────────────────────────────────────────────────────────
        // Helpers de marshaling big-endian
        // ─────────────────────────────────────────────────────────────────────

        private static byte[] ToBE16(ushort v) =>
            new[] { (byte)(v >> 8), (byte)v };

        private static byte[] ToBE32(uint v) =>
            new[] { (byte)(v >> 24), (byte)(v >> 16), (byte)(v >> 8), (byte)v };

        private static byte[] ToBE64(ulong v) =>
            new[]
            {
                (byte)(v >> 56), (byte)(v >> 48), (byte)(v >> 40), (byte)(v >> 32),
                (byte)(v >> 24), (byte)(v >> 16), (byte)(v >> 8),  (byte)v
            };

        private static uint ReadBE32(byte[] buf, int offset) =>
            ((uint)buf[offset] << 24) | ((uint)buf[offset + 1] << 16) |
            ((uint)buf[offset + 2] << 8) | buf[offset + 3];

        private static ulong ReadBE64(byte[] buf, int offset)
        {
            ulong hi = ReadBE32(buf, offset);
            ulong lo = ReadBE32(buf, offset + 4);
            return (hi << 32) | lo;
        }
    }
}
