using System;
using System.Security.Cryptography;
using System.Text;

namespace Visor3D.Seguridad
{
    /// <summary>
    /// Hash de contraseñas con PBKDF2-SHA256 (sal por usuario) y verificación del
    /// formato antiguo (SHA-256 sin sal) para migrar cuentas sin perder acceso.
    /// Formato: pbkdf2-sha256$iteraciones$sal_base64$hash_base64
    /// </summary>
    public static class PasswordHasher
    {
        private const int Iteraciones = 210_000;
        private const int SaltBytes = 16;
        private const int KeyBytes = 32;
        private const string Prefijo = "pbkdf2-sha256";

        public static string Hash(string password)
        {
            byte[] salt = RandomNumberGenerator.GetBytes(SaltBytes);
            byte[] key = Rfc2898DeriveBytes.Pbkdf2(
                password, salt, Iteraciones, HashAlgorithmName.SHA256, KeyBytes);

            return $"{Prefijo}${Iteraciones}${Convert.ToBase64String(salt)}${Convert.ToBase64String(key)}";
        }

        /// <summary>
        /// Verifica una contraseña. Si el valor guardado es del formato antiguo
        /// (SHA-256 sin sal), devuelve true y marca <paramref name="necesitaMigracion"/>.
        /// </summary>
        public static bool Verify(string password, string? stored, out bool necesitaMigracion)
        {
            necesitaMigracion = false;
            if (string.IsNullOrWhiteSpace(stored)) return false;

            if (stored.StartsWith(Prefijo + "$", StringComparison.Ordinal))
            {
                string[] partes = stored.Split('$');
                if (partes.Length != 4 || !int.TryParse(partes[1], out int iteraciones) || iteraciones <= 0)
                    return false;

                try
                {
                    byte[] salt = Convert.FromBase64String(partes[2]);
                    byte[] esperado = Convert.FromBase64String(partes[3]);
                    byte[] real = Rfc2898DeriveBytes.Pbkdf2(
                        password, salt, iteraciones, HashAlgorithmName.SHA256, esperado.Length);

                    return CryptographicOperations.FixedTimeEquals(real, esperado);
                }
                catch
                {
                    return false;
                }
            }

            // Formato antiguo: SHA-256 hexadecimal sin sal.
            string legado = Convert.ToHexString(
                SHA256.HashData(Encoding.UTF8.GetBytes(password))).ToLowerInvariant();

            bool coincide = CryptographicOperations.FixedTimeEquals(
                Encoding.ASCII.GetBytes(legado),
                Encoding.ASCII.GetBytes(stored.Trim().ToLowerInvariant()));

            if (coincide) necesitaMigracion = true;
            return coincide;
        }
    }
}
