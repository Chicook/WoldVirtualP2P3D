// File: WoldVirtualP2P3D/Core/P2P/PresenceLedger.cs
// Godot Node (C# class name must match file name, and be partial).
// Assumes your existing: IpfsManager.PinJsonAsync(path, json) -> Task<string> (CID)
//                        P2PWebNode.BroadcastAsync(topic, json)
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using WoldVirtual.AI;
using WoldVirtual.Security;

namespace WoldVirtual.P2P
{
    public partial class PresenceLedger : Node
    {
        private const long WeekSec = 7 * 24 * 3600;

        private readonly ConcurrentDictionary<string, PresenceProof> _proofs = new();
        private readonly ConcurrentDictionary<string, long> _claimIds = new();
        private readonly NonceCache _nonces = new(600);

        private IpfsManager? _ipfs;
        private P2PWebNode? _p2p;
        private LucIAPresenceAgent? _agent;

        // Godot Nodes can't take constructor args: call this after creating the node.
        public void Init(IpfsManager ipfs, P2PWebNode p2p) { _ipfs = ipfs; _p2p = p2p; }
        public void AttachLucIA(LucIAPresenceAgent agent) => _agent = agent;

        private static bool VerifyBoth(PresenceProof p)
        {
            var c = p.Claim;
            return SecurityManager.PeerIdFromPublicKey(p.IssuerPublicKey) == c.IssuerPeerId
                && SecurityManager.PeerIdFromPublicKey(p.WitnessPublicKey) == c.WitnessPeerId
                && ProofOfPresence.VerifySignature(c, p.SignatureIssuer, p.IssuerPublicKey)
                && ProofOfPresence.VerifySignature(c, p.SignatureWitness, p.WitnessPublicKey);
        }

        // Local creation. Returns null if anything fails validation.
        public async Task<PresenceProof?> CreateAndPinProofAsync(
            PresenceClaim claim, string mySig, string myPub, string witnessSig, string witnessPub)
        {
            if (_ipfs == null || _p2p == null) return null;

            var draft = new PresenceProof(claim, mySig, witnessSig, myPub, witnessPub, "", "");
            if (!ProofOfPresence.IsFresh(claim, 60)) return null;
            if (!VerifyBoth(draft)) return null;
            if (!_nonces.TryAdd(claim.IssuerPeerId + ":" + claim.Nonce)) return null;          // replay
            if (!_claimIds.TryAdd(ProofOfPresence.ClaimId(claim), claim.TimestampUnix)) return null; // duplicate

            Prune();

            string summary = "";
            if (_agent != null)
            {
                try { summary = await _agent.AnalyzeEncounterAsync(claim); } catch { }
            }

            var withSummary = draft with { LuciaSummary = summary };
            var json = JsonSerializer.Serialize(withSummary);
            var cid = await _ipfs.PinJsonAsync($"presence/{claim.IssuerPeerId}/{claim.TimestampUnix}.json", json);

            var final = withSummary with { Cid = cid };
            _proofs[cid] = final;

            await _p2p.BroadcastAsync("presence/new", JsonSerializer.Serialize(final));
            AppendLog(JsonSerializer.Serialize(final));

            if (_agent != null) { try { await _agent.OnPresenceProofAsync(final); } catch { } }
            return final;
        }

        // Proofs received from other peers: verify before storing.
        public bool TryAcceptRemote(PresenceProof p)
        {
            if (p.Claim == null || string.IsNullOrEmpty(p.Cid)) return false;
            if (!VerifyBoth(p)) return false;
            if (DateTimeOffset.UtcNow.ToUnixTimeSeconds() - p.Claim.TimestampUnix > WeekSec) return false;
            if (!_claimIds.TryAdd(ProofOfPresence.ClaimId(p.Claim), p.Claim.TimestampUnix)) return false;
            // LuciaSummary from remote is untrusted display text only.
            _proofs[p.Cid] = p with { LuciaSummary = "" };
            return true;
        }

        private static void AppendLog(string line)
        {
            try
            {
                var path = ProjectSettings.GlobalizePath("user://presence.jsonl");
                System.IO.File.AppendAllText(path, line + "\n");
            }
            catch { }
        }

        private void Prune()
        {
            var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            foreach (var kv in _proofs)
                if (now - kv.Value.Claim.TimestampUnix > WeekSec) _proofs.TryRemove(kv.Key, out _);
            foreach (var kv in _claimIds)
                if (now - kv.Value > WeekSec) _claimIds.TryRemove(kv.Key, out _);
        }

        public bool HasMet(string a, string b, int withinMinutes = 60)
        {
            var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            foreach (var p in _proofs.Values)
            {
                var c = p.Claim;
                bool pair = (c.IssuerPeerId == a && c.WitnessPeerId == b) ||
                            (c.IssuerPeerId == b && c.WitnessPeerId == a);
                if (pair && now - c.TimestampUnix < withinMinutes * 60L) return true;
            }
            return false;
        }

        public int GetUniqueEncountersLastWeek(string myPeerId)
        {
            var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            var peers = new HashSet<string>();
            foreach (var p in _proofs.Values)
            {
                if (now - p.Claim.TimestampUnix > WeekSec) continue;
                if (p.Claim.IssuerPeerId == myPeerId) peers.Add(p.Claim.WitnessPeerId);
                if (p.Claim.WitnessPeerId == myPeerId) peers.Add(p.Claim.IssuerPeerId);
            }
            return peers.Count;
        }

        public int CountEncountersInChunk(string chunk, int withinMinutes)
        {
            var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            int n = 0;
            foreach (var p in _proofs.Values)
                if (p.Claim.IslandChunk == chunk && now - p.Claim.TimestampUnix < withinMinutes * 60L) n++;
            return n;
        }
    }
}
