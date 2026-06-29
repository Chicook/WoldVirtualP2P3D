using Xunit;
using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using VisorSingularity.Identity;

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
            Assert.StartsWith("did:wv:node:", identity.NodeId);
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
    }
}
