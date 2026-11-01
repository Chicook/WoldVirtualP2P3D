using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Visor3D.Seguridad
{
    /// <summary>
    /// Estado global del equipo, adaptado de la configuración <c>Estado_Global</c>
    /// del proyecto de referencia (un único <c>estado.json</c> versionado y con
    /// marca de tiempo). Aquí no guarda identidad: sólo anota qué piezas necesita
    /// el visor y cuáles hay, para que el arranque decida entre acceso y ciclo de
    /// registro completo. Se reescribe en cada arranque; sirve también de
    /// diagnóstico para soporte.
    /// </summary>
    public sealed class EstadoGlobal
    {
        public const string Archivo = "estado.json";

        [JsonPropertyName("v")]
        public string Version { get; set; } = "1.0";

        [JsonPropertyName("ts")]
        public DateTime ActualizadoUtc { get; set; } = DateTime.UtcNow;

        /// <summary><c>vacio</c>, <c>incompleto</c> o <c>completo</c>.</summary>
        [JsonPropertyName("equipo")]
        public string Equipo { get; set; } = "vacio";

        /// <summary>Piezas que exige el visor y si están presentes.</summary>
        [JsonPropertyName("necesario")]
        public Dictionary<string, bool> Necesario { get; set; } = new();

        /// <summary><c>registro-completo</c>, <c>reparar</c> o <c>acceso</c>.</summary>
        [JsonPropertyName("accion")]
        public string Accion { get; set; } = "registro-completo";

        /// <summary>No hay nada de lo necesario: toca recorrer el registro entero.</summary>
        [JsonIgnore]
        public bool FaltaTodo => Accion == "registro-completo";

        /// <summary>
        /// Recalcula el estado desde el disco y lo guarda en
        /// <c>%LOCALAPPDATA%\WoldVirtualP2P3D\estado.json</c>.
        /// </summary>
        /// <param name="baseDir">Sólo para las pruebas; por defecto el perfil local.</param>
        /// <param name="godotDir">Sólo para las pruebas; por defecto el user:// del motor.</param>
        public static EstadoGlobal Actualizar(string? baseDir = null, string? godotDir = null)
        {
            string raiz = baseDir ?? PerfilUsuario.BaseDir;
            string motor = godotDir ?? MotorDir;

            var estado = new EstadoGlobal
            {
                ActualizadoUtc = DateTime.UtcNow,
                Necesario = new Dictionary<string, bool>
                {
                    ["credenciales"] = File.Exists(Path.Combine(raiz, "credentials.json")),
                    ["perfil"] = File.Exists(Path.Combine(raiz, "user", "user_profile.json")),
                    ["llave"] = File.Exists(Path.Combine(raiz, "user", "llave_acceso.json")),
                    ["sello"] = File.Exists(Path.Combine(raiz, "Seguridad", "pc_sello.json")),
                    ["motor"] = File.Exists(Path.Combine(motor, "registro.cfg")),
                }
            };

            var cuenta = PerfilUsuario.Diagnosticar(out _, raiz);
            bool algo = estado.Necesario.ContainsValue(true);

            if (cuenta == EstadoCuenta.Completa)
            {
                estado.Equipo = "completo";
                estado.Accion = "acceso";
            }
            else if (!algo)
            {
                estado.Equipo = "vacio";
                estado.Accion = "registro-completo";
            }
            else
            {
                estado.Equipo = "incompleto";
                estado.Accion = "reparar";
            }

            try
            {
                Directory.CreateDirectory(raiz);
                File.WriteAllText(
                    Path.Combine(raiz, Archivo),
                    JsonSerializer.Serialize(estado, new JsonSerializerOptions
                    {
                        WriteIndented = true,
                        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
                    }));
            }
            catch (Exception ex)
            {
                Visor3D.Services.VisorLog.Warn($"[estado] No se pudo guardar {Archivo}: {ex.Message}");
            }

            return estado;
        }

        /// <summary>user:// del motor: %APPDATA%\Godot\app_userdata\WoldVirtualP2P3D.</summary>
        public static string MotorDir => Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "Godot", "app_userdata", "WoldVirtualP2P3D");
    }
}
