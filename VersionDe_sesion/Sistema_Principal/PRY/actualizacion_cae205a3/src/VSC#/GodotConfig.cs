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

        private static string Perfil =>
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);

        public static string GetGodotExePath()
        {
            string godotName = AppExtractor.NombreMotorWindows;

            // 1. Recursos extraidos al LocalAppData (exe standalone)
            if (File.Exists(AppExtractor.GodotExePath)) return AppExtractor.GodotExePath;

            // 2. Junto al exe publicado
            string nextToExe = Path.Combine(ExeDir, "Servidor3D", godotName);
            if (File.Exists(nextToExe)) return nextToExe;

            // 3. Motor suelto en el escritorio de la maquina de desarrollo
            string desktopGodot = Path.Combine(Perfil, "Desktop", godotName);
            if (File.Exists(desktopGodot)) return desktopGodot;

            // 4. Busqueda relativa subiendo carpetas. El arbol de trabajo se
            //    promociona como .../PRY/actualizacion_<hash>/src y el <hash> cambia
            //    en cada promocion, asi que ninguna ruta de este fichero puede fijar
            //    el nombre de la instantanea: se sube desde el exe hasta encontrar.
            string? current = ExeDir;
            for (int i = 0; i < 8 && current != null; i++)
            {
                string c1 = Path.Combine(current, "Servidor3D", godotName);
                if (File.Exists(c1)) return c1;
                string c2 = Path.Combine(current, "src", "VSC#", "Servidor3D", godotName);
                if (File.Exists(c2)) return c2;
                current = Directory.GetParent(current)?.FullName;
            }
            return nextToExe;
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

            // 3. Busqueda relativa: ver el comentario de GetGodotExePath, mismo criterio.
            string? current = ExeDir;
            for (int i = 0; i < 8 && current != null; i++)
            {
                string c1 = Path.Combine(current, "MTBGT", "WoldVirtualP2P3D");
                if (Directory.Exists(c1)) return c1;
                string c2 = Path.Combine(current, "src", "MTBGT", "WoldVirtualP2P3D");
                if (Directory.Exists(c2)) return c2;
                current = Directory.GetParent(current)?.FullName;
            }
            return nextToExe;
        }

        public static string GetScenePath() => "res://WoldVirtual3DP2P.tscn";

        /// <summary>
        /// Mundo empaquetado (PCK) para lanzar Godot con <c>--main-pack</c>.
        /// Primero el que extrae <see cref="AppExtractor"/>; si no, junto al .exe
        /// o subiendo carpetas (modo desarrollo). Devuelve "" si no hay PCK.
        /// </summary>
        public static string GetMainPackPath()
        {
            if (File.Exists(AppExtractor.PckPath)) return AppExtractor.PckPath;

            string nextToExe = Path.Combine(ExeDir, "wvp3d.pck");
            if (File.Exists(nextToExe)) return nextToExe;

            string? current = ExeDir;
            for (int i = 0; i < 8 && current != null; i++)
            {
                string c1 = Path.Combine(current, "wvp3d.pck");
                if (File.Exists(c1)) return c1;
                string c2 = Path.Combine(current, "src", "VSC#", "wvp3d.pck");
                if (File.Exists(c2)) return c2;
                current = Directory.GetParent(current)?.FullName;
            }
            return "";
        }
    }
}