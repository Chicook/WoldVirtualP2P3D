using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using WoldVirtual.EstadoGlobal.Models;
using WoldVirtual.EstadoGlobal.Helpers;

namespace WoldVirtual.EstadoGlobal;

/// <summary>
/// Gestiona el ciclo de vida de una sesión de usuario y su persistencia.
/// </summary>
public sealed class SessionManager : IDisposable
{
    private readonly string _sessionsDir;
    private readonly Lock _lock = new();
    private IslandStateManager? _islandManager;
    private SessionState? _current;
    private IslandVisit? _activeVisit;

    public bool IsReadOnly { get; set; }

    public SessionManager(string? sessionsDir = null)
    {
        _sessionsDir = sessionsDir ?? GlobalConfig.EstadoGlobalDir;
        if (!Directory.Exists(_sessionsDir)) Directory.CreateDirectory(_sessionsDir);
        _islandManager = new IslandStateManager(Path.Combine(_sessionsDir, "peers"));
    }

    public SessionState StartSession()
    {
        lock (_lock)
        {
            _current = new SessionState();
            _activeVisit = null;

            _islandManager?.Dispose();
            _islandManager = new IslandStateManager(Path.Combine(_sessionsDir, "peers"), _current.SessionId)
            {
                IsReadOnly = IsReadOnly
            };

            GlobalLogger.Info($"Sesión iniciada: {_current.SessionId}");
            return _current;
        }
    }

    public void UpdateUser(Dictionary<string, object>? info)
    {
        lock (_lock)
        {
            if (_current == null || _islandManager == null) return;
            _current.UserInfo = info ?? [];
            var name = info?.GetValueOrDefault("userName")?.ToString() ?? "Guest";
            _islandManager.UpsertAvatar(new AvatarInfo(_current.SessionId, name));
        }
    }

    public void LogIslandVisit(string id, string name)
    {
        var now = DateTime.UtcNow;
        lock (_lock)
        {
            if (_current == null) return;
            if (_activeVisit != null) _activeVisit = _activeVisit with { DurationSeconds = (int)(now - _activeVisit.VisitTime).TotalSeconds };

            _activeVisit = new IslandVisit(id, name, now);
            _current.IslandsVisited.Add(_activeVisit);
        }
    }

    public void CloseSession()
    {
        lock (_lock)
        {
            if (_current == null || _islandManager == null) return;

            var now = DateTime.UtcNow;
            _current.EndTime = now;
            _current.IsActive = false;
            _current.DurationSeconds = (int)(now - _current.StartTime).TotalSeconds;

            if (_activeVisit != null) _activeVisit = _activeVisit with { DurationSeconds = (int)(now - _activeVisit.VisitTime).TotalSeconds };

            var state = _islandManager.GetCurrentState();
            if (state.ActiveAvatar?.Id == _current.SessionId)
            {
                _islandManager.UpsertAvatar(state.ActiveAvatar with { IsActive = false });
            }

            GlobalLogger.Info($"Sesión cerrada: {_current.SessionId} ({_current.DurationSeconds}s)");
            _current = null;
            _activeVisit = null;
        }
    }

    public void Dispose()
    {
        _islandManager?.Dispose();
    }
}
