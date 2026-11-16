// =============================================================================
// SelloCuenta.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Bloque Canónico de Cadena Local y Autocustodia (v3)
// =============================================================================

using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Modelo canónico del bloque de identidad 1:1 para la cadena local append-only.
    ///
    /// Separación estricta de dominios:
    ///   - idCuentaHash: Identificador público de cuenta, generado de entropía pura CSPRNG.
    ///   - hashBloque: Huella SHA-256 de la serialización canónica del bloque.
    ///   - compromisoRecuperacion: SHA-256(codigoRecuperacion || salt). El código NUNCA se persiste.
    ///   - firmaEcdsa / mac: Firma ECDSA P-256 (v3) o HMAC-SHA256 (v2) sobre el texto canónico.
    ///   - clavePublicaEcdsa: Clave pública ECDSA P-256 (formato SPKI / Base64) para verificación.
    /// </summary>
    public sealed class SelloCuenta
    {
        public const int VersionActual = 3;
        public const string ContextoDominioV2 = "WoldVirtualP2P3D::BloqueCadena::v2";
        public const string ContextoDominioV3 = "WoldVirtualP2P3D::BloqueCadena::v3";
        public const string DominioCuentaId = "WoldVirtualP2P3D::AccountID::v3";

        // ── Campos Canónicos de la Cadena ─────────────────────────────────────

        [JsonPropertyName("versionFormato")]
        public int VersionFormato { get; set; } = VersionActual;

        [JsonPropertyName("idCuentaHash")]
        public string IdCuentaHash { get; set; } = "";

        [JsonPropertyName("indice")]
        public long Indice { get; set; } = 0;

        [JsonPropertyName("hashPrevio")]
        public string HashPrevio { get; set; } = new string('0', 64);

        [JsonPropertyName("contador")]
        public long Contador { get; set; } = 1;

        [JsonPropertyName("timestampUtc")]
        public long TimestampUtc { get; set; } = DateTimeOffset.UtcNow.ToUnixTimeSeconds();

        [JsonPropertyName("huellaAnonimizada")]
        public string HuellaAnonimizada { get; set; } = "";

        [JsonPropertyName("salt")]
        public string Salt { get; set; } = "";

        [JsonPropertyName("compromisoRecuperacion")]
        public string CompromisoRecuperacion { get; set; } = "";

        [JsonPropertyName("keyId")]
        public string KeyId { get; set; } = "k1_ecdsa_p256";

        [JsonPropertyName("clavePublicaEcdsa")]
        public string ClavePublicaEcdsa { get; set; } = "";

        [JsonPropertyName("firmaEcdsa")]
        public string FirmaEcdsa { get; set; } = "";

        [JsonPropertyName("mac")]
        public string Mac { get; set; } = ""; // Para bloques v2 y compatibilidad hacia atrás

        [JsonPropertyName("hashBloque")]
        public string HashBloque { get; set; } = "";

        [JsonPropertyName("componentesHardware")]
        public List<string> ComponentesHardware { get; set; } = new();

        [JsonPropertyName("nivelProteccion")]
        public string NivelProteccion { get; set; } = "Dpapi";

        [JsonPropertyName("nota")]
        public string Nota { get; set; } = "Bloque de Identidad Canónica v3 — WoldVirtualP2P3D Zero Trust";

        // ── Propiedades de Compatibilidad hacia atrás (v1 / v2 / adaptadores) ─────

        [JsonIgnore]
        public int Version { get => VersionFormato; set => VersionFormato = value; }

        [JsonIgnore]
        public string CuentaId { get => IdCuentaHash; set => IdCuentaHash = value; }

        [JsonIgnore]
        public string BloqueId { get => HashBloque; set => HashBloque = value; }

        [JsonIgnore]
        public long ContadorMonotonico { get => Contador; set => Contador = value; }

        [JsonIgnore]
        public string MacFirma { get => string.IsNullOrWhiteSpace(FirmaEcdsa) ? Mac : FirmaEcdsa; set { if (VersionFormato >= 3) FirmaEcdsa = value; else Mac = value; } }

        [JsonIgnore]
        public string ClaveRecuperacionHash { get => CompromisoRecuperacion; set => CompromisoRecuperacion = value; }

        // ─────────────────────────────────────────────────────────────────────
        // Generación Criptográfica de Identificador de Cuenta
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Genera un nuevo identificador público de cuenta (idCuentaHash) a partir
        /// de entropía criptográfica aleatoria con separación de dominio.
        /// No depende de hardware, marcas de tiempo ni datos personales.
        /// </summary>
        public static string GenerarIdCuentaAleatorio()
        {
            byte[] entropy = new byte[32];
            RandomNumberGenerator.Fill(entropy);

            byte[] domainBytes = Encoding.UTF8.GetBytes(DominioCuentaId);
            byte[] payload = new byte[domainBytes.Length + entropy.Length];
            Buffer.BlockCopy(domainBytes, 0, payload, 0, domainBytes.Length);
            Buffer.BlockCopy(entropy, 0, payload, domainBytes.Length, entropy.Length);

            using var sha = SHA256.Create();
            byte[] hash = sha.ComputeHash(payload);
            CryptographicOperations.ZeroMemory(entropy);

            return Convert.ToHexString(hash).ToLowerInvariant();
        }

        // ─────────────────────────────────────────────────────────────────────
        // Serialización Canónica e Inequívoca
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Obtiene la representación canónica determinista del bloque para cálculo de hash.
        /// Formato delimitado libre de ambigüedades.
        /// </summary>
        public string ObtenerTextoCanonico()
        {
            if (VersionFormato >= 3)
            {
                return $"V:{VersionFormato}|ID:{IdCuentaHash}|IDX:{Indice}|PREV:{HashPrevio}|" +
                       $"CNT:{Contador}|TS:{TimestampUtc}|HW:{HuellaAnonimizada}|" +
                       $"SALT:{Salt}|REC:{CompromisoRecuperacion}|KEY:{KeyId}|PUB:{ClavePublicaEcdsa}";
            }

            // Formato Canónico v2
            return $"V:{VersionFormato}|ID:{IdCuentaHash}|IDX:{Indice}|PREV:{HashPrevio}|" +
                   $"CNT:{Contador}|TS:{TimestampUtc}|HW:{HuellaAnonimizada}|" +
                   $"SALT:{Salt}|REC:{CompromisoRecuperacion}|KEY:{KeyId}";
        }

        /// <summary>
        /// Calcula el hash SHA-256 del bloque sobre su serialización canónica.
        /// </summary>
        public string ComputarHashBloque()
        {
            byte[] bytes = Encoding.UTF8.GetBytes(ObtenerTextoCanonico());
            using var sha = SHA256.Create();
            return Convert.ToHexString(sha.ComputeHash(bytes)).ToLowerInvariant();
        }

        /// <summary>
        /// Obtiene el payload binario canónico para cálculo de firma o MAC.
        /// </summary>
        public byte[] ObtenerPayloadParaFirma(byte[] huellaComprometida)
        {
            string canonico = ObtenerTextoCanonico();
            byte[] baseBytes = Encoding.UTF8.GetBytes(canonico);
            byte[] full = new byte[baseBytes.Length + 1 + huellaComprometida.Length];
            Buffer.BlockCopy(baseBytes, 0, full, 0, baseBytes.Length);
            full[baseBytes.Length] = (byte)'|';
            Buffer.BlockCopy(huellaComprometida, 0, full, baseBytes.Length + 1, huellaComprometida.Length);
            return full;
        }

        // ─────────────────────────────────────────────────────────────────────
        // Firma y Verificación Criptográfica (ECDSA v3 + HMAC v2)
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Firma el bloque v3 con clave privada ECDSA P-256.
        /// </summary>
        public void FirmarEcdsa(ECDsa clavePrivada, byte[] huellaComprometida)
        {
            VersionFormato = 3;
            ClavePublicaEcdsa = Convert.ToBase64String(clavePrivada.ExportSubjectPublicKeyInfo());
            HashBloque = ComputarHashBloque();
            byte[] payload = ObtenerPayloadParaFirma(huellaComprometida);
            byte[] firma = clavePrivada.SignData(payload, HashAlgorithmName.SHA256);
            FirmaEcdsa = Convert.ToBase64String(firma);
        }

        /// <summary>
        /// Verifica la firma ECDSA P-256 de un bloque v3.
        /// </summary>
        public bool VerificarEcdsa(byte[] huellaComprometida, ECDsa? claveVerificadora = null)
        {
            if (string.IsNullOrWhiteSpace(FirmaEcdsa)) return false;

            // 1. Verificar hash canónico del bloque
            string hashEsperado = ComputarHashBloque();
            byte[] hashEspBytes = Encoding.UTF8.GetBytes(hashEsperado);
            byte[] hashLeidoBytes = Encoding.UTF8.GetBytes(HashBloque ?? "");
            if (!CryptographicOperations.FixedTimeEquals(hashEspBytes, hashLeidoBytes))
                return false;

            // 2. Verificar firma ECDSA P-256
            byte[] payload = ObtenerPayloadParaFirma(huellaComprometida);
            byte[] firmaBytes;
            try { firmaBytes = Convert.FromBase64String(FirmaEcdsa); }
            catch { return false; }

            if (claveVerificadora != null)
            {
                return claveVerificadora.VerifyData(payload, firmaBytes, HashAlgorithmName.SHA256);
            }

            if (string.IsNullOrWhiteSpace(ClavePublicaEcdsa)) return false;
            try
            {
                using var ecdsa = ECDsa.Create();
                ecdsa.ImportSubjectPublicKeyInfo(Convert.FromBase64String(ClavePublicaEcdsa), out _);
                return ecdsa.VerifyData(payload, firmaBytes, HashAlgorithmName.SHA256);
            }
            catch
            {
                return false;
            }
        }

        /// <summary>
        /// Firma v2 basada en HMAC (para compatibilidad de cadena existente).
        /// </summary>
        public void FirmarHmac(byte[] secretoClave, byte[] huellaComprometida)
        {
            HashBloque = ComputarHashBloque();
            byte[] payload = ObtenerPayloadParaFirma(huellaComprometida);
            using var hmac = new HMACSHA256(secretoClave);
            byte[] hash = hmac.ComputeHash(payload);
            Mac = Convert.ToHexString(hash).ToLowerInvariant();
        }

        /// <summary>
        /// Verifica el MAC HMAC de un bloque v2.
        /// </summary>
        public bool VerificarMac(byte[] secretoClave, byte[] huellaComprometida)
        {
            if (string.IsNullOrWhiteSpace(Mac)) return false;

            string hashEsperado = ComputarHashBloque();
            byte[] hashEspBytes = Encoding.UTF8.GetBytes(hashEsperado);
            byte[] hashLeidoBytes = Encoding.UTF8.GetBytes(HashBloque ?? "");
            if (!CryptographicOperations.FixedTimeEquals(hashEspBytes, hashLeidoBytes))
                return false;

            byte[] payload = ObtenerPayloadParaFirma(huellaComprometida);
            using var hmac = new HMACSHA256(secretoClave);
            byte[] macCalculado = hmac.ComputeHash(payload);

            byte[] macLeido;
            try { macLeido = Convert.FromHexString(Mac); }
            catch { return false; }

            return CryptographicOperations.FixedTimeEquals(macCalculado, macLeido);
        }

        /// <summary>
        /// Método de verificación unificado que soporta verificación dual:
        /// - Para v3: Verifica firma ECDSA P-256.
        /// - Para v2: Verifica MAC HMAC-SHA256.
        /// </summary>
        public bool VerificarAutenticidad(byte[] secretoHmac, byte[] huellaComprometida, ECDsa? claveEcdsa = null)
        {
            if (VersionFormato >= 3)
            {
                return VerificarEcdsa(huellaComprometida, claveEcdsa);
            }
            return VerificarMac(secretoHmac, huellaComprometida);
        }

        // ─────────────────────────────────────────────────────────────────────
        // Generación y Validación de Código de Recuperación (Base32)
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Genera un nuevo par de recuperación: código aleatorio de 32 bytes con sal de 32 bytes,
        /// calculando el compromiso SHA-256(código || sal).
        /// Devuelve el código formateado en Base32 con checksum Crockford para mostrar UNA SOLA VEZ.
        /// </summary>
        public static void GenerarNuevoParRecuperacion(
            out byte[] codigoRaw32,
            out string saltHex,
            out string compromisoHex,
            out string codigoBase32Legible)
        {
            codigoRaw32 = new byte[32];
            byte[] saltBytes = new byte[32];
            RandomNumberGenerator.Fill(codigoRaw32);
            RandomNumberGenerator.Fill(saltBytes);

            saltHex = Convert.ToHexString(saltBytes).ToLowerInvariant();

            // Compromiso = SHA-256(codigo || salt)
            byte[] combinado = new byte[64];
            Buffer.BlockCopy(codigoRaw32, 0, combinado, 0, 32);
            Buffer.BlockCopy(saltBytes, 0, combinado, 32, 32);

            using var sha = SHA256.Create();
            byte[] compBytes = sha.ComputeHash(combinado);
            compromisoHex = Convert.ToHexString(compBytes).ToLowerInvariant();

            // Formatear en Base32 con checksum integrado de 2 bytes
            codigoBase32Legible = CodificadorBase32.CodificarConChecksum(codigoRaw32);
        }

        /// <summary>
        /// Verifica un código en Base32 introducido por el usuario contra el compromiso y la sal.
        /// Utiliza comparación en tiempo constante (FixedTimeEquals).
        /// </summary>
        public static bool VerificarCodigoRecuperacion(
            string codigoBase32,
            string saltHex,
            string compromisoHexEsperado)
        {
            if (string.IsNullOrWhiteSpace(codigoBase32) ||
                string.IsNullOrWhiteSpace(saltHex) ||
                string.IsNullOrWhiteSpace(compromisoHexEsperado))
                return false;

            byte[]? codigoBytes = CodificadorBase32.DecodificarConChecksum(codigoBase32);
            if (codigoBytes == null || codigoBytes.Length != 32)
                return false;

            try
            {
                byte[] saltBytes;
                byte[] compEsperado;
                try
                {
                    saltBytes = Convert.FromHexString(saltHex);
                    compEsperado = Convert.FromHexString(compromisoHexEsperado);
                }
                catch { return false; }

                if (saltBytes.Length != 32 || compEsperado.Length != 32)
                    return false;

                byte[] combinado = new byte[64];
                Buffer.BlockCopy(codigoBytes, 0, combinado, 0, 32);
                Buffer.BlockCopy(saltBytes, 0, combinado, 32, 32);

                using var sha = SHA256.Create();
                byte[] compCalculado = sha.ComputeHash(combinado);

                return CryptographicOperations.FixedTimeEquals(compCalculado, compEsperado);
            }
            finally
            {
                CryptographicOperations.ZeroMemory(codigoBytes);
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // Migraciones: v1 -> v3 y v2 -> v3
        // ─────────────────────────────────────────────────────────────────────

        public static bool EsFormatoV1(string json)
        {
            if (string.IsNullOrWhiteSpace(json)) return false;
            try
            {
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;
                return root.TryGetProperty("uuid", out _) && root.TryGetProperty("firma", out _);
            }
            catch { return false; }
        }

        public static SelloCuenta MigrarDesdeV1(
            string jsonV1,
            ECDsa claveEcdsa,
            byte[] huellaBytes,
            out string codigoRecuperacionGenerado)
        {
            using var doc = JsonDocument.Parse(jsonV1);
            string uuid = doc.RootElement.GetProperty("uuid").GetString() ?? Guid.NewGuid().ToString("N");

            byte[] uuidBytes = Encoding.UTF8.GetBytes(uuid);
            byte[] domBytes = Encoding.UTF8.GetBytes(DominioCuentaId);
            byte[] payload = new byte[domBytes.Length + uuidBytes.Length];
            Buffer.BlockCopy(domBytes, 0, payload, 0, domBytes.Length);
            Buffer.BlockCopy(uuidBytes, 0, payload, domBytes.Length, uuidBytes.Length);
            using var sha = SHA256.Create();
            string idCuenta = Convert.ToHexString(sha.ComputeHash(payload)).ToLowerInvariant();

            GenerarNuevoParRecuperacion(out byte[] rawCode, out string salt, out string compromiso, out codigoRecuperacionGenerado);
            CryptographicOperations.ZeroMemory(rawCode);

            var hwLista = MaquinaHuellaDigital.ObtenerComponentes().ObtenerLista();

            var bloqueMigrado = new SelloCuenta
            {
                VersionFormato = VersionActual,
                IdCuentaHash = idCuenta,
                Indice = 0,
                HashPrevio = new string('0', 64),
                Contador = 1,
                TimestampUtc = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
                HuellaAnonimizada = MaquinaHuellaDigital.Obtener(),
                Salt = salt,
                CompromisoRecuperacion = compromiso,
                KeyId = "k1_ecdsa_p256",
                ComponentesHardware = new List<string>(hwLista),
                Nota = "Bloque Génesis v3 Migrado desde Sello v1 — WoldVirtualP2P3D"
            };

            bloqueMigrado.FirmarEcdsa(claveEcdsa, huellaBytes);
            return bloqueMigrado;
        }

        public static SelloCuenta MigrarDesdeV2(
            SelloCuenta selloV2,
            ECDsa claveEcdsa,
            byte[] huellaBytes)
        {
            var bloqueV3 = new SelloCuenta
            {
                VersionFormato = VersionActual,
                IdCuentaHash = selloV2.IdCuentaHash,
                Indice = selloV2.Indice + 1,
                HashPrevio = selloV2.HashBloque,
                Contador = selloV2.Contador + 1,
                TimestampUtc = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
                HuellaAnonimizada = MaquinaHuellaDigital.Obtener(),
                Salt = selloV2.Salt,
                CompromisoRecuperacion = selloV2.CompromisoRecuperacion,
                KeyId = "k1_ecdsa_p256",
                ComponentesHardware = new List<string>(selloV2.ComponentesHardware),
                Nota = "Bloque v3 Migrado desde Sello v2 — WoldVirtualP2P3D"
            };

            bloqueV3.FirmarEcdsa(claveEcdsa, huellaBytes);
            return bloqueV3;
        }

        // ─────────────────────────────────────────────────────────────────────
        // Serialización JSON
        // ─────────────────────────────────────────────────────────────────────

        public string Serializar() =>
            JsonSerializer.Serialize(this, new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            });

        public static SelloCuenta? Deserializar(string json)
        {
            if (string.IsNullOrWhiteSpace(json)) return null;
            try
            {
                var s = JsonSerializer.Deserialize<SelloCuenta>(json);
                if (s != null && string.IsNullOrWhiteSpace(s.IdCuentaHash) && !string.IsNullOrWhiteSpace(s.CuentaId))
                {
                    s.IdCuentaHash = s.CuentaId;
                }
                return s;
            }
            catch { return null; }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Codificador Base32 con Checksum (Crockford-safe)
    // ─────────────────────────────────────────────────────────────────────────

    public static class CodificadorBase32
    {
        // Alfabeto Crockford canónico de 32 símbolos (0-9, A-Z excluyendo I, L, O, U)
        private const string Alfabeto = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

        public static string CodificarConChecksum(byte[] datos)
        {
            if (datos == null || datos.Length == 0) return string.Empty;

            using var sha = SHA256.Create();
            byte[] hash = sha.ComputeHash(datos);
            byte[] conChecksum = new byte[datos.Length + 2];
            Buffer.BlockCopy(datos, 0, conChecksum, 0, datos.Length);
            conChecksum[datos.Length] = hash[0];
            conChecksum[datos.Length + 1] = hash[1];

            string base32 = CodificarCrudo(conChecksum);

            // Agrupación legible de 4 en 4 (ej. XXXX-XXXX-...)
            var sb = new StringBuilder();
            for (int i = 0; i < base32.Length; i++)
            {
                if (i > 0 && i % 4 == 0) sb.Append('-');
                sb.Append(base32[i]);
            }
            return sb.ToString();
        }

        public static byte[]? DecodificarConChecksum(string base32ConFormato)
        {
            if (string.IsNullOrWhiteSpace(base32ConFormato)) return null;

            string limpia = base32ConFormato.Replace("-", "").Replace(" ", "").Trim().ToUpperInvariant();
            // Normalización de caracteres ambiguos según Crockford
            limpia = limpia.Replace('I', '1').Replace('L', '1').Replace('O', '0');

            byte[]? decodificado = DecodificarCrudo(limpia);
            if (decodificado == null || decodificado.Length < 3) return null;

            int payloadLen = decodificado.Length - 2;
            byte[] payload = new byte[payloadLen];
            Buffer.BlockCopy(decodificado, 0, payload, 0, payloadLen);

            using var sha = SHA256.Create();
            byte[] hash = sha.ComputeHash(payload);

            byte check1 = decodificado[payloadLen];
            byte check2 = decodificado[payloadLen + 1];

            if (check1 != hash[0] || check2 != hash[1])
            {
                CryptographicOperations.ZeroMemory(payload);
                return null; // Checksum inválido
            }

            return payload;
        }

        private static string CodificarCrudo(byte[] datos)
        {
            var sb = new StringBuilder();
            int bitBuffer = 0;
            int bitCount = 0;

            foreach (byte b in datos)
            {
                bitBuffer = (bitBuffer << 8) | b;
                bitCount += 8;
                while (bitCount >= 5)
                {
                    bitCount -= 5;
                    int index = (bitBuffer >> bitCount) & 0x1F;
                    sb.Append(Alfabeto[index]);
                    bitBuffer &= (1 << bitCount) - 1;
                }
            }

            if (bitCount > 0)
            {
                int index = (bitBuffer << (5 - bitCount)) & 0x1F;
                sb.Append(Alfabeto[index]);
            }

            return sb.ToString();
        }

        private static byte[]? DecodificarCrudo(string base32)
        {
            var bytes = new List<byte>();
            int bitBuffer = 0;
            int bitCount = 0;

            foreach (char c in base32)
            {
                int val = Alfabeto.IndexOf(c);
                if (val < 0) return null;

                bitBuffer = (bitBuffer << 5) | val;
                bitCount += 5;

                if (bitCount >= 8)
                {
                    bitCount -= 8;
                    bytes.Add((byte)((bitBuffer >> bitCount) & 0xFF));
                    bitBuffer &= (1 << bitCount) - 1;
                }
            }

            return bytes.ToArray();
        }
    }
}
