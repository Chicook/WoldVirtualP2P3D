using System;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Text.Json;

namespace Visor3D.Services
{
    /// <summary>
    /// Autoprueba del WebNodo frente al OTA (<c>--webnodo-selftest</c>). Verifica
    /// el cierre de W-01/DT-11: el portal anuncia la release realmente instalada
    /// (no una constante del <c>.csproj</c>) y <c>/descargar</c> entrega el binario
    /// local en ejecución, sin depender de que su nombre en disco coincida con el
    /// nombre anunciado. Trabaja sobre un <c>release.json</c> sintético y sin red.
    /// Devuelve 0 sólo si todo pasa.
    /// </summary>
    public static class WebNodoSelfTest
    {
        public static int Run()
        {
            int fallos = 0;
            var salida = new StringBuilder();

            void Check(string nombre, bool ok, string detalle = "")
            {
                if (!ok) fallos++;
                string linea = $"[{(ok ? "OK" : "FALLO")}] {nombre}" +
                               (string.IsNullOrWhiteSpace(detalle) ? "" : $" — {detalle}");
                salida.AppendLine(linea);
                VisorLog.Info($"[webnodo] {linea}");
            }

            string raiz = Path.Combine(Path.GetTempPath(), "wvp3d_webnodo_selftest_" + Guid.NewGuid().ToString("N"));

            try
            {
                Directory.CreateDirectory(raiz);
                ComprobarEsquemaPublicado(Check, raiz);
                ComprobarFallbackSinRelease(Check, raiz);
                ComprobarPortalSirveBinarioLocal(Check);
            }
            catch (Exception ex)
            {
                Check("Autoprueba WebNodo", false, $"{ex.GetType().Name}: {ex.Message}");
            }
            finally
            {
                try { Directory.Delete(raiz, recursive: true); } catch { }
            }

            Cerrar(salida, fallos);
            return fallos == 0 ? 0 : 1;
        }

        /// <summary>
        /// Causa 1 de W-01: el <c>release.json</c> publicado usa
        /// <c>{ tag_name, name, version, assets[] }</c> y el lector debe entenderlo.
        /// </summary>
        private static void ComprobarEsquemaPublicado(Action<string, bool, string> check, string raiz)
        {
            string ruta = Path.Combine(raiz, "release.json");
            File.WriteAllText(ruta, @"{
  ""tag_name"": ""v9.9.9"",
  ""name"": ""Prueba sintética"",
  ""version"": ""9.9.9"",
  ""assets"": [
    { ""name"": ""DMWoldVirtualP2P3Dv9.9.9-linux.tar.gz"", ""size"": 100, ""digest"": ""sha256:aa"", ""url"": ""https://example.invalid/linux"" },
    { ""name"": ""DMWoldVirtualP2P3Dv9.9.9.exe"", ""size"": 12345678, ""digest"": ""sha256:bb"", ""url"": ""https://example.invalid/exe"" }
  ]
}", Encoding.UTF8);

            var r = WebNodoService.LeerReleaseParaPrueba(ruta);
            check("release.json {assets[]} → nombre del .exe", r.Name == "DMWoldVirtualP2P3Dv9.9.9.exe", r.Name);
            check("release.json {assets[]} → url del asset", r.Url == "https://example.invalid/exe", r.Url);
            check("release.json {assets[]} → versión", r.Version == "9.9.9", r.Version);
            check("release.json {assets[]} → tamaño en MB", r.SizeMb == "11.8", r.SizeMb);

            // Sin 'version' explícita: se deriva del tag.
            string rutaTag = Path.Combine(raiz, "release_solo_tag.json");
            File.WriteAllText(rutaTag, @"{
  ""tag_name"": ""v1.2.3"",
  ""assets"": [ { ""name"": ""Visor.exe"", ""size"": 1048576, ""url"": ""https://example.invalid/v"" } ]
}", Encoding.UTF8);

            var rt = WebNodoService.LeerReleaseParaPrueba(rutaTag);
            check("versión derivada de tag_name cuando falta 'version'", rt.Version == "1.2.3", rt.Version);
            check("tamaño de 1 MiB se muestra como 1.0", rt.SizeMb == "1.0", rt.SizeMb);
        }

        /// <summary>
        /// Sin <c>release.json</c> legible se cae al nombre derivado del ensamblado:
        /// nunca a una constante versionada a mano.
        /// </summary>
        private static void ComprobarFallbackSinRelease(Action<string, bool, string> check, string raiz)
        {
            string ruta = Path.Combine(raiz, "no_existe.json");
            var r = WebNodoService.LeerReleaseParaPrueba(ruta);
            check("fallback: nombre termina en .exe", r.Name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase), r.Name);
            check("fallback: versión = versión instalada", r.Version == WebNodoService.VersionInstalada,
                  $"{r.Version} vs {WebNodoService.VersionInstalada}");
        }

        /// <summary>
        /// Causas 2 y 4 de W-01: tras un OTA el anuncio y el binario servido deben
        /// referirse a la versión instalada aunque el fichero en disco conserve el
        /// nombre antiguo. Se emula con un nombre anunciado DISTINTO del binario real.
        /// </summary>
        private static void ComprobarPortalSirveBinarioLocal(Action<string, bool, string> check)
        {
            string? binario = WebNodoService.RutaBinarioEnEjecucion;
            check("binario del visor localizable para servir", binario != null,
                  binario ?? "no se encontró el apphost ni el .exe junto al ensamblado");
            if (binario == null) return;

            const string anunciado = "DMWoldVirtualP2P3Dv9.9.9.exe";
            WebNodoService.SembrarReleaseParaPrueba(
                anunciado, "https://example.invalid/exe", "11.8", "9.9.9");

            var nodo = new WebNodoService();
            try
            {
                // Sembrar marca la consulta como reciente: Start() no consulta GitHub.
                nodo.Start();
                check("Portal WebNodo escucha", nodo.IsRunning,
                      nodo.IsRunning ? $"http://localhost:{nodo.ActivePort}/" : nodo.StartError ?? "sin detalle");
                if (!nodo.IsRunning) return;

                string baseUrl = $"http://127.0.0.1:{nodo.ActivePort}";
                using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };

                int sinToken = (int)http.GetAsync($"{baseUrl}/api/info").GetAwaiter().GetResult().StatusCode;
                check("/api/info sigue exigiendo token", sinToken == 403, $"HTTP {sinToken}");

                using var infoResp = http.GetAsync($"{baseUrl}/api/info?token={WebNodoService.ApiToken}")
                                         .GetAwaiter().GetResult();
                using var info = JsonDocument.Parse(infoResp.Content.ReadAsStringAsync().GetAwaiter().GetResult());
                var raiz = info.RootElement;
                check("/api/info anuncia el nombre instalado",
                      raiz.GetProperty("nombre").GetString() == anunciado,
                      raiz.GetProperty("nombre").GetString() ?? "");
                check("/api/info anuncia la versión de la release",
                      raiz.GetProperty("version").GetString() == "9.9.9",
                      raiz.GetProperty("version").GetString() ?? "");
                check("/api/info distingue la versión instalada",
                      raiz.GetProperty("version_instalada").GetString() == WebNodoService.VersionInstalada,
                      raiz.GetProperty("version_instalada").GetString() ?? "");
                check("/api/info anuncia el tamaño",
                      raiz.GetProperty("tamano_mb").GetString() == "11.8",
                      raiz.GetProperty("tamano_mb").GetString() ?? "");

                // /descargar debe entregar el binario local (200) bajo el nombre
                // anunciado, no redirigir a GitHub (301/302).
                using var dl = http.GetAsync($"{baseUrl}/descargar", HttpCompletionOption.ResponseHeadersRead)
                                   .GetAwaiter().GetResult();
                check("/descargar entrega el binario local (no redirige)",
                      (int)dl.StatusCode == 200, $"HTTP {(int)dl.StatusCode}");

                long esperado = new FileInfo(binario).Length;
                string? nombreCabecera = dl.Content.Headers.ContentDisposition?.FileName?.Trim('"');
                check("/descargar anuncia el nombre del asset",
                      string.Equals(nombreCabecera, anunciado, StringComparison.OrdinalIgnoreCase),
                      nombreCabecera ?? "sin cabecera");
                check("/descargar anuncia el tamaño del binario local",
                      dl.Content.Headers.ContentLength == esperado,
                      $"{dl.Content.Headers.ContentLength} vs {esperado}");
            }
            catch (Exception ex)
            {
                check("Portal sirve el binario local", false, $"{ex.GetType().Name}: {ex.Message}");
            }
            finally
            {
                try { nodo.Dispose(); } catch { }
            }
        }

        private static void Cerrar(StringBuilder salida, int fallos)
        {
            string resumen = $"RESULTADO WEBNODO: {salida.ToString().Split('\n').Length} líneas, {fallos} fallos";
            salida.AppendLine(resumen);
            Console.WriteLine(salida.ToString());
            try
            {
                string dir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "WoldVirtualP2P3D", "logs");
                Directory.CreateDirectory(dir);
                File.WriteAllText(Path.Combine(dir, "webnodo-selftest.log"), salida.ToString(), Encoding.UTF8);
            }
            catch { }
        }
    }
}
