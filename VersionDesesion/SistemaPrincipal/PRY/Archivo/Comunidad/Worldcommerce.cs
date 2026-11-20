// File: WoldVirtualP2P3D/Core/Commerce/WoldCommerce.cs
// WOLD COMMERCE - REAL MONEY PHYGITAL - BABU IRINSA A DUNIYA
using System;
using System.Security.Cryptography;
using System.Text.Json;
using WoldVirtual.Security;

namespace WoldVirtual.Commerce
{
    public enum OrderStatus { Created, PaidEscrow, Shipped, Delivered, Disputed }

    public record WoldProduct(
        string ProductId,
        string SellerPeerId,
        string Name,
        int PriceKobo, // Real money in Kobo - 100 kobo = 1 Naira
        string IslandChunk, // Ina aka saida shi a game
        string IpfsImageCid,
        string RealStockLocation // "Abuja - Wuse"
    );

    public record WoldOrder(
        string OrderId,
        string BuyerPeerId,
        string SellerPeerId,
        string ProductId,
        int AmountKobo,
        long CreatedAt,
        OrderStatus Status,
        string PresenceProofCid, // Wannan order din ya samo asali daga haduwa ta gaskiya?
        string EscrowTxRef, // Paystack ref
        string DeliveryProofCid // Hoto + GPS da seller ya sanya hannu da P-256
    );

    public static class WoldCommerce
    {
        // Buyer ya biya - kudi ya shiga escrow, signature da P-256
        public static WoldOrder CreateOrder(WoldProduct product, string buyerPeerId, string presenceCid, ECDsa buyerKey)
        {
            var order = new WoldOrder(
                $"ORD_{Guid.NewGuid().ToString("N")[..8].ToUpper()}",
                buyerPeerId,
                product.SellerPeerId,
                product.ProductId,
                product.PriceKobo,
                DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
                OrderStatus.Created,
                presenceCid, // IMPORTANT: Order ya zo daga Proof-of-Presence
                "",
                ""
            );

            var json = JsonSerializer.Serialize(order);
            var sig = buyerKey.SignData(System.Text.Encoding.UTF8.GetBytes(json), HashAlgorithmName.SHA256);
            Console.WriteLine($"[COMMERCE] Order {order.OrderId} signed by {buyerPeerId} sig:{Convert.ToBase64String(sig)[..20]}...");

            return order;
        }

        // Seller ya tabbatar ya turo - da hoto + GPS + signature P-256
        public static string CreateDeliveryProof(string orderId, string latLong, string imageCid, ECDsa sellerKey)
        {
            var proof = new { orderId, latLong, imageCid, ts = DateTimeOffset.UtcNow.ToUnixTimeSeconds() };
            var json = JsonSerializer.Serialize(proof);
            var sig = sellerKey.SignData(System.Text.Encoding.UTF8.GetBytes(json), HashAlgorithmName.SHA256);
            return Convert.ToBase64String(sig) + "." + imageCid;
        }

        public static bool VerifyDelivery(string orderJson, string deliverySig, ECDsa sellerPubKey)
        {
            try{
                var parts = deliverySig.Split('.');
                var sig = Convert.FromBase64String(parts[0]);
                var data = System.Text.Encoding.UTF8.GetBytes(orderJson);
                return sellerPubKey.VerifyData(data, sig, HashAlgorithmName.SHA256);
            } catch { return false; }
        }
    }
  }
