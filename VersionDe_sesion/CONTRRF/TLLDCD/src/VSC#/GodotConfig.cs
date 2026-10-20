using System;
using System.Diagnostics;
using System.IO;

namespace Visor3D
{
    public static class GodotConfig
    {
        private static string ExeDir =>
            Path.GetDirectoryName(Process.GetCurrentProcess().MainModule?.FileName
                ?? AppDomain.CurrentDomain.BaseDirectory)
            ?? AppDomain.CurrentDomain.BaseDirectory;

        public static string GetGodotExePath()
        {
            const string godotName = "Godot_v4.7.2-stable_win64.exe";

            // 1. Recursos extraídos al LocalAppData (exe standalone)
            if (File.Exists(AppExtractor.GodotExePath)) return AppExtractor.GodotExePath;

            // 2. Junto al exe publicado
            string nextToExe = Path.Combine(ExeDir, "Servidor3D", godotName);
            if (File.Exists(nextToExe)) return nextToExe;

            // 3. Instalación del sistema de Godot
            string[] systemCandidates =
            {
                @"C:\Program Files\Godot\" + godotName,
                @"C:\Program Files (x86)\Godot\" + godotName,
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), godotName),
            };
            foreach (var c in systemCandidates)
            {
                if (File.Exists(c)) return c;
            }

            // 4. Variable de entorno PATH
            foreach (var dir in Environment.GetEnvironmentVariable("PATH")?.Split(';') ?? Array.Empty<string>())
            {
                if (string.IsNullOrWhiteSpace(dir)) continue;
                var c = Path.Combine(dir, godotName);
                if (File.Exists(c)) return c;
            }

            // 5. Búsqueda relativa ascendente (servidor embebido del repo)
            string? current = ExeDir;
            for (int i = 0; i < 8 && current != null; i++)
            {
                var c1 = Path.Combine(current, "Servidor3D", godotName);
                if (File.Exists(c1)) return c1;
                var c2 = Path.Combine(current, "src", "VSC#", "Servidor3D", godotName);
                if (File.Exists(c2)) return c2;
                current = Directory.GetParent(current)?.FullName;
            }

            return string.Empty;
        }

        public static string GetProjectPath()
        {
            // 1. Recursos extraidos al LocalAppData
            if (Directory.Exists(AppExtractor.ProjectPath) && File.Exists(Path.Combine(AppExtractor.ProjectPath, "project.godot")))
                return AppExtractor.ProjectPath;

            // 2. Junto al exe publicado
            string nextToExe = Path.Combine(ExeDir, "MTBGT", "WoldVirtualP2P3D");
            if (Directory.Exists(nextToExe) && File.Exists(Path.Combine(nextToExe, "project.godot")))
                return nextToExe;

            // 3. Ruta absoluta del repositorio
            string repoPath = @"C:\Users\User\Desktop\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_2069d33a\src\MTBGT\WoldVirtualP2P3D";
            if (Directory.Exists(repoPath)) return repoPath;

            // 4. Busqueda relativa
            string? current = ExeDir;
            for (int i = 0; i < 8 && current != null; i++)
            {
                string c1 = Path.Combine(current, "MTBGT", "WoldVirtualP2P3D");
                if (Directory.Exists(c1)) return c1;
                string c2 = Path.Combine(current, "src", "MTBGT", "WoldVirtualP2P3D");
                if (Directory.Exists(c2)) return c2;
                current = Directory.GetParent(current)?.FullName;
            }
            return repoPath;
        }

        public static string GetScenePath() => "res://WoldVirtual3DP2P.tscn";
    }
}