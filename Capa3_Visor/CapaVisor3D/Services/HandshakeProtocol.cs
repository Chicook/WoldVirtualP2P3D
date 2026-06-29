using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using VisorSingularity.Identity;

namespace VisorSingularity.Services
{
    public sealed record WalletBindingProof(
        string WalletAddress,
        string NodePublicKeyHex,
        long Timestamp,
        string SignatureHex);

    public sealed record HandshakeEnvelope(
        string ProtocolVersion,
        string SenderId,
        string WalletAddress,
        long Timestamp,
        string NodeSignature,
        WalletBindingProof BindingProof,
        IReadOnlyList<string> Capabilities);

    public sealed record HandshakeValidationResult(
        bool IsValid,
        string Reason,
        HandshakeEnvelope? Envelope);

    /// <summary>
    /// Formaliza el handshake P2P descrito en el plan DevAntigravityIA:
    /// versionado de protocolo, identidad DID, firma de nodo, prueba de wallet y
    /// ventana anti-replay por timestamp. El transporte queda fuera de este
    /// servicio para reutilizarlo desde UDP, TCP o WebSocket.
    /// </summary>
    public static class HandshakeProtocol
    {
        public const string CurrentProtocolVersion = "1.0";
        public const int MaxClockSkewSeconds = 30;

        private static readonly string[] DefaultCapabilities =
        {
            "chat",
            "avatar_sync",
            "island_sync"
        };

        private static readonly JsonSerializerOptions JsonOptions = new()
        {
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
        };

        public static string BuildRequest(
            NodeIdentity identity,
            string walletAddress,
            string walletSignature,
            string[]? capabilities = null)
        {
            ArgumentNullException.ThrowIfNull(identity);
            return BuildEnvelope(identity, walletAddress, walletSignature, capabilities);
        }

        public static string BuildResponse(
            NodeIdentity identity,
            string walletAddress,
            string walletSignature,
            string[]? capabilities = null)
        {
            ArgumentNullException.ThrowIfNull(identity);
            return BuildEnvelope(identity, walletAddress, walletSignature, capabilities);
        }

        public static HandshakeValidationResult Validate(
            string json,
            bool allowSimulatedWalletSignature = true,
            DateTimeOffset? nowUtc = null)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                return Invalid("empty handshake");
            }

            HandshakeEnvelope? envelope;
            try
            {
                envelope = JsonSerializer.Deserialize<HandshakeEnvelope>(json, JsonOptions);
            }
            catch (JsonException)
            {
                return Invalid("invalid handshake json");
            }

            if (envelope == null)
            {
                return Invalid("missing handshake envelope");
            }
            if (envelope.ProtocolVersion != CurrentProtocolVersion)
            {
                return Invalid("unsupported protocol version");
            }
            if (!IsSafeNodeId(envelope.SenderId))
            {
                return Invalid("invalid sender id");
            }
            if (string.IsNullOrEmpty(envelope.WalletAddress))
            {
                return Invalid("missing wallet address");
            }
            if (envelope.BindingProof == null)
            {
                return Invalid("missing binding proof");
            }

            long now = (nowUtc ?? DateTimeOffset.UtcNow).ToUnixTimeSeconds();
            if (Math.Abs(now - envelope.Timestamp) > MaxClockSkewSeconds)
            {
                return Invalid("handshake timestamp outside clock skew window");
            }
            if (Math.Abs(now - envelope.BindingProof.Timestamp) > MaxClockSkewSeconds)
            {
                return Invalid("binding timestamp outside clock skew window");
            }

            byte[] publicKey;
            byte[] signature;
            try
            {
                publicKey = Convert.FromHexString(envelope.BindingProof.NodePublicKeyHex);
                signature = Convert.FromHexString(TrimHexPrefix(envelope.NodeSignature));
            }
            catch (FormatException)
            {
                return Invalid("invalid hex fields");
            }

            string computedNodeId = ComputeNodeId(publicKey);
            if (!string.Equals(computedNodeId, envelope.SenderId, StringComparison.Ordinal))
            {
                return Invalid("sender id does not match public key");
            }

            string payload = BuildNodeSignaturePayload(
                envelope.ProtocolVersion,
                envelope.SenderId,
                envelope.WalletAddress,
                envelope.Timestamp,
                envelope.BindingProof);

            if (!VerifyNodeSignature(publicKey, Encoding.UTF8.GetBytes(payload), signature))
            {
                return Invalid("invalid node signature");
            }

            string walletMessage = BuildWalletBindingMessage(
                envelope.BindingProof.NodePublicKeyHex,
                envelope.BindingProof.Timestamp);

            bool walletOk = MetaMaskValidator.VerifySignature(
                envelope.WalletAddress,
                walletMessage,
                envelope.BindingProof.SignatureHex,
                allowSimulatedWalletSignature);

            if (!walletOk)
            {
                return Invalid("invalid wallet binding proof");
            }

            return new HandshakeValidationResult(true, "ok", envelope);
        }

        public static string BuildWalletBindingMessage(string nodePublicKeyHex, long timestamp)
        {
            return "WoldVirtual Node Identity Binding:" + nodePublicKeyHex + ":" + timestamp;
        }

        private static string BuildEnvelope(
            NodeIdentity identity,
            string walletAddress,
            string walletSignature,
            string[]? capabilities)
        {
            long timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            string publicKeyHex = Convert.ToHexString(identity.PublicKey).ToLowerInvariant();

            var proof = new WalletBindingProof(
                walletAddress,
                publicKeyHex,
                timestamp,
                walletSignature);

            string payload = BuildNodeSignaturePayload(
                CurrentProtocolVersion,
                identity.NodeId,
                walletAddress,
                timestamp,
                proof);

            string nodeSignature = Convert.ToHexString(
                identity.Sign(Encoding.UTF8.GetBytes(payload))).ToLowerInvariant();

            var envelope = new HandshakeEnvelope(
                CurrentProtocolVersion,
                identity.NodeId,
                walletAddress,
                timestamp,
                nodeSignature,
                proof,
                capabilities ?? DefaultCapabilities);

            return JsonSerializer.Serialize(envelope, JsonOptions);
        }

        private static string BuildNodeSignaturePayload(
            string protocolVersion,
            string senderId,
            string walletAddress,
            long timestamp,
            WalletBindingProof proof)
        {
            return string.Join("|",
                protocolVersion,
                senderId,
                walletAddress,
                timestamp,
                proof.NodePublicKeyHex,
                proof.Timestamp,
                proof.SignatureHex);
        }

        private static bool VerifyNodeSignature(byte[] publicKey, byte[] payload, byte[] signature)
        {
            try
            {
                using var ecdsa = ECDsa.Create();
                ecdsa.ImportSubjectPublicKeyInfo(publicKey, out _);
                return ecdsa.VerifyData(payload, signature, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);
            }
            catch (CryptographicException)
            {
                return false;
            }
        }

        private static string ComputeNodeId(byte[] publicKey)
        {
            byte[] hash = SHA256.HashData(publicKey);
            return Convert.ToHexString(hash).ToLowerInvariant();
        }

        private static bool IsSafeNodeId(string nodeId)
        {
            if (string.IsNullOrEmpty(nodeId)) return false;
            foreach (char c in nodeId)
            {
                bool ok = char.IsAsciiLetterOrDigit(c) || c == '_' || c == '-';
                if (!ok) return false;
            }
            return true;
        }

        private static string TrimHexPrefix(string value)
        {
            return value.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
                ? value[2..]
                : value;
        }

        private static HandshakeValidationResult Invalid(string reason)
        {
            return new HandshakeValidationResult(false, reason, null);
        }
    }
}
