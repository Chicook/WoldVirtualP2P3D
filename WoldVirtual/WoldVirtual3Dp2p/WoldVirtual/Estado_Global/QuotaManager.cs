using System;
using System.IO;
using System.Diagnostics;
using System.Collections.Generic;
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
        long vram = 0, ram = 0;
        try
        {
            var statusPath = Path.Combine(_rootDir, "Estado_Global", "vram_status.json");
            if (File.Exists(statusPath))
            {
                using var fs = new FileStream(statusPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                using var doc = JsonDocument.Parse(fs);
                if (doc.RootElement.TryGetProperty("vram", out var v)) vram = v.GetInt64();
                if (doc.RootElement.TryGetProperty("ram", out var r)) ram = r.GetInt64();
            }
        }
        catch { /* Ignorar errores de lectura de JSON temporal */ }

        long luciaRam = 0;
        try
        {
            var luciaProcs = Process.GetProcessesByName("python");
            foreach (var p in luciaProcs)
            {
                try
                {
                    if (p.MainModule?.FileName.Contains("lucIA", StringComparison.OrdinalIgnoreCase) == true)
                    {
                        luciaRam = p.WorkingSet64;
                        break;
                    }
                }
                catch { /* Acceso denegado a algunos procesos */ }
            }
        }
        catch { }

        var luciaDisk = GetDirSize(Path.Combine(_rootDir, "lucIA", "data"));
        var woldSize = GetDirSize(Path.Combine(_rootDir, "woldvirtual"));
        var binSize = GetDirSize(Path.Combine(_rootDir, "Visor3D_C#", "bin"));

        return new QuotaStatus(
            Storage3DUsed: woldSize,
            ExeSize: binSize,
            AIAssigned: (luciaRam > 0 ? luciaRam : 128 * 1024 * 1024) + luciaDisk,
            AvatarsAssigned: 48 * 1024 * 1024,
            RAMUsed: ram > 0 ? ram : _currentProcess.WorkingSet64,
            VRAMUsed: vram,
            NetworkBufferUsed: 64 * 1024 * 1024,
            SystemReserved: 40 * 1024 * 1024
        );
    }

    private static long GetDirSize(string path)
    {
        if (!Directory.Exists(path)) return 0;
        try
        {
            return Directory.GetFiles(path, "*", SearchOption.AllDirectories)
                .Sum(f => new FileInfo(f).Length);
        }
        catch { return 0; }
    }

    public string GetFormattedSummary(QuotaStatus s)
    {
        var total = (s.Storage3DUsed + s.ExeSize + s.AIAssigned + s.AvatarsAssigned +
                     s.RAMUsed + s.VRAMUsed + s.NetworkBufferUsed + s.SystemReserved) / (1024.0 * 1024.0);
        return $"WoldVirtual Node: {total:F1} / 1024 MB Used";
    }
}
