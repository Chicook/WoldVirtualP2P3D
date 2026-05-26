using System;
using System.IO;

namespace WoldVirtual.EstadoGlobal.Helpers;

/// <summary>
/// Configuración global de rutas para el proyecto.
/// Resuelve la ubicación del proyecto de forma dinámica para evitar rutas hardcodeadas (RF-01).
/// </summary>
public static class GlobalConfig
{
    private static string? _rootDir;

    /// <summary>
    /// Obtiene la ruta raíz del proyecto (donde se encuentra WoldVirtual y Estado_Global).
    /// </summary>
    public static string RootDir
    {
        get
        {
            if (_rootDir == null)
            {
                // Intentamos detectar si estamos en el entorno de desarrollo o producción
                var baseDir = AppDomain.CurrentDomain.BaseDirectory;
                
                // Buscamos hacia arriba hasta encontrar la carpeta 'WoldVirtual' o 'Estado_Global'
                var current = new DirectoryInfo(baseDir);
                while (current != null && !Directory.Exists(Path.Combine(current.FullName, "Estado_Global")))
                {
                    current = current.Parent;
                }

                _rootDir = current?.FullName ?? baseDir;
            }
            return _rootDir;
        }
    }

    public static string EstadoGlobalDir => Path.Combine(RootDir, "Estado_Global");
    public static string PeersDir => Path.Combine(EstadoGlobalDir, "peers");
    public static string GodotProjectDir => Path.Combine(RootDir, "WoldVirtual");
    public static string AssetsDir => Path.Combine(GodotProjectDir, "woldvirtual");
}
