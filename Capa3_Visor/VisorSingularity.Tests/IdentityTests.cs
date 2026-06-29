using Xunit;
using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using VisorSingularity.Identity;
using VisorSingularity.Services;

namespace VisorSingularity.Tests
{
    public class IdentityTests
    {
        [Fact]
        public void Test_LoadOrCreate_GeneratesValidIdentity()
        {
            using var identity = NodeIdentity.LoadOrCreate();
            
            Assert.NotNull(identity);
            Assert.False(string.IsNullOrEmpty(identity.NodeId));
            // NodeId debe ser el hash SHA-256 puro (64 hex), compatible con el saneamiento de PeerSyncService.
            Assert.Matches("^[a-fA-F0-9]{64}$", identity.NodeId);
            // El DID debe formatear el prefijo una sola vez (sin doble prefijo).
            Assert.Equal($"did:wv:node:{identity.NodeId}", identity.DID);
            Assert.DoesNotContain("did:wv:node:did:wv:node:", identity.DID);
            Assert.NotNull(identity.PublicKey);
            Assert.True(identity.PublicKey.Length > 0);
            Assert.True(identity.CurveName == "secp256k1" || identity.CurveName == "nistP256");
        }

        [Fact]
        public void Test_DPAPIPersistence_KeepsSameIdentity()
        {
            string appDataPath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "WoldVirtual"
            );
            string keyPath = Path.Combine(appDataPath, "node.key");

            string originalNodeId;
            using (var firstIdentity = NodeIdentity.LoadOrCreate())
            {
                originalNodeId = firstIdentity.NodeId;
            }

            Assert.True(File.Exists(keyPath));

            using (var secondIdentity = NodeIdentity.LoadOrCreate())
            {
                Assert.Equal(originalNodeId, secondIdentity.NodeId);
            }
        }

        [Fact]
        public void Test_SignatureAndVerification_Succeeds()
        {
            using var identity = NodeIdentity.LoadOrCreate();
            
            byte[] payload = Encoding.UTF8.GetBytes("WoldVirtual Metaverse Handshake 2026");
            byte[] signature = identity.Sign(payload);

            Assert.NotNull(signature);
            Assert.True(signature.Length > 0);

            bool isValid = identity.Verify(payload, signature);
            Assert.True(isValid);

            byte[] badPayload = Encoding.UTF8.GetBytes("WoldVirtual Metaverse Handshake 2027");
            bool isBadValid = identity.Verify(badPayload, signature);
            Assert.False(isBadValid);
        }

        [Fact]
        public void Test_MetaMaskValidator_ValidatesSimulatedSignature()
        {
            string wallet = "0x9826a7C841E34b46c9A4B1b7c1264E3bF6b72aEc";
            string message = "WoldVirtual Login Request";
            string signature = "0x_simulated_signature_abc123";

            bool isValid = MetaMaskValidator.VerifySignature(wallet, message, signature, allowSimulation: true);
            Assert.True(isValid);

            bool isRealRejected = MetaMaskValidator.VerifySignature(wallet, message, signature, allowSimulation: false);
            Assert.False(isRealRejected);
        }

        [Fact]
        public void Test_PeerSyncService_DirectoryTraversalPreventionRules()
        {
            const string pattern = "^[a-fA-F0-9]{64}$|^[a-zA-Z0-9_\\-]+$";

            Assert.DoesNotMatch(pattern, "../../escape");
            Assert.DoesNotMatch(pattern, "..\\escape");
            Assert.DoesNotMatch(pattern, "peer/escape");
            Assert.DoesNotMatch(pattern, "peer\\escape");
            Assert.Matches(pattern, "validPeerId");
            Assert.Matches(pattern, "did_wv_node_123");
            Assert.Matches(pattern, "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f61234"); // 64 chars hex
        }

        [Fact]
        public void Test_BindWallet_PersistsAndReturnsBindingProof()
        {
            using var identity = NodeIdentity.LoadOrCreate();
            string wallet = "0x9826a7C841E34b46c9A4B1b7c1264E3bF6b72aEc";
            string signature = "0x_simulated_signature_binding";

            bool bound = identity.BindWallet(wallet, signature);
            Assert.True(bound);
            Assert.Equal(wallet, identity.WalletAddress);

            var proof = identity.GetBindingProof();
            Assert.Equal(wallet, proof.WalletAddress);
            Assert.False(string.IsNullOrEmpty(proof.NodePublicKeyHex));
            Assert.False(string.IsNullOrEmpty(proof.SignatureHex));
        }

        [Fact]
        public void Test_NetworkTelemetry_CountsTrafficAndSecurityEvents()
        {
            var telemetry = NetworkTelemetryService.Instance;
            telemetry.Reset();

            telemetry.RecordPacketSent(100);
            telemetry.RecordPacketReceived(250);
            telemetry.RecordSignatureRejected();
            telemetry.RecordInjectionAttempt();
            telemetry.RecordReconnection();
            telemetry.RecordPeerSeen("peerAlpha");
            telemetry.RecordPeerSeen("peerBeta");

            var snapshot = telemetry.GetSnapshot();

            Assert.Equal(1, snapshot.PacketsSent);
            Assert.Equal(1, snapshot.PacketsReceived);
            Assert.Equal(100, snapshot.BytesSent);
            Assert.Equal(250, snapshot.BytesReceived);
            Assert.Equal(1, snapshot.SignaturesRejected);
            Assert.Equal(1, snapshot.InjectionAttempts);
            Assert.Equal(1, snapshot.Reconnections);
            Assert.Equal(2, snapshot.ActivePeers);

            telemetry.RecordPeerExpired("peerAlpha");
            Assert.Equal(1, telemetry.GetSnapshot().ActivePeers);
            Assert.Equal(1, telemetry.GetSnapshot().PeersExpired);

            telemetry.Reset();
            Assert.Equal(0, telemetry.GetSnapshot().PacketsReceived);
        }
    }
}
