using Visor3D.Seguridad.SMTPLC;
using Xunit;

namespace Visor3D.Tests
{
    /// <summary>
    /// Acoplamiento entre los detectores y la política SMTPLC (issue #26).
    /// Los umbrales viven duplicados a propósito —un const en el detector y el
    /// default de la política— porque la política decide con
    /// <c>IsVm || score >= umbral</c>: si el detector marcara por debajo, una sola
    /// señal floja bloquearía el alta. Aquí se fija esa igualdad para que mover
    /// uno de los dos sin el otro falle en la suite y no en producción.
    /// No se llama a Analyze(): lee WMI, registro y procesos, y su resultado
    /// depende del equipo donde corre la prueba.
    /// </summary>
    public sealed class SmtplcUmbralesPruebas
    {
        [Fact]
        public void El_umbral_de_vm_del_detector_es_el_de_la_politica()
        {
            var policy = new SmtplcPolicy();
            Assert.Equal(VmDetector.UmbralVm, policy.VmConfidenceThreshold);
        }

        [Fact]
        public void El_umbral_de_vpn_del_detector_es_el_de_la_politica()
        {
            var policy = new SmtplcPolicy();
            Assert.Equal(VpnDetector.UmbralVpn, policy.VpnConfidenceThreshold);
        }

        [Fact]
        public void La_politica_por_defecto_es_cuenta_unica_y_tres_dias_de_espera()
        {
            var policy = new SmtplcPolicy();

            Assert.Equal(1, policy.MaxAccountsPerLocation);
            Assert.Equal(4320, policy.CooldownMinutesBetweenAccounts); // 72 h
        }

        [Fact]
        public void El_bloqueo_de_vm_y_vpn_viene_activado_por_defecto()
        {
            var policy = new SmtplcPolicy();

            Assert.True(policy.BlockVirtualMachines);
            Assert.True(policy.BlockVpnAndProxies);
            Assert.True(policy.EnforcePhysicalSignatures);
        }
    }
}
