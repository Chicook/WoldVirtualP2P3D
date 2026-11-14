using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Update
{
    /// <summary>
    /// Autoprueba de actualización OTA sin GUI (--update-selftest) para H2 / H4.
    /// Valida de forma hermética y determinista sobre directorios temporales:
    /// 1. Rechazo fail-closed sin digest (P0-3).
    /// 2. Rechazo ante digest incorrecto / manipulación.
    /// 3. Detección de descarga truncada / incompleta.
    /// 4. Descarga íntegra verificada y generación de state.json.
    /// </summary>
    public static class UpdateSelfTest
    {
        private class MockHttpHandler : HttpMessageHandler
        {
            public byte[] Payload { get; set; } = Array.Empty<byte>();
            public bool Truncar { get; set; } = false;

            protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            {
                var response = new HttpResponseMessage(HttpStatusCode.OK);
                if (Truncar)
                {
                    // Enviar menos bytes que los esperados
                    byte[] corto = new byte[Math.Min(10, Payload.Length)];
                    Array.Copy(Payload, corto, corto.Length);
                    response.Content = new ByteArrayContent(corto);
                }
                else
                {
                    response.Content = new ByteArrayContent(Payload);
                }
                return Task.FromResult(response);
            }
        }

        public static int Run()
        {
            var log = new StringBuilder();
            int fallos = 0;

            void Check(string nombre, bool ok, string detalle = "")
            {
                if (!ok) fallos++;
                string linea = $"[{(ok ? "OK" : "FALLO")}] {nombre}" +
                               (string.IsNullOrWhiteSpace(detalle) ? "" : $" — {detalle}");
                log.AppendLine(linea);
                Console.WriteLine(linea);
            }

            string testDir = Path.Combine(Path.GetTempPath(), "wvp3d_update_selftest_" + Guid.NewGuid().ToString("N"));

            try
            {
                Directory.CreateDirectory(testDir);
                Task.Run(() => EjecutarAsync(testDir, Check)).GetAwaiter().GetResult();
            }
            catch (Exception ex)
            {
                Check("Ejecución general de UpdateSelfTest", false, $"{ex.GetType().Name}: {ex.Message}");
            }
            finally
            {
                try
                {
                    if (Directory.Exists(testDir))
                        Directory.Delete(testDir, recursive: true);
                }
                catch { }
            }

            string salida = log.ToString();
            try
            {
                File.WriteAllText(Path.Combine(Path.GetTempPath(), "woldvirtual_update_selftest.log"), salida, Encoding.UTF8);
            }
            catch { }

            Console.WriteLine($"== Fin UpdateSelfTest: {fallos} fallo(s) ==");
            return fallos == 0 ? 0 : 1;
        }

        private static async Task EjecutarAsync(string testDir, Action<string, bool, string> check)
        {
            byte[] payload = Encoding.UTF8.GetBytes("WoldVirtualP2P3D-Synthetic-Update-Binary-Payload-2026");
            string hashPayload;
            using (var sha = SHA256.Create())
            {
                hashPayload = Convert.ToHexString(sha.ComputeHash(payload)).ToLowerInvariant();
            }

            var mockHandler = new MockHttpHandler { Payload = payload };
            var downloader = new UpdateDownloader(testDir, mockHandler);

            // 1. Caso Fail-Closed sin digest (H1 / P0-3)
            var relSinDigest = new ReleaseInfo
            {
                TagName = "v2.7.5-test1",
                Version = "2.7.5",
                AssetName = "update_sin_digest.exe",
                AssetSize = payload.Length,
                AssetUrl = "https://mock.github.release/asset.exe",
                Digest = ""
            };
            bool resSinDigest = await downloader.DownloadAsync(relSinDigest);
            check("OTA fail-closed sin digest",
                  resSinDigest == false && !File.Exists(downloader.StateFile),
                  downloader.LastError ?? "ok");

            // 2. Caso Digest incorrecto / alterado
            var relDigestMalo = new ReleaseInfo
            {
                TagName = "v2.7.5-test2",
                Version = "2.7.5",
                AssetName = "update_digest_malo.exe",
                AssetSize = payload.Length,
                AssetUrl = "https://mock.github.release/asset.exe",
                Digest = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
            };
            bool resDigestMalo = await downloader.DownloadAsync(relDigestMalo);
            check("OTA rechazo de digest incorrecto",
                  resDigestMalo == false && !File.Exists(downloader.StateFile),
                  downloader.LastError ?? "ok");

            // 3. Caso Descarga truncada
            mockHandler.Truncar = true;
            var relTruncada = new ReleaseInfo
            {
                TagName = "v2.7.5-test3",
                Version = "2.7.5",
                AssetName = "update_truncada.exe",
                AssetSize = payload.Length,
                AssetUrl = "https://mock.github.release/asset.exe",
                Digest = "sha256:" + hashPayload
            };
            bool resTruncada = await downloader.DownloadAsync(relTruncada);
            check("OTA detección de descarga truncada",
                  resTruncada == false && !File.Exists(downloader.StateFile),
                  downloader.LastError ?? "ok");
            mockHandler.Truncar = false;

            // 4. Caso Descarga íntegra válida
            var relValida = new ReleaseInfo
            {
                TagName = "v2.7.5-test4",
                Version = "2.7.5",
                AssetName = "update_valida.exe",
                AssetSize = payload.Length,
                AssetUrl = "https://mock.github.release/asset.exe",
                Digest = "sha256:" + hashPayload
            };
            bool resValida = await downloader.DownloadAsync(relValida);
            string destinoFinal = Path.Combine(downloader.PendingDir, "update_valida.exe");
            bool archivoExiste = File.Exists(destinoFinal);
            bool stateExiste = File.Exists(downloader.StateFile);
            string stateJson = stateExiste ? File.ReadAllText(downloader.StateFile) : "";
            bool applyTrue = stateJson.Contains("\"apply\": true") || stateJson.Contains("\"apply\":true");

            check("OTA descarga válida con digest SHA-256 verificado",
                  resValida == true && archivoExiste && stateExiste && applyTrue,
                  resValida ? "Estado y binario listos para aplicar" : (downloader.LastError ?? "fallo"));
        }
    }
}
