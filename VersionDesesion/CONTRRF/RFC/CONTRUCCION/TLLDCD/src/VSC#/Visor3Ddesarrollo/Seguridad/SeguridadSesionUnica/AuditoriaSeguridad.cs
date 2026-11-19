// AuditoriaSeguridad.cs — Registro de auditoría de seguridad append-only con cadena HMAC.
// Cada entrada incluye timestamp, evento, actor, resultado y el hash de la entrada anterior,
// formando una cadena verificable. La clave HMAC se obtiene del secreto maestro de AlmacenSeguro.
// Log file: %LOCALAPPDATA%\WoldVirtualP2P3D\AuditLog\security_audit.jsonl
// Rotación cada 30 días; el hash del último bloque del fichero antiguo se embebe en el nuevo.
// ZeroMemory sobre arrays de clave al salir de cada operación.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;

namespace Visor3D.Seguridad.SesionUnica
{
    // ---------------------------------------------------------------------------
    // Enum de eventos auditables
    // ---------------------------------------------------------------------------
    public enum EventoAuditoria
    {
        InicioVerificacion,
        SelloValido,
        SelloAutorreparado,
        RollbackDetectado,
        ManipulacionDetectada,
        NuevoRegistro,
        BloqueoCuenta,
        RecuperacionSolicitada,
        OperacionIPC,
        ErrorCritico,
        AtestacionPlataforma,
        CambioHardware
    }

    // ---------------------------------------------------------------------------
    // Motor de auditoría principal
    // ---------------------------------------------------------------------------
    public static class AuditoriaSeguridad
    {
        // -----------------------------------------------------------------------
        // Constantes y rutas
        // -----------------------------------------------------------------------
        private const string AppFolder      = "WoldVirtualP2P3D";
        private const string AuditSubfolder = "AuditLog";
        private const string LogFileName    = "security_audit.jsonl";
        private const int    RotacionDias   = 30;

        // -----------------------------------------------------------------------
        // Estado interno (thread-safe)
        // -----------------------------------------------------------------------
        private static readonly object _lock = new object();

        /// <summary>
        /// Ruta completa del fichero de log activo.
        /// </summary>
        private static string LogFilePath
        {
            get
            {
                string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                return Path.Combine(localAppData, AppFolder, AuditSubfolder, LogFileName);
            }
        }

        // -----------------------------------------------------------------------
        // Punto de entrada público: Registrar
        // -----------------------------------------------------------------------

        /// <summary>
        /// Añade una entrada de auditoría a la cadena append-only.
        /// Thread-safe; nunca lanza excepciones.
        /// </summary>
        public static void Registrar(
            EventoAuditoria evento,
            string          actor,
            string          resultado,
            string?         detalle = null)
        {
            try
            {
                lock (_lock)
                {
                    EnsureDirectoryExists();
                    RotarSiNecesario();

                    string prevHash = ObtenerUltimoHash();
                    string ts       = DateTime.UtcNow.ToString("O"); // ISO 8601

                    byte[]? secreto = ObtenerSecretoMaestro();
                    string  mac     = ComputarMac(secreto, prevHash, ts, evento.ToString(), actor, resultado);
                    ZeroMemory(secreto);

                    string json = BuildJson(ts, evento, actor, resultado, detalle, prevHash, mac);
                    File.AppendAllText(LogFilePath, json + "\n", Encoding.UTF8);
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AuditoriaSeguridad] Registrar error: {ex.Message}");
            }
        }

        // -----------------------------------------------------------------------
        // Verificación de integridad de la cadena completa
        // -----------------------------------------------------------------------

        /// <summary>
        /// Recorre todas las entradas del fichero activo y verifica que la cadena
        /// de hashes prev_hash/mac sea consistente.
        /// Devuelve true si la cadena está íntegra.
        /// </summary>
        public static bool VerificarIntegridadCadena()
        {
            try
            {
                lock (_lock)
                {
                    if (!File.Exists(LogFilePath))
                        return true; // sin fichero, no hay manipulación

                    string[] lineas = File.ReadAllLines(LogFilePath, Encoding.UTF8);
                    if (lineas.Length == 0)
                        return true;

                    byte[]? secreto = ObtenerSecretoMaestro();

                    string hashAnterior = string.Empty; // primera entrada tiene prev_hash vacío

                    foreach (string linea in lineas)
                    {
                        string trimmed = linea.Trim();
                        if (string.IsNullOrEmpty(trimmed))
                            continue;

                        if (!ParseEntry(trimmed,
                                out string ts,
                                out string evento,
                                out string actor,
                                out string resultado,
                                out string prevHashLeido,
                                out string macLeido))
                        {
                            ZeroMemory(secreto);
                            Debug.WriteLine("[AuditoriaSeguridad] VerificarIntegridadCadena: línea no parseable");
                            return false;
                        }

                        // Verificar que prev_hash coincide con el hash calculado de la entrada anterior
                        if (!string.Equals(prevHashLeido, hashAnterior, StringComparison.Ordinal))
                        {
                            ZeroMemory(secreto);
                            Debug.WriteLine("[AuditoriaSeguridad] VerificarIntegridadCadena: ruptura en prev_hash");
                            return false;
                        }

                        // Verificar MAC
                        string macEsperado = ComputarMac(secreto, prevHashLeido, ts, evento, actor, resultado);
                        if (!string.Equals(macLeido, macEsperado, StringComparison.Ordinal))
                        {
                            ZeroMemory(secreto);
                            Debug.WriteLine("[AuditoriaSeguridad] VerificarIntegridadCadena: MAC inválido");
                            return false;
                        }

                        // El hash de esta entrada se convierte en el prev_hash de la siguiente
                        hashAnterior = ComputarHashEntrada(trimmed);
                    }

                    ZeroMemory(secreto);
                    return true;
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AuditoriaSeguridad] VerificarIntegridadCadena error: {ex.Message}");
                return false;
            }
        }

        // -----------------------------------------------------------------------
        // Diagnóstico: últimas N entradas en bruto (JSON lines)
        // -----------------------------------------------------------------------

        /// <summary>
        /// Devuelve las últimas <paramref name="n"/> líneas del log activo (JSON bruto).
        /// Para diagnóstico; nunca lanza.
        /// </summary>
        public static IReadOnlyList<string> ObtenerUltimasEntradas(int n = 20)
        {
            try
            {
                lock (_lock)
                {
                    if (!File.Exists(LogFilePath))
                        return Array.Empty<string>();

                    string[] lineas = File.ReadAllLines(LogFilePath, Encoding.UTF8);

                    // Filtrar líneas vacías y tomar las últimas n
                    var resultado = new List<string>(Math.Min(n, lineas.Length));
                    int inicio    = Math.Max(0, lineas.Length - n);
                    for (int i = inicio; i < lineas.Length; i++)
                    {
                        string l = lineas[i].Trim();
                        if (!string.IsNullOrEmpty(l))
                            resultado.Add(l);
                    }

                    return resultado.AsReadOnly();
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AuditoriaSeguridad] ObtenerUltimasEntradas error: {ex.Message}");
                return Array.Empty<string>();
            }
        }

        // -----------------------------------------------------------------------
        // Privados: infraestructura de fichero
        // -----------------------------------------------------------------------

        private static void EnsureDirectoryExists()
        {
            string? dir = Path.GetDirectoryName(LogFilePath);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                Directory.CreateDirectory(dir);
        }

        /// <summary>
        /// Si el fichero activo supera <see cref="RotacionDias"/> días de antigüedad,
        /// lo renombra y empieza uno nuevo. El hash del último bloque del fichero
        /// antiguo se embebe como primera entrada del nuevo (tipo "NuevoRegistro").
        /// </summary>
        private static void RotarSiNecesario()
        {
            try
            {
                if (!File.Exists(LogFilePath))
                    return;

                DateTime created = File.GetCreationTimeUtc(LogFilePath);
                if ((DateTime.UtcNow - created).TotalDays < RotacionDias)
                    return;

                // Calcular el hash del último bloque del fichero antiguo
                string ultimoHashViejo = ObtenerUltimoHash();

                // Renombrar fichero antiguo
                string? dir       = Path.GetDirectoryName(LogFilePath)!;
                string  timestamp = created.ToString("yyyyMMdd_HHmmss");
                string  archivado = Path.Combine(dir, $"security_audit_{timestamp}.jsonl");
                File.Move(LogFilePath, archivado);

                // Primera entrada del nuevo fichero: referencia al cierre del anterior
                string ts   = DateTime.UtcNow.ToString("O");
                byte[]? sec = ObtenerSecretoMaestro();
                string mac  = ComputarMac(sec, ultimoHashViejo, ts,
                                          EventoAuditoria.NuevoRegistro.ToString(),
                                          "sistema", "rotacion");
                ZeroMemory(sec);

                string json = BuildJson(ts, EventoAuditoria.NuevoRegistro,
                                        "sistema", "rotacion",
                                        $"fichero_anterior={Path.GetFileName(archivado)};ultimo_hash={ultimoHashViejo}",
                                        ultimoHashViejo, mac);
                File.AppendAllText(LogFilePath, json + "\n", Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AuditoriaSeguridad] RotarSiNecesario error: {ex.Message}");
            }
        }

        // -----------------------------------------------------------------------
        // Privados: hash y HMAC
        // -----------------------------------------------------------------------

        /// <summary>
        /// Devuelve el hash SHA-256 (hex) de la última línea del fichero activo,
        /// o string.Empty si el fichero no existe o está vacío.
        /// </summary>
        private static string ObtenerUltimoHash()
        {
            try
            {
                if (!File.Exists(LogFilePath))
                    return string.Empty;

                // Leer la última línea no vacía
                string ultimaLinea = string.Empty;
                using (FileStream fs = new FileStream(LogFilePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (StreamReader sr = new StreamReader(fs, Encoding.UTF8))
                {
                    string? linea;
                    while ((linea = sr.ReadLine()) != null)
                    {
                        string trimmed = linea.Trim();
                        if (!string.IsNullOrEmpty(trimmed))
                            ultimaLinea = trimmed;
                    }
                }

                if (string.IsNullOrEmpty(ultimaLinea))
                    return string.Empty;

                return ComputarHashEntrada(ultimaLinea);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AuditoriaSeguridad] ObtenerUltimoHash error: {ex.Message}");
                return string.Empty;
            }
        }

        /// <summary>
        /// SHA-256 del contenido bruto de una entrada (hex lowercase).
        /// </summary>
        private static string ComputarHashEntrada(string entradaJson)
        {
            byte[] bytes = Encoding.UTF8.GetBytes(entradaJson);
            byte[] hash  = SHA256.HashData(bytes);
            return Convert.ToHexString(hash).ToLowerInvariant();
        }

        /// <summary>
        /// HMACSHA256(secreto, prevHash + ts + evento + actor + resultado) → hex lowercase.
        /// Si secreto es null/vacío, usa una clave de emergencia derivada del nombre de máquina
        /// (nunca lanza, pero la seguridad se degrada).
        /// </summary>
        private static string ComputarMac(
            byte[]? secreto,
            string  prevHash,
            string  ts,
            string  evento,
            string  actor,
            string  resultado)
        {
            byte[] clave = (secreto != null && secreto.Length > 0)
                ? secreto
                : Encoding.UTF8.GetBytes(Environment.MachineName + "_fallback_audit_key");

            byte[] payload = Encoding.UTF8.GetBytes(prevHash + ts + evento + actor + resultado);

            using HMACSHA256 hmac = new HMACSHA256(clave);
            byte[] hash = hmac.ComputeHash(payload);
            return Convert.ToHexString(hash).ToLowerInvariant();
        }

        // -----------------------------------------------------------------------
        // Privados: secreto maestro
        // -----------------------------------------------------------------------

        /// <summary>
        /// Obtiene el secreto maestro de <see cref="AlmacenSeguro"/>.
        /// Devuelve null si no está disponible (modo degradado).
        /// </summary>
        private static byte[]? ObtenerSecretoMaestro()
        {
            try
            {
                // AlmacenSeguro.ObtenerSecretoMaestro() se define en el mismo namespace.
                return AlmacenSeguro.ObtenerOcrearSecretoMaestro();
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[AuditoriaSeguridad] ObtenerSecretoMaestro error: {ex.Message}");
                return null;
            }
        }

        // -----------------------------------------------------------------------
        // Privados: ZeroMemory
        // -----------------------------------------------------------------------

        /// <summary>
        /// Pone a cero los bytes del array de clave para minimizar la exposición
        /// en memoria. No-op si el array es null.
        /// </summary>
        [MethodImpl(MethodImplOptions.NoInlining | MethodImplOptions.NoOptimization)]
        private static void ZeroMemory(byte[]? data)
        {
            if (data == null || data.Length == 0)
                return;

            // Usar CryptographicOperations.ZeroMemory si está disponible (.NET 5+)
            CryptographicOperations.ZeroMemory(data.AsSpan());
        }

        // -----------------------------------------------------------------------
        // Privados: serialización JSON manual (sin dependencias externas)
        // -----------------------------------------------------------------------

        private static string BuildJson(
            string          ts,
            EventoAuditoria evento,
            string          actor,
            string          resultado,
            string?         detalle,
            string          prevHash,
            string          mac)
        {
            var sb = new StringBuilder();
            sb.Append('{');
            AppendJsonField(sb, "ts",        ts,              first: true);
            AppendJsonField(sb, "evento",    evento.ToString());
            AppendJsonField(sb, "actor",     actor);
            AppendJsonField(sb, "resultado", resultado);
            if (detalle != null)
                AppendJsonField(sb, "detalle", detalle);
            AppendJsonField(sb, "prev_hash", prevHash);
            AppendJsonField(sb, "mac",       mac);
            sb.Append('}');
            return sb.ToString();
        }

        private static void AppendJsonField(
            StringBuilder sb,
            string        key,
            string        value,
            bool          first = false)
        {
            if (!first) sb.Append(',');
            sb.Append('"');
            sb.Append(EscapeJson(key));
            sb.Append("\":\"");
            sb.Append(EscapeJson(value));
            sb.Append('"');
        }

        private static string EscapeJson(string s)
        {
            if (string.IsNullOrEmpty(s)) return string.Empty;
            return s
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\n",  "\\n")
                .Replace("\r",  "\\r")
                .Replace("\t",  "\\t");
        }

        // -----------------------------------------------------------------------
        // Privados: parser JSON mínimo para verificación
        // -----------------------------------------------------------------------

        /// <summary>
        /// Extrae los campos necesarios de una línea JSON de auditoría.
        /// Parser mínimo sin dependencias externas; espera el formato exacto
        /// producido por <see cref="BuildJson"/>.
        /// </summary>
        private static bool ParseEntry(
            string  line,
            out string ts,
            out string evento,
            out string actor,
            out string resultado,
            out string prevHash,
            out string mac)
        {
            ts = evento = actor = resultado = prevHash = mac = string.Empty;

            try
            {
                ts        = ExtractJsonStringField(line, "ts");
                evento    = ExtractJsonStringField(line, "evento");
                actor     = ExtractJsonStringField(line, "actor");
                resultado = ExtractJsonStringField(line, "resultado");
                prevHash  = ExtractJsonStringField(line, "prev_hash");
                mac       = ExtractJsonStringField(line, "mac");

                return !string.IsNullOrEmpty(ts) &&
                       !string.IsNullOrEmpty(evento) &&
                       !string.IsNullOrEmpty(actor) &&
                       !string.IsNullOrEmpty(resultado) &&
                       !string.IsNullOrEmpty(mac);
            }
            catch
            {
                return false;
            }
        }

        /// <summary>
        /// Extrae el valor de un campo string de un JSON plano:
        ///   "campo":"valor"
        /// </summary>
        private static string ExtractJsonStringField(string json, string fieldName)
        {
            string key   = $"\"{fieldName}\":\"";
            int    start = json.IndexOf(key, StringComparison.Ordinal);
            if (start < 0) return string.Empty;

            start += key.Length;
            int end = start;

            // Buscar la comilla de cierre respetando los escapes
            while (end < json.Length)
            {
                if (json[end] == '\\')
                {
                    end += 2; // saltar carácter escapado
                    continue;
                }
                if (json[end] == '"')
                    break;
                end++;
            }

            if (end >= json.Length) return string.Empty;

            string raw = json.Substring(start, end - start);

            // Desescapar secuencias básicas
            return raw
                .Replace("\\\"", "\"")
                .Replace("\\\\", "\\")
                .Replace("\\n",  "\n")
                .Replace("\\r",  "\r")
                .Replace("\\t",  "\t");
        }
    }
}
