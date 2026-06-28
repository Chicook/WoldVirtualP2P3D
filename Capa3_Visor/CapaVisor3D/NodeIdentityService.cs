using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace VisorSingularity
{
    internal sealed class NodeIdentity
    {
        public required string Did { get; init; }
        public required string PeerId { get; init; }
        public required string PublicKeyHex { get; init; }
        public required byte[] PrivateKeyPkcs8 { get; init; }
        public ulong Seq { get; set; }
    }

    internal static class NodeIdentityService
    {
        private static readonly object Gate = new();
        private static NodeIdentity? _cached;

        private static readonly byte[] Entropy = Encoding.UTF8.GetBytes("WCVcoinMTB|WoldVirtualP2P|NodeIdentity|v1");

        private static readonly string IdentityDir =
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "WoldVirtualP2P", "session");

        private static readonly string IdentityPath = Path.Combine(IdentityDir, "identity.json");

        public static NodeIdentity GetOrCreate()
        {
            lock (Gate)
            {
                if (_cached != null) return _cached;

                if (TryLoad(out var loaded))
                {
                    _cached = loaded;
                    return loaded;
                }

                var created = CreateNew();
                Persist(created);
                _cached = created;
                return created;
            }
        }

        public static void PersistSeq(ulong seq)
        {
            lock (Gate)
            {
                if (_cached == null) _cached = GetOrCreate();
                _cached.Seq = seq;
                Persist(_cached);
            }
        }

        private static bool TryLoad(out NodeIdentity identity)
        {
            identity = null!;
            try
            {
                if (!File.Exists(IdentityPath)) return false;
                string json = File.ReadAllText(IdentityPath, Encoding.UTF8);
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                string did = root.TryGetProperty("did", out var didEl) ? didEl.GetString() ?? "" : "";
                string peerId = root.TryGetProperty("peerId", out var pidEl) ? pidEl.GetString() ?? "" : "";
                string pub = root.TryGetProperty("pub", out var pubEl) ? pubEl.GetString() ?? "" : "";
                string encPriv = root.TryGetProperty("encPriv", out var encEl) ? encEl.GetString() ?? "" : "";
                ulong seq = 0;
                if (root.TryGetProperty("seq", out var seqEl) && seqEl.ValueKind == JsonValueKind.Number)
                    _ = seqEl.TryGetUInt64(out seq);

                if (string.IsNullOrWhiteSpace(did) ||
                    string.IsNullOrWhiteSpace(peerId) ||
                    string.IsNullOrWhiteSpace(pub) ||
                    string.IsNullOrWhiteSpace(encPriv))
                    return false;

                if (!PeerSchema.TryGetPeerIdFromDid(did, out string expectedPeerId) || expectedPeerId != peerId)
                    return false;

                byte[] protectedPkcs8 = Convert.FromBase64String(encPriv);
                byte[] pkcs8 = ProtectedData.Unprotect(protectedPkcs8, Entropy, DataProtectionScope.CurrentUser);

                identity = new NodeIdentity
                {
                    Did = did,
                    PeerId = peerId,
                    PublicKeyHex = pub,
                    PrivateKeyPkcs8 = pkcs8,
                    Seq = seq
                };
                return true;
            }
            catch
            {
                return false;
            }
        }

        private static NodeIdentity CreateNew()
        {
            using var ecdsa = CreateSecp256k1();
            ECParameters p = ecdsa.ExportParameters(true);

            string publicKeyHex = ToUncompressedPublicKeyHex(p);
            string did = DeriveDidFromPublicKey(p);
            _ = PeerSchema.TryGetPeerIdFromDid(did, out string peerId);

            byte[] pkcs8 = ecdsa.ExportPkcs8PrivateKey();

            return new NodeIdentity
            {
                Did = did,
                PeerId = peerId,
                PublicKeyHex = publicKeyHex,
                PrivateKeyPkcs8 = pkcs8,
                Seq = 0
            };
        }

        private static void Persist(NodeIdentity identity)
        {
            Directory.CreateDirectory(IdentityDir);

            byte[] protectedPkcs8 = ProtectedData.Protect(identity.PrivateKeyPkcs8, Entropy, DataProtectionScope.CurrentUser);

            var payload = new
            {
                did = identity.Did,
                peerId = identity.PeerId,
                pub = identity.PublicKeyHex,
                encPriv = Convert.ToBase64String(protectedPkcs8),
                seq = identity.Seq,
                updatedAt = DateTimeOffset.UtcNow.ToString("O")
            };

            string json = JsonSerializer.Serialize(payload);
            File.WriteAllText(IdentityPath, json, Encoding.UTF8);
        }

        public static ECDsa CreateEcdsaFromIdentity(NodeIdentity identity)
        {
            var ecdsa = CreateSecp256k1();
            ecdsa.ImportPkcs8PrivateKey(identity.PrivateKeyPkcs8, out _);
            return ecdsa;
        }

        public static ECDsa CreateEcdsaFromUncompressedPublicKeyHex(string publicKeyHex)
        {
            if (string.IsNullOrWhiteSpace(publicKeyHex) || publicKeyHex.Length != 130 || !publicKeyHex.StartsWith("04", StringComparison.Ordinal))
                throw new ArgumentException("Clave pública inválida.", nameof(publicKeyHex));

            byte[] pub = Convert.FromHexString(publicKeyHex);
            byte[] x = new byte[32];
            byte[] y = new byte[32];
            Buffer.BlockCopy(pub, 1, x, 0, 32);
            Buffer.BlockCopy(pub, 33, y, 0, 32);

            var parameters = new ECParameters
            {
                Curve = CreateSecp256k1Curve(),
                Q = new ECPoint { X = x, Y = y }
            };

            return ECDsa.Create(parameters);
        }

        private static ECDsa CreateSecp256k1()
        {
            var curve = CreateSecp256k1Curve();
            return ECDsa.Create(curve);
        }

        private static ECCurve CreateSecp256k1Curve()
        {
            try
            {
                return ECCurve.CreateFromFriendlyName("secP256k1");
            }
            catch
            {
                try
                {
                    return ECCurve.CreateFromFriendlyName("secp256k1");
                }
                catch
                {
                    return ECCurve.NamedCurves.nistP256;
                }
            }
        }

        private static string DeriveDidFromPublicKey(ECParameters p)
        {
            byte[] xy = new byte[64];
            Buffer.BlockCopy(p.Q.X!, 0, xy, 0, 32);
            Buffer.BlockCopy(p.Q.Y!, 0, xy, 32, 32);

            byte[] hash = Keccak256.ComputeHash(xy);
            Span<byte> addr = hash.AsSpan(hash.Length - 20, 20);
            string hex = Convert.ToHexString(addr).ToLowerInvariant();
            return "did:wcv:0x" + hex;
        }

        private static string ToUncompressedPublicKeyHex(ECParameters p)
        {
            byte[] pub = new byte[65];
            pub[0] = 0x04;
            Buffer.BlockCopy(p.Q.X!, 0, pub, 1, 32);
            Buffer.BlockCopy(p.Q.Y!, 0, pub, 33, 32);
            return Convert.ToHexString(pub).ToLowerInvariant();
        }
    }
}
