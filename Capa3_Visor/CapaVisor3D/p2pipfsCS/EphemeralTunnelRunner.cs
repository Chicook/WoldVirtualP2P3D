using System;
using System.Diagnostics;
using System.IO;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace VisorSingularity
{
    internal sealed record EphemeralTunnelResult(string Url, Process Process);

    internal static class EphemeralTunnelRunner
    {
        public static async Task<EphemeralTunnelResult?> StartAsync(
            string exe,
            string args,
            string urlPattern,
            int timeoutMs,
            CancellationToken token)
        {
            Process? process = null;
            string? found = null;

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

                var timeoutTask = Task.Delay(timeoutMs + 1000, scanCts.Token);
                await Task.WhenAny(
                    Scan(process.StandardOutput, exe),
                    Scan(process.StandardError, exe),
                    timeoutTask
                );

                if (!string.IsNullOrEmpty(found) && !process.HasExited)
                {
                    return new EphemeralTunnelResult(found, process);
                }

                StopProcess(process);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[EphemeralTunnelRunner] {exe}: {ex.Message}");
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
