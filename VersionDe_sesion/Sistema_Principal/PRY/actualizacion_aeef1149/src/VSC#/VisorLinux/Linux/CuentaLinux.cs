using System;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Visor3D.Linux;
using Visor3D.Seguridad;
using Visor3D.Seguridad.SesionUnica;
using Visor3D.Services;

namespace Visor3D.Linux
{
    /// <summary>
    /// Cuenta local del visor Linux con el mismo formato de ficheros que el
    /// visor de Windows (<c>user/user_profile.json</c>, <c>credentials.json</c>
    /// y sello de equipo), de modo que una carpeta de perfil pueda moverse
    /// entre ambos equipos.
    /// </summary>
    public static class CuentaLinux
    {
        public readonly struct Resultado
        {
            public bool Ok { get; }
            public string Mensaje { get; }
            public string Uuid { get; }

            private Resultado(bool ok, string mensaje, string uuid)
            {
                Ok = ok;
                Mensaje = mensaje;
                Uuid = uuid;
            }

            public static Resultado Bien(string mensaje, string uuid = "") => new(true, mensaje, uuid);
            public static Resultado Mal(string mensaje) => new(false, mensaje, "");
        }

        public static EstadoCuenta Estado(out string motivo) => PerfilUsuario.Diagnosticar(out motivo);

        public static bool HayCuenta => PerfilUsuario.Diagnosticar(out _) == EstadoCuenta.Completa;

        public static string NombreGuardado() => PerfilUsuario.NombreGuardado();

        /// <summary>Crea la cuenta única de este equipo (nombre + contraseña).</summary>
        public static Resultado Crear(string nombre, string password, string repetir)
        {
            nombre = (nombre ?? "").Trim();

            if (PerfilUsuario.TieneIdentidad)
                return Resultado.Mal("Este equipo ya tiene una cuenta. Sólo se permite UNA cuenta por equipo.");

            if (nombre.Length < 3)
                return Resultado.Mal("El nombre de usuario debe tener al menos 3 caracteres.");
            if (password.Length < 6)
                return Resultado.Mal("La contraseña debe tener al menos 6 caracteres.");
            if (password != repetir)
                return Resultado.Mal("Las contraseñas no coinciden.");

            try
            {
                string uuid = Guid.NewGuid().ToString();
                string hash = PasswordHasher.Hash(password);

                Directory.CreateDirectory(PerfilUsuario.UserDir);

                var perfil = new JsonObject
                {
                    ["uuid"] = uuid,
                    ["nombre"] = nombre,
                    ["passwordHash"] = hash,
                    ["hardwareHash"] = RegistroPcUnico.Obtener(),
                    ["plataforma"] = "linux",
                    ["creado"] = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                };
                Escribir(PerfilUsuario.PerfilPath, perfil.ToJsonString(Opciones));

                var credenciales = new JsonObject
                {
                    ["username"] = nombre,
                    ["passwordHash"] = hash,
                };
                Escribir(PerfilUsuario.CredencialesPath, credenciales.ToJsonString(Opciones));

                RegistroPcUnico.RegistrarCuenta(uuid);
                VisorLog.Info($"[cuenta] Cuenta Linux creada para «{nombre}» ({uuid[..8]}…).");
                return Resultado.Bien("Cuenta creada. Ya puedes entrar al mundo.", uuid);
            }
            catch (Exception ex)
            {
                VisorLog.Error("[cuenta] No se pudo crear la cuenta", ex);
                return Resultado.Mal($"No se pudo guardar la cuenta: {ex.Message}");
            }
        }

        /// <summary>Valida nombre y contraseña contra el perfil y las credenciales locales.</summary>
        public static Resultado Acceder(string nombre, string password)
        {
            nombre = (nombre ?? "").Trim();
            if (nombre.Length == 0 || password.Length == 0)
                return Resultado.Mal("Escribe tu nombre y tu contraseña.");

            if (Validar(PerfilUsuario.PerfilPath, "nombre", nombre, password) ||
                Validar(PerfilUsuario.CredencialesPath, "username", nombre, password))
            {
                string uuid = UuidDe(nombre);
                VisorLog.Info($"[cuenta] Acceso local correcto para «{nombre}».");
                return Resultado.Bien("Acceso concedido.", uuid);
            }

            // Los usuarios que vienen del paquete Linux "sólo Godot" tienen nick
            // en registro.cfg pero aún no han creado cuenta en el visor.
            return Resultado.Mal("Nombre o contraseña incorrectos.");
        }

        /// <summary>Nick que el motor guardó en <c>user://registro.cfg</c>, si lo hay.</summary>
        public static string NickDeGodot()
        {
            try
            {
                string cfg = Path.Combine(RutasLinux.GodotUserDir, "registro.cfg");
                if (!File.Exists(cfg)) return "";

                bool enJugador = false;
                foreach (string lineaCruda in File.ReadLines(cfg))
                {
                    string linea = lineaCruda.Trim();
                    if (linea.StartsWith("[", StringComparison.Ordinal))
                    {
                        enJugador = linea.Equals("[jugador]", StringComparison.OrdinalIgnoreCase);
                        continue;
                    }
                    if (!enJugador || !linea.StartsWith("nick", StringComparison.OrdinalIgnoreCase)) continue;

                    int igual = linea.IndexOf('=');
                    if (igual < 0) continue;
                    // ConfigFile escribe cadenas entre comillas: nick="Lucía"
                    return linea[(igual + 1)..].Trim().Trim('"');
                }
            }
            catch { /* registro ilegible: no se propone nick */ }
            return "";
        }

        public static string SemillaNueva(int palabras = 12)
            => string.Join(' ', Bip39.Generate(palabras));

        private static readonly JsonSerializerOptions Opciones = new()
        {
            WriteIndented = true,
            Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        };

        private static void Escribir(string ruta, string contenido)
        {
            string? dir = Path.GetDirectoryName(ruta);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

            string temporal = ruta + ".tmp";
            File.WriteAllText(temporal, contenido, new UTF8Encoding(false));
            File.Move(temporal, ruta, overwrite: true);
        }

        private static bool Validar(string ruta, string campoUsuario, string nombre, string password)
        {
            try
            {
                if (!File.Exists(ruta)) return false;
                using var doc = JsonDocument.Parse(File.ReadAllText(ruta, Encoding.UTF8));
                var raiz = doc.RootElement;

                string guardado = raiz.TryGetProperty(campoUsuario, out var u) ? u.GetString() ?? "" : "";
                string hash = raiz.TryGetProperty("passwordHash", out var h) ? h.GetString() ?? "" : "";

                if (!guardado.Equals(nombre, StringComparison.OrdinalIgnoreCase)) return false;
                if (!PasswordHasher.Verify(password, hash, out bool migrar)) return false;

                if (migrar) MigrarHash(ruta, password);
                return true;
            }
            catch
            {
                return false;
            }
        }

        private static void MigrarHash(string ruta, string password)
        {
            try
            {
                if (JsonNode.Parse(File.ReadAllText(ruta, Encoding.UTF8)) is not JsonObject obj) return;
                obj["passwordHash"] = PasswordHasher.Hash(password);
                obj["hashVersion"] = 2;
                Escribir(ruta, obj.ToJsonString(Opciones));
            }
            catch { /* si no se puede migrar, el acceso ya se concedió */ }
        }

        private static string UuidDe(string nombre)
        {
            foreach (var (ruta, campo) in new[]
                     {
                         (PerfilUsuario.PerfilPath, "nombre"),
                         (PerfilUsuario.CredencialesPath, "username"),
                     })
            {
                try
                {
                    if (!File.Exists(ruta)) continue;
                    using var doc = JsonDocument.Parse(File.ReadAllText(ruta, Encoding.UTF8));
                    var raiz = doc.RootElement;
                    string guardado = raiz.TryGetProperty(campo, out var u) ? u.GetString() ?? "" : "";
                    if (!guardado.Equals(nombre, StringComparison.OrdinalIgnoreCase)) continue;

                    foreach (string clave in new[] { "uuid", "id", "userId" })
                    {
                        if (raiz.TryGetProperty(clave, out var v) && !string.IsNullOrWhiteSpace(v.GetString()))
                            return v.GetString()!;
                    }
                }
                catch { }
            }
            return "";
        }
    }
}
