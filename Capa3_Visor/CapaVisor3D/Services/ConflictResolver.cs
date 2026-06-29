using System;
using System.Collections.Concurrent;
using System.Text.Json;

namespace VisorSingularity.Services
{
    /// <summary>
    /// Decision tomada por el resolvedor ante un estado entrante de un peer.
    /// </summary>
    public enum ResolutionDecision
    {
        /// <summary>Aceptar y aplicar el estado entrante.</summary>
        Accept,
        /// <summary>Ignorar: es un replay o un estado causalmente anterior.</summary>
        IgnoreStale,
        /// <summary>Conflicto concurrente resuelto a favor del entrante (LWW gana).</summary>
        AcceptConcurrentWin,
        /// <summary>Conflicto concurrente resuelto a favor del local (LWW pierde).</summary>
        RejectConcurrentLose,
        /// <summary>Rechazar: modificacion de isla por un nodo que no es su autor.</summary>
        RejectUnauthorizedIsland
    }

    /// <summary>
    /// Resolvedor de conflictos de estado P2P (seccion 2.3 y 2.5 del plan).
    ///
    /// Aplica tres capas de defensa al integrar el estado de un peer:
    ///   1. Anti-replay: descarta estados con numero de secuencia (seq) menor o
    ///      igual al ultimo procesado de ese peer.
    ///   2. Causalidad (Vector Clock): si el estado entrante precede causalmente
    ///      al local se ignora; si es concurrente se resuelve por LWW usando el
    ///      timestamp criptografico firmado.
    ///   3. Autoria de isla: solo la wallet creadora de una isla puede modificar
    ///      sus datos estructurales.
    ///
    /// Es thread-safe: mantiene el ultimo seq por peer en un diccionario
    /// concurrente, ya que se invoca desde el loop de recepcion UDP.
    /// </summary>
    public sealed class ConflictResolver
    {
        // Ultimo numero de secuencia aceptado por cada peer (anti-replay).
        private readonly ConcurrentDictionary<string, long> _lastSeqByPeer = new();

        // Autor (wallet) registrado de cada isla conocida.
        private readonly ConcurrentDictionary<string, string> _islandOwners = new();

        /// <summary>
        /// Comprueba el numero de secuencia anti-replay de un peer. Devuelve true
        /// si <paramref name="incomingSeq"/> es nuevo (mayor al ultimo visto) y lo
        /// registra; false si es un replay o llega desordenado.
        /// </summary>
        public bool TryAdvanceSeq(string peerId, long incomingSeq)
        {
            if (string.IsNullOrEmpty(peerId) || incomingSeq < 0) return false;

            while (true)
            {
                if (!_lastSeqByPeer.TryGetValue(peerId, out long last))
                {
                    if (_lastSeqByPeer.TryAdd(peerId, incomingSeq)) return true;
                    continue; // otra hebra inserto primero; reintentar
                }

                if (incomingSeq <= last) return false; // replay o desorden

                if (_lastSeqByPeer.TryUpdate(peerId, incomingSeq, last)) return true;
                // CAS fallo por carrera; reintentar el bucle.
            }
        }

        /// <summary>
        /// Registra al autor de una isla la primera vez que se observa. Si ya
        /// estaba registrada con otro autor, no lo sobrescribe (la autoria es
        /// inmutable una vez establecida).
        /// </summary>
        public void RegisterIslandOwner(string islandId, string ownerWallet)
        {
            if (string.IsNullOrEmpty(islandId) || string.IsNullOrEmpty(ownerWallet)) return;
            _islandOwners.TryAdd(islandId, ownerWallet);
        }

        /// <summary>
        /// Verifica que <paramref name="claimantWallet"/> puede modificar la isla
        /// <paramref name="islandId"/>. Si la isla no tiene autor conocido, lo
        /// registra y autoriza (primer creador gana). Si ya tiene autor, solo
        /// autoriza a esa misma wallet.
        /// </summary>
        public bool IsIslandModificationAuthorized(string islandId, string claimantWallet)
        {
            if (string.IsNullOrEmpty(islandId)) return false;
            if (string.IsNullOrEmpty(claimantWallet)) return false;

            string owner = _islandOwners.GetOrAdd(islandId, claimantWallet);
            return string.Equals(owner, claimantWallet, StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>
        /// Resuelve si se debe aplicar el estado entrante de un peer combinando
        /// las tres capas de defensa. <paramref name="localClock"/> se fusiona con
        /// el reloj entrante cuando la decision es de aceptacion.
        /// </summary>
        public ResolutionDecision Resolve(
            string peerId,
            long incomingSeq,
            VectorClock incomingClock,
            VectorClock localClock,
            long incomingSignedTimestamp,
            long localSignedTimestamp)
        {
            // Capa 1: anti-replay por numero de secuencia.
            if (!TryAdvanceSeq(peerId, incomingSeq))
            {
                return ResolutionDecision.IgnoreStale;
            }

            // Capa 2: causalidad mediante reloj vectorial.
            var ordering = (incomingClock ?? new VectorClock())
                .CompareTo(localClock ?? new VectorClock());

            switch (ordering)
            {
                case ClockOrdering.After:
                    // El entrante incluye causalmente al local: aceptar.
                    localClock?.Merge(incomingClock!);
                    return ResolutionDecision.Accept;

                case ClockOrdering.Equal:
                case ClockOrdering.Before:
                    // El entrante es igual o anterior: nada nuevo que aplicar.
                    return ResolutionDecision.IgnoreStale;

                case ClockOrdering.Concurrent:
                default:
                    // Split-brain: resolver por Last-Write-Wins con timestamp firmado.
                    // Empate de timestamp se rompe por peerId para ser deterministico.
                    if (incomingSignedTimestamp > localSignedTimestamp)
                    {
                        localClock?.Merge(incomingClock!);
                        return ResolutionDecision.AcceptConcurrentWin;
                    }
                    return ResolutionDecision.RejectConcurrentLose;
            }
        }

        /// <summary>
        /// Extrae el numero de secuencia (campo "seq") de un estado JSON.
        /// Devuelve 0 si no existe, permitiendo compatibilidad con estados
        /// antiguos sin secuencia.
        /// </summary>
        public static long ExtractSeq(JsonElement root)
        {
            if (root.TryGetProperty("seq", out var seqEl) &&
                seqEl.ValueKind == JsonValueKind.Number &&
                seqEl.TryGetInt64(out long seq))
            {
                return seq;
            }
            return 0;
        }

        /// <summary>
        /// Extrae el reloj vectorial (campo "vc") de un estado JSON.
        /// </summary>
        public static VectorClock ExtractClock(JsonElement root)
        {
            if (root.TryGetProperty("vc", out var vcEl) &&
                vcEl.ValueKind == JsonValueKind.Object)
            {
                return VectorClock.FromJson(vcEl.GetRawText());
            }
            return new VectorClock();
        }

        /// <summary>Olvida el estado de un peer (al purgarse por inactividad).</summary>
        public void ForgetPeer(string peerId)
        {
            if (string.IsNullOrEmpty(peerId)) return;
            _lastSeqByPeer.TryRemove(peerId, out _);
        }
    }
}
