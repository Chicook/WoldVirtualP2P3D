using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using VisorSingularity;

namespace VisorSingularity.ServidorDescentralizado
{
    /// <summary>
    /// Sistema para compartir recursos de servidor descentralizado vía IPFS
    /// Integrado con el sistema IPFS existente del proyecto
    /// </summary>
    public class IpfsResourceSharing
    {
        private readonly IpfsPublisher _ipfsPublisher;
        
        public IpfsResourceSharing(IpfsPublisher ipfsPublisher)
        {
            _ipfsPublisher = ipfsPublisher ?? throw new ArgumentNullException(nameof(ipfsPublisher));
        }
        
        /// <summary>
        /// Comparte información de recursos del servidor descentralizado vía IPFS
        /// </summary>
        public async Task<string> ShareResourcesViaIpfs(ResourceMetrics metrics, 
                                                       MiningRigConfig? miningRig = null)
        {
            try
            {
                // Crear objeto de datos de recursos
                var resourceData = new DecentralizedResourceData
                {
                    Timestamp = metrics.Timestamp,
                    NodeId = GenerateNodeId(),
                    Resources = new ResourceInfo
                    {
                        Cpu = new CpuInfo
                        {
                            CurrentPercent = metrics.CpuPercent,
                            LimitPercent = metrics.CpuLimitPercent,
                            IsLimitExceeded = metrics.IsCpuLimitExceeded
                        },
                        Memory = new MemoryInfo
                        {
                            CurrentBytes = metrics.RamBytes,
                            LimitBytes = metrics.RamLimitBytes,
                            IsLimitExceeded = metrics.IsRamLimitExceeded
                        },
                        Disk = new DiskInfo
                        {
                            CurrentBytes = metrics.DiskBytes,
                            LimitBytes = metrics.DiskLimitBytes,
                            IsLimitExceeded = metrics.IsDiskLimitExceeded
                        },
                        Vram = new VramInfo
                        {
                            CurrentBytes = metrics.VramBytes,
                            LimitBytes = metrics.VramLimitBytes,
                            IsLimitExceeded = metrics.IsVramLimitExceeded
                        },
                        Bandwidth = new BandwidthInfo
                        {
                            CurrentBps = metrics.BandwidthBps,
                            LimitBps = metrics.BandwidthLimitBps,
                            IsLimitExceeded = metrics.IsBandwidthLimitExceeded
                        }
                    },
                    TotalUsageBytes = metrics.TotalUsageBytes,
                    IsSharingEnabled = metrics.IsSharingEnabled,
                    MiningRig = miningRig
                };
                
                // Serializar a JSON
                string jsonData = JsonSerializer.Serialize(resourceData, new JsonSerializerOptions
                {
                    WriteIndented = true,
                    PropertyNamingPolicy = JsonNamingPolicy.CamelCase
                });
                
                // Guardar en archivo temporal
                string tempFile = Path.GetTempFileName();
                await File.WriteAllTextAsync(tempFile, jsonData);
                
                try
                {
                    // Publicar en IPFS usando el sistema existente
                    await _ipfsPublisher.PublishDirectoryAsync(Path.GetDirectoryName(tempFile)!, 
                        includeSubdirectories: false);
                    
                    // Obtener CID
                    string cid = _ipfsPublisher.LastCid;
                    
                    if (string.IsNullOrEmpty(cid))
                    {
                        throw new InvalidOperationException("No se obtuvo CID después de publicar en IPFS");
                    }
                    
                    // Crear URL IPFS
                    string ipfsUrl = $"ipfs://{cid}";
                    string gatewayUrl = _ipfsPublisher.LocalGatewayUrl ?? 
                                       $"http://127.0.0.1:8080/ipfs/{cid}";
                    
                    Debug.WriteLine($"[IpfsSharing] Recursos compartidos vía IPFS:");
                    Debug.WriteLine($"[IpfsSharing] CID: {cid}");
                    Debug.WriteLine($"[IpfsSharing] URL: {gatewayUrl}");
                    Debug.WriteLine($"[IpfsSharing] Datos: {jsonData.Substring(0, Math.Min(200, jsonData.Length))}...");
                    
                    // Retornar CID y URL
                    return $"{cid}|{gatewayUrl}";
                }
                finally
                {
                    // Limpiar archivo temporal
                    try { File.Delete(tempFile); } catch { }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[IpfsSharing] Error compartiendo recursos: {ex.Message}");
                throw;
            }
        }
        
        /// <summary>
        /// Recupera datos de recursos compartidos desde IPFS
        /// </summary>
        public async Task<DecentralizedResourceData?> RetrieveResourcesFromIpfs(string cid)
        {
            try
            {
                // Construir URL del gateway
                string gatewayUrl = $"http://127.0.0.1:8080/ipfs/{cid}/resources.json";
                
                // Descargar datos
                using var httpClient = new HttpClient();
                string jsonData = await httpClient.GetStringAsync(gatewayUrl);
                
                // Deserializar
                var resourceData = JsonSerializer.Deserialize<DecentralizedResourceData>(jsonData, 
                    new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase });
                
                Debug.WriteLine($"[IpfsSharing] Recursos recuperados desde IPFS:");
                Debug.WriteLine($"[IpfsSharing] CID: {cid}");
                Debug.WriteLine($"[IpfsSharing] Datos: {jsonData.Substring(0, Math.Min(200, jsonData.Length))}...");
                
                return resourceData;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[IpfsSharing] Error recuperando recursos: {ex.Message}");
                return null;
            }
        }
        
        /// <summary>
        /// Genera un ID único para el nodo
        /// </summary>
        private string GenerateNodeId()
        {
            return $"DSN-{Guid.NewGuid().ToString("N").Substring(0, 8).ToUpper()}";
        }
    }
    
    /// <summary>
    /// Datos de recursos del servidor descentralizado
    /// </summary>
    public class DecentralizedResourceData
    {
        public DateTime Timestamp { get; set; }
        public string NodeId { get; set; } = string.Empty;
        public ResourceInfo Resources { get; set; } = new();
        public long TotalUsageBytes { get; set; }
        public bool IsSharingEnabled { get; set; }
        public MiningRigConfig? MiningRig { get; set; }
    }
    
    /// <summary>
    /// Información de recursos
    /// </summary>
    public class ResourceInfo
    {
        public CpuInfo Cpu { get; set; } = new();
        public MemoryInfo Memory { get; set; } = new();
        public DiskInfo Disk { get; set; } = new();
        public VramInfo Vram { get; set; } = new();
        public BandwidthInfo Bandwidth { get; set; } = new();
    }
    
    /// <summary>
    /// Información de CPU
    /// </summary>
    public class CpuInfo
    {
        public double CurrentPercent { get; set; }
        public double LimitPercent { get; set; }
        public bool IsLimitExceeded { get; set; }
    }
    
    /// <summary>
    /// Información de memoria RAM
    /// </summary>
    public class MemoryInfo
    {
        public long CurrentBytes { get; set; }
        public long LimitBytes { get; set; }
        public bool IsLimitExceeded { get; set; }
    }
    
    /// <summary>
    /// Información de disco
    /// </summary>
    public class DiskInfo
    {
        public long CurrentBytes { get; set; }
        public long LimitBytes { get; set; }
        public bool IsLimitExceeded { get; set; }
    }
    
    /// <summary>
    /// Información de VRAM
    /// </summary>
    public class VramInfo
    {
        public long CurrentBytes { get; set; }
        public long LimitBytes { get; set; }
        public bool IsLimitExceeded { get; set; }
    }
    
    /// <summary>
    /// Información de ancho de banda
    /// </summary>
    public class BandwidthInfo
    {
        public long CurrentBps { get; set; }
        public long LimitBps { get; set; }
        public bool IsLimitExceeded { get; set; }
    }
}