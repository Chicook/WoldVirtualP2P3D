using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

namespace VisorSingularity
{
    /// <summary>
    /// Publica directorios o archivos en la red IPFS a través de la CLI de Kubo y
    /// proporciona URLs de acceso mediante gateways públicos descentralizados.
    /// </summary>
    public class IpfsPublisher
    {
        // ─── Gateways públicos (ordenados por fiabilidad y resiliencia ante bloqueos) ─────────────────────
        public static readonly string[] PublicGateways =
        {
            "https://4everland.io/ipfs/",
            "https://w3s.link/ipfs/",
            "https://ipfs.eth.aragon.network/ipfs/",
            "https://cf-ipfs.com/ipfs/",
            "https://storry.tv/ipfs/",
            "https://ipfs.io/ipfs/",
            "https://cloudflare-ipfs.com/ipfs/",
            "https://dweb.link/ipfs/",
            "https://gateway.pinata.cloud/ipfs/"
        };

        // ─── Estado ───────────────────────────────────────────────────────────
        private readonly IpfsManager _manager;

        /// <summary>Último CID (v1, base32) publicado.</summary>
        public string? LastCid { get; private set; }

        /// <summary>URI nativa IPFS: ipfs://&lt;CID&gt;</summary>
        public string? IpfsUri => LastCid != null ? $"ipfs://{LastCid}" : null;

        /// <summary>URL del gateway local Kubo.</summary>
        public string? LocalGatewayUrl =>
            LastCid != null ? $"{IpfsManager.GatewayUrl}/ipfs/{LastCid}" : null;

        /// <summary>Lista completa de URLs (local primero, luego públicos).</summary>
        public List<string> AllGatewayUrls { get; } = new();

        /// <summary>Evento de log de estado para la UI.</summary>
        public event Action<string>? OnStatusChanged;

        // ─── Constructor ──────────────────────────────────────────────────────
        public IpfsPublisher(IpfsManager manager)
        {
            _manager                  = manager;
            _manager.OnStatusChanged += msg => OnStatusChanged?.Invoke(msg);
        }

        // ─── API Pública ──────────────────────────────────────────────────────

        /// <summary>
        /// Añade un archivo a IPFS.
        /// Devuelve el CID o null si falla.
        /// </summary>
        public async Task<string?> PublishFileAsync(
            string filePath, CancellationToken token = default)
        {
            if (!File.Exists(filePath))
            {
                LogStatus($"⚠️ Archivo no encontrado para publicar en IPFS: {filePath}");
                return null;
            }

            LogStatus($"📤 Añadiendo archivo a IPFS: {Path.GetFileName(filePath)}...");

            // --quieter devuelve solo el CID (última línea).
            // --cid-version=1 genera CIDs v1 (base32).
            string rawOutput = await _manager.RunCliAsync(
                $"add --quieter --cid-version=1 \"{filePath}\"",
                token);

            if (string.IsNullOrWhiteSpace(rawOutput))
            {
                LogStatus("⚠️ IPFS no devolvió un CID válido.");
                return null;
            }

            string[] lines = rawOutput.Split('\n', StringSplitOptions.RemoveEmptyEntries);
            LastCid         = lines[^1].Trim();

            LogStatus($"✅ Archivo publicado en IPFS — CID: {LastCid}");

            RebuildGatewayUrls();

            return LastCid;
        }

        /// <summary>
        /// Añade un directorio completo a IPFS de forma recursiva.
        /// Devuelve el CID raíz o null si falla.
        /// </summary>
        /// <param name="dirPath">Ruta local del directorio a publicar.</param>
        /// <param name="token">Token de cancelación.</param>
        public async Task<string?> PublishDirectoryAsync(
            string dirPath, CancellationToken token = default)
        {
            if (!Directory.Exists(dirPath))
            {
                LogStatus($"⚠️ Directorio no encontrado para publicar en IPFS: {dirPath}");
                return null;
            }

            LogStatus($"📤 Añadiendo directorio a IPFS: {Path.GetFileName(dirPath)}/");

            // --quieter devuelve solo el CID raíz (última línea).
            // --cid-version=1 genera CIDs v1 (base32), más modernos.
            string rawOutput = await _manager.RunCliAsync(
                $"add --recursive --quieter --cid-version=1 \"{dirPath}\"",
                token);

            if (string.IsNullOrWhiteSpace(rawOutput))
            {
                LogStatus("⚠️ IPFS no devolvió un CID válido.");
                return null;
            }

            // Tomar solo la última línea (CID raíz)
            string[] lines = rawOutput.Split('\n', StringSplitOptions.RemoveEmptyEntries);
            LastCid         = lines[^1].Trim();

            LogStatus($"✅ Contenido publicado en IPFS — CID: {LastCid}");

            // Construir lista de URLs de acceso
            RebuildGatewayUrls();

            LogStatus($"🔗 Gateway local: {LocalGatewayUrl}");
            LogStatus($"🌍 Gateway público: https://ipfs.io/ipfs/{LastCid}");

            return LastCid;
        }

        /// <summary>
        /// Fija un CID localmente para que no sea eliminado por el GC de IPFS.
        /// </summary>
        public async Task PinAsync(string cid, CancellationToken token = default)
        {
            LogStatus($"📌 Fijando CID en el nodo local: {cid}");
            await _manager.RunCliAsync($"pin add {cid}", token);
            LogStatus($"✅ CID fijado localmente: {cid}");
        }

        /// <summary>
        /// Publica y fija en un solo paso.
        /// </summary>
        public async Task<string?> PublishAndPinAsync(
            string filePath, CancellationToken token = default)
        {
            string? cid = await PublishFileAsync(filePath, token);
            if (cid != null)
                await PinAsync(cid, token);
            return cid;
        }

        /// <summary>
        /// Devuelve el primer gateway público disponible para el último CID.
        /// Útil para abrir en el navegador.
        /// </summary>
        public string? GetBestPublicUrl()
        {
            if (LastCid == null) return null;
            return $"https://ipfs.io/ipfs/{LastCid}";
        }

        // ─── Métodos Privados ─────────────────────────────────────────────────

        private void RebuildGatewayUrls()
        {
            AllGatewayUrls.Clear();

            if (LastCid == null) return;

            // Gateway local siempre primero
            AllGatewayUrls.Add($"{IpfsManager.GatewayUrl}/ipfs/{LastCid}");

            // Gateways públicos
            foreach (string gw in PublicGateways)
            {
                AllGatewayUrls.Add(gw + LastCid);
            }
        }

        private void LogStatus(string msg) => OnStatusChanged?.Invoke(msg);
    }
}
