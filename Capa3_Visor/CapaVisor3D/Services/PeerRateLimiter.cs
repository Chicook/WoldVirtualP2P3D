using System;
using System.Collections.Concurrent;
using System.Collections.Generic;

namespace VisorSingularity.Services
{
    /// <summary>
    /// Limita la tasa de actualizaciones de estado por peer (sección 2.3 del plan)
    /// y aplica bloqueo temporal de IP tras intentos de inyección.
    /// </summary>
    public sealed class PeerRateLimiter
    {
        public const int MaxUpdatesPerSecond = 5;
        public const int DefaultBlockSeconds = 60;
        private const int WindowMs = 1000;

        private readonly ConcurrentDictionary<string, Queue<long>> _peerWindows = new();
        private readonly ConcurrentDictionary<string, long> _blockedIps = new();

        public bool IsIpBlocked(string ip)
        {
            if (string.IsNullOrEmpty(ip)) return false;
            if (!_blockedIps.TryGetValue(ip, out long unblockAt)) return false;

            long now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            if (now >= unblockAt)
            {
                _blockedIps.TryRemove(ip, out _);
                return false;
            }
            return true;
        }

        public void BlockIp(string ip, int seconds = DefaultBlockSeconds)
        {
            if (string.IsNullOrEmpty(ip)) return;
            long unblockAt = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() + (seconds * 1000L);
            _blockedIps[ip] = unblockAt;
        }

        /// <summary>
        /// Devuelve true si la actualización está permitida; false si supera 5/s.
        /// </summary>
        public bool TryAllowPeerUpdate(string peerId)
        {
            if (string.IsNullOrEmpty(peerId)) return false;

            long now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            var window = _peerWindows.GetOrAdd(peerId, _ => new Queue<long>());

            lock (window)
            {
                while (window.Count > 0 && now - window.Peek() > WindowMs)
                {
                    window.Dequeue();
                }

                if (window.Count >= MaxUpdatesPerSecond)
                {
                    return false;
                }

                window.Enqueue(now);
                return true;
            }
        }

        public void ForgetPeer(string peerId)
        {
            if (string.IsNullOrEmpty(peerId)) return;
            _peerWindows.TryRemove(peerId, out _);
        }
    }
}
