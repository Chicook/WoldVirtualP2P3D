using System;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;

namespace Visor3D.Update
{
    public class UpdateChecker
    {
        private const string Repo = "Chicook/WoldVirtualP2P3D";
        // Release objetivo: https://github.com/Chicook/WoldVirtualP2P3D/releases/tag/v0.0.111_actualizacion_2069d33a
        private const string ReleaseTag = "v0.0.111_actualizacion_2069d33a";
        private static readonly HttpClient Client = new HttpClient();

        static UpdateChecker()
        {
            Client.DefaultRequestHeaders.Add("User-Agent", "WoldVirtualP2P3D-Visor3D-Updater");
            var token = Environment.GetEnvironmentVariable("GITHUB_TOKEN");
            if (!string.IsNullOrWhiteSpace(token))
                Client.DefaultRequestHeaders.Add("Authorization", "token " + token);
        }

        public async Task<ReleaseInfo?> CheckForUpdateAsync(string currentVersion)
        {
            try
            {
                var url = $"https://api.github.com/repos/{Repo}/releases/tags/{ReleaseTag}";
                var json = await Client.GetStringAsync(url);
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;
                var tag = root.GetProperty("tag_name").GetString() ?? "";

                // Si la release ya coincide con la versi├│n instalada, no hay nada que hacer.
                if (VersionMatches(tag, currentVersion)) return null;

                foreach (var asset in root.GetProperty("assets").EnumerateArray())
                {
                    var name = asset.GetProperty("name").GetString() ?? "";
                    if (name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
                    {
                        return new ReleaseInfo
                        {
                            TagName = tag,
                            Version = tag,
                            AssetUrl = asset.GetProperty("browser_download_url").GetString() ?? "",
                            AssetName = name,
                            AssetSize = asset.GetProperty("size").GetInt64(),
                            Prerelease = root.GetProperty("prerelease").GetBoolean()
                        };
                    }
                }
            }
            catch
            {
                // Sin red o GitHub no disponible: continuar sin actualizar.
            }
            return null;
        }

        private static bool VersionMatches(string tag, string currentVersion)
        {
            if (string.IsNullOrWhiteSpace(tag) || string.IsNullOrWhiteSpace(currentVersion))
                return false;
            try
            {
                var tagNum = ExtractVersion(tag);
                var curNum = new Version(currentVersion);
                if (tagNum != null && curNum != null)
                    return tagNum.Major == curNum.Major && tagNum.Minor == curNum.Minor && tagNum.Build == curNum.Build;
            }
            catch { }
            return tag.Contains(currentVersion, StringComparison.OrdinalIgnoreCase);
        }

        private static Version? ExtractVersion(string tag)
        {
            var digits = System.Text.RegularExpressions.Regex.Match(tag, @"(\d+)\.(\d+)\.(\d+)");
            if (!digits.Success) return null;
            return new Version(int.Parse(digits.Groups[1].Value),
                               int.Parse(digits.Groups[2].Value),
                               int.Parse(digits.Groups[3].Value));
        }
    }
}
