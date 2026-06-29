using System;
using System.Collections.Concurrent;
using System.Globalization;
using System.Text;
using System.Threading;

namespace VisorSingularity.Services
{
    /// <summary>
    /// Instantanea inmutable del estado de la red P2P en un momento dado.
    /// Se entrega a la capa de presentacion para mostrar telemetria sin exponer
    /// el estado interno mutable del servicio.
    /// </summary>
    public sealed record NetworkTelemetrySnapshot(
        long PacketsSent,
        long PacketsReceived,
        long BytesSent,
        long BytesReceived,
        long SignaturesRejected,
        long InjectionAttempts,
        long Reconnections,
        long PeersExpired,
        int ActivePeers,
        DateTimeOffset LastActivityUtc,
        TimeSpan Uptime);

    /// <summary>
    /// Servicio central de telemetria de red P2P. Recopila contadores de trafico,
    /// seguridad y conectividad emitidos por <c>PeerSyncService</c> y
    /// <c>P2PWebNode</c>. Es thread-safe (usa <see cref="Interlocked"/>) porque
    /// recibe eventos desde multiples loops asincronos simultaneos.
    ///
    /// Sustituye los <c>Debug.WriteLine</c> dispersos por metricas agregadas que
    /// la UI puede consultar y que sirven de base para alertas y diagnostico.
    /// </summary>
    public sealed class NetworkTelemetryService
    {
        // Singleton de proceso: hay una unica red P2P por instancia del visor.
        private static readonly Lazy<NetworkTelemetryService> _instance =
            new(() => new NetworkTelemetryService());

        public static NetworkTelemetryService Instance => _instance.Value;

        // ── Contadores (acceso via Interlocked) ───────────────────────────────
        private long _packetsSent;
        private long _packetsReceived;
        private long _bytesSent;
        private long _bytesReceived;
        private long _signaturesRejected;
        private long _injectionAttempts;
        private long _reconnections;
        private long _peersExpired;

        // Marca de tiempo (ticks UTC) de la ultima actividad de red observada.
        private long _lastActivityTicks;

        private readonly DateTimeOffset _startedUtc;

        // Conjunto de peers vistos recientemente, para contar peers activos.
        private readonly ConcurrentDictionary<string, DateTimeOffset> _activePeers = new();

        // Ventana tras la cual un peer se considera inactivo para la metrica.
        private static readonly TimeSpan ActiveWindow = TimeSpan.FromSeconds(35);

        /// <summary>Se dispara cada vez que cambia algun contador relevante.</summary>
        public event Action<NetworkTelemetrySnapshot>? SnapshotUpdated;

        private NetworkTelemetryService()
        {
            _startedUtc = DateTimeOffset.UtcNow;
            _lastActivityTicks = _startedUtc.UtcTicks;
        }

        // ── Registro de eventos de trafico ────────────────────────────────────

        /// <summary>Registra un paquete saliente (broadcast/respuesta).</summary>
        public void RecordPacketSent(int byteCount)
        {
            Interlocked.Increment(ref _packetsSent);
            Interlocked.Add(ref _bytesSent, Math.Max(0, byteCount));
            TouchActivity();
        }

        /// <summary>Registra un paquete entrante valido o no.</summary>
        public void RecordPacketReceived(int byteCount)
        {
            Interlocked.Increment(ref _packetsReceived);
            Interlocked.Add(ref _bytesReceived, Math.Max(0, byteCount));
            TouchActivity();
        }

        // ── Registro de eventos de seguridad ──────────────────────────────────

        /// <summary>Una firma criptografica remota no pudo validarse.</summary>
        public void RecordSignatureRejected()
        {
            Interlocked.Increment(ref _signaturesRejected);
            TouchActivity();
        }

        /// <summary>Se detecto un intento de inyeccion (Directory Traversal, etc.).</summary>
        public void RecordInjectionAttempt()
        {
            Interlocked.Increment(ref _injectionAttempts);
            TouchActivity();
        }

        // ── Registro de eventos de conectividad ───────────────────────────────

        /// <summary>Un transporte (WS/UDP/tunel) tuvo que reconectarse.</summary>
        public void RecordReconnection()
        {
            Interlocked.Increment(ref _reconnections);
            TouchActivity();
        }

        /// <summary>Un peer fue purgado por inactividad.</summary>
        public void RecordPeerExpired(string peerId)
        {
            Interlocked.Increment(ref _peersExpired);
            if (!string.IsNullOrEmpty(peerId))
            {
                _activePeers.TryRemove(peerId, out _);
            }
            EmitSnapshot();
        }

        /// <summary>Marca a un peer como visto ahora (lo cuenta como activo).</summary>
        public void RecordPeerSeen(string peerId)
        {
            if (string.IsNullOrEmpty(peerId)) return;
            _activePeers[peerId] = DateTimeOffset.UtcNow;
            TouchActivity();
            EmitSnapshot();
        }

        // ── Consulta ──────────────────────────────────────────────────────────

        /// <summary>Numero de peers vistos dentro de la ventana activa.</summary>
        public int GetActivePeerCount()
        {
            var threshold = DateTimeOffset.UtcNow - ActiveWindow;
            int count = 0;
            foreach (var kvp in _activePeers)
            {
                if (kvp.Value >= threshold)
                {
                    count++;
                }
                else
                {
                    // Limpieza perezosa de entradas caducadas.
                    _activePeers.TryRemove(kvp.Key, out _);
                }
            }
            return count;
        }

        /// <summary>Construye una instantanea coherente del estado actual.</summary>
        public NetworkTelemetrySnapshot GetSnapshot()
        {
            return new NetworkTelemetrySnapshot(
                PacketsSent: Interlocked.Read(ref _packetsSent),
                PacketsReceived: Interlocked.Read(ref _packetsReceived),
                BytesSent: Interlocked.Read(ref _bytesSent),
                BytesReceived: Interlocked.Read(ref _bytesReceived),
                SignaturesRejected: Interlocked.Read(ref _signaturesRejected),
                InjectionAttempts: Interlocked.Read(ref _injectionAttempts),
                Reconnections: Interlocked.Read(ref _reconnections),
                PeersExpired: Interlocked.Read(ref _peersExpired),
                ActivePeers: GetActivePeerCount(),
                LastActivityUtc: new DateTimeOffset(
                    Interlocked.Read(ref _lastActivityTicks), TimeSpan.Zero),
                Uptime: DateTimeOffset.UtcNow - _startedUtc);
        }

        /// <summary>Resumen legible de una sola linea para barras de estado/logs.</summary>
        public string GetSummaryLine()
        {
            var s = GetSnapshot();
            var ci = CultureInfo.InvariantCulture;
            var sb = new StringBuilder();
            sb.Append("Peers: ").Append(s.ActivePeers.ToString(ci));
            sb.Append(" | Rx: ").Append(s.PacketsReceived.ToString(ci));
            sb.Append(" / Tx: ").Append(s.PacketsSent.ToString(ci));
            sb.Append(" | Rechazos: ").Append(s.SignaturesRejected.ToString(ci));
            sb.Append(" | Inyecciones: ").Append(s.InjectionAttempts.ToString(ci));
            sb.Append(" | Reconexiones: ").Append(s.Reconnections.ToString(ci));
            return sb.ToString();
        }

        /// <summary>Reinicia todos los contadores (util para tests y nueva sesion).</summary>
        public void Reset()
        {
            Interlocked.Exchange(ref _packetsSent, 0);
            Interlocked.Exchange(ref _packetsReceived, 0);
            Interlocked.Exchange(ref _bytesSent, 0);
            Interlocked.Exchange(ref _bytesReceived, 0);
            Interlocked.Exchange(ref _signaturesRejected, 0);
            Interlocked.Exchange(ref _injectionAttempts, 0);
            Interlocked.Exchange(ref _reconnections, 0);
            Interlocked.Exchange(ref _peersExpired, 0);
            Interlocked.Exchange(ref _lastActivityTicks, DateTimeOffset.UtcNow.UtcTicks);
            _activePeers.Clear();
            EmitSnapshot();
        }

        // ── Internos ──────────────────────────────────────────────────────────

        private void TouchActivity()
        {
            Interlocked.Exchange(ref _lastActivityTicks, DateTimeOffset.UtcNow.UtcTicks);
        }

        private void EmitSnapshot()
        {
            var handler = SnapshotUpdated;
            if (handler != null)
            {
                handler(GetSnapshot());
            }
        }
    }
}
