// =============================================================================
// ProveedorClaves.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Proveedor Criptográfico por Capacidades (CNG / TPM / DPAPI)
// =============================================================================

using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using Microsoft.Win32;

namespace Visor3D.Seguridad.SesionUnica
{
    public enum NivelProteccion
    {
        Software = 1,
        Dpapi = 2,
        Tpm = 3,
        Vbs = 4
    }

    /// <summary>
    /// Administra la jerarquía y ciclo de vida de claves criptográficas locales.
    /// Evalúa dinámicamente las capacidades del host (TPM 2.0 / CNG / DPAPI),
    /// seleccionando el nivel de protección más alto disponible y degradando
    /// de forma explícita y auditada si una capacidad falla.
    /// </summary>
    public sealed class ProveedorClaves : IDisposable
    {
        private static readonly object _syncLock = new();
        private static ProveedorClaves? _instancia;

        private const string KeyNamePrefix = "WVP3D_ECDSA_P256_";
        private const string SubKeyRegistro = @"Software\WoldVirtualP2P3D\Security\Keys";
        private static readonly byte[] EntropyDpapi = Encoding.UTF8.GetBytes("WVP3D::KeyProvider::Entropy::v3");

        public static ProveedorClaves Instancia
        {
            get
            {
                if (_instancia == null)
                {
                    lock (_syncLock)
                    {
                        _instancia ??= new ProveedorClaves();
                    }
                }
                return _instancia;
            }
        }

        public NivelProteccion NivelActivo { get; private set; }
        public NivelProteccion RequerirNivelMinimo { get; set; } = NivelProteccion.Dpapi;
        public string MotivoDegradacion { get; private set; } = "Operación normal.";

        private ECDsa? _claveActiva;
        private string _keyIdActivo = "k1_ecdsa_p256";

        public ProveedorClaves()
        {
            EvaluarCapacidades();
        }

        /// <summary>
        /// Evalúa las capacidades reales de la plataforma y establece el nivel activo.
        /// </summary>
        public void EvaluarCapacidades()
        {
            // 1. Verificar si TPM 2.0 está soportado mediante CNG Platform Crypto Provider
            bool tpmSoportado = ProbarSoporteTpmCng();

            if (tpmSoportado)
            {
                NivelActivo = NivelProteccion.Tpm;
                MotivoDegradacion = "TPM 2.0 activo mediante Microsoft Platform Crypto Provider.";
            }
            else
            {
                // 2. Degradación controlada a DPAPI
                NivelActivo = NivelProteccion.Dpapi;
                MotivoDegradacion = "TPM 2.0 no provisionado para el usuario; fallback seguro a DPAPI (CurrentUser + Entropy).";
            }

            // Verificar si el nivel activo satisface la política mínima
            if (NivelActivo < RequerirNivelMinimo)
            {
                AuditoriaSeguridad.Registrar(
                    EventoAuditoria.ErrorCritico,
                    "ProveedorClaves",
                    $"El nivel activo ({NivelActivo}) no cumple el nivel mínimo requerido ({RequerirNivelMinimo}). {MotivoDegradacion}");
            }
        }

        private static bool ProbarSoporteTpmCng()
        {
            try
            {
                // Banderas oficiales de Windows CNG SDK
                var provider = new CngProvider("Microsoft Platform Crypto Provider");
                var keyParams = new CngKeyCreationParameters
                {
                    Provider = provider,
                    KeyCreationOptions = CngKeyCreationOptions.OverwriteExistingKey
                };

                string testKeyName = "WVP3D_TPM_Probe_TestKey";
                using (var key = CngKey.Create(CngAlgorithm.ECDsaP256, testKeyName, keyParams))
                {
                    key.Delete();
                }
                return true;
            }
            catch
            {
                // Fallo esperado en sistemas estándar sin elevación o sin TPM 2.0 Owner Auth
                return false;
            }
        }

        /// <summary>
        /// Obtiene o genera la clave ECDSA P-256 para el identificador de clave especificado.
        /// </summary>
        public ECDsa ObtenerOCrearClaveEcdsa(string keyId = "k1_ecdsa_p256")
        {
            lock (_syncLock)
            {
                if (_claveActiva != null && _keyIdActivo == keyId)
                {
                    return _claveActiva;
                }

                _keyIdActivo = keyId;

                // Intentar cargar mediante TPM si el nivel lo permite
                if (NivelActivo >= NivelProteccion.Tpm)
                {
                    try
                    {
                        var key = CngKey.Open(KeyNamePrefix + keyId, new CngProvider("Microsoft Platform Crypto Provider"));
                        _claveActiva = new ECDsaCng(key);
                        return _claveActiva;
                    }
                    catch
                    {
                        // Si no existe, crear en TPM
                        try
                        {
                            var provider = new CngProvider("Microsoft Platform Crypto Provider");
                            var keyParams = new CngKeyCreationParameters
                            {
                                Provider = provider,
                                KeyCreationOptions = CngKeyCreationOptions.None
                            };
                            var key = CngKey.Create(CngAlgorithm.ECDsaP256, KeyNamePrefix + keyId, keyParams);
                            _claveActiva = new ECDsaCng(key);
                            return _claveActiva;
                        }
                        catch (Exception ex)
                        {
                            // Degradación controlada a DPAPI
                            NivelActivo = NivelProteccion.Dpapi;
                            MotivoDegradacion = $"Fallo al crear clave en TPM ({ex.Message}); degradando a DPAPI.";
                            AuditoriaSeguridad.Registrar(
                                EventoAuditoria.ErrorCritico,
                                "ProveedorClaves",
                                MotivoDegradacion);
                        }
                    }
                }

                // Nivel DPAPI: almacenar clave en registro HKCU cifrada con DPAPI
                _claveActiva = ObtenerOCrearClaveDpapi(keyId);
                return _claveActiva;
            }
        }

        private static ECDsa ObtenerOCrearClaveDpapi(string keyId)
        {
            try
            {
                using var baseKey = Registry.CurrentUser.OpenSubKey(SubKeyRegistro);
                if (baseKey?.GetValue(keyId) is byte[] encryptedBlob)
                {
                    byte[] pkcs8Bytes = ProtectedData.Unprotect(encryptedBlob, EntropyDpapi, DataProtectionScope.CurrentUser);
                    try
                    {
                        var ecdsa = ECDsa.Create();
                        ecdsa.ImportPkcs8PrivateKey(pkcs8Bytes, out _);
                        return ecdsa;
                    }
                    finally
                    {
                        CryptographicOperations.ZeroMemory(pkcs8Bytes);
                    }
                }
            }
            catch { }

            // Generar nueva clave ECDSA P-256
            var nuevaClave = ECDsa.Create(ECCurve.NamedCurves.nistP256);
            byte[] rawPkcs8 = nuevaClave.ExportPkcs8PrivateKey();

            try
            {
                byte[] encrypted = ProtectedData.Protect(rawPkcs8, EntropyDpapi, DataProtectionScope.CurrentUser);
                using var baseKey = Registry.CurrentUser.CreateSubKey(SubKeyRegistro);
                baseKey.SetValue(keyId, encrypted, RegistryValueKind.Binary);
            }
            finally
            {
                CryptographicOperations.ZeroMemory(rawPkcs8);
            }

            return nuevaClave;
        }

        /// <summary>
        /// Exporta la clave pública activa en formato SubjectPublicKeyInfo (SPKI Base64).
        /// </summary>
        public string ObtenerClavePublicaSpkiBase64(string keyId = "k1_ecdsa_p256")
        {
            var clave = ObtenerOCrearClaveEcdsa(keyId);
            byte[] spki = clave.ExportSubjectPublicKeyInfo();
            return Convert.ToBase64String(spki);
        }

        /// <summary>
        /// Firma un payload canónico con la clave activa ECDSA P-256.
        /// </summary>
        public byte[] FirmarPayload(byte[] payload, string keyId = "k1_ecdsa_p256")
        {
            var clave = ObtenerOCrearClaveEcdsa(keyId);
            return clave.SignData(payload, HashAlgorithmName.SHA256);
        }

        /// <summary>
        /// Verifica una firma ECDSA P-256 usando la clave pública especificada.
        /// </summary>
        public static bool VerificarFirma(byte[] payload, byte[] firma, string clavePublicaSpkiBase64)
        {
            try
            {
                byte[] spki = Convert.FromBase64String(clavePublicaSpkiBase64);
                using var ecdsa = ECDsa.Create();
                ecdsa.ImportSubjectPublicKeyInfo(spki, out _);
                return ecdsa.VerifyData(payload, firma, HashAlgorithmName.SHA256);
            }
            catch
            {
                return false;
            }
        }

        public void Dispose()
        {
            _claveActiva?.Dispose();
            _claveActiva = null;
        }
    }
}
