using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text.Json;
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
    /// Descarga el binario de la release en segundo plano (async/await), con
    /// reanudación por rangos, verificación SHA-256 y estado "listo para aplicar".
    /// </summary>
    public class UpdateDownloader
    {
        private readonly string baseDir;
        private readonly HttpMessageHandler? customHandler;

        public string PendingDir => Path.Combine(baseDir, "update-pending");
        public string StateFile => Path.Combine(baseDir, "state.json");

        /// <summary>Último error legible (para mostrarlo en el botón, sin MessageBox).</summary>
        public string? LastError { get; private set; }

        public UpdateDownloader(string? customBaseDir = null, HttpMessageHandler? customHandler = null)
        {
            // En apps single-file, BaseDirectory es la carpeta del .exe.
            // Para pruebas herméticas (H2 / selftests), se puede inyectar una ruta temporal y un handler falso.
            baseDir = customBaseDir ?? Path.Combine(AppContext.BaseDirectory, "STM_actualizar");
            this.customHandler = customHandler;
        }

        /// <summary>
        /// Descarga el asset de la release. Devuelve true sólo si el archivo se
        /// descargó completo, su SHA-256 coincide con el publicado y se registró
        /// el estado "listo para aplicar".
        /// </summary>
        public async Task<bool> DownloadAsync(ReleaseInfo release,
                                              IProgress<DownloadProgress>? progress = null,
                                              CancellationToken ct = default)
        {
            LastError = null;

            if (release == null || string.IsNullOrWhiteSpace(release.AssetUrl))
            {
                LastError = "La release no tiene un binario descargable.";
                return false;
            }

            try
            {
                Directory.CreateDirectory(PendingDir);

                // Un intento nuevo invalida el estado anterior: si queda "apply": true
                // de una descarga vieja, el aplicador podría intentar aplicar un fichero
                // que ya no existe.
                try { if (File.Exists(StateFile)) File.Delete(StateFile); } catch { }

                // Comprobación temprana de permisos: mejor fallar aquí que tras 400 MB.
                string probe = Path.Combine(PendingDir, ".write-test");
                try
                {
                    File.WriteAllText(probe, "ok");
                    File.Delete(probe);
                }
                catch
                {
                    LastError = $"No se puede escribir en «{PendingDir}». Mueve el visor a una carpeta escribible.";
                    return false;
                }

                string nombre = string.IsNullOrWhiteSpace(release.AssetName) ? "update.exe" : release.AssetName!;
                string destino = Path.Combine(PendingDir, nombre);
                string temporal = destino + ".part";

                // Limpia restos de OTRA descarga, pero conserva el .part para reanudar.
                foreach (var f in Directory.GetFiles(PendingDir))
                {
                    if (!string.Equals(f, temporal, StringComparison.OrdinalIgnoreCase) &&
                        !string.Equals(f, destino, StringComparison.OrdinalIgnoreCase))
                    {
                        try { File.Delete(f); } catch { }
                    }
                }

                long inicio = File.Exists(temporal) ? new FileInfo(temporal).Length : 0;
                if (release.AssetSize > 0 && inicio >= release.AssetSize)
                {
                    // El .part ya tiene el tamaño final: se valida sin volver a bajar.
                    inicio = release.AssetSize;
                }

                using var http = customHandler != null
                    ? new HttpClient(customHandler, disposeHandler: false)
                    : new HttpClient { Timeout = TimeSpan.FromMinutes(30) };
                http.DefaultRequestHeaders.UserAgent.ParseAdd("WoldVirtualP2P3D-Updater/1.1");

                using var req = new HttpRequestMessage(HttpMethod.Get, release.AssetUrl);
                if (inicio > 0)
                    req.Headers.Range = new RangeHeaderValue(inicio, null);

                using var resp = await http.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, ct);

                bool reanudando = inicio > 0 && resp.StatusCode == HttpStatusCode.PartialContent;
                if (!reanudando && inicio > 0)
                {
                    // El servidor no soporta rangos (o el fichero cambió): empezar de cero.
                    inicio = 0;
                    try { File.Delete(temporal); } catch { }
                }

                resp.EnsureSuccessStatusCode();

                long total = (reanudando ? inicio : 0) + (resp.Content.Headers.ContentLength ?? 0);
                if (total <= 0) total = release.AssetSize;
                long recibido = inicio;

                var buffer = new byte[81920];
                await using (var origen = await resp.Content.ReadAsStreamAsync(ct))
                await using (var fs = new FileStream(temporal,
                             reanudando ? FileMode.Append : FileMode.Create,
                             FileAccess.Write, FileShare.None))
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

                if (release.AssetSize > 0 && recibido != release.AssetSize)
                {
                    LastError = $"La descarga quedó incompleta ({recibido} de {release.AssetSize} bytes). Se reanudará.";
                    return false;   // conserva el .part para el siguiente intento
                }

                // Verificación criptográfica contra el digest publicado por GitHub (H1 / P0-3: Fail-Closed).
                // Sin digest y longitud esperados no se marca la descarga como buena ni se entra en fase de aplicación.
                if (string.IsNullOrWhiteSpace(release.Digest))
                {
                    try { File.Delete(temporal); } catch { }
                    LastError = "La release no incluye un digest SHA-256 verificable. Descarga rechazada por seguridad.";
                    return false;
                }

                string? hash = CalcularSha256(temporal);
                if (hash == null)
                {
                    try { File.Delete(temporal); } catch { }
                    LastError = "No se pudo calcular el hash SHA-256 del archivo descargado.";
                    return false;
                }

                string esperado = release.Digest.StartsWith("sha256:", StringComparison.OrdinalIgnoreCase)
                    ? release.Digest.Substring(7).Trim()
                    : release.Digest.Trim();

                if (!hash.Equals(esperado, StringComparison.OrdinalIgnoreCase))
                {
                    try { File.Delete(temporal); } catch { }
                    LastError = "El archivo descargado no coincide con el SHA-256 publicado. Descarga descartada.";
                    return false;
                }

                // Renombrado atómico: el .exe sólo "existe" cuando está completo.
                if (File.Exists(destino)) File.Delete(destino);
                File.Move(temporal, destino);

                WriteState(release, nombre, hash);
                return true;
            }
            catch (OperationCanceledException)
            {
                LastError = "Descarga cancelada.";
                return false;   // conserva el .part
            }
            catch (Exception ex)
            {
                LastError = $"Error de descarga: {ex.Message}";
                return false;
            }
        }

        private static string? CalcularSha256(string path)
        {
            try
            {
                using var sha = SHA256.Create();
                using var fs = File.OpenRead(path);
                return Convert.ToHexString(sha.ComputeHash(fs)).ToLowerInvariant();
            }
            catch
            {
                return null;
            }
        }

        /// <summary>Marca el estado para que el aplicador externo sepa qué reemplazar (escritura atómica).</summary>
        private void WriteState(ReleaseInfo release, string assetName, string sha256)
        {
            var estado = new
            {
                apply = true,
                asset = assetName,
                tag = release.TagName,
                version = release.Version,
                size = release.AssetSize,
                sha256,
                downloadedAt = DateTime.UtcNow.ToString("o")
            };

            string json = JsonSerializer.Serialize(estado, new JsonSerializerOptions { WriteIndented = true });
            string tmp = StateFile + ".tmp";
            File.WriteAllText(tmp, json);
            File.Move(tmp, StateFile, overwrite: true);
        }
    }
}
