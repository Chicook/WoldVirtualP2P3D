// =============================================================================
// DiagnosticoPlataforma.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Telemetría y Señales de Riesgo de Plataforma
// =============================================================================

using System;
using System.Diagnostics;
using System.IO;
using System.Management;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using Microsoft.Win32;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Instantánea de telemetría y estado de seguridad del sistema operativo.
    ///
    /// AVISO DE SEGURIDAD (Zero Trust):
    ///   Las mediciones locales (Secure Boot, VBS, HVCI, DebugPort, Virtualización)
    ///   se consideran SEÑALES DE RIESGO para detección heurística de anomalías.
    ///   No constituyen pruebas de seguridad matemáticamente inviolables en un host
    ///   potencialmente hostil donde un atacante disponga de acceso al kernel o hipervisor.
    /// </summary>
    public sealed class EstadoPlataforma
    {
        public bool SecureBootActivo { get; set; }
        public bool VbsActivo { get; set; }
        public bool HvciActivo { get; set; }
        public bool TpmDisponible { get; set; }
        public string TpmVersion { get; set; } = string.Empty;
        public bool DepuradorDetectado { get; set; }
        public bool VirtualizacionDetectada { get; set; }
        public string HashEjecutable { get; set; } = string.Empty;
        public DateTime Timestamp { get; set; }
    }

    /// <summary>
    /// Recopilador de telemetría y comprobaciones de integridad del entorno de ejecución.
    /// </summary>
    public static class DiagnosticoPlataforma
    {
        private static readonly TimeSpan WmiTimeout = TimeSpan.FromSeconds(3);

        private static class NativeMethods
        {
            [DllImport("kernel32.dll", SetLastError = false, ExactSpelling = true)]
            [return: MarshalAs(UnmanagedType.Bool)]
            internal static extern bool IsDebuggerPresent();

            [DllImport("kernel32.dll", SetLastError = true, ExactSpelling = true)]
            [return: MarshalAs(UnmanagedType.Bool)]
            internal static extern bool CheckRemoteDebuggerPresent(
                IntPtr hProcess,
                [MarshalAs(UnmanagedType.Bool)] ref bool isDebuggerPresent);
        }

        public static EstadoPlataforma ObtenerEstadoActual()
        {
            var ep = new EstadoPlataforma
            {
                Timestamp              = DateTime.UtcNow,
                SecureBootActivo       = SecureBootActivo(),
                DepuradorDetectado     = DepuradorActivo(),
                VirtualizacionDetectada= DetectarVirtualizacion(),
                HashEjecutable         = ComputarHashEjecutable()
            };

            ep.VbsActivo = VbsActivoRapido();
            ep.HvciActivo = HvciActivoRapido();

            var (tpmOk, tpmVer) = ConsultarTpm();
            ep.TpmDisponible = tpmOk;
            ep.TpmVersion    = tpmVer;

            return ep;
        }

        public static bool DepuradorActivo()
        {
            try
            {
                if (NativeMethods.IsDebuggerPresent())
                    return true;

                bool remoto = false;
                IntPtr hProc = Process.GetCurrentProcess().Handle;
                if (NativeMethods.CheckRemoteDebuggerPresent(hProc, ref remoto) && remoto)
                    return true;

                if (Debugger.IsAttached)
                    return true;
            }
            catch { }
            return false;
        }

        public static bool VbsActivoRapido()
        {
            try
            {
                using var key = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Control\DeviceGuard");
                if (key != null)
                {
                    object? val = key.GetValue("VirtualizationBasedSecurityStatus");
                    if (val is int i && i == 2)
                        return true;
                }
            }
            catch { }
            return false;
        }

        public static bool HvciActivoRapido()
        {
            try
            {
                using var key = Registry.LocalMachine.OpenSubKey(
                    @"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity");
                if (key != null)
                {
                    object? val = key.GetValue("Enabled");
                    if (val is int i && i == 1)
                        return true;
                }
            }
            catch { }
            return false;
        }

        public static bool SecureBootActivo()
        {
            try
            {
                using var key = Registry.LocalMachine.OpenSubKey(
                    @"SYSTEM\CurrentControlSet\Control\SecureBoot\State");
                if (key != null)
                {
                    object? val = key.GetValue("UEFISecureBootEnabled");
                    if (val is int i && i == 1)
                        return true;
                }
            }
            catch { }
            return false;
        }

        private static bool DetectarVirtualizacion()
        {
            try
            {
                using var key = Registry.LocalMachine.OpenSubKey(@"HARDWARE\DESCRIPTION\System\BIOS");
                if (key != null)
                {
                    string mfg = (key.GetValue("SystemManufacturer") as string ?? "").ToLowerInvariant();
                    string prod = (key.GetValue("SystemProductName") as string ?? "").ToLowerInvariant();

                    string[] marcasVM = { "vmware", "virtualbox", "qemu", "kvm", "hyper-v", "xen", "parallels" };
                    foreach (var vm in marcasVM)
                    {
                        if (mfg.Contains(vm) || prod.Contains(vm))
                            return true;
                    }
                }
            }
            catch { }
            return false;
        }

        private static (bool disponible, string version) ConsultarTpm()
        {
            try
            {
                using var key = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Services\TPM\WMI");
                if (key != null)
                    return (true, "2.0");
            }
            catch { }
            return (false, string.Empty);
        }

        private static string ComputarHashEjecutable()
        {
            try
            {
                string? exePath = Process.GetCurrentProcess().MainModule?.FileName;
                if (!string.IsNullOrEmpty(exePath) && File.Exists(exePath))
                {
                    using var stream = File.OpenRead(exePath);
                    using var sha = SHA256.Create();
                    return Convert.ToHexString(sha.ComputeHash(stream)).ToLowerInvariant();
                }
            }
            catch { }
            return string.Empty;
        }
    }

    /// <summary>
    /// Alias de compatibilidad hacia atrás para código existente.
    /// </summary>
    [Obsolete("Utilizar DiagnosticoPlataforma; sus resultados son señales de riesgo heurísticas.")]
    public static class AtestacionPlataforma
    {
        public static EstadoPlataforma ObtenerEstadoActual() => DiagnosticoPlataforma.ObtenerEstadoActual();
        public static bool DepuradorActivo() => DiagnosticoPlataforma.DepuradorActivo();
        public static bool VbsActivoRapido() => DiagnosticoPlataforma.VbsActivoRapido();
        public static bool SecureBootActivo() => DiagnosticoPlataforma.SecureBootActivo();
    }

    /// <summary>
    /// Utilidades criptográficas internas compartidas en el namespace.
    /// </summary>
    internal static class CryptoUtils
    {
        internal static void ZeroMemory(byte[]? buffer)
        {
            if (buffer == null) return;
            CryptographicOperations.ZeroMemory(buffer.AsSpan());
        }
    }
}
