using System;
using System.IO;
using Visor3D.Seguridad;
using Visor3D.Seguridad.SesionUnica;
using Xunit;

namespace Visor3D.Tests
{
    /// <summary>
    /// Reinicio de la base de usuarios (F2 del issue #38 y el bloque 2.6.4).
    /// Se pasa siempre baseDir/godotDir temporales: el reset borra en bloque, así
    /// que ejecutarlo contra %LOCALAPPDATA%\WoldVirtualP2P3D real sería perder la cuenta.
    /// </summary>
    public sealed class ReinicioCuentaPruebas : IDisposable
    {
        private readonly string _carpeta;
        private readonly string _raiz;
        private readonly string _motor;

        public ReinicioCuentaPruebas()
        {
            _carpeta = Path.Combine(Path.GetTempPath(), "wvp_reset_" + Guid.NewGuid().ToString("N"));
            _raiz = Path.Combine(_carpeta, "local");
            _motor = Path.Combine(_carpeta, "godot");
            Directory.CreateDirectory(_raiz);
            Directory.CreateDirectory(_motor);
        }

        public void Dispose()
        {
            try { Directory.Delete(_carpeta, recursive: true); } catch { }
        }

        private static void Escribir(string ruta, string contenido)
        {
            string? dir = Path.GetDirectoryName(ruta);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            File.WriteAllText(ruta, contenido);
        }

        /// <summary>Equipo ya registrado, con cachés del motor y diagnóstico local.</summary>
        private void ConCuentaYMotor()
        {
            Escribir(Path.Combine(_raiz, "credentials.json"), """{"username":"ana","passwordHash":"h"}""");
            Escribir(Path.Combine(_raiz, "user", "user_profile.json"), """{"nombre":"ana","passwordHash":"h"}""");
            Escribir(Path.Combine(_raiz, "user", "llave_acceso.json"), """{"k":"v"}""");
            Escribir(Path.Combine(_raiz, "user", "semilla_wallet.json"), """{"semilla":"x"}""");
            Escribir(Path.Combine(_raiz, "Seguridad", "pc_sello.json"), """{"sello":"y"}""");
            Escribir(Path.Combine(_raiz, "cloudflared.exe"), "binario");
            Escribir(Path.Combine(_raiz, "logs", "visor-20261105.log"), "linea");
            Directory.CreateDirectory(Path.Combine(_raiz, "runtime", "2.7.7"));

            Escribir(Path.Combine(_motor, "registro.cfg"), "[state]");
            Escribir(Path.Combine(_motor, "avatar_hash.json"), "{}");
            Escribir(Path.Combine(_motor, "carrusel", "turno.cfg"), "[turno]");
            Escribir(Path.Combine(_motor, "shader_cache", "a.tmp"), "cache");
        }

        private string[] Respaldos()
        {
            string carpeta = Path.Combine(_raiz, "respaldo_cuenta");
            return Directory.Exists(carpeta) ? Directory.GetDirectories(carpeta) : Array.Empty<string>();
        }

        [Fact]
        public void El_reinicio_archiva_la_identidad_y_deja_el_equipo_sin_cuenta()
        {
            ConCuentaYMotor();

            Assert.True(ReinicioCuenta.EjecutarSiProcede("2.7.7", _raiz, _motor));

            Assert.False(File.Exists(Path.Combine(_raiz, "credentials.json")));
            Assert.False(File.Exists(Path.Combine(_raiz, "user", "user_profile.json")));
            Assert.False(File.Exists(Path.Combine(_raiz, "user", "llave_acceso.json")));
            Assert.False(File.Exists(Path.Combine(_raiz, "Seguridad", "pc_sello.json")));
            Assert.False(File.Exists(Path.Combine(_motor, "registro.cfg")));
            Assert.False(Directory.Exists(Path.Combine(_motor, "carrusel")));

            Assert.Equal(EstadoCuenta.SinIdentidad, PerfilUsuario.Diagnosticar(out _, _raiz));

            // Archivado, no borrado: todo sigue existiendo dentro de respaldo_cuenta.
            string respaldo = Respaldos()[0];
            Assert.True(File.Exists(Path.Combine(respaldo, "credentials.json")));
            Assert.True(File.Exists(Path.Combine(respaldo, "user_profile.json")));
            Assert.True(File.Exists(Path.Combine(respaldo, "semilla_wallet.json")));
            Assert.True(File.Exists(Path.Combine(respaldo, "avatar_hash.json")));
            Assert.True(Directory.Exists(Path.Combine(respaldo, "carrusel")));
        }

        [Fact]
        public void El_reinicio_conserva_runtime_logs_y_caches_del_motor()
        {
            ConCuentaYMotor();

            ReinicioCuenta.EjecutarSiProcede("2.7.7", _raiz, _motor);

            Assert.True(Directory.Exists(Path.Combine(_raiz, "runtime", "2.7.7")));
            Assert.True(File.Exists(Path.Combine(_raiz, "logs", "visor-20261105.log")));
            Assert.True(Directory.Exists(Path.Combine(_motor, "shader_cache")));
        }

        [Fact]
        public void El_marcador_por_version_evita_repetirlo_en_el_mismo_arranque()
        {
            ConCuentaYMotor();
            Assert.True(ReinicioCuenta.EjecutarSiProcede("2.7.7", _raiz, _motor));
            Assert.Single(Respaldos());

            Assert.False(ReinicioCuenta.EjecutarSiProcede("2.7.7", _raiz, _motor));
            Assert.Single(Respaldos());
            Assert.Equal("2.7.7", File.ReadAllText(Path.Combine(_raiz, "reset_cuenta.txt")).Trim());
        }

        [Fact]
        public void Una_version_nueva_vuelve_a_reiniciar_y_refresca_el_marcador()
        {
            ConCuentaYMotor();
            ReinicioCuenta.EjecutarSiProcede("2.7.7", _raiz, _motor);

            // El usuario vuelve a registrarse y llega 2.7.8: el reset por versión aplica otra vez.
            Escribir(Path.Combine(_raiz, "credentials.json"), """{"username":"otro","passwordHash":"h2"}""");
            Assert.True(ReinicioCuenta.EjecutarSiProcede("2.7.8", _raiz, _motor));

            Assert.False(File.Exists(Path.Combine(_raiz, "credentials.json")));
            Assert.Equal("2.7.8", File.ReadAllText(Path.Combine(_raiz, "reset_cuenta.txt")).Trim());

            // El respaldo se nombra por segundo: dos reinicios seguidos caen en la misma
            // carpeta y RutaLibre desambigua con sufijo _2, no crea una segunda carpeta.
            string respaldo = Respaldos()[0];
            Assert.True(File.Exists(Path.Combine(respaldo, "credentials.json")));
            Assert.True(File.Exists(Path.Combine(respaldo, "credentials_2.json")));
        }

        [Fact]
        public void Equipo_nuevo_sin_restos_se_marca_sin_dejar_fallos_pendientes()
        {
            // Archivar() devuelve true cuando el fichero no existía: no hay nada que
            // respaldar y el arranque no debe reintentar el reset en cada sesión.
            Assert.True(ReinicioCuenta.EjecutarSiProcede("2.7.7", _raiz, _motor));
            Assert.Equal("2.7.7", File.ReadAllText(Path.Combine(_raiz, "reset_cuenta.txt")).Trim());
            Assert.Equal("2.7.7", File.ReadAllText(Path.Combine(_motor, "reset_flag.txt")));
        }

        [Fact]
        public void Reset_total_es_unico_y_respeta_la_cuenta_posterior()
        {
            ConCuentaYMotor();
            Assert.True(ReinicioCuenta.EjecutarResetTotal("2.7.7", _raiz, _motor));
            Assert.True(ReinicioCuenta.ResetTotalHecho(_raiz));

            Escribir(Path.Combine(_raiz, "credentials.json"), """{"username":"nueva","passwordHash":"h"}""");

            Assert.False(ReinicioCuenta.EjecutarResetTotal("2.7.8", _raiz, _motor));
            Assert.True(File.Exists(Path.Combine(_raiz, "credentials.json")));
        }

        [Fact]
        public void Reset_total_deja_tambien_el_marcador_por_version()
        {
            // Línea 195: escribe reset_cuenta.txt a la vez, para que el reset por versión
            // no arrastre otra copia de una cuenta ya archivada en el mismo arranque.
            ConCuentaYMotor();
            ReinicioCuenta.EjecutarResetTotal("2.6.4", _raiz, _motor);

            Assert.Equal("2.6.4", File.ReadAllText(Path.Combine(_raiz, "reset_cuenta.txt")).Trim());
            Assert.False(ReinicioCuenta.EjecutarSiProcede("2.6.4", _raiz, _motor));
        }

        [Fact]
        public void Reset_total_barra_todo_salvo_runtime_logs_cloudflared_y_caches()
        {
            ConCuentaYMotor();
            Escribir(Path.Combine(_raiz, "islas.json"), "{}");

            Assert.True(ReinicioCuenta.EjecutarResetTotal("2.7.7", _raiz, _motor));

            Assert.True(Directory.Exists(Path.Combine(_raiz, "runtime")));
            Assert.True(Directory.Exists(Path.Combine(_raiz, "logs")));
            Assert.True(File.Exists(Path.Combine(_raiz, "cloudflared.exe")));
            Assert.True(Directory.Exists(Path.Combine(_motor, "shader_cache")));

            Assert.False(File.Exists(Path.Combine(_raiz, "islas.json")));
            Assert.False(File.Exists(Path.Combine(_raiz, "Seguridad", "pc_sello.json")));
            Assert.False(File.Exists(Path.Combine(_motor, "registro.cfg")));

            Assert.Contains(Directory.GetDirectories(Path.Combine(_raiz, "respaldo_cuenta")),
                            d => Path.GetFileName(d).StartsWith("reset-total-"));
        }

        [Fact]
        public void Limpiar_estado_godot_no_toca_el_perfil_local()
        {
            ConCuentaYMotor();

            Assert.True(ReinicioCuenta.LimpiarEstadoGodot("equipo-sin-cuenta", _raiz, _motor));

            Assert.False(File.Exists(Path.Combine(_motor, "registro.cfg")));
            Assert.Equal("equipo-sin-cuenta", File.ReadAllText(Path.Combine(_motor, "reset_flag.txt")));
            Assert.True(File.Exists(Path.Combine(_raiz, "credentials.json")));
            Assert.True(File.Exists(Path.Combine(_raiz, "user", "user_profile.json")));
        }

        [Fact]
        public void Limpiar_estado_godot_sin_restos_devuelve_false()
        {
            Assert.False(ReinicioCuenta.LimpiarEstadoGodot("equipo-sin-cuenta", _raiz, _motor));
            Assert.Empty(Respaldos());
        }
    }
}
