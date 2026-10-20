using System;
using System.IO;
using System.Net.Http;
using System.Threading.Tasks;

namespace Visor3D.Update
{
    public class UpdateDownloader
    {
        private readonly string baseDir;
        public string PendingDir => Path.Combine(baseDir, "update-pending");
        public string StateFile => Path.Combine(baseDir, "state.json");

        public UpdateDownloader()
        {
            baseDir = Path.Combine(AppContext.BaseDirectory, "STM_actualizar");
        }

        public async Task<bool> DownloadAsync(ReleaseInfo release)
        {
            try
            {
                Directory.CreateDirectory(PendingDir);
                var dest = Path.Combine(PendingDir, release.AssetName ?? "update.exe");

                using var http = new HttpClient();
                http.DefaultRequestHeaders.Add("User-Agent", "WoldVirtualP2P3D-Visor3D-Updater");
                using var resp = await http.GetAsync(release.AssetUrl, HttpCompletionOption.ResponseHeadersRead);
                resp.EnsureSuccessStatusCode();

                await using var fs = File.Create(dest);
                await resp.Content.CopyToAsync(fs);

                var state = $$"""
                    {
                      "apply": true,
                      "asset": "{{release.AssetName}}",
                      "tag": "{{release.TagName}}",
                      "size": {{release.AssetSize}},
                      "downloadedAt": "{{DateTime.UtcNow:o}}"
                    }
                    """;
                File.WriteAllText(StateFile, state);
                return true;
            }
            catch
            {
                return false;
            }
        }
    }
}
