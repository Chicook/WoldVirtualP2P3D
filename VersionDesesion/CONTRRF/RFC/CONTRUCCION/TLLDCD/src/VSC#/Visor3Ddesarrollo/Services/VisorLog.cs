using System;
using System.IO;
using System.Linq;

namespace Visor3D.Services
{
    /// <summary>
    /// Log local con rotación (7 días) en %LOCALAPPDATA%\WoldVirtualP2P3D\logs.
    /// Nunca lanza: un fallo de log no debe tumbar el visor.
    /// </summary>
    public static class VisorLog
    {
        private static readonly object Candado = new();

        public static string Carpeta => Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WoldVirtualP2P3D", "logs");

        public static string ArchivoActual => Path.Combine(Carpeta, $"visor-{DateTime.Now:yyyyMMdd}.log");

        public static void Info(string mensaje) => Escribir("INFO", mensaje);
        public static void Warn(string mensaje) => Escribir("WARN", mensaje);
        public static void Error(string mensaje, Exception? ex = null) =>
            Escribir("ERROR", ex == null ? mensaje : $"{mensaje} :: {ex.GetType().Name}: {ex.Message}");

        private static void Escribir(string nivel, string mensaje)
        {
            try
            {
                Directory.CreateDirectory(Carpeta);
                string linea = $"{DateTime.Now:HH:mm:ss} [{nivel}] {mensaje}{Environment.NewLine}";
                lock (Candado)
                {
                    File.AppendAllText(ArchivoActual, linea);
                }
                Rotar();
            }
            catch
            {
                // El log nunca debe romper la app.
            }
        }

        private static void Rotar()
        {
            try
            {
                DateTime limite = DateTime.Now.AddDays(-7);
                foreach (string f in Directory.GetFiles(Carpeta, "visor-*.log"))
                {
                    if (File.GetLastWriteTime(f) < limite)
                    {
                        try { File.Delete(f); } catch { }
                    }
                }
            }
            catch { }
        }

        /// <summary>Últimas líneas del log de hoy (para «Copiar diagnóstico»).</summary>
        public static string Cola(int lineas = 40)
        {
            try
            {
                if (!File.Exists(ArchivoActual)) return "(sin registros hoy)";
                return string.Join(Environment.NewLine, File.ReadAllLines(ArchivoActual).TakeLast(lineas));
            }
            catch
            {
                return "(no se pudo leer el log)";
            }
        }
    }
}
