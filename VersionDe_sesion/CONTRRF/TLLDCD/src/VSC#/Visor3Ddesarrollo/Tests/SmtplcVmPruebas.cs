using System.Net.NetworkInformation;
using Visor3D.Seguridad.SMTPLC;
using Xunit;

namespace Visor3D.Tests
{
    /// <summary>
    /// Clasificación de adaptadores de red para la detección de máquina virtual.
    /// El bloqueo por VM es un veto duro del registro, de modo que un falso
    /// positivo deja al usuario sin cuenta: estos casos fijan la frontera entre
    /// «adaptador que Windows crea por software en un equipo físico» (conmutadores
    /// de Hyper-V/WSL2, VMnet de VMware, host-only de VirtualBox, túneles) y
    /// «NIC de un invitado real», que sí debe contar.
    /// </summary>
    public class SmtplcVmPruebas
    {
        [Theory]
        [InlineData("vEthernet (Default Switch)", "Hyper-V Virtual Ethernet Adapter #2")]
        [InlineData("vEthernet (WSL (Hyper-V firewall))", "Hyper-V Virtual Ethernet Adapter")]
        [InlineData("VMware Network Adapter VMnet8", "VMware Virtual Ethernet Adapter for VMnet8")]
        [InlineData("VirtualBox Host-Only Network", "VirtualBox Host-Only Ethernet Adapter")]
        [InlineData("WireGuard Tunnel", "Wintun Userspace Tunnel")]
        public void Los_conmutadores_por_software_no_cuentan_como_VM(string nombre, string descripcion)
        {
            Assert.True(VmDetector.EsAdaptadorNoFisico(nombre, descripcion, NetworkInterfaceType.Ethernet));
        }

        [Theory]
        [InlineData("Ethernet", "Microsoft Hyper-V Network Adapter")]      // invitado de Hyper-V: SÍ cuenta
        [InlineData("Ethernet 2", "Realtek PCIe GbE Family Controller")]
        [InlineData("Ethernet", "Intel(R) 82574L Gigabit Network Connection")]
        [InlineData("Wi-Fi", "Intel(R) Wi-Fi 6 AX201 160MHz")]
        public void Las_NIC_de_invitado_y_de_hardware_real_si_cuentan(string nombre, string descripcion)
        {
            Assert.False(VmDetector.EsAdaptadorNoFisico(nombre, descripcion, NetworkInterfaceType.Ethernet));
        }

        [Theory]
        [InlineData(NetworkInterfaceType.Loopback)]
        [InlineData(NetworkInterfaceType.Tunnel)]
        public void Loopback_y_tuneles_nunca_cuentan(NetworkInterfaceType tipo)
        {
            Assert.True(VmDetector.EsAdaptadorNoFisico("cualquiera", "cualquiera", tipo));
        }
    }
}
