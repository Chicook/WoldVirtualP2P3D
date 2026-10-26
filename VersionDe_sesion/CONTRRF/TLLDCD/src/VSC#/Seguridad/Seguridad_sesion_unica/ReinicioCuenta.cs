using System;
using System.Collections.Generic;
using System.IO;
using Visor3D.Services;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Reinicia la base de usuarios local una sola vez por versión.
    ///
    /// Archiva —no borra— las credenciales, el perfil, la llave, la semilla y el
    /// sello de PC, junto con el registro del jugador en Godot. El visor vuelve
    /// al estado de equipo sin registrar: pantalla de bienvenida con «Crear
    /// cuenta» y, en el motor, carrusel + registro de nick.
    ///
    /// No toca runtime, logs, motor, PCK ni la carpeta internal_storage.
    /// </summary>
    public static class ReinicioCuenta
    {
        private static readonly string BaseDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WoldVirtualP2P3D");

        private static readonly string GodotDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "Godot", "app_userdata", "WoldVirtualP2P3D");

        private static string Marcador => Path.Combine(BaseDir, "reset_cuenta.txt");

        // Sin estos ficheros el equipo deja de estar registrado.
        private static readonly string[] CriticosLocal =
        {
            "credentials.json",
            "user\\user_profile.json",
            "user\\llave_acceso.json",
            "Seguridad\\pc_sello.json"
        };

        private static readonly string[] EstadoGodot =
        {
            "registro.cfg",
            "p2p_session.json",
            "session_host.txt",
            "islas_registro.cfg",
            "isla_propiedad.cfg",
            "avatar_hash.json",
            "avatar.sha256",
            "sesion_islas_snapshot.json",
            "carrusel"
        };

        /// <summary>
        /// Ejecuta el reinicio si esta versión aún no lo hizo.
        /// Devuelve true sólo cuando la cuenta quedó realmente archivada.
        /// </summary>
        public static bool EjecutarSiProcede(string version)
        {
            try
            {
                if (File.Exists(Marcador) &&
                    File.ReadAllText(Marcador).Trim() == version)
                    return false;

                string destino = Path.Combine(
                    BaseDir, "respaldo_cuenta",
                    DateTime.Now.ToString("yyyyMMdd-HHmmss"));
                Directory.CreateDirectory(destino);

                var fallos = new List<string>();

                foreach (string relativo in CriticosLocal)
                {
                    if (!Archivar(Path.Combine(BaseDir, relativo), destino))
                        fallos.Add(relativo);
                }

                // Resto del directorio de usuario (semilla, amigos, sesión P2P).
                ArchivarRestoDeUsuario(destino);

                foreach (string nombre in EstadoGodot)
                    Archivar(Path.Combine(GodotDir, nombre), destino);

                // Boot.gd borra registro.cfg si el movimiento falló por bloqueo.
                Directory.CreateDirectory(GodotDir);
                File.WriteAllText(Path.Combine(GodotDir, "reset_flag.txt"), version);

                if (fallos.Count > 0)
                {
                    // Sin marcador: el próximo arranque reintenta el reinicio.
                    VisorLog.Warn(
                        $"[cuenta] Reinicio {version} incompleto; pendientes: {string.Join(", ", fallos)}. Respaldo: {destino}");
                    return false;
                }

                File.WriteAllText(Marcador, version);
                VisorLog.Info($"[cuenta] Base de usuarios reiniciada para {version}. Respaldo: {destino}");
                return true;
            }
            catch (Exception ex)
            {
                VisorLog.Error($"[cuenta] No se pudo reiniciar la base de usuarios para {version}", ex);
                return false;
            }
        }

        private static void ArchivarRestoDeUsuario(string destino)
        {
            string userDir = Path.Combine(BaseDir, "user");
            if (!Directory.Exists(userDir)) return;

            foreach (string fichero in Directory.GetFiles(userDir))
            {
                // Los críticos ya se movieron; el resto se archiva sin bloquear.
                Archivar(fichero, destino);
            }
        }

        /// <summary>Mueve un fichero o carpeta al respaldo. true si ya no está en origen.</summary>
        private static bool Archivar(string ruta, string destino)
        {
            try
            {
                if (File.Exists(ruta))
                {
                    string objetivo = RutaLibre(destino, Path.GetFileName(ruta));
                    File.Move(ruta, objetivo);
                    return true;
                }

                if (Directory.Exists(ruta))
                {
                    string objetivo = RutaLibre(destino, Path.GetFileName(ruta));
                    Directory.Move(ruta, objetivo);
                    return true;
                }

                return true; // no existía: nada que archivar
            }
            catch (Exception ex)
            {
                VisorLog.Warn($"[cuenta] No se pudo archivar {ruta}: {ex.Message}");
                return false;
            }
        }

        private static string RutaLibre(string destino, string nombre)
        {
            string objetivo = Path.Combine(destino, nombre);
            if (!File.Exists(objetivo) && !Directory.Exists(objetivo))
                return objetivo;

            string sinExtension = Path.GetFileNameWithoutExtension(nombre);
            string extension = Path.GetExtension(nombre);
            for (int i = 2; ; i++)
            {
                string candidato = Path.Combine(destino, $"{sinExtension}_{i}{extension}");
                if (!File.Exists(candidato) && !Directory.Exists(candidato))
                    return candidato;
            }
        }
    }
}
