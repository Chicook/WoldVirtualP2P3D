using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Services
{
    public class ServidorLucIAOficial : IDisposable
    {
        public const int PuertoPorDefecto = 8765;
        private Process? _proceso;
        private Process? _ollama;
        private readonly int _puerto;
        private readonly SemaphoreSlim _inicio = new(1, 1);
        private readonly StringBuilder _salida = new();
        private bool _detenido;

        public bool EstaEnLinea { get; private set; }
        public string? UltimoError { get; private set; }
        public bool EstaEscuchando() => PuertoAbierto();

        public bool EstaListo()
        {
            try
            {
                using var cliente = new TcpClient();
                if (!cliente.ConnectAsync("127.0.0.1", _puerto).Wait(900)) return false;
                using var flujo = cliente.GetStream();
                flujo.ReadTimeout = 1500;
                using var lector = new StreamReader(flujo);
                using var saludo = JsonDocument.Parse(lector.ReadLine() ?? "{}");
                return saludo.RootElement.TryGetProperty("tipo", out var tipo) &&
                    tipo.GetString() == "hola" &&
                    saludo.RootElement.TryGetProperty("protocolo", out var protocolo) &&
                    protocolo.GetInt32() == 1;
            }
            catch { return false; }
        }

        public ServidorLucIAOficial(int puerto = PuertoPorDefecto) => _puerto = puerto;

        public async Task<bool> IniciarAsync(CancellationToken ct = default)
        {
            await _inicio.WaitAsync(ct);
            try
            {
                if (_detenido) return false;
                EstaEnLinea = false;
                UltimoError = null;
                if (PuertoAbierto())
                {
                    if (EstaListo())
                    {
                        EstaEnLinea = true;
                        return true;
                    }
                    return Fallar($"El puerto {_puerto} está ocupado pero no responde el protocolo de LucIA.");
                }

                string? python = GodotConfig.GetPythonExePath();
                string? script = BuscarScript();
                if (string.IsNullOrWhiteSpace(python) || !File.Exists(python))
                    return Fallar("Falta el Python privado de LucIA. Vuelve a extraer el runtime del visor.");
                if (string.IsNullOrWhiteSpace(script) || !File.Exists(script))
                    return Fallar("Falta servidor_lucia.py en el runtime de LucIA.");
                if (!await PrepararOllamaAsync(ct)) return false;
                if (_detenido) return false;

                if (_proceso == null || _proceso.HasExited)
                {
                    _proceso?.Dispose();
                    var psi = new ProcessStartInfo(python)
                    {
                        WorkingDirectory = Path.GetDirectoryName(script)!,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        StandardOutputEncoding = Encoding.UTF8,
                        StandardErrorEncoding = Encoding.UTF8,
                    };
                    psi.ArgumentList.Add("-I");
                    psi.ArgumentList.Add("-u");
                    psi.ArgumentList.Add("-B");
                    psi.ArgumentList.Add("-X");
                    psi.ArgumentList.Add("utf8");
                    psi.ArgumentList.Add(script);
                    psi.ArgumentList.Add("--puerto");
                    psi.ArgumentList.Add(_puerto.ToString());
                    psi.ArgumentList.Add("--sin-precalentar");
                    psi.ArgumentList.Add("--sin-precarga-voz");
                    psi.Environment["PYTHONIOENCODING"] = "utf-8";
                    psi.Environment["PYTHONUTF8"] = "1";
                    psi.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
                    lock (_salida) _salida.Clear();
                    _proceso = new Process { StartInfo = psi };
                    _proceso.OutputDataReceived += (_, e) => RegistrarSalida(e.Data);
                    _proceso.ErrorDataReceived += (_, e) => RegistrarSalida(e.Data);
                    VisorLog.Info($"[LucIA] Python: {python}; servidor: {script}");
                    _proceso.Start();
                    _proceso.BeginOutputReadLine();
                    _proceso.BeginErrorReadLine();
                }

                for (int i = 0; i < 60 && !_detenido; i++)
                {
                    await Task.Delay(500, ct);
                    if (EstaListo())
                    {
                        EstaEnLinea = true;
                        VisorLog.Info($"[LucIA] Cerebro listo en 127.0.0.1:{_puerto}");
                        return true;
                    }
                    if (_proceso.HasExited)
                    {
                        _proceso.WaitForExit();
                        string detalle;
                        lock (_salida) detalle = _salida.ToString().Trim();
                        return Fallar($"LucIA terminó (código {_proceso.ExitCode}). {detalle}");
                    }
                }
                return Fallar("LucIA no respondió al saludo dentro de 30 segundos. Revisa el registro del visor.");
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
            catch (Exception ex) { return Fallar($"Error al iniciar LucIA: {ex.Message}"); }
            finally { _inicio.Release(); }
        }

        private async Task<bool> PrepararOllamaAsync(CancellationToken ct)
        {
            string url = (Environment.GetEnvironmentVariable("LUCIA_OLLAMA_URL") ?? "http://127.0.0.1:11434").TrimEnd('/');
            using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(3) };
            string? datos = null;
            try { datos = await http.GetStringAsync(url + "/api/tags", ct); }
            catch (Exception ex) when (ex is HttpRequestException || (ex is TaskCanceledException && !ct.IsCancellationRequested)) { }
            if (datos == null && url == "http://127.0.0.1:11434")
            {
                string? ejecutable = new[]
                {
                    Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Ollama", "ollama.exe"),
                    Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Ollama", "ollama.exe"),
                }.FirstOrDefault(File.Exists);
                if (ejecutable != null && (_ollama == null || _ollama.HasExited))
                {
                    _ollama?.Dispose();
                    var inicio = new ProcessStartInfo(ejecutable)
                    {
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        WorkingDirectory = Path.GetDirectoryName(ejecutable)!,
                    };
                    inicio.ArgumentList.Add("serve");
                    inicio.Environment["OLLAMA_HOST"] = "127.0.0.1:11434";
                    _ollama = Process.Start(inicio);
                }
                if (_ollama != null)
                {
                    for (int i = 0; i < 20 && !_detenido; i++)
                    {
                        await Task.Delay(500, ct);
                        try { datos = await http.GetStringAsync(url + "/api/tags", ct); break; }
                        catch (Exception ex) when (ex is HttpRequestException || (ex is TaskCanceledException && !ct.IsCancellationRequested)) { }
                        if (_ollama.HasExited) break;
                    }
                }
            }
            if (datos == null)
                return Fallar("Ollama no responde. Inicia Ollama y descarga un modelo con: ollama pull qwen2.5:3b. El visor reintentará la conexión.");
            using var documento = JsonDocument.Parse(datos);
            if (!documento.RootElement.TryGetProperty("models", out var modelos) || modelos.GetArrayLength() == 0)
                return Fallar("Ollama no tiene modelos. Ejecuta: ollama pull qwen2.5:3b. El visor reintentará sin reinstalar.");
            string? forzado = Environment.GetEnvironmentVariable("LUCIA_MODELO");
            if (!string.IsNullOrWhiteSpace(forzado) && !modelos.EnumerateArray().Any(m =>
                m.TryGetProperty("name", out var nombre) && string.Equals(nombre.GetString(), forzado, StringComparison.OrdinalIgnoreCase)))
                return Fallar($"El modelo configurado en LUCIA_MODELO no está instalado: {forzado}.");
            return true;
        }

        private void RegistrarSalida(string? linea)
        {
            if (string.IsNullOrWhiteSpace(linea)) return;
            lock (_salida)
            {
                _salida.AppendLine(linea);
                if (_salida.Length > 4000) _salida.Remove(0, _salida.Length - 4000);
            }
            VisorLog.Info("[LucIA Python] " + linea);
        }

        private bool Fallar(string mensaje)
        {
            UltimoError = mensaje;
            EstaEnLinea = false;
            VisorLog.Error("[LucIA] " + mensaje);
            return false;
        }

        private bool PuertoAbierto()
        {
            try
            {
                using var cliente = new TcpClient();
                return cliente.ConnectAsync("127.0.0.1", _puerto).Wait(400) && cliente.Connected;
            }
            catch { return false; }
        }

        private static string? BuscarScript()
        {
            if (AppExtractor.EmbebeLucia) return AppExtractor.LuciaScriptPath;
            foreach (string src in GodotConfig.SrcCandidatos())
            {
                string candidato = Path.Combine(src, "MTBGT", "WoldVirtualP2P3D", "lucia3D",
                    "GLTF_lucIA", "celebro_3D", "puente_3D", "servidor_lucia.py");
                if (File.Exists(candidato)) return candidato;
            }
            return null;
        }

        public void Detener()
        {
            _detenido = true;
            foreach (var proceso in new[] { _proceso, _ollama })
            {
                if (proceso == null) continue;
                try
                {
                    if (!proceso.HasExited)
                    {
                        proceso.Kill(entireProcessTree: true);
                        proceso.WaitForExit(3000);
                    }
                }
                catch (Exception ex) { VisorLog.Info($"[LucIA] No se pudo cerrar el proceso propio: {ex.Message}"); }
                finally { proceso.Dispose(); }
            }
            EstaEnLinea = false;
        }

        public void Dispose() => Detener();
    }
}
