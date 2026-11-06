using System;
using System.IO;
using System.Runtime.CompilerServices;

namespace Visor3D.Tests
{
    /// <summary>
    /// Aislamiento del entorno de pruebas. <see cref="Visor3D.Seguridad.SesionUnica.ReinicioCuenta"/>
    /// y <see cref="Visor3D.Seguridad.EstadoGlobal"/> tiran INFOs al log local, y
    /// <c>%LOCALAPPDATA%\WoldVirtualP2P3D\logs</c> es el fichero que el usuario copia
    /// y manda a soporte: ver ahí «base de usuarios reiniciada» por culpa de un test
    /// es un susto gratis. El módulo redirige el log a un temporal antes del primer test;
    /// la identidad de cuenta ya se aísla paso a paso con baseDir/godotDir.
    /// </summary>
    internal static class PruebasEntorno
    {
        internal static string CarpetaLog { get; private set; } = Path.GetTempPath();

        [ModuleInitializer]
        internal static void Configurar()
        {
            CarpetaLog = Path.Combine(Path.GetTempPath(), "wvp3d_pruebas_logs");
            Directory.CreateDirectory(CarpetaLog);
            Environment.SetEnvironmentVariable("WOLD_LOG_DIR", CarpetaLog);
        }
    }
}
