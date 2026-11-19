// SeguridadReforzada.cs — Refuerzos aditivos para SeguridadSesionUnica.
//
// Estrategias estándar de código abierto implementadas solo con la BCL de
// .NET (sin paquetes externos, para no romper el build ni la cadena de
// suministro):
//   • HKDF-SHA256 (RFC 5869)              — separación de claves por contexto.
//   • PBKDF2-HMAC-SHA256 (RFC 8018)       — derivación lenta de secretos.
//   • TOTP/HOTP (RFC 4226 y RFC 6238)     — segundo factor de un solo uso.
//   • Nonces con TTL                      — anti-replay en mensajes firmados.
//   • Token bucket                        — límite de tasa por identidad.
//   • ECDSA P-256                         — firma/verificación de atestaciones.
//   • Comparación en tiempo constante     — evita fugas por temporización.
//
// Namespace deliberadamente distinto (Visor3D.Seguridad.Reforzada) para que
// el módulo sea aditivo: no modifica ni reemplaza las clases existentes de
// Visor3D.Seguridad.SesionUnica.

using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;

namespace Visor3D.Seguridad.Reforzada
{
    /// <summary>Comparaciones y comprobaciones sin fugas de tiempo.</summary>
    public static class ComparacionConstante
    {
        /// <summary>Igualdad de bytes en tiempo dependiente solo de la longitud.</summary>
        public static bool Iguales(ReadOnlySpan<byte> a, ReadOnlySpan<byte> b) =>
            CryptographicOperations.FixedTimeEquals(a, b);

        /// <summary>Igualdad de cadenas UTF-8 sin cortocircuito por carácter.</summary>
        public static bool Iguales(string a, string b)
        {
            if (a == null || b == null) return ReferenceEquals(a, b);
            byte[] ba = Encoding.UTF8.GetBytes(a);
            byte[] bb = Encoding.UTF8.GetBytes(b);
            return CryptographicOperations.FixedTimeEquals(ba, bb);
        }
    }

    /// <summary>Funciones de derivación de claves.</summary>
    public static class Kdf
    {
        private const int HashLen = 32;

        /// <summary>
        /// HKDF-SHA256 (RFC 5869): extrae entropía y expande con etiqueta de
        /// contexto. Dos módulos con el mismo secreto obtienen claves distintas.
        /// </summary>
        public static byte[] HkdfSha256(byte[] ikm, byte[]? salt, string info, int length)
        {
            return HkdfSha256(ikm, salt, Encoding.UTF8.GetBytes(info ?? ""), length);
        }

        /// <summary>Variante byte a byte de HKDF-SHA256 (interoperable con RFC 5869).</summary>
        public static byte[] HkdfSha256(byte[] ikm, byte[]? salt, byte[]? info, int length)
        {
            if (ikm == null || ikm.Length == 0) throw new ArgumentException("ikm vacío", nameof(ikm));
            if (length < 1 || length > 255 * HashLen)
                throw new ArgumentOutOfRangeException(nameof(length));
            byte[] sal = salt != null && salt.Length > 0 ? salt : new byte[HashLen];
            byte[] prk;
            using (var extractor = new HMACSHA256(sal))
                prk = extractor.ComputeHash(ikm);

            byte[] infoBytes = info ?? Array.Empty<byte>();
            byte[] okm = new byte[length];
            byte[] bloque = Array.Empty<byte>();
            int escrito = 0;
            byte contador = 1;
            using (var expander = new HMACSHA256(prk))
            {
                while (escrito < length)
                {
                    byte[] entrada = new byte[bloque.Length + infoBytes.Length + 1];
                    Buffer.BlockCopy(bloque, 0, entrada, 0, bloque.Length);
                    Buffer.BlockCopy(infoBytes, 0, entrada, bloque.Length, infoBytes.Length);
                    entrada[^1] = contador;
                    bloque = expander.ComputeHash(entrada);
                    int copiar = Math.Min(HashLen, length - escrito);
                    Buffer.BlockCopy(bloque, 0, okm, escrito, copiar);
                    escrito += copiar;
                    contador++;
                }
            }
            CryptographicOperations.ZeroMemory(prk);
            return okm;
        }

        /// <summary>PBKDF2-HMAC-SHA256 (RFC 8018) con sal aleatoria de 16 bytes.</summary>
        public static byte[] Pbkdf2(string password, byte[] salt, int iteraciones, int length)
        {
            if (password == null) throw new ArgumentNullException(nameof(password));
            if (salt == null || salt.Length < 8) throw new ArgumentException("sal débil", nameof(salt));
            if (iteraciones < 100_000) throw new ArgumentOutOfRangeException(nameof(iteraciones));
            return Rfc2898DeriveBytes.Pbkdf2(
                Encoding.UTF8.GetBytes(password), salt, iteraciones,
                HashAlgorithmName.SHA256, length);
        }
    }

    /// <summary>
    /// Registro de nonces vistos recientemente. Un nonce repetido dentro de su
    /// ventana se rechaza: la reinyección de un mensaje firmado válido falla.
    /// </summary>
    public sealed class RegistroNonces
    {
        private readonly Dictionary<string, long> _expira = new(StringComparer.Ordinal);
        private readonly object _sync = new();
        private readonly long _ttlMs;
        private readonly int _maximo;

        public RegistroNonces(TimeSpan? ttl = null, int maximo = 100_000)
        {
            _ttlMs = (long)(ttl ?? TimeSpan.FromSeconds(30)).TotalMilliseconds;
            _maximo = maximo > 0 ? maximo : throw new ArgumentOutOfRangeException(nameof(maximo));
        }

        public int Activos
        {
            get { lock (_sync) return _expira.Count; }
        }

        /// <summary>Registra el nonce; devuelve false si ya estaba vivo (replay).</summary>
        public bool IntentarRegistrar(string nonce, DateTimeOffset ahora)
        {
            if (string.IsNullOrEmpty(nonce)) return false;
            long t = ahora.ToUnixTimeMilliseconds();
            lock (_sync)
            {
                PurgarLock(t);
                if (_expira.ContainsKey(nonce)) return false;
                if (_expira.Count >= _maximo) return false;
                _expira[nonce] = t + _ttlMs;
                return true;
            }
        }

        public int Purgar(DateTimeOffset ahora)
        {
            lock (_sync) return PurgarLock(ahora.ToUnixTimeMilliseconds());
        }

        private int PurgarLock(long t)
        {
            List<string>? caducados = null;
            foreach (var par in _expira)
            {
                if (par.Value > t) continue;
                (caducados ??= new List<string>()).Add(par.Key);
            }
            if (caducados == null) return 0;
            foreach (var clave in caducados) _expira.Remove(clave);
            return caducados.Count;
        }
    }

    /// <summary>Limitador de tasa por cubo de fichas, seguro entre hilos.</summary>
    public sealed class LimitadorFichas
    {
        private struct Cubo
        {
            public double Fichas;
            public long UltimoMs;
        }

        private readonly Dictionary<string, Cubo> _cubos = new(StringComparer.Ordinal);
        private readonly object _sync = new();
        private readonly double _capacidad;
        private readonly double _recargaPorMs;

        public LimitadorFichas(double capacidad = 10.0, double recargaPorSegundo = 2.0)
        {
            if (capacidad <= 0) throw new ArgumentOutOfRangeException(nameof(capacidad));
            if (recargaPorSegundo <= 0) throw new ArgumentOutOfRangeException(nameof(recargaPorSegundo));
            _capacidad = capacidad;
            _recargaPorMs = recargaPorSegundo / 1000.0;
        }

        /// <summary>Intenta consumir fichas; devuelve también las restantes.</summary>
        public bool IntentarConsumir(string clave, out double restantes,
                                     DateTimeOffset ahora, double costo = 1.0)
        {
            if (string.IsNullOrEmpty(clave)) throw new ArgumentException("clave vacía", nameof(clave));
            if (costo <= 0 || costo > _capacidad)
                throw new ArgumentOutOfRangeException(nameof(costo));

            long t = ahora.ToUnixTimeMilliseconds();
            lock (_sync)
            {
                Cubo cubo = _cubos.TryGetValue(clave, out Cubo previo)
                    ? previo
                    : new Cubo { Fichas = _capacidad, UltimoMs = t };

                double transcurrido = Math.Max(0, t - cubo.UltimoMs);
                cubo.Fichas = Math.Min(_capacidad, cubo.Fichas + transcurrido * _recargaPorMs);
                bool permitido = cubo.Fichas >= costo;
                if (permitido) cubo.Fichas -= costo;
                cubo.UltimoMs = t;
                _cubos[clave] = cubo;
                restantes = cubo.Fichas;
                return permitido;
            }
        }
    }

    public enum OtpHash
    {
        Sha1 = 0,
        Sha256 = 1,
        Sha512 = 2,
    }

    /// <summary>TOTP/HOTP según RFC 4226 y RFC 6238.</summary>
    public static class Totp
    {
        private const string AlfabetoBase32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

        /// <summary>Genera el código de 6-8 dígitos para el instante indicado.</summary>
        public static string Generar(byte[] secreto, DateTimeOffset instante,
                                     int digitos = 6, int periodo = 30,
                                     OtpHash hash = OtpHash.Sha1)
        {
            if (secreto == null || secreto.Length == 0)
                throw new ArgumentException("secreto vacío", nameof(secreto));
            if (digitos < 6 || digitos > 8) throw new ArgumentOutOfRangeException(nameof(digitos));
            if (periodo <= 0) throw new ArgumentOutOfRangeException(nameof(periodo));

            long contador = instante.ToUnixTimeSeconds() / periodo;
            byte[] mensaje = new byte[8];
            BinaryPrimitives.WriteInt64BigEndian(mensaje, contador);

            byte[] mac = Hmac(secreto, mensaje, hash);
            int desplazamiento = mac[^1] & 0x0F;
            int binario =
                ((mac[desplazamiento] & 0x7F) << 24) |
                ((mac[desplazamiento + 1] & 0xFF) << 16) |
                ((mac[desplazamiento + 2] & 0xFF) << 8) |
                (mac[desplazamiento + 3] & 0xFF);
            int modulo = (int)Math.Pow(10, digitos);
            return (binario % modulo).ToString(new string('0', digitos));
        }

        /// <summary>
        /// Verifica un código admitiendo ±1 periodo de desfase de reloj.
        /// Usa comparación en tiempo constante.
        /// </summary>
        public static bool Verificar(byte[] secreto, string codigo, DateTimeOffset instante,
                                     int digitos = 6, int periodo = 30,
                                     OtpHash hash = OtpHash.Sha1, int ventana = 1)
        {
            if (string.IsNullOrEmpty(codigo)) return false;
            for (int desfase = -ventana; desfase <= ventana; desfase++)
            {
                string esperado = Generar(
                    secreto, instante.AddSeconds(desfase * (double)periodo),
                    digitos, periodo, hash);
                if (ComparacionConstante.Iguales(esperado, codigo)) return true;
            }
            return false;
        }

        private static byte[] Hmac(byte[] clave, byte[] mensaje, OtpHash hash)
        {
            switch (hash)
            {
                case OtpHash.Sha256:
                    using (var h = new HMACSHA256(clave)) return h.ComputeHash(mensaje);
                case OtpHash.Sha512:
                    using (var h = new HMACSHA512(clave)) return h.ComputeHash(mensaje);
                default:
                    using (var h = new HMACSHA1(clave)) return h.ComputeHash(mensaje);
            }
        }
    }

    /// <summary>
    /// Firma y verificación de atestaciones de sesión con ECDSA P-256.
    /// La clave privada se genera con CNG y se exporta solo si se solicita.
    /// </summary>
    public sealed class AtestacionEcdsa : IDisposable
    {
        private readonly ECDsa _clave;

        private AtestacionEcdsa(ECDsa clave) => _clave = clave;

        public static AtestacionEcdsa Generar()
        {
            var clave = ECDsa.Create(ECCurve.NamedCurves.nistP256);
            return new AtestacionEcdsa(clave);
        }

        /// <summary>Clave pública en formato SubjectPublicKeyInfo (base-64).</summary>
        public string ClavePublicaBase64 =>
            Convert.ToBase64String(_clave.ExportSubjectPublicKeyInfo());

        /// <summary>Firma SHA-256 sobre los datos (formato DER de ECDSA).</summary>
        public byte[] Firmar(ReadOnlySpan<byte> datos) =>
            _clave.SignData(datos, HashAlgorithmName.SHA256);

        /// <summary>Verifica una firma con la clave pública SPKI en base-64.</summary>
        public static bool Verificar(string clavePublicaBase64, ReadOnlySpan<byte> datos,
                                     byte[] firma)
        {
            if (string.IsNullOrEmpty(clavePublicaBase64) || firma == null || firma.Length == 0)
                return false;
            try
            {
                using var clave = ECDsa.Create();
                clave.ImportSubjectPublicKeyInfo(Convert.FromBase64String(clavePublicaBase64), out _);
                return clave.VerifyData(datos, firma, HashAlgorithmName.SHA256);
            }
            catch (CryptographicException)
            {
                return false;
            }
            catch (FormatException)
            {
                return false;
            }
        }

        public void Dispose() => _clave.Dispose();
    }
}
