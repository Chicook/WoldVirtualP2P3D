using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows;

namespace Visor3D
{
    /// <summary>
    /// Extrae los recursos embebidos (Godot exe + proyecto 3D) a %LOCALAPPDATA%\WoldVirtualP2P3D\runtime\0.0.20\
    /// Solo lo hace la primera vez o cuando la version cambia.
    /// </summary>
    public static class AppExtractor
    {
        // v0.0.20: identificador de runtime propio para forzar la re-extracción del
        // proyecto Godot (transporte WebSocket sobre túnel) en instalaciones previas.
        private const string AppVersion = "0.0.20";
        public static readonly string RuntimeDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WoldVirtualP2P3D", "runtime", AppVersion);

        private static readonly string VersionFile = Path.Combine(RuntimeDir, ".extracted");

        public static string GodotExePath =>
            Path.Combine(RuntimeDir, "Servidor3D", "Godot_v4.7.2-stable_win64.exe");

        public static string ProjectPath =>
            Path.Combine(RuntimeDir, "WoldVirtualP2P3D");

        /// <summary>Extrae los recursos si no se ha hecho ya. Devuelve false si falla.</summary>
        public static bool EnsureExtracted()
        {
            try
            {
                if (File.Exists(VersionFile) &&
                    File.ReadAllText(VersionFile).Trim() == AppVersion &&
                    File.Exists(GodotExePath) &&
                    Directory.Exists(ProjectPath) &&
                    File.Exists(Path.Combine(ProjectPath, "project.godot")))
                {
                    return true;
                }

                if (Directory.Exists(RuntimeDir))
                {
                    try { Directory.Delete(RuntimeDir, recursive: true); } catch { }
                }
                Directory.CreateDirectory(RuntimeDir);

                var assembly = Assembly.GetExecutingAssembly();

                // 1. Extraer Godot ejecutable a Servidor3D
                string servidorDir = Path.Combine(RuntimeDir, "Servidor3D");
                Directory.CreateDirectory(servidorDir);
                if (!ExtractResource(assembly, "Visor3D.godot_exe.zip", servidorDir))
                    return false;

                // Si se extrajo con subcarpeta o directo en la raíz de servidorDir
                string godotEnServidor = Path.Combine(servidorDir, "Godot_v4.7.2-stable_win64.exe");
                if (!File.Exists(godotEnServidor))
                {
                    // Buscar si quedó en otra subcarpeta
                    var found = Directory.GetFiles(servidorDir, "Godot_v4.7.2-stable_win64.exe", SearchOption.AllDirectories);
                    if (found.Length > 0 && found[0] != godotEnServidor)
                    {
                        File.Copy(found[0], godotEnServidor, overwrite: true);
                    }
                }

                // 2. Extraer proyecto Godot completo a WoldVirtualP2P3D
                Directory.CreateDirectory(ProjectPath);
                if (!ExtractResource(assembly, "Visor3D.godot_project.zip", ProjectPath))
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
    }
}