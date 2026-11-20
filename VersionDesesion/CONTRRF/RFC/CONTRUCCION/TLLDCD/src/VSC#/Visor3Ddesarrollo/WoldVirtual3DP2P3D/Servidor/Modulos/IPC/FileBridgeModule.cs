using System.Text.Json;
using System.Text.Json.Serialization;
using WoldVirtual.Servidor.Modulos.Blockchain;
using WoldVirtual.Servidor.Modulos.Dao;
using WoldVirtual.Servidor.Modulos.Tuneles;

namespace WoldVirtual.Servidor.Modulos.Ipc;

/// <summary>
/// Canal local por archivos para que Godot y el servidor se comuniquen sin
/// abrir un socket de loopback. La API HTTP sigue disponible para invitados.
/// </summary>
public sealed class FileBridgeModule(BlockchainModule blockchain, DaoModule dao, TunnelModule tunnel)
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        PropertyNameCaseInsensitive = true
    };
    private readonly string _root = Environment.GetEnvironmentVariable("WVP_IPC_DIR") is { Length: > 0 } configured
        ? Path.GetFullPath(configured)
        : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "WoldVirtualP2P3D", "2.9.3", "ipc");
    private CancellationTokenSource? _stop;
    private Task? _worker;

    public string Root => _root;

    public Task StartAsync(CancellationToken applicationStopping)
    {
        Directory.CreateDirectory(Path.Combine(_root, "requests"));
        Directory.CreateDirectory(Path.Combine(_root, "responses"));
        _stop = CancellationTokenSource.CreateLinkedTokenSource(applicationStopping);
        _worker = Task.Run(() => ProcessLoopAsync(_stop.Token));
        Console.WriteLine($"[ipc] Puente local por archivos activo: {_root}");
        return Task.CompletedTask;
    }

    public async Task StopAsync()
    {
        if (_stop is null) return;
        _stop.Cancel();
        if (_worker is not null) { try { await _worker.WaitAsync(TimeSpan.FromSeconds(2)); } catch { } }
        _stop.Dispose();
        _stop = null;
    }

    private async Task ProcessLoopAsync(CancellationToken ct)
    {
        var inbox = Path.Combine(_root, "requests");
        while (!ct.IsCancellationRequested)
        {
            var didWork = false;
            foreach (var file in Directory.EnumerateFiles(inbox, "*.req"))
            {
                if (ct.IsCancellationRequested) break;
                didWork = true;
                await ProcessFileAsync(file, ct);
            }
            if (!didWork)
            {
                try { await Task.Delay(35, ct); }
                catch (OperationCanceledException) when (ct.IsCancellationRequested) { break; }
            }
        }
    }

    private async Task ProcessFileAsync(string path, CancellationToken ct)
    {
        BridgeRequest? request = null;
        try
        {
            var json = await File.ReadAllTextAsync(path, ct);
            request = JsonSerializer.Deserialize<BridgeRequest>(json, JsonOptions);
            if (request is null || !IsSafeId(request.Id)) throw new InvalidDataException("Solicitud IPC inválida.");
            var (status, body) = await DispatchAsync(request, ct);
            var responsePath = Path.Combine(_root, "responses", request.Id + ".res");
            var tempPath = responsePath + ".tmp";
            var responseBytes = JsonSerializer.SerializeToUtf8Bytes(new BridgeResponse(request.Id, status, body), JsonOptions);
            await File.WriteAllBytesAsync(tempPath, responseBytes, ct);
            try
            {
                File.Move(tempPath, responsePath, overwrite: true);
            }
            catch
            {
                File.Copy(tempPath, responsePath, overwrite: true);
                try { File.Delete(tempPath); } catch { }
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            if (request is not null && !string.IsNullOrWhiteSpace(request.Id))
            {
                var responsePath = Path.Combine(_root, "responses", request.Id + ".res");
                await File.WriteAllTextAsync(responsePath, JsonSerializer.Serialize(new BridgeResponse(request.Id, 500, new { error = ex.Message }), JsonOptions), ct);
            }
            Console.Error.WriteLine($"[ipc] Solicitud fallida: {ex.Message}");
        }
        finally { try { File.Delete(path); } catch { } }
    }

    private async Task<(int Status, object Body)> DispatchAsync(BridgeRequest request, CancellationToken ct)
    {
        var path = request.Path.Split('?', 2)[0];
        var method = request.Method.ToUpperInvariant();
        var payload = request.Body.ValueKind == System.Text.Json.JsonValueKind.Object
            ? request.Body.Deserialize<JsonElement>(JsonOptions) : default;
        string? Get(string key) => payload.ValueKind == System.Text.Json.JsonValueKind.Object && payload.TryGetProperty(key, out var value) ? value.GetString() : null;

        if (method == "GET" && path == "/api/health")
            return (200, new { ok = true, version = "2.9.3-preview", blockchain = blockchain.Estado, dao = new { miembros = dao.TotalMiembrosEnLinea }, tunel = tunnel.Estado });
        if (method == "GET" && path == "/api/tunnel/status") return (200, tunnel.Estado);
        if (method == "POST" && path == "/api/session/connect")
        {
            var nick = (Get("nick") ?? "").Trim();
            if (nick.Length is < 2 or > 24 || nick.Any(char.IsControl)) return (400, new { error = "El nick debe tener entre 2 y 24 caracteres." });
            return (200, new { conectado = true, token = dao.Conectar(nick), anfitrion = "LucIA", siguiente = "elegir_avatar" });
        }
        if (method == "POST" && path == "/api/dao/register")
        {
            var nick = (Get("nick") ?? "").Trim();
            var avatar = (Get("avatar") ?? "").Trim();
            var token = (Get("token") ?? "").Trim();
            if (string.IsNullOrWhiteSpace(token) || nick.Length is < 2 or > 24 || avatar.Length is < 1 or > 48)
                return (400, new { error = "Falta conexión, nick o avatar." });
            try { return (200, new { registrado = true, miembro = await dao.RegistrarAsync(token, nick, avatar, ct) }); }
            catch (InvalidOperationException ex) { return (409, new { error = ex.Message }); }
        }
        if (method == "GET" && path == "/api/dao/members") return (200, dao.OnlineMembers());
        if (method == "POST" && path == "/api/dao/heartbeat")
            return dao.Heartbeat(Get("id") ?? "") ? (200, new { activo = true }) : (404, new { activo = false });
        const string memberPrefix = "/api/dao/members/";
        if (method == "DELETE" && path.StartsWith(memberPrefix, StringComparison.Ordinal))
        {
            var id = Uri.UnescapeDataString(path[memberPrefix.Length..]);
            return dao.Desconectar(id) ? (200, new { eliminado = true }) : (404, new { eliminado = false });
        }
        return (404, new { error = "Ruta local no disponible en el puente." });
    }

    private sealed record BridgeRequest(string Id, string Method, string Path, JsonElement Body);
    private sealed record BridgeResponse(string Id, int Status, object Body);

    private static bool IsSafeId(string value) => value.Length is > 0 and <= 64 &&
        value.All(character => char.IsAsciiLetterOrDigit(character) || character is '-' or '_');
}
