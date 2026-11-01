using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Win32;

namespace Visor3D.Seguridad.SMTPLC
{
    /// <summary>
    /// Generador de firmas de ubicación física persistente.
    /// Correlaciona y vincula diferentes dispositivos presentes en el mismo espacio físico
    /// mediante el análisis combinado de:
    /// 1. Dirección MAC física del Router de Enlace (BSSID Gateway mediante resolución ARP a nivel 2).
    /// 2. Clúster de balizas Wi-Fi ambientales (RF Fingerprint mediante WlanAPI).
    /// 3. Subred e IP pública compartida (NAT).
    /// </summary>
    public static class LocationFingerprinter
    {
        private static readonly string[] PublicIpEndpoints = new[]
        {
            "https://api.ipify.org",
            "https://icanhazip.com",
            "https://checkip.amazonaws.com"
        };

        /// <summary>
        /// Captura la firma de ubicación física completa del dispositivo actual.
        /// </summary>
        public static async Task<PhysicalLocationSignature> CaptureAsync(CancellationToken cancellationToken = default)
        {
            var signature = new PhysicalLocationSignature
            {
                DeviceMachineGuid = GetDeviceMachineGuid(),
                TimestampUtc = DateTime.UtcNow
            };

            // 1. Obtener IP y MAC física del Router / Gateway predeterminado
            (string gatewayIp, string gatewayMac) = ResolveDefaultGatewayMac();
            signature.GatewayIp = gatewayIp;
            signature.GatewayMacAddress = gatewayMac;

            // 2. Obtener Clúster de Balizas Wi-Fi del entorno físico (RF Spectrum)
            signature.WifiClusterHash = CaptureAmbientWifiClusterHash();

            // 3. Obtener IP Pública y Subred WAN
            signature.PublicIp = await ResolvePublicIpAsync(cancellationToken);
            signature.PublicSubnetHash = ComputeSubnetHash(signature.PublicIp);

            // 4. Calcular el Hash Maestro de Ubicación Física (LocationClusterHash)
            signature.LocationClusterHash = ComputeLocationClusterHash(
                signature.GatewayMacAddress,
                signature.WifiClusterHash,
                signature.PublicSubnetHash);

            return signature;
        }

        /// <summary>
        /// Identifica la puerta de enlace predeterminada activa y resuelve su MAC física vía ARP.
        /// Todos los dispositivos en la misma red local (casa/oficina) obtienen la misma MAC.
        /// </summary>
        private static (string GatewayIp, string GatewayMac) ResolveDefaultGatewayMac()
        {
            string gatewayIp = "";
            string gatewayMac = "";

            try
            {
                // Buscar la interfaz de red principal activa con Gateway
                foreach (var nic in NetworkInterface.GetAllNetworkInterfaces())
                {
                    if (nic.OperationalStatus != OperationalStatus.Up) continue;
                    if (nic.NetworkInterfaceType == NetworkInterfaceType.Loopback) continue;

                    var ipProps = nic.GetIPProperties();
                    foreach (var gw in ipProps.GatewayAddresses)
                    {
                        if (gw.Address.AddressFamily == AddressFamily.InterNetwork &&
                            !gw.Address.Equals(IPAddress.Any) &&
                            !gw.Address.Equals(IPAddress.None))
                        {
                            gatewayIp = gw.Address.ToString();
                            gatewayMac = QueryArpMac(gw.Address);
                            if (!string.IsNullOrEmpty(gatewayMac))
                            {
                                return (gatewayIp, gatewayMac);
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error resolviendo Gateway MAC: {ex.Message}");
            }

            return (gatewayIp, string.IsNullOrEmpty(gatewayMac) ? "00:00:00:00:00:00" : gatewayMac);
        }

        /// <summary>
        /// Consulta la MAC del Gateway mediante la llamada nativa SendARP (Iphlpapi.dll).
        /// </summary>
        private static string QueryArpMac(IPAddress ipAddress)
        {
            try
            {
                byte[] ipBytes = ipAddress.GetAddressBytes();
                uint destIp = BitConverter.ToUInt32(ipBytes, 0);

                byte[] macBytes = new byte[6];
                uint macLen = (uint)macBytes.Length;

                int ret = SmtplcNativeMethods.SendARP(destIp, 0, macBytes, ref macLen);
                if (ret == 0 && macLen == 6)
                {
                    return string.Join(":", macBytes.Select(b => b.ToString("X2")));
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Falló SendARP para {ipAddress}: {ex.Message}");
            }

            return "";
        }

        /// <summary>
        /// Escanea las redes Wi-Fi visibles en el entorno mediante WlanAPI y computa un hash
        /// del conjunto de BSSIDs y SSIDs. Este espectro RF es único de la posición geográfica física.
        /// </summary>
        private static string CaptureAmbientWifiClusterHash()
        {
            IntPtr clientHandle = IntPtr.Zero;
            IntPtr pInterfaceList = IntPtr.Zero;
            var bssids = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);

            try
            {
                uint negotiatedVersion;
                uint result = SmtplcNativeMethods.WlanOpenHandle(
                    SmtplcNativeMethods.WLAN_CLIENT_VERSION_VISTA,
                    IntPtr.Zero,
                    out negotiatedVersion,
                    out clientHandle);

                if (result != 0 || clientHandle == IntPtr.Zero)
                {
                    return "WIFI_UNAVAILABLE_OR_DISABLED";
                }

                result = SmtplcNativeMethods.WlanEnumInterfaces(clientHandle, IntPtr.Zero, out pInterfaceList);
                if (result != 0 || pInterfaceList == IntPtr.Zero)
                {
                    return "WIFI_NO_INTERFACES";
                }

                var interfaceList = Marshal.PtrToStructure<SmtplcNativeMethods.WLAN_INTERFACE_INFO_LIST>(pInterfaceList);
                IntPtr currentIntfPtr = new IntPtr(pInterfaceList.ToInt64() + Marshal.SizeOf(typeof(uint)) * 2);

                for (int i = 0; i < interfaceList.dwNumberOfItems; i++)
                {
                    var info = Marshal.PtrToStructure<SmtplcNativeMethods.WLAN_INTERFACE_INFO>(currentIntfPtr);
                    Guid guid = info.InterfaceGuid;

                    IntPtr pAvailableList = IntPtr.Zero;
                    uint netResult = SmtplcNativeMethods.WlanGetAvailableNetworkList(
                        clientHandle,
                        ref guid,
                        2, // WLAN_AVAILABLE_NETWORK_INCLUDE_ALL_MANUAL_HIDDEN_PROFILES
                        IntPtr.Zero,
                        out pAvailableList);

                    if (netResult == 0 && pAvailableList != IntPtr.Zero)
                    {
                        try
                        {
                            var netList = Marshal.PtrToStructure<SmtplcNativeMethods.WLAN_AVAILABLE_NETWORK_LIST>(pAvailableList);
                            IntPtr currentNetPtr = new IntPtr(pAvailableList.ToInt64() + Marshal.SizeOf(typeof(uint)) * 2);
                            int structSize = Marshal.SizeOf(typeof(SmtplcNativeMethods.WLAN_AVAILABLE_NETWORK));

                            for (int j = 0; j < netList.dwNumberOfItems; j++)
                            {
                                var network = Marshal.PtrToStructure<SmtplcNativeMethods.WLAN_AVAILABLE_NETWORK>(currentNetPtr);
                                if (network.dot11Ssid.uSSIDLength > 0)
                                {
                                    string ssid = Encoding.UTF8.GetString(
                                        network.dot11Ssid.ucSSID, 0, (int)network.dot11Ssid.uSSIDLength);
                                    bssids.Add($"{ssid}_{network.wlanSignalQuality / 10}");
                                }
                                currentNetPtr = new IntPtr(currentNetPtr.ToInt64() + structSize);
                            }
                        }
                        finally
                        {
                            SmtplcNativeMethods.WlanFreeMemory(pAvailableList);
                        }
                    }

                    currentIntfPtr = new IntPtr(currentIntfPtr.ToInt64() + Marshal.SizeOf(typeof(SmtplcNativeMethods.WLAN_INTERFACE_INFO)));
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Excepción escaneando Wi-Fi ambiental: {ex.Message}");
            }
            finally
            {
                if (pInterfaceList != IntPtr.Zero)
                {
                    SmtplcNativeMethods.WlanFreeMemory(pInterfaceList);
                }
                if (clientHandle != IntPtr.Zero)
                {
                    SmtplcNativeMethods.WlanCloseHandle(clientHandle, IntPtr.Zero);
                }
            }

            if (bssids.Count == 0)
            {
                return "WIFI_BEACONS_NONE";
            }

            // Tomar los primeros 12 identificadores más representativos
            string joined = string.Join("|", bssids.Take(12));
            using var sha = SHA256.Create();
            byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(joined));
            return Convert.ToHexString(hash);
        }

        private static async Task<string> ResolvePublicIpAsync(CancellationToken ct)
        {
            using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(2.5) };
            http.DefaultRequestHeaders.Add("User-Agent", "WoldVirtualP2P3D-SMTPLC/2.5.5");

            foreach (var ep in PublicIpEndpoints)
            {
                try
                {
                    string ip = await http.GetStringAsync(ep, ct);
                    ip = ip.Trim();
                    if (IPAddress.TryParse(ip, out _))
                    {
                        return ip;
                    }
                }
                catch
                {
                    // Intentar siguiente endpoint
                }
            }

            return "127.0.0.1";
        }

        private static string ComputeSubnetHash(string ipAddress)
        {
            if (IPAddress.TryParse(ipAddress, out var ip))
            {
                byte[] bytes = ip.GetAddressBytes();
                // Subred /24 para IPv4 (agrupa conexiones en el mismo rango de ISP local)
                if (bytes.Length == 4)
                {
                    string subnet = $"{bytes[0]}.{bytes[1]}.{bytes[2]}.0/24";
                    using var sha = SHA256.Create();
                    return Convert.ToHexString(sha.ComputeHash(Encoding.UTF8.GetBytes(subnet)));
                }
            }

            return "SUBNET_LOCAL";
        }

        /// <summary>
        /// Computa el Hash de Clúster de Ubicación Física combinando MAC de Router, RF Wi-Fi y Subred WAN.
        /// </summary>
        public static string ComputeLocationClusterHash(string gatewayMac, string wifiClusterHash, string publicSubnetHash)
        {
            string raw = $"{gatewayMac.Trim().ToUpperInvariant()}:{wifiClusterHash}:{publicSubnetHash}";
            using var sha = SHA256.Create();
            byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(raw));
            return Convert.ToHexString(hash);
        }

        /// <summary>
        /// Obtiene el identificador de máquina local de Windows (MachineGuid) para diferenciar
        /// dos dispositivos reales físicos en la misma casa/oficina.
        /// </summary>
        public static string GetDeviceMachineGuid()
        {
            try
            {
                using var key = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Cryptography");
                string guid = key?.GetValue("MachineGuid")?.ToString() ?? "";
                if (!string.IsNullOrWhiteSpace(guid)) return guid;
            }
            catch
            {
                // Fallback
            }

            return Environment.MachineName;
        }
    }
}
