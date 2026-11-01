using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using Visor3D.Seguridad.SMTPLC;

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
                string versionMarcador = File.Exists(marcador)
                    ? (File.ReadAllLines(marcador).FirstOrDefault()?.Trim() ?? "")
                    : "";
                Check("Marcador de versión", versionMarcador == AppExtractor.Version,
                      $"marcador='{versionMarcador}' esperado='{AppExtractor.Version}'");

                ComprobarPortal(Check);
                ComprobarDescubrimiento(Check);
                ComprobarUmbralVm(Check);
                ComprobarRecolector(Check);

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

        /// <summary>
        /// El detector y la política deben compartir umbral: si el detector marca VM
        /// por debajo del umbral de la política, una sola señal bloquea el registro.
        /// </summary>
        private static void ComprobarUmbralVm(Action<string, bool, string> check)
        {
            var policy = new SmtplcPolicy();
            bool ok = Math.Abs(VmDetector.UmbralVm - 0.50) < 0.0001 &&
                      Math.Abs(policy.VmConfidenceThreshold - VmDetector.UmbralVm) < 0.0001;
            check("Umbral de VM unificado (0,50)", ok,
                  $"detector={VmDetector.UmbralVm:0.00} política={policy.VmConfidenceThreshold:0.00}");
        }

        /// <summary>
        /// Purga del recolector sobre una raíz de usar y tirar: debe borrar las
        /// versiones viejas y conservar la vigente, la anterior y los ficheros sueltos.
        /// </summary>
        private static void ComprobarRecolector(Action<string, bool, string> check)
        {
            string raiz = Path.Combine(Path.GetTempPath(), "wvp3d_recolector_" + Guid.NewGuid().ToString("N"));
            try
            {
                foreach (var v in new[] { "2.6.9", "2.7.0", "2.7.1" })
                    Directory.CreateDirectory(Path.Combine(raiz, v));
                string nota = Path.Combine(raiz, "nota.txt");
                File.WriteAllText(nota, "no se toca");

                var (borradas, fallos) = RuntimeCleaner.PurgarAntiguos(raiz, "2.7.1", "2.7.0");
                bool ok = !Directory.Exists(Path.Combine(raiz, "2.6.9")) &&
                          Directory.Exists(Path.Combine(raiz, "2.7.0")) &&
                          Directory.Exists(Path.Combine(raiz, "2.7.1")) &&
                          File.Exists(nota) &&
                          borradas.Count == 1 && fallos.Count == 0;
                check("Recolector de runtimes (conserva vigente y anterior)", ok,
                      $"borradas=[{string.Join(", ", borradas)}] fallos={fallos.Count}");
            }
            catch (Exception ex)
            {
                check("Recolector de runtimes", false, $"{ex.GetType().Name}: {ex.Message}");
            }
            finally
            {
                try { Directory.Delete(raiz, recursive: true); } catch { }
            }
        }

        private static void ComprobarMotor(Action<string, bool, string> check)
        {
            string log = Path.Combine(Path.GetTempPath(), "wvp3d_arranque_selftest.log");
            try { if (File.Exists(log)) File.Delete(log); } catch { }

            // El mundo sólo carga si user://registro.cfg trae avatar y nick; sin eso
            // Boot.gd se queda en el carrusel esperando a que alguien elija y nunca
            // abre la isla ni el 8911. Por eso la prueba usa un perfil de usar y
            // tirar bajo %TEMP%: así no depende del perfil del equipo ni lo toca,
            // y un p2p_session.json real no la convierte en cliente remoto.
            string perfil = Path.Combine(Path.GetTempPath(), "wvp3d_arranque_perfil_" + Guid.NewGuid().ToString("N"));
            string datos = Path.Combine(perfil, "Godot", "app_userdata", "WoldVirtualP2P3D");

            var psi = new ProcessStartInfo(AppExtractor.GodotExePath)
            {
                UseShellExecute = false,
                CreateNoWindow = true
            };
            psi.Environment["APPDATA"] = perfil;
            psi.ArgumentList.Add("--headless");
            psi.ArgumentList.Add("--main-pack");
            psi.ArgumentList.Add(AppExtractor.PckPath);
            psi.ArgumentList.Add("--log-file");
            psi.ArgumentList.Add(log);
            psi.ArgumentList.Add("--quit-after");
            psi.ArgumentList.Add("3000");
            psi.ArgumentList.Add("--");
            psi.ArgumentList.Add("--server");

            try
            {
                Directory.CreateDirectory(datos);
                File.WriteAllText(Path.Combine(datos, "registro.cfg"),
                    "[jugador]\n\n" +
                    "avatar_scene=\"res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC/AVH1Ch3D.tscn\"\n" +
                    "nick=\"Prueba\"\n");
            }
            catch (Exception ex)
            {
                check("Motor arranca desde el PCK", false, $"no se pudo crear el perfil de prueba: {ex.Message}");
                return;
            }

            try
            {
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
                      $"exit={proceso.ExitCode} isla={mundo} red={red} errores={errores} perfil={perfil}");
            }
            finally
            {
                try { Directory.Delete(perfil, recursive: true); } catch { }
            }
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
            Console.WriteLine(salida.ToString());
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
