using System;

namespace ServidorVirtualCS.Models;

public sealed class NodeResourceSnapshot
{
    public DateTimeOffset CapturedAt { get; init; } = DateTimeOffset.UtcNow;

    public string MachineName { get; init; } = Environment.MachineName;

    public string CpuName { get; init; } = "CPU desconocida";

    public int LogicalCores { get; init; }

    public double CpuLoadPercent { get; init; }

    public ulong AvailableRamMb { get; init; }

    public ulong TotalRamMb { get; init; }

    public string GpuName { get; init; } = "GPU desconocida";

    public ulong DedicatedVramMb { get; init; }

    public ulong AvailableDiskMb { get; init; }

    public ulong TotalDiskMb { get; init; }

    public double NetworkBandwidthMbPerSecond { get; init; }

    public string IpfsApiUrl { get; init; } = "http://127.0.0.1:5001";
}
