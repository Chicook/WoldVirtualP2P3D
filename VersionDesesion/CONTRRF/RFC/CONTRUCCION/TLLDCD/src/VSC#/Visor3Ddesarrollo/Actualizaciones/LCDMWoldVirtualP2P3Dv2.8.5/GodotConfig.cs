using System;
using System.Collections.Generic;
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

        /// <summary>Nombres que ha tenido la carpeta raíz del proyecto en disco.</summary>
        private static readonly string[] NombresVersion = { "VersionDesesion", "VersionDe_sesion" };

        /// <summary>Nombres que ha tenido la carpeta de sistema dentro de la raíz.</summary>
        private static readonly string[] NombresSistema = { "SistemaPrincipal", "Sistema_Principal" };

        /// <summary>
        /// Raíz del repositorio: la carpeta que contiene la carpeta de versión
        /// (con CONTRRF dentro). Se sube desde el ejecutable, el proyecto Godot
        /// y el directorio actual. Null cuando no hay árbol de desarrollo.
        /// </summary>
        public static string? RepoRoot()
        {
            foreach (string? inicio in new[] { ExeDir, AppExtractor.ProjectPath, Directory.GetCurrentDirectory() })
            {
                if (string.IsNullOrWhiteSpace(inicio)) continue;
                DirectoryInfo? dir;
                try { dir = new DirectoryInfo(inicio); }
                catch { continue; }

                while (dir != null)
                {
                    try
                    {
                        foreach (string nombre in NombresVersion)
                        {
                            if (Directory.Exists(Path.Combine(dir.FullName, nombre, "CONTRRF")))
                                return dir.FullName;
                        }
                    }
                    catch { }
                    dir = dir.Parent;
                }
            }
            return null;
        }

        /// <summary>Carpeta de versión dentro del repositorio, con el nombre que tenga en disco.</summary>
        private static string? VersionDir(string repo)
        {
            foreach (string nombre in NombresVersion)
            {
                string ruta = Path.Combine(repo, nombre);
                if (Directory.Exists(ruta)) return ruta;
            }
            return null;
        }

        /// <summary>Raíz src del árbol activo (CONTRRF\RFC\CONTRUCCION\TLLDCD\src).</summary>
        public static string? SrcActivo()
        {
            string? repo = RepoRoot();
            if (repo == null) return null;
            string? version = VersionDir(repo);
            if (version == null) return null;
            string ruta = Path.Combine(version, "CONTRRF", "RFC", "CONTRUCCION", "TLLDCD", "src");
            return Directory.Exists(ruta) ? ruta : null;
        }

        /// <summary>
        /// Raíces src de versiones anteriores, de la más reciente a la más vieja:
        /// PRY\Archivo\VersionesDeRefuerzo\actualizacion_*\src (layout actual) y
        /// PRY\actualizacion_*\src (layout previo a la reorganización).
        /// Ahí viven los binarios que no se versionan, como LC_STM\python.
        /// </summary>
        public static string[] SrcLegado()
        {
            string? repo = RepoRoot();
            if (repo == null) return Array.Empty<string>();

            string? version = VersionDir(repo);
            string? sistema = null;
            if (version != null)
            {
                foreach (string nombre in NombresSistema)
                {
                    string ruta = Path.Combine(version, nombre);
                    if (Directory.Exists(ruta)) { sistema = ruta; break; }
                }
            }
            if (sistema == null) return Array.Empty<string>();

            var encontrados = new List<(DateTime, string)>();
            void Recoger(string carpeta)
            {
                try
                {
                    if (!Directory.Exists(carpeta)) return;
                    foreach (string anterior in Directory.GetDirectories(carpeta, "actualizacion_*"))
                    {
                        string src = Path.Combine(anterior, "src");
                        if (!Directory.Exists(src)) continue;
                        DateTime fecha;
                        try { fecha = Directory.GetLastWriteTimeUtc(anterior); }
                        catch { fecha = DateTime.MinValue; }
                        encontrados.Add((fecha, src));
                    }
                }
                catch { }
            }

            string pry = Path.Combine(sistema, "PRY");
            Recoger(Path.Combine(pry, "Archivo", "VersionesDeRefuerzo"));
            Recoger(pry);

            encontrados.Sort((a, b) => b.Item1.CompareTo(a.Item1));
            var rutas = new string[encontrados.Count];
            for (int i = 0; i < encontrados.Count; i++) rutas[i] = encontrados[i].Item2;
            return rutas;
        }

        /// <summary>Raíces src conocidas: el árbol activo primero, luego el archivo.</summary>
        public static string[] SrcCandidatos()
        {
            var lista = new List<string>();
            string? activo = SrcActivo();
            if (activo != null) lista.Add(activo);
            lista.AddRange(SrcLegado());
            return lista.ToArray();
        }

        /// <summary>Python en el nuevo sistema de desarrollo (.dev) o embebido en el activo/archivo.</summary>
        public static string? GetPythonExePath()
        {
            string? envPython = Environment.GetEnvironmentVariable("WVP_PYTHON");
            if (!string.IsNullOrWhiteSpace(envPython) && File.Exists(envPython)) return envPython;

            string? envVenv = Environment.GetEnvironmentVariable("VIRTUAL_ENV");
            if (!string.IsNullOrWhiteSpace(envVenv))
            {
                string venvExe = Path.Combine(envVenv, "Scripts", "python.exe");
                if (File.Exists(venvExe)) return venvExe;
            }

            string? repo = RepoRoot();
            if (repo != null)
            {
                foreach (string cand in new[]
                {
                    Path.Combine(repo, "VersionDesesion", "CONTRRF", "RFC", "CONTRUCCION", ".dev", ".python", "python.exe"),
                    Path.Combine(repo, "VersionDesesion", "CONTRRF", "RFC", "CONTRUCCION", ".dev", "venv", "Scripts", "python.exe"),
                })
                {
                    if (File.Exists(cand)) return cand;
                }
            }

            foreach (string src in SrcCandidatos())
            {
                string exe = Path.Combine(src, "LC_STM", "python", "python.exe");
                if (File.Exists(exe)) return exe;
            }
            return null;
        }

        public static string? GetPythonwExePath()
        {
            string? repo = RepoRoot();
            if (repo != null)
            {
                foreach (string cand in new[]
                {
                    Path.Combine(repo, "VersionDesesion", "CONTRRF", "RFC", "CONTRUCCION", ".dev", ".python", "pythonw.exe"),
                    Path.Combine(repo, "VersionDesesion", "CONTRRF", "RFC", "CONTRUCCION", ".dev", "venv", "Scripts", "pythonw.exe"),
                })
                {
                    if (File.Exists(cand)) return cand;
                }
            }

            foreach (string src in SrcCandidatos())
            {
                string exe = Path.Combine(src, "LC_STM", "python", "pythonw.exe");
                if (File.Exists(exe)) return exe;
            }
            return null;
        }

        public static string GetGodotExePath()
        {
            const string godotName = "Godot_v4.7.2-stable_win64.exe";

            // 1. Recursos extraidos al LocalAppData (exe standalone)
            if (File.Exists(AppExtractor.GodotExePath)) return AppExtractor.GodotExePath;

            // 2. Junto al exe publicado
            string nextToExe = Path.Combine(ExeDir, "Servidor3D", godotName);
            if (File.Exists(nextToExe)) return nextToExe;

            // 3. Árboles de desarrollo: activo (RFC\CONTRUCCION\TLLDCD\src) y archivo
            foreach (string src in SrcCandidatos())
            {
                string candidato = Path.Combine(src, "VSC#", "Servidor3D", godotName);
                if (File.Exists(candidato)) return candidato;
            }

            string desktopGodot = @"C:\Users\User\Desktop\" + godotName;
            if (File.Exists(desktopGodot)) return desktopGodot;

            // 4. Busqueda relativa subiendo carpetas
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

            // 3. Arbol de desarrollo actual (TLLDCD/src/MTBGT), subiendo carpetas
            //    desde el exe. Va antes que las rutas historicas: el arbol viejo
            //    no tiene _importar_construccion_editor y la escena del editor
            //    nunca llegaria a la isla.
            string? current = ExeDir;
            for (int i = 0; i < 12 && current != null; i++)
            {
                foreach (string candidata in new[]
                {
                    Path.Combine(current, "src", "MTBGT", "WoldVirtualP2P3D"),
                    Path.Combine(current, "MTBGT", "WoldVirtualP2P3D"),
                })
                {
                    if (File.Exists(Path.Combine(candidata, "project.godot")))
                        return candidata;
                }
                current = Directory.GetParent(current)?.FullName;
            }

            // 4. Árboles de desarrollo: activo (RFC\CONTRUCCION\TLLDCD\src) y archivo
            string? primero = null;
            foreach (string src in SrcCandidatos())
            {
                string candidata = Path.Combine(src, "MTBGT", "WoldVirtualP2P3D");
                primero ??= candidata;
                if (File.Exists(Path.Combine(candidata, "project.godot"))) return candidata;
            }

            return primero ?? Path.Combine(ExeDir, "MTBGT", "WoldVirtualP2P3D");
        }

        public static string GetScenePath() => "res://WoldVirtual3DP2P.tscn";

        /// <summary>
        /// Mundo empaquetado (PCK) para lanzar Godot con <c>--main-pack</c>.
        /// Primero el que extrae <see cref="AppExtractor"/>; si no, junto al .exe
        /// o subiendo carpetas (modo desarrollo). Devuelve "" si no hay PCK.
        /// </summary>
        public static string GetMainPackPath()
        {
            // 1. Paquete volátil (embebido en el .exe, materializado en %TEMP%)
            string? volatil = Visor3D.CargaVolatil.VolatilePackage.PckVolatilPath;
            if (!string.IsNullOrEmpty(volatil) && File.Exists(volatil)) return volatil;

            if (File.Exists(AppExtractor.PckPath)) return AppExtractor.PckPath;

            string nextToExe = Path.Combine(ExeDir, "wvp3d.pck");
            if (File.Exists(nextToExe)) return nextToExe;

            // En el árbol de desarrollo el export vive en CopiaDeSeguridad
            foreach (string src in SrcCandidatos())
            {
                foreach (string cand in new[]
                {
                    Path.Combine(src, "VSC#", "Visor3Ddesarrollo", "CopiaDeSeguridad", "wvp3d.pck"),
                    Path.Combine(src, "VSC#", "Visor3Ddesarrollo", "wvp3d.pck"),
                    Path.Combine(src, "VSC#", "wvp3d.pck"),
                })
                {
                    if (File.Exists(cand)) return cand;
                }
            }

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