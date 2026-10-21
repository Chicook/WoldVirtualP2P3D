using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows;

namespace Visor3D
{
    /// <summary>
    /// Extrae los recursos embebidos (motor Godot + mundo .pck) a
    /// %LOCALAPPDATA%\WoldVirtualP2P3D\runtime\0.1.0-pck\.
    /// Solo lo hace la primera vez o cuando cambia la versión del runtime.
    /// </summary>
    public static class AppExtractor
    {
        // v0.1.0-pck: el mundo viaja como PCK (no como proyecto suelto), así que
        // este marcador fuerza la re-extracción en instalaciones anteriores.
        private const string AppVersion = "0.1.0";

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
                    File.ReadAllText(VersionFile).Trim() == AppVersion &&
                    File.Exists(GodotExePath) &&
                    File.Exists(PckPath))
                {
                    return true;
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

                File.WriteAllText(VersionFile, AppVersion);
                return true;
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    $"Error al preparar el motor 3D:\n{ex.Message}\n\nDirectorio: {RuntimeDir}",
                    "Error de extracción", MessageBoxButton.OK, MessageBoxImage.Error);
                return false;
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
            foreach (var entry in archive.Entries)
            {
                if (string.IsNullOrEmpty(entry.Name)) continue; // Carpeta
                string cleanEntryName = entry.FullName.TrimStart('/', '\\');
                string targetPath = Path.GetFullPath(Path.Combine(destDir, cleanEntryName));
                if (!targetPath.StartsWith(destDir, StringComparison.OrdinalIgnoreCase))
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
