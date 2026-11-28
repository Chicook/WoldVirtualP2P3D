// File: WoldVirtualP2P3D/Core/Security/ProofOfPresence.cs
// RFC-P2P-ZT-PRESENCE v1.0 - Zero-Trust Proof
using System;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace WoldVirtual.Security
{
    public record PresenceClaim(
        string IssuerPeerId,
        string WitnessPeerId,
        string IslandChunk,
        double PosX, double PosY, double PosZ,
        long TimestampUnix,
        string Nonce
    );

    public record PresenceProof(
        PresenceClaim Claim,
        string SignatureIssuer,
        string SignatureWitness,
        string Cid
    );

    public static class ProofOfPresence
    {
        public static string SignClaim(PresenceClaim claim, ECDsa privateKey)
        {
            var json = JsonSerializer.Serialize(claim);
            var data = Encoding.UTF8.GetBytes(json);
            var sig = privateKey.SignData(data, HashAlgorithmName.SHA256);
            return Convert.ToBase64String(sig);
        }

        public static bool VerifyClaim(PresenceClaim claim, string signatureB64, ECDsa publicKey)
        {
            try {
                var json = JsonSerializer.Serialize(claim);
                var data = Encoding.UTF8.GetBytes(json);
                var sig = Convert.FromBase64String(signatureB64);
                return publicKey.VerifyData(data, sig, HashAlgorithmName.SHA256);
            } catch { return false; }
        }

        public static PresenceClaim CreateClaim(string myPeerId, string witnessPeerId, string chunk, Godot.Vector3 pos)
        {
            return new PresenceClaim(
                myPeerId,
                witnessPeerId,
                chunk,
                Math.Round(pos.X, 2), Math.Round(pos.Y, 2), Math.Round(pos.Z, 2),
                DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
                Guid.NewGuid().ToString("N")[..8]
            );
        }
    }
}
