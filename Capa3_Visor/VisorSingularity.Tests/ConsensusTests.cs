using Xunit;
using VisorSingularity.Services;

namespace VisorSingularity.Tests
{
    public class ConsensusTests
    {
        [Fact]
        public void TestVectorClockComparisons()
        {
            var clockA = new VectorClock();
            var clockB = new VectorClock();

            // Empty clocks are equal
            Assert.Equal(ClockOrdering.Equal, clockA.CompareTo(clockB));

            // A increments node1
            clockA.Increment("node1");
            // A should be After B (A is more advanced)
            Assert.Equal(ClockOrdering.After, clockA.CompareTo(clockB));
            // B should be Before A
            Assert.Equal(ClockOrdering.Before, clockB.CompareTo(clockA));

            // B increments node1 as well
            clockB.Increment("node1");
            Assert.Equal(ClockOrdering.Equal, clockA.CompareTo(clockB));

            // A increments node1 again, B increments node2
            clockA.Increment("node1");
            clockB.Increment("node2");
            // Now A has {node1:2, node2:0}, B has {node1:1, node2:1}. They are concurrent.
            Assert.Equal(ClockOrdering.Concurrent, clockA.CompareTo(clockB));
            Assert.Equal(ClockOrdering.Concurrent, clockB.CompareTo(clockA));
        }

        [Fact]
        public void TestVectorClockMerge()
        {
            var clockA = new VectorClock();
            clockA.Increment("node1");
            clockA.Increment("node1");

            var clockB = new VectorClock();
            clockB.Increment("node1");
            clockB.Increment("node2");

            clockA.Merge(clockB);
            // clockA should now have {node1:2, node2:1}
            Assert.Equal(2, clockA.Get("node1"));
            Assert.Equal(1, clockA.Get("node2"));
        }

        [Fact]
        public void TestVectorClockSerialization()
        {
            var clock = new VectorClock();
            clock.Increment("node1");
            clock.Increment("node2");
            clock.Increment("node2");

            string json = clock.ToJson();
            var deserialized = VectorClock.FromJson(json);

            Assert.Equal(1, deserialized.Get("node1"));
            Assert.Equal(2, deserialized.Get("node2"));
            Assert.Equal(0, deserialized.Get("node3"));
        }

        [Fact]
        public void TestConflictResolverSeqAntiReplay()
        {
            var resolver = new ConflictResolver();

            // First seq 10 is accepted
            Assert.True(resolver.TryAdvanceSeq("peer1", 10));

            // Replay of 10 or 9 is ignored
            Assert.False(resolver.TryAdvanceSeq("peer1", 10));
            Assert.False(resolver.TryAdvanceSeq("peer1", 9));

            // Advanced seq 11 is accepted
            Assert.True(resolver.TryAdvanceSeq("peer1", 11));
        }

        [Fact]
        public void TestConflictResolverResolveCausalAndLww()
        {
            var resolver = new ConflictResolver();
            
            var localClock = new VectorClock();
            localClock.Increment("local");

            var incomingClock = new VectorClock();
            incomingClock.Increment("local");
            incomingClock.Increment("remote"); // incoming clock is causal successor (After local)

            // 1. Causal successor is accepted
            var decision1 = resolver.Resolve(
                peerId: "remote",
                incomingSeq: 1,
                incomingClock: incomingClock,
                localClock: localClock,
                incomingSignedTimestamp: 1000,
                localSignedTimestamp: 500
            );
            Assert.Equal(ResolutionDecision.Accept, decision1);

            // Now localClock contains the merged clock {local:1, remote:1}
            Assert.Equal(1, localClock.Get("local"));
            Assert.Equal(1, localClock.Get("remote"));

            // 2. Causal predecessor or equal is ignored
            var staleClock = new VectorClock();
            staleClock.Increment("local"); // {local:1} - Before/Equal to local clock
            
            var decision2 = resolver.Resolve(
                peerId: "remote",
                incomingSeq: 2,
                incomingClock: staleClock,
                localClock: localClock,
                incomingSignedTimestamp: 2000,
                localSignedTimestamp: 1000
            );
            Assert.Equal(ResolutionDecision.IgnoreStale, decision2);

            // 3. Concurrent clocks resolved via LWW
            var concurrentClock = new VectorClock();
            concurrentClock.Increment("remote");
            concurrentClock.Increment("remote"); // {remote:2} -> concurrent to local {local:1, remote:1}

            // Incoming wins because of higher timestamp (1200 > 1000)
            var decision3 = resolver.Resolve(
                peerId: "remote",
                incomingSeq: 3,
                incomingClock: concurrentClock,
                localClock: localClock,
                incomingSignedTimestamp: 1200,
                localSignedTimestamp: 1000
            );
            Assert.Equal(ResolutionDecision.AcceptConcurrentWin, decision3);

            // Incoming loses because of lower timestamp (800 < 1200)
            var concurrentClock2 = new VectorClock();
            concurrentClock2.Increment("local");
            concurrentClock2.Increment("local"); // concurrent again
            
            var decision4 = resolver.Resolve(
                peerId: "remote",
                incomingSeq: 4,
                incomingClock: concurrentClock2,
                localClock: localClock,
                incomingSignedTimestamp: 800,
                localSignedTimestamp: 1200
            );
            Assert.Equal(ResolutionDecision.RejectConcurrentLose, decision4);
        }

        [Fact]
        public void TestConflictResolverIslandOwnership()
        {
            var resolver = new ConflictResolver();

            // Claim island1 with walletA
            Assert.True(resolver.IsIslandModificationAuthorized("island1", "walletA"));

            // walletA can modify it again
            Assert.True(resolver.IsIslandModificationAuthorized("island1", "walletA"));
            // Case insensitive comparison
            Assert.True(resolver.IsIslandModificationAuthorized("island1", "WALLETA"));

            // walletB cannot modify island1 (first creator/claimant wins)
            Assert.False(resolver.IsIslandModificationAuthorized("island1", "walletB"));
        }
    }
}
