using System;
using System.Diagnostics;
using System.IO;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace VisorSingularity
{
    public sealed class IPFSTunnelConnector : IDisposable
    {
        private Process? _process;
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
            LogStatus("Iniciando túnel Cloudflare (cloudflared)...");

            try
            {
                string? cfPath = ResolveCloudflared();
                if (cfPath == null)
                {
                    LogStatus("ERROR: cloudflared no encontrado. Instálalo con: winget install cloudflare.cloudflared o descárgalo de https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/");
                    return;
                }

                var psi = new ProcessStartInfo
                {
                    FileName = cfPath,
                    Arguments = $"tunnel --url http://127.0.0.1:{_localPort}",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                };

                _process = new Process { StartInfo = psi };
                _cts = new CancellationTokenSource();

                _process.Start();

                _process.ErrorDataReceived += OnOutput;
                _process.BeginErrorReadLine();
                _process.OutputDataReceived += OnOutput;
                _process.BeginOutputReadLine();

                IsConnected = true;
                OnConnectionChanged?.Invoke(true);
                LogStatus("Proxy cloudflared iniciado. Esperando URL pública...");
            }
            catch (Exception ex)
            {
                IsConnected = false;
                OnConnectionChanged?.Invoke(false);
                LogStatus($"Error al iniciar cloudflared: {ex.Message}");
                Cleanup();
            }
        }

        private static string? ResolveCloudflared()
        {
            try
            {
                var proc = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = "where",
                        Arguments = "cloudflared",
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        CreateNoWindow = true
                    }
                };
                proc.Start();
                string? line = proc.StandardOutput.ReadLine();
                proc.WaitForExit(3000);
                if (!string.IsNullOrEmpty(line) && File.Exists(line))
                    return line;
            }
            catch { }

            string[] candidates =
            {
                Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    @"Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe"),
                @"C:\Program Files\Cloudflare\cloudflared.exe",
                @"C:\Program Files (x86)\Cloudflare\cloudflared.exe"
            };

            foreach (var c in candidates)
            {
                if (File.Exists(c))
                    return c;
            }

            try
            {
                var proc = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = "cloudflared",
                        Arguments = "--version",
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        CreateNoWindow = true
                    }
                };
                proc.Start();
                proc.WaitForExit(3000);
                if (proc.ExitCode == 0)
                    return "cloudflared";
            }
            catch { }

            return null;
        }

        private void OnOutput(object sender, DataReceivedEventArgs e)
        {
            if (string.IsNullOrEmpty(e.Data)) return;

            var match = Regex.Match(e.Data, @"(https?://[a-zA-Z0-9_-]+\.trycloudflare\.com)");
            if (match.Success && PublicUrl == null)
            {
                PublicUrl = match.Groups[1].Value;
                IsConnected = true;
                OnUrlReceived?.Invoke(PublicUrl);
                LogStatus($"Nodo público: {PublicUrl}");
            }

            Debug.WriteLine($"[cloudflared] {e.Data}");
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
            LogStatus("Túnel Cloudflare cerrado.");
        }

        private void Cleanup()
        {
            try
            {
                _cts?.Cancel();

                if (_process != null && !_process.HasExited)
                {
                    _process.Kill(entireProcessTree: true);
                    _process.WaitForExit(3000);
                    _process.Dispose();
                    _process = null;
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
