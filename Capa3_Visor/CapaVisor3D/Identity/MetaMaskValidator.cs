using System;

namespace VisorSingularity.Identity
{
    public static class MetaMaskValidator
    {
        public static bool IsSimulatedSignature(string signature)
        {
            return !string.IsNullOrEmpty(signature) && signature.StartsWith("0x_simulated_signature_", StringComparison.Ordinal);
        }

        public static bool VerifySignature(string walletAddress, string message, string signature, bool allowSimulation = true)
        {
            if (string.IsNullOrEmpty(walletAddress) || string.IsNullOrEmpty(signature))
                return false;

            if (allowSimulation && IsSimulatedSignature(signature))
            {
                return true;
            }

            // Extensible hooks: Real Ethereum signature verification would recover the address
            // using Nethereum.Signer:
            // var signer = new Nethereum.Signer.EthereumMessageSigner();
            // var address = signer.EncodeUTF8AndEcRecover(message, signature);
            // return address.Equals(walletAddress, StringComparison.OrdinalIgnoreCase);

            return false;
        }
    }
}
