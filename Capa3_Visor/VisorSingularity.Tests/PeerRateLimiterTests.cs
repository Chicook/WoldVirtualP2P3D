using System;
using Xunit;
using VisorSingularity.Services;

namespace VisorSingularity.Tests
{
    public class PeerRateLimiterTests
    {
        [Fact]
        public void Test_AllowsUpToFiveUpdatesPerSecond()
        {
            var limiter = new PeerRateLimiter();
            const string peer = "peerAlpha";

            for (int i = 0; i < PeerRateLimiter.MaxUpdatesPerSecond; i++)
            {
                Assert.True(limiter.TryAllowPeerUpdate(peer));
            }

            Assert.False(limiter.TryAllowPeerUpdate(peer));
        }

        [Fact]
        public void Test_BlocksIpTemporarily()
        {
            var limiter = new PeerRateLimiter();
            const string ip = "192.168.1.50";

            Assert.False(limiter.IsIpBlocked(ip));
            limiter.BlockIp(ip, 1);
            Assert.True(limiter.IsIpBlocked(ip));
        }

        [Fact]
        public void Test_ForgetPeerResetsWindow()
        {
            var limiter = new PeerRateLimiter();
            const string peer = "peerBeta";

            for (int i = 0; i < PeerRateLimiter.MaxUpdatesPerSecond; i++)
            {
                limiter.TryAllowPeerUpdate(peer);
            }
            Assert.False(limiter.TryAllowPeerUpdate(peer));

            limiter.ForgetPeer(peer);
            Assert.True(limiter.TryAllowPeerUpdate(peer));
        }
    }
}
