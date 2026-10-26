using System;
using System.IO;
using System.Text.Json;
using Visor3D.Seguridad.SesionUnica;

namespace Visor3D.Seguridad
{
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
