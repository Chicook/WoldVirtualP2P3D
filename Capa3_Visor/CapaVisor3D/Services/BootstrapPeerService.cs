using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace VisorSingularity.Services
{
    /// <summary>
    /// Nodo semilla (bootstrap peer) de la red WoldVirtual: punto de entrada
    /// conocido para descubrir la malla P2P más allá de la LAN.
    /// </summary>
    public sealed record SeedPeer(string NodeId, string Host, int Port, string? Wallet);

    /// <summary>
    /// Carga la lista de nodos semilla publicada en IPFS bajo un nombre IPNS
    /// fijo (sección 2.5 del plan, "Bootstrap de Red — Internet"). Al arrancar,
    /// el visor resuelve el IPNS vía gateways públicos (sin depender de un Kubo
    /// local ya iniciado), valida las entradas y cachea la última lista buena
    /// para poder reincorporarse a la red incluso sin conectividad a IPFS.
    ///
    /// El parseo y la validación son funciones puras testables sin red.
    /// </summary>
    public sealed class BootstrapPeerService
    {
        // Nombre IPNS fijo de la lista de semillas (placeholder configurable).
        public const string DefaultIpnsName = "k51qzi5uqu5wld-woldvirtual-bootstrap";

        // Gateways IPFS públicos que resuelven rutas /ipns/<name>.
        private static readonly string[] PublicGateways =
        {
            "https://ipfs.io/ipns/",
            "https://dweb.link/ipns/",
            "https://cf-ipfs.com/ipns/",
            "https://4everland.io/ipns/"
        };

        // Límite defensivo del tamaño de la lista descargada.
        private const int MaxListBytes = 256 * 1024; // 256 KB
        private const int MaxSeedPeers = 512;

        // Regex de NodeId: hash de 64 hex o identificador alfanumérico seguro.
        private static readonly Regex NodeIdRegex =
            new("^[a-fA-F0-9]{64}$|^[a-zA-Z0-9_\\-]+$", RegexOptions.Compiled);

        private readonly string _cacheFilePath;
        private readonly string _ipnsName;
        private static readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(8) };

        // La caché usa camelCase para coincidir con el formato de la lista IPNS.
        private static readonly JsonSerializerOptions _cacheJsonOptions = new()
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase
        };

        public BootstrapPeerService(string cacheFilePath, string? ipnsName = null)
        {
            _cacheFilePath = cacheFilePath;
            _ipnsName = string.IsNullOrWhiteSpace(ipnsName) ? DefaultIpnsName : ipnsName!;
        }

        /// <summary>
        /// Obtiene la lista de semillas: intenta resolver el IPNS por cada gateway
        /// público; si lo consigue, refresca la caché; si todos fallan, recurre a
        /// la última lista cacheada. Nunca lanza: devuelve lista vacía en el peor caso.
        /// </summary>
        public async Task<IReadOnlyList<SeedPeer>> GetSeedPeersAsync(CancellationToken token = default)
        {
            foreach (var gateway in PublicGateways)
            {
                var fetched = await TryFetchFromGatewayAsync(gateway, token).ConfigureAwait(false);
                if (fetched != null && fetched.Count > 0)
                {
                    SaveCache(fetched);
                    NetworkTelemetryService.Instance.RecordPacketReceived(fetched.Count);
                    return fetched;
                }
            }

            // Sin conectividad a IPFS: usar la última lista buena conocida.
            return LoadCache();
        }

        private async Task<IReadOnlyList<SeedPeer>?> TryFetchFromGatewayAsync(string gateway, CancellationToken token)
        {
            try
            {
                string url = gateway + _ipnsName;
                using var resp = await _http.GetAsync(url, HttpCompletionOption.ResponseHeadersRead, token)
                    .ConfigureAwait(false);
                if (!resp.IsSuccessStatusCode) return null;

                byte[] data = await resp.Content.ReadAsByteArrayAsync(token).ConfigureAwait(false);
                if (data.Length == 0 || data.Length > MaxListBytes) return null;

                string json = System.Text.Encoding.UTF8.GetString(data);
                return ParseSeedList(json);
            }
            catch (Exception)
            {
                // Gateway caído/bloqueado: el llamador probará el siguiente.
                return null;
            }
        }

        // ── Parseo y validación (puro, testable) ──────────────────────────────

        /// <summary>
        /// Parsea el JSON de la lista de semillas y devuelve solo las entradas
        /// válidas. Formato esperado:
        /// <code>{ "version":"1.0", "peers":[ {"nodeId","host","port","wallet"} ] }</code>
        /// </summary>
        public static IReadOnlyList<SeedPeer> ParseSeedList(string json)
        {
            var result = new List<SeedPeer>();
            if (string.IsNullOrWhiteSpace(json)) return result;

            try
            {
                using var doc = JsonDocument.Parse(json);
                if (doc.RootElement.ValueKind != JsonValueKind.Object) return result;
                if (!doc.RootElement.TryGetProperty("peers", out var peersEl) ||
                    peersEl.ValueKind != JsonValueKind.Array)
                {
                    return result;
                }

                foreach (var item in peersEl.EnumerateArray())
                {
                    if (result.Count >= MaxSeedPeers) break;
                    var seed = ParseSeedEntry(item);
                    if (seed != null) result.Add(seed);
                }
            }
            catch (JsonException)
            {
                // JSON corrupto: devolvemos lo acumulado (posiblemente vacío).
            }

            return result;
        }

        private static SeedPeer? ParseSeedEntry(JsonElement item)
        {
            if (item.ValueKind != JsonValueKind.Object) return null;

            string nodeId = GetString(item, "nodeId");
            string host = GetString(item, "host");
            if (!IsValidNodeId(nodeId) || !IsValidHost(host)) return null;

            int port = 0;
            if (item.TryGetProperty("port", out var portEl) &&
                portEl.ValueKind == JsonValueKind.Number &&
                portEl.TryGetInt32(out int p))
            {
                port = p;
            }
            if (port <= 0 || port > 65535) return null;

            string? wallet = GetString(item, "wallet");
            if (string.IsNullOrEmpty(wallet)) wallet = null;

            return new SeedPeer(nodeId, host, port, wallet);
        }

        /// <summary>Valida el NodeId contra el mismo criterio que PeerSyncService.</summary>
        public static bool IsValidNodeId(string nodeId)
        {
            return !string.IsNullOrEmpty(nodeId) && NodeIdRegex.IsMatch(nodeId);
        }

        /// <summary>
        /// Valida el host: no vacío y sin caracteres de separación de ruta ni
        /// secuencias de salto, para evitar inyección al persistir la caché.
        /// </summary>
        public static bool IsValidHost(string host)
        {
            if (string.IsNullOrWhiteSpace(host)) return false;
            if (host.Contains('/') || host.Contains('\\') || host.Contains("..")) return false;
            return host.Length <= 253; // límite de longitud de hostname
        }

        // ── Caché local ───────────────────────────────────────────────────────

        /// <summary>Guarda la lista en disco como respaldo para bootstrap offline.</summary>
        public void SaveCache(IReadOnlyList<SeedPeer> peers)
        {
            try
            {
                var dir = Path.GetDirectoryName(_cacheFilePath);
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

                var payload = new { version = "1.0", cachedAt = DateTimeOffset.UtcNow, peers };
                string json = JsonSerializer.Serialize(payload, _cacheJsonOptions);
                File.WriteAllText(_cacheFilePath, json);
            }
            catch (Exception)
            {
                // La caché es best-effort; un fallo de escritura no es crítico.
            }
        }

        /// <summary>Carga la última lista cacheada, o vacía si no existe/corrupta.</summary>
        public IReadOnlyList<SeedPeer> LoadCache()
        {
            try
            {
                if (!File.Exists(_cacheFilePath)) return Array.Empty<SeedPeer>();
                string json = File.ReadAllText(_cacheFilePath);
                return ParseSeedList(json);
            }
            catch (Exception)
            {
                return Array.Empty<SeedPeer>();
            }
        }

        // ── Helpers ───────────────────────────────────────────────────────────

        private static string GetString(JsonElement obj, string property)
        {
            if (obj.TryGetProperty(property, out var el) && el.ValueKind == JsonValueKind.String)
            {
                return el.GetString() ?? string.Empty;
            }
            return string.Empty;
        }
    }
}
