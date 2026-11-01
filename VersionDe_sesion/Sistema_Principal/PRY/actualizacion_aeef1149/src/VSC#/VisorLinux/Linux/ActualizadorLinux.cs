using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Visor3D.Seguridad;
using Visor3D.Services;
using Visor3D.Update;

namespace Visor3D.Linux
{
    /// <summary>
    /// Actualizaciones del paquete Linux. El comprobador compartido
    /// (<see cref="UpdateChecker"/>) elige el binario <c>.exe</c> del visor de
    /// Windows, que aquí no sirve: esta clase consulta las mismas releases y se
    /// queda con el <c>.tar.gz</c> de Linux, descarga el paquete y verifica su
    /// digest SHA-256 publicado. La sustitución del paquete en marcha la hace
    /// el usuario cerrando el visor y extrayendo el archivo.
    /// </summary>
    public sealed class ActualizadorLinux
    {
        private const string Repo = "Chicook/WoldVirtualP2P3D";

        private static readonly HttpClient Cliente = new() { Timeout = TimeSpan.FromSeconds(30) };

        static ActualizadorLinux()
        {
            Cliente.DefaultRequestHeaders.UserAgent.ParseAdd(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " +
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
            Cliente.DefaultRequestHeaders.Accept.ParseAdd("application/vnd.github+json");

            string? token = Environment.GetEnvironmentVariable("GITHUB_TOKEN");
            if (!string.IsNullOrWhiteSpace(token))
                Cliente.DefaultRequestHeaders.Authorization =
                    new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", token);
        }

        public static string Carpeta => Path.Combine(PerfilUsuario.BaseDir, "actualizaciones");

        public string? UltimoError { get; private set; }

        public const string ComoAplicar =
            "Para aplicar la actualización: cierra el visor, extrae el archivo .tar.gz sobre la carpeta " +
            "del visor (sustituye motor, mundo y el ejecutable) y vuelve a abrirlo. " +
            "La cuenta y el mundo guardado viven fuera de esa carpeta, así que no se pierden.";

        /// <summary>
        /// Devuelve el paquete Linux más reciente, o <c>null</c> si no hay nada
        /// más nuevo que <paramref name="versionLocal"/>.
        /// </summary>
        public async Task<ReleaseInfo?> BuscarAsync(string versionLocal)
        {
            UltimoError = null;

            var local = UpdateChecker.ParseVersion(versionLocal) ?? new Version(0, 0, 0, 0);
            try
            {
                var releases = await LeerReleasesAsync().ConfigureAwait(false);
                if (releases.Count == 0)
                {
                    UltimoError = "GitHub no devolvió ninguna release (¿sin conexión o límite de peticiones?).";
                    return null;
                }

                var elegido = MejorPaqueteLinux(releases, local);
                VisorLog.Info(elegido == null
                    ? $"[actualizar] Linux {local}: no hay paquete más nuevo."
                    : $"[actualizar] Linux {local} → {elegido.TagName} ({elegido.AssetName}).");
                return elegido;
            }
            catch (Exception ex)
            {
                UltimoError = $"No se pudo consultar GitHub: {ex.Message}";
                VisorLog.Warn("[actualizar] " + UltimoError);
                return null;
            }
        }

        /// <summary>
        /// Descarga el paquete en <see cref="Carpeta"/> midiendo el progreso.
        /// Sólo da el archivo por bueno si el SHA-256 coincide con el digest
        /// publicado por GitHub; si no hay digest, se acepta el tamaño exacto.
        /// </summary>
        public async Task<string?> DescargarAsync(ReleaseInfo release,
                                                  IProgress<DownloadProgress>? progreso = null,
                                                  CancellationToken ct = default)
        {
            UltimoError = null;

            if (release == null || string.IsNullOrWhiteSpace(release.AssetUrl) ||
                string.IsNullOrWhiteSpace(release.AssetName))
            {
                UltimoError = "La release no tiene un paquete Linux descargable.";
                return null;
            }

            string destino = Path.Combine(Carpeta, release.AssetName!);
            string temporal = destino + ".part";

            try
            {
                Directory.CreateDirectory(Carpeta);

                using var respuesta = await Cliente.GetAsync(
                    release.AssetUrl, HttpCompletionOption.ResponseHeadersRead, ct).ConfigureAwait(false);
                if (!respuesta.IsSuccessStatusCode)
                {
                    UltimoError = $"GitHub respondió {(int)respuesta.StatusCode} al descargar el paquete.";
                    return null;
                }

                long total = respuesta.Content.Headers.ContentLength ?? release.AssetSize;
                await using (var origen = await respuesta.Content.ReadAsStreamAsync(ct).ConfigureAwait(false))
                await using (var salida = new FileStream(
                    temporal, FileMode.Create, FileAccess.Write, FileShare.None, 81920, useAsync: true))
                {
                    byte[] buffer = new byte[81920];
                    long recibidos = 0;
                    progreso?.Report(new DownloadProgress(0, total));

                    int leidos;
                    while ((leidos = await origen.ReadAsync(buffer, ct).ConfigureAwait(false)) > 0)
                    {
                        await salida.WriteAsync(buffer.AsMemory(0, leidos), ct).ConfigureAwait(false);
                        recibidos += leidos;
                        progreso?.Report(new DownloadProgress(recibidos, total));
                    }
                }

                string? problema = Verificar(temporal, release);
                if (problema != null)
                {
                    UltimoError = problema;
                    try { File.Delete(temporal); } catch { }
                    return null;
                }

                File.Move(temporal, destino, overwrite: true);
                VisorLog.Info($"[actualizar] Paquete Linux descargado: {destino}");
                return destino;
            }
            catch (OperationCanceledException)
            {
                UltimoError = "Descarga cancelada.";
                return null;
            }
            catch (Exception ex)
            {
                UltimoError = $"No se pudo descargar: {ex.Message}";
                VisorLog.Warn("[actualizar] " + UltimoError);
                return null;
            }
        }

        private static string? Verificar(string ruta, ReleaseInfo release)
        {
            string digest = (release.Digest ?? "").Trim();
            string hash = digest.StartsWith("sha256:", StringComparison.OrdinalIgnoreCase)
                ? digest["sha256:".Length..]
                : digest;

            long tamano = new FileInfo(ruta).Length;
            if (release.AssetSize > 0 && tamano != release.AssetSize)
                return $"El archivo quedó incompleto ({tamano} de {release.AssetSize} bytes).";

            if (hash.Length != 64) return null;   // GitHub puede publicar el asset sin digest

            using var fs = File.OpenRead(ruta);
            string calculado = Convert.ToHexString(SHA256.HashData(fs)).ToLowerInvariant();
            return string.Equals(calculado, hash, StringComparison.OrdinalIgnoreCase)
                ? null
                : "El SHA-256 del archivo no coincide con el publicado; se descarta.";
        }

        private static ReleaseInfo? MejorPaqueteLinux(List<GhRelease> releases, Version local)
        {
            ReleaseInfo? estable = null, previa = null;
            Version? verEstable = null, verPrevia = null;

            foreach (var rel in releases)
            {
                if (rel.Draft) continue;

                var asset = ElegirPaqueteLinux(rel.Assets);
                if (asset == null) continue;

                var version = Mayor(UpdateChecker.ParseVersion(rel.TagName),
                                    UpdateChecker.ParseAssetVersion(asset.Name));
                if (version == null || version <= local) continue;

                var info = new ReleaseInfo
                {
                    TagName = rel.TagName,
                    Version = version.ToString(),
                    AssetUrl = asset.Url,
                    AssetName = asset.Name,
                    AssetSize = asset.Size,
                    Digest = asset.Digest,
                    Prerelease = rel.Prerelease,
                };

                if (rel.Prerelease)
                {
                    if (verPrevia == null || version > verPrevia) { previa = info; verPrevia = version; }
                }
                else
                {
                    if (verEstable == null || version > verEstable) { estable = info; verEstable = version; }
                }
            }

            return estable ?? previa;
        }

        /// <summary>
        /// El paquete de Linux es el <c>.tar.gz</c> cuyo nombre menciona Linux.
        /// Se prefiere el de mayor versión en el nombre porque la release
        /// acumula varias versiones y sólo una es la vigente.
        /// </summary>
        private static GhAsset? ElegirPaqueteLinux(List<GhAsset> assets)
        {
            static bool EsPaquete(string nombre) =>
                (nombre.EndsWith(".tar.gz", StringComparison.OrdinalIgnoreCase) ||
                 nombre.EndsWith(".tgz", StringComparison.OrdinalIgnoreCase)) &&
                nombre.Contains("linux", StringComparison.OrdinalIgnoreCase);

            return assets.Where(a => EsPaquete(a.Name) && !string.IsNullOrWhiteSpace(a.Url))
                         .OrderByDescending(a => UpdateChecker.ParseAssetVersion(a.Name) ?? new Version(0, 0, 0, 0))
                         .FirstOrDefault();
        }

        private static Version? Mayor(Version? a, Version? b)
        {
            if (a == null) return b;
            if (b == null) return a;
            return a >= b ? a : b;
        }

        private static async Task<List<GhRelease>> LeerReleasesAsync()
        {
            string url = $"https://api.github.com/repos/{Repo}/releases?per_page=30&t={DateTime.UtcNow.Ticks}";
            using var resp = await Cliente.GetAsync(url).ConfigureAwait(false);
            if (!resp.IsSuccessStatusCode)
                throw new InvalidOperationException($"{(int)resp.StatusCode} {resp.ReasonPhrase}");

            await using var stream = await resp.Content.ReadAsStreamAsync().ConfigureAwait(false);
            using var doc = await JsonDocument.ParseAsync(stream).ConfigureAwait(false);
            if (doc.RootElement.ValueKind != JsonValueKind.Array) return new List<GhRelease>();

            var lista = new List<GhRelease>();
            foreach (var el in doc.RootElement.EnumerateArray())
            {
                var rel = new GhRelease
                {
                    TagName = el.TryGetProperty("tag_name", out var t) ? t.GetString() ?? "" : "",
                    Draft = el.TryGetProperty("draft", out var d) && d.GetBoolean(),
                    Prerelease = el.TryGetProperty("prerelease", out var p) && p.GetBoolean(),
                };

                if (el.TryGetProperty("assets", out var assets) && assets.ValueKind == JsonValueKind.Array)
                {
                    foreach (var a in assets.EnumerateArray())
                    {
                        rel.Assets.Add(new GhAsset
                        {
                            Name = a.TryGetProperty("name", out var n) ? n.GetString() ?? "" : "",
                            Url = a.TryGetProperty("browser_download_url", out var u) ? u.GetString() ?? "" : "",
                            Size = a.TryGetProperty("size", out var s) ? s.GetInt64() : 0,
                            Digest = a.TryGetProperty("digest", out var dg) ? dg.GetString() ?? "" : "",
                        });
                    }
                }

                lista.Add(rel);
            }
            return lista;
        }

        private sealed class GhRelease
        {
            public string TagName { get; set; } = "";
            public bool Draft { get; set; }
            public bool Prerelease { get; set; }
            public List<GhAsset> Assets { get; } = new();
        }

        private sealed class GhAsset
        {
            public string Name { get; set; } = "";
            public string Url { get; set; } = "";
            public long Size { get; set; }
            public string Digest { get; set; } = "";
        }
    }
}
