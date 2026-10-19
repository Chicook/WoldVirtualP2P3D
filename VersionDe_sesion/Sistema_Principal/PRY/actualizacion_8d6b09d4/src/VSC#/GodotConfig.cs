using System;
using System.IO;

namespace Visor3D
{
    public static class GodotConfig
    {
        public static string GetGodotExePath()
        {
            // 1. Ruta absoluta directa solicitada por el usuario
            string direct = @"C:\Users\User\Desktop\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\VSC#\Servidor3D\Godot_v4.7.2-stable_win64.exe";
            if (File.Exists(direct)) return direct;

            // Alternativa consola si existiera
            string directConsole = @"C:\Users\User\Desktop\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\VSC#\Servidor3D\Godot_v4.7.2-stable_win64_console.exe";
            if (File.Exists(directConsole)) return directConsole;

            // 2. Búsqueda relativa desde AppDomain
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string rel = Path.Combine(baseDir, "Servidor3D", "Godot_v4.7.2-stable_win64.exe");
            if (File.Exists(rel)) return rel;

            string? current = baseDir;
            for (int i = 0; i < 6 && current != null; i++)
            {
                string c1 = Path.Combine(current, "Servidor3D", "Godot_v4.7.2-stable_win64.exe");
                if (File.Exists(c1)) return c1;
                string c2 = Path.Combine(current, "src", "VSC#", "Servidor3D", "Godot_v4.7.2-stable_win64.exe");
                if (File.Exists(c2)) return c2;
                current = Directory.GetParent(current)?.FullName;
            }

            return direct;
        }

        public static string GetProjectPath()
        {
            // 1. Ruta absoluta directa del proyecto Godot solicitada
            string direct = @"C:\Users\User\Desktop\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\MTBGT\WoldVirtualP2P3D";
            if (Directory.Exists(direct)) return direct;

            // 2. Búsqueda relativa
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string? current = baseDir;
            for (int i = 0; i < 6 && current != null; i++)
            {
                string c1 = Path.Combine(current, "MTBGT", "WoldVirtualP2P3D");
                if (Directory.Exists(c1)) return c1;
                string c2 = Path.Combine(current, "src", "MTBGT", "WoldVirtualP2P3D");
                if (Directory.Exists(c2)) return c2;
                current = Directory.GetParent(current)?.FullName;
            }

            return direct;
        }

        public static string GetScenePath()
        {
            // La escena solicitada WoldVirtual3DP2P.tscn
            return "res://WoldVirtual3DP2P.tscn";
        }
    }
}
