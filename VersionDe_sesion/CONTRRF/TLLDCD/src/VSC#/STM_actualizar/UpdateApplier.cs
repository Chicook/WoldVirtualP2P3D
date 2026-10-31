using System;
using System.Diagnostics;
using System.IO;
using System.Text.Json;

namespace Visor3D.Update
{
    /// <summary>
    /// Aplica la actualización descargada. Como el visor se distribuye como un
    /// ÚNICO .exe, no puede sobrescribirse a sí mismo mientras se ejecuta. La
    /// técnica segura en Windows es delegar en un script por lotes que:
    ///   1) espera a que el proceso actual termine,
    ///   2) sustituye el binario (con REINTENTOS para evitar "Access Denied"),
    ///   3) relanza el visor ya actualizado,
    ///   4) se autodestruye.
    /// Esto evita cualquier problema de bloqueo de archivo o de permisos.
    /// </summary>
    public static class UpdateApplier
    {
        private static readonly string BaseDir =
            Path.Combine(AppContext.BaseDirectory, "STM_actualizar");

        private static string StateFile => Path.Combine(BaseDir, "state.json");
        private static string PendingDir => Path.Combine(BaseDir, "update-pending");

        /// <summary>
        /// Si hay una actualización pendiente marcada como "apply", arranca el
        /// script de reemplazo y devuelve true. El llamador debe cerrar la app
        /// inmediatamente después para liberar el .exe.
        /// </summary>
        public static bool ApplyPendingUpdate(string? currentExePath = null)
        {
            try
            {
                if (!File.Exists(StateFile)) return false;

                // Sólo se aplica si el estado lo indica explícitamente.
                using (var doc = JsonDocument.Parse(File.ReadAllText(StateFile)))
                {
                    if (!doc.RootElement.TryGetProperty("apply", out var apply) || !apply.GetBoolean())
                        return false;
                }

                if (!Directory.Exists(PendingDir)) return false;

                string? nuevoExe = null;
                foreach (var f in Directory.GetFiles(PendingDir, "*.exe"))
                {
                    nuevoExe = f;
                    break;
                }
                if (nuevoExe == null) return false;

                // Ruta del ejecutable en curso (funciona también en single-file).
                string exeActual = currentExePath ?? Environment.ProcessPath ?? "";
                if (string.IsNullOrWhiteSpace(exeActual) || !File.Exists(exeActual))
                    return false;

                string bat = Path.Combine(BaseDir, "apply-pending.bat");
                File.WriteAllText(bat, ConstruirScript(exeActual, nuevoExe, Environment.ProcessId));

                var psi = new ProcessStartInfo
                {
                    FileName = bat,
                    UseShellExecute = true,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden,
                    WorkingDirectory = BaseDir
                };
                Process.Start(psi);
                return true;
            }
            catch
            {
                // Si falla, el visor sigue funcionando con la versión actual.
                return false;
            }
        }

        /// <summary>
        /// Genera el .bat de reemplazo. Nada de elevar privilegios: el visor es
        /// portable (se ejecuta desde una carpeta con permiso de escritura), por
        /// lo que basta con reintentar hasta que el .exe quede desbloqueado.
        /// La espera se hace por PID (preciso) y no por nombre de imagen.
        /// </summary>
        private static string ConstruirScript(string exeActual, string nuevoExe, int pid)
        {
            string exeDir = Path.GetDirectoryName(exeActual) ?? ".";

            return $$"""
                @echo off
                setlocal enabledelayedexpansion
                title Wold Virtual P2P 3D - Actualizador

                set "PID={{pid}}"
                set "EXE={{exeActual}}"
                set "EXEDIR={{exeDir}}"
                set "NEWEXE={{nuevoExe}}"
                set "STATEDIR={{BaseDir}}"

                rem --- 1) Esperar a que el visor principal termine (por PID, max ~120 s) ---
                set /a WAIT=0
                :wait_exit
                tasklist /FI "PID eq %PID%" 2>NUL | find /I "%PID%" >NUL
                if not errorlevel 1 (
                    timeout /t 1 /nobreak >NUL
                    set /a WAIT+=1
                    if !WAIT! LSS 120 goto wait_exit
                )
                timeout /t 2 /nobreak >NUL

                rem --- 2) Respaldar el binario actual y colocar el nuevo ---
                if exist "%EXE%.old" del /f /q "%EXE%.old" >NUL 2>&1
                set /a TRY=0
                :retry_rename
                move /Y "%EXE%" "%EXE%.old" >NUL 2>&1
                if errorlevel 1 (
                    set /a TRY+=1
                    if !TRY! LSS 20 (
                        timeout /t 1 /nobreak >NUL
                        goto retry_rename
                    )
                )
                set /a TRY=0
                :retry_copy
                copy /Y "%NEWEXE%" "%EXE%" >NUL 2>&1
                if errorlevel 1 (
                    set /a TRY+=1
                    if !TRY! LSS 20 (
                        timeout /t 1 /nobreak >NUL
                        goto retry_copy
                    )
                )

                rem --- 3) Limpieza de residuos ---
                del /f /q "%NEWEXE%" >NUL 2>&1
                rd /s /q "%STATEDIR%\update-pending" >NUL 2>&1
                del /f /q "%STATEDIR%\state.json" >NUL 2>&1

                rem --- 4) Relanzar el visor ya actualizado ---
                if exist "%EXE%" start "" /D "%EXEDIR%" "%EXE%"

                rem --- 5) Autodestruccion del script ---
                (goto) 2>nul & del "%~f0"
                """;
        }
    }
}
