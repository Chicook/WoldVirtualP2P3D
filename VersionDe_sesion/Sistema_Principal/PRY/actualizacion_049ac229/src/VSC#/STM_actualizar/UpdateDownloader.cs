using System;
using System.IO;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Update
{
    /// <summary>Progreso de una descarga (bytes recibidos sobre el total).</summary>
    public readonly struct DownloadProgress
    {
        public long BytesReceived { get; }
        public long TotalBytes { get; }
        public double Percentage => TotalBytes > 0 ? (double)BytesReceived / TotalBytes * 100.0 : 0;

        public DownloadProgress(long bytesReceived, long totalBytes)
        {
            BytesReceived = bytesReceived;
            TotalBytes = totalBytes;
        }
    }

    /// <summary>
    /// Descarga el binario de la release en segundo plano (async/await), sin
    /// bloquear la UI, y lo deja preparado para que <see cref="UpdateApplier"/>
    /// lo aplique al cerrar la aplicación.
    /// </summary>
    public class UpdateDownloader
    {
        private readonly string baseDir;

        public string PendingDir => Path.Combine(baseDir, "update-pending");
        public string StateFile => Path.Combine(baseDir, "state.json");

        public UpdateDownloader()
        {
            // En apps single-file, BaseDirectory es la carpeta del .exe.
            baseDir = Path.Combine(AppContext.BaseDirectory, "STM_actualizar");
        }

        /// <summary>
        /// Descarga el asset de la release. Devuelve true sólo si el archivo se
        /// descargó completo y se registró el estado "listo para aplicar".
        /// </summary>
        public async Task<bool> DownloadAsync(ReleaseInfo release,
                                              IProgress<DownloadProgress>? progress = null,
                                              CancellationToken ct = default)
        {
            if (release == null || string.IsNullOrWhiteSpace(release.AssetUrl))
                return false;

            try
            {
                Directory.CreateDirectory(PendingDir);

                // Limpia descargas anteriores para no acumular binarios huérfanos.
                foreach (var f in Directory.GetFiles(PendingDir))
                {
                    try { File.Delete(f); } catch { }
                }

                string nombre = string.IsNullOrWhiteSpace(release.AssetName) ? "update.exe" : release.AssetName!;
                string destino = Path.Combine(PendingDir, nombre);
                string temporal = destino + ".part";

                using var http = new HttpClient { Timeout = TimeSpan.FromMinutes(15) };
                http.DefaultRequestHeaders.UserAgent.ParseAdd("WoldVirtualP2P3D-Updater/1.0");

                using var resp = await http.GetAsync(release.AssetUrl, HttpCompletionOption.ResponseHeadersRead, ct);
                resp.EnsureSuccessStatusCode();

                long total = resp.Content.Headers.ContentLength ?? release.AssetSize;
                long recibido = 0;
                var buffer = new byte[81920];

                await using (var origen = await resp.Content.ReadAsStreamAsync(ct))
                await using (var fs = new FileStream(temporal, FileMode.Create, FileAccess.Write, FileShare.None))
                {
                    int leidos;
                    while ((leidos = await origen.ReadAsync(buffer.AsMemory(0, buffer.Length), ct)) > 0)
                    {
                        await fs.WriteAsync(buffer.AsMemory(0, leidos), ct);
                        recibido += leidos;
                        progress?.Report(new DownloadProgress(recibido, total));
                    }
                    await fs.FlushAsync(ct);
                }

                // Verificación de integridad mínima: si conocemos el tamaño y no
                // coincide, la descarga está corrupta y no debe aplicarse.
                if (total > 0 && recibido != total)
                {
                    try { File.Delete(temporal); } catch { }
                    return false;
                }

                // Renombrado atómico: el .exe sólo "existe" cuando está completo.
                if (File.Exists(destino)) File.Delete(destino);
                File.Move(temporal, destino);

                WriteState(release, nombre);
                return true;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>Marca el estado para que el aplicador externo sepa qué reemplazar.</summary>
        private void WriteState(ReleaseInfo release, string assetName)
        {
            var estado = $$"""
                {
                  "apply": true,
                  "asset": "{{assetName}}",
                  "tag": "{{release.TagName}}",
                  "size": {{release.AssetSize}},
                  "downloadedAt": "{{DateTime.UtcNow:o}}"
                }
                """;
            File.WriteAllText(StateFile, estado);
        }
    }
}
