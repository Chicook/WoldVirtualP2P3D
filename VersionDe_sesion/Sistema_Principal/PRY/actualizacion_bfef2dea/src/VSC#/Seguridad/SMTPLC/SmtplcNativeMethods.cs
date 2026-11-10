using System;
using System.Runtime.InteropServices;

namespace Visor3D.Seguridad.SMTPLC
{
    /// <summary>
    /// Envolturas P/Invoke para APIs nativas de Windows (Iphlpapi, Wlanapi, WinINet).
    /// Permiten resolución ARP a nivel de hardware y detección de señales RF / proxies.
    /// </summary>
    internal static class SmtplcNativeMethods
    {
        #region Iphlpapi - Resolución ARP de Router / Gateway

        [DllImport("iphlpapi.dll", ExactSpelling = true)]
        public static extern int SendARP(
            uint destIp,
            uint srcIp,
            [Out] byte[] macAddr,
            ref uint macAddrLen);

        #endregion

        #region Wlanapi - Escaneo de Entorno Wi-Fi / BSSID Triangulation

        public const uint WLAN_CLIENT_VERSION_VISTA = 2;
        public const uint DOT11_SSID_MAX_LENGTH = 32;

        [DllImport("wlanapi.dll", SetLastError = true)]
        public static extern uint WlanOpenHandle(
            uint dwClientVersion,
            IntPtr pReserved,
            out uint pdwNegotiatedVersion,
            out IntPtr phClientHandle);

        [DllImport("wlanapi.dll", SetLastError = true)]
        public static extern uint WlanCloseHandle(
            IntPtr hClientHandle,
            IntPtr pReserved);

        [DllImport("wlanapi.dll", SetLastError = true)]
        public static extern uint WlanEnumInterfaces(
            IntPtr hClientHandle,
            IntPtr pReserved,
            out IntPtr ppInterfaceList);

        [DllImport("wlanapi.dll", SetLastError = true)]
        public static extern uint WlanGetAvailableNetworkList(
            IntPtr hClientHandle,
            ref Guid pInterfaceGuid,
            uint dwFlags,
            IntPtr pReserved,
            out IntPtr ppAvailableNetworkList);

        [DllImport("wlanapi.dll")]
        public static extern void WlanFreeMemory(IntPtr pMemory);

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        public struct WLAN_INTERFACE_INFO
        {
            public Guid InterfaceGuid;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)]
            public string strInterfaceDescription;
            public int isState;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct WLAN_INTERFACE_INFO_LIST
        {
            public uint dwNumberOfItems;
            public uint dwIndex;
            // Array de WLAN_INTERFACE_INFO sigue en memoria
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct DOT11_SSID
        {
            public uint uSSIDLength;
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = (int)DOT11_SSID_MAX_LENGTH)]
            public byte[] ucSSID;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        public struct WLAN_AVAILABLE_NETWORK
        {
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)]
            public string strProfileName;
            public DOT11_SSID dot11Ssid;
            public int dot11BssType;
            public uint uNumberOfBssids;
            public bool bNetworkConnectable;
            public uint wlanNotConnectableReason;
            public uint uNumberOfPhyTypes;
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 8)]
            public int[] dot11PhyType;
            public bool bMorePhyTypes;
            public uint wlanSignalQuality;
            public bool bSecurityEnabled;
            public int dot11DefaultAuthAlgorithm;
            public int dot11DefaultCipherAlgorithm;
            public uint dwFlags;
            public uint dwReserved;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct WLAN_AVAILABLE_NETWORK_LIST
        {
            public uint dwNumberOfItems;
            public uint dwIndex;
            // Array de WLAN_AVAILABLE_NETWORK sigue en memoria
        }

        #endregion
    }
}
