// File: WoldVirtualP2P3D/Godot/Scripts/CommerceShopCrypto.cs
// Shop - Crypto USDC - Real product
using Godot;
using WoldVirtual.Commerce;
using WoldVirtual.Security;

public partial class CommerceShopCrypto : Area3D
{
    [Export] public string SellerPeerId = "seller_crypto_01";
    [Export] public string SellerWallet = "0x1234... seller Base wallet";
    [Export] public string ProductName = "Wold Hoodie - Real - Ships Worldwide";
    [Export] public float PriceUSDC = 35f;
    
    private string _myPeerId;
    private System.Security.Cryptography.ECDsa _myKey;
    private string _lastPresenceCid = "";

    public override void _Ready()
    {
        _myPeerId = SecurityManager.GetPeerId(SecurityManager.GetOrCreateECDSA());
        _myKey = SecurityManager.GetOrCreateECDSA();
        BodyEntered += OnEnter;
    }

    private void OnEnter(Node3D body){
        if(!body.HasMethod("get_peer_id")) return;
        GD.Print($"[SHOP-CRYPTO] {ProductName} {PriceUSDC} USDC - Seller {SellerPeerId} - Need PresenceProof");
    }

    public void SetPresenceCid(string cid){ _lastPresenceCid = cid; GD.Print($"[CRYPTO] Presence set {cid} - can buy now"); }

    public void OnBuyWithCryptoPressed(){
        if(string.IsNullOrEmpty(_lastPresenceCid)){
            GD.Print("[CRYPTO-FAIL] Dole ka hadu da seller a game da farko! Presence required - anti-bot!");
            return;
        }
        GD.Print($"[CRYPTO-ORDER] {ProductName} {PriceUSDC} USDC - Presence:{_lastPresenceCid[..10]} - Connect wallet...");
        // Call CryptoEscrow.HoldUSDCInEscrowAsync
        // WalletConnect / MetaMask popup
    }
}
