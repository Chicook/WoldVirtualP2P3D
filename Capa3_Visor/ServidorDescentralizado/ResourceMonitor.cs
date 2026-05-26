using System;
using System.Diagnostics;
using System.IO;
using System.Management;
using System.Net.NetworkInformation;
using System.Threading;
using System.Threading.Tasks;

namespace VisorSingularity.ServidorDescentralizado
{
    /// <summary>
    /// Monitor de recursos del sistema para reservar CPU, RAM, disco, VRAM y ancho de banda
    /// </summary>
    public class ResourceMonitor : IDisposable
    {
        private readonly PerformanceCounter? _cpuCounter;
        private readonly PerformanceCounter? _ramCounter;
        private readonly PerformanceCounter? _diskCounter;
        private readonly PerformanceCounter? _networkCounter;
        private readonly ManagementObjectSearcher? _gpuSearcher;
        
        private CancellationTokenSource? _monitoringCts;
        private Task? _monitoringTask;
        private bool _isDisposed;
        
        // Límites de recursos (en porcentaje o bytes)
        public double CpuLimitPercent { get; set; } = 10.0; // 10% de CPU
        public long RamLimitBytes { get; set; } = 256 * 1024 * 1024; // 256 MB
        public long DiskLimitBytes { get; set; } = 500 * 1024 * 1024; // 500 MB
        public long VramLimitBytes { get; set; } = 128 * 1024 * 1024; // 128 MB
        public long BandwidthLimitBps { get; set; } = 10 * 1024 * 1024; // 10 Mbps
        
        // Recursos actualmente utilizados
        public double CurrentCpuPercent { get; private set; }
        public long CurrentRamBytes { get; private set; }
        public long CurrentDiskBytes { get; private set; }
        public long CurrentVramBytes { get; private set; }
        public long CurrentBandwidthBps { get; private set; }
        
        // Eventos
        public event Action<ResourceMetrics>? OnMetricsUpdated;
        public event Action<string, double>? OnResourceLimitExceeded;
        
        public ResourceMonitor()
        {
            _monitoringCts = new CancellationTokenSource(); // Inicializar aquí para evitar null
            try
            {
                _cpuCounter = TryInitializePerformanceCounter("Processor", "% Processor Time", "_Total");
                _ramCounter = TryInitializePerformanceCounter("Memory", "Available MBytes");
                _diskCounter = TryInitializePerformanceCounter("PhysicalDisk", "% Disk Time", "_Total");
                
                string netInterface = GetPrimaryNetworkInterface();
                if (!string.IsNullOrEmpty(netInterface))
                {
                    _networkCounter = TryInitializePerformanceCounter("Network Interface", "Bytes Total/sec", netInterface);
                }
                
                try { _gpuSearcher = new ManagementObjectSearcher("SELECT * FROM Win32_VideoController"); } catch { }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[ResourceMonitor] Error inicializando contadores: {ex.Message}");
            }
        }
        
        private PerformanceCounter? TryInitializePerformanceCounter(string categoryName, string counterName, string instanceName = "")
        {
            try
            {
                // Intentar con nombres en inglés
                if (string.IsNullOrEmpty(instanceName))
                {
                    return new PerformanceCounter(categoryName, counterName);
                }
                else
                {
                    return new PerformanceCounter(categoryName, counterName, instanceName);
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[ResourceMonitor] Falló la inicialización del contador '{counterName}' con nombres en inglés: {ex.Message}");
                // Intentar encontrar nombres localizados
                try
                {
                    var localizedCategory = PerformanceCounterCategory.GetCategories()
                                            .FirstOrDefault(c => c.CategoryName.Equals(categoryName, StringComparison.OrdinalIgnoreCase) ||
                                                                 c.CategoryName.Equals(categoryName, StringComparison.CurrentCultureIgnoreCase));
                    
                    if (localizedCategory != null)
                    {
                        // No hay una forma directa de obtener el nombre localizado de un contador específico sin iterar
                        // Por simplicidad, si la categoría se encuentra, asumimos que el contador también podría existir
                        // y lo intentamos de nuevo con el nombre original, esperando que el sistema lo resuelva.
                        // Una solución más robusta implicaría iterar sobre los contadores de la categoría.
                        
                        if (string.IsNullOrEmpty(instanceName))
                        {
                            return new PerformanceCounter(localizedCategory.CategoryName, counterName);
                        }
                        else
                        {
                            return new PerformanceCounter(localizedCategory.CategoryName, counterName, instanceName);
                        }
                    }
                }
                catch (Exception innerEx)
                {
                    Debug.WriteLine($"[ResourceMonitor] Falló la búsqueda de nombres localizados para '{counterName}': {innerEx.Message}");
                }
            }
            return null; // No se pudo inicializar el contador
        }
        
        private string GetPrimaryNetworkInterface()
        {
            foreach (NetworkInterface ni in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (ni.OperationalStatus == OperationalStatus.Up && 
                    ni.NetworkInterfaceType != NetworkInterfaceType.Loopback)
                {
                    return ni.Description;
                }
            }
            return "Intel(R) Ethernet Connection";
        }
        
        public void StartMonitoring(int updateIntervalMs = 1000)
        {
            if (_monitoringTask != null && !_monitoringTask.IsCompleted)
                return;
                
            _monitoringCts = new CancellationTokenSource();
            _monitoringTask = Task.Run(async () =>
            {
                while (!_monitoringCts.Token.IsCancellationRequested)
                {
                    try
                    {
                        UpdateMetrics();
                        await Task.Delay(updateIntervalMs, _monitoringCts.Token);
                    }
                    catch (TaskCanceledException)
                    {
                        break;
                    }
                    catch (Exception ex)
                    {
                        Debug.WriteLine($"[ResourceMonitor] Error en monitoreo: {ex.Message}");
                    }
                }
            }, _monitoringCts.Token);
        }
        
        public void StopMonitoring()
        {
            _monitoringCts?.Cancel();
            _monitoringTask?.Wait(5000);
        }
        
        private void UpdateMetrics()
        {
            try
            {
                // CPU
                CurrentCpuPercent = _cpuCounter != null ? _cpuCounter.NextValue() : 5.0; // Valor simulado si falla
                
                // RAM (convertir MB disponibles a bytes usados)
                if (_ramCounter != null)
                {
                    float availableMB = _ramCounter.NextValue();
                    long totalRam = GetTotalPhysicalMemory();
                    CurrentRamBytes = totalRam - (long)(availableMB * 1024 * 1024);
                }
                else
                {
                    CurrentRamBytes = 128 * 1024 * 1024; // 128MB simulado
                }
                
                // Disco
                if (_diskCounter != null)
                {
                    double diskTimePercent = _diskCounter.NextValue();
                }
                CurrentDiskBytes = GetDiskUsageBytes();
                
                // VRAM
                CurrentVramBytes = GetGpuMemoryUsage();
                
                // Ancho de banda
                CurrentBandwidthBps = _networkCounter != null ? (long)(_networkCounter.NextValue() * 8) : 5 * 1024 * 1024; // 5 Mbps simulado
                
                // Verificar límites
                CheckResourceLimits();
                
                // Notificar actualización
                var metrics = new ResourceMetrics
                {
                    Timestamp = DateTime.UtcNow,
                    CpuPercent = CurrentCpuPercent,
                    RamBytes = CurrentRamBytes,
                    DiskBytes = CurrentDiskBytes,
                    VramBytes = CurrentVramBytes,
                    BandwidthBps = CurrentBandwidthBps,
                    CpuLimitPercent = CpuLimitPercent,
                    RamLimitBytes = RamLimitBytes,
                    DiskLimitBytes = DiskLimitBytes,
                    VramLimitBytes = VramLimitBytes,
                    BandwidthLimitBps = BandwidthLimitBps
                };
                
                OnMetricsUpdated?.Invoke(metrics);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[ResourceMonitor] Error actualizando métricas: {ex.Message}");
            }
        }
        
        private void CheckResourceLimits()
        {
            if (CurrentCpuPercent > CpuLimitPercent)
                OnResourceLimitExceeded?.Invoke("CPU", CurrentCpuPercent);
                
            if (CurrentRamBytes > RamLimitBytes)
                OnResourceLimitExceeded?.Invoke("RAM", CurrentRamBytes);
                
            if (CurrentDiskBytes > DiskLimitBytes)
                OnResourceLimitExceeded?.Invoke("DISK", CurrentDiskBytes);
                
            if (CurrentVramBytes > VramLimitBytes)
                OnResourceLimitExceeded?.Invoke("VRAM", CurrentVramBytes);
                
            if (CurrentBandwidthBps > BandwidthLimitBps)
                OnResourceLimitExceeded?.Invoke("BANDWIDTH", CurrentBandwidthBps);
        }
        
        private long GetTotalPhysicalMemory()
        {
            try
            {
                using var searcher = new ManagementObjectSearcher("SELECT TotalPhysicalMemory FROM Win32_ComputerSystem");
                foreach (ManagementObject obj in searcher.Get())
                {
                    if (obj["TotalPhysicalMemory"] != null)
                    {
                        return Convert.ToInt64(obj["TotalPhysicalMemory"]);
                    }
                }
            }
            catch { }
            
            return 8L * 1024 * 1024 * 1024; // 8 GB por defecto
        }
        
        private long GetDiskUsageBytes()
        {
            try
            {
                string systemDrive = Environment.GetFolderPath(Environment.SpecialFolder.System).Substring(0, 1);
                var drive = new DriveInfo(systemDrive);
                return drive.TotalSize - drive.AvailableFreeSpace;
            }
            catch { }
            
            return 0;
        }
        
        private long GetGpuMemoryUsage()
        {
            try
            {
                if (_gpuSearcher == null) return 0; // Añadir verificación de nulidad
                
                foreach (ManagementObject obj in _gpuSearcher.Get())
                {
                    if (obj["AdapterRAM"] != null)
                    {
                        long totalVram = Convert.ToInt64(obj["AdapterRAM"]);
                        // Estimación simple: 30% de uso
                        return (long)(totalVram * 0.3);
                    }
                }
            }
            catch { }
            
            return 0;
        }
        
        public ResourceMetrics GetCurrentMetrics()
        {
            return new ResourceMetrics
            {
                Timestamp = DateTime.UtcNow,
                CpuPercent = CurrentCpuPercent,
                RamBytes = CurrentRamBytes,
                DiskBytes = CurrentDiskBytes,
                VramBytes = CurrentVramBytes,
                BandwidthBps = CurrentBandwidthBps,
                CpuLimitPercent = CpuLimitPercent,
                RamLimitBytes = RamLimitBytes,
                DiskLimitBytes = DiskLimitBytes,
                VramLimitBytes = VramLimitBytes,
                BandwidthLimitBps = BandwidthLimitBps
            };
        }
        
        public void SetResourceLimits(double cpuPercent, long ramMB, long diskMB, long vramMB, long bandwidthMbps)
        {
            CpuLimitPercent = cpuPercent;
            RamLimitBytes = ramMB * 1024 * 1024;
            DiskLimitBytes = diskMB * 1024 * 1024;
            VramLimitBytes = vramMB * 1024 * 1024;
            BandwidthLimitBps = bandwidthMbps * 1024 * 1024;
        }
        
        public void Dispose()
        {
            if (_isDisposed) return;
            
            _isDisposed = true;
            StopMonitoring();
            
            _cpuCounter?.Dispose();
            _ramCounter?.Dispose();
            _diskCounter?.Dispose();
            _networkCounter?.Dispose();
            _gpuSearcher?.Dispose();
            _monitoringCts?.Dispose();
            
            GC.SuppressFinalize(this);
        }
    }
    
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