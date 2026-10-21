using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace Visor3D.Update
{
    /// <summary>
    /// Consulta la API pública de GitHub Releases y determina si existe una
    /// versión más reciente que la instalada localmente (comparación SemVer).
    /// </summary>
    public class UpdateChecker
    {
        private const string Repo = "Chicook/WoldVirtualP2P3D";

        // Una única instancia de HttpClient reutilizada (evita agotar sockets).
        private static readonly HttpClient Client = new HttpClient
        {
            Timeout = TimeSpan.FromSeconds(25)
        };

        static UpdateChecker()
        {
            // GitHub EXIGE un User-Agent. Usamos uno de navegador real para
            // evitar bloqueos/rechazos de la API (403) en IPs compartidas.
            Client.DefaultRequestHeaders.UserAgent.ParseAdd(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
            Client.DefaultRequestHeaders.Accept.ParseAdd("application/vnd.github+json");

            // Token opcional: sube el límite de 60 a 5000 peticiones/hora.
            var token = Environment.GetEnvironmentVariable("GITHUB_TOKEN");
            if (!string.IsNullOrWhiteSpace(token))
                Client.DefaultRequestHeaders.Authorization =
                    new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", token);
        }

        /// <summary>
        /// Devuelve la mejor actualización disponible, o null si ya estamos al día.
        /// </summary>
        /// <param name="currentVersion">Versión local (p. ej. "0.0.13").</param>
        public async Task<ReleaseInfo?> CheckForUpdateAsync(string currentVersion)
        {
            try
            {
                var local = ParseVersion(currentVersion) ?? new Version(0, 0, 0, 0);
                Log($"Versión local normalizada: {local}");
                Log($"Consultando: {currentVersion}");

                var releases = await FetchReleasesAsync();
                if (releases.Count == 0)
                {
                    Log("No se encontraron releases publicadas.");
                    return null;
                }

                // Elegimos, por separado, la mejor versión ESTABLE y la mejor
                // PRERELEASE, y damos prioridad a la estable. Así, si sólo existen
                // betas publicadas, también se detectan.
                ReleaseInfo? mejorEstable = null;
                Version? mejorEstableVer = null;
                ReleaseInfo? mejorPre = null;
                Version? mejorPreVer = null;

                foreach (var rel in releases)
                {
                    if (rel.Draft) continue;                     // los borradores no son públicos

                    var asset = ElegirAsset(rel.Assets);
                    if (asset == null || string.IsNullOrWhiteSpace(asset.Url)) continue;  // sin binario

                    // Este proyecto reutiliza la MISMA release (mismo tag) y sólo
                    // sustituye el binario, por lo que la versión real puede estar en
                    // el NOMBRE del fichero (p. ej. DMWold...v0.0.013....exe). Tomamos
                    // la mayor entre la del tag y la del binario para no perder updates.
                    var tagVer = ParseVersion(rel.TagName);
                    var assetVer = ParseAssetVersion(asset.Name);
                    var v = MaxVersion(tagVer, assetVer);
                    Log($"Release '{rel.TagName}' | tag={tagVer} | asset='{asset.Name}' ({assetVer}) | efectiva={v} | local={local}");
                    if (v == null || v <= local) continue;       // no es más nueva que la local

                    var info = new ReleaseInfo
                    {
                        TagName = rel.TagName,
                        Version = v.ToString(),
                        AssetUrl = asset.Url,
                        AssetName = asset.Name,
                        AssetSize = asset.Size,
                        Prerelease = rel.Prerelease
                    };

                    if (rel.Prerelease)
                    {
                        if (mejorPre == null || v > mejorPreVer!) { mejorPre = info; mejorPreVer = v; }
                    }
                    else
                    {
                        if (mejorEstable == null || v > mejorEstableVer!) { mejorEstable = info; mejorEstableVer = v; }
                    }
                }

                var elegido = mejorEstable ?? mejorPre;
                Log(elegido == null
                    ? "El sistema ya está al día."
                    : $"Actualización disponible: {elegido.TagName} ({elegido.AssetName})");
                return elegido;
            }
            catch (Exception ex)
            {
                Log($"Error consultando GitHub: {ex.Message}");
                return null;
            }
        }

        // ─────────────────────────────────────────────────────────────────
        //  Llamada HTTP a la API de GitHub
        // ─────────────────────────────────────────────────────────────────
        private static async Task<List<GhRelease>> FetchReleasesAsync()
        {
            // 'per_page' limita el payload; el parámetro 't' rompe la caché de GitHub.
            var url = $"https://api.github.com/repos/{Repo}/releases?per_page=30&t={DateTime.UtcNow.Ticks}";

            using var resp = await Client.GetAsync(url);
            if (!resp.IsSuccessStatusCode)
            {
                Log($"GitHub respondió {(int)resp.StatusCode} {resp.ReasonPhrase}");
                return new List<GhRelease>();
            }

            await using var stream = await resp.Content.ReadAsStreamAsync();
            using var doc = await JsonDocument.ParseAsync(stream);
            if (doc.RootElement.ValueKind != JsonValueKind.Array)
                return new List<GhRelease>();

            var lista = new List<GhRelease>();
            foreach (var el in doc.RootElement.EnumerateArray())
            {
                var rel = new GhRelease
                {
                    TagName = el.TryGetProperty("tag_name", out var t) ? t.GetString() ?? "" : "",
                    Draft = el.TryGetProperty("draft", out var d) && d.GetBoolean(),
                    Prerelease = el.TryGetProperty("prerelease", out var p) && p.GetBoolean()
                };

                if (el.TryGetProperty("assets", out var assets) && assets.ValueKind == JsonValueKind.Array)
                {
                    foreach (var a in assets.EnumerateArray())
                    {
                        rel.Assets.Add(new GhAsset
                        {
                            Name = a.TryGetProperty("name", out var n) ? n.GetString() ?? "" : "",
                            Url = a.TryGetProperty("browser_download_url", out var u) ? u.GetString() ?? "" : "",
                            Size = a.TryGetProperty("size", out var s) ? s.GetInt64() : 0
                        });
                    }
                }
                lista.Add(rel);
            }

            Log($"Releases recibidas: {lista.Count}");
            return lista;
        }

        // ─────────────────────────────────────────────────────────────────
        //  Selección del binario a descargar
        // ─────────────────────────────────────────────────────────────────
        private static GhAsset? ElegirAsset(List<GhAsset> assets)
        {
            // 1) .exe cuyo nombre recuerde al visor (criterio preferente).
            var exes = assets.Where(a =>
                a.Name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) &&
                (a.Name.Contains("Wold", StringComparison.OrdinalIgnoreCase) ||
                 a.Name.Contains("Visor", StringComparison.OrdinalIgnoreCase) ||
                 a.Name.Contains("DMWold", StringComparison.OrdinalIgnoreCase))).ToList();

            // 2) Si no hubiera ninguno "del visor", cualquier .exe.
            if (exes.Count == 0)
                exes = assets.Where(a => a.Name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase)).ToList();

            if (exes.Count == 0)
                return assets.FirstOrDefault(a => a.Name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase));

            // De todos los binarios, nos quedamos con el de MAYOR versión en el nombre
            // (la release acumula varias versiones del .exe y sólo una es la actual).
            return exes.OrderByDescending(a => ParseAssetVersion(a.Name) ?? new Version(0, 0, 0, 0))
                       .First();
        }

        // ─────────────────────────────────────────────────────────────────
        //  Normalización / comparación de versiones (tolerante a "v0.0.012")
        // ─────────────────────────────────────────────────────────────────
        /// <summary>
        /// Extrae una <see cref="Version"/> de un tag tipo "v1.2.0", "0.0.012",
        /// "1.2.3-beta.1", etc. Normaliza ceros a la izquierda y rellena a 4
        /// componentes para que la comparación sea homogénea.
        /// </summary>
        public static Version? ParseVersion(string? tag)
        {
            if (string.IsNullOrWhiteSpace(tag)) return null;

            var m = Regex.Match(tag, @"\d+(?:\.\d+){0,3}");
            if (!m.Success) return null;

            var nums = m.Value.Split('.')
                              .Select(s => int.TryParse(s, out var n) ? n : 0)
                              .ToArray();

            int a = nums.Length > 0 ? nums[0] : 0;
            int b = nums.Length > 1 ? nums[1] : 0;
            int c = nums.Length > 2 ? nums[2] : 0;
            int d = nums.Length > 3 ? nums[3] : 0;
            return new Version(a, b, c, d);
        }

        /// <summary>
        /// Extrae la versión del NOMBRE de un binario, p. ej.
        /// "DMWoldVirtualp2pCNXv0.0.013_actualizacion_049ac229.exe" -> 0.0.13.
        /// Exige al menos "mayor.menor" para no confundir hashes ("b5592aff")
        /// ni textos como "3D" con números de versión.
        /// </summary>
        public static Version? ParseAssetVersion(string? fileName)
        {
            if (string.IsNullOrWhiteSpace(fileName)) return null;

            var m = Regex.Match(fileName, @"(?<!\d)(\d+)\.(\d+)(?:\.(\d+))?(?:\.(\d+))?(?!\d)");
            if (!m.Success) return null;

            if (!int.TryParse(m.Groups[1].Value, out int a)) return null;
            if (!int.TryParse(m.Groups[2].Value, out int b)) return null;
            int c = m.Groups[3].Success && int.TryParse(m.Groups[3].Value, out var cv) ? cv : 0;
            int d = m.Groups[4].Success && int.TryParse(m.Groups[4].Value, out var dv) ? dv : 0;
            return new Version(a, b, c, d);
        }

        /// <summary>Devuelve la mayor de dos versiones (tolerante a null).</summary>
        private static Version? MaxVersion(Version? a, Version? b)
        {
            if (a == null) return b;
            if (b == null) return a;
            return a >= b ? a : b;
        }

        // ─────────────────────────────────────────────────────────────────
        //  Log de depuración (LocalAppData\WoldVirtualP2P3D\update_debug.log)
        // ─────────────────────────────────────────────────────────────────
        private static void Log(string message)
        {
            try
            {
                string dir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "WoldVirtualP2P3D");
                Directory.CreateDirectory(dir);

                File.AppendAllText(
                    Path.Combine(dir, "update_debug.log"),
                    $"[{DateTime.Now:HH:mm:ss}] [Checker] {message}{Environment.NewLine}");

                Console.WriteLine($"[UpdateChecker] {message}");
            }
            catch { /* el log nunca debe romper la app */ }
        }

        // DTOs mínimos para deserializar la respuesta de GitHub.
        private sealed class GhRelease
        {
            public string TagName { get; set; } = "";
            public bool Draft { get; set; }
            public bool Prerelease { get; set; }
            public List<GhAsset> Assets { get; } = new List<GhAsset>();
        }

        private sealed class GhAsset
        {
            public string Name { get; set; } = "";
            public string Url { get; set; } = "";
            public long Size { get; set; }
        }
    }
}
