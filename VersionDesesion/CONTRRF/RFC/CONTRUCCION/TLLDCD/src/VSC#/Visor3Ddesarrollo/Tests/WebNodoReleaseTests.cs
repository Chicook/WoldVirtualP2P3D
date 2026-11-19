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

        [Theory]
        [InlineData("v2.8.6", false)]
        [InlineData(" V2.8.7 ", true)]
        [InlineData("v2.9.0", true)]
        [InlineData("desconocida", false)]
        public void Remota_no_degrada_la_instalada(string version, bool aceptada)
        {
            var local = (Name: "DAO-preview.exe", Url: "", SizeMb: "—", Version: "2.8.7");
            var remota = (Name: "DAO.exe", Url: "https://example.invalid/official", SizeMb: "20", Version: version);
            Assert.Equal(aceptada ? remota : local,
                WebNodoService.SeleccionarRelease(local, remota, "2.8.7"));
            Assert.Equal(version.Trim().TrimStart('v', 'V') == "2.8.7",
                WebNodoService.EsVersionInstalada(version, "2.8.7"));
        }

        [Fact]
        public void Semilla_antigua_no_anuncia_version_inferior_al_runtime()
        {
            var r = WebNodoService.NormalizarReleaseLocal(("Antiguo.exe", "https://example.invalid/old", "1", "0.0.0"));
            Assert.Equal(WebNodoService.VersionInstalada, r.Version);
            Assert.Equal("", r.Url);
            Assert.NotEqual("Antiguo.exe", r.Name);
        }

        [Fact]
        public void No_retrocede_un_anuncio_remoto_mas_nuevo()
        {
            var actual = (Name: "Nuevo.exe", Url: "https://example.invalid/new", SizeMb: "20", Version: "3.1.0");
            Assert.Equal(actual, WebNodoService.SeleccionarRelease(actual,
                ("Anterior.exe", "https://example.invalid/old", "10", "3.0.0"), "2.8.7"));
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

            var r = WebNodoService.LeerReleaseParaPrueba(ruta);

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

            var r = WebNodoService.LeerReleaseParaPrueba(ruta);

            Assert.Equal("1.2.3", r.Version);
            Assert.Equal("1.0", r.SizeMb);
        }

        [Fact]
        public void Sin_release_cae_al_nombre_del_ensamblado()
        {
            string ruta = Path.Combine(Path.GetTempPath(), "no_existe_" + Guid.NewGuid().ToString("N") + ".json");

            var r = WebNodoService.LeerReleaseParaPrueba(ruta);

            Assert.Equal((System.Reflection.Assembly.GetEntryAssembly()?.GetName().Name ??
                typeof(WebNodoService).Assembly.GetName().Name ?? "Visor3D") + ".exe", r.Name);
            Assert.Equal(WebNodoService.VersionInstalada, r.Version);
        }

        [Fact]
        public void Release_corrupto_cae_al_nombre_del_ensamblado()
        {
            var r = WebNodoService.LeerReleaseParaPrueba(EscribirRelease("{ esto no es json"));

            Assert.EndsWith(".exe", r.Name, StringComparison.OrdinalIgnoreCase);
            Assert.Equal(WebNodoService.VersionInstalada, r.Version);
        }

        [Fact]
        public void Sin_asset_exe_cae_al_nombre_del_ensamblado()
        {
            string ruta = EscribirRelease(@"{
  ""tag_name"": ""v3.0.0"",
  ""assets"": [ { ""name"": ""WoldVirtualP2P3Dv3.0.0-linux.tar.gz"", ""size"": 5, ""url"": ""https://example.invalid/l"" } ]
}");

            var r = WebNodoService.LeerReleaseParaPrueba(ruta);

            Assert.Equal((System.Reflection.Assembly.GetEntryAssembly()?.GetName().Name ??
                typeof(WebNodoService).Assembly.GetName().Name ?? "Visor3D") + ".exe", r.Name);
        }
    }
}
