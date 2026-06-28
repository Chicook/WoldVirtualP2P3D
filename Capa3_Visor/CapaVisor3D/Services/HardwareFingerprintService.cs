using System;
using System.IO;
using System.Management;
using System.Security.Cryptography;
using System.Text;

namespace VisorSingularity.Services
{
    internal static class HardwareFingerprintService
    {
        public static string GetOSName()
        {
            try
            {
                using var searcher = new ManagementObjectSearcher("SELECT Caption FROM Win32_OperatingSystem");
                foreach (var obj in searcher.Get())
                {
                    var caption = obj["Caption"]?.ToString();
                    if (!string.IsNullOrEmpty(caption))
                    {
                        return caption.Trim();
                    }
                }
            }
            catch
            {
                return $"{Environment.OSVersion} ({(Environment.Is64BitOperatingSystem ? "64-bit" : "32-bit")})";
            }

            return "Windows OS";
        }

        public static string GetCpuName()
        {
            try
            {
                using var searcher = new ManagementObjectSearcher("SELECT Name FROM Win32_Processor");
                foreach (var obj in searcher.Get())
                {
                    var name = obj["Name"]?.ToString();
                    if (!string.IsNullOrEmpty(name))
                    {
                        return name.Trim();
                    }
                }
            }
            catch
            {
                return Environment.GetEnvironmentVariable("PROCESSOR_IDENTIFIER") ?? "Desconocido";
            }

            return "Generic CPU";
        }

        public static string GetMotherboardName()
        {
            try
            {
                using var searcher = new ManagementObjectSearcher("SELECT Manufacturer, Product FROM Win32_BaseBoard");
                foreach (var obj in searcher.Get())
                {
                    string manufacturer = obj["Manufacturer"]?.ToString() ?? "";
                    string product = obj["Product"]?.ToString() ?? "";
                    string result = $"{manufacturer} {product}".Trim();
                    if (!string.IsNullOrEmpty(result))
                    {
                        return result;
                    }
                }
            }
            catch
            {
                return "Placa Base Generica (WMI no disponible)";
            }

            return "Baseboard";
        }

        public static string GenerateSignature(string os, string cpu, string motherboard)
        {
            string rawData = $"{os.ToLower().Trim()}|{cpu.ToLower().Trim()}|{motherboard.ToLower().Trim()}";
            byte[] bytes = SHA256.HashData(Encoding.UTF8.GetBytes(rawData));
            var builder = new StringBuilder(bytes.Length * 2);

            foreach (byte b in bytes)
            {
                builder.Append(b.ToString("x2"));
            }

            return builder.ToString();
        }

        public static string EncryptString(string plainText, string keyString)
        {
            if (string.IsNullOrEmpty(plainText)) return "";
            try
            {
                byte[] key = SHA256.HashData(Encoding.UTF8.GetBytes(keyString));
                byte[] iv = new byte[16];
                Array.Copy(key, iv, 16);

                using var aes = Aes.Create();
                aes.Key = key;
                aes.IV = iv;

                using var encryptor = aes.CreateEncryptor(aes.Key, aes.IV);
                using var ms = new MemoryStream();
                using (var cs = new CryptoStream(ms, encryptor, CryptoStreamMode.Write))
                using (var sw = new StreamWriter(cs, Encoding.UTF8))
                {
                    sw.Write(plainText);
                }
                return Convert.ToBase64String(ms.ToArray());
            }
            catch
            {
                return plainText;
            }
        }

        public static string DecryptString(string cipherText, string keyString)
        {
            if (string.IsNullOrEmpty(cipherText)) return "";
            try
            {
                byte[] key = SHA256.HashData(Encoding.UTF8.GetBytes(keyString));
                byte[] iv = new byte[16];
                Array.Copy(key, iv, 16);

                using var aes = Aes.Create();
                aes.Key = key;
                aes.IV = iv;

                using var decryptor = aes.CreateDecryptor(aes.Key, aes.IV);
                using var ms = new MemoryStream(Convert.FromBase64String(cipherText));
                using var cs = new CryptoStream(ms, decryptor, CryptoStreamMode.Read);
                using var sr = new StreamReader(cs, Encoding.UTF8);
                return sr.ReadToEnd();
            }
            catch
            {
                return cipherText;
            }
        }
    }
}
