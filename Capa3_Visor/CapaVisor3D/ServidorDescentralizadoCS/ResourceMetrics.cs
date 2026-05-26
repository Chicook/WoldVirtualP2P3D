using System;
using System.Diagnostics;
using System.IO;
using System.Linq; // Añadir para FirstOrDefault
using System.Management;
using System.Net.NetworkInformation;
using System.Threading;
using System.Threading.Tasks;

namespace VisorSingularity.ServidorDescentralizado
{
    /// <summary>
    /// Métricas de recursos del sistema
    /// </summary>
    public class ResourceMetrics
    {
        public DateTime Timestamp { get; set; }
        
        // Uso actual
        public double CpuPercent { get; set; }
        public long RamBytes { get; set; }
        public long DiskBytes { get; set; }
        public long VramBytes { get; set; }
        public long BandwidthBps { get; set; }
        
        // Límites configurados
        public double CpuLimitPercent { get; set; }
        public long RamLimitBytes { get; set; }
        public long DiskLimitBytes { get; set; }
        public long VramLimitBytes { get; set; }
        public long BandwidthLimitBps { get; set; }
        
        // Propiedades calculadas
        public double CpuUsageRatio => CpuPercent / 100.0;
        public double RamUsageRatio => (double)RamBytes / RamLimitBytes;
        public double DiskUsageRatio => (double)DiskBytes / DiskLimitBytes;
        public double VramUsageRatio => (double)VramBytes / VramLimitBytes;
        public double BandwidthUsageRatio => (double)BandwidthBps / BandwidthLimitBps;
        
        public bool IsCpuLimitExceeded => CpuPercent > CpuLimitPercent;
        public bool IsRamLimitExceeded => RamBytes > RamLimitBytes;
        public bool IsDiskLimitExceeded => DiskBytes > DiskLimitBytes;
        public bool IsVramLimitExceeded => VramBytes > VramLimitBytes;
        public bool IsBandwidthLimitExceeded => BandwidthBps > BandwidthLimitBps;
        
        public long TotalUsedBytes => RamBytes + DiskBytes + VramBytes;
        
        public override string ToString()
        {
            return $"CPU: {CpuPercent:F1}%/{CpuLimitPercent}% | " +
                   $"RAM: {FormatBytes(RamBytes)}/{FormatBytes(RamLimitBytes)} | " +
                   $"Disco: {FormatBytes(DiskBytes)}/{FormatBytes(DiskLimitBytes)} | " +
                   $"VRAM: {FormatBytes(VramBytes)}/{FormatBytes(VramLimitBytes)} | " +
                   $"Red: {FormatBits(BandwidthBps)}/{FormatBits(BandwidthLimitBps)}";
        }
        
        private static string FormatBytes(long bytes)
        {
            string[] suffixes = { "B", "KB", "MB", "GB", "TB" };
            int suffixIndex = 0;
            double size = bytes;
            
            while (size >= 1024 && suffixIndex < suffixes.Length - 1)
            {
                size /= 1024;
                suffixIndex++;
            }
            
            return $"{size:F1} {suffixes[suffixIndex]}";
        }
        
        private static string FormatBits(long bits)
        {
            string[] suffixes = { "bps", "Kbps", "Mbps", "Gbps" };
            int suffixIndex = 0;
            double size = bits;
            
            while (size >= 1000 && suffixIndex < suffixes.Length - 1)
            {
                size /= 1000;
                suffixIndex++;
            }
            
            return $"{size:F1} {suffixes[suffixIndex]}";
        }
    }
}