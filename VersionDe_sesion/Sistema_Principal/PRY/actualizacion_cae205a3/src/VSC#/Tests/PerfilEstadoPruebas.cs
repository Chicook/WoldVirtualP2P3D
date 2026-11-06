using System;
using System.IO;
using System.Text.Json;
using Visor3D.Seguridad;
using Xunit;

namespace Visor3D.Tests
{
    /// <summary>
    /// Diagnóstico de cuenta (PerfilUsuario) y estado del equipo (EstadoGlobal).
    /// Ambos aceptan baseDir/godotDir «sólo para las pruebas»; aquí se pasan siempre
    /// a un directorio temporal para no leer ni escribir %LOCALAPPDATA%\WoldVirtualP2P3D.
    /// </summary>
    public sealed class PerfilEstadoPruebas : IDisposable
    {
        private readonly string _carpeta;

        public PerfilEstadoPruebas()
        {
            _carpeta = Path.Combine(Path.GetTempPath(), "wvp_perfil_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_carpeta);
        }

        public void Dispose()
        {
            try { Directory.Delete(_carpeta, recursive: true); } catch { }
        }

        private string CarpetaNueva(string nombre)
        {
            string ruta = Path.Combine(_carpeta, nombre);
            Directory.CreateDirectory(ruta);
            return ruta;
        }

        private static void Escribir(string ruta, string contenido)
        {
            string? dir = Path.GetDirectoryName(ruta);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            File.WriteAllText(ruta, contenido);
        }

        [Fact]
        public void Credenciales_con_usuario_y_hash_son_cuenta_completa()
        {
            string raiz = CarpetaNueva("completa");
            Escribir(Path.Combine(raiz, "credentials.json"),
                     """{"username":"ana","passwordHash":"scrypt$1$abc"}""");

            var estado = PerfilUsuario.Diagnosticar(out string motivo, raiz);

            Assert.Equal(EstadoCuenta.Completa, estado);
            Assert.Contains("credenciales locales utilizables", motivo);
        }

        [Fact]
        public void Perfil_con_nombre_y_hash_tambien_registra_el_equipo()
        {
            string raiz = CarpetaNueva("perfil");
            Escribir(Path.Combine(raiz, "user", "user_profile.json"),
                     """{"nombre":"ana","passwordHash":"scrypt$1$abc"}""");

            Assert.Equal(EstadoCuenta.Completa, PerfilUsuario.Diagnosticar(out _, raiz));
        }

        [Fact]
        public void Nombre_sin_hash_no_da_acceso_y_deja_los_restos_en_el_motivo()
        {
            string raiz = CarpetaNueva("sinhash");
            Escribir(Path.Combine(raiz, "user", "user_profile.json"), """{"nombre":"ana"}""");

            var estado = PerfilUsuario.Diagnosticar(out string motivo, raiz);

            Assert.Equal(EstadoCuenta.Incompleta, estado);
            Assert.Contains("user_profile.json sin usuario/hash válidos", motivo);
        }

        [Fact]
        public void Directorio_vacio_es_equipo_sin_identidad()
        {
            string raiz = CarpetaNueva("nuevo");

            var estado = PerfilUsuario.Diagnosticar(out string motivo, raiz);

            Assert.Equal(EstadoCuenta.SinIdentidad, estado);
            Assert.Contains("sin restos", motivo);
        }

        [Fact]
        public void Json_ilegible_cuenta_como_resto_no_como_acceso()
        {
            // Un credentials.json roto es peor que no tenerlo: impide el alta limpia
            // y obliga a «reparar», que es lo que el arranque tiene que avisar.
            string raiz = CarpetaNueva("roto");
            Escribir(Path.Combine(raiz, "credentials.json"), "{ esto no es json");

            Assert.Equal(EstadoCuenta.Incompleta, PerfilUsuario.Diagnosticar(out _, raiz));
        }

        [Fact]
        public void Llave_suelta_se_nombra_en_el_motivo_del_log()
        {
            string raiz = CarpetaNueva("llave");
            Escribir(Path.Combine(raiz, "user", "llave_acceso.json"), """{"k":"v"}""");

            var estado = PerfilUsuario.Diagnosticar(out string motivo, raiz);

            Assert.Equal(EstadoCuenta.Incompleta, estado);
            Assert.Contains("llave_acceso.json suelta", motivo);
        }

        [Fact]
        public void Estado_global_equipo_nuevo_pide_registro_completo()
        {
            string raiz = CarpetaNueva("eg-nuevo");
            string motor = CarpetaNueva("eg-motor-nuevo");

            var estado = EstadoGlobal.Actualizar(raiz, motor);

            Assert.Equal("vacio", estado.Equipo);
            Assert.Equal("registro-completo", estado.Accion);
            Assert.True(estado.FaltaTodo);
            Assert.DoesNotContain(true, estado.Necesario.Values);
        }

        [Fact]
        public void Estado_global_con_cuenta_completa_da_acceso_directo()
        {
            string raiz = CarpetaNueva("eg-completo");
            string motor = CarpetaNueva("eg-motor-completo");
            Escribir(Path.Combine(raiz, "credentials.json"),
                     """{"username":"ana","passwordHash":"scrypt$1$abc"}""");

            var estado = EstadoGlobal.Actualizar(raiz, motor);

            Assert.Equal("completo", estado.Equipo);
            Assert.Equal("acceso", estado.Accion);
            Assert.False(estado.FaltaTodo);
            Assert.True(estado.Necesario["credenciales"]);
        }

        [Fact]
        public void Estado_global_motor_con_ficheros_y_sin_cuenta_toca_reparar()
        {
            // Medido: el registro.cfg del motor no entra en PerfilUsuario.Diagnosticar,
            // así que restos de motor sin credenciales caen en «incompleto/reparar»,
            // nunca en «registro-completo».
            string raiz = CarpetaNueva("eg-restos");
            string motor = CarpetaNueva("eg-motor-restos");
            Escribir(Path.Combine(motor, "registro.cfg"), "[state]");

            var estado = EstadoGlobal.Actualizar(raiz, motor);

            Assert.Equal("incompleto", estado.Equipo);
            Assert.Equal("reparar", estado.Accion);
            Assert.True(estado.Necesario["motor"]);
        }

        [Fact]
        public void Estado_global_se_persiste_con_el_esquema_corto()
        {
            string raiz = CarpetaNueva("eg-json");
            string motor = CarpetaNueva("eg-motor-json");
            Escribir(Path.Combine(raiz, "user", "user_profile.json"),
                     """{"nombre":"ana","passwordHash":"scrypt$1$abc"}""");

            EstadoGlobal.Actualizar(raiz, motor);

            using var doc = JsonDocument.Parse(File.ReadAllText(Path.Combine(raiz, EstadoGlobal.Archivo)));
            Assert.Equal("completo", doc.RootElement.GetProperty("equipo").GetString());
            Assert.Equal("acceso", doc.RootElement.GetProperty("accion").GetString());
            Assert.True(doc.RootElement.GetProperty("necesario").GetProperty("perfil").GetBoolean());
            Assert.True(doc.RootElement.TryGetProperty("ts", out _));
        }
    }
}
