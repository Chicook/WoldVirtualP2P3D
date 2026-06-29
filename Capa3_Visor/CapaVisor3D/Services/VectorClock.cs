using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Text.Json;

namespace VisorSingularity.Services
{
    /// <summary>
    /// Resultado de comparar dos relojes vectoriales.
    /// </summary>
    public enum ClockOrdering
    {
        /// <summary>Ambos relojes son identicos.</summary>
        Equal,
        /// <summary>El reloj A ocurrio estrictamente antes que B (A → B).</summary>
        Before,
        /// <summary>El reloj A ocurrio estrictamente despues que B (B → A).</summary>
        After,
        /// <summary>Los relojes son concurrentes: hubo split-brain (A ∥ B).</summary>
        Concurrent
    }

    /// <summary>
    /// Reloj vectorial para causalidad distribuida en la red P2P de WoldVirtual.
    ///
    /// Cada nodo mantiene un contador monotonico por cada peer conocido. Al
    /// comparar dos relojes se determina si un estado precede a otro, le sigue,
    /// es identico o es concurrente (split-brain). Esto sustenta la recuperacion
    /// tras particiones de red descrita en la seccion 2.5 del plan: el nodo con
    /// el reloj "anterior" solicita un catch-up; los concurrentes se resuelven
    /// por LWW criptografico (timestamp firmado) y por autoria de isla.
    ///
    /// La clave de cada entrada es el NodeId (hash SHA-256 de 64 hex).
    /// </summary>
    public sealed class VectorClock
    {
        private readonly Dictionary<string, long> _counters;

        public VectorClock()
        {
            _counters = new Dictionary<string, long>(StringComparer.Ordinal);
        }

        private VectorClock(Dictionary<string, long> counters)
        {
            _counters = counters;
        }

        /// <summary>Numero de entradas (nodos conocidos) del reloj.</summary>
        public int Count => _counters.Count;

        /// <summary>Devuelve el contador de un nodo (0 si no existe).</summary>
        public long Get(string nodeId)
        {
            if (string.IsNullOrEmpty(nodeId)) return 0;
            return _counters.TryGetValue(nodeId, out var v) ? v : 0;
        }

        /// <summary>
        /// Incrementa el contador del nodo local. Se invoca antes de emitir un
        /// nuevo estado para reflejar el avance causal de este nodo.
        /// </summary>
        public long Increment(string localNodeId)
        {
            if (string.IsNullOrEmpty(localNodeId))
                throw new ArgumentException("localNodeId no puede estar vacio", nameof(localNodeId));

            long next = Get(localNodeId) + 1;
            _counters[localNodeId] = next;
            return next;
        }

        /// <summary>
        /// Fusiona otro reloj tomando el maximo por nodo (operacion de join del
        /// semilattice). Tras recibir el estado de un peer, el nodo local hace
        /// merge para no perder el conocimiento causal del resto de la red.
        /// </summary>
        public void Merge(VectorClock other)
        {
            if (other == null) return;
            foreach (var kvp in other._counters)
            {
                long current = Get(kvp.Key);
                if (kvp.Value > current)
                {
                    _counters[kvp.Key] = kvp.Value;
                }
            }
        }

        /// <summary>
        /// Compara este reloj (A) con otro (B) y devuelve la relacion causal.
        /// </summary>
        public ClockOrdering CompareTo(VectorClock other)
        {
            if (other == null) return ClockOrdering.After;

            bool aGreater = false; // existe algun nodo con A > B
            bool bGreater = false; // existe algun nodo con B > A

            // Recorremos la union de claves de ambos relojes.
            var keys = new HashSet<string>(_counters.Keys, StringComparer.Ordinal);
            keys.UnionWith(other._counters.Keys);

            foreach (var key in keys)
            {
                long a = Get(key);
                long b = other.Get(key);
                if (a > b) aGreater = true;
                else if (b > a) bGreater = true;

                // Si ya divergen en ambos sentidos, son concurrentes.
                if (aGreater && bGreater) return ClockOrdering.Concurrent;
            }

            if (!aGreater && !bGreater) return ClockOrdering.Equal;
            return aGreater ? ClockOrdering.After : ClockOrdering.Before;
        }

        /// <summary>True si este reloj es causalmente posterior o igual a <paramref name="other"/>.</summary>
        public bool DominatesOrEquals(VectorClock other)
        {
            var ord = CompareTo(other);
            return ord == ClockOrdering.After || ord == ClockOrdering.Equal;
        }

        /// <summary>Crea una copia independiente del reloj.</summary>
        public VectorClock Clone()
        {
            return new VectorClock(new Dictionary<string, long>(_counters, StringComparer.Ordinal));
        }

        // ── Serializacion JSON ────────────────────────────────────────────────

        /// <summary>
        /// Serializa el reloj a un objeto JSON simple { nodeId: counter, ... }.
        /// Se incrusta en el campo "vc" del estado del peer.
        /// </summary>
        public string ToJson()
        {
            return JsonSerializer.Serialize(_counters);
        }

        /// <summary>
        /// Reconstruye un reloj desde su representacion JSON. Entradas invalidas
        /// (clave vacia o contador negativo) se descartan de forma defensiva.
        /// </summary>
        public static VectorClock FromJson(string? json)
        {
            var clock = new VectorClock();
            if (string.IsNullOrWhiteSpace(json)) return clock;

            try
            {
                using var doc = JsonDocument.Parse(json);
                if (doc.RootElement.ValueKind != JsonValueKind.Object) return clock;

                foreach (var prop in doc.RootElement.EnumerateObject())
                {
                    if (string.IsNullOrEmpty(prop.Name)) continue;
                    if (prop.Value.ValueKind == JsonValueKind.Number &&
                        prop.Value.TryGetInt64(out long counter) && counter >= 0)
                    {
                        clock._counters[prop.Name] = counter;
                    }
                }
            }
            catch (JsonException)
            {
                // JSON corrupto: devolvemos un reloj vacio en lugar de propagar.
            }

            return clock;
        }

        /// <summary>Representacion legible para logs y diagnostico.</summary>
        public override string ToString()
        {
            if (_counters.Count == 0) return "{}";
            var sb = new StringBuilder("{");
            bool first = true;
            foreach (var kvp in _counters.OrderBy(k => k.Key, StringComparer.Ordinal))
            {
                if (!first) sb.Append(", ");
                // Mostramos solo un prefijo del nodeId para no saturar el log.
                string shortId = kvp.Key.Length > 8 ? kvp.Key.Substring(0, 8) : kvp.Key;
                sb.Append(shortId).Append(':').Append(kvp.Value.ToString(CultureInfo.InvariantCulture));
                first = false;
            }
            sb.Append('}');
            return sb.ToString();
        }
    }
}
