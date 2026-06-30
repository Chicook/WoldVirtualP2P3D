using System;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace VisorSingularity.Services
{
    /// <summary>
    /// Tipos de mensaje de control del protocolo de recuperacion (catch-up).
    /// Viajan por el mismo socket UDP que el estado, distinguidos por el campo
    /// "_t". Los broadcasts de estado normales no llevan "_t".
    /// </summary>
    public static class CatchupMessageType
    {
        /// <summary>Anuncio de presencia con el reloj vectorial del emisor.</summary>
        public const string Hello = "hello";
        /// <summary>Solicitud de estado completo al peer mas avanzado.</summary>
        public const string SyncRequest = "sync_req";
        /// <summary>Respuesta con el estado completo solicitado.</summary>
        public const string SyncResponse = "sync_resp";
    }

    /// <summary>
    /// Construye y parsea los mensajes de control del "Catch-up State Sync"
    /// (seccion 2.5 del plan). Cuando un nodo se reincorpora tras una particion
    /// de red, anuncia su reloj vectorial (HELLO); si otro nodo detecta que esta
    /// mas avanzado, el nodo atrasado solicita (SYNC_REQ) y recibe (SYNC_RESP) el
    /// estado completo para reconciliar el split-brain.
    ///
    /// Todos los metodos son estaticos y sin estado: la decision de "quien esta
    /// mas avanzado" se delega al <see cref="VectorClock"/>.
    /// </summary>
    public static class CatchupProtocol
    {
        /// <summary>
        /// Devuelve el tipo de mensaje de control, o null si el JSON es un
        /// broadcast de estado normal (sin campo "_t").
        /// </summary>
        public static string? GetMessageType(JsonElement root)
        {
            if (root.TryGetProperty("_t", out var tEl) &&
                tEl.ValueKind == JsonValueKind.String)
            {
                return tEl.GetString();
            }
            return null;
        }

        /// <summary>Construye un mensaje HELLO con la identidad y el reloj del nodo.</summary>
        public static string BuildHello(string nodeId, VectorClock clock)
        {
            var obj = new JsonObject
            {
                ["_t"] = CatchupMessageType.Hello,
                ["from"] = nodeId,
                ["vc"] = JsonNode.Parse(clock.ToJson())
            };
            return obj.ToJsonString();
        }

        /// <summary>
        /// Construye una solicitud de sincronizacion dirigida a un peer concreto,
        /// incluyendo el reloj del solicitante para que el receptor sepa que falta.
        /// </summary>
        public static string BuildSyncRequest(string fromNodeId, string toNodeId, VectorClock clock)
        {
            var obj = new JsonObject
            {
                ["_t"] = CatchupMessageType.SyncRequest,
                ["from"] = fromNodeId,
                ["to"] = toNodeId,
                ["vc"] = JsonNode.Parse(clock.ToJson())
            };
            return obj.ToJsonString();
        }

        /// <summary>
        /// Envuelve el estado completo del nodo en una respuesta de sincronizacion
        /// dirigida al solicitante. El estado va firmado aparte por el emisor.
        /// </summary>
        public static string BuildSyncResponse(string fromNodeId, string toNodeId, string signedStateJson)
        {
            var stateNode = JsonNode.Parse(signedStateJson);
            var obj = new JsonObject
            {
                ["_t"] = CatchupMessageType.SyncResponse,
                ["from"] = fromNodeId,
                ["to"] = toNodeId,
                ["state"] = stateNode
            };
            return obj.ToJsonString();
        }

        /// <summary>
        /// Decide si el nodo local debe solicitar catch-up a un peer dado.
        /// Solo lo hara cuando el reloj del peer sea causalmente posterior
        /// (<see cref="ClockOrdering.After"/>) o concurrente respecto al local,
        /// senal de que ese peer puede tener informacion que el local no posee.
        /// </summary>
        public static bool ShouldRequestCatchup(VectorClock localClock, VectorClock peerClock)
        {
            if (peerClock == null) return false;
            var ordering = peerClock.CompareTo(localClock ?? new VectorClock());
            return ordering == ClockOrdering.After || ordering == ClockOrdering.Concurrent;
        }

        /// <summary>
        /// Extrae el reloj vectorial de un mensaje de control.
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

        /// <summary>Lee un campo string del mensaje (from/to), o cadena vacia.</summary>
        public static string GetString(JsonElement root, string property)
        {
            if (root.TryGetProperty(property, out var el) &&
                el.ValueKind == JsonValueKind.String)
            {
                return el.GetString() ?? string.Empty;
            }
            return string.Empty;
        }

        /// <summary>
        /// Extrae el JSON de estado embebido en una respuesta SYNC_RESP, o null
        /// si el mensaje no contiene un objeto "state" valido.
        /// </summary>
        public static string? ExtractEmbeddedState(JsonElement root)
        {
            if (root.TryGetProperty("state", out var stateEl) &&
                stateEl.ValueKind == JsonValueKind.Object)
            {
                return stateEl.GetRawText();
            }
            return null;
        }
    }
}
