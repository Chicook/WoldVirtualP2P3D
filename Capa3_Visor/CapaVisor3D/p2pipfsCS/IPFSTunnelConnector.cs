using System;
using System.Diagnostics;
using System.IO;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace VisorSingularity
{
    public class IPFSTunnelConnector : IDisposable
    {
        private Process? _sshProcess;
        private CancellationTokenSource? _cts;
        private bool _disposed;
        private readonly int _localPort;

        public bool IsConnected { get; private set; }
        public string? PublicUrl { get; private set; }

        public event Action<string>? OnStatusChanged;
        public event Action<bool>? OnConnectionChanged;
        public event Action<string>? OnUrlReceived;

        public IPFSTunnelConnector(int localPort)
        {
            _localPort = localPort;
        }

        public async Task ConnectAsync()
        {
            await Task.Run(() => ConnectInternal());
        }

        private void ConnectInternal()
        {
            DisconnectInternal();
            LogStatus("Estableciendo túnel SSH a localhost.run...");

            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = "ssh",
                    Arguments = $"-o StrictHostKeyChecking=no -R 80:127.0.0.1:{_localPort} localhost.run",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                };

                _sshProcess = new Process { StartInfo = psi };
                _cts = new CancellationTokenSource();

                _sshProcess.Start();

                // Capturar la URL desde la salida del proceso SSH
                _sshProcess.ErrorDataReceived += OnSshOutput;
                _sshProcess.BeginErrorReadLine();
                _sshProcess.OutputDataReceived += OnSshOutput;
                _sshProcess.BeginOutputReadLine();

                IsConnected = true;
                OnConnectionChanged?.Invoke(true);
                LogStatus("Túnel SSH establecido. Esperando URL pública...");
            }
            catch (Exception ex)
            {
                IsConnected = false;
                OnConnectionChanged?.Invoke(false);
                LogStatus($"Error al crear túnel SSH: {ex.Message}");
                Cleanup();
            }
        }

        private void OnSshOutput(object sender, DataReceivedEventArgs e)
        {
            if (string.IsNullOrEmpty(e.Data)) return;

            // localhost.run devuelve la URL en el formato: https://xxxx-xxxx-xxxx.loca.lt
            var match = Regex.Match(e.Data, @"(https?://[a-zA-Z0-9_-]+\.loca\.lt)");
            if (match.Success && PublicUrl == null)
            {
                PublicUrl = match.Groups[1].Value;
                IsConnected = true;
                OnUrlReceived?.Invoke(PublicUrl);
                LogStatus($"¡Nodo público en: {PublicUrl}");
            }

            Debug.WriteLine($"[localhost.run] {e.Data}");
        }

        public void Disconnect()
        {
            DisconnectInternal();
        }

        private void DisconnectInternal()
        {
            Cleanup();
            IsConnected = false;
            PublicUrl = null;
            OnConnectionChanged?.Invoke(false);
            LogStatus("Túnel SSH cerrado.");
        }

        private void Cleanup()
        {
            try
            {
                _cts?.Cancel();

                if (_sshProcess != null && !_sshProcess.HasExited)
                {
                    _sshProcess.Kill(entireProcessTree: true);
                    _sshProcess.WaitForExit(3000);
                    _sshProcess.Dispose();
                    _sshProcess = null;
                }
            }
            catch { }
        }

        private void LogStatus(string msg)
        {
            OnStatusChanged?.Invoke(msg);
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            DisconnectInternal();
            _cts?.Dispose();
        }
    }
}
