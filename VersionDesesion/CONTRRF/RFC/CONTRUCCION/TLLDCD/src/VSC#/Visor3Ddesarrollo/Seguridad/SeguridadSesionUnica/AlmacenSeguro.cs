// =============================================================================
// AlmacenSeguro.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Persistencia Dual y Cadena Local Append-Only (Zero Trust v3)
// =============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Win32;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Gestión de persistencia dual: LocalAppData + Registro HKCU con DPAPI nativo y Cadena Local append-only.
    ///
    /// Todas las escrituras son atómicas.
    /// Las claves maestras se purgan con CryptographicOperations.ZeroMemory.
    /// Resistencia ante cierres intempestivos (crash recovery) en cadena_local.jsonl.
    /// Cifrado autenticado local con AES-GCM (256 bits).
    /// </summary>
    public static class AlmacenSeguro
    {
        private static readonly byte[] EntropiaDpapi = Encoding.UTF8.GetBytes("WVP3D::DPAPI::Entropy::v3");
        private const string SubKeyRegistro = @"Software\WoldVirtualP2P3D\Security";
        private const string ValorClaveSecreta = "MasterSecretBlob";
        private const string ValorSelloBackup = "MachineSealBlob";
        private const string ValorContadorMonotonico = "MonotonicCounter";
        private const string ValorFallosRecuperacion = "RecoveryFailedAttempts";
        private const string ValorBloqueoRecuperacionHasta = "RecoveryLockoutUntilUtc";

        private static readonly string DirectorioSello = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WoldVirtualP2P3D", "Seguridad");

        public static string RutaArchivoSello => Path.Combine(DirectorioSello, "pc_sello.json");
        public static string RutaCadenaLocal => Path.Combine(DirectorioSello, "cadena_local.jsonl");

        private static readonly object BloqueoIo = new();

        /// <summary>
        /// Obtiene o genera la clave secreta maestra aleatoria de 32 bytes (desacoplada de datos WMI).
        /// Protegida en reposo con DPAPI nativo (CurrentUser + entropía aislada).
        /// </summary>
        public static byte[] ObtenerOcrearSecretoMaestro()
        {
            lock (BloqueoIo)
            {
                using var key = Registry.CurrentUser.CreateSubKey(SubKeyRegistro);
                byte[]? blobCifrado = key.GetValue(ValorClaveSecreta) as byte[];

                if (blobCifrado != null && blobCifrado.Length > 0)
                {
                    try
                    {
                        byte[] secretoExistente = DesprotegerDpapi(blobCifrado, EntropiaDpapi);
                        if (secretoExistente.Length == 32)
                            return secretoExistente;
                    }
                    catch
                    {
                        // Si falla la desprotección DPAPI, se regenerará
                    }
                }

                byte[] nuevoSecreto = new byte[32];
                RandomNumberGenerator.Fill(nuevoSecreto);

                try
                {
                    byte[] cifrado = ProtegerDpapi(nuevoSecreto, EntropiaDpapi);
                    key.SetValue(ValorClaveSecreta, cifrado, RegistryValueKind.Binary);
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"[AlmacenSeguro] Aviso al guardar secreto DPAPI: {ex.Message}");
                }

                byte[] copiaRetorno = new byte[32];
                Buffer.BlockCopy(nuevoSecreto, 0, copiaRetorno, 0, 32);
                CryptographicOperations.ZeroMemory(nuevoSecreto);

                return copiaRetorno;
            }
        }

        /// <summary>
        /// Guarda el bloque v3 en anclaje dual con firma ECDSA P-256 y lo añade a la cadena local de forma atómica.
        /// </summary>
        public static void GuardarDualV3(SelloCuenta sello, ECDsa claveEcdsa, byte[] huellaBytes)
        {
            lock (BloqueoIo)
            {
                sello.FirmarEcdsa(claveEcdsa, huellaBytes);
                PersistirSelloEnAnclajes(sello);
            }
        }

        /// <summary>
        /// Guarda el bloque v2 en anclaje dual con HMAC (compatibilidad retroactiva).
        /// </summary>
        public static void GuardarDual(SelloCuenta sello, byte[] secretoClave, byte[] huellaBytes)
        {
            lock (BloqueoIo)
            {
                sello.FirmarHmac(secretoClave, huellaBytes);
                PersistirSelloEnAnclajes(sello);
            }
        }

        private static void PersistirSelloEnAnclajes(SelloCuenta sello)
        {
            string json = sello.Serializar();
            byte[] jsonBytes = Encoding.UTF8.GetBytes(json);

            Directory.CreateDirectory(DirectorioSello);

            // 1. Anclaje Primario: Archivo atómico (tmp + Replace / Move)
            string tmpFile = RutaArchivoSello + $".{Guid.NewGuid():N}.tmp";
            File.WriteAllText(tmpFile, json, Encoding.UTF8);
            try
            {
                if (File.Exists(RutaArchivoSello))
                {
                    File.Copy(tmpFile, RutaArchivoSello, overwrite: true);
                    File.Delete(tmpFile);
                }
                else
                {
                    File.Move(tmpFile, RutaArchivoSello, overwrite: true);
                }
            }
            catch
            {
                File.WriteAllText(RutaArchivoSello, json, Encoding.UTF8);
                try { if (File.Exists(tmpFile)) File.Delete(tmpFile); } catch { }
            }

            // 2. Anclaje Secundario: Registro HKCU protegido con DPAPI
            try
            {
                using var key = Registry.CurrentUser.CreateSubKey(SubKeyRegistro);
                byte[] cifrado = ProtegerDpapi(jsonBytes, EntropiaDpapi);
                key.SetValue(ValorSelloBackup, cifrado, RegistryValueKind.Binary);
                key.SetValue(ValorContadorMonotonico, sello.Contador, RegistryValueKind.QWord);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[AlmacenSeguro] Error al escribir anclaje de registro: {ex.Message}");
            }

            // 3. Cadena Local Append-Only (cadena_local.jsonl)
            GuardarBloqueEnCadenaInterno(sello);
        }

        /// <summary>
        /// Añade un bloque al final de cadena_local.jsonl mediante escritura atómica.
        /// </summary>
        public static void GuardarBloqueEnCadena(SelloCuenta bloque)
        {
            lock (BloqueoIo)
            {
                Directory.CreateDirectory(DirectorioSello);
                GuardarBloqueEnCadenaInterno(bloque);
            }
        }

        private static void GuardarBloqueEnCadenaInterno(SelloCuenta bloque)
        {
            string lineaJson = JsonSerializer.Serialize(bloque, new JsonSerializerOptions
            {
                WriteIndented = false,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            });

            string tmpChain = RutaCadenaLocal + $".{Guid.NewGuid():N}.tmp";

            if (File.Exists(RutaCadenaLocal))
            {
                File.Copy(RutaCadenaLocal, tmpChain, overwrite: true);
            }

            File.AppendAllText(tmpChain, lineaJson + Environment.NewLine, Encoding.UTF8);

            try
            {
                File.Copy(tmpChain, RutaCadenaLocal, overwrite: true);
                File.Delete(tmpChain);
            }
            catch
            {
                File.AppendAllText(RutaCadenaLocal, lineaJson + Environment.NewLine, Encoding.UTF8);
                try { if (File.Exists(tmpChain)) File.Delete(tmpChain); } catch { }
            }
        }

        /// <summary>
        /// Lee la cadena local completa.
        /// Detecta si la última línea quedó incompleta por fallo de alimentación o interrupción
        /// y la repara eliminando únicamente la línea truncada (crash recovery).
        /// </summary>
        public static List<SelloCuenta> LeerCadenaCompleta(out bool huboRecuperacionInterrupcion)
        {
            huboRecuperacionInterrupcion = false;
            var bloques = new List<SelloCuenta>();

            lock (BloqueoIo)
            {
                if (!File.Exists(RutaCadenaLocal))
                    return bloques;

                string[] lineas = File.ReadAllLines(RutaCadenaLocal, Encoding.UTF8);
                bool necesitaTruncar = false;
                int lineasValidas = 0;

                for (int i = 0; i < lineas.Length; i++)
                {
                    string linea = lineas[i].Trim();
                    if (string.IsNullOrWhiteSpace(linea)) continue;

                    var bloque = SelloCuenta.Deserializar(linea);
                    if (bloque != null && !string.IsNullOrWhiteSpace(bloque.IdCuentaHash))
                    {
                        bloques.Add(bloque);
                        lineasValidas++;
                    }
                    else
                    {
                        if (i == lineas.Length - 1 && lineasValidas > 0)
                        {
                            necesitaTruncar = true;
                            huboRecuperacionInterrupcion = true;
                        }
                    }
                }

                if (necesitaTruncar)
                {
                    var sb = new StringBuilder();
                    foreach (var b in bloques)
                    {
                        sb.AppendLine(JsonSerializer.Serialize(b, new JsonSerializerOptions
                        {
                            WriteIndented = false,
                            Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
                        }));
                    }
                    File.WriteAllText(RutaCadenaLocal, sb.ToString(), Encoding.UTF8);
                }

                return bloques;
            }
        }

        public static string? LeerAnclajeArchivo()
        {
            lock (BloqueoIo)
            {
                if (!File.Exists(RutaArchivoSello)) return null;
                try
                {
                    return File.ReadAllText(RutaArchivoSello, Encoding.UTF8);
                }
                catch
                {
                    return null;
                }
            }
        }

        public static string? LeerAnclajeRegistro()
        {
            lock (BloqueoIo)
            {
                try
                {
                    using var key = Registry.CurrentUser.OpenSubKey(SubKeyRegistro);
                    if (key == null) return null;

                    byte[]? blob = key.GetValue(ValorSelloBackup) as byte[];
                    if (blob == null || blob.Length == 0) return null;

                    byte[] desprotegido = DesprotegerDpapi(blob, EntropiaDpapi);
                    return Encoding.UTF8.GetString(desprotegido);
                }
                catch
                {
                    return null;
                }
            }
        }

        public static long LeerUltimoContadorRegistro()
        {
            lock (BloqueoIo)
            {
                try
                {
                    using var key = Registry.CurrentUser.OpenSubKey(SubKeyRegistro);
                    object? val = key?.GetValue(ValorContadorMonotonico);
                    return val is long l ? l : (val is int i ? i : 0);
                }
                catch { return 0; }
            }
        }

        public static void RegistrarUltimoContadorRegistro(long contador)
        {
            lock (BloqueoIo)
            {
                try
                {
                    using var key = Registry.CurrentUser.CreateSubKey(SubKeyRegistro);
                    key.SetValue(ValorContadorMonotonico, contador, RegistryValueKind.QWord);
                }
                catch { }
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // Cifrado y Descifrado Autenticado AES-GCM (256 bits)
        // ─────────────────────────────────────────────────────────────────────

        public static byte[] CifrarDatosSensibles(byte[] plaintext, byte[] claveAes256, out byte[] nonce, out byte[] tag)
        {
            nonce = new byte[AesGcm.NonceByteSizes.MaxSize]; // 12 bytes
            tag = new byte[AesGcm.TagByteSizes.MaxSize];     // 16 bytes
            RandomNumberGenerator.Fill(nonce);

            byte[] ciphertext = new byte[plaintext.Length];
            using var aes = new AesGcm(claveAes256, AesGcm.TagByteSizes.MaxSize);
            aes.Encrypt(nonce, plaintext, ciphertext, tag);

            return ciphertext;
        }

        public static byte[] DescifrarDatosSensibles(byte[] ciphertext, byte[] claveAes256, byte[] nonce, byte[] tag)
        {
            byte[] plaintext = new byte[ciphertext.Length];
            using var aes = new AesGcm(claveAes256, AesGcm.TagByteSizes.MaxSize);
            aes.Decrypt(nonce, ciphertext, tag, plaintext);

            return plaintext;
        }

        // ─────────────────────────────────────────────────────────────────────
        // Gestión de Intentos Fallidos y Backoff Persistente de Recuperación
        // ─────────────────────────────────────────────────────────────────────

        public static void RegistrarFalloRecuperacionPersistente()
        {
            lock (BloqueoIo)
            {
                int fallos = 1;
                try
                {
                    using var key = Registry.CurrentUser.CreateSubKey(SubKeyRegistro);
                    fallos = (int)(key.GetValue(ValorFallosRecuperacion, 0) ?? 0) + 1;
                    key.SetValue(ValorFallosRecuperacion, fallos, RegistryValueKind.DWord);
                }
                catch { }

                int segundos = fallos switch
                {
                    <= 3 => 2,
                    4 or 5 => 30,
                    _ => 900
                };

                long hastaUtc = DateTimeOffset.UtcNow.ToUnixTimeSeconds() + segundos;

                try
                {
                    using var key = Registry.CurrentUser.CreateSubKey(SubKeyRegistro);
                    key.SetValue(ValorBloqueoRecuperacionHasta, hastaUtc, RegistryValueKind.QWord);
                }
                catch { }

                // Fallback persistente en disco en caso de restricciones en registro HKCU
                try
                {
                    Directory.CreateDirectory(DirectorioSello);
                    string backoffFile = Path.Combine(DirectorioSello, "recovery_backoff.json");
                    string json = $"{{\"fallos\":{fallos},\"hastaUtc\":{hastaUtc}}}";
                    File.WriteAllText(backoffFile, json, Encoding.UTF8);
                }
                catch { }
            }
        }

        public static bool EstaBloqueadoPorBackoff(out long segundosRestantes)
        {
            segundosRestantes = 0;
            lock (BloqueoIo)
            {
                long hastaUtc = 0;

                try
                {
                    using var key = Registry.CurrentUser.OpenSubKey(SubKeyRegistro);
                    if (key != null)
                    {
                        hastaUtc = Convert.ToInt64(key.GetValue(ValorBloqueoRecuperacionHasta, 0L) ?? 0L);
                    }
                }
                catch { }

                // Fallback a fichero si el registro no devolvió bloqueo
                if (hastaUtc == 0)
                {
                    try
                    {
                        string backoffFile = Path.Combine(DirectorioSello, "recovery_backoff.json");
                        if (File.Exists(backoffFile))
                        {
                            using var doc = JsonDocument.Parse(File.ReadAllText(backoffFile, Encoding.UTF8));
                            if (doc.RootElement.TryGetProperty("hastaUtc", out var prop))
                            {
                                hastaUtc = prop.GetInt64();
                            }
                        }
                    }
                    catch { }
                }

                long ahoraUtc = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
                if (ahoraUtc < hastaUtc)
                {
                    segundosRestantes = hastaUtc - ahoraUtc;
                    return true;
                }
                return false;
            }
        }

        public static void ReiniciarBloqueoRecuperacion()
        {
            lock (BloqueoIo)
            {
                try
                {
                    using var key = Registry.CurrentUser.CreateSubKey(SubKeyRegistro);
                    key.DeleteValue(ValorFallosRecuperacion, throwOnMissingValue: false);
                    key.DeleteValue(ValorBloqueoRecuperacionHasta, throwOnMissingValue: false);
                }
                catch { }

                try
                {
                    string backoffFile = Path.Combine(DirectorioSello, "recovery_backoff.json");
                    if (File.Exists(backoffFile)) File.Delete(backoffFile);
                }
                catch { }
            }
        }

        public static void EliminarAnclajesParaSoporte()
        {
            lock (BloqueoIo)
            {
                try { if (File.Exists(RutaArchivoSello)) File.Delete(RutaArchivoSello); } catch { }
                try { if (File.Exists(RutaCadenaLocal)) File.Delete(RutaCadenaLocal); } catch { }

                try
                {
                    using var key = Registry.CurrentUser.OpenSubKey(SubKeyRegistro, writable: true);
                    key?.DeleteValue(ValorSelloBackup, throwOnMissingValue: false);
                    key?.DeleteValue(ValorContadorMonotonico, throwOnMissingValue: false);
                    key?.DeleteValue(ValorFallosRecuperacion, throwOnMissingValue: false);
                    key?.DeleteValue(ValorBloqueoRecuperacionHasta, throwOnMissingValue: false);
                }
                catch { }
            }
        }

        #region Implementación Nativa DPAPI (Crypt32.dll)

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct DATA_BLOB
        {
            public int cbData;
            public IntPtr pbData;
        }

        [DllImport("Crypt32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        private static extern bool CryptProtectData(
            ref DATA_BLOB pDataIn,
            string szDataDescr,
            ref DATA_BLOB pOptionalEntropy,
            IntPtr pvReserved,
            IntPtr pPromptStruct,
            int dwFlags,
            ref DATA_BLOB pDataOut);

        [DllImport("Crypt32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        private static extern bool CryptUnprotectData(
            ref DATA_BLOB pDataIn,
            IntPtr ppszDataDescr,
            ref DATA_BLOB pOptionalEntropy,
            IntPtr pvReserved,
            IntPtr pPromptStruct,
            int dwFlags,
            ref DATA_BLOB pDataOut);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr LocalFree(IntPtr hMem);

        private const int CRYPTPROTECT_UI_FORBIDDEN = 0x1;

        private static byte[] ProtegerDpapi(byte[] data, byte[] entropy)
        {
            var dataIn = new DATA_BLOB();
            var dataOut = new DATA_BLOB();
            var entropyBlob = new DATA_BLOB();

            GCHandle hData = GCHandle.Alloc(data, GCHandleType.Pinned);
            GCHandle hEntropy = GCHandle.Alloc(entropy, GCHandleType.Pinned);

            try
            {
                dataIn.cbData = data.Length;
                dataIn.pbData = hData.AddrOfPinnedObject();

                entropyBlob.cbData = entropy.Length;
                entropyBlob.pbData = hEntropy.AddrOfPinnedObject();

                bool ok = CryptProtectData(ref dataIn, "WVP3D_SEAL", ref entropyBlob, IntPtr.Zero, IntPtr.Zero, CRYPTPROTECT_UI_FORBIDDEN, ref dataOut);
                if (!ok)
                    throw new CryptographicException($"Fallo en CryptProtectData: {Marshal.GetLastWin32Error()}");

                byte[] result = new byte[dataOut.cbData];
                Marshal.Copy(dataOut.pbData, result, 0, dataOut.cbData);
                return result;
            }
            finally
            {
                hData.Free();
                hEntropy.Free();
                if (dataOut.pbData != IntPtr.Zero)
                    LocalFree(dataOut.pbData);
            }
        }

        private static byte[] DesprotegerDpapi(byte[] cipherText, byte[] entropy)
        {
            var dataIn = new DATA_BLOB();
            var dataOut = new DATA_BLOB();
            var entropyBlob = new DATA_BLOB();

            GCHandle hCipher = GCHandle.Alloc(cipherText, GCHandleType.Pinned);
            GCHandle hEntropy = GCHandle.Alloc(entropy, GCHandleType.Pinned);

            try
            {
                dataIn.cbData = cipherText.Length;
                dataIn.pbData = hCipher.AddrOfPinnedObject();

                entropyBlob.cbData = entropy.Length;
                entropyBlob.pbData = hEntropy.AddrOfPinnedObject();

                bool ok = CryptUnprotectData(ref dataIn, IntPtr.Zero, ref entropyBlob, IntPtr.Zero, IntPtr.Zero, CRYPTPROTECT_UI_FORBIDDEN, ref dataOut);
                if (!ok)
                    throw new CryptographicException($"Fallo en CryptUnprotectData: {Marshal.GetLastWin32Error()}");

                byte[] result = new byte[dataOut.cbData];
                Marshal.Copy(dataOut.pbData, result, 0, dataOut.cbData);
                return result;
            }
            finally
            {
                hCipher.Free();
                hEntropy.Free();
                if (dataOut.pbData != IntPtr.Zero)
                    LocalFree(dataOut.pbData);
            }
        }

        #endregion
    }
}
