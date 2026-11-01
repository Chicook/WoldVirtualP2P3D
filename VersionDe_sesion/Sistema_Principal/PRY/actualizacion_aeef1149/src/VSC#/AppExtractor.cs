using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows;

namespace Visor3D
{
    /// <summary>
    /// Extrae los recursos embebidos (motor Godot + mundo .pck) a
    /// %LOCALAPPDATA%\WoldVirtualP2P3D\runtime\<versión>\.
    /// Solo lo hace la primera vez o cuando cambia la versión del runtime.
    /// </summary>
    public static class AppExtractor
    {
        // El marcador de re-extracción es la versión del propio ensamblado, no una
        // constante a mano: un OTA reemplaza el .exe —y con él el PCK embebido—, y si
        // el marcador no se moviera el visor seguiría arrancando el mundo extraído por
        // una versión anterior.
        private static readonly string AppVersion = ObtenerVersionEnsamblado();

        /// <summary>Versión usada como marcador de re-extracción (informativa).</summary>
        public static string Version => AppVersion;

        /// <summary>En la prueba de arranque no debe aparecer ningún diálogo modal.</summary>
        public static bool SilentErrors { get; set; }

        private static string ObtenerVersionEnsamblado()
        {
            var info = typeof(AppExtractor).Assembly
                .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion;
            if (string.IsNullOrWhiteSpace(info)) return "0.0.0";

            int plus = info.IndexOf('+');          // descarta el sufijo "+<sha>"
            return (plus >= 0 ? info.Substring(0, plus) : info).Trim();
        }

        /// <summary>
        /// Carpeta de runtime. Se puede redirigir con la variable de entorno
        /// <c>WOLD_RUNTIME_DIR</c> (pruebas y modo portable); si no, LocalAppData.
        /// </summary>
        public static readonly string RuntimeDir = ResolverRuntimeDir();

        private static string ResolverRuntimeDir()
        {
            string? custom = Environment.GetEnvironmentVariable("WOLD_RUNTIME_DIR");
            if (!string.IsNullOrWhiteSpace(custom))
                return custom;

            return Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "WoldVirtualP2P3D", "runtime", AppVersion);
        }

        private static readonly string VersionFile = Path.Combine(RuntimeDir, ".extracted");

        public static string GodotExePath =>
            Path.Combine(RuntimeDir, "Servidor3D", "Godot_v4.7.2-stable_win64.exe");

        /// <summary>Mundo empaquetado que se pasa a Godot con <c>--main-pack</c>.</summary>
        public static string PckPath => Path.Combine(RuntimeDir, "wvp3d.pck");

        /// <summary>Proyecto suelto (solo modo desarrollo; ya no se extrae del .exe).</summary>
        public static string ProjectPath => Path.Combine(RuntimeDir, "WoldVirtualP2P3D");

        /// <summary>Extrae los recursos si no se ha hecho ya. Devuelve false si falla.</summary>
        public static bool EnsureExtracted()
        {
            try
            {
                if (File.Exists(VersionFile) &&
                    File.Exists(GodotExePath) &&
                    File.Exists(PckPath))
                {
                    var lines = File.ReadAllLines(VersionFile);
                    if (lines.Length > 0 && lines[0].Trim() == AppVersion)
                    {
                        string expectedPckHash = "";
                        string expectedGodotHash = "";
                        for (int i = 1; i < lines.Length; i++)
                        {
                            if (lines[i].StartsWith("pck_sha256=", StringComparison.OrdinalIgnoreCase))
                                expectedPckHash = lines[i].Substring("pck_sha256=".Length).Trim();
                            else if (lines[i].StartsWith("godot_sha256=", StringComparison.OrdinalIgnoreCase))
                                expectedGodotHash = lines[i].Substring("godot_sha256=".Length).Trim();
                        }

                        // Reutilizar solo si ambos hashes coinciden (H4: fiabilidad de extracción)
                        bool pckOk = string.IsNullOrEmpty(expectedPckHash) || CalcularSha256(PckPath) == expectedPckHash;
                        bool godotOk = string.IsNullOrEmpty(expectedGodotHash) || CalcularSha256(GodotExePath) == expectedGodotHash;
                        if (pckOk && godotOk)
                        {
                            return true;
                        }
                    }
                }

                if (Directory.Exists(RuntimeDir))
                {
                    try { Directory.Delete(RuntimeDir, recursive: true); } catch { }
                }
                Directory.CreateDirectory(RuntimeDir);

                var assembly = Assembly.GetExecutingAssembly();

                // 1. Motor Godot → Servidor3D
                string servidorDir = Path.Combine(RuntimeDir, "Servidor3D");
                Directory.CreateDirectory(servidorDir);
                if (!ExtractResource(assembly, "Visor3D.godot_exe.zip", servidorDir))
                    return false;

                string godotEnServidor = GodotExePath;
                if (!File.Exists(godotEnServidor))
                {
                    var found = Directory.GetFiles(servidorDir, "Godot_v4.7.2-stable_win64.exe", SearchOption.AllDirectories);
                    if (found.Length > 0 && found[0] != godotEnServidor)
                        File.Copy(found[0], godotEnServidor, overwrite: true);
                }

                // 2. Mundo empaquetado → wvp3d.pck
                if (!ExtractFile(assembly, "Visor3D.wvp3d.pck", PckPath))
                    return false;

                string pckHash = CalcularSha256(PckPath) ?? "";
                string godotHash = CalcularSha256(godotEnServidor) ?? "";
                File.WriteAllLines(VersionFile, new[]
                {
                    AppVersion,
                    $"pck_sha256={pckHash}",
                    $"godot_sha256={godotHash}"
                });
                return true;
            }
            catch (Exception ex)
            {
                if (!SilentErrors)
                {
                    MessageBox.Show(
                        $"Error al preparar el motor 3D:\n{ex.Message}\n\nDirectorio: {RuntimeDir}",
                        "Error de extracción", MessageBoxButton.OK, MessageBoxImage.Error);
                }
                return false;
            }
        }

        private static string? CalcularSha256(string path)
        {
            try
            {
                if (!File.Exists(path)) return null;
                using var sha = System.Security.Cryptography.SHA256.Create();
                using var fs = File.OpenRead(path);
                return Convert.ToHexString(sha.ComputeHash(fs)).ToLowerInvariant();
            }
            catch
            {
                return null;
            }
        }

        private static bool ExtractResource(Assembly asm, string resourceName, string destDir)
        {
            using Stream? stream = asm.GetManifestResourceStream(resourceName);
            if (stream == null)
            {
                // Si no está embebido (modo debug o sin recursos embebidos), omitir sin error fatal
                return false;
            }

            using var archive = new ZipArchive(stream, ZipArchiveMode.Read);
            string destDirFull = Path.GetFullPath(destDir);
            string destDirWithSep = destDirFull.EndsWith(Path.DirectorySeparatorChar.ToString())
                ? destDirFull
                : destDirFull + Path.DirectorySeparatorChar;

            foreach (var entry in archive.Entries)
            {
                if (string.IsNullOrEmpty(entry.Name)) continue; // Carpeta
                string cleanEntryName = entry.FullName.TrimStart('/', '\\');
                string targetPath = Path.GetFullPath(Path.Combine(destDirFull, cleanEntryName));
                if (!targetPath.StartsWith(destDirWithSep, StringComparison.OrdinalIgnoreCase))
                    continue;

                string? parentDir = Path.GetDirectoryName(targetPath);
                if (!string.IsNullOrEmpty(parentDir) && !Directory.Exists(parentDir))
                {
                    Directory.CreateDirectory(parentDir);
                }

                entry.ExtractToFile(targetPath, overwrite: true);
            }

            return true;
        }

        /// <summary>Copia un recurso embebido tal cual (el PCK no es un ZIP).</summary>
        private static bool ExtractFile(Assembly asm, string resourceName, string destPath)
        {
            using Stream? stream = asm.GetManifestResourceStream(resourceName);
            if (stream == null) return false;

            string? dir = Path.GetDirectoryName(destPath);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

            using var fs = File.Create(destPath);
            stream.CopyTo(fs);
            return true;
        }
    }
}
