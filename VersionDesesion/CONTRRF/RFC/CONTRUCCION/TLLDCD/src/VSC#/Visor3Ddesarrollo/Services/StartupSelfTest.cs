using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
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
                bool tieneVolatil = Array.Exists(recursos, n => n.EndsWith("actualizacion_volatil.zip", StringComparison.OrdinalIgnoreCase));
                bool tienePatch = Array.Exists(recursos, n => n.EndsWith("dao_patch.pck", StringComparison.OrdinalIgnoreCase));
                bool tienePck = Array.Exists(recursos, n => n.EndsWith("wvp3d.pck", StringComparison.OrdinalIgnoreCase));
                bool modoDelta = tienePatch;
                bool modoCompleto = tienePck && !tienePatch;
                bool tienePaqueteMundo = tienePatch || tieneVolatil || tienePck;
                string etiquetaPaquete = modoDelta ? "parche DAO" : (modoCompleto ? "mundo completo" : "paquete volátil");
                Check("Recursos embebidos (motor + " + etiquetaPaquete + ")",
                      tieneMotor && tienePaqueteMundo,
                      $"motor={tieneMotor} patch={tienePatch} pck={tienePck} volatil={tieneVolatil}");

                if (!tieneMotor || !tienePaqueteMundo)
                    return Cerrar(salida, fallos);

                AppExtractor.SilentErrors = true;
                bool extraido = AppExtractor.EnsureExtracted();
                Check("Extracción del runtime (motor)", extraido, AppExtractor.RuntimeDir);
                Check("Ejecutable del motor", File.Exists(AppExtractor.GodotExePath),
                      Tamano(AppExtractor.GodotExePath));

                if (modoDelta)
                {
                    Check("Parche DAO extraído", File.Exists(AppExtractor.DaoPatchPath), Tamano(AppExtractor.DaoPatchPath));
                    bool baseDisponible = DeltaPackManager.EnsureBasePackAvailable();
                    Check("Base original 2.8.6 disponible", baseDisponible,
                          baseDisponible ? Tamano(DeltaPackManager.BasePckPath) : DeltaPackManager.BasePckPath);
                }
                else if (modoCompleto)
                {
                    Check("Mundo completo extraído", File.Exists(AppExtractor.PckPath), Tamano(AppExtractor.PckPath));
                }
                else
                {
                    bool montado = Visor3D.CargaVolatil.VolatilePackage.EnsureReady();
                    string? pckVol = Visor3D.CargaVolatil.VolatilePackage.PckVolatilPath;
                    long tamPck = !string.IsNullOrEmpty(pckVol) && File.Exists(pckVol)
                        ? new FileInfo(pckVol).Length : 0;
                    Check("Paquete volátil montado (PCK en RAM)", montado && tamPck > 100L * 1024 * 1024,
                          $"pck={tamPck / 1048576.0:0.0} MiB");

                    Check("Configuración en RAM (cuenta)",
                          !string.IsNullOrWhiteSpace(Visor3D.CargaVolatil.VolatilePackage.CuentaJson), "");
                    Check("Configuración en RAM (sesión)",
                          !string.IsNullOrWhiteSpace(Visor3D.CargaVolatil.VolatilePackage.SesionYaml), "");
                }

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
                    ComprobarMotor(Check, modoDelta);
            }
            catch (Exception ex)
            {
                Check("Prueba de arranque", false, $"{ex.GetType().Name}: {ex.Message}");
            }

            return Cerrar(salida, fallos);
        }

        public static int RunLucia() => Task.Run(RunLuciaAsync).GetAwaiter().GetResult();

        private static async Task<int> RunLuciaAsync()
        {
            const int puerto = 18765;
            var salida = new StringBuilder();
            bool correcto = false;
            bool silentErrorsAnterior = AppExtractor.SilentErrors;
            int turnosCorrectos = 0, turnosConVoz = 0, turnosSinVoz = 0;
            string fase = "runtime embebido";

            void Registrar(string mensaje)
            {
                salida.AppendLine(mensaje);
                VisorLog.Info("[lucia-selftest] " + mensaje);
            }

            void Exigir(bool ok, string detalle)
            {
                if (!ok) throw new InvalidDataException(detalle);
                Registrar("[OK] " + detalle);
            }

            static string Texto(JsonElement evento, string campo) =>
                evento.TryGetProperty(campo, out var valor) && valor.ValueKind == JsonValueKind.String
                    ? valor.GetString() ?? "" : "";

            try
            {
                Registrar($"LucIA selftest: {DateTimeOffset.Now:O}; versión={AppExtractor.Version}; " +
                          $"EXE={Environment.ProcessPath}; build_id={typeof(AppExtractor).Assembly.ManifestModule.ModuleVersionId}");
                Exigir(AppExtractor.EmbebeLucia, "El EXE contiene el runtime de LucIA (sin recurrir al repositorio)");
                AppExtractor.SilentErrors = true;
                fase = "extracción normal";
                Exigir(AppExtractor.EnsureExtracted(), "Extracción normal: " + AppExtractor.RuntimeDir);
                string? python = GodotConfig.GetPythonExePath();
                Exigir(python == AppExtractor.LuciaPythonPath && File.Exists(python),
                    $"Python privado: resuelto={python ?? "no disponible"}; esperado={AppExtractor.LuciaPythonPath}");
                string directorio = Path.GetFullPath(AppExtractor.LuciaDir)
                    .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
                string script = Path.GetFullPath(AppExtractor.LuciaScriptPath);
                Exigir(File.Exists(script) && script.StartsWith(directorio, StringComparison.OrdinalIgnoreCase),
                    "Servidor existente dentro de LuciaDir: " + script);

                fase = "puerto de prueba";
                Exigir(!IPGlobalProperties.GetIPGlobalProperties().GetActiveTcpListeners().Any(e => e.Port == puerto),
                    $"Puerto {puerto} libre; no se reutiliza un servidor preexistente");
                using (var servicio = new ServidorLucIAOficial(puerto))
                {
                    fase = "arranque de LucIA y diagnóstico Ollama (límite 120 s)";
                    Registrar("Ollama: " + ResumirLucia(Environment.GetEnvironmentVariable("LUCIA_OLLAMA_URL")
                        ?? "http://127.0.0.1:11434"));
                    using (var inicio = new CancellationTokenSource(TimeSpan.FromSeconds(120)))
                    {
                        bool iniciado = await servicio.IniciarAsync(inicio.Token);
                        Exigir(iniciado, "Inicio del servicio real; diagnóstico: " +
                            ResumirLucia(servicio.UltimoError ?? "Ollama y servidor disponibles"));
                    }

                    using var cliente = new TcpClient();
                    fase = "conexión TCP y saludo (límite 10 s)";
                    using var conexion = new CancellationTokenSource(TimeSpan.FromSeconds(10));
                    await cliente.ConnectAsync(IPAddress.Loopback, puerto, conexion.Token);
                    using var flujo = cliente.GetStream();
                    using var lector = new StreamReader(flujo, new UTF8Encoding(false, true));
                    using var escritor = new StreamWriter(flujo, new UTF8Encoding(false))
                    {
                        AutoFlush = true,
                        NewLine = "\n"
                    };
                    using var saludo = await LeerEventoLuciaAsync(lector, conexion.Token);
                    var hola = saludo.RootElement;
                    if (Texto(hola, "tipo") == "error")
                        throw new InvalidDataException("error: " + ResumirLucia(Texto(hola, "mensaje")));
                    Exigir(Texto(hola, "tipo") == "hola" &&
                        hola.TryGetProperty("protocolo", out var protocolo) &&
                        protocolo.ValueKind == JsonValueKind.Number && protocolo.TryGetInt32(out int version) && version == 1,
                        "Saludo hola con protocolo 1");
                    string modelo = Texto(hola, "modelo");
                    Exigir(!string.IsNullOrWhiteSpace(modelo), "Modelo anunciado: " + ResumirLucia(modelo));

                    string[] consultas =
                    {
                        "Hola, Lucía. Preséntate en español y dime en dos frases cómo puedes ayudarme a explorar este mundo virtual.",
                        "Lucía, explícame en español dos consejos sencillos para colaborar de forma segura con otras personas en un mundo virtual."
                    };
                    for (int i = 0; i < consultas.Length; i++)
                    {
                        int turno = i + 1;
                        fase = $"turno {turno} (límite total 180 s)";
                        using var limite = new CancellationTokenSource(TimeSpan.FromSeconds(180));
                        Registrar($"[ENVÍO] Turno {turno}: {consultas[i]}");
                        string consulta = JsonSerializer.Serialize(new { tipo = "consulta", texto = consultas[i] });
                        await escritor.WriteLineAsync(consulta.AsMemory(), limite.Token);
                        bool fin = false;
                        int tokens = 0, avisos = 0;
                        long bytesPcm = 0;
                        var respuesta = new StringBuilder();
                        while (!fin)
                        {
                            limite.Token.ThrowIfCancellationRequested();
                            using var documento = await LeerEventoLuciaAsync(lector, limite.Token);
                            var evento = documento.RootElement;
                            string tipo = Texto(evento, "tipo");
                            switch (tipo)
                            {
                                case "estado":
                                    Registrar($"[EVENTO] Turno {turno}: estado={ResumirLucia(Texto(evento, "estado"))}");
                                    break;
                                case "token":
                                    string fragmento = Texto(evento, "texto");
                                    respuesta.Append(fragmento);
                                    tokens++;
                                    Registrar($"[EVENTO] Turno {turno}: token texto={ResumirLucia(fragmento)}");
                                    break;
                                case "voz":
                                    byte[] pcm = Convert.FromBase64String(Texto(evento, "pcm"));
                                    int rate = evento.GetProperty("rate").GetInt32();
                                    int canales = evento.GetProperty("canales").GetInt32();
                                    Exigir(pcm.Length > 0 && rate > 0 && canales > 0 && pcm.Length % (2L * canales) == 0,
                                        $"Turno {turno}: voz PCM16 recibida, bytes={pcm.Length}, rate={rate}, canales={canales} (sin reproducir)");
                                    bytesPcm += pcm.Length;
                                    break;
                                case "aviso":
                                    string aviso = Texto(evento, "mensaje");
                                    if (string.IsNullOrWhiteSpace(aviso))
                                        throw new InvalidDataException("Evento aviso sin mensaje");
                                    avisos++;
                                    Registrar($"[AVISO] Turno {turno}: {ResumirLucia(aviso)}");
                                    break;
                                case "error":
                                    throw new InvalidDataException("Evento error: " + ResumirLucia(Texto(evento, "mensaje")));
                                case "fin":
                                    string textoFinal = Texto(evento, "texto");
                                    string modeloFinal = Texto(evento, "modelo");
                                    Registrar($"[EVENTO] Turno {turno}: fin modelo={ResumirLucia(modeloFinal)}; texto={ResumirLucia(textoFinal)}");
                                    Exigir(tokens > 0 && !string.IsNullOrWhiteSpace(respuesta.ToString()) &&
                                        !string.IsNullOrWhiteSpace(textoFinal), $"Turno {turno}: texto no vacío en token y fin");
                                    Exigir(modeloFinal == modelo, $"Turno {turno}: fin del modelo anunciado");
                                    Exigir(bytesPcm > 0 || avisos > 0,
                                        $"Turno {turno}: voz PCM={bytesPcm} bytes; avisos={avisos} (se exige PCM o aviso explícito)");
                                    fin = true;
                                    break;
                                default:
                                    throw new InvalidDataException("Evento de protocolo inesperado: " + ResumirLucia(tipo));
                            }
                        }
                        limite.Token.ThrowIfCancellationRequested();
                        turnosCorrectos++;
                        if (bytesPcm > 0) turnosConVoz++;
                        else turnosSinVoz++;
                        Registrar($"[OK] Turno {turno}: respuesta real hasta fin; tokens={tokens}; errores=0; " +
                            (bytesPcm > 0 ? $"VOZ: PCM RECIBIDO ({bytesPcm} bytes)" : "VOZ: SIN PCM, CON AVISO; voz no validada"));
                    }
                    fase = "cierre del servicio propio";
                }
                Exigir(turnosCorrectos == 2, "Dos consultas reales completadas; servicio propio cerrado");
                correcto = true;
            }
            catch (OperationCanceledException)
            {
                Registrar($"[FALLO] {fase}: tiempo agotado; prueba interrumpida sin reintentos");
            }
            catch (Exception ex)
            {
                Registrar($"[FALLO] {fase}: {ex.GetType().Name}: {ResumirLucia(ex.Message)}");
            }
            finally
            {
                AppExtractor.SilentErrors = silentErrorsAnterior;
            }

            string Resultado() => $"RESULTADO LUCIA: {(correcto ? "OK" : "FALLO")}; turnos correctos={turnosCorrectos}/2; " +
                                  $"turnos con PCM={turnosConVoz}; turnos SIN VOZ con aviso={turnosSinVoz}";
            try
            {
                string? dev = Environment.GetEnvironmentVariable("WOLD_DEV_DIR");
                string logDir = string.IsNullOrWhiteSpace(dev) ? VisorLog.Carpeta : Path.Combine(dev, "logs");
                Directory.CreateDirectory(logDir);
                File.WriteAllText(Path.Combine(logDir, "lucia-selftest.log"),
                    salida.ToString() + Resultado() + Environment.NewLine);
            }
            catch (Exception ex)
            {
                correcto = false;
                Registrar("[FALLO] No se pudo guardar lucia-selftest.log: " + ResumirLucia(ex.Message));
            }
            Registrar(Resultado());
            Console.WriteLine(salida.ToString());
            return correcto ? 0 : 1;
        }

        private static async Task<JsonDocument> LeerEventoLuciaAsync(StreamReader lector, CancellationToken ct)
        {
            string? linea = await lector.ReadLineAsync(ct);
            if (linea == null) throw new EndOfStreamException("LucIA cerró la conexión antes de completar el protocolo");
            return JsonDocument.Parse(linea);
        }

        private static string ResumirLucia(string texto)
        {
            string linea = texto.Replace('\r', ' ').Replace('\n', ' ');
            return linea.Length <= 500 ? linea : linea.Substring(0, 500) + " [truncado]";
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

        private static void ComprobarMotor(Action<string, bool, string> check, bool modoDelta)
        {
            string raizPruebas = Environment.GetEnvironmentVariable("WOLD_DEV_DIR") ?? "";
            if (string.IsNullOrWhiteSpace(raizPruebas)) raizPruebas = Path.GetTempPath();
            string log = Path.Combine(raizPruebas, "startup-selftest", "godot.log");
            try { if (File.Exists(log)) File.Delete(log); } catch { }

            // El mundo sólo carga si user://registro.cfg trae avatar y nick; sin eso
            // Boot.gd se queda en el carrusel esperando a que alguien elija y nunca
            // abre la isla ni el 8911. Por eso la prueba usa un perfil de usar y
            // tirar en el directorio de pruebas: así no depende del perfil del equipo ni lo toca,
            // y un p2p_session.json real no la convierte en cliente remoto.
            string perfil = Path.Combine(raizPruebas, "startup-selftest", "perfil_" + Guid.NewGuid().ToString("N"));
            string datos = Path.Combine(perfil, "Godot", "app_userdata", "WoldVirtualP2P3D");

            var psi = new ProcessStartInfo(AppExtractor.GodotExePath)
            {
                UseShellExecute = false,
                CreateNoWindow = true
            };
            psi.Environment["APPDATA"] = perfil;
            psi.ArgumentList.Add("--headless");
            psi.ArgumentList.Add("--main-pack");
            psi.ArgumentList.Add(modoDelta
                ? AppExtractor.DaoPatchPath
                : Visor3D.CargaVolatil.VolatilePackage.PckVolatilPath ?? AppExtractor.PckPath);
            psi.ArgumentList.Add("--log-file");
            psi.ArgumentList.Add(log);
            // El mundo completo son 509 MiB: la isla necesita más de un puñado de
            // iteraciones para montarse en headless antes de que el motor salga.
            psi.ArgumentList.Add("--quit-after");
            psi.ArgumentList.Add("15000");
            psi.ArgumentList.Add("--");
            psi.ArgumentList.Add("--server");
            // LucIA recibe siempre a una persona; la prueba no la tiene. Con este
            // indicador, el motor entra directo con el perfil guardado y monta la
            // isla y el 8911, que es lo que la autoprueba comprueba.
            psi.ArgumentList.Add("--sin-recepcion");

            if (modoDelta)
                psi.Environment["WOLD_BASE_PCK"] = DeltaPackManager.BasePckPath;

            try { Directory.CreateDirectory(Path.GetDirectoryName(log)!); }
            catch (Exception ex)
            {
                check("Motor arranca desde el PCK", false, $"no se pudo preparar el directorio de prueba: {ex.Message}");
                return;
            }

            try
            {
                Directory.CreateDirectory(datos);
                File.WriteAllText(Path.Combine(datos, "registro.cfg"),
                    "[jugador]\n\n" +
                    "avatar_scene=\"res://avatares/AVH1.tscn\"\n" +
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
                // Godot 4.7 en Windows registra este ERROR cuando no puede leer el
                // almacén de certificados del sistema; no afecta al mundo ni a la red.
                string sinAvisoCertificados = texto.Replace(
                    "ERROR: Failed to read the root certificate store.", "");
                bool mundo = texto.Contains("Isla 0 preparada");
                bool red = texto.Contains("Servidor WebSocket activo");
                bool errores = sinAvisoCertificados.Contains("ERROR:") ||
                               texto.Contains("SCRIPT ERROR");
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
