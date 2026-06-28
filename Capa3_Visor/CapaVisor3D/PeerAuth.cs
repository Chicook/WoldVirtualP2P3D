using System;
using System.Collections.Concurrent;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace VisorSingularity
{
    internal static class PeerAuth
    {
        private static readonly ConcurrentDictionary<string, ulong> LastSeqByPeerId = new(StringComparer.Ordinal);

        public static bool TrySignOutgoing(string unsignedPeerJson, NodeIdentity identity, out string signedPeerJson)
        {
            signedPeerJson = string.Empty;

            if (string.IsNullOrWhiteSpace(unsignedPeerJson) || !unsignedPeerJson.TrimStart().StartsWith("{", StringComparison.Ordinal))
                return false;

            if (Encoding.UTF8.GetByteCount(unsignedPeerJson) > PeerSchema.MaxPeerSizeBytes)
                return false;

            try
            {
                using var doc = JsonDocument.Parse(unsignedPeerJson);
                if (doc.RootElement.ValueKind != JsonValueKind.Object) return false;

                using var ms = new System.IO.MemoryStream();
                using (var writer = new Utf8JsonWriter(ms, new JsonWriterOptions { Indented = false }))
                {
                    writer.WriteStartObject();

                    bool hasDid = false;
                    bool hasPub = false;
                    bool hasSeq = false;
                    bool hasTs = false;

                    foreach (var prop in doc.RootElement.EnumerateObject())
                    {
                        if (string.Equals(prop.Name, "sig", StringComparison.Ordinal))
                            continue;

                        if (string.Equals(prop.Name, "did", StringComparison.Ordinal))
                        {
                            hasDid = true;
                            continue;
                        }
                        if (string.Equals(prop.Name, "pub", StringComparison.Ordinal))
                        {
                            hasPub = true;
                            continue;
                        }
                        if (string.Equals(prop.Name, "seq", StringComparison.Ordinal))
                        {
                            hasSeq = true;
                            continue;
                        }
                        if (string.Equals(prop.Name, "ts", StringComparison.Ordinal))
                        {
                            hasTs = true;
                            continue;
                        }

                        writer.WritePropertyName(prop.Name);
                        writer.WriteRawValue(prop.Value.GetRawText(), skipInputValidation: true);
                    }

                    writer.WriteString("did", identity.Did);
                    writer.WriteString("pub", identity.PublicKeyHex);

                    ulong seq = identity.Seq + 1;
                    identity.Seq = seq;
                    NodeIdentityService.PersistSeq(seq);
                    writer.WriteNumber("seq", seq);

                    if (hasTs)
                    {
                        if (doc.RootElement.TryGetProperty("ts", out var tsEl))
                        {
                            writer.WritePropertyName("ts");
                            writer.WriteRawValue(tsEl.GetRawText(), skipInputValidation: true);
                        }
                        else
                        {
                            writer.WriteString("ts", DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture));
                        }
                    }
                    else
                    {
                        writer.WriteString("ts", DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture));
                    }

                    writer.WriteEndObject();
                }

                string unsignedWithIdentity = Encoding.UTF8.GetString(ms.ToArray());
                if (!CanonicalJson.TryRemovePropertyAndCanonicalize(unsignedWithIdentity, "sig", out var canonical))
                    return false;

                byte[] hash = Keccak256.ComputeHash(canonical);

                using var ecdsa = NodeIdentityService.CreateEcdsaFromIdentity(identity);
                byte[] sig = ecdsa.SignHash(hash);

                using var signedDoc = JsonDocument.Parse(unsignedWithIdentity);
                using var finalMs = new System.IO.MemoryStream();
                using (var writer = new Utf8JsonWriter(finalMs, new JsonWriterOptions { Indented = false }))
                {
                    writer.WriteStartObject();
                    foreach (var prop in signedDoc.RootElement.EnumerateObject())
                    {
                        writer.WritePropertyName(prop.Name);
                        writer.WriteRawValue(prop.Value.GetRawText(), skipInputValidation: true);
                    }
                    writer.WriteString("sig", Convert.ToBase64String(sig));
                    writer.WriteEndObject();
                }

                signedPeerJson = Encoding.UTF8.GetString(finalMs.ToArray());
                return true;
            }
            catch (JsonException)
            {
                return false;
            }
            catch
            {
                return false;
            }
        }

        public static bool TryValidateIncoming(string peerJson, string localPeerId, out string remotePeerId)
        {
            remotePeerId = string.Empty;

            if (string.IsNullOrWhiteSpace(peerJson) || !peerJson.TrimStart().StartsWith("{", StringComparison.Ordinal))
                return false;

            if (Encoding.UTF8.GetByteCount(peerJson) > PeerSchema.MaxPeerSizeBytes)
                return false;

            if (!PeerSchema.TryValidate(peerJson, out string extractedPeerId))
                return false;

            if (extractedPeerId == localPeerId)
                return false;

            try
            {
                using var doc = JsonDocument.Parse(peerJson);
                var root = doc.RootElement;

                if (!root.TryGetProperty("did", out var didEl) ||
                    !root.TryGetProperty("pub", out var pubEl) ||
                    !root.TryGetProperty("sig", out var sigEl) ||
                    !root.TryGetProperty("seq", out var seqEl))
                    return false;

                string did = didEl.GetString() ?? "";
                string pub = pubEl.GetString() ?? "";
                string sigB64 = sigEl.GetString() ?? "";
                if (string.IsNullOrWhiteSpace(did) || string.IsNullOrWhiteSpace(pub) || string.IsNullOrWhiteSpace(sigB64))
                    return false;

                if (!seqEl.TryGetUInt64(out ulong seq))
                    return false;

                if (!PeerSchema.TryGetPeerIdFromDid(did, out string expectedPeerId))
                    return false;

                if (!string.Equals(expectedPeerId, extractedPeerId, StringComparison.Ordinal))
                    return false;

                byte[] pubBytes = Convert.FromHexString(pub);
                if (pubBytes.Length != 65 || pubBytes[0] != 0x04)
                    return false;

                byte[] xy = new byte[64];
                Buffer.BlockCopy(pubBytes, 1, xy, 0, 64);
                byte[] addrHash = Keccak256.ComputeHash(xy);
                string addr = Convert.ToHexString(addrHash.AsSpan(addrHash.Length - 20, 20)).ToLowerInvariant();
                string derivedDid = "did:wcv:0x" + addr;
                if (!string.Equals(derivedDid, did, StringComparison.Ordinal))
                    return false;

                if (LastSeqByPeerId.TryGetValue(expectedPeerId, out ulong last) && seq <= last)
                    return false;

                if (!CanonicalJson.TryRemovePropertyAndCanonicalize(peerJson, "sig", out var canonical))
                    return false;

                byte[] hash = Keccak256.ComputeHash(canonical);
                byte[] sig = Convert.FromBase64String(sigB64);

                using var ecdsa = NodeIdentityService.CreateEcdsaFromUncompressedPublicKeyHex(pub);
                if (!ecdsa.VerifyHash(hash, sig))
                    return false;

                LastSeqByPeerId[expectedPeerId] = seq;
                remotePeerId = expectedPeerId;
                return true;
            }
            catch (FormatException)
            {
                return false;
            }
            catch (CryptographicException)
            {
                return false;
            }
            catch (JsonException)
            {
                return false;
            }
        }
    }
}
