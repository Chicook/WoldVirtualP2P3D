// deploy.js - Deploy WoldEscrow to Base Sepolia (test) / Base Mainnet (real)
// npm install ethers@6 dotenv

require('dotenv').config();
const { ethers } = require('ethers');

const RPC_BASE_SEPOLIA = "https://sepolia.base.org"; // test - free
const RPC_BASE_MAINNET = "https://mainnet.base.org"; // real USDC

// USDC addresses
const USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e79217eA9f0C1Bd0F5e2b"; // same on sepolia, use faucet
const USDC_BASE_MAINNET = "0x036CbD53842c5426634e79217eA9f0C1Bd0F5e2b";

const ESCROW_ABI = [
  "constructor(address _oracle)",
  "function createOrder(bytes32 orderId, address seller, uint256 amount, string presenceCid) external",
  "function release(bytes32 orderId, string deliverySig, address seller) external",
  "function orders(bytes32) view returns (address buyer, address seller, uint256 amount, string presenceCid, bool released, bool refunded)"
];

const ESCROW_BYTECODE = "0x608060405234801561001057600080fd5b50604051610..."; // Compiled bytecode - zan baka full a kasa

async function main(){
  const network = process.argv[2] || "sepolia"; // sepolia or mainnet
  const rpc = network === "mainnet" ? RPC_BASE_MAINNET : RPC_BASE_SEPOLIA;
  const privateKey = process.env.PRIVATE_KEY;
  if(!privateKey){ console.log("Set PRIVATE_KEY in .env"); return; }

  const provider = new ethers.JsonRpcProvider(rpc);
  const wallet = new ethers.Wallet(privateKey, provider);
  console.log(`[DEPLOY] Wallet ${wallet.address} on ${network} ${rpc}`);

  const balance = await provider.getBalance(wallet.address);
  console.log(`[BALANCE] ${ethers.formatEther(balance)} ETH`);

  // Deploy
  const factory = new ethers.ContractFactory(ESCROW_ABI, ESCROW_BYTECODE, wallet);
  const oracle = wallet.address; // oracle = deployer for now
  
  console.log(`[DEPLOYING] WoldEscrow oracle=${oracle}`);
  const contract = await factory.deploy(oracle);
  await contract.waitForDeployment();
  
  const address = await contract.getAddress();
  console.log(`[DEPLOYED] WoldEscrow at ${address} on ${network}`);
  console.log(`[SAVE] Add to .env: ESCROW_CONTRACT=${address}`);
  console.log(`[VERIFY] https://${network === "mainnet" ? "basescan.org" : "sepolia.basescan.org"}/address/${address}`);

  // Test USDC faucet info
  console.log(`[USDC] Use faucet for test: https://faucet.circle.com/ - USDC Base Sepolia`);
}

main().catch(console.error);
