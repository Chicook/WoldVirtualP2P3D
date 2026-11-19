using System;
using System.Security.Cryptography;
using System.Text;
using Visor3D.Seguridad;
using Xunit;

namespace Visor3D.Tests
{
    /// <summary>
    /// Hash y verificación de contraseñas, incluida la migración del formato
    /// antiguo (SHA-256 sin sal). Un fallo aquí deja fuera al usuario de su cuenta,
    /// que es exactamente lo que el proyecto no debe permitir al actualizar.
    /// </summary>
    public class PasswordHasherTests
    {
        [Fact]
        public void Hash_y_Verify_hacen_roundtrip()
        {
            string hash = PasswordHasher.Hash("Clave-Ñ-Ünicode-123");

            Assert.StartsWith("pbkdf2-sha256$", hash, StringComparison.Ordinal);
            Assert.True(PasswordHasher.Verify("Clave-Ñ-Ünicode-123", hash, out bool migrar));
            Assert.False(migrar);
        }

        [Fact]
        public void Hash_usa_sal_aleatoria()
        {
            Assert.NotEqual(PasswordHasher.Hash("misma"), PasswordHasher.Hash("misma"));
        }

        [Fact]
        public void Verify_con_clave_incorrecta_devuelve_false()
        {
            Assert.False(PasswordHasher.Verify("otra", PasswordHasher.Hash("clave"), out _));
        }

        [Theory]
        [InlineData(null)]
        [InlineData("")]
        [InlineData("   ")]
        public void Verify_sin_valor_guardado_devuelve_false(string? guardado)
        {
            Assert.False(PasswordHasher.Verify("x", guardado, out _));
        }

        [Theory]
        [InlineData("pbkdf2-sha256$abc$def")]            // faltan partes
        [InlineData("pbkdf2-sha256$0$AAAA$AAAA")]        // iteraciones inválidas
        [InlineData("pbkdf2-sha256$1000$no-base64$AAAA")] // sal no decodificable
        public void Verify_con_formato_corrupto_devuelve_false(string guardado)
        {
            Assert.False(PasswordHasher.Verify("x", guardado, out _));
        }

        [Fact]
        public void Verify_migra_el_formato_antiguo_sin_sal()
        {
            string legado = Convert.ToHexString(
                SHA256.HashData(Encoding.UTF8.GetBytes("clave-antigua"))).ToLowerInvariant();

            Assert.True(PasswordHasher.Verify("clave-antigua", legado, out bool migrar));
            Assert.True(migrar);
        }

        [Fact]
        public void Verify_legado_con_clave_incorrecta_no_migra()
        {
            string legado = Convert.ToHexString(
                SHA256.HashData(Encoding.UTF8.GetBytes("clave-antigua"))).ToLowerInvariant();

            Assert.False(PasswordHasher.Verify("otra", legado, out bool migrar));
            Assert.False(migrar);
        }
    }
}
