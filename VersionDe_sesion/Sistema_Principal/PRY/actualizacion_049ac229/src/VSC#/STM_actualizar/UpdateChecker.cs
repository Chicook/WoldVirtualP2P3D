using System;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;

namespace Visor3D.Update
{
    public class UpdateChecker
    {
        private const string Repo = "Chicook/WoldVirtualP2P3D";
        private static readonly HttpClient Client = new HttpClient();

        static UpdateChecker()
        {
            // Usar un User-Agent de navegador real para evitar bloqueos de GitHub API
            Client.DefaultRequestHeaders.Add("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
            Client.DefaultRequestHeaders.Add("Accept", "application/vnd.github.v3+json");
            
            var token = Environment.GetEnvironmentVariable("GITHUB_TOKEN");
            if (!string.IsNullOrWhiteSpace(token))
                Client.DefaultRequestHeaders.Add("Authorization", "token " + token);
        }

        public async Task<ReleaseInfo?> CheckForUpdateAsync(string currentVersion)
        {
            try
            {
                // Primero intentar con 'latest'
                var url = $"https://api.github.com/repos/{Repo}/releases/latest";
                Console.WriteLine($"[UpdateChecker] Consultando GitHub: {url}");
                var response = await Client.GetAsync(url);
                
                string json;
                if (response.IsSuccessStatusCode)
                {
                    json = await response.Content.ReadAsStringAsync();
                }
                else
                {
                    // Si 'latest' falla, intentar obtener la lista completa de releases
                    Console.WriteLine("[UpdateChecker] 'latest' no encontrado o error. Consultando lista de releases...");
                    url = $"https://api.github.com/repos/{Repo}/releases";
                    json = await Client.GetStringAsync(url);
                    using var listDoc = JsonDocument.Parse(json);
                    if (listDoc.RootElement.ValueKind == JsonValueKind.Array && listDoc.RootElement.GetArrayLength() > 0)
                    {
                        // Tomar la primera release de la lista (suele ser la más reciente)
                        json = listDoc.RootElement[0].GetRawText();
                    }
                    else
                    {
                        Console.WriteLine("[UpdateChecker] No se encontraron releases en el repositorio.");
                        return null;
                    }
                }

                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;
                
                // Loguear el JSON para debug (solo los primeros 500 caracteres)
                string preview = json.Length > 500 ? json.Substring(0, 500) : json;
                Console.WriteLine($"[UpdateChecker] JSON Recibido: {preview}");

                var tag = root.GetProperty("tag_name").GetString() ?? "";
                Console.WriteLine($"[UpdateChecker] Tag detectado en GitHub: {tag}");

                // Si la versión actual ya es igual o mayor a la de la release, no actualizar.
                if (IsUpToDate(tag, currentVersion))
                {
                    Console.WriteLine("[UpdateChecker] La versión local ya está al día.");
                    return null;
                }

                foreach (var asset in root.GetProperty("assets").EnumerateArray())
                {
                    var name = asset.GetProperty("name").GetString() ?? "";
                    if (name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
                    {
                        Console.WriteLine($"[UpdateChecker] Asset encontrado: {name}");
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
            catch (Exception ex)
            {
                Console.WriteLine($"[UpdateChecker] Error crítico: {ex.Message}");
            }
            return null;
        }

        private static bool IsUpToDate(string tag, string currentVersion)
        {
            if (string.IsNullOrWhiteSpace(tag)) return true;
            
            try
            {
                var latestVer = ExtractVersion(tag);
                var currentVer = ExtractVersion(currentVersion);

                if (latestVer != null && currentVer != null)
                {
                    Console.WriteLine($"[UpdateChecker] Comparación: Local {currentVer} vs Remoto {latestVer}");
                    // Si la versión remota es estrictamente mayor, hay actualización
                    return currentVer >= latestVer;
                }
            }
            catch { }

            // Si no podemos parsear, solo comparamos si son idénticos
            return tag.Trim().Equals(currentVersion.Trim(), StringComparison.OrdinalIgnoreCase);
        }

        private static Version? ExtractVersion(string tag)
        {
            if (string.IsNullOrWhiteSpace(tag)) return null;
            
            try 
            {
                // Limpiar caracteres y buscar números (ej: 0.0.12 o 0.0.012)
                var match = System.Text.RegularExpressions.Regex.Match(tag, @"(\d+\.\d+(\.\d+)?(\.\d+)?)");
                if (match.Success)
                {
                    string vStr = match.Value;
                    // Normalizar versiones como 0.0.012 a 0.0.12 para que Version.TryParse funcione
                    string[] parts = vStr.Split('.');
                    for (int i = 0; i < parts.Length; i++)
                    {
                        if (int.TryParse(parts[i], out int n))
                            parts[i] = n.ToString();
                    }
                    vStr = string.Join(".", parts);

                    if (Version.TryParse(vStr, out var v))
                        return v;
                }
            }
            catch { }
            return null;
        }
    }
}
