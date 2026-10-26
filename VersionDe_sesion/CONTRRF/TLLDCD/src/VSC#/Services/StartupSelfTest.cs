using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

namespace Visor3D.Services
{
    /// <summary>
    /// Prueba de arranque previa a publicar (<c>--startup-selftest</c>). Comprueba,
    /// sin abrir ventana, lo que rompe una release: recursos embebidos, extracción
    /// del runtime, marcador de versión, portal WebNodo y arranque real del motor
    /// con el PCK. Escribe el resultado en logs\arranque-selftest.log y devuelve
    /// 0 sólo si todo pasa.
    /// </summary>
    public static class StartupSelfTest
    {
        public static int Run()
        {
            var salida = new StringBuilder();
            int fallos = 0;

            void Check(string nombre, bool ok, string detalle = "")
            {
                if (!ok) fallos++;
                string linea = $"[{(ok ? "OK" : "FALLO")}] {nombre}" +
                               (string.IsNullOrWhiteSpace(detalle) ? "" : $" — {detalle}");
                salida.AppendLine(linea);
                VisorLog.Info($"[arranque] {linea}");
            }

            try
            {
                var asm = Assembly.GetExecutingAssembly();
                var recursos = asm.GetManifestResourceNames();

                bool tieneMotor = Array.Exists(recursos, n => n.EndsWith("godot_exe.zip", StringComparison.OrdinalIgnoreCase));
                bool tienePck = Array.Exists(recursos, n => n.EndsWith("wvp3d.pck", StringComparison.OrdinalIgnoreCase));
                Check("Recursos embebidos (motor + mundo)", tieneMotor && tienePck,
                      $"motor={tieneMotor} pck={tienePck}");

                if (!tieneMotor || !tienePck)
                    return Cerrar(salida, fallos);

                AppExtractor.SilentErrors = true;
                bool extraido = AppExtractor.EnsureExtracted();
                Check("Extracción del runtime", extraido, AppExtractor.RuntimeDir);
                Check("Ejecutable del motor", File.Exists(AppExtractor.GodotExePath),
                      Tamano(AppExtractor.GodotExePath));

                long tamPck = new FileInfo(AppExtractor.PckPath).Exists
                    ? new FileInfo(AppExtractor.PckPath).Length : 0;
                Check("PCK extraído", tamPck > 100L * 1024 * 1024, $"{tamPck / 1048576.0:0.0} MiB");

                long tamEmbebido = 0;
                using (Stream? s = asm.GetManifestResourceStream("Visor3D.wvp3d.pck"))
                    if (s != null) tamEmbebido = s.Length;
                Check("PCK íntegro (extraído = embebido)", tamEmbebido > 0 && tamPck == tamEmbebido,
                      $"embebido={tamEmbebido / 1048576.0:0.0} MiB");

                string marcador = Path.Combine(AppExtractor.RuntimeDir, ".extracted");
                string versionMarcador = File.Exists(marcador) ? File.ReadAllText(marcador).Trim() : "";
                Check("Marcador de versión", versionMarcador == AppExtractor.Version,
                      $"marcador='{versionMarcador}' esperado='{AppExtractor.Version}'");

                ComprobarPortal(Check);
                ComprobarDescubrimiento(Check);

                if (File.Exists(AppExtractor.GodotExePath))
                    ComprobarMotor(Check);
            }
            catch (Exception ex)
            {
                Check("Prueba de arranque", false, $"{ex.GetType().Name}: {ex.Message}");
            }

            return Cerrar(salida, fallos);
        }

        private static void ComprobarPortal(Action<string, bool, string> check)
        {
            var nodo = new WebNodoService();
            try
            {
                nodo.Start();
                check("Portal WebNodo escucha", nodo.IsRunning,
                      nodo.IsRunning ? $"http://localhost:{nodo.ActivePort}/" : nodo.StartError ?? "sin detalle");
                if (!nodo.IsRunning) return;

                using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(20) };
                string baseUrl = $"http://127.0.0.1:{nodo.ActivePort}";

                string html = http.GetStringAsync(baseUrl + "/").GetAwaiter().GetResult();
                check("GET / responde el portal", html.Contains("Wold Virtual"), $"{html.Length} B");

                var token = Regex.Match(html, @"WT\s*=\s*'([^']+)'");
                check("Token de sesión embebido", token.Success, "");
                if (!token.Success) return;

                string info = http.GetStringAsync($"{baseUrl}/api/info?token={token.Groups[1].Value}")
                                  .GetAwaiter().GetResult();
                bool disponible = info.Contains("\"disponible\":true") && info.Contains(".exe");
                check("/api/info anuncia un .exe", disponible, info.Trim());

                // Presencia pública: otro visor debe poder saber si el nodo está en
                // línea sin conocer el token de esta sesión.
                nodo.PublicTunnelUrl = "https://nodo.invalid";
                bool presencia = DescubrimientoP2P.ConsultarNodoAsync(baseUrl)
                                                    .GetAwaiter().GetResult();
                check("/api/p2p-status sin token (presencia)", presencia, baseUrl);
            }
            catch (Exception ex)
            {
                check("Portal WebNodo", false, $"{ex.GetType().Name}: {ex.Message}");
            }
            finally
            {
                try { nodo.Dispose(); } catch { }
            }
        }

        /// <summary>
        /// Comprueba la escucha de la baliza LAN sin depender de otro equipo: el
        /// propio test inyecta un paquete válido y otro ajeno por loopback.
        /// </summary>
        private static void ComprobarDescubrimiento(Action<string, bool, string> check)
            => RedSelfTest.ComprobarDescubrimiento(check);

        private static void ComprobarMotor(Action<string, bool, string> check)
        {
            string log = Path.Combine(Path.GetTempPath(), "wvp3d_arranque_selftest.log");
            try { if (File.Exists(log)) File.Delete(log); } catch { }

            var psi = new ProcessStartInfo(AppExtractor.GodotExePath)
            {
                UseShellExecute = false,
                CreateNoWindow = true
            };
            psi.ArgumentList.Add("--headless");
            psi.ArgumentList.Add("--main-pack");
            psi.ArgumentList.Add(AppExtractor.PckPath);
            psi.ArgumentList.Add("--log-file");
            psi.ArgumentList.Add(log);
            psi.ArgumentList.Add("--quit-after");
            psi.ArgumentList.Add("300");

            using var proceso = Process.Start(psi);
            if (proceso == null)
            {
                check("Motor arranca desde el PCK", false, "no se pudo lanzar el proceso");
                return;
            }

            bool termino = proceso.WaitForExit(120_000);
            if (!termino)
            {
                try { proceso.Kill(entireProcessTree: true); } catch { }
                check("Motor arranca desde el PCK", false, "sin salida en 120 s");
                return;
            }

            string texto = File.Exists(log) ? File.ReadAllText(log) : "";
            bool mundo = texto.Contains("Isla 0 preparada") || texto.Contains("isla", StringComparison.OrdinalIgnoreCase);
            bool red = texto.Contains("Servidor WebSocket activo");
            bool errores = texto.Contains("ERROR:") || texto.Contains("SCRIPT ERROR");
            check("Motor arranca desde el PCK", proceso.ExitCode == 0 && mundo && red && !errores,
                  $"exit={proceso.ExitCode} isla={mundo} red={red} errores={errores}");
        }

        private static string Tamano(string ruta)
        {
            try { return new FileInfo(ruta).Exists ? $"{new FileInfo(ruta).Length / 1048576.0:0.0} MiB" : "no existe"; }
            catch { return "no legible"; }
        }

        private static int Cerrar(StringBuilder salida, int fallos)
        {
            salida.AppendLine(fallos == 0
                ? "RESULTADO ARRANQUE: OK"
                : $"RESULTADO ARRANQUE: {fallos} FALLO(S)");
            try
            {
                Directory.CreateDirectory(VisorLog.Carpeta);
                File.WriteAllText(Path.Combine(VisorLog.Carpeta, "arranque-selftest.log"), salida.ToString());
            }
            catch { }
            return fallos == 0 ? 0 : 1;
        }
    }
}
