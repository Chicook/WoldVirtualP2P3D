using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace VisorSingularity.Services
{
    public static class NodeIdentityManager
    {
        private static readonly string FolderPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WoldVirtualP2P"
        );
        private static readonly string FilePath = Path.Combine(FolderPath, "node_identity.json");

        public static NodeIdentity? Current { get; private set; }

        public static void Initialize(string username)
        {
            try
            {
                if (!Directory.Exists(FolderPath))
                {
                    Directory.CreateDirectory(FolderPath);
                }

                if (File.Exists(FilePath))
                {
                    string json = File.ReadAllText(FilePath, Encoding.UTF8);
                    Current = JsonSerializer.Deserialize<NodeIdentity>(json);
                }

                if (Current == null || string.IsNullOrEmpty(Current.NodeId) || string.IsNullOrEmpty(Current.PrivateKeyBase64))
                {
                    // Generar nuevo par de claves e identidad usando ECDSA P-256
                    using var ecdsa = ECDsa.Create(ECCurve.NamedCurves.nistP256);
                    
                    byte[] privateBytes = ecdsa.ExportPkcs8PrivateKey();
                    byte[] publicBytes = ecdsa.ExportSubjectPublicKeyInfo();

                    string privateBase64 = Convert.ToBase64String(privateBytes);
                    string publicBase64 = Convert.ToBase64String(publicBytes);

                    // Generar un seed estable a partir del hash de la clave pública para mantener el formato NDxxxxx
                    int seed = Math.Abs(publicBase64.GetHashCode()) % 90000 + 10000;
                    string nodeId = $"ND{seed}";

                    Current = new NodeIdentity
                    {
                        NodeId = nodeId,
                        Username = username,
                        PrivateKeyBase64 = privateBase64,
                        PublicKeyBase64 = publicBase64
                    };

                    Save();
                }
                else if (Current.Username != username && !string.IsNullOrEmpty(username))
                {
                    // Actualizar el nombre de usuario si ha cambiado
                    Current.Username = username;
                    Save();
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[NodeIdentityManager] Error en Initialize: {ex.Message}");
                // Fallback a identidad efímera en memoria para evitar caídas del programa si falla la escritura en disco
                if (Current == null)
                {
                    using var ecdsa = ECDsa.Create(ECCurve.NamedCurves.nistP256);
                    string privateBase64 = Convert.ToBase64String(ecdsa.ExportPkcs8PrivateKey());
                    string publicBase64 = Convert.ToBase64String(ecdsa.ExportSubjectPublicKeyInfo());
                    Current = new NodeIdentity
                    {
                        NodeId = $"ND{new Random().Next(10000, 99000)}",
                        Username = username,
                        PrivateKeyBase64 = privateBase64,
                        PublicKeyBase64 = publicBase64
                    };
                }
            }
        }

        public static void Save()
        {
            if (Current == null) return;
            try
            {
                var options = new JsonSerializerOptions { WriteIndented = true };
                string json = JsonSerializer.Serialize(Current, options);
                File.WriteAllText(FilePath, json, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[NodeIdentityManager] Error al guardar la identidad: {ex.Message}");
            }
        }

        public static string SignData(string data)
        {
            if (Current == null || string.IsNullOrEmpty(Current.PrivateKeyBase64))
                throw new InvalidOperationException("Identidad no inicializada.");

            using var ecdsa = ECDsa.Create();
            byte[] privateBytes = Convert.FromBase64String(Current.PrivateKeyBase64);
            ecdsa.ImportPkcs8PrivateKey(privateBytes, out _);

            byte[] dataBytes = Encoding.UTF8.GetBytes(data);
            byte[] signatureBytes = ecdsa.SignData(dataBytes, HashAlgorithmName.SHA256);
            return Convert.ToBase64String(signatureBytes);
        }

        public static bool VerifyData(string data, string signatureBase64, string publicKeyBase64)
        {
            if (string.IsNullOrEmpty(data) || string.IsNullOrEmpty(signatureBase64) || string.IsNullOrEmpty(publicKeyBase64))
                return false;

            try
            {
                using var ecdsa = ECDsa.Create();
                byte[] publicBytes = Convert.FromBase64String(publicKeyBase64);
                ecdsa.ImportSubjectPublicKeyInfo(publicBytes, out _);

                byte[] dataBytes = Encoding.UTF8.GetBytes(data);
                byte[] signatureBytes = Convert.FromBase64String(signatureBase64);
                return ecdsa.VerifyData(dataBytes, signatureBytes, HashAlgorithmName.SHA256);
            }
            catch
            {
                return false;
            }
        }
    }
}
