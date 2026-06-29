using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Diagnostics;

namespace VisorSingularity.Identity
{
    public sealed class NodeIdentity : IDisposable
    {
        private readonly ECDsa _ecdsa;
        public string NodeId { get; }
        public string DID => $"did:wv:node:{NodeId}";
        public byte[] PublicKey { get; }
        public string CurveName { get; }

        private NodeIdentity(ECDsa ecdsa, string nodeId, byte[] publicKey, string curveName)
        {
            _ecdsa = ecdsa;
            NodeId = nodeId;
            PublicKey = publicKey;
            CurveName = curveName;
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
            
            using var sha256 = SHA256.Create();
            byte[] hash = sha256.ComputeHash(publicKey);
            
            var sb = new StringBuilder();
            foreach (var b in hash)
            {
                sb.Append(b.ToString("x2"));
            }
            string nodeId = sb.ToString();

            return new NodeIdentity(ecdsa, nodeId, publicKey, curveName);
        }

        public byte[] Sign(byte[] data)
        {
            return _ecdsa.SignData(data, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);
        }

        public bool Verify(byte[] data, byte[] signature)
        {
            return _ecdsa.VerifyData(data, signature, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);
        }

        public void Dispose()
        {
            _ecdsa.Dispose();
        }
    }
}
