using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using AForge.Video;
using AForge.Video.DirectShow;

namespace Visor3D.Chat
{
    /// <summary>
    /// Captura de webcam vía DirectShow (AForge). Cada trama se reescala a
    /// 320x180 y se comprime en JPEG para no saturar el relay.
    /// </summary>
    public sealed class ChatWebcam : IDisposable
    {
        private readonly object _gate = new();
        private readonly Stopwatch _throttle = Stopwatch.StartNew();
        private VideoCaptureDevice? _dispositivo;
        private FilterInfoCollection? _dispositivos;
        private bool _disposed;

        private static readonly ImageCodecInfo? CodecJpeg =
            ImageCodecInfo.GetImageEncoders().FirstOrDefault(c => c.FormatID == ImageFormat.Jpeg.Guid);

        public bool IsRunning { get; private set; }
        public string? LastError { get; private set; }

        public event Action<byte[]>? FrameJpeg;
        public event Action<string>? Error;

        public static List<(int Index, string Name)> ListDevices()
        {
            var lista = new List<(int, string)>();
            try
            {
                var coleccion = new FilterInfoCollection(FilterCategory.VideoInputDevice);
                for (int i = 0; i < coleccion.Count; i++)
                    lista.Add((i, coleccion[i].Name));
            }
            catch { }
            return lista;
        }

        public bool Start(int indice = 0)
        {
            lock (_gate)
            {
                if (IsRunning) return true;
                try
                {
                    _dispositivos = new FilterInfoCollection(FilterCategory.VideoInputDevice);
                    if (_dispositivos.Count == 0)
                    {
                        LastError = "No hay ninguna webcam conectada.";
                        return false;
                    }
                    if (indice < 0 || indice >= _dispositivos.Count) indice = 0;

                    _dispositivo = new VideoCaptureDevice(_dispositivos[indice].MonikerString);
                    _dispositivo.NewFrame += OnNewFrame;
                    _dispositivo.VideoSourceError += OnVideoError;
                    _dispositivo.Start();
                    IsRunning = true;
                    LastError = null;
                    return true;
                }
                catch (Exception ex)
                {
                    LastError = $"Webcam no disponible: {ex.Message}";
                    DetenerLocked();
                    return false;
                }
            }
        }

        private void OnVideoError(object? sender, VideoSourceErrorEventArgs e)
        {
            LastError = $"Webcam: {e.Description}";
            Error?.Invoke(LastError);
        }

        private void OnNewFrame(object? sender, NewFrameEventArgs e)
        {
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

        public void Stop()
        {
            lock (_gate) DetenerLocked();
        }

        private void DetenerLocked()
        {
            var disp = _dispositivo;
            _dispositivo = null;
            IsRunning = false;
            if (disp == null) return;
            try
            {
                disp.NewFrame -= OnNewFrame;
                disp.VideoSourceError -= OnVideoError;
                if (disp.IsRunning)
                {
                    disp.SignalToStop();
                    disp.WaitForStop();
                }
                disp.Stop();
            }
            catch { }
            _dispositivos = null;
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
