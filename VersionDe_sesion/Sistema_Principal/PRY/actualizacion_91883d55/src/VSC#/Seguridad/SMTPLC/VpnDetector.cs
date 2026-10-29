using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Win32;

namespace Visor3D.Seguridad.SMTPLC
{
    /// <summary>
    /// Motor de detección profunda de VPNs, Proxies, Túneles (WireGuard, OpenVPN, Wintun)
    /// y conexiones anónimas o alojadas en centros de datos / servidores cloud.
    /// </summary>
    public static class VpnDetector
    {
        private static readonly string[] VpnKeywords = new[]
        {
            "tap-windows", "wintun", "wireguard", "nordlynx", "nordvpn",
            "protonvpn", "openvpn", "tailscale", "zerotier", "cloudflarewarp", "warp",
            "expressvpn", "surfshark", "mullvad", "cisco anyconnect", "forticlient",
            "fortinet", "globalprotect", "softether", "kaspersky vpn", "windscribe",
            "hidemyass", "private internet access", "pia", "tunnelbear", "speedify",
            "cyberghost", "vyprvpn", "purevpn", "hotspot shield", "vpn"
        };

        private static readonly string[] DatacenterHostingKeywords = new[]
        {
            "amazon", "aws", "google cloud", "google llc", "microsoft azure", "azure",
            "digitalocean", "hetzner", "ovh", "linode", "akamai", "m247", "datacamp",
            "choopa", "contabo", "vultr", "leaseweb", "alibaba", "tencent", "oracle cloud",
            "server", "hosting", "datacenter", "colo", "vps"
        };

        // Endpoints públicos redundantes ultralivianos para resolución de IP/ISP (timeout de 2.5s)
        private static readonly string[] PublicIpServices = new[]
        {
            "https://api.ipify.org?format=json",
            "https://ipinfo.io/json"
        };

        /// <summary>
        /// Análisis sincrónico rápido (interfaces, proxies locales, MTU, DNS).
        /// </summary>
        public static VpnDetectionResult AnalyzeLocal()
        {
            var result = new VpnDetectionResult();
            double score = 0.0;
            var detectedTypes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var detectedAdapters = new List<string>();
            var artifacts = new List<string>();

            // 1. Inspección de adaptadores de red (TUN/TAP, WireGuard, PPP, nombres de software VPN)
            InspectNetworkInterfaces(detectedTypes, detectedAdapters, artifacts, ref score);

            // 2. Inspección de configuración de Proxy del sistema (WinINet, Registry, WPAD)
            InspectSystemProxy(detectedTypes, artifacts, ref score);

            // 3. Inspección de anomalías de MTU (encapsulación de túneles)
            InspectMtuAnomalies(detectedTypes, artifacts, ref score);

            // 4. Inspección de servidores DNS en rangos de túnel (10.8.x, 10.2.x, etc.)
            InspectDnsServers(detectedTypes, artifacts, ref score);

            result.ConfidenceScore = Math.Min(1.0, score);
            result.IsVpnOrProxy = result.ConfidenceScore >= 0.40;
            result.DetectedVpnTypes = detectedTypes.ToList();
            result.DetectedAdapters = detectedAdapters;
            result.Artifacts = artifacts;

            if (result.IsVpnOrProxy)
            {
                result.Summary = $"Conexión VPN/Proxy activa detectada ({string.Join(", ", result.DetectedVpnTypes)}) con {result.ConfidenceScore * 100:0}% de confianza.";
            }
            else
            {
                result.Summary = "Conexión de red directa legítima. No se detectan túneles ni proxies locales.";
            }

            return result;
        }

        /// <summary>
        /// Análisis asincrónico completo: incluye verificación local + análisis de IP pública y ASN/ISP.
        /// </summary>
        public static async Task<VpnDetectionResult> AnalyzeAsync(CancellationToken cancellationToken = default)
        {
            var result = AnalyzeLocal();

            // Si ya se confirmó VPN local con alta confianza (> 85%), no es estrictamente necesario esperar la red
            if (result.ConfidenceScore >= 0.85)
            {
                return result;
            }

            try
            {
                using var cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
                cts.CancelAfter(TimeSpan.FromSeconds(2.8));

                await InspectPublicIpReputationAsync(result, cts.Token);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Salto de verificación ASN externa por timeout o red: {ex.Message}");
            }

            result.ConfidenceScore = Math.Min(1.0, result.ConfidenceScore);
            result.IsVpnOrProxy = result.ConfidenceScore >= 0.40;

            if (result.IsVpnOrProxy)
            {
                result.Summary = $"Conexión VPN/Proxy detectada ({string.Join(", ", result.DetectedVpnTypes)}) con {result.ConfidenceScore * 100:0}% de confianza.";
            }

            return result;
        }

        private static void InspectNetworkInterfaces(HashSet<string> types, List<string> adapters, List<string> artifacts, ref double score)
        {
            try
            {
                var interfaces = NetworkInterface.GetAllNetworkInterfaces();
                foreach (var nic in interfaces)
                {
                    // Solo adaptadores activos o conectados
                    if (nic.OperationalStatus != OperationalStatus.Up) continue;

                    string name = nic.Name.ToLowerInvariant();
                    string desc = nic.Description.ToLowerInvariant();
                    string combined = $"{name} {desc}";

                    // Comprobar tipo de interfaz (Tunnel o PPP)
                    if (nic.NetworkInterfaceType == NetworkInterfaceType.Tunnel ||
                        nic.NetworkInterfaceType == NetworkInterfaceType.Ppp)
                    {
                        score += 0.50;
                        types.Add($"Interfaz Tunnel/PPP ({nic.NetworkInterfaceType})");
                        adapters.Add($"{nic.Name} ({nic.Description})");
                        artifacts.Add($"Adaptador activo de tipo túnel detectado: '{nic.Name}' [{nic.NetworkInterfaceType}].");
                    }

                    // Comprobar firmas por palabra clave
                    foreach (var kw in VpnKeywords)
                    {
                        if (combined.Contains(kw))
                        {
                            score += 0.55;
                            string vpnProvider = IdentifyVpnProvider(kw);
                            types.Add(vpnProvider);
                            adapters.Add($"{nic.Name} ({nic.Description})");
                            artifacts.Add($"Adaptador de red coincide con firma de VPN conocida: '{kw}' en '{nic.Description}'.");
                            break;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error inspeccionando interfaces de red: {ex.Message}");
            }
        }

        private static void InspectSystemProxy(HashSet<string> types, List<string> artifacts, ref double score)
        {
            try
            {
                // 1. Registro de Windows: ProxyEnable y ProxyServer
                using var internetSettings = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Internet Settings");
                if (internetSettings != null)
                {
                    object? proxyEnable = internetSettings.GetValue("ProxyEnable");
                    if (proxyEnable != null && Convert.ToInt32(proxyEnable) == 1)
                    {
                        string proxyServer = internetSettings.GetValue("ProxyServer")?.ToString() ?? "desconocido";
                        score += 0.50;
                        types.Add("Proxy HTTP/SOCKS del Sistema");
                        artifacts.Add($"Proxy manual activo en Windows: '{proxyServer}'.");
                    }

                    string autoConfig = internetSettings.GetValue("AutoConfigURL")?.ToString() ?? "";
                    if (!string.IsNullOrWhiteSpace(autoConfig))
                    {
                        score += 0.40;
                        types.Add("Proxy Automático (PAC)");
                        artifacts.Add($"Script de autoconfiguración de Proxy (PAC) activo: '{autoConfig}'.");
                    }
                }

                // 2. WebRequest.DefaultWebProxy
                var defaultProxy = WebRequest.DefaultWebProxy;
                if (defaultProxy != null)
                {
                    var testUri = new Uri("http://example.com");
                    var proxyUri = defaultProxy.GetProxy(testUri);
                    if (proxyUri != null && proxyUri != testUri)
                    {
                        score += 0.45;
                        types.Add("Proxy .NET Default");
                        artifacts.Add($"WebRequest redirigido a través del Proxy: '{proxyUri}'.");
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error inspeccionando configuración de proxy: {ex.Message}");
            }
        }

        private static void InspectMtuAnomalies(HashSet<string> types, List<string> artifacts, ref double score)
        {
            try
            {
                foreach (var nic in NetworkInterface.GetAllNetworkInterfaces())
                {
                    if (nic.OperationalStatus != OperationalStatus.Up) continue;
                    if (nic.NetworkInterfaceType == NetworkInterfaceType.Loopback) continue;

                    var ipProps = nic.GetIPProperties();
                    var ipv4Props = ipProps.GetIPv4Properties();
                    if (ipv4Props != null)
                    {
                        int mtu = ipv4Props.Mtu;
                        // MTUs típicos de túneles VPN: 1280 (IPv6 tunnel), 1360, 1400, 1420 (Wireguard), 1450 (GRE)
                        // Ethernet estándar es 1500.
                        if (mtu > 0 && mtu <= 1420 && mtu >= 1200)
                        {
                            // Si además tiene una puerta de enlace asignada, refuerza sospecha
                            if (ipProps.GatewayAddresses.Count > 0)
                            {
                                score += 0.25;
                                types.Add("MTU Anómalo de Túnel");
                                artifacts.Add($"Adaptador '{nic.Name}' presenta MTU encapsulado ({mtu} bytes), típico de túneles WireGuard/OpenVPN.");
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error inspeccionando MTU: {ex.Message}");
            }
        }

        private static void InspectDnsServers(HashSet<string> types, List<string> artifacts, ref double score)
        {
            try
            {
                foreach (var nic in NetworkInterface.GetAllNetworkInterfaces())
                {
                    if (nic.OperationalStatus != OperationalStatus.Up) continue;

                    var ipProps = nic.GetIPProperties();
                    foreach (var dns in ipProps.DnsAddresses)
                    {
                        string dnsStr = dns.ToString();
                        // Rango típico de servidores DNS de OpenVPN/Wireguard en túneles locales
                        if (dnsStr.StartsWith("10.8.") || dnsStr.StartsWith("10.2.") || dnsStr.StartsWith("100.64."))
                        {
                            score += 0.35;
                            types.Add("DNS Privado de Red VPN");
                            artifacts.Add($"Servidor DNS en subred de túnel VPN detectado: {dnsStr} en '{nic.Name}'.");
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error inspeccionando servidores DNS: {ex.Message}");
            }
        }

        private static async Task InspectPublicIpReputationAsync(VpnDetectionResult result, CancellationToken ct)
        {
            using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(2.5) };
            http.DefaultRequestHeaders.Add("User-Agent", "WoldVirtualP2P3D-Security/2.5.5");

            string? json = null;
            foreach (var url in PublicIpServices)
            {
                try
                {
                    var response = await http.GetAsync(url, ct);
                    if (response.IsSuccessStatusCode)
                    {
                        json = await response.Content.ReadAsStringAsync(ct);
                        break;
                    }
                }
                catch
                {
                    // Intentar con el siguiente endpoint de respaldo
                }
            }

            if (string.IsNullOrWhiteSpace(json)) return;

            try
            {
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                string org = "";
                if (root.TryGetProperty("org", out var orgProp)) org = orgProp.GetString() ?? "";
                if (string.IsNullOrWhiteSpace(org) && root.TryGetProperty("isp", out var ispProp)) org = ispProp.GetString() ?? "";

                if (!string.IsNullOrWhiteSpace(org))
                {
                    string orgLower = org.ToLowerInvariant();
                    foreach (var dc in DatacenterHostingKeywords)
                    {
                        if (orgLower.Contains(dc))
                        {
                            result.ConfidenceScore += 0.55;
                            result.DetectedVpnTypes.Add($"Proveedor Datacenter/Hosting ({org})");
                            result.Artifacts.Add($"La IP pública proviene de un centro de datos / servidor cloud ({org}) en vez de un ISP residencial.");
                            break;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error parseando respuesta de reputación IP: {ex.Message}");
            }
        }

        private static string IdentifyVpnProvider(string keyword)
        {
            if (keyword.Contains("wireguard")) return "Protocolo WireGuard";
            if (keyword.Contains("openvpn") || keyword.Contains("tap-windows")) return "Protocolo OpenVPN (TAP/TUN)";
            if (keyword.Contains("wintun")) return "Adaptador Wintun";
            if (keyword.Contains("nordlynx") || keyword.Contains("nordvpn")) return "NordVPN";
            if (keyword.Contains("proton")) return "ProtonVPN";
            if (keyword.Contains("tailscale")) return "Red Mesh Tailscale";
            if (keyword.Contains("zerotier")) return "Red Virtual ZeroTier";
            if (keyword.Contains("cloudflare") || keyword.Contains("warp")) return "Cloudflare 1.1.1.1 WARP";
            if (keyword.Contains("expressvpn")) return "ExpressVPN";
            if (keyword.Contains("surfshark")) return "Surfshark VPN";
            if (keyword.Contains("mullvad")) return "Mullvad VPN";
            if (keyword.Contains("cisco")) return "Cisco AnyConnect VPN";
            if (keyword.Contains("forti")) return "Fortinet VPN";
            return $"Software VPN ({keyword})";
        }
    }
}
