// File: WoldVirtualP2P3D/Core/Security/ProofOfPresence.cs
using System;
using System.Collections.Concurrent;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace WoldVirtual.Security
{
    // LuciaContext removed on purpose: remote, unsigned text must never reach the LLM.
    public record PresenceClaim(
        string IssuerPeerId,
        string WitnessPeerId,
        string IslandChunk,
        double PosX, double PosY, double PosZ,
        long TimestampUnix,
        string Nonce);

    public record PresenceProof(
        PresenceClaim Claim,
        string SignatureIssuer,
        string SignatureWitness,
        string IssuerPublicKey,
        string WitnessPublicKey,
        string Cid,
        string LuciaSummary);

    public sealed class NonceCache
    {
        private readonly ConcurrentDictionary<string, long> _seen = new();
        private readonly long _ttl;
        public NonceCache(int ttlSeconds) { _ttl = ttlSeconds; }

        // true = new nonce, false = replay
        public bool TryAdd(string key)
        {
            var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            foreach (var kv in _seen)
                if (now - kv.Value > _ttl) _seen.TryRemove(kv.Key, out _);
            return _seen.TryAdd(key, now);
        }
    }

    public static class ProofOfPresence
    {
        private static string F(double v) => v.ToString("F2", CultureInfo.InvariantCulture);

        // Fixed byte layout: identical on every platform/language.
        public static string Canonical(PresenceClaim c) => string.Join("|",
            "WVP1", c.IssuerPeerId, c.WitnessPeerId, c.IslandChunk,
            F(c.PosX), F(c.PosY), F(c.PosZ), c.TimestampUnix, c.Nonce);

        public static string ClaimId(PresenceClaim c)
        {
            var pair = string.CompareOrdinal(c.IssuerPeerId, c.WitnessPeerId) < 0
                ? c.IssuerPeerId + "+" + c.WitnessPeerId
                : c.WitnessPeerId + "+" + c.IssuerPeerId;
            return pair + "@" + (c.TimestampUnix / 60); // one proof per pair per minute
        }

        public static PresenceClaim CreateClaim(string issuerId, string witnessId, string chunk,
                                                float x, float y, float z)
        {
            return new PresenceClaim(
                issuerId, witnessId, chunk,
                Math.Round((double)x, 2), Math.Round((double)y, 2), Math.Round((double)z, 2),
                DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
                Convert.ToHexString(RandomNumberGenerator.GetBytes(16)).ToLowerInvariant());
        }

        public static string SignClaim(PresenceClaim claim, ECDsa key) =>
            Convert.ToBase64String(key.SignData(Encoding.UTF8.GetBytes(Canonical(claim)), HashAlgorithmName.SHA256));

        // Signature check only (no clock): usable on old proofs too.
        public static bool VerifySignature(PresenceClaim claim, string sigB64, string publicKeyB64)
        {
            try
            {
                using var pub = ECDsa.Create();
                pub.ImportSubjectPublicKeyInfo(Convert.FromBase64String(publicKeyB64), out _);
                return pub.VerifyData(Encoding.UTF8.GetBytes(Canonical(claim)),
                                      Convert.FromBase64String(sigB64), HashAlgorithmName.SHA256);
            }
            catch { return false; }
        }

        public static bool IsFresh(PresenceClaim c, int maxSkewSec = 30) =>
            Math.Abs(DateTimeOffset.UtcNow.ToUnixTimeSeconds() - c.TimestampUnix) <= maxSkewSec;

        // Witness side: validate BEFORE signing. Returns (sig, pubKey) or null.
        public static (string Sig, string PubKey)? TryWitnessSign(
            PresenceClaim claim, ECDsa myKey, string myPeerId,
            float myX, float myY, float myZ, NonceCache nonces, double maxDistance = 15.0)
        {
            if (claim.WitnessPeerId != myPeerId) return null;
            if (claim.IssuerPeerId == myPeerId) return null;
            if (!IsFresh(claim)) return null;

            var dx = claim.PosX - myX; var dy = claim.PosY - myY; var dz = claim.PosZ - myZ;
            if (Math.Sqrt(dx * dx + dy * dy + dz * dz) > maxDistance) return null;

            if (!nonces.TryAdd(claim.IssuerPeerId + ":" + claim.Nonce)) return null;

            return (SignClaim(claim, myKey), SecurityManager.GetPublicKeyB64(myKey));
        }
    }
}
