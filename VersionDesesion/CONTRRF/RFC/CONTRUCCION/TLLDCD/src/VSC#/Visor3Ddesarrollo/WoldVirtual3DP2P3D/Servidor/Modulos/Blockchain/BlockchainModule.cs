using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace WoldVirtual.Servidor.Modulos.Blockchain;

/// <summary>Cadena local demostrativa. No pretende sustituir la cadena oficial.</summary>
public sealed class BlockchainModule
{
    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly List<BlockRecord> _blocks = [];
    private readonly string _filePath = ResolvePath();
    private const int Difficulty = 3;

    public object Estado => new
    {
        activa = _blocks.Count > 0,
        bloques = _blocks.Count,
        ultimo_hash = _blocks.Count == 0 ? "" : _blocks[^1].Hash,
        dificultad = Difficulty,
        almacenamiento = _filePath
    };

    public async Task IniciarAsync(CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_filePath)!);
        if (File.Exists(_filePath))
        {
            try
            {
                var existing = JsonSerializer.Deserialize<List<BlockRecord>>(await File.ReadAllTextAsync(_filePath, cancellationToken));
                if (existing is { Count: > 0 } && Validate(existing)) _blocks.AddRange(existing);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[blockchain] No se pudo leer la cadena local: {ex.Message}");
            }
        }

        if (_blocks.Count == 0)
        {
            _blocks.Add(Mine(0, DateTimeOffset.UtcNow, "GENESIS WoldVirtual P2P", "0"));
            await PersistAsync(cancellationToken);
        }

        await MinarAsync(JsonSerializer.Serialize(new { tipo = "servidor_inicio", version = "2.9.3-preview" }), cancellationToken);

        Console.WriteLine($"[blockchain] Lista; {_blocks.Count} bloque(s), {Difficulty} ceros de prueba.");
    }

    public async Task<BlockRecord> MinarAsync(string data, CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken);
        try
        {
            if (_blocks.Count == 0)
                _blocks.Add(Mine(0, DateTimeOffset.UtcNow, "GENESIS WoldVirtual P2P", "0"));
            var previous = _blocks[^1];
            var block = Mine(previous.Index + 1, DateTimeOffset.UtcNow, data, previous.Hash, cancellationToken);
            _blocks.Add(block);
            await PersistAsync(cancellationToken);
            return block;
        }
        finally { _gate.Release(); }
    }

    public async Task<IReadOnlyList<BlockRecord>> ObtenerAsync(CancellationToken cancellationToken)
    {
        await _gate.WaitAsync(cancellationToken);
        try { return _blocks.ToArray(); }
        finally { _gate.Release(); }
    }

    private BlockRecord Mine(int index, DateTimeOffset timestamp, string data, string previousHash,
        CancellationToken cancellationToken = default)
    {
        long nonce = 0;
        var prefix = new string('0', Difficulty);
        while (true)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var hash = Hash(index, timestamp, data, previousHash, nonce);
            if (hash.StartsWith(prefix, StringComparison.Ordinal))
                return new BlockRecord(index, timestamp, data, previousHash, nonce, hash);
            nonce++;
        }
    }

    private static string Hash(int index, DateTimeOffset timestamp, string data, string previousHash, long nonce)
    {
        var input = $"{index}|{timestamp:O}|{data}|{previousHash}|{nonce}";
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(input))).ToLowerInvariant();
    }

    private bool Validate(IReadOnlyList<BlockRecord> chain)
    {
        var prefix = new string('0', Difficulty);
        for (var i = 0; i < chain.Count; i++)
        {
            var block = chain[i];
            if (block.Index != i || !block.Hash.StartsWith(prefix, StringComparison.Ordinal) ||
                block.Hash != Hash(block.Index, block.Timestamp, block.Data, block.PreviousHash, block.Nonce)) return false;
            if (i > 0 && block.PreviousHash != chain[i - 1].Hash) return false;
        }
        return chain[0].PreviousHash == "0";
    }

    private async Task PersistAsync(CancellationToken cancellationToken)
    {
        var dir = Path.GetDirectoryName(_filePath);
        if (!string.IsNullOrEmpty(dir))
            Directory.CreateDirectory(dir);

        var json = JsonSerializer.Serialize(_blocks, JsonOptions);
        var temp = _filePath + ".tmp";
        for (var intento = 0; intento < 3; intento++)
        {
            try
            {
                await File.WriteAllTextAsync(temp, json, cancellationToken);
                File.Move(temp, _filePath, overwrite: true);
                return;
            }
            catch (Exception) when (intento < 2)
            {
                await Task.Delay(50 * (intento + 1), cancellationToken);
            }
            catch
            {
                try
                {
                    await File.WriteAllTextAsync(_filePath, json, cancellationToken);
                    if (File.Exists(temp)) File.Delete(temp);
                    return;
                }
                catch (Exception writeEx)
                {
                    Console.Error.WriteLine($"[blockchain] Advertencia al persistir bloques: {writeEx.Message}");
                }
            }
        }
    }

    private static string ResolvePath()
    {
        var configured = Environment.GetEnvironmentVariable("WVP_DATA_DIR");
        var root = !string.IsNullOrWhiteSpace(configured)
            ? configured
            : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "WoldVirtualP2P3D", "2.9.3");
        return Path.Combine(root, "blockchain", "blocks.json");
    }

    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };
}

public sealed record BlockRecord(int Index, DateTimeOffset Timestamp, string Data, string PreviousHash, long Nonce, string Hash);

public static class BlockchainEndpoints
{
    public static IEndpointRouteBuilder MapBlockchainEndpoints(this IEndpointRouteBuilder endpoints)
    {
        endpoints.MapGet("/api/blockchain/status", (BlockchainModule chain) => Results.Ok(chain.Estado));
        endpoints.MapGet("/api/blockchain/blocks", async (BlockchainModule chain, CancellationToken ct) =>
            Results.Ok(await chain.ObtenerAsync(ct)));
        endpoints.MapPost("/api/blockchain/mine", async (MineRequest request, BlockchainModule chain, CancellationToken ct) =>
        {
            var text = (request.Data ?? "").Trim();
            if (text.Length is < 1 or > 512) return Results.BadRequest(new { error = "data debe tener entre 1 y 512 caracteres" });
            return Results.Ok(await chain.MinarAsync(text, ct));
        });
        return endpoints;
    }
}

public sealed record MineRequest(string? Data);
