using Xunit;
using System.Text.Json;
using VisorSingularity.Services;

namespace VisorSingularity.Tests
{
    /// <summary>
    /// Pruebas de los mecanismos de consenso distribuido: relojes vectoriales y
    /// resolucion de conflictos (anti-replay, causalidad/LWW y autoria de isla).
    /// </summary>
    public class ConsensusTests
    {
        // ── VectorClock ───────────────────────────────────────────────────────

        [Fact]
        public void VectorClock_Increment_AdvancesCounter()
        {
            var vc = new VectorClock();
            Assert.Equal(0, vc.Get("nodeA"));
            Assert.Equal(1, vc.Increment("nodeA"));
            Assert.Equal(2, vc.Increment("nodeA"));
            Assert.Equal(2, vc.Get("nodeA"));
        }

        [Fact]
        public void VectorClock_CompareTo_DetectsBeforeAfterEqual()
        {
            var a = new VectorClock();
            var b = new VectorClock();
            Assert.Equal(ClockOrdering.Equal, a.CompareTo(b));

            a.Increment("nodeA"); // a = {A:1}
            Assert.Equal(ClockOrdering.After, a.CompareTo(b));
            Assert.Equal(ClockOrdering.Before, b.CompareTo(a));
        }

        [Fact]
        public void VectorClock_CompareTo_DetectsConcurrency()
        {
            var a = new VectorClock();
            var b = new VectorClock();
            a.Increment("nodeA"); // a = {A:1}
            b.Increment("nodeB"); // b = {B:1}

            // Cada uno avanzo en una dimension distinta → split-brain.
            Assert.Equal(ClockOrdering.Concurrent, a.CompareTo(b));
            Assert.Equal(ClockOrdering.Concurrent, b.CompareTo(a));
        }

        [Fact]
        public void VectorClock_Merge_TakesMaxPerNode()
        {
            var a = new VectorClock();
            a.Increment("nodeA"); a.Increment("nodeA"); // {A:2}
            var b = new VectorClock();
            b.Increment("nodeA"); // {A:1}
            b.Increment("nodeB"); // {A:1, B:1}

            a.Merge(b); // esperado {A:2, B:1}
            Assert.Equal(2, a.Get("nodeA"));
            Assert.Equal(1, a.Get("nodeB"));
        }

        [Fact]
        public void VectorClock_JsonRoundTrip_PreservesState()
        {
            var vc = new VectorClock();
            vc.Increment("nodeA");
            vc.Increment("nodeB");
            vc.Increment("nodeB");

            string json = vc.ToJson();
            var restored = VectorClock.FromJson(json);

            Assert.Equal(1, restored.Get("nodeA"));
            Assert.Equal(2, restored.Get("nodeB"));
            Assert.Equal(ClockOrdering.Equal, vc.CompareTo(restored));
        }

        [Fact]
        public void VectorClock_FromJson_HandlesCorruptInput()
        {
            Assert.Equal(0, VectorClock.FromJson(null).Count);
            Assert.Equal(0, VectorClock.FromJson("not-json").Count);
            Assert.Equal(0, VectorClock.FromJson("[1,2,3]").Count);
        }

        // ── ConflictResolver: anti-replay ─────────────────────────────────────

        [Fact]
        public void ConflictResolver_TryAdvanceSeq_RejectsReplayAndDisorder()
        {
            var r = new ConflictResolver();
            Assert.True(r.TryAdvanceSeq("peer1", 1));
            Assert.True(r.TryAdvanceSeq("peer1", 2));
            Assert.False(r.TryAdvanceSeq("peer1", 2)); // replay exacto
            Assert.False(r.TryAdvanceSeq("peer1", 1)); // desorden hacia atras
            Assert.True(r.TryAdvanceSeq("peer1", 5));   // salto adelante ok
        }

        // ── ConflictResolver: autoria de isla ─────────────────────────────────

        [Fact]
        public void ConflictResolver_IslandAuthorship_OnlyCreatorCanModify()
        {
            var r = new ConflictResolver();
            // El primer reclamante se convierte en el autor.
            Assert.True(r.IsIslandModificationAuthorized("island_0", "0xCREATOR"));
            // El mismo autor puede seguir modificando.
            Assert.True(r.IsIslandModificationAuthorized("island_0", "0xcreator")); // case-insensitive
            // Un tercero no autorizado es rechazado.
            Assert.False(r.IsIslandModificationAuthorized("island_0", "0xATTACKER"));
        }

        // ── ConflictResolver: resolucion combinada ────────────────────────────

        [Fact]
        public void ConflictResolver_Resolve_AcceptsCausallyNewer()
        {
            var r = new ConflictResolver();
            var local = new VectorClock();
            var incoming = new VectorClock();
            incoming.Increment("peerX"); // entrante adelantado

            var decision = r.Resolve("peerX", 1, incoming, local, 1000, 500);
            Assert.Equal(ResolutionDecision.Accept, decision);
        }

        [Fact]
        public void ConflictResolver_Resolve_IgnoresReplay()
        {
            var r = new ConflictResolver();
            var local = new VectorClock();
            var incoming = new VectorClock();
            incoming.Increment("peerX");

            Assert.Equal(ResolutionDecision.Accept, r.Resolve("peerX", 1, incoming, local, 1000, 500));
            // Mismo seq de nuevo → replay.
            Assert.Equal(ResolutionDecision.IgnoreStale, r.Resolve("peerX", 1, incoming, local, 1000, 500));
        }

        [Fact]
        public void ConflictResolver_Resolve_ConcurrentResolvedByLww()
        {
            var r = new ConflictResolver();
            var local = new VectorClock();
            local.Increment("localNode"); // local avanzo

            var incoming = new VectorClock();
            incoming.Increment("peerX");   // entrante avanzo en otra dimension → concurrente

            // Timestamp entrante mayor → gana el entrante.
            var win = r.Resolve("peerX", 1, incoming, local, 2000, 1000);
            Assert.Equal(ResolutionDecision.AcceptConcurrentWin, win);

            // Otro peer concurrente con timestamp menor → pierde.
            var local2 = new VectorClock();
            local2.Increment("localNode");
            var incoming2 = new VectorClock();
            incoming2.Increment("peerY");
            var lose = r.Resolve("peerY", 1, incoming2, local2, 500, 1000);
            Assert.Equal(ResolutionDecision.RejectConcurrentLose, lose);
        }

        // ── CatchupProtocol ───────────────────────────────────────────────────

        private static JsonElement Parse(string json) => JsonDocument.Parse(json).RootElement;

        [Fact]
        public void Catchup_BuildHello_IsRecognizedAndCarriesClock()
        {
            var clock = new VectorClock();
            clock.Increment("nodeA");
            string hello = CatchupProtocol.BuildHello("nodeA", clock);

            var root = Parse(hello);
            Assert.Equal(CatchupMessageType.Hello, CatchupProtocol.GetMessageType(root));
            Assert.Equal("nodeA", CatchupProtocol.GetString(root, "from"));
            Assert.Equal(1, CatchupProtocol.ExtractClock(root).Get("nodeA"));
        }

        [Fact]
        public void Catchup_NormalStateHasNoMessageType()
        {
            // Un broadcast de estado normal no debe ser tratado como control.
            var root = Parse("{\"u\":{},\"i\":{},\"v\":\"1.0\"}");
            Assert.Null(CatchupProtocol.GetMessageType(root));
        }

        [Fact]
        public void Catchup_ShouldRequest_WhenPeerIsAheadOrConcurrent()
        {
            var local = new VectorClock();

            // Peer más avanzado → solicitar.
            var ahead = new VectorClock();
            ahead.Increment("peerX");
            Assert.True(CatchupProtocol.ShouldRequestCatchup(local, ahead));

            // Peer igual → no solicitar.
            Assert.False(CatchupProtocol.ShouldRequestCatchup(local, new VectorClock()));

            // Peer concurrente → solicitar (puede tener datos que no tenemos).
            var l2 = new VectorClock(); l2.Increment("localNode");
            var concurrent = new VectorClock(); concurrent.Increment("peerY");
            Assert.True(CatchupProtocol.ShouldRequestCatchup(l2, concurrent));
        }

        [Fact]
        public void Catchup_ShouldNotRequest_WhenLocalIsAhead()
        {
            var local = new VectorClock();
            local.Increment("localNode");
            local.Increment("localNode");
            var behind = new VectorClock();
            behind.Increment("localNode"); // peer atrasado respecto al local

            Assert.False(CatchupProtocol.ShouldRequestCatchup(local, behind));
        }

        [Fact]
        public void Catchup_SyncResponse_EmbedsAndExtractsState()
        {
            string signedState = "{\"u\":{\"peerX\":{\"x\":1.0}},\"i\":{},\"sig\":\"ab\",\"pubkey\":\"cd\"}";
            string resp = CatchupProtocol.BuildSyncResponse("peerX", "peerY", signedState);

            var root = Parse(resp);
            Assert.Equal(CatchupMessageType.SyncResponse, CatchupProtocol.GetMessageType(root));
            Assert.Equal("peerY", CatchupProtocol.GetString(root, "to"));

            string? extracted = CatchupProtocol.ExtractEmbeddedState(root);
            Assert.NotNull(extracted);
            // El estado embebido conserva la firma original.
            var stateRoot = Parse(extracted!);
            Assert.True(stateRoot.TryGetProperty("sig", out _));
        }

        [Fact]
        public void Catchup_SyncRequest_TargetsSpecificPeer()
        {
            var clock = new VectorClock();
            string req = CatchupProtocol.BuildSyncRequest("requester", "target", clock);

            var root = Parse(req);
            Assert.Equal(CatchupMessageType.SyncRequest, CatchupProtocol.GetMessageType(root));
            Assert.Equal("requester", CatchupProtocol.GetString(root, "from"));
            Assert.Equal("target", CatchupProtocol.GetString(root, "to"));
        }
    }
}
