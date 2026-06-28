using System;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace VisorSingularity
{
    /// <summary>
    /// Esquema tipado formalizado para los archivos peer_*.json compartidos entre C# (Visor WPF)
    /// y Godot (NetworkLayer.gd). Este contrato asegura compatibilidad bidireccional y es la
    /// fuente única de verdad para la estructura de datos de sincronización P2P.
    ///
    /// Estructura del JSON:
    /// <code>
    /// {
    ///   "u": { "peerId": { "x":0,"y":0,"z":0, "rx":0,"ry":0,"rz":0, "a":"idle", "t":1719568800.0 } },
    ///   "i": { "peerId": { "name":"Isla1", "cx":0, "cy":0 } },
    ///   "e": [ { "type":"chat", "msg":"Hola", "ts":1719568800.0 } ],
    ///   "ts": "2026-06-28T12:00:00",
    ///   "v": "1.0"
    /// }
    /// </code>
    /// </summary>
    public static class PeerSchema
    {
        /// <summary>Versión actual del esquema. Godot escribe "1.0" en el campo "v".</summary>
        public const string SchemaVersion = "1.0";

        /// <summary>Tamaño máximo permitido para un peer JSON en bytes (seguridad).</summary>
        public const int MaxPeerSizeBytes = 65536;

        /// <summary>Número máximo de peers almacenados simultáneamente en disco.</summary>
        public const int MaxPeersOnDisk = 100;

        /// <summary>Nombre de la carpeta de peers relativa al Estado_Global.</summary>
        public const string PeersFolderName = "peers";

        /// <summary>Prefijo de los archivos de peer en disco.</summary>
        public const string PeerFilePrefix = "peer_";

        /// <summary>Extensión de los archivos de peer.</summary>
        public const string PeerFileExtension = ".json";

        /// <summary>
        /// Valida que un JSON de peer tenga la estructura mínima requerida:
        /// un diccionario raíz con al menos un bloque "u" (usuarios) o "i" (islas).
        /// </summary>
        /// <param name="json">Cadena JSON a validar.</param>
        /// <param name="peerId">Si es válido, contiene el ID del peer extraído del bloque "u" o "i".</param>
        /// <returns>True si el JSON cumple el esquema mínimo.</returns>
        public static bool TryValidate(string json, out string peerId)
        {
            peerId = string.Empty;

            if (string.IsNullOrWhiteSpace(json) || !json.TrimStart().StartsWith("{"))
                return false;

            if (System.Text.Encoding.UTF8.GetByteCount(json) > MaxPeerSizeBytes)
                return false;

            try
            {
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                if (root.TryGetProperty("did", out var didEl) && didEl.ValueKind == JsonValueKind.String)
                {
                    string did = didEl.GetString() ?? "";
                    if (TryGetPeerIdFromDid(did, out string didPeerId))
                    {
                        if (HasPeerKey(root, didPeerId))
                        {
                            peerId = didPeerId;
                            return IsValidPeerId(peerId);
                        }
                    }
                }

                // Extraer ID del primer key del bloque "u" (usuarios)
                if (root.TryGetProperty("u", out var usersEl) && usersEl.ValueKind == JsonValueKind.Object)
                {
                    foreach (var prop in usersEl.EnumerateObject())
                    {
                        peerId = prop.Name;

                        // Validar que el bloque de usuario tenga al menos el campo "t" (timestamp)
                        if (prop.Value.ValueKind == JsonValueKind.Object &&
                            prop.Value.TryGetProperty("t", out var tEl) &&
                            (tEl.ValueKind == JsonValueKind.Number))
                        {
                            return IsValidPeerId(peerId);
                        }

                        // Aceptar aunque no tenga "t" (compatibilidad con versiones anteriores)
                        return IsValidPeerId(peerId);
                    }
                }

                // Fallback: extraer del bloque "i" (islas) si no hay usuarios
                if (root.TryGetProperty("i", out var islandsEl) && islandsEl.ValueKind == JsonValueKind.Object)
                {
                    foreach (var prop in islandsEl.EnumerateObject())
                    {
                        peerId = prop.Name;
                        return IsValidPeerId(peerId);
                    }
                }

                return false;
            }
            catch (JsonException)
            {
                return false;
            }
        }

        /// <summary>
        /// Valida que un ID de peer solo contenga caracteres seguros y no sea susceptible
        /// a Path Traversal. Caracteres permitidos: alfanumérico, '-', '_', ':', '.'
        /// </summary>
        public static bool IsValidPeerId(string id)
        {
            if (string.IsNullOrEmpty(id) || id.Length > 128)
                return false;

            if (id.Contains("..") || id.Contains("/") || id.Contains("\\"))
                return false;

            foreach (char c in id)
            {
                if (!char.IsLetterOrDigit(c) && c != '-' && c != '_' && c != '.')
                    return false;
            }

            return true;
        }

        public static bool TryGetPeerIdFromDid(string did, out string peerId)
        {
            peerId = string.Empty;
            if (string.IsNullOrWhiteSpace(did)) return false;

            if (!did.StartsWith("did:wcv:0x", StringComparison.OrdinalIgnoreCase)) return false;
            string addr = did.Substring("did:wcv:".Length);
            if (!addr.StartsWith("0x", StringComparison.OrdinalIgnoreCase)) return false;
            addr = addr.Substring(2);
            if (addr.Length != 40) return false;

            foreach (char c in addr)
                if (!Uri.IsHexDigit(c)) return false;

            peerId = "did_wcv_0x" + addr.ToLowerInvariant();
            return IsValidPeerId(peerId);
        }

        public static bool TryGetDidFromPeerId(string peerId, out string did)
        {
            did = string.Empty;
            if (string.IsNullOrWhiteSpace(peerId)) return false;
            if (!peerId.StartsWith("did_wcv_0x", StringComparison.Ordinal)) return false;
            string addr = peerId.Substring("did_wcv_".Length);
            if (!addr.StartsWith("0x", StringComparison.Ordinal)) return false;
            addr = addr.Substring(2);
            if (addr.Length != 40) return false;
            foreach (char c in addr)
                if (!Uri.IsHexDigit(c)) return false;
            did = "did:wcv:0x" + addr.ToLowerInvariant();
            return true;
        }

        /// <summary>
        /// Genera un nombre de archivo de peer seguro a partir de un ID validado.
        /// Ejemplo: "abc123" → "peer_abc123.json"
        /// </summary>
        public static string GetPeerFileName(string validatedId)
            => $"{PeerFilePrefix}{validatedId}{PeerFileExtension}";

        /// <summary>
        /// Extrae el ID de un peer a partir del nombre del archivo.
        /// Ejemplo: "peer_abc123.json" → "abc123"
        /// Devuelve null si el nombre no cumple el formato esperado.
        /// </summary>
        public static string? ExtractPeerIdFromFileName(string fileName)
        {
            if (string.IsNullOrEmpty(fileName)) return null;

            // Obtener solo el nombre de archivo sin la ruta
            string name = System.IO.Path.GetFileName(fileName);

            if (!name.StartsWith(PeerFilePrefix, StringComparison.Ordinal) ||
                !name.EndsWith(PeerFileExtension, StringComparison.Ordinal))
                return null;

            string id = name.Substring(
                PeerFilePrefix.Length,
                name.Length - PeerFilePrefix.Length - PeerFileExtension.Length);

            return IsValidPeerId(id) ? id : null;
        }

        private static bool HasPeerKey(JsonElement root, string peerId)
        {
            if (root.TryGetProperty("u", out var usersEl) && usersEl.ValueKind == JsonValueKind.Object)
                if (usersEl.TryGetProperty(peerId, out _))
                    return true;

            if (root.TryGetProperty("i", out var islandsEl) && islandsEl.ValueKind == JsonValueKind.Object)
                if (islandsEl.TryGetProperty(peerId, out _))
                    return true;

            return false;
        }
    }
}
