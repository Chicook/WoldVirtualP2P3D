using System;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Xunit;
using VisorSingularity.Services;

namespace VisorSingularity.Tests
{
    public class PeerRateLimiterTests
    {
        [Fact]
        public void TestPeerRateLimiterUpdates()
        {
            var rateLimiter = new PeerRateLimiter();
            string peerId = "test_peer_123";

            // Allow first 5 updates
            for (int i = 0; i < 5; i++)
            {
                Assert.True(rateLimiter.TryAllowPeerUpdate(peerId));
            }

            // 6th update in same window should be blocked
            Assert.False(rateLimiter.TryAllowPeerUpdate(peerId));
        }

        [Fact]
        public async Task TestIpBlockingAndExpiration()
        {
            var rateLimiter = new PeerRateLimiter();
            string maliciousIp = "192.168.1.50";

            Assert.False(rateLimiter.IsIpBlocked(maliciousIp));

            // Block IP for 1 second
            rateLimiter.BlockIp(maliciousIp, seconds: 1);
            Assert.True(rateLimiter.IsIpBlocked(maliciousIp));

            // Wait 1.1 seconds and check again
            await Task.Delay(1100);
            Assert.False(rateLimiter.IsIpBlocked(maliciousIp));
        }

        [Fact]
        public void TestDirectoryTraversalRegexSaneamiento()
        {
            // Regex from PeerSyncService.cs to sanitize remoteId
            var regexHex = new Regex("^[a-fA-F0-9]{64}$");
            var regexAlphaNum = new Regex("^[a-zA-Z0-9_\\-]+$");

            Func<string, bool> isIdSafe = (id) => regexHex.IsMatch(id) || regexAlphaNum.IsMatch(id);

            // Safe cases
            Assert.True(isIdSafe("f83a73c09b8c92a6f8c75c8e9826a7C841E34b9826a7C841E34b9826a7C841E3"));
            Assert.True(isIdSafe("user_avatar-123"));
            Assert.True(isIdSafe("peerNode"));

            // Dangerous/Unsafe cases (directory traversal, special chars)
            Assert.False(isIdSafe("../peer"));
            Assert.False(isIdSafe("..\\peer"));
            Assert.False(isIdSafe("peer/sub"));
            Assert.False(isIdSafe("peerId; rm -rf /"));
            Assert.False(isIdSafe("peerId?foo=bar"));
        }
    }
}
