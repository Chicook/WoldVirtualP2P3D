// =============================================================================
// EndurecimientoProceso.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Mitigaciones de Proceso y Defensa en Profundidad (Windows)
// =============================================================================

using System;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace Visor3D.Seguridad.SesionUnica
{
    public sealed record EstadoEndurecimiento(
        bool DepuradorPresente,
        bool DllSearchRestringido,
        bool DepHabilitado,
        string Diagnostico);

    /// <summary>
    /// Aplica mitigaciones de proceso nativas de Windows documentadas y compatibles
    /// con .NET 8 / WPF / single-file, evitando romper el compilador JIT o DLLs de la solución.
    /// </summary>
    public static class EndurecimientoProceso
    {
        private const uint LOAD_LIBRARY_SEARCH_DEFAULT_DIRS = 0x00001000;
        private const uint PROCESS_DEP_ENABLE = 0x00000001;

        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern bool SetDllDirectory(string lpPathName);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetDefaultDllDirectories(uint DirectoryFlags);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetProcessDEPPolicy(uint dwFlags);

        [DllImport("kernel32.dll", ExactSpelling = true)]
        private static extern bool IsDebuggerPresent();

        [DllImport("kernel32.dll", SetLastError = true, ExactSpelling = true)]
        private static extern bool CheckRemoteDebuggerPresent(IntPtr hProcess, ref bool isDebuggerPresent);

        private static bool _dllSearchRestringido = false;
        private static bool _depHabilitado = false;

        /// <summary>
        /// Aplica las mitigaciones de proceso compatibles al iniciar la aplicación.
        /// </summary>
        public static void AplicarMitigaciones()
        {
            try
            {
                // 1. Restringir la búsqueda de DLLs para neutralizar DLL Search Order Hijacking
                // Quitar el directorio de trabajo actual (CWD) de la ruta de búsqueda
                SetDllDirectory(string.Empty);
                _dllSearchRestringido = SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
            }
            catch { }

            try
            {
                // 2. Aplicar Data Execution Prevention (DEP) estricto
                _depHabilitado = SetProcessDEPPolicy(PROCESS_DEP_ENABLE);
            }
            catch { }
        }

        /// <summary>
        /// Evalúa la presencia de depuradores activos o adjuntos.
        /// </summary>
        public static bool EsDepuradorPresente()
        {
#if DEBUG
            // En modo desarrollo/depuración, permitir pruebas sin bloqueo
            return false;
#else
            if (Debugger.IsAttached) return true;
            if (IsDebuggerPresent()) return true;

            bool remoteDebugger = false;
            try
            {
                CheckRemoteDebuggerPresent(Process.GetCurrentProcess().Handle, ref remoteDebugger);
            }
            catch { }

            return remoteDebugger;
#endif
        }

        /// <summary>
        /// Diagnostica el estado general de mitigaciones y riesgos de proceso.
        /// </summary>
        public static EstadoEndurecimiento Diagnosticar()
        {
            bool depurador = EsDepuradorPresente();
            string diag = depurador
                ? "ALERTA: Depurador de procesos detectado. Modo restringido activo para operaciones sensibles."
                : "Mitigaciones de proceso y búsqueda de DLLs activas.";

            return new EstadoEndurecimiento(
                DepuradorPresente: depurador,
                DllSearchRestringido: _dllSearchRestringido,
                DepHabilitado: _depHabilitado,
                Diagnostico: diag);
        }
    }
}
