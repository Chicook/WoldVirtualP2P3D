using System;
using System.IO;
using System.Text.Json;
using Visor3D.Seguridad.SesionUnica;

namespace Visor3D.Seguridad
{
    /// <summary>Estado de la cuenta local tal como la ve el arranque del visor.</summary>
    public enum EstadoCuenta
    {
        /// <summary>No hay ningún resto: equipo nuevo, toca el ciclo de registro completo.</summary>
        SinIdentidad,
        /// <summary>Hay credenciales con hash utilizables: el PC está registrado.</summary>
        Completa,
        /// <summary>Hay restos (perfil sin hash, llave o sello sueltos) que no permiten entrar.</summary>
        Incompleta
    }

    /// <summary>
    /// Rutas estables del perfil. Viven en %LOCALAPPDATA%\WoldVirtualP2P3D,
    /// fuera de <c>runtime\&lt;versión&gt;</c> (que AppExtractor borra en cada OTA),
    /// así que la cuenta sobrevive a las actualizaciones del visor.
    /// </summary>
    public static class PerfilUsuario
    {
        public static string BaseDir { get; } = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WoldVirtualP2P3D");

        public static string UserDir => Path.Combine(BaseDir, "user");
        public static string PerfilPath => Path.Combine(UserDir, "user_profile.json");
        public static string CredencialesPath => Path.Combine(BaseDir, "credentials.json");
        public static string LlavePath => Path.Combine(UserDir, "llave_acceso.json");

        /// <summary>
        /// Hay identidad en este PC si existe perfil, credenciales o el sello de
        /// cuenta única. Sirve para impedir una segunda cuenta aunque falte uno
        /// de los ficheros.
        /// </summary>
        public static bool TieneIdentidad =>
            File.Exists(PerfilPath) ||
            File.Exists(CredencialesPath) ||
            RegistroPcUnico.YaExisteCuentaEnEstePc();

        public static bool TieneLlave => File.Exists(LlavePath);

        /// <summary>Nombre de usuario guardado, o cadena vacía si no hay perfil legible.</summary>
        public static string NombreGuardado()
        {
            foreach (var (ruta, campo) in new[] { (PerfilPath, "nombre"), (CredencialesPath, "username") })
            {
                try
                {
                    if (!File.Exists(ruta)) continue;
                    using var doc = JsonDocument.Parse(File.ReadAllText(ruta));
                    if (doc.RootElement.TryGetProperty(campo, out var valor))
                    {
                        string nombre = valor.GetString() ?? "";
                        if (!string.IsNullOrWhiteSpace(nombre)) return nombre;
                    }
                }
                catch { /* perfil ilegible: se prueba el siguiente */ }
            }
            return "";
        }

        /// <summary>
        /// Decide si este PC puede arrancar como registrado. Sólo cuenta como
        /// cuenta completa una credencial legible con usuario y hash —las dos
        /// que acepta el login—; el perfil, la llave o el sello por separado no
        /// sirven para entrar y dejan al equipo en un callejón sin salida.
        /// </summary>
        /// <param name="motivo">Explicación para el log del arranque.</param>
        /// <param name="baseDir">Sólo para las pruebas; por defecto <see cref="BaseDir"/>.</param>
        public static EstadoCuenta Diagnosticar(out string motivo, string? baseDir = null)
        {
            string raiz = baseDir ?? BaseDir;
            string perfil = Path.Combine(raiz, "user", "user_profile.json");
            string credenciales = Path.Combine(raiz, "credentials.json");
            string llave = Path.Combine(raiz, "user", "llave_acceso.json");
            string sello = Path.Combine(raiz, "Seguridad", "pc_sello.json");

            bool hayPerfil = File.Exists(perfil);
            bool hayCredenciales = File.Exists(credenciales);
            bool hayLlave = File.Exists(llave);
            bool haySello = File.Exists(sello);

            if (CredencialUtilizable(perfil, "nombre") || CredencialUtilizable(credenciales, "username"))
            {
                motivo = "credenciales locales utilizables";
                return EstadoCuenta.Completa;
            }

            if (!hayPerfil && !hayCredenciales && !hayLlave && !haySello)
            {
                motivo = "sin restos de cuenta en el equipo";
                return EstadoCuenta.SinIdentidad;
            }

            var restos = new System.Collections.Generic.List<string>();
            if (hayPerfil) restos.Add("user_profile.json sin usuario/hash válidos");
            if (hayCredenciales) restos.Add("credentials.json sin usuario/hash válidos");
            if (hayLlave) restos.Add("llave_acceso.json suelta");
            if (haySello) restos.Add("sello de PC sin credenciales");
            motivo = "restos sin acceso: " + string.Join(", ", restos);
            return EstadoCuenta.Incompleta;
        }

        private static bool CredencialUtilizable(string ruta, string campoUsuario)
        {
            try
            {
                if (!File.Exists(ruta)) return false;
                using var doc = JsonDocument.Parse(File.ReadAllText(ruta));
                var raiz = doc.RootElement;
                string usuario = raiz.TryGetProperty(campoUsuario, out var u) ? u.GetString() ?? "" : "";
                string hash = raiz.TryGetProperty("passwordHash", out var h) ? h.GetString() ?? "" : "";
                return !string.IsNullOrWhiteSpace(usuario) && !string.IsNullOrWhiteSpace(hash);
            }
            catch { return false; }
        }

        /// <summary>
        /// Importa la cuenta de instalaciones anteriores (p. ej. %APPDATA%\WoldVirtual)
        /// cuando este equipo todavía no tiene perfil propio. Nunca sobrescribe
        /// ficheros existentes: la cuenta actual manda.
        /// </summary>
        public static bool MigrarSiProcede()
        {
            if (File.Exists(PerfilPath) || File.Exists(CredencialesPath)) return false;

            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);

            string[] origenes =
            {
                Path.Combine(local, "WoldVirtual"),
                Path.Combine(roaming, "WoldVirtual"),
            };

            bool migrado = false;
            foreach (string origen in origenes)
            {
                migrado |= CopiarSiExiste(Path.Combine(origen, "user", "user_profile.json"), PerfilPath);
                migrado |= CopiarSiExiste(Path.Combine(origen, "credentials.json"), CredencialesPath);
                migrado |= CopiarSiExiste(Path.Combine(origen, "user", "llave_acceso.json"), LlavePath);
                migrado |= CopiarSiExiste(Path.Combine(origen, "user", "semilla_wallet.json"),
                                          Path.Combine(UserDir, "semilla_wallet.json"));
            }
            return migrado;
        }

        private static bool CopiarSiExiste(string origen, string destino)
        {
            try
            {
                if (!File.Exists(origen) || File.Exists(destino)) return false;
                string? dir = Path.GetDirectoryName(destino);
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                File.Copy(origen, destino);
                return true;
            }
            catch { return false; }
        }
    }
}
