using System;
using System.Collections.Generic;
using System.IO;

namespace Visor3D.Linux
{
    /// <summary>
    /// Rutas del paquete Linux. El tar desplegado es
    /// <c>WoldVirtualP2P3Dv2.7.2/{woldvirtual-linux, motor/, mundo/}</c>;
    /// en desarrollo se admite el árbol del repositorio y las variables
    /// <c>WOLD_MOTOR</c> / <c>WOLD_PCK</c> para apuntar a otra copia.
    /// </summary>
    public static class RutasLinux
    {
        public const string Version = "2.7.2";
        public const string NombreMotor = "Godot_v4.7.2-stable_linux.x86_64";
        public const string NombrePck = "wvp3d.pck";

        public static string BaseDir => AppContext.BaseDirectory;

        /// <summary>Ejecutable del motor Godot para Linux, o null si no está.</summary>
        public static string? MotorExe => BuscarArchivo(
            Environment.GetEnvironmentVariable("WOLD_MOTOR"),
            RuntimeLinux.MotorPath,
            Path.Combine("motor", NombreMotor),
            Path.Combine("Servidor3D", NombreMotor));

        /// <summary>Mundo empaquetado (PCK), o null si no está.</summary>
        public static string? Pck => BuscarArchivo(
            Environment.GetEnvironmentVariable("WOLD_PCK"),
            RuntimeLinux.PckPath,
            Path.Combine("mundo", NombrePck),
            NombrePck,
            Path.Combine("src", "VSC#", NombrePck));

        public static bool Disponible => MotorExe != null && Pck != null;

        /// <summary>
        /// <c>user://</c> del motor en Linux: <c>$XDG_DATA_HOME/godot/app_userdata/&lt;proyecto&gt;</c>
        /// (por defecto <c>~/.local/share</c>). No es la carpeta de Windows.
        /// </summary>
        public static string GodotUserDir
        {
            get
            {
                string? forzada = Environment.GetEnvironmentVariable("WOLD_GODOT_USER_DIR");
                if (!string.IsNullOrWhiteSpace(forzada)) return forzada;

                string? datos = Environment.GetEnvironmentVariable("XDG_DATA_HOME");
                if (string.IsNullOrWhiteSpace(datos))
                {
                    string casa = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
                    datos = Path.Combine(casa, ".local", "share");
                }
                return Path.Combine(datos, "godot", "app_userdata", "WoldVirtualP2P3D");
            }
        }

        /// <summary>Descripción corta para el panel de estado y el diagnóstico.</summary>
        public static string Resumen()
        {
            string motor = MotorExe ?? "(no encontrado)";
            string pck = Pck ?? "(no encontrado)";
            string runtime = RuntimeLinux.Extraido ? "extraído" : "sin extraer";
            return $"motor: {motor}{Environment.NewLine}PCK: {pck}{Environment.NewLine}" +
                   $"runtime: {RuntimeLinux.Dir} ({runtime}){Environment.NewLine}user:// del motor: {GodotUserDir}";
        }

        private static string? BuscarArchivo(string? forzada, params string[] relativos)
        {
            if (!string.IsNullOrWhiteSpace(forzada) && File.Exists(forzada)) return forzada;

            foreach (string raiz in Raices())
            {
                foreach (string relativo in relativos)
                {
                    string candidato = Path.Combine(raiz, relativo);
                    if (File.Exists(candidato)) return candidato;
                }
            }
            return null;
        }

        /// <summary>El directorio del binario y hasta cinco ancestros (modo desarrollo).</summary>
        private static IEnumerable<string> Raices()
        {
            string? actual = BaseDir;
            for (int i = 0; i < 6 && actual != null; i++)
            {
                yield return actual;
                actual = Directory.GetParent(actual)?.FullName;
            }
        }
    }
}
