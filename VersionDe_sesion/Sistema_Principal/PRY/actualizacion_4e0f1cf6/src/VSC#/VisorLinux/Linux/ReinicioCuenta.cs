using System;
using System.Collections.Generic;
using System.IO;
using Visor3D.Linux;
using Visor3D.Services;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Reinicio de la base de usuarios local en Linux. Archiva —nunca borra—
    /// credenciales, perfil, llave, semilla y sello, junto con el registro del
    /// jugador en Godot, y deja el equipo listo para el ciclo de registro.
    /// No toca logs, respaldos ni el motor.
    /// </summary>
    public static class ReinicioCuenta
    {
        private static readonly string[] ConservarLocal = { "runtime", "logs", "respaldo_cuenta" };
        private static readonly string[] ConservarLocalArchivos = { "reset_total.txt", "reset_cuenta.txt" };
        private static readonly string[] ConservarGodot = { "logs", "shader_cache", "vulkan", "objectdb_snapshots" };

        private static readonly string[][] CriticosLocal =
        {
            new[] { "credentials.json" },
            new[] { "user", "user_profile.json" },
            new[] { "user", "llave_acceso.json" },
            new[] { "Seguridad", "pc_sello.json" },
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
            "carrusel",
        };

        private static string Marcador(string raiz) => Path.Combine(raiz, "reset_cuenta.txt");
        private static string MarcadorTotal(string raiz) => Path.Combine(raiz, "reset_total.txt");

        /// <summary>Reinicia una sola vez por marca. True si la cuenta quedó archivada.</summary>
        public static bool EjecutarSiProcede(string version, string? baseDir = null, string? godotDir = null)
        {
            string raiz = baseDir ?? PerfilUsuario.BaseDir;
            string motor = godotDir ?? RutasLinux.GodotUserDir;
            try
            {
                string marcador = Marcador(raiz);
                if (File.Exists(marcador) && File.ReadAllText(marcador).Trim() == version)
                    return false;

                string destino = Path.Combine(raiz, "respaldo_cuenta", DateTime.Now.ToString("yyyyMMdd-HHmmss"));
                Directory.CreateDirectory(destino);

                var fallos = new List<string>();
                foreach (string[] relativo in CriticosLocal)
                {
                    string ruta = Path.Combine(raiz, Path.Combine(relativo));
                    if (!Archivar(ruta, destino)) fallos.Add(Path.Combine(relativo));
                }

                ArchivarRestoDeUsuario(destino, raiz);

                foreach (string nombre in EstadoGodot)
                    Archivar(Path.Combine(motor, nombre), destino);

                Directory.CreateDirectory(motor);
                File.WriteAllText(Path.Combine(motor, "reset_flag.txt"), version);

                if (fallos.Count > 0)
                {
                    VisorLog.Warn($"[cuenta] Reinicio {version} incompleto; pendientes: {string.Join(", ", fallos)}. Respaldo: {destino}");
                    return false;
                }

                File.WriteAllText(marcador, version);
                VisorLog.Info($"[cuenta] Base de usuarios reiniciada para {version}. Respaldo: {destino}");
                return true;
            }
            catch (Exception ex)
            {
                VisorLog.Error($"[cuenta] No se pudo reiniciar la base de usuarios para {version}", ex);
                return false;
            }
        }

        /// <summary>
        /// Borrado total único: archiva todo el estado de cuenta (local y del
        /// motor) y deja el marcador permanente <c>reset_total.txt</c>.
        /// </summary>
        public static bool EjecutarResetTotal(string version, string? baseDir = null, string? godotDir = null)
        {
            string raiz = baseDir ?? PerfilUsuario.BaseDir;
            string motor = godotDir ?? RutasLinux.GodotUserDir;
            string marcador = MarcadorTotal(raiz);

            try
            {
                if (File.Exists(marcador) && !string.IsNullOrWhiteSpace(File.ReadAllText(marcador)))
                    return false;

                string destino = Path.Combine(raiz, "respaldo_cuenta", "reset-total-" + DateTime.Now.ToString("yyyyMMdd-HHmmss"));
                string destinoLocal = Path.Combine(destino, "local");
                string destinoMotor = Path.Combine(destino, "godot");
                Directory.CreateDirectory(destinoLocal);
                Directory.CreateDirectory(destinoMotor);

                int archivados = 0;

                if (Directory.Exists(raiz))
                {
                    foreach (string entrada in Directory.GetFileSystemEntries(raiz))
                    {
                        if (SeConserva(entrada, ConservarLocal, ConservarLocalArchivos)) continue;
                        if (string.Equals(entrada, motor, StringComparison.OrdinalIgnoreCase)) continue;
                        if (Archivar(entrada, destinoLocal)) archivados++;
                    }
                }

                if (Directory.Exists(motor))
                {
                    foreach (string entrada in Directory.GetFileSystemEntries(motor))
                    {
                        if (SeConserva(entrada, ConservarGodot, Array.Empty<string>())) continue;
                        if (Archivar(entrada, destinoMotor)) archivados++;
                    }
                }

                var pendientes = new List<string>();
                foreach (string[] relativo in CriticosLocal)
                {
                    if (File.Exists(Path.Combine(raiz, Path.Combine(relativo)))) pendientes.Add(Path.Combine(relativo));
                }
                if (File.Exists(Path.Combine(motor, "registro.cfg"))) pendientes.Add("registro.cfg");

                if (pendientes.Count > 0)
                {
                    VisorLog.Warn($"[cuenta] Reset total {version} incompleto; pendientes: {string.Join(", ", pendientes)}. Respaldo: {destino}");
                    return false;
                }

                Directory.CreateDirectory(motor);
                File.WriteAllText(Path.Combine(motor, "reset_flag.txt"), version);
                File.WriteAllText(marcador, version);
                File.WriteAllText(Marcador(raiz), version);

                VisorLog.Info($"[cuenta] Reset total {version}: {archivados} elementos archivados en {destino}.");
                return true;
            }
            catch (Exception ex)
            {
                VisorLog.Error($"[cuenta] Reset total {version} fallido", ex);
                return false;
            }
        }

        public static bool ResetTotalHecho(string? baseDir = null)
        {
            try
            {
                string marcador = MarcadorTotal(baseDir ?? PerfilUsuario.BaseDir);
                return File.Exists(marcador) && !string.IsNullOrWhiteSpace(File.ReadAllText(marcador));
            }
            catch { return false; }
        }

        /// <summary>Archiva sólo el estado del motor (equipo sin cuenta). True si había restos.</summary>
        public static bool LimpiarEstadoGodot(string motivo, string? baseDir = null, string? godotDir = null)
        {
            string raiz = baseDir ?? PerfilUsuario.BaseDir;
            string motor = godotDir ?? RutasLinux.GodotUserDir;
            try
            {
                bool hayRestos = false;
                foreach (string nombre in EstadoGodot)
                {
                    string ruta = Path.Combine(motor, nombre);
                    if (File.Exists(ruta) || Directory.Exists(ruta)) { hayRestos = true; break; }
                }
                if (!hayRestos) return false;

                string destino = Path.Combine(raiz, "respaldo_cuenta",
                    DateTime.Now.ToString("yyyyMMdd-HHmmss") + "-" + motivo);
                Directory.CreateDirectory(destino);
                foreach (string nombre in EstadoGodot)
                    Archivar(Path.Combine(motor, nombre), destino);

                Directory.CreateDirectory(motor);
                File.WriteAllText(Path.Combine(motor, "reset_flag.txt"), motivo);
                VisorLog.Info($"[cuenta] Estado del motor archivado ({motivo}). Respaldo: {destino}");
                return true;
            }
            catch (Exception ex)
            {
                VisorLog.Warn($"[cuenta] No se pudo archivar el estado del motor ({motivo}): {ex.Message}");
                return false;
            }
        }

        private static bool SeConserva(string ruta, string[] carpetas, string[] archivos)
        {
            string nombre = Path.GetFileName(ruta);
            if (Array.Exists(carpetas, c => nombre.Equals(c, StringComparison.OrdinalIgnoreCase))) return true;
            if (Array.Exists(archivos, c => nombre.Equals(c, StringComparison.OrdinalIgnoreCase))) return true;
            return nombre.EndsWith(".log", StringComparison.OrdinalIgnoreCase);
        }

        private static void ArchivarRestoDeUsuario(string destino, string raiz)
        {
            string userDir = Path.Combine(raiz, "user");
            if (!Directory.Exists(userDir)) return;

            foreach (string fichero in Directory.GetFiles(userDir))
                Archivar(fichero, destino);
        }

        private static bool Archivar(string ruta, string destino)
        {
            try
            {
                if (File.Exists(ruta))
                {
                    File.Move(ruta, RutaLibre(destino, Path.GetFileName(ruta)));
                    return true;
                }
                if (Directory.Exists(ruta))
                {
                    Directory.Move(ruta, RutaLibre(destino, Path.GetFileName(ruta)));
                    return true;
                }
                return true;
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
            if (!File.Exists(objetivo) && !Directory.Exists(objetivo)) return objetivo;

            string sinExtension = Path.GetFileNameWithoutExtension(nombre);
            string extension = Path.GetExtension(nombre);
            for (int i = 2; ; i++)
            {
                string candidato = Path.Combine(destino, $"{sinExtension}_{i}{extension}");
                if (!File.Exists(candidato) && !Directory.Exists(candidato)) return candidato;
            }
        }
    }
}
