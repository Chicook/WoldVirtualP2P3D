using Xunit;
using System.IO;
using System.Linq;
using VisorSingularity.Services;

namespace VisorSingularity.Tests
{
    /// <summary>
    /// Pruebas del bootstrap de red por IPNS: parseo y validación de la lista de
    /// nodos semilla y persistencia de la caché local para arranque offline.
    /// </summary>
    public class BootstrapTests
    {
        [Fact]
        public void ParseSeedList_ParsesValidEntries()
        {
            string json = @"{
                ""version"": ""1.0"",
                ""peers"": [
                    { ""nodeId"": ""a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f61234"", ""host"": ""203.0.113.5"", ""port"": 50099, ""wallet"": ""0xABC"" },
                    { ""nodeId"": ""seedNodeTwo"", ""host"": ""seed.woldvirtual.io"", ""port"": 50099 }
                ]
            }";

            var peers = BootstrapPeerService.ParseSeedList(json);

            Assert.Equal(2, peers.Count);
            Assert.Equal("203.0.113.5", peers[0].Host);
            Assert.Equal(50099, peers[0].Port);
            Assert.Equal("0xABC", peers[0].Wallet);
            Assert.Null(peers[1].Wallet); // wallet opcional ausente
        }

        [Fact]
        public void ParseSeedList_RejectsInvalidEntries()
        {
            string json = @"{
                ""peers"": [
                    { ""nodeId"": """", ""host"": ""1.2.3.4"", ""port"": 50099 },
                    { ""nodeId"": ""validId"", ""host"": ""../escape"", ""port"": 50099 },
                    { ""nodeId"": ""validId"", ""host"": ""1.2.3.4"", ""port"": 0 },
                    { ""nodeId"": ""validId"", ""host"": ""1.2.3.4"", ""port"": 70000 },
                    { ""nodeId"": ""goodId"", ""host"": ""1.2.3.4"", ""port"": 50099 }
                ]
            }";

            var peers = BootstrapPeerService.ParseSeedList(json);

            // Solo la última entrada es válida.
            Assert.Single(peers);
            Assert.Equal("goodId", peers[0].NodeId);
        }

        [Fact]
        public void ParseSeedList_HandlesCorruptOrEmptyInput()
        {
            Assert.Empty(BootstrapPeerService.ParseSeedList(null!));
            Assert.Empty(BootstrapPeerService.ParseSeedList(""));
            Assert.Empty(BootstrapPeerService.ParseSeedList("not-json"));
            Assert.Empty(BootstrapPeerService.ParseSeedList("{\"peers\": \"notarray\"}"));
            Assert.Empty(BootstrapPeerService.ParseSeedList("[1,2,3]"));
        }

        [Fact]
        public void IsValidHost_RejectsPathInjection()
        {
            Assert.True(BootstrapPeerService.IsValidHost("203.0.113.5"));
            Assert.True(BootstrapPeerService.IsValidHost("seed.woldvirtual.io"));
            Assert.False(BootstrapPeerService.IsValidHost(""));
            Assert.False(BootstrapPeerService.IsValidHost("../../etc"));
            Assert.False(BootstrapPeerService.IsValidHost("a/b"));
            Assert.False(BootstrapPeerService.IsValidHost("a\\b"));
        }

        [Fact]
        public void IsValidNodeId_AcceptsHashAndSafeIds()
        {
            Assert.True(BootstrapPeerService.IsValidNodeId(
                "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f61234"));
            Assert.True(BootstrapPeerService.IsValidNodeId("seed_node-1"));
            Assert.False(BootstrapPeerService.IsValidNodeId(""));
            Assert.False(BootstrapPeerService.IsValidNodeId("bad/id"));
        }

        [Fact]
        public void Cache_SaveAndLoad_RoundTrips()
        {
            string tempFile = Path.Combine(Path.GetTempPath(),
                $"wv_bootstrap_test_{System.Guid.NewGuid():N}.json");
            try
            {
                var service = new BootstrapPeerService(tempFile);
                var seeds = new[]
                {
                    new SeedPeer("goodId", "203.0.113.5", 50099, "0xABC"),
                    new SeedPeer("seedTwo", "seed.woldvirtual.io", 50099, null)
                };

                service.SaveCache(seeds);
                Assert.True(File.Exists(tempFile));

                var loaded = service.LoadCache();
                Assert.Equal(2, loaded.Count);
                Assert.Contains(loaded, p => p.NodeId == "goodId" && p.Port == 50099);
            }
            finally
            {
                if (File.Exists(tempFile)) File.Delete(tempFile);
            }
        }

        [Fact]
        public void Cache_LoadMissingFile_ReturnsEmpty()
        {
            string missing = Path.Combine(Path.GetTempPath(),
                $"wv_missing_{System.Guid.NewGuid():N}.json");
            var service = new BootstrapPeerService(missing);
            Assert.Empty(service.LoadCache());
        }
    }
}
