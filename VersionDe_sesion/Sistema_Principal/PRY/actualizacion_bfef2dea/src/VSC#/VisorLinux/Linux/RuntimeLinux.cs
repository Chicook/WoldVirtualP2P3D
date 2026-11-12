using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using Visor3D.Seguridad;
using Visor3D.Services;

namespace Visor3D.Linux
{
    /// <summary>
    /// Motor Godot de Linux y mundo empaquetado, embebidos en el propio visor
    /// (igual que el exe de Windows lleva <c>godot_exe.zip</c> y <c>wvp3d.pck</c>).
    /// Se extraen una vez a <c>~/.local/share/WoldVirtualP2P3D/runtime/&lt;versión&gt;/</c>
    /// y de ahí los lanza <see cref="LanzadorMundo"/>.
    /// <c>WOLD_RUNTIME_DIR</c> redirige la carpeta (pruebas).
    /// </summary>
    public static class RuntimeLinux
    {
        private const string RecursoMotor = "Visor3D.Linux.godot_linux.zip";
        private const string RecursoPck = "Visor3D.Linux.wvp3d.pck";
        private const string Marcador = ".extracted";
        private const string MarcadorArranque = ".arranque_ok";

        /// <summary>Versión del ensamblado: si cambia, se vuelve a extraer.</summary>
        public static string Version { get; } = ObtenerVersion();

        public static string Dir
        {
            get
            {
                string? forzada = Environment.GetEnvironmentVariable("WOLD_RUNTIME_DIR");
                if (!string.IsNullOrWhiteSpace(forzada)) return forzada;
                return Path.Combine(PerfilUsuario.BaseDir, "runtime", Version);
            }
        }

        public static string MotorPath => Path.Combine(Dir, "Servidor3D", RutasLinux.NombreMotor);
        public static string PckPath => Path.Combine(Dir, RutasLinux.NombrePck);

        public static bool TieneMotorEmbebido => Recurso(RecursoMotor) != null;
        public static bool TienePckEmbebido => Recurso(RecursoPck) != null;

        /// <summary>El motor y el mundo ya están en disco, con el marcador al día.</summary>
        public static bool Extraido
        {
            get
            {
                try
                {
                    return File.Exists(Path.Combine(Dir, Marcador))
                        && File.ReadAllText(Path.Combine(Dir, Marcador)).Trim() == Version
                        && File.Exists(MotorPath)
                        && File.Exists(PckPath);
                }
                catch
                {
                    return false;
                }
            }
        }

        /// <summary>
        /// Deja motor y mundo listos en <see cref="Dir"/>. Idempotente y barato
        /// cuando ya está hecho. Devuelve false y explica el motivo si falla.
        /// </summary>
        public static bool Asegurar(out string? error, Action<string>? aviso = null)
        {
            error = null;
            if (Extraido) return true;

            if (!TieneMotorEmbebido || !TienePckEmbebido)
            {
                error = "Este visor no lleva el motor y el mundo dentro; indica un motor con WOLD_MOTOR y un mundo con WOLD_PCK.";
                return false;
            }

            try
            {
                // Sólo se borra una extracción a medias nuestra; si WOLD_RUNTIME_DIR
                // apunta a una carpeta con otras cosas, se escribe encima y ya está.
                if (Directory.Exists(Dir) && EsNuestra(Dir))
                {
                    try { Directory.Delete(Dir, recursive: true); } catch { /* se reutiliza lo que haya */ }
                }
                Directory.CreateDirectory(Dir);

                aviso?.Invoke($"Extrayendo el motor ({RutasLinux.NombreMotor})…");
                string servidor = Path.Combine(Dir, "Servidor3D");
                Directory.CreateDirectory(servidor);
                ExtraerZip(RecursoMotor, servidor);

                if (!File.Exists(MotorPath))
                {
                    string[] encontrados = Directory.GetFiles(servidor, RutasLinux.NombreMotor, SearchOption.AllDirectories);
                    if (encontrados.Length == 0)
                    {
                        error = "El motor embebido no contenía " + RutasLinux.NombreMotor;
                        return false;
                    }
                    File.Move(encontrados[0], MotorPath, overwrite: true);
                }
                DarPermisoEjecucion(MotorPath);

                aviso?.Invoke($"Extrayendo el mundo ({RutasLinux.NombrePck})…");
                using (Stream origen = Recurso(RecursoPck)!)
                using (FileStream destino = File.Create(PckPath))
                    origen.CopyTo(destino);

                File.WriteAllText(Path.Combine(Dir, Marcador), Version);
                VisorLog.Info($"[runtime] Extraído en {Dir}");
                LimpiarAntiguos();
                return true;
            }
            catch (Exception ex)
            {
                VisorLog.Error("[runtime] No se pudo extraer el motor y el mundo", ex);
                error = $"{ex.GetType().Name}: {ex.Message}";
                return false;
            }
        }

        /// <summary>Constancia de que esta versión llegó a abrir la ventana.</summary>
        public static void MarcarArranqueCorrecto()
        {
            try
            {
                string? raiz = RaizRuntime();
                if (raiz == null) return;
                Directory.CreateDirectory(raiz);
                File.WriteAllText(Path.Combine(raiz, MarcadorArranque),
                    Version + Environment.NewLine + DateTime.UtcNow.ToString("o"));
            }
            catch (Exception ex)
            {
                VisorLog.Warn($"[runtime] No se pudo marcar el arranque: {ex.Message}");
            }
        }

        /// <summary>
        /// Borra los runtimes de otras versiones salvo la última que arrancó bien.
        /// Sólo actúa si la carpeta padre se llama <c>runtime</c> (protege
        /// <c>WOLD_RUNTIME_DIR</c> en pruebas y el modo portable).
        /// </summary>
        private static void LimpiarAntiguos()
        {
            try
            {
                string? raiz = RaizRuntime();
                if (raiz == null) return;

                string marcador = Path.Combine(raiz, MarcadorArranque);
                if (!File.Exists(marcador)) return;

                string anterior = File.ReadAllText(marcador).Split('\n')[0].Trim();
                if (anterior.Length == 0 || anterior == Version) return;

                foreach (string dir in Directory.GetDirectories(raiz))
                {
                    string nombre = Path.GetFileName(dir);
                    if (nombre == Version || nombre == anterior) continue;
                    try
                    {
                        Directory.Delete(dir, recursive: true);
                        VisorLog.Info($"[runtime] Borrado runtime antiguo {nombre}");
                    }
                    catch (Exception ex)
                    {
                        VisorLog.Warn($"[runtime] No se pudo borrar {nombre}: {ex.Message}");
                    }
                }
            }
            catch (Exception ex)
            {
                VisorLog.Warn($"[runtime] Limpieza omitida: {ex.Message}");
            }
        }

        private static string? RaizRuntime()
        {
            string raiz = Path.GetDirectoryName(Dir.TrimEnd('/', '\\')) ?? "";
            if (raiz.Length == 0) return null;
            return Path.GetFileName(raiz) == "runtime" ? raiz : null;
        }

        private static void ExtraerZip(string recurso, string destino)
        {
            using Stream? flujo = Recurso(recurso);
            if (flujo == null) throw new InvalidOperationException($"Falta el recurso {recurso}");

            string destinoCompleto = Path.GetFullPath(destino);
            using var zip = new ZipArchive(flujo, ZipArchiveMode.Read);
            foreach (var entrada in zip.Entries)
            {
                if (string.IsNullOrEmpty(entrada.Name)) continue;
                string ruta = Path.GetFullPath(Path.Combine(destinoCompleto, entrada.FullName));
                if (!ruta.StartsWith(destinoCompleto, StringComparison.Ordinal)) continue;

                string? padre = Path.GetDirectoryName(ruta);
                if (!string.IsNullOrEmpty(padre)) Directory.CreateDirectory(padre);
                entrada.ExtractToFile(ruta, overwrite: true);
            }
        }

        private static void DarPermisoEjecucion(string ruta)
        {
            if (OperatingSystem.IsWindows()) return;
            try
            {
                File.SetUnixFileMode(ruta,
                    UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute |
                    UnixFileMode.GroupRead | UnixFileMode.GroupExecute |
                    UnixFileMode.OtherRead | UnixFileMode.OtherExecute);
            }
            catch (Exception ex)
            {
                VisorLog.Warn($"[runtime] No se pudo dar permiso de ejecución a {ruta}: {ex.Message}");
            }
        }

        private static Stream? Recurso(string nombre) =>
            Assembly.GetExecutingAssembly().GetManifestResourceStream(nombre);

        /// <summary>Carpeta vacía o con el marcador de una extracción anterior.</summary>
        private static bool EsNuestra(string dir)
        {
            try
            {
                if (File.Exists(Path.Combine(dir, Marcador))) return true;
                return Directory.GetFileSystemEntries(dir).Length == 0;
            }
            catch
            {
                return false;
            }
        }

        private static string ObtenerVersion()
        {
            var info = typeof(RuntimeLinux).Assembly
                .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion;
            if (string.IsNullOrWhiteSpace(info)) return RutasLinux.Version;

            int mas = info!.IndexOf('+');
            return (mas >= 0 ? info[..mas] : info).Trim();
        }
    }
}
