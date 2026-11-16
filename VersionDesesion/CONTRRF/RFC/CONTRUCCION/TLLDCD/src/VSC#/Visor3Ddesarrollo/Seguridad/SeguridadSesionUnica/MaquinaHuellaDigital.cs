using System;
using System.Collections.Generic;
using System.Management;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using Microsoft.Win32;

namespace Visor3D.Seguridad.SesionUnica
{
    public sealed class HuellaComponentes
    {
        public string BaseboardHash { get; init; } = "";
        public string CpuHash { get; init; } = "";
        public string BiosHash { get; init; } = "";
        public string DiskHash { get; init; } = "";
        public string MachineGuidHash { get; init; } = "";

        public string[] ObtenerLista() =>
            new[] { BaseboardHash, CpuHash, BiosHash, DiskHash, MachineGuidHash };
    }

    /// <summary>
    /// Extracción optimizada, anónima y tolerante a fallos de hardware con coincidencia difusa (3/5).
    /// Cumple RGPD: ningún número de serie se guarda ni procesa en texto claro.
    /// Incorpora consulta nativa ultra-rápida de SMBIOS (GetSystemFirmwareTable) con fallback a WMI.
    /// </summary>
    public static class MaquinaHuellaDigital
    {
        private static readonly byte[] SaltRgpd = Encoding.UTF8.GetBytes("WVP3D::RGPD::HW_ANON::v3");
        private static readonly byte[] SaltApp = Encoding.UTF8.GetBytes("WoldVirtualP2P3D::SesionUnica::v3");

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint GetSystemFirmwareTable(
            uint firmwareTableProviderSignature,
            uint firmwareTableID,
            IntPtr pFirmwareTableBuffer,
            uint bufferSize);

        private const uint FIRMWARE_TABLE_RSMB = 0x52534D42; // 'RSMB' en ASCII

        // Caché en memoria thread-safe sin bloquear excepciones permanentemente (PublicationOnly)
        private static readonly Lazy<HuellaComponentes> CacheComponentes =
            new(ExtraerComponentesSeguros, LazyThreadSafetyMode.PublicationOnly);

        private static readonly Lazy<string> CacheHuellaUnificada =
            new(() => DerivarHuellaHex(CacheComponentes.Value), LazyThreadSafetyMode.PublicationOnly);

        /// <summary>
        /// Obtiene la huella unificada en formato hexadecimal (256 bits).
        /// Tras el primer cálculo, se resuelve desde la caché estática en ~0.001 ms sin consultar WMI.
        /// </summary>
        public static string Obtener() => CacheHuellaUnificada.Value;

        public static byte[] ObtenerBytes() => Encoding.UTF8.GetBytes(Obtener());

        public static HuellaComponentes ObtenerComponentes() => CacheComponentes.Value;

        /// <summary>
        /// Comprobación difusa: devuelve true si al menos 'umbral' componentes coinciden.
        /// Permite que actualizaciones de BIOS o reemplazo de disco no bloqueen una cuenta legítima.
        /// </summary>
        public static bool CoincideFuzzy(IReadOnlyList<string>? componentesRegistrados, IReadOnlyList<string>? componentesActuales, int umbral = 3)
        {
            if (componentesRegistrados == null || componentesActuales == null) return false;
            int coincidencias = 0;
            int limite = Math.Min(componentesRegistrados.Count, componentesActuales.Count);

            for (int i = 0; i < limite; i++)
            {
                if (!string.IsNullOrWhiteSpace(componentesRegistrados[i]) &&
                    string.Equals(componentesRegistrados[i], componentesActuales[i], StringComparison.OrdinalIgnoreCase))
                {
                    coincidencias++;
                }
            }

            return coincidencias >= umbral;
        }

        private static string HashearComponente(string valorCrudo)
        {
            if (string.IsNullOrWhiteSpace(valorCrudo)) return "EMPTY_COMPONENT";
            byte[] input = Encoding.UTF8.GetBytes(valorCrudo.Trim().ToUpperInvariant());
            using var hmac = new HMACSHA256(SaltRgpd);
            return Convert.ToHexString(hmac.ComputeHash(input)).ToLowerInvariant();
        }

        private static byte[]? ObtenerTablaSmbiosNativa()
        {
            try
            {
                uint size = GetSystemFirmwareTable(FIRMWARE_TABLE_RSMB, 0, IntPtr.Zero, 0);
                if (size == 0) return null;

                IntPtr buffer = Marshal.AllocHGlobal((int)size);
                try
                {
                    uint read = GetSystemFirmwareTable(FIRMWARE_TABLE_RSMB, 0, buffer, size);
                    if (read == size)
                    {
                        byte[] rawBytes = new byte[size];
                        Marshal.Copy(buffer, rawBytes, 0, (int)size);
                        return rawBytes;
                    }
                }
                finally
                {
                    Marshal.FreeHGlobal(buffer);
                }
            }
            catch { }
            return null;
        }

        private static HuellaComponentes ExtraerComponentesSeguros()
        {
            string baseboard = "";
            string cpu = "";
            string bios = "";
            string disk = "";
            string machineGuid = "";

            // Intento 1: Consulta nativa SMBIOS directa (ultra-rápida, sin winmgmt)
            byte[]? smbiosBytes = ObtenerTablaSmbiosNativa();
            if (smbiosBytes != null && smbiosBytes.Length > 0)
            {
                using var sha = SHA256.Create();
                byte[] smbiosHash = sha.ComputeHash(smbiosBytes);
                baseboard = "SMBIOS_RAW_" + Convert.ToHexString(smbiosHash);
                bios = "BIOS_RAW_" + Convert.ToHexString(smbiosHash);
            }

            // Fallback a WMI si SMBIOS nativo no estuvo disponible
            if (string.IsNullOrEmpty(baseboard))
            {
                try
                {
                    using var sBase = new ManagementObjectSearcher("SELECT SerialNumber, Product FROM Win32_BaseBoard");
                    foreach (ManagementObject obj in sBase.Get())
                    {
                        baseboard = $"{obj["SerialNumber"]}|{obj["Product"]}";
                        break;
                    }
                }
                catch { }
            }

            try
            {
                // CPU
                using var sCpu = new ManagementObjectSearcher("SELECT ProcessorId FROM Win32_Processor");
                foreach (ManagementObject obj in sCpu.Get())
                {
                    cpu = $"{obj["ProcessorId"]}";
                    break;
                }
            }
            catch { }

            if (string.IsNullOrEmpty(bios))
            {
                try
                {
                    using var sBios = new ManagementObjectSearcher("SELECT SerialNumber, Version FROM Win32_BIOS");
                    foreach (ManagementObject obj in sBios.Get())
                    {
                        bios = $"{obj["SerialNumber"]}|{obj["Version"]}";
                        break;
                    }
                }
                catch { }
            }

            try
            {
                // Disco
                using var sDisk = new ManagementObjectSearcher("SELECT SerialNumber FROM Win32_DiskDrive");
                foreach (ManagementObject obj in sDisk.Get())
                {
                    disk = $"{obj["SerialNumber"]}";
                    break;
                }
            }
            catch { }

            try
            {
                // MachineGuid nativo de Windows (Registry) sin sobrecarga WMI
                using var key = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Cryptography");
                machineGuid = key?.GetValue("MachineGuid")?.ToString() ?? "";
            }
            catch { }

            if (string.IsNullOrWhiteSpace(machineGuid))
                machineGuid = Environment.MachineName;

            return new HuellaComponentes
            {
                BaseboardHash = HashearComponente(baseboard),
                CpuHash = HashearComponente(cpu),
                BiosHash = HashearComponente(bios),
                DiskHash = HashearComponente(disk),
                MachineGuidHash = HashearComponente(machineGuid)
            };
        }

        private static string DerivarHuellaHex(HuellaComponentes comp)
        {
            string ikmRaw = string.Join("::", comp.ObtenerLista());
            byte[] ikm = Encoding.UTF8.GetBytes(ikmRaw);

            byte[] derived = HKDF.DeriveKey(
                HashAlgorithmName.SHA256,
                ikm,
                32,
                SaltApp,
                Encoding.UTF8.GetBytes("machine-unified-binding-v3"));

            return Convert.ToHexString(derived).ToLowerInvariant();
        }
    }
}
