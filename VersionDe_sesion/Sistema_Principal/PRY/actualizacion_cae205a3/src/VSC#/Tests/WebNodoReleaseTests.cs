using System;
using System.IO;
using Visor3D.Services;
using Xunit;

namespace Visor3D.Tests
{
    /// <summary>
    /// Lectura del <c>release.json</c> por el WebNodo (causa 1 de W-01/DT-11). El
    /// pipeline publica <c>{ tag_name, name, version, assets[] }</c>; si el lector
    /// no entiende ese esquema, el portal anuncia un binario equivocado y la
    /// descarga apunta a una versión que no es la instalada.
    /// </summary>
    public class WebNodoReleaseTests
    {
        private static string EscribirRelease(string json)
        {
            string dir = Path.Combine(Path.GetTempPath(), "wvp3d_tests_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            string ruta = Path.Combine(dir, "release.json");
            File.WriteAllText(ruta, json);
            return ruta;
        }

        [Fact]
        public void Lee_el_esquema_publicado_con_assets()
        {
            string ruta = EscribirRelease(@"{
  ""tag_name"": ""v9.9.9"",
  ""name"": ""Prueba"",
  ""version"": ""9.9.9"",
  ""assets"": [
    { ""name"": ""DMWoldVirtualP2P3Dv9.9.9-linux.tar.gz"", ""size"": 100, ""url"": ""https://example.invalid/linux"" },
    { ""name"": ""DMWoldVirtualP2P3Dv9.9.9.exe"", ""size"": 12345678, ""url"": ""https://example.invalid/exe"" }
  ]
}");

            var r = AnuncioRelease.LeerReleaseParaPrueba(ruta);

            Assert.Equal("DMWoldVirtualP2P3Dv9.9.9.exe", r.Name);
            Assert.Equal("https://example.invalid/exe", r.Url);
            Assert.Equal("9.9.9", r.Version);
            Assert.Equal("11.8", r.SizeMb);
        }

        [Fact]
        public void Deriva_la_version_del_tag_si_falta_version()
        {
            string ruta = EscribirRelease(@"{
  ""tag_name"": ""v1.2.3"",
  ""assets"": [ { ""name"": ""Visor.exe"", ""size"": 1048576, ""url"": ""https://example.invalid/v"" } ]
}");

            var r = AnuncioRelease.LeerReleaseParaPrueba(ruta);

            Assert.Equal("1.2.3", r.Version);
            Assert.Equal("1.0", r.SizeMb);
        }

        [Fact]
        public void Sin_release_cae_al_nombre_del_ensamblado()
        {
            string ruta = Path.Combine(Path.GetTempPath(), "no_existe_" + Guid.NewGuid().ToString("N") + ".json");

            var r = AnuncioRelease.LeerReleaseParaPrueba(ruta);

            Assert.Equal($"DMWoldVirtualP2P3Dv{AnuncioRelease.VersionInstalada}.exe", r.Name);
            Assert.Equal(AnuncioRelease.VersionInstalada, r.Version);
        }

        [Fact]
        public void Release_corrupto_cae_al_nombre_del_ensamblado()
        {
            var r = AnuncioRelease.LeerReleaseParaPrueba(EscribirRelease("{ esto no es json"));

            Assert.EndsWith(".exe", r.Name, StringComparison.OrdinalIgnoreCase);
            Assert.Equal(AnuncioRelease.VersionInstalada, r.Version);
        }

        [Fact]
        public void Sin_asset_exe_cae_al_nombre_del_ensamblado()
        {
            string ruta = EscribirRelease(@"{
  ""tag_name"": ""v3.0.0"",
  ""assets"": [ { ""name"": ""WoldVirtualP2P3Dv3.0.0-linux.tar.gz"", ""size"": 5, ""url"": ""https://example.invalid/l"" } ]
}");

            var r = AnuncioRelease.LeerReleaseParaPrueba(ruta);

            Assert.Equal($"DMWoldVirtualP2P3Dv{AnuncioRelease.VersionInstalada}.exe", r.Name);
        }
    }
}
