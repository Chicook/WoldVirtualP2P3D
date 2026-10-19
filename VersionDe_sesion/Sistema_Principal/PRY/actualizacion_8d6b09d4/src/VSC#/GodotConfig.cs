using System;
using System.Diagnostics;
using System.IO;

namespace Visor3D
{
    public static class GodotConfig
    {
        /// <summary>
        /// Directorio donde reside el .exe real (funciona tanto en desarrollo como en single-file publish).
        /// AppDomain.CurrentDomain.BaseDirectory devuelve un directorio temporal en single-file;
        /// Process.MainModule.FileName apunta siempre al .exe original.
        /// </summary>
        private static string ExeDir =>
            Path.GetDirectoryName(Process.GetCurrentProcess().MainModule?.FileName
                ?? AppDomain.CurrentDomain.BaseDirectory)
            ?? AppDomain.CurrentDomain.BaseDirectory;

        public static string GetGodotExePath()
        {
            const string godotName = "Godot_v4.7.2-stable_win64.exe";

            // 1. Junto al .exe publicado (Servidor3D/ copiado al lado del exe)
            string nextToExe = Path.Combine(ExeDir, "Servidor3D", godotName);
            if (File.Exists(nextToExe)) return nextToExe;

            // 2. Ruta absoluta correcta del repositorio actual
            string repoPath = @"C:\Users\User\Desktop\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_8d6b09d4\src\VSC#\Servidor3D\" + godotName;
            if (File.Exists(repoPath)) return repoPath;

            // 3. Búsqueda relativa subiendo desde el directorio del exe
            string? current = ExeDir;
            for (int i = 0; i < 8 && current != null; i++)
            {
                string c1 = Path.Combine(current, "Servidor3D", godotName);
                if (File.Exists(c1)) return c1;
                string c2 = Path.Combine(current, "src", "VSC#", "Servidor3D", godotName);
                if (File.Exists(c2)) return c2;
                current = Directory.GetParent(current)?.FullName;
            }

            // 4. Búsqueda desde AppDomain (modo debug / dotnet run)
            string? cur2 = AppDomain.CurrentDomain.BaseDirectory;
            for (int i = 0; i < 8 && cur2 != null; i++)
            {
                string c1 = Path.Combine(cur2, "Servidor3D", godotName);
                if (File.Exists(c1)) return c1;
                string c2 = Path.Combine(cur2, "src", "VSC#", "Servidor3D", godotName);
                if (File.Exists(c2)) return c2;
                cur2 = Directory.GetParent(cur2)?.FullName;
            }

            // Fallback: ruta repo (mostrará aviso claro si no existe)
            return repoPath;
        }

        public static string GetProjectPath()
        {
            const string projectSubPath = "WoldVirtualP2P3D";

            // 1. Junto al .exe publicado (MTBGT/ copiado al lado del exe)
            string nextToExe = Path.Combine(ExeDir, "MTBGT", projectSubPath);
            if (Directory.Exists(nextToExe)) return nextToExe;

            // 2. Ruta absoluta correcta del repositorio actual
            string repoPath = @"C:\Users\User\Desktop\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_8d6b09d4\src\MTBGT\WoldVirtualP2P3D";
            if (Directory.Exists(repoPath)) return repoPath;

            // 3. Búsqueda relativa subiendo desde el directorio del exe
            string? current = ExeDir;
            for (int i = 0; i < 8 && current != null; i++)
            {
                string c1 = Path.Combine(current, "MTBGT", projectSubPath);
                if (Directory.Exists(c1)) return c1;
                string c2 = Path.Combine(current, "src", "MTBGT", projectSubPath);
                if (Directory.Exists(c2)) return c2;
                current = Directory.GetParent(current)?.FullName;
            }

            // 4. Búsqueda desde AppDomain (modo debug)
            string? cur2 = AppDomain.CurrentDomain.BaseDirectory;
            for (int i = 0; i < 8 && cur2 != null; i++)
            {
                string c1 = Path.Combine(cur2, "MTBGT", projectSubPath);
                if (Directory.Exists(c1)) return c1;
                string c2 = Path.Combine(cur2, "src", "MTBGT", projectSubPath);
                if (Directory.Exists(c2)) return c2;
                cur2 = Directory.GetParent(cur2)?.FullName;
            }

            return repoPath;
        }

        public static string GetScenePath()
        {
            return "res://WoldVirtual3DP2P.tscn";
        }
    }
}
