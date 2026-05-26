using Microsoft.VisualBasic.Devices;
using ServidorVirtualCS.Models;
using System;
using System.IO;
using System.Linq;
using System.Management;
using System.Net.NetworkInformation;

namespace ServidorVirtualCS.Services;

public sealed class HardwareProfileService
{
    public NodeResourceSnapshot Capture()
    {
        ComputerInfo computerInfo = new();
        (string cpuName, double cpuLoadPercent) = ReadCpuData();
        (string gpuName, ulong vramMb) = ReadGpuData();
        (ulong totalDiskMb, ulong freeDiskMb) = ReadDiskData();
        double bandwidthMbPerSecond = ReadNetworkBandwidth();

        return new NodeResourceSnapshot
        {
            CapturedAt = DateTimeOffset.UtcNow,
            MachineName = Environment.MachineName,
            CpuName = cpuName,
            LogicalCores = Environment.ProcessorCount,
            CpuLoadPercent = cpuLoadPercent,
            TotalRamMb = ToMb(computerInfo.TotalPhysicalMemory),
            AvailableRamMb = ToMb(computerInfo.AvailablePhysicalMemory),
            GpuName = gpuName,
            DedicatedVramMb = vramMb,
            TotalDiskMb = totalDiskMb,
            AvailableDiskMb = freeDiskMb,
            NetworkBandwidthMbPerSecond = bandwidthMbPerSecond
        };
    }

    private static (string CpuName, double CpuLoadPercent) ReadCpuData()
    {
        try
        {
            using ManagementObjectSearcher searcher = new("SELECT Name, LoadPercentage FROM Win32_Processor");
            ManagementObject? processor = searcher.Get().Cast<ManagementObject>().FirstOrDefault();
            string name = processor?["Name"]?.ToString() ?? "CPU desconocida";
            double load = Convert.ToDouble(processor?["LoadPercentage"] ?? 0d);
            return (name, load);
        }
        catch
        {
            return ("CPU desconocida", 0d);
        }
    }

    private static (string GpuName, ulong DedicatedVramMb) ReadGpuData()
    {
        try
        {
            using ManagementObjectSearcher searcher = new("SELECT Name, AdapterRAM FROM Win32_VideoController");
            ManagementObject? gpu = searcher.Get().Cast<ManagementObject>().FirstOrDefault();
            string name = gpu?["Name"]?.ToString() ?? "GPU desconocida";
            ulong adapterRam = 0;

            if (gpu?["AdapterRAM"] is not null)
            {
                adapterRam = Convert.ToUInt64(gpu["AdapterRAM"]);
            }

            return (name, ToMb(adapterRam));
        }
        catch
        {
            return ("GPU desconocida", 0);
        }
    }

    private static (ulong TotalDiskMb, ulong FreeDiskMb) ReadDiskData()
    {
        try
        {
            string systemRoot = Path.GetPathRoot(Environment.SystemDirectory) ?? "C:\\";
            DriveInfo? drive = DriveInfo.GetDrives()
                .FirstOrDefault(d => d.IsReady && string.Equals(d.RootDirectory.FullName, systemRoot, StringComparison.OrdinalIgnoreCase));

            if (drive is null)
            {
                drive = DriveInfo.GetDrives().FirstOrDefault(d => d.IsReady);
            }

            if (drive is null)
            {
                return (0, 0);
            }

            return (ToMb((ulong)drive.TotalSize), ToMb((ulong)drive.AvailableFreeSpace));
        }
        catch
        {
            return (0, 0);
        }
    }

    private static double ReadNetworkBandwidth()
    {
        try
        {
            NetworkInterface? nic = NetworkInterface.GetAllNetworkInterfaces()
                .Where(nic => nic.OperationalStatus == OperationalStatus.Up)
                .Where(nic => nic.NetworkInterfaceType != NetworkInterfaceType.Loopback)
                .OrderByDescending(nic => nic.Speed)
                .FirstOrDefault();

            if (nic is null || nic.Speed <= 0)
            {
                return 0;
            }

            double bytesPerSecond = nic.Speed / 8d;
            return Math.Round(bytesPerSecond / 1024d / 1024d, 2);
        }
        catch
        {
            return 0;
        }
    }

    private static ulong ToMb(ulong valueInBytes)
    {
        return valueInBytes / 1024UL / 1024UL;
    }
}
