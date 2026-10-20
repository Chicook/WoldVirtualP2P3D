using System;
using System.Diagnostics;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.RedP2P
{
    /// <summary>
    /// Gestiona un túnel SSH efímero usando localhost.run (sin instalación extra).
    /// Cuando el proceso SSH imprime la URL pública en stderr/stdout, la extrae y
    /// dispara el evento UrlObtenida.
    /// </summary>
    public class P2PTunnelManager : IDisposable
    {
        private Process? _tunnelProcess;
        private CancellationTokenSource? _cts;
        private bool _disposed;

        /// <summary>Disparado cuando el túnel ya tiene URL pública disponible.</summary>
        public event Action<string>? UrlObtenida;

        /// <summary>Disparado si el proceso del túnel muere inesperadamente.</summary>
        public event Action? TunnelMuerto;

        /// <summary>Puerto local donde escucha el nodo P2P de este visor.</summary>
        public int PuertoLocal { get; }

        public string? UrlPublica { get; private set; }

        public P2PTunnelManager(int puertoLocal = 7890)
        {
            PuertoLocal = puertoLocal;
        }

        /// <summary>
        /// Inicia el túnel SSH hacia localhost.run apuntando a <see cref="PuertoLocal"/>.
        /// La URL llega de forma asíncrona a través del evento <see cref="UrlObtenida"/>.
        /// </summary>
        public Task IniciarAsync()
        {
            if (_tunnelProcess != null) return Task.CompletedTask;

            _cts = new CancellationTokenSource();

            var psi = new ProcessStartInfo
            {
                FileName               = "ssh",
                // -o StrictHostKeyChecking=no evita que cuelgue esperando confirmación de host
                // -R 80 reenvía el puerto local al servidor de localhost.run
                Arguments              = $"-o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:localhost:{PuertoLocal} nokey@localhost.run",
                UseShellExecute        = false,
                CreateNoWindow         = true,
                RedirectStandardOutput = true,
                RedirectStandardError  = true
            };

            _tunnelProcess = new Process { StartInfo = psi, EnableRaisingEvents = true };
            _tunnelProcess.Exited += (_, _) => TunnelMuerto?.Invoke();

            // localhost.run imprime la URL tanto en stdout como en stderr
            _tunnelProcess.OutputDataReceived += (_, e) => ProcesarLinea(e.Data);
            _tunnelProcess.ErrorDataReceived  += (_, e) => ProcesarLinea(e.Data);

            _tunnelProcess.Start();
            _tunnelProcess.BeginOutputReadLine();
            _tunnelProcess.BeginErrorReadLine();

            return Task.CompletedTask;
        }

        private static readonly Regex RegexUrl =
            new(@"https?://[a-zA-Z0-9.-]+\.(lhr\.[a-z]+|serveo\.net|pinggy\.link|trycloudflare\.com)[^\s]*", RegexOptions.Compiled | RegexOptions.IgnoreCase);

        private void ProcesarLinea(string? linea)
        {
            if (string.IsNullOrWhiteSpace(linea)) return;

            var m = RegexUrl.Match(linea);
            if (m.Success)
            {
                UrlPublica = m.Value.TrimEnd('/');
                UrlObtenida?.Invoke(UrlPublica);
            }
        }

        public void Detener()
        {
            _cts?.Cancel();
            try
            {
                if (_tunnelProcess != null && !_tunnelProcess.HasExited)
                {
                    _tunnelProcess.Kill(entireProcessTree: true);
                }
            }
            catch { }
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            Detener();
            _tunnelProcess?.Dispose();
            _tunnelProcess = null;
        }
    }
}
