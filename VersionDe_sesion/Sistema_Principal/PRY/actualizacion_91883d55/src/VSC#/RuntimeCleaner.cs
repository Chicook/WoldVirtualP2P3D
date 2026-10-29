using System;
using System.Collections.Generic;
using System.IO;
using Visor3D.Services;

namespace Visor3D
{
    /// <summary>
    /// Recolector de <c>%LOCALAPPDATA%\WoldVirtualP2P3D\runtime</c>. Cada versión
    /// deja ahí su motor y su PCK (≈700 MB); sin recolector se acumulan sin límite.
    /// Se conservan siempre la versión en ejecución y la última que arrancó bien, y
    /// la purga sólo ocurre cuando el marcador <c>.arranque_ok</c> demuestra que el
    /// arranque anterior terminó, nunca antes de extraer la versión nueva.
    /// </summary>
    public static class RuntimeCleaner
    {
        private const string Marcador = ".arranque_ok";

        /// <summary>
        /// Purga, tras un arranque correcto de otra versión, las carpetas de runtime
        /// que no sean la vigente ni la última buena. No borra nada si la carpeta
        /// padre no se llama <c>runtime</c> (protege <c>WOLD_RUNTIME_DIR</c>).
        /// </summary>
        public static void EjecutarAlArrancar()
        {
            try
            {
                string? raiz = RaizRuntime();
                if (raiz == null) return;

                string marcador = Path.Combine(raiz, Marcador);
                if (!File.Exists(marcador)) return;

                string anterior = File.ReadAllText(marcador).Split('\n')[0].Trim();
                string vigente = AppExtractor.Version;
                if (anterior.Length == 0 ||
                    string.Equals(anterior, vigente, StringComparison.OrdinalIgnoreCase))
                    return;

                var (borradas, fallos) = PurgarAntiguos(raiz, vigente, anterior);
                if (borradas.Count > 0)
                    VisorLog.Info($"[runtime] Purga tras arranque correcto de {anterior}: " +
                                  $"borradas [{string.Join(", ", borradas)}]");
                foreach (var fallo in fallos)
                    VisorLog.Info($"[runtime] No se pudo borrar {fallo}");
            }
            catch (Exception ex)
            {
                VisorLog.Info($"[runtime] Recolector omitido: {ex.GetType().Name}: {ex.Message}");
            }
        }

        /// <summary>Deja constancia de que esta versión llegó a mostrar la ventana.</summary>
        public static void MarcarArranqueCorrecto()
        {
            try
            {
                string? raiz = RaizRuntime();
                if (raiz == null) return;

                Directory.CreateDirectory(raiz);
                File.WriteAllText(
                    Path.Combine(raiz, Marcador),
                    AppExtractor.Version + Environment.NewLine + DateTime.UtcNow.ToString("o"));
            }
            catch (Exception ex)
            {
                VisorLog.Info($"[runtime] No se pudo marcar el arranque: {ex.GetType().Name}: {ex.Message}");
            }
        }

        /// <summary>
        /// Borra las carpetas de <paramref name="raiz"/> salvo la vigente y la última
        /// buena. Devuelve las borradas y los errores, para poder probarlo aislado.
        /// </summary>
        public static (List<string> Borradas, List<string> Fallos) PurgarAntiguos(
            string raiz, string vigente, string anterior)
        {
            var borradas = new List<string>();
            var fallos = new List<string>();

            foreach (string dir in Directory.GetDirectories(raiz))
            {
                string nombre = Path.GetFileName(dir);
                if (string.Equals(nombre, vigente, StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(nombre, anterior, StringComparison.OrdinalIgnoreCase))
                    continue;

                try
                {
                    Directory.Delete(dir, recursive: true);
                    borradas.Add(nombre);
                }
                catch (Exception ex)
                {
                    fallos.Add($"{nombre} ({ex.GetType().Name})");
                }
            }

            return (borradas, fallos);
        }

        /// <summary>
        /// Carpeta <c>runtime</c> que contiene a la versión vigente, o <c>null</c>
        /// cuando <c>WOLD_RUNTIME_DIR</c> apunta a una ruta propia de pruebas.
        /// </summary>
        private static string? RaizRuntime()
        {
            string? raiz = Path.GetDirectoryName(AppExtractor.RuntimeDir.TrimEnd('\\', '/'));
            if (string.IsNullOrWhiteSpace(raiz)) return null;
            if (!string.Equals(new DirectoryInfo(raiz).Name, "runtime", StringComparison.OrdinalIgnoreCase))
                return null;
            return raiz;
        }
    }
}
