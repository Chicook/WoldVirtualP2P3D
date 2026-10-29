using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Seguridad.SMTPLC
{
    /// <summary>
    /// Servicio Principal del Sistema de Seguridad SMTPLC
    /// (Seguridad Multi-Terminal por Locación, Proxy y Clientes).
    /// Coordina y ejecuta en tiempo real:
    /// 1. Detección profunda de Máquinas Virtuales (VMware, VirtualBox, Hyper-V, QEMU, KVM).
    /// 2. Detección de conexiones VPN, Proxies y túneles de anonimización.
    /// 3. Prevención estricta de múltiples cuentas creadas en diferentes dispositivos dentro de la misma ubicación física.
    /// </summary>
    public class SmtplcSecurityService
    {
        private static readonly Lazy<SmtplcSecurityService> _instance =
            new(() => new SmtplcSecurityService());

        public static SmtplcSecurityService Instance => _instance.Value;

        public SmtplcPolicy Policy { get; set; } = new();
        public LocationAccountLedger Ledger { get; }

        public SmtplcSecurityService(LocationAccountLedger? ledger = null, SmtplcPolicy? policy = null)
        {
            Ledger = ledger ?? new LocationAccountLedger();
            if (policy != null) Policy = policy;
        }

        /// <summary>
        /// Evaluación integral asincrónica antes de permitir el registro de una cuenta.
        /// </summary>
        public async Task<SecurityEvaluationResult> EvaluateRegistrationAsync(
            string candidateAccountName,
            string? deviceHardwareHash = null,
            SmtplcPolicy? customPolicy = null,
            CancellationToken cancellationToken = default)
        {
            var policy = customPolicy ?? Policy;
            var evaluation = new SecurityEvaluationResult
            {
                EvaluatedAtUtc = DateTime.UtcNow
            };

            // =========================================================================
            // FASE 1: DETECCIÓN DE MÁQUINAS VIRTUALES (VM)
            // =========================================================================
            evaluation.VmResult = VmDetector.Analyze();

            if (policy.BlockVirtualMachines &&
                (evaluation.VmResult.IsVm || evaluation.VmResult.ConfidenceScore >= policy.VmConfidenceThreshold))
            {
                evaluation.IsAllowed = false;
                evaluation.Code = DenialReasonCode.VmDetected;
                evaluation.DenialTitle = "Entorno Virtualizado No Permitido";

                string detectedList = evaluation.VmResult.DetectedHypervisors.Count > 0
                    ? string.Join(", ", evaluation.VmResult.DetectedHypervisors)
                    : "Hipervisor genérico";

                evaluation.DenialReason =
                    $"Se ha detectado la ejecución en una Máquina Virtual ({detectedList}). " +
                    "Por motivos de seguridad, prevención de fraude y anti-sybil, la creación de cuentas " +
                    "solo está permitida en hardware físico real directamente instalado.";

                return evaluation;
            }

            // =========================================================================
            // FASE 2: DETECCIÓN DE VPNS, PROXIES Y TÚNELES DE ANONIMIZACIÓN
            // =========================================================================
            evaluation.VpnResult = await VpnDetector.AnalyzeAsync(cancellationToken);

            if (policy.BlockVpnAndProxies &&
                (evaluation.VpnResult.IsVpnOrProxy || evaluation.VpnResult.ConfidenceScore >= policy.VpnConfidenceThreshold))
            {
                evaluation.IsAllowed = false;
                evaluation.Code = DenialReasonCode.VpnOrProxyDetected;
                evaluation.DenialTitle = "Conexión VPN / Proxy Detectada";

                string vpnList = evaluation.VpnResult.DetectedVpnTypes.Count > 0
                    ? string.Join(", ", evaluation.VpnResult.DetectedVpnTypes)
                    : "Túnel anónimo";

                evaluation.DenialReason =
                    $"Se ha detectado el uso de una conexión intermedia ({vpnList}). " +
                    "Para garantizar la transparencia y evitar la creación no autorizada de cuentas duplicadas, " +
                    "debe registrarse utilizando una conexión a Internet directa legítima sin VPN ni Proxies activos.";

                return evaluation;
            }

            // =========================================================================
            // FASE 3: FIRMA DE UBICACIÓN FÍSICA MULTI-DISPOSITIVO (ARP + RF + NAT)
            // =========================================================================
            try
            {
                evaluation.LocationSignature = await LocationFingerprinter.CaptureAsync(cancellationToken);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Advertencia capturando firma de ubicación: {ex.Message}");
                // Fallback seguro de firma
                evaluation.LocationSignature = new PhysicalLocationSignature
                {
                    DeviceMachineGuid = LocationFingerprinter.GetDeviceMachineGuid(),
                    GatewayMacAddress = "00:00:00:00:00:00",
                    LocationClusterHash = "FALLBACK_LOCATION_HASH"
                };
            }

            // =========================================================================
            // FASE 4: EVALUACIÓN DE POLÍTICA MULTI-CUENTA EN LA MISMA UBICACIÓN
            // =========================================================================
            var (allowed, code, reason, conflicts) = Ledger.EvaluateLocationQuota(
                evaluation.LocationSignature, policy);

            evaluation.ExistingAccountsInLocation = conflicts.Count;
            evaluation.ConflictingAccounts = conflicts;

            if (!allowed)
            {
                evaluation.IsAllowed = false;
                evaluation.Code = code;
                evaluation.DenialTitle = code == DenialReasonCode.MultipleAccountsInSameLocation
                    ? "Límite de Cuentas por Ubicación Alcanzado"
                    : "Período de Enfriamiento por Ubicación Activo";
                evaluation.DenialReason = reason;

                return evaluation;
            }

            // =========================================================================
            // VERIFICACIÓN EXITOSA
            // =========================================================================
            evaluation.IsAllowed = true;
            evaluation.Code = DenialReasonCode.Allowed;
            evaluation.DenialTitle = "Autorizado";
            evaluation.DenialReason = "Todas las políticas de seguridad (Anti-VM, Anti-VPN y Anti-Multi-dispositivo) fueron aprobadas.";

            return evaluation;
        }

        /// <summary>
        /// Registra la cuenta de forma definitiva en el Ledger de ubicación tras ser creada.
        /// </summary>
        public void CommitRegistration(
            string accountUuid,
            string accountName,
            SecurityEvaluationResult evaluation,
            string? deviceHardwareHash = null)
        {
            if (string.IsNullOrWhiteSpace(accountUuid))
                throw new ArgumentException("El UUID de cuenta no puede estar vacío.", nameof(accountUuid));

            Ledger.RecordAccount(
                accountUuid,
                accountName,
                evaluation.LocationSignature,
                deviceHardwareHash ?? LocationFingerprinter.GetDeviceMachineGuid());
        }

        /// <summary>
        /// Genera un informe textual de auditoría completo apto para registros técnicos o soporte.
        /// </summary>
        public string GenerateFullAuditReport(SecurityEvaluationResult evaluation)
        {
            var sb = new StringBuilder();
            sb.AppendLine("=================================================================");
            sb.AppendLine("           INFORME DE AUDITORÍA DE SEGURIDAD SMTPLC             ");
            sb.AppendLine("=================================================================");
            sb.AppendLine($"Fecha/Hora UTC:    {evaluation.EvaluatedAtUtc:yyyy-MM-dd HH:mm:ss} UTC");
            sb.AppendLine($"Estado General:    {(evaluation.IsAllowed ? "[APROBADO]" : "[DENEGADO]")}");
            sb.AppendLine($"Código:            {evaluation.Code}");
            sb.AppendLine($"Motivo:            {evaluation.DenialReason}");
            sb.AppendLine();

            sb.AppendLine("--- 1. EVALUACIÓN DE MÁQUINA VIRTUAL (Anti-VM) ---");
            sb.AppendLine($"Es VM:             {evaluation.VmResult.IsVm}");
            sb.AppendLine($"Confianza:         {evaluation.VmResult.ConfidenceScore * 100:0.0}%");
            sb.AppendLine($"Hipervisores:      {(evaluation.VmResult.DetectedHypervisors.Count > 0 ? string.Join(", ", evaluation.VmResult.DetectedHypervisors) : "Ninguno")}");
            foreach (var art in evaluation.VmResult.Artifacts)
            {
                sb.AppendLine($"  - [Hallazgo] {art}");
            }
            sb.AppendLine();

            sb.AppendLine("--- 2. EVALUACIÓN DE RED Y VPN (Anti-VPN / Proxy) ---");
            sb.AppendLine($"Es VPN/Proxy:      {evaluation.VpnResult.IsVpnOrProxy}");
            sb.AppendLine($"Confianza:         {evaluation.VpnResult.ConfidenceScore * 100:0.0}%");
            sb.AppendLine($"Tipos detectados:  {(evaluation.VpnResult.DetectedVpnTypes.Count > 0 ? string.Join(", ", evaluation.VpnResult.DetectedVpnTypes) : "Conexión directa")}");
            foreach (var art in evaluation.VpnResult.Artifacts)
            {
                sb.AppendLine($"  - [Hallazgo] {art}");
            }
            sb.AppendLine();

            sb.AppendLine("--- 3. ANCLAJE DE UBICACIÓN FÍSICA MULTI-DISPOSITIVO ---");
            sb.AppendLine($"IP Pública WAN:    {evaluation.LocationSignature.PublicIp}");
            sb.AppendLine($"Gateway Router MAC:{evaluation.LocationSignature.GatewayMacAddress}");
            sb.AppendLine($"Hash RF Wi-Fi:     {evaluation.LocationSignature.WifiClusterHash}");
            sb.AppendLine($"Hash Ubicación:    {evaluation.LocationSignature.LocationClusterHash}");
            sb.AppendLine($"Dispositivo GUID:  {evaluation.LocationSignature.DeviceMachineGuid}");
            sb.AppendLine();

            sb.AppendLine("--- 4. LIBRO MAYOR DE CUENTAS EN LA UBICACIÓN ---");
            sb.AppendLine($"Cuentas previas:   {evaluation.ExistingAccountsInLocation}");
            foreach (var acc in evaluation.ConflictingAccounts)
            {
                sb.AppendLine($"  - Cuenta: {acc.AccountName} (UUID: {acc.AccountUuid}, Registrada: {acc.RegisteredAtUtc:yyyy-MM-dd HH:mm:ss} UTC)");
            }
            sb.AppendLine("=================================================================");

            return sb.ToString();
        }
    }
}
