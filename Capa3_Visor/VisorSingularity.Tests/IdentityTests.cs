using System;
using System.Text;
using Xunit;
using VisorSingularity.Identity;
using VisorSingularity.Services;

namespace VisorSingularity.Tests
{
    public class IdentityTests
    {
        [Fact]
        public void TestNodeIdentityCreationAndSelfSignature()
        {
            // Load or create a node identity
            using var identity = NodeIdentity.LoadOrCreate();
            
            Assert.NotNull(identity.NodeId);
            Assert.NotEmpty(identity.NodeId);
            Assert.StartsWith("did:wv:node:", identity.DID, StringComparison.Ordinal);
            Assert.NotNull(identity.PublicKey);
            Assert.NotEmpty(identity.PublicKey);

            // Test signing and verification
            byte[] data = Encoding.UTF8.GetBytes("Hello WoldVirtual P2P 3D!");
            byte[] signature = identity.Sign(data);
            
            Assert.NotNull(signature);
            Assert.NotEmpty(signature);
            
            bool isValid = identity.Verify(data, signature);
            Assert.True(isValid);

            // Verify with altered data
            byte[] alteredData = Encoding.UTF8.GetBytes("Hello WoldVirtual P2P 3D?!");
            bool isAlteredValid = identity.Verify(alteredData, signature);
            Assert.False(isAlteredValid);
        }

        [Fact]
        public void TestWalletBindingAndValidation()
        {
            using var identity = NodeIdentity.LoadOrCreate();
            
            // Try invalid arguments
            Assert.False(identity.BindWallet("", ""));
            Assert.False(identity.BindWallet("0x123", ""));

            // Bind using a simulated signature (allowSimulated = true)
            string testWallet = "0x9826a7C841E34b9826a7C841E34b9826a7C841E3";
            string simulatedSig = "0x_simulated_signature_123456";
            
            bool bindOk = identity.BindWallet(testWallet, simulatedSig, allowSimulated: true);
            Assert.True(bindOk);
            Assert.Equal(testWallet.ToUpperInvariant(), identity.WalletAddress);

            // Generate binding proof
            var proof = identity.GetBindingProof();
            Assert.NotNull(proof);
            Assert.Equal(testWallet.ToUpperInvariant(), proof.WalletAddress);
            Assert.Equal(Convert.ToHexString(identity.PublicKey).ToLowerInvariant(), proof.NodePublicKeyHex);
            Assert.Equal(simulatedSig, proof.SignatureHex);
        }

        [Fact]
        public void TestMetaMaskValidatorSimulatedSignature()
        {
            string signature = "0x_simulated_signature_abcde";
            Assert.True(MetaMaskValidator.IsSimulatedSignature(signature));
            Assert.False(MetaMaskValidator.IsSimulatedSignature("0x_real_signature_looks_like_this"));
            Assert.False(MetaMaskValidator.IsSimulatedSignature(""));

            Assert.True(MetaMaskValidator.VerifySignature("0xAddress", "Some Message", signature, allowSimulation: true));
            Assert.False(MetaMaskValidator.VerifySignature("0xAddress", "Some Message", signature, allowSimulation: false));
        }
    }
}
