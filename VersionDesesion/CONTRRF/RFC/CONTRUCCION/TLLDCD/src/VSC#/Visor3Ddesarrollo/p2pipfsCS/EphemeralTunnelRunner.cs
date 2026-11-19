using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Services.P2PIPFS
{
    internal sealed record EphemeralTunnelResult(string Url, Process Process);

    internal static class EphemeralTunnelRunner
    {
        public static async Task<EphemeralTunnelResult?> StartAsync(
            string exe,
            string args,
            string urlPattern,
            int timeoutMs,
            CancellationToken token,
            Action<string>? onDiagnostic = null)
        {
            Process? process = null;
            string? found = null;
            var diagnostics = new ConcurrentQueue<string>();

            try
            {
                process = Process.Start(new ProcessStartInfo
                {
                    FileName = exe,
                    Arguments = args,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                });
                if (process == null) return null;

                using var scanCts = CancellationTokenSource.CreateLinkedTokenSource(token);
                scanCts.CancelAfter(timeoutMs);

                async Task Scan(StreamReader reader, string label)
                {
                    try
                    {
                        while (!scanCts.IsCancellationRequested && !process.HasExited)
                        {
                            string? line = await reader.ReadLineAsync();
                            if (line == null) break;

                            Debug.WriteLine($"[{label}] {line}");
                            diagnostics.Enqueue(line.Trim());
                            while (diagnostics.Count > 12) diagnostics.TryDequeue(out _);
                            try { onDiagnostic?.Invoke(line.Trim()); } catch { }
                            var match = Regex.Match(line, urlPattern);
                            if (match.Success)
                            {
                                string matched = match.Value;
                                if (!matched.StartsWith("http://") && !matched.StartsWith("https://"))
                                {
                                    matched = "http://" + matched;
                                }

                                found = matched;
                                scanCts.Cancel();
                                return;
                            }
                        }
                    }
                    catch
                    {
                    }
                }

                Task scanOut = Scan(process.StandardOutput, exe);
                Task scanErr = Scan(process.StandardError, exe);
                await Task.WhenAny(
                    scanOut,
                    scanErr,
                    Task.Delay(timeoutMs + 1000, scanCts.Token).ContinueWith(_ => { })
                );

                if (!string.IsNullOrEmpty(found) && !process.HasExited)
                {
                    // Continuar drenando stdout y stderr para que los búferes de tubería del SO
                    // no se llenen y bloqueen el proceso del túnel mientras esté activo
                    _ = Task.Run(async () =>
                    {
                        try
                        {
                            while (!process.HasExited)
                            {
                                var l = await process.StandardOutput.ReadLineAsync().ConfigureAwait(false);
                                if (l == null) break;
                            }
                        }
                        catch { }
                    });
                    _ = Task.Run(async () =>
                    {
                        try
                        {
                            while (!process.HasExited)
                            {
                                var l = await process.StandardError.ReadLineAsync().ConfigureAwait(false);
                                if (l == null) break;
                            }
                        }
                        catch { }
                    });

                    return new EphemeralTunnelResult(found, process);
                }

                bool exited = process.HasExited;
                int exitCode = exited ? process.ExitCode : -1;
                if (!exited) StopProcess(process);
                try { await Task.WhenAll(scanOut, scanErr); } catch { }

                string detail = string.Join(" | ", diagnostics.ToArray().TakeLast(5));
                if (string.IsNullOrWhiteSpace(detail))
                    detail = exited
                        ? $"El proceso terminó sin publicar una URL (código {exitCode})."
                        : $"No publicó una URL en {timeoutMs / 1000} s.";
                try { onDiagnostic?.Invoke(detail); } catch { }
                if (exited) StopProcess(process);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[EphemeralTunnelRunner] {exe}: {ex.Message}");
                try { onDiagnostic?.Invoke($"{Path.GetFileName(exe)}: {ex.Message}"); } catch { }
                StopProcess(process);
            }

            return null;
        }

        private static void StopProcess(Process? process)
        {
            try
            {
                process?.Kill(entireProcessTree: true);
                process?.Dispose();
            }
            catch
            {
            }
        }
    }
}

