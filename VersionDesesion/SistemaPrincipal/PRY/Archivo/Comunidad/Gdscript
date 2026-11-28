# File: WoldVirtualP2P3D/Godot/Scripts/PresenceArea.gd
extends Area3D

@export var presence_ledger_path: NodePath
var ledger
var myPeerId: String
var myKeys

func _ready():
    myPeerId = P2PWebNode.PeerId
    myKeys = SecurityManager.GetOrCreateECDSA()
    ledger = get_node(presence_ledger_path)
    body_entered.connect(_on_body_entered)

func _on_body_entered(body):
    if not body.has_method("get_peer_id"): return
    var witnessId = body.get_peer_id()
    if witnessId == myPeerId: return
    if ledger.HasMet(myPeerId, witnessId, 2): return
    var chunk = get_current_chunk()
    var claim = ProofOfPresence.CreateClaim(myPeerId, witnessId, chunk, global_position)
    var mySig = ProofOfPresence.SignClaim(claim, myKeys)
    var witnessSig = await P2PWebNode.RequestSignature(witnessId, claim)
    if witnessSig != "":
        var proof = await ledger.CreateAndPinProofAsync(claim, mySig, witnessSig)
        print("[PRESENCE] Proof: ", proof.Cid)
        get_node("/root/LucIA").OnPresence(proof)
