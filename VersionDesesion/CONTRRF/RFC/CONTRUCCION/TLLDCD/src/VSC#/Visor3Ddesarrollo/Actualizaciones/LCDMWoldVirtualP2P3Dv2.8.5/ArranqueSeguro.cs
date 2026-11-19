using System;
using System.Diagnostics;
using System.IO;
using Visor3D.Services;

namespace Visor3D.Seguridad
{
    /// <summary>
    /// Puerta de arranque *fail-closed* con el subsistema defensivo STM_DEF
    /// (<c>STM_HRTS\STM_DEF</c>). Antes de abrir el visor se ejecuta el hook
    /// <c>arranque</c> de STM_DEF —escaneo estático del árbol + verificación del
    /// sello de integridad— y, si el veredicto es de bloqueo (hallazgo ALTA o
    /// sello manipulado), el arranque se DETIENE.
    ///
    /// Es el mismo paso del dropper, invertido: aquel ejecutaba sin comprobar;
    /// aquí no se abre ventana sin comprobar antes. Este servicio sólo lanza la
    /// comprobación y lee su veredicto: nunca modifica, descarga ni ejecuta nada.
    ///
    /// Si el árbol Python no está presente (una release publicada no lo incluye)
    /// o no hay intérprete disponible, la comprobación no bloquea —no puede
    /// exigirse una línea base ausente— y queda registrado en el log.
    /// </summary>
    public static class ArranqueSeguro
    {
        /// <summary>Ruta relativa del subsistema defensivo dentro de la raíz <c>src</c>.</summary>
        private static readonly string[] Marca = { "STM_HRTS", "STM_DEF", "arranque.py" };

        /// <summary>Intérpretes Python a probar, en orden de preferencia.</summary>
        private static readonly string[] Interpretes = { "python", "py", "python3" };

        /// <summary>Milisegundos máximos que se espera el hook antes de permitir el arranque.</summary>
        private const int EsperaMs = 60_000;

        /// <summary>True si STM_DEF dictamina que el arranque debe detenerse.</summary>
        public static bool Bloquea() => Comprobar() == Veredicto.Detener;

        private enum Veredicto { Permitir, Detener }

        private static Veredicto Comprobar()
        {
            string? raiz = LocalizarRaiz();
            if (raiz is null)
            {
                VisorLog.Info("[STM_DEF] Arbol defensivo no presente: arranque permitido (sin linea base).");
                return Veredicto.Permitir;
            }

            string? interprete = LocalizarPython(raiz);
            if (interprete is null)
            {
                VisorLog.Warn("[STM_DEF] Interprete Python no disponible: arranque permitido sin comprobacion.");
                return Veredicto.Permitir;
            }

            try
            {
                var ps = new ProcessStartInfo
                {
                    FileName = interprete,
                    WorkingDirectory = raiz,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                };
                ps.ArgumentList.Add("-m");
                ps.ArgumentList.Add("STM_HRTS.STM_DEF");
                ps.ArgumentList.Add("arranque");

                using var proceso = Process.Start(ps);
                if (proceso is null)
                {
                    VisorLog.Warn("[STM_DEF] No se pudo iniciar el hook de arranque: se permite el arranque.");
                    return Veredicto.Permitir;
                }

                string salida = proceso.StandardOutput.ReadToEnd();
                string error = proceso.StandardError.ReadToEnd();
                if (!proceso.WaitForExit(EsperaMs))
                {
                    try { proceso.Kill(entireProcessTree: true); } catch { }
                    VisorLog.Warn("[STM_DEF] El hook de arranque excedio el tiempo: se permite el arranque.");
                    return Veredicto.Permitir;
                }

                // Códigos de salida de STM_DEF: 0 limpio, 1 bloqueo, 2 uso incorrecto.
                if (proceso.ExitCode == 1)
                {
                    VisorLog.Error($"[STM_DEF] ARRANQUE DETENIDO (fail-closed). {salida.Trim()} {error.Trim()}".Trim());
                    return Veredicto.Detener;
                }

                VisorLog.Info("[STM_DEF] Arranque permitido: escaneo e integridad sin bloqueos.");
                return Veredicto.Permitir;
            }
            catch (Exception ex)
            {
                VisorLog.Warn($"[STM_DEF] Fallo al ejecutar el hook de arranque: {ex.GetType().Name}: {ex.Message}. Se permite el arranque.");
                return Veredicto.Permitir;
            }
        }

        /// <summary>
        /// Sube desde el directorio del ejecutable y desde el directorio actual
        /// hasta encontrar la raíz <c>src</c> que contiene <c>STM_HRTS\STM_DEF</c>.
        /// </summary>
        private static string? LocalizarRaiz()
        {
            foreach (string inicio in new[] { AppContext.BaseDirectory, Directory.GetCurrentDirectory() })
            {
                DirectoryInfo? dir;
                try { dir = new DirectoryInfo(inicio); }
                catch { continue; }

                while (dir is not null)
                {
                    try
                    {
                        if (File.Exists(Path.Combine(dir.FullName, Path.Combine(Marca))))
                            return dir.FullName;
                    }
                    catch { }
                    dir = dir.Parent;
                }
            }
            return null;
        }

        /// <summary>Primer intérprete Python que responde a <c>--version</c>, o null.</summary>
        private static string? LocalizarPython(string raiz)
        {
            foreach (string candidato in Interpretes)
            {
                try
                {
                    var ps = new ProcessStartInfo
                    {
                        FileName = candidato,
                        WorkingDirectory = raiz,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                    };
                    ps.ArgumentList.Add("--version");

                    using var proceso = Process.Start(ps);
                    if (proceso is null) continue;
                    if (!proceso.WaitForExit(10_000))
                    {
                        try { proceso.Kill(entireProcessTree: true); } catch { }
                        continue;
                    }
                    if (proceso.ExitCode == 0)
                        return candidato;
                }
                catch
                {
                    // Intérprete inexistente: se prueba el siguiente.
                }
            }
            return null;
        }
    }
}
