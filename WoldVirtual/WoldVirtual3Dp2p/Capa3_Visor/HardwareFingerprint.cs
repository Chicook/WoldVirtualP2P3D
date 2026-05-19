using System;
using System.Globalization;
using System.Management;
using System.Security.Cryptography;
using System.Text;

namespace VisorSingularity
{
    [System.Runtime.Versioning.SupportedOSPlatform("windows")]
    public class HardwareFingerprint
    {
        public string ProcessorId { get; private set; }
        public string MotherboardId { get; private set; }
        public string OsId { get; private set; }
        public string UniqueHash { get; private set; }

        public HardwareFingerprint()
        {
            ProcessorId = GetProcessorId();
            MotherboardId = GetMotherboardId();
            OsId = GetOsId();
            UniqueHash = GenerateHash(ProcessorId + MotherboardId + OsId);
        }

        private static string GetProcessorId()
        {
            try
            {
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("Select ProcessorId From Win32_Processor"))
                {
                    foreach (ManagementObject mo in searcher.Get())
                    {
                        return mo[nameof(ProcessorId)]?.ToString() ?? "UNKNOWN_CPU";
                    }
                }
            }
            catch { return "ERROR_CPU"; }
            return "NOT_FOUND_CPU";
        }

        private static string GetMotherboardId()
        {
            try
            {
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("Select SerialNumber From Win32_BaseBoard"))
                {
                    foreach (ManagementObject mo in searcher.Get())
                    {
                        return mo["SerialNumber"]?.ToString() ?? "UNKNOWN_BOARD";
                    }
                }
            }
            catch { return "ERROR_BOARD"; }
            return "NOT_FOUND_BOARD";
        }

        private static string GetOsId()
        {
            try
            {
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("Select SerialNumber From Win32_OperatingSystem"))
                {
                    foreach (ManagementObject mo in searcher.Get())
                    {
                        return mo["SerialNumber"]?.ToString() ?? "UNKNOWN_OS";
                    }
                }
            }
            catch { return "ERROR_OS"; }
            return "NOT_FOUND_OS";
        }

        private static string GenerateHash(string input)
        {
            byte[] bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
            return Convert.ToHexString(bytes).ToLower(CultureInfo.InvariantCulture);
        }
    }
}
