using System;
using System.Diagnostics;
using System.IO;

namespace Visor3D.Update
{
    public static class UpdateApplier
    {
        public static void ApplyPendingUpdate(string currentExePath)
        {
            try
            {
                var baseDir = Path.Combine(AppContext.BaseDirectory, "STM_actualizar");
                var stateFile = Path.Combine(baseDir, "state.json");
                if (!File.Exists(stateFile)) return;

                var state = File.ReadAllText(stateFile);
                if (!state.Contains("\"apply\": true")) return;

                string? pendingExe = null;
                var pendingDir = Path.Combine(baseDir, "update-pending");
                if (Directory.Exists(pendingDir))
                {
                    foreach (var f in Directory.GetFiles(pendingDir, "*.exe"))
                    {
                        pendingExe = f;
                        break;
                    }
                }

                if (pendingExe == null || !File.Exists(pendingExe)) return;

                // No se puede reemplazar el .exe mientras est├í en ejecuci├│n.
                // Escribe un .bat desatendido que espera a que el visor cierre,
                // hace el reemplazo at├│mico y relanza el visor actualizado.
                var bat = Path.Combine(baseDir, "apply-pending.bat");
                File.WriteAllText(bat,
                    $"@echo off{Environment.NewLine}" +
                    $"timeout /t 2 /nobreak >nul{Environment.NewLine}" +
                    $"if exist \"{currentExePath}.old\" del /f /q \"{currentExePath}.old\"{Environment.NewLine}" +
                    $"ren \"{currentExePath}\" \"{currentExePath}.old\"{Environment.NewLine}" +
                    $"move /Y \"{pendingExe}\" \"{currentExePath}\"{Environment.NewLine}" +
                    $"del /f /q \"{stateFile}\"{Environment.NewLine}" +
                    $"rd /s /q \"{pendingDir}\" 2>nul{Environment.NewLine}" +
                    $"start \"\" \"{currentExePath}\"{Environment.NewLine}");

                var psi = new ProcessStartInfo(bat)
                {
                    UseShellExecute = true,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden
                };
                Process.Start(psi);
            }
            catch
            {
                // Si falla el reemplazo, el visor sigue funcionando con la versi├│n actual.
            }
        }
    }
}
