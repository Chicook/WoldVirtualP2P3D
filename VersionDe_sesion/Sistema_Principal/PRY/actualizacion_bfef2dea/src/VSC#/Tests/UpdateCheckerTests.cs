using System;
using Visor3D.Update;
using Xunit;

namespace Visor3D.Tests
{
    /// <summary>
    /// Normalización de versiones de <see cref="UpdateChecker"/>. Es la lógica que
    /// decide si hay actualización, así que un fallo aquí rompe el OTA en silencio
    /// (lección de W-01: el asset puede llevar la versión real en el nombre).
    /// </summary>
    public class UpdateCheckerTests
    {
        [Theory]
        [InlineData("v1.2.0", 1, 2, 0)]
        [InlineData("0.0.012", 0, 0, 12)]
        [InlineData("1.2.3-beta.1", 1, 2, 3)]
        [InlineData("v2.7.5", 2, 7, 5)]
        [InlineData("release-3.0", 3, 0, 0)]
        public void ParseVersion_normaliza_tags(string tag, int a, int b, int c)
        {
            Assert.Equal(new Version(a, b, c, 0), UpdateChecker.ParseVersion(tag));
        }

        [Theory]
        [InlineData(null)]
        [InlineData("")]
        [InlineData("   ")]
        [InlineData("sin-numeros")]
        public void ParseVersion_sin_numero_devuelve_null(string? tag)
        {
            Assert.Null(UpdateChecker.ParseVersion(tag));
        }

        [Theory]
        [InlineData("DMWoldVirtualP2P3Dv2.7.5.exe", 2, 7, 5)]
        [InlineData("DMWoldVirtualp2pCNXv0.0.013_actualizacion_049ac229.exe", 0, 0, 13)]
        [InlineData("WoldVirtualP2P3Dv2.7.4-linux.tar.gz", 2, 7, 4)]
        public void ParseAssetVersion_extrae_del_nombre(string fichero, int a, int b, int c)
        {
            Assert.Equal(new Version(a, b, c, 0), UpdateChecker.ParseAssetVersion(fichero));
        }

        [Theory]
        [InlineData("Visor3D.exe")]              // «3D» no es una versión
        [InlineData("DMWoldVirtualP2P3D.exe")]   // el «3D» del nombre no cuenta
        [InlineData("hash_b5592aff.exe")]        // un hash hexadecimal no es una versión
        [InlineData(null)]
        public void ParseAssetVersion_ignora_numeros_irrelevantes(string? fichero)
        {
            Assert.Null(UpdateChecker.ParseAssetVersion(fichero));
        }

        /// <summary>
        /// El tag y el nombre del binario pueden discrepar: el OTA reutiliza la
        /// misma release sustituyendo sólo el asset. La versión efectiva es la
        /// mayor de las dos (regla del proyecto), y en un tag con «3D» las letras
        /// no deben aportar dígitos falsos.
        /// </summary>
        [Fact]
        public void Version_del_asset_manda_sobre_un_tag_antiguo()
        {
            var tag = UpdateChecker.ParseVersion("v2.7.5");
            var asset = UpdateChecker.ParseAssetVersion("DMWoldVirtualP2P3Dv2.7.6.exe");

            Assert.NotNull(asset);
            Assert.True(asset! > tag);
        }

        [Fact]
        public void ParseVersion_no_confunde_las_letras_del_nombre()
        {
            // A diferencia de ParseAssetVersion, ParseVersion toma el primer bloque
            // numérico, así que en un nombre de fichero daría «2»: por eso el OTA
            // usa ParseAssetVersion para los assets.
            Assert.Equal(new Version(2, 0, 0, 0), UpdateChecker.ParseVersion("DMWoldVirtualP2P3Dv2.7.5.exe"));
        }
    }
}
