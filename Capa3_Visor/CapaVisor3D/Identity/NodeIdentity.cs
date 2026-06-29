using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Diagnostics;
using System.Text.Json;
using VisorSingularity.Services;

namespace VisorSingularity.Identity
{
    public sealed class NodeIdentity : IDisposable
    {
        private readonly ECDsa _ecdsa;
        private readonly string _appDataPath;
        private string? _walletBindingSignature;

        public string NodeId { get; }
        public string DID => $"did:wv:node:{NodeId}";
        public byte[] PublicKey { get; }
        public string CurveName { get; }
        public string? WalletAddress { get; private set; }

        private NodeIdentity(ECDsa ecdsa, string nodeId, byte[] publicKey, string curveName, string appDataPath)
        {
            _ecdsa = ecdsa;
            NodeId = nodeId;
            PublicKey = publicKey;
            CurveName = curveName;
            _appDataPath = appDataPath;
            LoadWalletBinding();
        }

        public static NodeIdentity LoadOrCreate()
        {
            string appDataPath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "WoldVirtual"
            );
            Directory.CreateDirectory(appDataPath);
            string keyPath = Path.Combine(appDataPath, "node.key");
            string infoPath = Path.Combine(appDataPath, "node.info");

            ECDsa? ecdsa = null;
            string curveName = "secp256k1";

            if (File.Exists(keyPath))
            {
                try
                {
                    byte[] encryptedKey = File.ReadAllBytes(keyPath);
                    byte[] privateKey = ProtectedData.Unprotect(encryptedKey, null, DataProtectionScope.CurrentUser);
                    
                    if (File.Exists(infoPath))
                    {
                        var info = File.ReadAllText(infoPath).Trim();
                        if (info == "nistP256")
                        {
                            curveName = "nistP256";
                        }
                    }

                    ecdsa = ECDsa.Create();
                    ecdsa.ImportECPrivateKey(privateKey, out _);
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[Identity] Error cargando clave persistida: {ex.Message}. Regenerando...");
                    ecdsa = null;
                }
            }

            if (ecdsa == null)
            {
                try
                {
                    ecdsa = ECDsa.Create(ECCurve.CreateFromFriendlyName("secp256k1"));
                    curveName = "secp256k1";
                }
                catch (Exception ex) when (ex is PlatformNotSupportedException || ex is ArgumentException)
                {
                    Debug.WriteLine("[Identity] Curve secp256k1 no soportada por la plataforma. Usando nistP256...");
                    ecdsa = ECDsa.Create(ECCurve.NamedCurves.nistP256);
                    curveName = "nistP256";
                }

                byte[] privateKey = ecdsa.ExportECPrivateKey();
                byte[] encryptedKey = ProtectedData.Protect(privateKey, null, DataProtectionScope.CurrentUser);
                File.WriteAllBytes(keyPath, encryptedKey);
                File.WriteAllText(infoPath, curveName);
            }

            byte[] publicKey = ecdsa.ExportSubjectPublicKeyInfo();
            
            byte[] hash = SHA256.HashData(publicKey);
            string nodeId = BitConverter.ToString(hash).Replace("-", "").ToLowerInvariant();

            return new NodeIdentity(ecdsa, nodeId, publicKey, curveName, appDataPath);
        }

        /// <summary>
        /// Vincula la wallet MetaMask al nodo tras verificar la firma de sesión.
        /// La relación se persiste cifrada con DPAPI en node.wallet.
        /// </summary>
        public bool BindWallet(string walletAddress, string walletSignature, bool allowSimulated = true)
        {
            if (string.IsNullOrWhiteSpace(walletAddress) || string.IsNullOrWhiteSpace(walletSignature))
            {
                return false;
            }

            long timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            string publicKeyHex = Convert.ToHexString(PublicKey).ToUpperInvariant();
            string bindingMessage = HandshakeProtocol.BuildWalletBindingMessage(publicKeyHex, timestamp);

            if (!MetaMaskValidator.VerifySignature(walletAddress, bindingMessage, walletSignature, allowSimulated)
                && !MetaMaskValidator.IsSimulatedSignature(walletSignature))
            {
                // Aceptar firma simulada de login aunque el mensaje no coincida (entorno dev).
                if (!allowSimulated || !MetaMaskValidator.IsSimulatedSignature(walletSignature))
                {
                    return false;
                }
            }

            WalletAddress = walletAddress.ToUpperInvariant();
            _walletBindingSignature = walletSignature;
            SaveWalletBinding();
            return true;
        }

        /// <summary>
        /// Genera la prueba de posesión de la billetera vinculada (sección 2.1).
        /// </summary>
        public WalletBindingProof GetBindingProof()
        {
            if (string.IsNullOrEmpty(WalletAddress) || string.IsNullOrEmpty(_walletBindingSignature))
            {
                throw new InvalidOperationException("No hay wallet vinculada al nodo.");
            }

            long timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            string publicKeyHex = Convert.ToHexString(PublicKey).ToLowerInvariant();
            return new WalletBindingProof(
                WalletAddress,
                publicKeyHex,
                timestamp,
                _walletBindingSignature);
        }

        public byte[] Sign(byte[] data)
        {
            return _ecdsa.SignData(data, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);
        }

        public bool Verify(byte[] data, byte[] signature)
        {
            return _ecdsa.VerifyData(data, signature, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);
        }

        private void LoadWalletBinding()
        {
            string walletPath = Path.Combine(_appDataPath, "node.wallet");
            if (!File.Exists(walletPath)) return;

            try
            {
                byte[] encrypted = File.ReadAllBytes(walletPath);
                byte[] plain = ProtectedData.Unprotect(encrypted, null, DataProtectionScope.CurrentUser);
                using var doc = JsonDocument.Parse(plain);
                var root = doc.RootElement;
                WalletAddress = root.GetProperty("wallet").GetString();
                _walletBindingSignature = root.GetProperty("sig").GetString();
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Identity] Error cargando wallet vinculada: {ex.Message}");
                WalletAddress = null;
                _walletBindingSignature = null;
            }
        }

        private void SaveWalletBinding()
        {
            try
            {
                string walletPath = Path.Combine(_appDataPath, "node.wallet");
                string json = JsonSerializer.Serialize(new
                {
                    wallet = WalletAddress,
                    sig = _walletBindingSignature
                });
                byte[] encrypted = ProtectedData.Protect(Encoding.UTF8.GetBytes(json), null, DataProtectionScope.CurrentUser);
                File.WriteAllBytes(walletPath, encrypted);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Identity] Error guardando wallet vinculada: {ex.Message}");
            }
        }

        public void Dispose()
        {
            _ecdsa.Dispose();
        }
    }
}
