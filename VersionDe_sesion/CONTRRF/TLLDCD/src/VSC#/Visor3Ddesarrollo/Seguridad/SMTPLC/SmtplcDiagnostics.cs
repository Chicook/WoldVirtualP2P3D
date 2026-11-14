using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;

namespace Visor3D.Seguridad.SMTPLC
{
    /// <summary>
    /// Herramienta de autodiagnóstico y pruebas rápidas para el subsistema SMTPLC.
    /// Permite evaluar el estado de seguridad de la máquina local y generar un reporte instantáneo.
    /// </summary>
    public static class SmtplcDiagnostics
    {
        /// <summary>
        /// Ejecuta un diagnóstico completo en la máquina actual y devuelve el informe detallado en texto.
        /// </summary>
        public static async Task<string> RunFullDiagnosticAsync(string testAccount = "TestAuditoria")
        {
            var sw = Stopwatch.StartNew();
            var service = SmtplcSecurityService.Instance;

            var evaluation = await service.EvaluateRegistrationAsync(
                testAccount,
                LocationFingerprinter.GetDeviceMachineGuid());

            sw.Stop();

            var report = new StringBuilder();
            report.AppendLine("================================================================================");
            report.AppendLine("             DIAGNÓSTICO DEL SISTEMA DE SEGURIDAD SMTPLC                       ");
            report.AppendLine("================================================================================");
            report.AppendLine($"Tiempo de Análisis:   {sw.ElapsedMilliseconds} ms");
            report.AppendLine($"Resultado Global:     {(evaluation.IsAllowed ? "APROBADO (Permite Registro)" : "DENEGADO (Bloqueo Activo)")}");
            report.AppendLine($"Código de Decisión:   {evaluation.Code}");
            report.AppendLine($"Título:               {evaluation.DenialTitle}");
            report.AppendLine($"Motivo Explicativo:   {evaluation.DenialReason}");
            report.AppendLine();

            report.AppendLine("[1] MÁQUINA VIRTUAL (ANTI-VM):");
            report.AppendLine($"    - ¿Es Entorno Virtual?: {evaluation.VmResult.IsVm}");
            report.AppendLine($"    - Confianza:           {evaluation.VmResult.ConfidenceScore * 100:0.0}%");
            report.AppendLine($"    - Resumen:             {evaluation.VmResult.Summary}");
            if (evaluation.VmResult.Artifacts.Count > 0)
            {
                report.AppendLine("    - Artefactos detectados:");
                foreach (var art in evaluation.VmResult.Artifacts)
                    report.AppendLine($"      * {art}");
            }

            report.AppendLine();
            report.AppendLine("[2] RED, VPN Y PROXIES (ANTI-VPN):");
            report.AppendLine($"    - ¿Es VPN / Proxy?:    {evaluation.VpnResult.IsVpnOrProxy}");
            report.AppendLine($"    - Confianza:           {evaluation.VpnResult.ConfidenceScore * 100:0.0}%");
            report.AppendLine($"    - Resumen:             {evaluation.VpnResult.Summary}");
            if (evaluation.VpnResult.Artifacts.Count > 0)
            {
                report.AppendLine("    - Artefactos detectados:");
                foreach (var art in evaluation.VpnResult.Artifacts)
                    report.AppendLine($"      * {art}");
            }

            report.AppendLine();
            report.AppendLine("[3] ANCLAJE DE UBICACIÓN FÍSICA MULTI-DISPOSITIVO:");
            report.AppendLine($"    - IP Pública WAN:      {evaluation.LocationSignature.PublicIp}");
            report.AppendLine($"    - Gateway Router IP:   {evaluation.LocationSignature.GatewayIp}");
            report.AppendLine($"    - Gateway MAC (BSSID): {evaluation.LocationSignature.GatewayMacAddress}");
            report.AppendLine($"    - Clúster Wi-Fi RF:    {evaluation.LocationSignature.WifiClusterHash}");
            report.AppendLine($"    - LocationClusterHash: {evaluation.LocationSignature.LocationClusterHash}");
            report.AppendLine($"    - DeviceMachineGuid:   {evaluation.LocationSignature.DeviceMachineGuid}");

            report.AppendLine();
            report.AppendLine("[4] ESTADO DEL LIBRO MAYOR (LEDGER):");
            report.AppendLine($"    - Cuentas en el lugar: {evaluation.ExistingAccountsInLocation}");
            foreach (var acc in evaluation.ConflictingAccounts)
            {
                report.AppendLine($"      * Cuenta '{acc.AccountName}' registrada el {acc.RegisteredAtUtc:yyyy-MM-dd HH:mm} UTC");
            }

            report.AppendLine("================================================================================");
            return report.ToString();
        }
    }
}
