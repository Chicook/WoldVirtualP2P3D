using System;
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

        private string GetProcessorId()
        {
            try
            {
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("Select ProcessorId From Win32_Processor"))
                {
                    foreach (ManagementObject mo in searcher.Get())
                    {
                        return mo["ProcessorId"]?.ToString() ?? "UNKNOWN_CPU";
                    }
                }
            }
            catch { return "ERROR_CPU"; }
            return "NOT_FOUND_CPU";
        }

        private string GetMotherboardId()
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

        private string GetOsId()
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

        private string GenerateHash(string input)
        {
            using (SHA256 sha256Hash = SHA256.Create())
            {
                byte[] bytes = sha256Hash.ComputeHash(Encoding.UTF8.GetBytes(input));
                StringBuilder builder = new StringBuilder();
                for (int i = 0; i < bytes.Length; i++)
                {
                    builder.Append(bytes[i].ToString("x2"));
                }
                return builder.ToString();
            }
        }
    }
}
