// File: WoldVirtualP2P3D/Godot/Scripts/PresenceArea.cs
// Your P2PWebNode.RequestSignature must now return the witness signature AND public key:
//   public static Task<(string Sig, string PubKey)?> RequestSignature(string witnessId, PresenceClaim claim)
// On the witness side, call ProofOfPresence.TryWitnessSign(...) when a request arrives.
using System;
using System.Security.Cryptography;
using Godot;
using WoldVirtual.P2P;
using WoldVirtual.Security;

public partial class PresenceArea : Area3D
{
    [Export] public NodePath PresenceLedgerPath = new NodePath();

    private PresenceLedger? _ledger;
    private ECDsa? _keys;
    private string _myPeerId = "";
    private string _myPub = "";

    public override void _Ready()
    {
        _keys = SecurityManager.GetOrCreateECDSA();
        _myPeerId = SecurityManager.GetPeerId(_keys);
        _myPub = SecurityManager.GetPublicKeyB64(_keys);

        if (!PresenceLedgerPath.IsEmpty && HasNode(PresenceLedgerPath))
            _ledger = GetNode<PresenceLedger>(PresenceLedgerPath);

        BodyEntered += OnBodyEntered;
    }

    public override void _ExitTree()
    {
        BodyEntered -= OnBodyEntered;
        _keys?.Dispose();
    }

    private async void OnBodyEntered(Node3D body)
    {
        try
        {
            if (_ledger == null || _keys == null) return;
            if (!body.HasMethod("get_peer_id")) return;

            var witnessId = (string)body.Call("get_peer_id");
            if (string.IsNullOrEmpty(witnessId) || witnessId == _myPeerId) return;
            if (_ledger.HasMet(_myPeerId, witnessId, 2)) return;

            var pos = body.GlobalPosition;
            var chunk = $"embossed_{Mathf.RoundToInt(pos.X)}_{Mathf.RoundToInt(pos.Z)}";

            var claim = ProofOfPresence.CreateClaim(_myPeerId, witnessId, chunk, pos.X, pos.Y, pos.Z);
            var mySig = ProofOfPresence.SignClaim(claim, _keys);

            var w = await P2PWebNode.RequestSignature(witnessId, claim);
            if (w == null || string.IsNullOrEmpty(w.Value.Sig)) return;

            var proof = await _ledger.CreateAndPinProofAsync(claim, mySig, _myPub, w.Value.Sig, w.Value.PubKey);
            if (proof != null)
                GD.Print($"[WOLD-PRESENCE] {proof.Cid} | {proof.LuciaSummary}");
        }
        catch (Exception e)
        {
            GD.PushError($"[WOLD-PRESENCE] {e.Message}");
        }
    }
}
