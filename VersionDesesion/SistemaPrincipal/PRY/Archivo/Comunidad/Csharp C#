// File: WoldVirtualP2P3D/Godot/Scripts/PresenceArea.cs
using Godot;
using WoldVirtual.Security;
using WoldVirtual.P2P;

public partial class PresenceArea : Area3D
{
    [Export] public NodePath PresenceLedgerPath;
    private PresenceLedger ledger;
    private string myPeerId;
    private System.Security.Cryptography.ECDsa myKeys;

    public override void _Ready()
    {
        myPeerId = P2PWebNode.PeerId;
        myKeys = SecurityManager.GetOrCreateECDSA();
        ledger = GetNode<PresenceLedger>(PresenceLedgerPath);
        BodyEntered += OnBodyEntered;
    }

    private async void OnBodyEntered(Node3D body)
    {
        if (!body.HasMethod("get_peer_id")) return;
        var witnessId = (string)body.Call("get_peer_id");
        if (witnessId == myPeerId) return;
        if (ledger.HasMet(myPeerId, witnessId, 2)) return;

        var chunk = GetCurrentChunk();
        var claim = ProofOfPresence.CreateClaim(myPeerId, witnessId, chunk, GlobalPosition);
        var mySig = ProofOfPresence.SignClaim(claim, myKeys);
        var witnessSig = await P2PWebNode.RequestSignature(witnessId, claim);

        if (!string.IsNullOrEmpty(witnessSig))
        {
            var proof = await ledger.CreateAndPinProofAsync(claim, mySig, witnessSig);
            GD.Print($"[PRESENCE] Proof: {proof.Cid}");
            GetNode("/root/LucIA").Call("OnPresence", proof);
        }
    }

    private string GetCurrentChunk() => $"embossed_{GlobalPosition.X:F0}_{GlobalPosition.Z:F0}";
}
