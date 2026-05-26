using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using WoldVirtual.EstadoGlobal.Models;
using WoldVirtual.EstadoGlobal.Helpers;
using Timer = System.Timers.Timer;

namespace WoldVirtual.EstadoGlobal;

/// <summary>
/// Gestiona la sincronización P2P del estado de las islas mediante archivos JSON.
/// </summary>
public sealed class IslandStateManager : IDisposable
{
    private readonly string _peerDir;
    private readonly string _hostPeerPath;
    private readonly ReaderWriterLockSlim _lock = new();
    private readonly FileSystemWatcher _watcher;
    private readonly Timer _debounceTimer;
    private readonly HashSet<string> _pendingChanges = [];
    private readonly Dictionary<string, IslandStateData> _peerCache = [];

    private IslandStateData _hostState = new();
    private IslandStateData _aggregatedState = new();
    private List<IslandInfo> _cachedIslands = [];

    private const long MaxDiskQuota = 64 * 1024 * 1024; // 64MB para peers

    public bool IsReadOnly { get; set; }
    public event Action? OnStateChanged;

    private static readonly JsonSerializerOptions _jsonOptions = new()
    {
        TypeInfoResolver = GlobalJsonContext.Default,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    public IslandStateManager(string? peerDir = null, string? peerId = null)
    {
        _peerDir = peerDir ?? GlobalConfig.PeersDir;
        var fileName = string.IsNullOrEmpty(peerId) ? "peer_host.json" : $"peer_{peerId}.json";
        _hostPeerPath = Path.Combine(_peerDir, fileName);

        if (!Directory.Exists(_peerDir)) Directory.CreateDirectory(_peerDir);

        _watcher = new FileSystemWatcher(_peerDir, "peer_*.json")
        {
            NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.FileName
        };
        _watcher.Changed += (s, e) => QueueChange(e.FullPath);
        _watcher.Created += (s, e) => QueueChange(e.FullPath);
        _watcher.Deleted += (s, e) => RemovePeer(e.Name);
        _watcher.EnableRaisingEvents = true;

        _debounceTimer = new Timer(150) { AutoReset = false };
        _debounceTimer.Elapsed += (s, e) => ProcessChanges();

        InitialLoad();
    }

    private void InitialLoad()
    {
        _lock.EnterWriteLock();
        try
        {
            _peerCache.Clear();
            _hostState = LoadFile(_hostPeerPath) ?? new IslandStateData();
            _peerCache[Path.GetFileName(_hostPeerPath)] = _hostState;

            foreach (var file in Directory.GetFiles(_peerDir, "peer_*.json"))
            {
                var name = Path.GetFileName(file);
                if (name.Equals(Path.GetFileName(_hostPeerPath), StringComparison.OrdinalIgnoreCase)) continue;
                var peer = LoadFile(file);
                if (peer != null) _peerCache[name] = peer;
            }
            RebuildAggregatedState();
        }
        finally { _lock.ExitWriteLock(); }
    }

    private static IslandStateData? LoadFile(string path)
    {
        if (!File.Exists(path)) return null;
        try
        {
            using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            using var doc = JsonDocument.Parse(stream);
            if (!PeerValidator.IsValid(doc, out var error))
            {
                GlobalLogger.Warning($"Peer inválido {Path.GetFileName(path)}: {error}");
                return null;
            }
            stream.Position = 0;
            return JsonSerializer.Deserialize<IslandStateData>(stream, _jsonOptions);
        }
        catch (Exception ex)
        {
            GlobalLogger.Error($"Error cargando {Path.GetFileName(path)}", ex);
            return null;
        }
    }

    private void QueueChange(string path)
    {
        lock (_pendingChanges)
        {
            _pendingChanges.Add(path);
            _debounceTimer.Stop();
            _debounceTimer.Start();
        }
    }

    private void ProcessChanges()
    {
        string[] paths;
        lock (_pendingChanges)
        {
            paths = [.. _pendingChanges];
            _pendingChanges.Clear();
        }

        var changed = false;
        _lock.EnterWriteLock();
        try
        {
            foreach (var path in paths)
            {
                var peer = LoadFile(path);
                if (peer != null)
                {
                    var name = Path.GetFileName(path);
                    _peerCache[name] = peer;
                    if (path.Equals(_hostPeerPath, StringComparison.OrdinalIgnoreCase)) _hostState = peer;
                    changed = true;
                }
            }
            if (changed) RebuildAggregatedState();
        }
        finally { _lock.ExitWriteLock(); }
    }

    private void RemovePeer(string? name)
    {
        if (string.IsNullOrEmpty(name)) return;
        _lock.EnterWriteLock();
        try
        {
            if (_peerCache.Remove(name)) RebuildAggregatedState();
        }
        finally { _lock.ExitWriteLock(); }
    }

    private void RebuildAggregatedState()
    {
        var aggregated = new IslandStateData();
        foreach (var peer in _peerCache.Values)
        {
            foreach (var user in peer.Users) aggregated.Users[user.Key] = user.Value;
            foreach (var island in peer.Islands)
            {
                if (!aggregated.Islands.TryGetValue(island.Key, out var existing) ||
                    (island.Value.LastModifiedAt ?? DateTime.MinValue) > (existing.LastModifiedAt ?? DateTime.MinValue))
                {
                    aggregated.Islands[island.Key] = island.Value;
                }
            }
        }
        _aggregatedState = aggregated;
        _cachedIslands = [.. aggregated.Islands.Values];
        OnStateChanged?.Invoke();
    }

    public IslandStateData GetCurrentState()
    {
        _lock.EnterReadLock();
        try { return _aggregatedState; }
        finally { _lock.ExitReadLock(); }
    }

    public IReadOnlyList<IslandInfo> GetIslands()
    {
        _lock.EnterReadLock();
        try { return _cachedIslands; }
        finally { _lock.ExitReadLock(); }
    }

    public void UpsertAvatar(AvatarInfo avatar)
    {
        _lock.EnterWriteLock();
        try { _hostState.ActiveAvatar = avatar; }
        finally { _lock.ExitWriteLock(); }
        SaveState();
    }

    public void UpsertIsland(IslandInfo island)
    {
        _lock.EnterWriteLock();
        try { _hostState.Islands[island.Id] = island with { LastModifiedAt = DateTime.UtcNow }; }
        finally { _lock.ExitWriteLock(); }
        SaveState();
    }

    public void SaveState()
    {
        if (IsReadOnly) return;

        byte[] data;
        _lock.EnterReadLock();
        try
        {
            _hostState.LastUpdated = DateTime.UtcNow;
            data = JsonSerializer.SerializeToUtf8Bytes(_hostState, _jsonOptions);
        }
        finally { _lock.ExitReadLock(); }

        Task.Run(() =>
        {
            try
            {
                var temp = _hostPeerPath + ".tmp";
                File.WriteAllBytes(temp, data);
                File.Move(temp, _hostPeerPath, true);
                EnforceQuota();
            }
            catch (Exception ex) { GlobalLogger.Error("Error al guardar estado", ex); }
        });
    }

    private void EnforceQuota()
    {
        try
        {
            var files = new DirectoryInfo(_peerDir).GetFiles("peer_*.json")
                .OrderBy(f => f.LastWriteTime).ToList();
            var total = files.Sum(f => f.Length);
            while (total > MaxDiskQuota && files.Count > 1)
            {
                var f = files[0];
                if (f.FullName.Equals(_hostPeerPath, StringComparison.OrdinalIgnoreCase))
                {
                    if (files.Count == 1) break;
                    f = files[1];
                }
                total -= f.Length;
                f.Delete();
                files.Remove(f);
            }
        }
        catch { }
    }

    public void Dispose()
    {
        _watcher.Dispose();
        _debounceTimer.Dispose();
        _lock.Dispose();
    }
}
