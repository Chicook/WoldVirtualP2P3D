using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using AForge.Video;
using AForge.Video.DirectShow;
using Microsoft.Win32;
using Visor3D.Services;

namespace Visor3D.Chat
{
    /// <summary>
    /// Captura de webcam vía DirectShow (AForge). Cada trama se reescala a
    /// 320x180 y se comprime en JPEG para no saturar el relay.
    /// <para>
    /// Un PC suele exponer varias "cámaras": la real y filtros de software
    /// (OBS Virtual Camera, ManyCam, NVIDIA Broadcast…) que arrancan sin error
    /// pero no entregan ninguna trama. Por eso <see cref="Start"/> no se queda
    /// con el índice 0: ordena los dispositivos por probabilidad de ser una
    /// cámara real, comprueba que el elegido entregue imagen y, si no, pasa al
    /// siguiente. Cuando no hay ninguna, <see cref="LastError"/> dice por qué.
    /// </para>
    /// </summary>
    public sealed class ChatWebcam : IDisposable
    {
        /// <summary>Milisegundos que se espera la primera trama de cada candidato.</summary>
        private const int TimeoutPrimeraTramaMs = 1500;

        /// <summary>Cuántos dispositivos se prueban antes de rendirse.</summary>
        private const int MaxCandidatos = 3;

        /// <summary>Sin tramas durante este tiempo, la cámara se da por caída.</summary>
        private const int CaidaSinTramaMs = 6000;

        /// <summary>Interfaz de dispositivo de cámara (KSCATEGORY_VIDEO_CAMERA).</summary>
        private const string InterfazCamara =
            @"SYSTEM\CurrentControlSet\Control\DeviceClasses\{e5323777-f976-4f5b-9b55-b94699c46e44}";

        private const string ConsentimientoCamara =
            @"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam";

        private static readonly string[] NombresVirtuales =
        {
            "obs virtual", "virtual camera", "cámara virtual", "camara virtual", "manycam",
            "snap camera", "nvidia broadcast", "xsplit", "epoccam", "droidcam", "splitcam", "vcam"
        };

        private static readonly string[] NombresNoRgb =
        {
            " ir", "infrared", "infrarroj", "depth", "profundidad", "windows hello", "face auth"
        };

        private readonly object _gate = new();
        private readonly Stopwatch _throttle = Stopwatch.StartNew();
        private VideoCaptureDevice? _dispositivo;
        private bool _disposed;

        private ManualResetEventSlim? _esperaTrama;
        private DateTime _ultimaTrama = DateTime.MinValue;
        private Timer? _vigia;
        private int _sinTramaAvisado;

        private static readonly ImageCodecInfo? CodecJpeg =
            ImageCodecInfo.GetImageEncoders().FirstOrDefault(c => c.FormatID == ImageFormat.Jpeg.Guid);

        public bool IsRunning { get; private set; }
        public string? LastError { get; private set; }

        /// <summary>Nombre del dispositivo que está entregando imagen.</summary>
        public string? ActiveDevice { get; private set; }

        /// <summary>Excepción de la última enumeración DirectShow, si la hubo.</summary>
        public static string? LastEnumerationError { get; private set; }

        public event Action<byte[]>? FrameJpeg;
        public event Action<string>? Error;

        public static List<(int Index, string Name)> ListDevices() =>
            Enumerar().Select(d => (d.Index, d.Name)).ToList();

        /// <summary>Enumeración DirectShow con su moniker; nunca lanza.</summary>
        private static List<(int Index, string Name, string Moniker)> Enumerar()
        {
            var lista = new List<(int, string, string)>();
            try
            {
                var coleccion = new FilterInfoCollection(FilterCategory.VideoInputDevice);
                for (int i = 0; i < coleccion.Count; i++)
                    lista.Add((i, coleccion[i].Name, coleccion[i].MonikerString));
                LastEnumerationError = null;
            }
            catch (Exception ex)
            {
                LastEnumerationError = $"{ex.GetType().Name}: {ex.Message}";
                VisorLog.Error("[Webcam] la enumeración DirectShow falló", ex);
            }
            return lista;
        }

        public bool Start(int indice = 0)
        {
            lock (_gate)
            {
                if (IsRunning) return true;

                var detectados = Enumerar();
                if (detectados.Count == 0)
                {
                    LastError = DiagnosticosSinCamara();
                    VisorLog.Warn("[Webcam] " + LastError);
                    Error?.Invoke(LastError);
                    return false;
                }

                var descartes = new List<string>();
                foreach (var candidato in OrdenarCandidatos(detectados, indice).Take(MaxCandidatos))
                {
                    if (IntentarArrancar(candidato, out string? fallo))
                    {
                        LastError = null;
                        ActiveDevice = candidato.Name;
                        VisorLog.Info(descartes.Count == 0
                            ? $"[Webcam] activa: {candidato.Name}"
                            : $"[Webcam] activa: {candidato.Name} — sin imagen en {string.Join("; ", descartes)}");
                        return true;
                    }
                    descartes.Add($"{candidato.Name} ({fallo})");
                }

                ActiveDevice = null;
                LastError = descartes.Count == 0
                    ? "No se pudo abrir ninguna webcam."
                    : "Ninguna webcam entregó imagen: " + string.Join(" | ", descartes);
                VisorLog.Warn("[Webcam] " + LastError);
                Error?.Invoke(LastError);
                return false;
            }
        }

        /// <summary>
        /// Arranca un dispositivo y sólo lo da por bueno cuando llega la primera
        /// trama: un filtro de software devuelve <c>Start()</c> correcto y se
        /// queda mudo, que es justo el fallo que dejaba la imagen en negro.
        /// </summary>
        private bool IntentarArrancar((int Index, string Name, string Moniker) candidato, out string? fallo)
        {
            fallo = null;
            VideoCaptureDevice? dispositivo = null;
            var espera = new ManualResetEventSlim(false);

            try
            {
                _esperaTrama = espera;
                _ultimaTrama = DateTime.MinValue;
                Interlocked.Exchange(ref _sinTramaAvisado, 0);

                dispositivo = new VideoCaptureDevice(candidato.Moniker);
                dispositivo.NewFrame += OnNewFrame;
                dispositivo.VideoSourceError += OnVideoError;
                dispositivo.Start();

                if (!espera.Wait(TimeoutPrimeraTramaMs))
                {
                    fallo = "arranca pero no entrega ninguna trama";
                    DetenerDispositivo(dispositivo);
                    return false;
                }

                _dispositivo = dispositivo;
                IsRunning = true;
                _throttle.Restart();
                ArrancarVigia(candidato.Name);
                return true;
            }
            catch (Exception ex)
            {
                fallo = $"{ex.GetType().Name}: {ex.Message}";
                if (dispositivo != null) DetenerDispositivo(dispositivo);
                return false;
            }
            finally
            {
                _esperaTrama = null;
                espera.Dispose();
            }
        }

        /// <summary>
        /// Las cámaras reales se registran como dispositivos PnP
        /// (<c>@device:pnp:</c>); las virtuales son filtros de software
        /// (<c>@device:sw:</c>). El índice pedido por el llamante sólo tiene
        /// preferencia si apunta a un dispositivo plausible.
        /// </summary>
        private static IEnumerable<(int Index, string Name, string Moniker)> OrdenarCandidatos(
            List<(int Index, string Name, string Moniker)> detectados, int indicePreferido)
        {
            return detectados
                .Select(d => (Dispositivo: d, Puntos: Puntuacion(d.Name, d.Moniker)))
                .OrderByDescending(x => x.Puntos + (x.Dispositivo.Index == indicePreferido && x.Puntos >= 0 ? 1000 : 0))
                .ThenBy(x => x.Dispositivo.Index)
                .Select(x => x.Dispositivo);
        }

        private static int Puntuacion(string nombre, string moniker)
        {
            int puntos = 0;
            string n = nombre.ToLowerInvariant();
            string m = moniker.ToLowerInvariant();

            if (m.StartsWith("@device:pnp:", StringComparison.Ordinal)) puntos += 100;
            else if (m.StartsWith("@device:sw:", StringComparison.Ordinal)) puntos -= 100;

            if (NombresVirtuales.Any(v => n.Contains(v))) puntos -= 60;
            if (NombresNoRgb.Any(v => n.Contains(v))) puntos -= 40;

            return puntos;
        }

        /// <summary>Vigía que avisa si la cámara activa se queda muda en plena sesión.</summary>
        private void ArrancarVigia(string nombre)
        {
            _vigia?.Dispose();
            _vigia = new Timer(_ =>
            {
                if (!IsRunning || Interlocked.CompareExchange(ref _sinTramaAvisado, 1, 0) != 0) return;

                DateTime ultima = _ultimaTrama;
                if (ultima == DateTime.MinValue) return;

                double segundos = (DateTime.UtcNow - ultima).TotalSeconds;
                if (segundos * 1000 < CaidaSinTramaMs)
                {
                    Interlocked.Exchange(ref _sinTramaAvisado, 0);
                    return;
                }

                string mensaje = $"La cámara «{nombre}» dejó de enviar imagen hace {segundos:0} s.";
                LastError = mensaje;
                VisorLog.Warn("[Webcam] " + mensaje);
                Error?.Invoke(mensaje);
            }, null, 2000, 2000);
        }

        private void OnVideoError(object? sender, VideoSourceErrorEventArgs e)
        {
            LastError = $"Webcam: {e.Description}";
            VisorLog.Warn("[Webcam] " + LastError);
            Error?.Invoke(LastError);
        }

        private void OnNewFrame(object? sender, NewFrameEventArgs e)
        {
            _ultimaTrama = DateTime.UtcNow;
            var espera = _esperaTrama;
            if (espera != null)
            {
                try { espera.Set(); } catch { }
            }

            if (_throttle.ElapsedMilliseconds < 1000 / ChatProtocol.VideoFps) return;
            _throttle.Restart();

            try
            {
                using var origen = (Bitmap)e.Frame.Clone();
                using var peque = new Bitmap(ChatProtocol.VideoWidth, ChatProtocol.VideoHeight);
                using (var g = Graphics.FromImage(peque))
                {
                    g.InterpolationMode = InterpolationMode.Bilinear;
                    g.PixelOffsetMode = PixelOffsetMode.HighSpeed;
                    g.DrawImage(origen, 0, 0, ChatProtocol.VideoWidth, ChatProtocol.VideoHeight);
                }

                using var ms = new MemoryStream();
                if (CodecJpeg != null)
                {
                    using var parametros = new EncoderParameters(1);
                    parametros.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, 55L);
                    peque.Save(ms, CodecJpeg, parametros);
                }
                else
                {
                    peque.Save(ms, ImageFormat.Jpeg);
                }

                FrameJpeg?.Invoke(ms.ToArray());
            }
            catch (Exception ex)
            {
                LastError = $"Webcam: {ex.Message}";
                Error?.Invoke(LastError);
            }
        }

        /// <summary>
        /// Explica por qué no aparece ninguna cámara en vez de limitarse a
        /// decir que no hay: Wine no expone DirectShow, Windows puede tener la
        /// cámara bloqueada por privacidad y el registro sabe si hay hardware
        /// aunque DirectShow no lo liste.
        /// </summary>
        private static string DiagnosticosSinCamara()
        {
            if (LastEnumerationError != null)
                return "DirectShow no pudo enumerar las cámaras (" + LastEnumerationError + ").";

            if (CorreBajoWine())
                return "El visor está corriendo bajo Wine, que no expone las cámaras por DirectShow: " +
                       "la webcam sólo funciona en Windows nativo.";

            if (string.Equals(Consentimiento(), "Deny", StringComparison.OrdinalIgnoreCase))
                return "Windows tiene bloqueado el acceso a la cámara " +
                       "(Configuración → Privacidad y seguridad → Cámara → acceso y aplicaciones de escritorio).";

            int interfaces = ContarInterfacesCamara();
            if (interfaces > 0)
                return $"El sistema registra {interfaces} cámara(s) pero DirectShow no expone ninguna: " +
                       "controlador en uso por otra aplicación, incompatible o pendiente de reconectar.";

            return "No hay ninguna webcam conectada.";
        }

        private static bool CorreBajoWine()
        {
            try
            {
                if (NativeLibrary.TryLoad("ntdll.dll", out IntPtr modulo) &&
                    NativeLibrary.TryGetExport(modulo, "wine_get_version", out _)) return true;
            }
            catch { }

            try
            {
                using var clave = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Wine");
                if (clave != null) return true;
            }
            catch { }

            return false;
        }

        private static string? Consentimiento()
        {
            foreach (var raiz in new[] { RegistryHive.CurrentUser, RegistryHive.LocalMachine })
            {
                try
                {
                    using var colmena = RegistryKey.OpenBaseKey(raiz, RegistryView.Default);
                    using var clave = colmena.OpenSubKey(ConsentimientoCamara);
                    if (clave?.GetValue("Value") is string valor) return valor;
                }
                catch { }
            }
            return null;
        }

        private static int ContarInterfacesCamara()
        {
            try
            {
                using var clave = Registry.LocalMachine.OpenSubKey(InterfazCamara);
                return clave?.GetSubKeyNames().Count(n => !n.Equals("Properties", StringComparison.OrdinalIgnoreCase)) ?? 0;
            }
            catch
            {
                return 0;
            }
        }

        public void Stop()
        {
            lock (_gate) DetenerLocked();
        }

        private void DetenerLocked()
        {
            var disp = _dispositivo;
            _dispositivo = null;
            IsRunning = false;
            ActiveDevice = null;

            _vigia?.Dispose();
            _vigia = null;

            if (disp == null) return;
            DetenerDispositivo(disp);
        }

        /// <summary>
        /// Desengancha los manejadores antes de parar y no espera indefinidamente:
        /// durante el cambio de candidato un <c>WaitForStop</c> colgado dejaría
        /// el botón de cámara bloqueado.
        /// </summary>
        private void DetenerDispositivo(VideoCaptureDevice dispositivo)
        {
            try
            {
                dispositivo.NewFrame -= OnNewFrame;
                dispositivo.VideoSourceError -= OnVideoError;

                if (dispositivo.IsRunning)
                {
                    dispositivo.SignalToStop();
                    var limite = Stopwatch.StartNew();
                    while (dispositivo.IsRunning && limite.ElapsedMilliseconds < 1200)
                        Thread.Sleep(25);
                    if (dispositivo.IsRunning) dispositivo.Stop();
                }
            }
            catch { }
        }

        public void Dispose()
        {
            lock (_gate)
            {
                if (_disposed) return;
                _disposed = true;
            }
            Stop();
        }
    }
}
