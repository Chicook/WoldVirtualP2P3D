using System.Collections.Concurrent;
using System.Text.Json;
using WoldVirtual.Servidor.Modulos.Blockchain;

namespace WoldVirtual.Servidor.Modulos.Dao;

/// <summary>Presencia temporal de la sede DAO y alta de participantes de una sesión.</summary>
public sealed class DaoModule
{
    private readonly BlockchainModule _blockchain;
    private readonly ConcurrentDictionary<string, MemberRecord> _members = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, PendingConnection> _pending = new(StringComparer.Ordinal);
    private readonly Timer _cleanup;

    public DaoModule(BlockchainModule blockchain)
    {
        _blockchain = blockchain;
        _cleanup = new Timer(_ => Prune(), null, Timeout.Infinite, Timeout.Infinite);
    }

    public int TotalMiembrosEnLinea => OnlineMembers().Count;

    public Task IniciarAsync(CancellationToken cancellationToken)
    {
        _members["lucia"] = new MemberRecord("lucia", "LucIA", "anfitriona", 0, DateTimeOffset.UtcNow, true);
        _cleanup.Change(TimeSpan.FromSeconds(5), TimeSpan.FromSeconds(5));
        Console.WriteLine("[dao] Sede activa; LucIA fija en la posición 0,0,0.");
        return Task.CompletedTask;
    }

    public void Detener() => _cleanup.Dispose();

    public string Conectar(string nick)
    {
        var token = Convert.ToHexString(Guid.NewGuid().ToByteArray()).ToLowerInvariant();
        _pending[token] = new PendingConnection(nick, DateTimeOffset.UtcNow);
        return token;
    }

    public async Task<MemberRecord> RegistrarAsync(string token, string nick, string avatar, CancellationToken ct)
    {
        if (!_pending.TryGetValue(token, out var pending) || DateTimeOffset.UtcNow - pending.CreatedAt > TimeSpan.FromMinutes(5))
            throw new InvalidOperationException("La conexión preliminar caducó; vuelve a pulsar Conectar.");
        _pending.TryRemove(token, out _);
        var id = Convert.ToHexString(Guid.NewGuid().ToByteArray()).ToLowerInvariant();
        await _blockchain.MinarAsync(JsonSerializer.Serialize(new { tipo = "dao_member", id, nick, avatar }), ct);
        var member = new MemberRecord(id, nick, avatar, PositionFor(id), DateTimeOffset.UtcNow, false);
        _members[id] = member;
        return member;
    }

    public bool Heartbeat(string id)
    {
        if (!_members.TryGetValue(id, out var member) || member.IsHost) return false;
        _members[id] = member with { LastSeen = DateTimeOffset.UtcNow };
        return true;
    }

    public IReadOnlyList<MemberRecord> OnlineMembers()
    {
        Prune();
        return _members.Values.OrderBy(m => m.Position).ThenBy(m => m.Nick, StringComparer.OrdinalIgnoreCase).ToArray();
    }

    public bool Desconectar(string id)
    {
        return _members.TryGetValue(id, out var member) && !member.IsHost && _members.TryRemove(id, out _);
    }

    private void Prune()
    {
        var cutoff = DateTimeOffset.UtcNow - TimeSpan.FromSeconds(20);
        foreach (var item in _members)
            if (!item.Value.IsHost && item.Value.LastSeen < cutoff) _members.TryRemove(item.Key, out _);
        var pendingCutoff = DateTimeOffset.UtcNow - TimeSpan.FromMinutes(5);
        foreach (var item in _pending)
            if (item.Value.CreatedAt < pendingCutoff) _pending.TryRemove(item.Key, out _);
    }

    private static int PositionFor(string id) => Math.Abs(id.GetHashCode(StringComparison.Ordinal) % 100_000) + 1;
}

public sealed record PendingConnection(string Nick, DateTimeOffset CreatedAt);
public sealed record MemberRecord(string Id, string Nick, string Avatar, int Position, DateTimeOffset LastSeen, bool IsHost);
public sealed record ConnectRequest(string? Nick);
public sealed record RegisterRequest(string? Token, string? Nick, string? Avatar);
public sealed record HeartbeatRequest(string? Id);

public static class DaoEndpoints
{
    public static IEndpointRouteBuilder MapDaoEndpoints(this IEndpointRouteBuilder endpoints)
    {
        endpoints.MapPost("/api/session/connect", (ConnectRequest request, DaoModule dao) =>
        {
            var nick = (request.Nick ?? "").Trim();
            if (nick.Length is < 2 or > 24 || nick.Any(char.IsControl))
                return Results.BadRequest(new { error = "El nick debe tener entre 2 y 24 caracteres." });
            return Results.Ok(new { conectado = true, token = dao.Conectar(nick), anfitrion = "LucIA", siguiente = "elegir_avatar" });
        });

        endpoints.MapPost("/api/dao/register", async (RegisterRequest request, DaoModule dao, CancellationToken ct) =>
        {
            var nick = (request.Nick ?? "").Trim();
            var avatar = (request.Avatar ?? "").Trim();
            var token = (request.Token ?? "").Trim();
            if (string.IsNullOrWhiteSpace(token) || nick.Length is < 2 or > 24 || avatar.Length is < 1 or > 48)
                return Results.BadRequest(new { error = "Falta conexión, nick o avatar." });
            try
            {
                var member = await dao.RegistrarAsync(token, nick, avatar, ct);
                return Results.Ok(new { registrado = true, miembro = member });
            }
            catch (InvalidOperationException ex) { return Results.Conflict(new { error = ex.Message }); }
        });

        endpoints.MapGet("/api/dao/members", (DaoModule dao) => Results.Ok(dao.OnlineMembers()));
        endpoints.MapPost("/api/dao/heartbeat", (HeartbeatRequest request, DaoModule dao) =>
            dao.Heartbeat(request.Id ?? "") ? Results.Ok(new { activo = true }) : Results.NotFound(new { activo = false }));
        endpoints.MapDelete("/api/dao/members/{id}", (string id, DaoModule dao) =>
            dao.Desconectar(id) ? Results.NoContent() : Results.NotFound());
        return endpoints;
    }
}
