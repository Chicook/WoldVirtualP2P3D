using System;
using System.IO;
using System.Diagnostics;
using System.Linq;
using System.Text.Json;
using WoldVirtual.EstadoGlobal.Helpers;

namespace WoldVirtual.EstadoGlobal;

/// <summary>
/// Monitor de recursos y cuotas para el nodo del metaverso.
/// </summary>
public sealed class QuotaManager
{
    private readonly string _rootDir;
    private readonly Process _currentProcess;

    public QuotaManager(string? rootDir = null)
    {
        _rootDir = rootDir ?? GlobalConfig.RootDir;
        _currentProcess = Process.GetCurrentProcess();
    }

    public record QuotaStatus(
        long Storage3DUsed,
        long ExeSize,
        long AIAssigned,
        long AvatarsAssigned,
        long RAMUsed,
        long VRAMUsed,
        long NetworkBufferUsed,
        long SystemReserved
    );

    public QuotaStatus GetCurrentStatus()
    {
        var usage = ReadRuntimeResourceUsage();
        long luciaRam = GetLuciaRamUsage();

        var luciaDisk = GetDirSize(Path.Combine(_rootDir, "lucIA", "data"));
        var woldSize = GetDirSize(Path.Combine(_rootDir, "woldvirtual"));
        var binSize = GetDirSize(Path.Combine(_rootDir, "Visor3D_C#", "bin"));

        return new QuotaStatus(
            Storage3DUsed: woldSize,
            ExeSize: binSize,
            AIAssigned: (luciaRam > 0 ? luciaRam : 128 * 1024 * 1024) + luciaDisk,
            AvatarsAssigned: 48 * 1024 * 1024,
            RAMUsed: usage.Ram > 0 ? usage.Ram : _currentProcess.WorkingSet64,
            VRAMUsed: usage.Vram,
            NetworkBufferUsed: 64 * 1024 * 1024,
            SystemReserved: 40 * 1024 * 1024
        );
    }

    private (long Vram, long Ram) ReadRuntimeResourceUsage()
    {
        var statusPath = Path.Combine(_rootDir, "Estado_Global", "vram_status.json");
        if (!File.Exists(statusPath))
        {
            return (0, 0);
        }

        try
        {
            using var fs = new FileStream(statusPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            using var doc = JsonDocument.Parse(fs);

            long vram = doc.RootElement.TryGetProperty("vram", out var v) ? v.GetInt64() : 0;
            long ram = doc.RootElement.TryGetProperty("ram", out var r) ? r.GetInt64() : 0;
            return (vram, ram);
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[QuotaManager] Error leyendo vram_status.json: {ex.Message}");
            return (0, 0);
        }
    }

    private static long GetLuciaRamUsage()
    {
        try
        {
            foreach (var process in Process.GetProcessesByName("python"))
            {
                using (process)
                {
                    try
                    {
                        if (process.MainModule?.FileName.Contains("lucIA", StringComparison.OrdinalIgnoreCase) == true)
                        {
                            return process.WorkingSet64;
                        }
                    }
                    catch (Exception ex)
                    {
                        Debug.WriteLine($"[QuotaManager] Sin acceso a proceso python: {ex.Message}");
                    }
                }
            }
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[QuotaManager] Error buscando proceso lucIA: {ex.Message}");
        }

        return 0;
    }

    private static long GetDirSize(string path)
    {
        if (!Directory.Exists(path)) return 0;
        try
        {
            return Directory.GetFiles(path, "*", SearchOption.AllDirectories)
                .Sum(f => new FileInfo(f).Length);
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[QuotaManager] Error calculando tamaño de '{path}': {ex.Message}");
            return 0;
        }
    }

    public string GetFormattedSummary(QuotaStatus s)
    {
        var total = (s.Storage3DUsed + s.ExeSize + s.AIAssigned + s.AvatarsAssigned +
                     s.RAMUsed + s.VRAMUsed + s.NetworkBufferUsed + s.SystemReserved) / (1024.0 * 1024.0);
        return $"WoldVirtual Node: {total:F1} / 1024 MB Used";
    }
}
