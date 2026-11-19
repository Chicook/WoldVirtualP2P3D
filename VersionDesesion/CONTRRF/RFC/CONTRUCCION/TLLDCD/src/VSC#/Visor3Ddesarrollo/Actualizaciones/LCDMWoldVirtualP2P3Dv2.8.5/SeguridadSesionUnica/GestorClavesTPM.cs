// GestorClavesTPM.cs
// Namespace: Visor3D.Seguridad.SesionUnica
// Gestión de claves criptográficas con soporte TPM 2.0 (Microsoft Platform Crypto Provider)
// y fallback a Software KSP (CNG) cuando el TPM no está disponible.
// Solo dependencias: System.*, System.Security.Cryptography, Microsoft.Win32, P/Invoke (ncrypt.dll / bcrypt.dll).
// Compatible con .NET 8 Windows.

using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Gestión de claves criptográficas con soporte TPM 2.0 (Microsoft Platform Crypto Provider)
    /// y fallback a DPAPI cuando el TPM no está disponible o la clave no es sellable.
    ///
    /// Prioridad:
    ///   1. TPM físico — clave no exportable, sellada a PCR si disponible
    ///   2. Software KSP (CNG) — clave no exportable pero sin hardware root
    ///   3. DPAPI — última línea (AlmacenSeguro ya lo hace para el secreto maestro)
    ///
    /// Las claves se identifican por nombre: "LuciaSecureCore_v1_&lt;cuentaId&gt;"
    /// La clave privada NUNCA sale del KSP. Solo se expone la clave pública.
    /// Las operaciones de firma se realizan en el KSP (NCryptSignHash).
    /// </summary>
    public static class GestorClavesTPM
    {
        // ─────────────────────────────────────────────────────────────────────────
        // Constantes NCrypt / BCrypt
        // ─────────────────────────────────────────────────────────────────────────

        private const string NCRYPT_RSA_ALGORITHM               = "RSA";
        private const string MS_PLATFORM_CRYPTO_PROVIDER        = "Microsoft Platform Crypto Provider";
        private const string MS_KEY_STORAGE_PROVIDER            = "Microsoft Software Key Storage Provider";
        private const string BCRYPT_RSAPUBLIC_BLOB              = "RSAPUBLICBLOB";
        private const string NCRYPT_ALGORITHM_PROPERTY          = "Algorithm Name";
        private const string NCRYPT_LENGTH_PROPERTY             = "Length";
        private const string NCRYPT_EXPORT_POLICY_PROPERTY      = "Export Policy";
        private const string NCRYPT_KEY_USAGE_PROPERTY          = "Key Usage";
        private const string BCRYPT_SHA256_ALGORITHM            = "SHA256";

        // NCrypt flags
        private const uint NCRYPT_SILENT_FLAG                   = 0x00000040;
        private const uint NCRYPT_OVERWRITE_KEY_FLAG            = 0x00000080;
        private const uint NCRYPT_PERSIST_FLAG                  = 0x00000001;
        private const uint NCRYPT_ALLOW_EXPORT_FLAG             = 0x00000001;
        private const uint NCRYPT_ALLOW_PLAINTEXT_EXPORT_FLAG   = 0x00000002;
        private const uint NCRYPT_ALLOW_ARCHIVING_FLAG          = 0x00000004;
        private const uint NCRYPT_ALLOW_PLAINTEXT_ARCHIVING_FLAG = 0x00000008;
        // Export policy = 0 means NOT exportable
        private const uint NCRYPT_NO_EXPORT_FLAG                = 0x00000000;
        // Key usage
        private const uint NCRYPT_ALLOW_SIGNING_FLAG            = 0x00000001;
        private const uint NCRYPT_ALLOW_DECRYPT_FLAG            = 0x00000002;

        // NCrypt property flags
        private const uint NCRYPT_PROPERTY_SET_NO_FLAG          = 0x00000000;
        private const uint NCRYPT_PERSIST_ONLY_FLAG             = 0x40000000;

        // NCryptFinalizeKey flags
        private const uint NCRYPT_NO_FLAG                       = 0x00000000;

        // BCrypt/NCrypt error codes
        private const int NTE_BAD_KEYSET                        = unchecked((int)0x80090016);
        private const int NTE_NO_KEY                            = unchecked((int)0x8009002D);
        private const int ERROR_SUCCESS                         = 0;

        // BCrypt padding info for PSS / PKCS1
        private const uint BCRYPT_PAD_PKCS1                     = 0x00000002;

        // ─────────────────────────────────────────────────────────────────────────
        // P/Invoke — ncrypt.dll
        // ─────────────────────────────────────────────────────────────────────────

        [DllImport("ncrypt.dll", CharSet = CharSet.Unicode, SetLastError = false)]
        private static extern int NCryptOpenStorageProvider(
            out IntPtr phProvider,
            string pszProviderName,
            uint dwFlags);

        [DllImport("ncrypt.dll", CharSet = CharSet.Unicode, SetLastError = false)]
        private static extern int NCryptCreatePersistedKey(
            IntPtr hProvider,
            out IntPtr phKey,
            string pszAlgId,
            string? pszKeyName,
            uint dwLegacyKeySpec,
            uint dwFlags);

        [DllImport("ncrypt.dll", CharSet = CharSet.Unicode, SetLastError = false)]
        private static extern int NCryptSetProperty(
            IntPtr hObject,
            string pszProperty,
            byte[] pbInput,
            uint cbInput,
            uint dwFlags);

        [DllImport("ncrypt.dll", CharSet = CharSet.Unicode, SetLastError = false)]
        private static extern int NCryptFinalizeKey(
            IntPtr hKey,
            uint dwFlags);

        [DllImport("ncrypt.dll", CharSet = CharSet.Unicode, SetLastError = false)]
        private static extern int NCryptOpenKey(
            IntPtr hProvider,
            out IntPtr phKey,
            string pszKeyName,
            uint dwLegacyKeySpec,
            uint dwFlags);

        [DllImport("ncrypt.dll", CharSet = CharSet.Unicode, SetLastError = false)]
        private static extern int NCryptExportKey(
            IntPtr hKey,
            IntPtr hExportKey,
            string pszBlobType,
            IntPtr pParameterList,
            byte[]? pbOutput,
            uint cbOutput,
            out uint pcbResult,
            uint dwFlags);

        [DllImport("ncrypt.dll", CharSet = CharSet.Unicode, SetLastError = false)]
        private static extern int NCryptSignHash(
            IntPtr hKey,
            IntPtr pPaddingInfo,
            byte[] pbHashValue,
            uint cbHashValue,
            byte[]? pbSignature,
            uint cbSignature,
            out uint pcbResult,
            uint dwFlags);

        [DllImport("ncrypt.dll", CharSet = CharSet.Unicode, SetLastError = false)]
        private static extern int NCryptDeleteKey(
            IntPtr hKey,
            uint dwFlags);

        [DllImport("ncrypt.dll", CharSet = CharSet.Unicode, SetLastError = false)]
        private static extern int NCryptFreeObject(IntPtr hObject);

        // ─────────────────────────────────────────────────────────────────────────
        // Struct para BCRYPT_PKCS1_PADDING_INFO
        // ─────────────────────────────────────────────────────────────────────────

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct BCRYPT_PKCS1_PADDING_INFO
        {
            [MarshalAs(UnmanagedType.LPWStr)]
            public string pszAlgId;
        }

        // ─────────────────────────────────────────────────────────────────────────
        // Helpers privados
        // ─────────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Intenta abrir un KSP por nombre. Devuelve el handle o IntPtr.Zero si falla.
        /// </summary>
        private static IntPtr AbrirProvider(string providerName)
        {
            int status = NCryptOpenStorageProvider(out IntPtr hProv, providerName, 0);
            return status == ERROR_SUCCESS ? hProv : IntPtr.Zero;
        }

        /// <summary>
        /// Libera un handle NCrypt si es válido (no lanza).
        /// </summary>
        private static void LiberarHandle(IntPtr h)
        {
            if (h != IntPtr.Zero)
            {
                try { NCryptFreeObject(h); } catch { /* ignorar */ }
            }
        }

        /// <summary>
        /// Establece una propiedad DWORD en un objeto NCrypt.
        /// </summary>
        private static int SetPropertyDword(IntPtr hObj, string property, uint value)
        {
            byte[] buf = BitConverter.GetBytes(value);
            return NCryptSetProperty(hObj, property, buf, (uint)buf.Length, NCRYPT_PROPERTY_SET_NO_FLAG);
        }

        /// <summary>
        /// Abre la clave por nombre probando primero TPM y luego Software KSP.
        /// Devuelve (hProvider, hKey) o (Zero, Zero) si no existe.
        /// El llamador debe liberar ambos handles.
        /// </summary>
        private static (IntPtr hProv, IntPtr hKey) AbrirClaveExistente(string nombreClave)
        {
            // Prioridad 1: TPM
            IntPtr hProv = AbrirProvider(MS_PLATFORM_CRYPTO_PROVIDER);
            if (hProv != IntPtr.Zero)
            {
                int s = NCryptOpenKey(hProv, out IntPtr hKey, nombreClave, 0, NCRYPT_SILENT_FLAG);
                if (s == ERROR_SUCCESS)
                    return (hProv, hKey);
                LiberarHandle(hProv);
            }

            // Prioridad 2: Software KSP
            hProv = AbrirProvider(MS_KEY_STORAGE_PROVIDER);
            if (hProv != IntPtr.Zero)
            {
                int s = NCryptOpenKey(hProv, out IntPtr hKey, nombreClave, 0, NCRYPT_SILENT_FLAG);
                if (s == ERROR_SUCCESS)
                    return (hProv, hKey);
                LiberarHandle(hProv);
            }

            return (IntPtr.Zero, IntPtr.Zero);
        }

        // ─────────────────────────────────────────────────────────────────────────
        // API pública
        // ─────────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Comprueba si el TPM 2.0 (Microsoft Platform Crypto Provider) está disponible en este equipo.
        /// Nunca lanza excepción.
        /// </summary>
        public static bool TpmDisponible()
        {
            try
            {
                IntPtr hProv = AbrirProvider(MS_PLATFORM_CRYPTO_PROVIDER);
                if (hProv == IntPtr.Zero) return false;
                LiberarHandle(hProv);
                return true;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[GestorClavesTPM] TpmDisponible excepción: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Crea una clave RSA-2048 persistente con el nombre dado.
        /// Intenta primero el TPM (Microsoft Platform Crypto Provider).
        /// Si falla, cae al Software KSP (Microsoft Software Key Storage Provider).
        /// La clave privada NO es exportable.
        /// Devuelve true si la clave fue creada (o ya existía); false si falla todo.
        /// </summary>
        public static bool CrearClaveIdentidad(string nombreClave)
        {
            if (string.IsNullOrWhiteSpace(nombreClave)) return false;

            // Lista de proveedores en orden de preferencia
            string[] proveedores = TpmDisponible()
                ? new[] { MS_PLATFORM_CRYPTO_PROVIDER, MS_KEY_STORAGE_PROVIDER }
                : new[] { MS_KEY_STORAGE_PROVIDER };

            foreach (string provName in proveedores)
            {
                IntPtr hProv = IntPtr.Zero;
                IntPtr hKey  = IntPtr.Zero;
                try
                {
                    hProv = AbrirProvider(provName);
                    if (hProv == IntPtr.Zero) continue;

                    // ¿Ya existe la clave? Abrirla es suficiente.
                    int openStatus = NCryptOpenKey(hProv, out hKey, nombreClave, 0, NCRYPT_SILENT_FLAG);
                    if (openStatus == ERROR_SUCCESS)
                    {
                        Debug.WriteLine($"[GestorClavesTPM] Clave '{nombreClave}' ya existe en '{provName}'.");
                        return true;
                    }
                    if (hKey != IntPtr.Zero) { LiberarHandle(hKey); hKey = IntPtr.Zero; }

                    // Crear clave nueva RSA-2048
                    int createStatus = NCryptCreatePersistedKey(
                        hProv,
                        out hKey,
                        NCRYPT_RSA_ALGORITHM,
                        nombreClave,
                        0,
                        NCRYPT_OVERWRITE_KEY_FLAG | NCRYPT_SILENT_FLAG);

                    if (createStatus != ERROR_SUCCESS)
                    {
                        Debug.WriteLine($"[GestorClavesTPM] NCryptCreatePersistedKey falló (0x{createStatus:X8}) en '{provName}'.");
                        continue;
                    }

                    // Longitud de clave: 2048 bits
                    int setLen = SetPropertyDword(hKey, NCRYPT_LENGTH_PROPERTY, 2048);
                    if (setLen != ERROR_SUCCESS)
                        Debug.WriteLine($"[GestorClavesTPM] SetProperty(Length) advirtió 0x{setLen:X8}.");

                    // Política de exportación: NO exportable (valor 0)
                    int setExp = SetPropertyDword(hKey, NCRYPT_EXPORT_POLICY_PROPERTY, NCRYPT_NO_EXPORT_FLAG);
                    if (setExp != ERROR_SUCCESS)
                        Debug.WriteLine($"[GestorClavesTPM] SetProperty(ExportPolicy) advirtió 0x{setExp:X8}.");

                    // Uso: solo firma
                    int setUsage = SetPropertyDword(hKey, NCRYPT_KEY_USAGE_PROPERTY, NCRYPT_ALLOW_SIGNING_FLAG);
                    if (setUsage != ERROR_SUCCESS)
                        Debug.WriteLine($"[GestorClavesTPM] SetProperty(KeyUsage) advirtió 0x{setUsage:X8}.");

                    // Finalizar (persiste la clave en el KSP)
                    int finalStatus = NCryptFinalizeKey(hKey, NCRYPT_NO_FLAG);
                    if (finalStatus != ERROR_SUCCESS)
                    {
                        Debug.WriteLine($"[GestorClavesTPM] NCryptFinalizeKey falló (0x{finalStatus:X8}) en '{provName}'.");
                        continue;
                    }

                    Debug.WriteLine($"[GestorClavesTPM] Clave '{nombreClave}' creada exitosamente en '{provName}'.");
                    return true;
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[GestorClavesTPM] CrearClaveIdentidad excepción ({provName}): {ex.Message}");
                }
                finally
                {
                    LiberarHandle(hKey);
                    LiberarHandle(hProv);
                }
            }

            Debug.WriteLine($"[GestorClavesTPM] CrearClaveIdentidad falló para '{nombreClave}' en todos los proveedores.");
            return false;
        }

        /// <summary>
        /// Exporta la clave pública RSA en formato BCRYPT_RSAPUBLIC_BLOB.
        /// Devuelve null si la clave no existe o si ocurre algún error.
        /// La clave privada nunca es expuesta.
        /// </summary>
        public static byte[]? ObtenerClavePublicaRaw(string nombreClave)
        {
            if (string.IsNullOrWhiteSpace(nombreClave)) return null;

            IntPtr hProv = IntPtr.Zero;
            IntPtr hKey  = IntPtr.Zero;
            try
            {
                (hProv, hKey) = AbrirClaveExistente(nombreClave);
                if (hKey == IntPtr.Zero)
                {
                    Debug.WriteLine($"[GestorClavesTPM] ObtenerClavePublicaRaw: clave '{nombreClave}' no encontrada.");
                    return null;
                }

                // Primer paso: obtener tamaño del blob
                int sizeStatus = NCryptExportKey(
                    hKey,
                    IntPtr.Zero,
                    BCRYPT_RSAPUBLIC_BLOB,
                    IntPtr.Zero,
                    null,
                    0,
                    out uint cbResult,
                    0);

                if (sizeStatus != ERROR_SUCCESS || cbResult == 0)
                {
                    Debug.WriteLine($"[GestorClavesTPM] NCryptExportKey (size) falló 0x{sizeStatus:X8}.");
                    return null;
                }

                byte[] blob = new byte[cbResult];
                int exportStatus = NCryptExportKey(
                    hKey,
                    IntPtr.Zero,
                    BCRYPT_RSAPUBLIC_BLOB,
                    IntPtr.Zero,
                    blob,
                    cbResult,
                    out uint cbUsed,
                    0);

                if (exportStatus != ERROR_SUCCESS)
                {
                    Debug.WriteLine($"[GestorClavesTPM] NCryptExportKey (data) falló 0x{exportStatus:X8}.");
                    return null;
                }

                // Ajustar al tamaño real
                if (cbUsed < cbResult)
                    Array.Resize(ref blob, (int)cbUsed);

                return blob;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[GestorClavesTPM] ObtenerClavePublicaRaw excepción: {ex.Message}");
                return null;
            }
            finally
            {
                LiberarHandle(hKey);
                LiberarHandle(hProv);
            }
        }

        /// <summary>
        /// Firma los datos con la clave privada persistente usando SHA-256 con relleno PKCS#1 v1.5.
        /// La operación de firma ocurre dentro del KSP (TPM o Software KSP).
        /// La clave privada nunca sale del KSP.
        /// Devuelve null si la clave no existe o si falla la operación.
        /// </summary>
        public static byte[]? FirmarConClavePermanente(string nombreClave, byte[] data)
        {
            if (string.IsNullOrWhiteSpace(nombreClave) || data == null || data.Length == 0)
                return null;

            IntPtr hProv    = IntPtr.Zero;
            IntPtr hKey     = IntPtr.Zero;
            IntPtr pPadding = IntPtr.Zero;
            try
            {
                (hProv, hKey) = AbrirClaveExistente(nombreClave);
                if (hKey == IntPtr.Zero)
                {
                    Debug.WriteLine($"[GestorClavesTPM] FirmarConClavePermanente: clave '{nombreClave}' no encontrada.");
                    return null;
                }

                // Calcular SHA-256 del payload
                byte[] hash = SHA256.HashData(data);

                // Configurar PKCS1 padding info apuntando a "SHA256"
                var paddingInfo = new BCRYPT_PKCS1_PADDING_INFO { pszAlgId = BCRYPT_SHA256_ALGORITHM };
                pPadding = Marshal.AllocHGlobal(Marshal.SizeOf<BCRYPT_PKCS1_PADDING_INFO>());
                Marshal.StructureToPtr(paddingInfo, pPadding, false);

                // Paso 1: obtener tamaño de la firma
                int sizeStatus = NCryptSignHash(
                    hKey,
                    pPadding,
                    hash,
                    (uint)hash.Length,
                    null,
                    0,
                    out uint cbSignature,
                    BCRYPT_PAD_PKCS1);

                if (sizeStatus != ERROR_SUCCESS || cbSignature == 0)
                {
                    Debug.WriteLine($"[GestorClavesTPM] NCryptSignHash (size) falló 0x{sizeStatus:X8}.");
                    return null;
                }

                // Paso 2: firmar
                byte[] signature = new byte[cbSignature];
                int signStatus = NCryptSignHash(
                    hKey,
                    pPadding,
                    hash,
                    (uint)hash.Length,
                    signature,
                    cbSignature,
                    out uint cbUsed,
                    BCRYPT_PAD_PKCS1);

                if (signStatus != ERROR_SUCCESS)
                {
                    Debug.WriteLine($"[GestorClavesTPM] NCryptSignHash (sign) falló 0x{signStatus:X8}.");
                    return null;
                }

                if (cbUsed < cbSignature)
                    Array.Resize(ref signature, (int)cbUsed);

                return signature;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[GestorClavesTPM] FirmarConClavePermanente excepción: {ex.Message}");
                return null;
            }
            finally
            {
                if (pPadding != IntPtr.Zero)
                    Marshal.FreeHGlobal(pPadding);
                LiberarHandle(hKey);
                LiberarHandle(hProv);
            }
        }

        /// <summary>
        /// Verifica la firma de <paramref name="data"/> usando la clave pública de la clave identificada
        /// por <paramref name="nombreClave"/>. Usa RSA + SHA-256 + PKCS#1 v1.5.
        /// Devuelve false si la clave no existe, la firma es inválida o se produce algún error.
        /// </summary>
        public static bool VerificarFirmaClavePermanente(string nombreClave, byte[] data, byte[] firma)
        {
            if (string.IsNullOrWhiteSpace(nombreClave) || data == null || firma == null
                || data.Length == 0 || firma.Length == 0)
                return false;

            try
            {
                // Obtener clave pública raw (BCRYPT_RSAPUBLIC_BLOB)
                byte[]? pubKeyBlob = ObtenerClavePublicaRaw(nombreClave);
                if (pubKeyBlob == null)
                {
                    Debug.WriteLine($"[GestorClavesTPM] VerificarFirma: no se pudo obtener clave pública de '{nombreClave}'.");
                    return false;
                }

                // Importar la clave pública con RSACng a través del blob BCrypt
                using RSA rsa = RSA.Create();

                // BCrypt RSAPUBLIC BLOB: BCRYPT_RSAKEY_BLOB struct + exponent + modulus
                // Parsear el blob manualmente para importar en RSA managed
                RSAParameters rsaParams = ParseBcryptRsaPublicBlob(pubKeyBlob);
                rsa.ImportParameters(rsaParams);

                // Verificar firma
                byte[] hash = SHA256.HashData(data);
                bool result = rsa.VerifyHash(hash, firma, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
                return result;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[GestorClavesTPM] VerificarFirmaClavePermanente excepción: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Elimina la clave persistente identificada por <paramref name="nombreClave"/>.
        /// Uso exclusivo para soporte técnico autorizado.
        /// Devuelve true si la clave fue eliminada o no existía; false si falla.
        /// </summary>
        public static bool EliminarClaveIdentidad(string nombreClave)
        {
            if (string.IsNullOrWhiteSpace(nombreClave)) return false;

            IntPtr hProv = IntPtr.Zero;
            IntPtr hKey  = IntPtr.Zero;
            try
            {
                (hProv, hKey) = AbrirClaveExistente(nombreClave);
                if (hKey == IntPtr.Zero)
                {
                    // La clave no existe; se considera operación exitosa
                    Debug.WriteLine($"[GestorClavesTPM] EliminarClaveIdentidad: '{nombreClave}' no existe.");
                    return true;
                }

                // NCryptDeleteKey libera el handle hKey internamente; no llamar NCryptFreeObject después.
                int deleteStatus = NCryptDeleteKey(hKey, 0);
                hKey = IntPtr.Zero; // ya liberado por NCryptDeleteKey

                if (deleteStatus != ERROR_SUCCESS)
                {
                    Debug.WriteLine($"[GestorClavesTPM] NCryptDeleteKey falló 0x{deleteStatus:X8} para '{nombreClave}'.");
                    return false;
                }

                Debug.WriteLine($"[GestorClavesTPM] Clave '{nombreClave}' eliminada.");
                return true;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[GestorClavesTPM] EliminarClaveIdentidad excepción: {ex.Message}");
                return false;
            }
            finally
            {
                // hKey puede ser Zero si NCryptDeleteKey lo consumió
                if (hKey != IntPtr.Zero) LiberarHandle(hKey);
                LiberarHandle(hProv);
            }
        }

        // ─────────────────────────────────────────────────────────────────────────
        // Parseo de BCRYPT_RSAPUBLIC_BLOB para importar en RSA managed
        // ─────────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Parsea un BCRYPT_RSAKEY_BLOB (formato "RSAPUBLICBLOB") y devuelve los RSAParameters.
        /// Layout:
        ///   ULONG Magic        (4 bytes)  — 0x31415352 = "RSA1"
        ///   ULONG BitLength    (4 bytes)
        ///   ULONG cbPublicExp  (4 bytes)
        ///   ULONG cbModulus    (4 bytes)
        ///   ULONG cbPrime1     (4 bytes)  — 0 en public blob
        ///   ULONG cbPrime2     (4 bytes)  — 0 en public blob
        ///   BYTE  PublicExponent[cbPublicExp]
        ///   BYTE  Modulus[cbModulus]
        /// </summary>
        private static RSAParameters ParseBcryptRsaPublicBlob(byte[] blob)
        {
            if (blob == null || blob.Length < 24)
                throw new ArgumentException("Blob demasiado corto para ser un BCRYPT_RSAPUBLIC_BLOB.");

            int offset = 0;
            uint magic      = BitConverter.ToUInt32(blob, offset); offset += 4;
            uint bitLength  = BitConverter.ToUInt32(blob, offset); offset += 4;
            uint cbExp      = BitConverter.ToUInt32(blob, offset); offset += 4;
            uint cbMod      = BitConverter.ToUInt32(blob, offset); offset += 4;
            uint cbPrime1   = BitConverter.ToUInt32(blob, offset); offset += 4;
            uint cbPrime2   = BitConverter.ToUInt32(blob, offset); offset += 4;

            // Magic "RSA1" = 0x31415352
            if (magic != 0x31415352u)
                throw new InvalidOperationException($"Magic incorrecto en BCRYPT blob: 0x{magic:X8}.");

            if ((long)offset + cbExp + cbMod > blob.Length)
                throw new InvalidOperationException("Blob truncado: datos de exponent/modulus fuera de rango.");

            byte[] exponent = new byte[cbExp];
            Array.Copy(blob, offset, exponent, 0, (int)cbExp);
            offset += (int)cbExp;

            byte[] modulus = new byte[cbMod];
            Array.Copy(blob, offset, modulus, 0, (int)cbMod);

            // BCrypt almacena en big-endian; RSAParameters espera big-endian => sin cambio necesario
            return new RSAParameters
            {
                Exponent = exponent,
                Modulus  = modulus
            };
        }
    }
}
