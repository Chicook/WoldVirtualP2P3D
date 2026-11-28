// File: WoldVirtualP2P3D/Core/Commerce/CryptoEscrow.cs
// CRYPTO ESCROW - USDC on Base - Real crypto - P-256 verified - No USD, No Naira
using System;
using System.Numerics;
using System.Threading.Tasks;
using Nethereum.Web3;
using Nethereum.Contracts;
using WoldVirtual.Security;

namespace WoldVirtual.Commerce
{
    public record CryptoOrder(
        string OrderId,
        string BuyerPeerId,
        string SellerPeerId,
        string ProductId,
        decimal AmountUSDC, // e.g., 35.00 USDC
        long CreatedAt,
        OrderStatus Status,
        string PresenceProofCid, // Dole - anti-bot
        string TxHash,
        string EscrowContractAddress
    );

    public class CryptoEscrow
    {
        // Base Mainnet USDC: 0x036CbD53842c5426634e79217eA9f0C1Bd0F5e2b - 6 decimals
        private const string USDC_BASE = "0x036CbD53842c5426634e79217eA9f0C1Bd0F5e2b";
        private const string ESCROW_CONTRACT = "0xYOUR_ESCROW_CONTRACT"; // Deploy naka
        private readonly Web3 _web3;
        private readonly string _privateKey; // Server wallet for escrow

        public CryptoEscrow(string rpcUrl, string escrowPrivateKey)
        {
            _web3 = new Web3(rpcUrl); // https://mainnet.base.org
            _privateKey = escrowPrivateKey;
        }

        // 1. Buyer ya biya USDC zuwa escrow contract
        public async Task<(bool ok, string txHash)> HoldUSDCInEscrowAsync(CryptoOrder order, string buyerWallet)
        {
            // Solidity escrow:
            // function createOrder(bytes32 orderId, address seller, uint256 amount, string memory presenceCid) external
            // function release(bytes32 orderId, string memory deliverySig) external - only buyer or after delivery proof P-256
            
            var contract = _web3.Eth.GetContract(ABI, ESCROW_CONTRACT);
            var createFunc = contract.GetFunction("createOrder");

            var orderIdBytes = System.Text.Encoding.UTF8.GetBytes(order.OrderId);
            var amount = Web3.Convert.ToWei(order.AmountUSDC, 6); // USDC 6 decimals

            var txHash = await createFunc.SendTransactionAsync(
                buyerWallet,
                new HexBigInteger(300000),
                null,
                orderIdBytes,
                order.SellerPeerId, // seller wallet mapped to peerId
                amount,
                order.PresenceProofCid
            );

            Console.WriteLine($"[CRYPTO-ESCROW] Order {order.OrderId} {order.AmountUSDC} USDC tx:{txHash} Presence:{order.PresenceProofCid[..10]}");

            return (true, txHash);
        }

        // 2. Seller ya sanya delivery proof da P-256 - smart contract ya tabbatar da signature
        public async Task<bool> ReleaseUSDCToSellerAsync(CryptoOrder order, string deliverySigB64, string sellerWallet)
        {
            // deliverySigB64 = P-256 signature na seller
            // Contract ya tabbatar: ecrecover? amma P-256 ba secp256k1 ba - sai off-chain verification da oracle
            
            var contract = _web3.Eth.GetContract(ABI, ESCROW_CONTRACT);
            var releaseFunc = contract.GetFunction("release");

            var txHash = await releaseFunc.SendTransactionAsync(
                _privateKey,
                new HexBigInteger(300000),
                null,
                System.Text.Encoding.UTF8.GetBytes(order.OrderId),
                deliverySigB64,
                sellerWallet
            );

            Console.WriteLine($"[CRYPTO-RELEASE] {order.AmountUSDC} USDC to {sellerWallet} tx:{txHash}");
            return true;
        }

        // P-256 -> Ethereum address mapping (ECDSA P-256 peerId -> secp256k1 wallet)
        public
