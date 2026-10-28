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

        private static string Marcador(string baseDir) => Path.Combine(baseDir, "reset_cuenta.txt");

        private static string MarcadorTotal(string baseDir) => Path.Combine(baseDir, "reset_total.txt");

        // Lo que no es base de datos de usuario: motor, diagnósticos, copias y herramientas.
        private static readonly string[] ConservarLocal = { "runtime", "logs", "respaldo_cuenta" };
        private static readonly string[] ConservarLocalArchivos = { "cloudflared.exe", "reset_total.txt", "reset_cuenta.txt" };

        // Cachés del motor: se regeneran solas y no contienen identidad.
        private static readonly string[] ConservarGodot = { "logs", "shader_cache", "vulkan", "objectdb_snapshots" };

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
        /// <param name="version">Marca del reinicio; si ya está escrita, no se repite.</param>
        /// <param name="baseDir">Sólo para las pruebas; por defecto %LOCALAPPDATA%\WoldVirtualP2P3D.</param>
        /// <param name="godotDir">Sólo para las pruebas; por defecto el user:// del motor.</param>
        public static bool EjecutarSiProcede(string version, string? baseDir = null, string? godotDir = null)
        {
            string raiz = baseDir ?? BaseDir;
            string motor = godotDir ?? GodotDir;
            try
            {
                string marcador = Marcador(raiz);
                if (File.Exists(marcador) &&
                    File.ReadAllText(marcador).Trim() == version)
                    return false;

                string destino = Path.Combine(
                    raiz, "respaldo_cuenta",
                    DateTime.Now.ToString("yyyyMMdd-HHmmss"));
                Directory.CreateDirectory(destino);

                var fallos = new List<string>();

                foreach (string relativo in CriticosLocal)
                {
                    if (!Archivar(Path.Combine(raiz, relativo), destino))
                        fallos.Add(relativo);
                }

                // Resto del directorio de usuario (semilla, amigos, sesión P2P).
                ArchivarRestoDeUsuario(destino, raiz);

                foreach (string nombre in EstadoGodot)
                    Archivar(Path.Combine(motor, nombre), destino);

                // Boot.gd borra registro.cfg si el movimiento falló por bloqueo.
                Directory.CreateDirectory(motor);
                File.WriteAllText(Path.Combine(motor, "reset_flag.txt"), version);

                if (fallos.Count > 0)
                {
                    // Sin marcador: el próximo arranque reintenta el reinicio.
                    VisorLog.Warn(
                        $"[cuenta] Reinicio {version} incompleto; pendientes: {string.Join(", ", fallos)}. Respaldo: {destino}");
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
        /// Borrado total único de la base de usuarios local (2.6.4): archiva en
        /// <c>respaldo_cuenta\reset-total-&lt;fecha&gt;</c> todo el estado de la
        /// cuenta —perfil, credenciales, llave, semilla, amigos y sello— junto
        /// con el estado del jugador en Godot (registro, avatar, islas,
        /// construcción, inventario y sesión). Conserva el runtime, los logs,
        /// las cachés del motor y cloudflared.
        ///
        /// Deja el marcador permanente <c>reset_total.txt</c>: se ejecuta una
        /// sola vez, así que lo que el usuario registre después persiste en
        /// esta y en futuras versiones.
        /// </summary>
        /// <returns><c>true</c> si en este arranque se vació la base.</returns>
        public static bool EjecutarResetTotal(string version, string? baseDir = null, string? godotDir = null)
        {
            string raiz = baseDir ?? BaseDir;
            string motor = godotDir ?? GodotDir;
            string marcador = MarcadorTotal(raiz);

            try
            {
                if (File.Exists(marcador) && !string.IsNullOrWhiteSpace(File.ReadAllText(marcador)))
                    return false; // ya se hizo: la cuenta nueva no se vuelve a tocar

                string destino = Path.Combine(
                    raiz, "respaldo_cuenta",
                    "reset-total-" + DateTime.Now.ToString("yyyyMMdd-HHmmss"));
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
                        // El motor tiene su propio barrido; si vive dentro de la raíz no se archiva en bloque.
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

                // Comprobar que no quedó identidad utilizable antes de marcar.
                var pendientes = new List<string>();
                foreach (string relativo in CriticosLocal)
                    if (File.Exists(Path.Combine(raiz, relativo)))
                        pendientes.Add(relativo);
                if (File.Exists(Path.Combine(motor, "registro.cfg")))
                    pendientes.Add("registro.cfg");

                if (pendientes.Count > 0)
                {
                    VisorLog.Warn(
                        $"[cuenta] Reset total {version} incompleto; pendientes: {string.Join(", ", pendientes)}. Respaldo: {destino}");
                    return false;
                }

                Directory.CreateDirectory(motor);
                File.WriteAllText(Path.Combine(motor, "reset_flag.txt"), version);

                // Marcador permanente: ni esta ni futuras versiones repiten el reset.
                File.WriteAllText(marcador, version);
                File.WriteAllText(Marcador(raiz), version);

                VisorLog.Info(
                    $"[cuenta] Reset total {version}: {archivados} elementos archivados en {destino}. Base local vacía; el registro que se haga ahora persiste.");
                return true;
            }
            catch (Exception ex)
            {
                VisorLog.Error($"[cuenta] Reset total {version} fallido", ex);
                return false;
            }
        }

        /// <summary>Si ya se hizo el reset total, no se reimportan cuentas antiguas.</summary>
        public static bool ResetTotalHecho(string? baseDir = null)
        {
            try
            {
                string marcador = MarcadorTotal(baseDir ?? BaseDir);
                return File.Exists(marcador) && !string.IsNullOrWhiteSpace(File.ReadAllText(marcador));
            }
            catch { return false; }
        }

        private static bool SeConserva(string ruta, string[] carpetas, string[] archivos)
        {
            string nombre = Path.GetFileName(ruta);
            if (Array.Exists(carpetas, c => nombre.Equals(c, StringComparison.OrdinalIgnoreCase)))
                return true;
            if (Array.Exists(archivos, c => nombre.Equals(c, StringComparison.OrdinalIgnoreCase)))
                return true;
            return nombre.EndsWith(".log", StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>
        /// Archiva sólo el estado del motor cuando el equipo no tiene cuenta
        /// (equipo nuevo o copia sin credenciales) para que el motor no entre
        /// directo con un avatar y nick viejos y el ciclo de registro empiece
        /// de cero. No toca nada del perfil local.
        /// </summary>
        /// <returns>true si había algo que archivar.</returns>
        public static bool LimpiarEstadoGodot(string motivo, string? baseDir = null, string? godotDir = null)
        {
            string raiz = baseDir ?? BaseDir;
            string motor = godotDir ?? GodotDir;
            try
            {
                bool hayRestos = false;
                foreach (string nombre in EstadoGodot)
                {
                    string ruta = Path.Combine(motor, nombre);
                    if (File.Exists(ruta) || Directory.Exists(ruta)) { hayRestos = true; break; }
                }
                if (!hayRestos) return false;

                string destino = Path.Combine(
                    raiz, "respaldo_cuenta",
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

        private static void ArchivarRestoDeUsuario(string destino, string baseDir)
        {
            string userDir = Path.Combine(baseDir, "user");
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
