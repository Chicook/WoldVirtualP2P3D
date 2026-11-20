// File: WoldVirtualP2P3D/Godot/Scripts/CommerceShop.cs
// Shop 3D a cikin Isla - ka kusanto, UI ya bude, ka siya real product
using Godot;
using WoldVirtual.Commerce;
using WoldVirtual.Security;

public partial class CommerceShop : Area3D
{
    [Export] public string SellerPeerId = "seller_abuja_01";
    [Export] public string ProductName = "Keenat Sneakers";
    [Export] public int PriceKobo = 3500000; // ₦35,000
    [Export] public string RealLocation = "Wuse, Abuja";

    private WoldProduct _product;
    private string _myPeerId;
    private System.Security.Cryptography.ECDsa _myKey;
    private string _lastPresenceCid = "";

    public override void _Ready()
    {
        _myPeerId = SecurityManager.GetPeerId(SecurityManager.GetOrCreateECDSA());
        _myKey = SecurityManager.GetOrCreateECDSA();
        _product = new WoldProduct($"PROD_{SellerPeerId}", SellerPeerId, ProductName, PriceKobo, $"shop_{GlobalPosition.X:F0}_{GlobalPosition.Z:F0}", "", RealLocation);
        BodyEntered += OnPlayerEnter;
    }

    private void OnPlayerEnter(Node3D body)
    {
        if(!body.HasMethod("get_peer_id")) return;
        // Bude UI - "Ka hadu da Seller - kana so ka siya?"
        GD.Print($"[WOLD-SHOP] {_myPeerId} entered shop {ProductName} by {SellerPeerId}");
        // Anan ka kira PresenceArea - idan sun hadu, _lastPresenceCid zai cika
        // UI: "Siya da ₦{PriceKobo/100} - Real delivery zuwa gida"
    }

    public void OnBuyButtonPressed()
    {
        if(string.IsNullOrEmpty(_lastPresenceCid)){
            GD.Print("[COMMERCE-FAIL] Dole ka hadu da seller a game da farko - Proof-of-Presence required!");
            return;
        }
        var order = WoldCommerce.CreateOrder(_product, _myPeerId, _lastPresenceCid, _myKey);
        GD.Print($"[COMMERCE] Order created {order.OrderId} - Presence: {_lastPresenceCid} - Paystack escrow...");
        // Anan ka kira PaystackEscrow.HoldInEscrowAsync
    }
}
