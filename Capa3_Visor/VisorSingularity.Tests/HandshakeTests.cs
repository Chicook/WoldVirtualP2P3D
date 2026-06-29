using System;
using System.Text.Json;
using Xunit;
using VisorSingularity.Identity;
using VisorSingularity.Services;

namespace VisorSingularity.Tests
{
    public class HandshakeTests
    {
        [Fact]
        public void Handshake_BuildAndValidateRequest_Succeeds()
        {
            using var identity = NodeIdentity.LoadOrCreate();
            string wallet = "0x9826a7C841E34b46c9A4B1b7c1264E3bF6b72aEc";
            string signature = "0x_simulated_signature_handshake";

            string json = HandshakeProtocol.BuildRequest(identity, wallet, signature);
            var result = HandshakeProtocol.Validate(json, allowSimulatedWalletSignature: true);

            Assert.True(result.IsValid, result.Reason);
            Assert.NotNull(result.Envelope);
            Assert.Equal(identity.NodeId, result.Envelope!.SenderId);
            Assert.Equal(wallet, result.Envelope.WalletAddress);
            Assert.Contains("island_sync", result.Envelope.Capabilities);
        }

        [Fact]
        public void Handshake_RejectsTamperedSenderId()
        {
            using var identity = NodeIdentity.LoadOrCreate();
            string json = HandshakeProtocol.BuildRequest(
                identity,
                "0x9826a7C841E34b46c9A4B1b7c1264E3bF6b72aEc",
                "0x_simulated_signature_handshake");

            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement.Clone();
            var map = JsonSerializer.Deserialize<Dictionary<string, object?>>(root.GetRawText())!;
            map["sender_id"] = "attackerNode";
            string tampered = JsonSerializer.Serialize(map);

            var result = HandshakeProtocol.Validate(tampered, allowSimulatedWalletSignature: true);

            Assert.False(result.IsValid);
            Assert.Equal("sender id does not match public key", result.Reason);
        }

        [Fact]
        public void Handshake_RejectsExpiredTimestamp()
        {
            using var identity = NodeIdentity.LoadOrCreate();
            string json = HandshakeProtocol.BuildRequest(
                identity,
                "0x9826a7C841E34b46c9A4B1b7c1264E3bF6b72aEc",
                "0x_simulated_signature_handshake");

            var result = HandshakeProtocol.Validate(
                json,
                allowSimulatedWalletSignature: true,
                nowUtc: DateTimeOffset.UtcNow.AddMinutes(5));

            Assert.False(result.IsValid);
            Assert.Equal("handshake timestamp outside clock skew window", result.Reason);
        }

        [Fact]
        public void Handshake_RejectsRealWalletWhenSimulationDisabled()
        {
            using var identity = NodeIdentity.LoadOrCreate();
            string json = HandshakeProtocol.BuildRequest(
                identity,
                "0x9826a7C841E34b46c9A4B1b7c1264E3bF6b72aEc",
                "0x_simulated_signature_handshake");

            var result = HandshakeProtocol.Validate(json, allowSimulatedWalletSignature: false);

            Assert.False(result.IsValid);
            Assert.Equal("invalid wallet binding proof", result.Reason);
        }

        [Fact]
        public void Handshake_WalletBindingMessage_IsDeterministic()
        {
            string message = HandshakeProtocol.BuildWalletBindingMessage("abc123", 42);
            Assert.Equal("WoldVirtual Node Identity Binding:abc123:42", message);
        }
    }
}
