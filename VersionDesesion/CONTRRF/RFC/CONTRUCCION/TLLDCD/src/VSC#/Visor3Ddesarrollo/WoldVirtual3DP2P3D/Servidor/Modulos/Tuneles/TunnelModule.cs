using System.Diagnostics;
using System.Text.RegularExpressions;

namespace WoldVirtual.Servidor.Modulos.Tuneles;

/// <summary>Publica el servidor local con un túnel saliente efímero opcional.</summary>
public sealed class TunnelModule : IAsyncDisposable
{
    private readonly object _gate = new();
    private Process? _process;
    private CancellationTokenSource? _stop;
    private Task? _loop;
    private string? _publicUrl;
    private string _provider = "ninguno";
    private string? _error;

    public object Estado
    {
        get { lock (_gate) return new { activo = _publicUrl is not null && _process is { HasExited: false }, url = _publicUrl ?? "", proveedor = _provider, error = _error ?? "" }; }
    }

    public Task IniciarAsync(int localPort, CancellationToken applicationStopping)
    {
        if (Environment.GetEnvironmentVariable("WVP_DISABLE_TUNNEL") == "1")
        {
            _error = "Túnel desactivado para desarrollo local.";
            return Task.CompletedTask;
        }
        if (_loop is not null) return Task.CompletedTask;
        _stop = CancellationTokenSource.CreateLinkedTokenSource(applicationStopping);
        _loop = Task.Run(() => RunLoopAsync(localPort, _stop.Token));
        Console.WriteLine("[tunel] Módulo iniciado; buscando cloudflared o OpenSSH.");
        return Task.CompletedTask;
    }

    public async Task DetenerAsync()
    {
        if (_stop is null) return;
        try { _stop.Cancel(); } catch { }
        Process? process;
        lock (_gate) { process = _process; _process = null; _publicUrl = null; }
        try { if (process is { HasExited: false }) process.Kill(entireProcessTree: true); } catch { }
        if (_loop is not null) { try { await _loop.WaitAsync(TimeSpan.FromSeconds(3)); } catch { } }
        _stop.Dispose(); _stop = null; _loop = null;
    }

    public async ValueTask DisposeAsync() => await DetenerAsync();

    private async Task RunLoopAsync(int port, CancellationToken ct)
    {
        var delay = TimeSpan.FromSeconds(4);
        while (!ct.IsCancellationRequested)
        {
            var preferencia = Environment.GetEnvironmentVariable("WVP_TUNNEL_PROVIDER");
            var launch = string.Equals(preferencia, "ssh", StringComparison.OrdinalIgnoreCase)
                ? FindSsh()
                : FindCloudflared() ?? FindSsh();
            if (launch is null)
            {
                SetError("Instala cloudflared o activa OpenSSH para publicar el host.");
                await PauseAsync(TimeSpan.FromSeconds(10), ct);
                continue;
            }

            try
            {
                var urlSource = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
                var start = new ProcessStartInfo(launch.Value.File) { UseShellExecute = false, CreateNoWindow = true };
                foreach (var arg in launch.Value.Args(port)) start.ArgumentList.Add(arg);
                start.RedirectStandardOutput = true;
                start.RedirectStandardError = true;
                var process = new Process { StartInfo = start, EnableRaisingEvents = true };
                process.OutputDataReceived += (_, e) => Scan(e.Data, urlSource);
                process.ErrorDataReceived += (_, e) => Scan(e.Data, urlSource);
                if (!process.Start()) throw new InvalidOperationException("No se pudo iniciar el cliente de túnel.");
                process.BeginOutputReadLine(); process.BeginErrorReadLine();
                lock (_gate) { _process = process; _provider = launch.Value.Name; _error = null; _publicUrl = null; }

                var timeout = Task.Delay(TimeSpan.FromSeconds(35), ct);
                var completed = await Task.WhenAny(urlSource.Task, process.WaitForExitAsync(ct), timeout);
                if (completed == urlSource.Task)
                {
                    var url = await urlSource.Task;
                    lock (_gate) _publicUrl = url;
                    Console.WriteLine($"[tunel] Host público disponible: {url}");
                    await process.WaitForExitAsync(ct);
                }
                else if (!ct.IsCancellationRequested) SetError("El proveedor no publicó una URL; se reintentará.");
                try { if (!process.HasExited) process.Kill(entireProcessTree: true); } catch { }
                process.Dispose();
                lock (_gate) { if (ReferenceEquals(_process, process)) _process = null; _publicUrl = null; }
                await PauseAsync(delay, ct);
                delay = TimeSpan.FromSeconds(Math.Min(30, delay.TotalSeconds * 1.5));
            }
            catch (OperationCanceledException) { break; }
            catch (Exception ex)
            {
                SetError(ex.Message);
                await PauseAsync(delay, ct);
                delay = TimeSpan.FromSeconds(Math.Min(30, delay.TotalSeconds * 1.5));
            }
        }
    }

    private static void Scan(string? line, TaskCompletionSource<string> source)
    {
        if (string.IsNullOrWhiteSpace(line) || source.Task.IsCompleted) return;
        var url = Regex.Match(line, @"https://[a-z0-9-]+\.trycloudflare\.com", RegexOptions.IgnoreCase);
        if (!url.Success) url = Regex.Match(line, @"https?://[a-z0-9-]+\.lhr\.life", RegexOptions.IgnoreCase);
        if (url.Success) source.TrySetResult(url.Value.TrimEnd('/'));
    }

    private static (string Name, string File, Func<int, string[]> Args)? FindCloudflared()
    {
        var env = Environment.GetEnvironmentVariable("CLOUDFLARED_EXE");
        var candidates = new[] { env, Path.Combine(AppContext.BaseDirectory, "cloudflared.exe"), "cloudflared" };
        var found = candidates.FirstOrDefault(path => !string.IsNullOrWhiteSpace(path) && (File.Exists(path) || path == "cloudflared"));
        return found is null ? null : ("Cloudflare Quick Tunnel", found, port => ["tunnel", "--no-autoupdate", "--url", $"http://127.0.0.1:{port}"]);
    }

    private static (string Name, string File, Func<int, string[]> Args)? FindSsh()
    {
        var ssh = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "System32", "OpenSSH", "ssh.exe");
        if (!File.Exists(ssh)) ssh = "ssh";
        return ("OpenSSH localhost.run", ssh, port => ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=NUL", "-o", "ServerAliveInterval=30", "-o", "ConnectTimeout=15", "-o", "ExitOnForwardFailure=yes", "-R", $"80:localhost:{port}", "nokey@localhost.run"]);
    }

    private void SetError(string value) { lock (_gate) { _error = value; _publicUrl = null; } }
    private static async Task PauseAsync(TimeSpan delay, CancellationToken ct) { try { await Task.Delay(delay, ct); } catch (OperationCanceledException) { } }
}

public static class TunnelEndpoints
{
    public static IEndpointRouteBuilder MapTunnelEndpoints(this IEndpointRouteBuilder endpoints)
    {
        endpoints.MapGet("/api/tunnel/status", (TunnelModule tunnel) => Results.Ok(tunnel.Estado));
        return endpoints;
    }
}
