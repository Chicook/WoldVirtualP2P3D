using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using Visor3D.Services;

namespace Visor3D.Linux
{
    /// <summary>
    /// Lanza el motor Godot de Linux como proceso aparte (en Linux no se puede
    /// incrustar una ventana ajena como en Windows) con el mundo empaquetado,
    /// el rol de red resuelto y <c>p2p_session.json</c> en <c>user://</c>.
    /// La misma línea de órdenes que inyecta el visor WPF: <c>--main-pack</c>
    /// y, tras <c>--</c>, <c>--client/--ip/--port/--peer-url</c>.
    /// </summary>
    public sealed class LanzadorMundo : IDisposable
    {
        private Process? _proceso;

        public bool EnEjecucion => _proceso is { HasExited: false };
        public int IdProceso => _proceso?.Id ?? 0;

        public event Action<string>? Salida;
        public event Action<int>? Terminado;

        public static string? MotivoNoDisponible()
        {
            if (RutasLinux.MotorExe != null && RutasLinux.Pck != null) return null;
            if (RuntimeLinux.TieneMotorEmbebido && RuntimeLinux.TienePckEmbebido) return null;
            if (RutasLinux.MotorExe == null) return $"No se encuentra el motor ({RutasLinux.NombreMotor}).";
            return $"No se encuentra el mundo ({RutasLinux.NombrePck}).";
        }

        /// <summary>
        /// Arranca el motor. <paramref name="destino"/> es el enlace del
        /// anfitrión o una dirección <c>ip:8911</c>; vacío = anfitrión local.
        /// </summary>
        public bool Lanzar(string nick, string? destino, string tokenInvitacion, string? miTunel)
        {
            if (EnEjecucion) return true;

            // Motor y mundo viajan dentro del visor: si aún no están en disco, se
            // extraen aquí (idempotente; la UI ya lo suele haber hecho antes).
            if (!RuntimeLinux.Asegurar(out string? errorExtraccion, linea => Salida?.Invoke(linea)))
            {
                if (RutasLinux.MotorExe == null || RutasLinux.Pck == null)
                {
                    Salida?.Invoke("[visor] No se pudo preparar el motor: " + errorExtraccion);
                    return false;
                }
                Salida?.Invoke("[visor] Uso el motor y el mundo que hay junto al visor.");
            }

            string? problema = MotivoNoDisponible();
            if (problema != null)
            {
                Salida?.Invoke("[visor] " + problema);
                return false;
            }

            try
            {
                string motor = RutasLinux.MotorExe!;
                string pck = RutasLinux.Pck!;
                AsegurarEjecutable(motor);

                bool esCliente = TryParsearDestino(destino, out string host, out int puerto);
                string peerUrl = esCliente ? ConInvitacion(destino!.Trim(), tokenInvitacion) : "";

                EscribirSesion(esCliente, host, puerto, peerUrl, tokenInvitacion, miTunel);

                var args = new List<string> { "--main-pack", pck };
                if (esCliente)
                {
                    args.Add("--");
                    args.Add("--client");
                    args.Add($"--ip={host}");
                    args.Add($"--port={puerto}");
                    args.Add($"--peer-url={peerUrl}");
                }

                var info = new ProcessStartInfo
                {
                    FileName = motor,
                    WorkingDirectory = Path.GetDirectoryName(motor) ?? RutasLinux.BaseDir,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                };
                foreach (string arg in args) info.ArgumentList.Add(arg);

                var proceso = new Process { StartInfo = info, EnableRaisingEvents = true };
                proceso.OutputDataReceived += (_, e) => { if (e.Data != null) Salida?.Invoke(e.Data); };
                proceso.ErrorDataReceived += (_, e) => { if (e.Data != null) Salida?.Invoke(e.Data); };
                proceso.Exited += (_, _) =>
                {
                    int codigo = -1;
                    try { codigo = proceso.ExitCode; } catch { }
                    Salida?.Invoke($"[motor] proceso terminado (código {codigo}).");
                    Terminado?.Invoke(codigo);
                };

                if (!proceso.Start()) return false;

                proceso.BeginOutputReadLine();
                proceso.BeginErrorReadLine();
                _proceso = proceso;

                VisorLog.Info(esCliente
                    ? $"[mundo] Motor lanzado como CLIENTE → {host}:{puerto} (peer-url={peerUrl})."
                    : "[mundo] Motor lanzado como ANFITRIÓN local.");
                Salida?.Invoke(esCliente
                    ? $"[visor] Cliente remoto → {host}:{puerto}"
                    : "[visor] Anfitrión local (sin destino remoto).");
                return true;
            }
            catch (Exception ex)
            {
                VisorLog.Error("[mundo] No se pudo lanzar el motor", ex);
                Salida?.Invoke($"[visor] No se pudo lanzar el motor: {ex.Message}");
                return false;
            }
        }

        public void Detener()
        {
            var proceso = _proceso;
            if (proceso == null) return;
            try
            {
                if (!proceso.HasExited) proceso.Kill(entireProcessTree: true);
            }
            catch (Exception ex)
            {
                VisorLog.Warn($"[mundo] No se pudo detener el motor: {ex.Message}");
            }
        }

        public void Dispose()
        {
            Detener();
            _proceso?.Dispose();
            _proceso = null;
        }

        /// <summary>
        /// Ficha que el motor lee cuando no hay argumentos suficientes
        /// (<c>Red.gd</c> y <c>ChunkManager.gd</c>): misma forma que la del visor WPF.
        /// </summary>
        private static void EscribirSesion(bool esCliente, string host, int puerto,
                                           string peerUrl, string token, string? miTunel)
        {
            try
            {
                var sesion = new
                {
                    peerUrl = esCliente ? peerUrl : "",
                    invitacion = token,
                    remoteIp = esCliente ? host : "",
                    remotePort = esCliente ? puerto : 8911,
                    esCliente,
                    rolEfectivo = esCliente ? "cliente_remoto" : "servidor_local",
                    hostResuelto = esCliente ? host : "127.0.0.1",
                    myTunnelUrl = miTunel ?? "",
                    puertoLocal = 7890,
                    puertoGodot = 8911,
                    esPrimerUsuario = !esCliente,
                    plataforma = "linux",
                    timestamp = DateTime.UtcNow.ToString("o"),
                };

                Directory.CreateDirectory(RutasLinux.GodotUserDir);
                File.WriteAllText(
                    Path.Combine(RutasLinux.GodotUserDir, "p2p_session.json"),
                    JsonSerializer.Serialize(sesion, new JsonSerializerOptions { WriteIndented = true }),
                    new UTF8Encoding(false));
            }
            catch (Exception ex)
            {
                VisorLog.Warn($"[mundo] No se pudo escribir p2p_session.json: {ex.Message}");
            }
        }

        /// <summary>Añade <c>?invitacion=</c> (o <c>&amp;invitacion=</c>) a una URL del portal.</summary>
        private static string ConInvitacion(string destino, string token)
        {
            if (string.IsNullOrWhiteSpace(token)) return destino;
            if (!Uri.TryCreate(destino, UriKind.Absolute, out Uri? uri)) return destino;
            if (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps) return destino;

            string baseUrl = destino.TrimEnd('/');
            if (baseUrl.Contains("invitacion=", StringComparison.OrdinalIgnoreCase)) return baseUrl;
            string separador = baseUrl.Contains('?') ? "&" : "/?";
            return $"{baseUrl}{separador}invitacion={Uri.EscapeDataString(token)}";
        }

        /// <summary>
        /// Token de invitación que viaja en el enlace del anfitrión
        /// (<c>?invitacion=…</c>). Sin él, el portal del anfitrión rechaza el
        /// WebSocket del motor y del chat.
        /// </summary>
        public static string ExtraerInvitacion(string? entrada)
        {
            if (string.IsNullOrWhiteSpace(entrada)) return "";

            string s = entrada.Trim().Trim('"', '\'');
            int marca = s.IndexOf("invitacion=", StringComparison.OrdinalIgnoreCase);
            if (marca < 0) return "";

            string resto = s[(marca + "invitacion=".Length)..];
            int fin = resto.IndexOfAny(new[] { '&', '#', ' ', '\t' });
            if (fin >= 0) resto = resto[..fin];
            return Uri.UnescapeDataString(resto.Trim());
        }

        public static bool TryParsearDestino(string? entrada, out string host, out int puerto)
        {
            host = "";
            puerto = 8911;
            if (string.IsNullOrWhiteSpace(entrada)) return false;

            string s = entrada.Trim().Trim('"', '\'');
            if (s.StartsWith("http://", StringComparison.OrdinalIgnoreCase)) s = s[7..];
            else if (s.StartsWith("https://", StringComparison.OrdinalIgnoreCase)) s = s[8..];
            else if (s.StartsWith("woldvirtual://", StringComparison.OrdinalIgnoreCase)) s = s[15..];

            int barra = s.IndexOf('/');
            if (barra >= 0) s = s[..barra];

            int dosPuntos = s.LastIndexOf(':');
            if (dosPuntos > 0 && dosPuntos < s.Length - 1)
            {
                if (int.TryParse(s[(dosPuntos + 1)..], out int puertoLeido))
                {
                    // 3030-3040 y 7890 son puertos del portal/nodo: el motor viaja por 8911.
                    puerto = (puertoLeido is >= 3030 and <= 3040) || puertoLeido is 7890 or 80 or 443
                        ? 8911
                        : puertoLeido;
                }
                s = s[..dosPuntos];
            }

            host = s.Trim();
            return host.Length > 0;
        }

        private static void AsegurarEjecutable(string ruta)
        {
            if (!OperatingSystem.IsLinux()) return;
            try
            {
                var modo = File.GetUnixFileMode(ruta);
                if ((modo & UnixFileMode.UserExecute) == 0)
                    File.SetUnixFileMode(ruta, modo | UnixFileMode.UserExecute | UnixFileMode.GroupExecute | UnixFileMode.OtherExecute);
            }
            catch (Exception ex)
            {
                VisorLog.Warn($"[mundo] No se pudo marcar como ejecutable {ruta}: {ex.Message}");
            }
        }
    }
}
