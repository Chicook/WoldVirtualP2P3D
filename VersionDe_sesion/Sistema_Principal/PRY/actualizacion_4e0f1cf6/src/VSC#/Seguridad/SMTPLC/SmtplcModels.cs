using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Visor3D.Seguridad.SMTPLC
{
    /// <summary>
    /// Código de denegación o resultado de la evaluación de seguridad.
    /// </summary>
    public enum DenialReasonCode
    {
        Allowed = 0,
        VmDetected = 1,
        VpnOrProxyDetected = 2,
        MultipleAccountsInSameLocation = 3,
        LocationCooldownActive = 4,
        HardwareTamperingDetected = 5,
        InternalError = 6
    }

    /// <summary>
    /// Resultado del análisis de detección de Máquinas Virtuales (VM).
    /// </summary>
    public class VmDetectionResult
    {
        public bool IsVm { get; set; }
        public double ConfidenceScore { get; set; } // 0.0 a 1.0 (0% a 100%)
        public List<string> DetectedHypervisors { get; set; } = new();
        public List<string> Artifacts { get; set; } = new();
        public string Summary { get; set; } = "Sin indicios de máquina virtual.";

        public override string ToString() =>
            IsVm ? $"[VM DETECTADA - Confianza: {ConfidenceScore * 100:0.#}%] {string.Join(", ", DetectedHypervisors)}"
                 : "[SISTEMA REAL] No se detectó entorno virtualizado.";
    }

    /// <summary>
    /// Resultado del análisis de detección de VPNs, Proxies o Túneles.
    /// </summary>
    public class VpnDetectionResult
    {
        public bool IsVpnOrProxy { get; set; }
        public double ConfidenceScore { get; set; } // 0.0 a 1.0
        public List<string> DetectedVpnTypes { get; set; } = new();
        public List<string> DetectedAdapters { get; set; } = new();
        public List<string> Artifacts { get; set; } = new();
        public string Summary { get; set; } = "Conexión directa legítima (sin VPN ni Proxy detectados).";

        public override string ToString() =>
            IsVpnOrProxy ? $"[VPN/PROXY DETECTADO - Confianza: {ConfidenceScore * 100:0.#}%] {string.Join(", ", DetectedVpnTypes)}"
                         : "[CONEXIÓN DIRECTA] Conexión de red legítima.";
    }

    /// <summary>
    /// Firma de ubicación física única y persistente, calculada combinando:
    /// 1. MAC física del router de enlace predeterminado (BSSID Gateway vía ARP).
    /// 2. Clúster de balizas Wi-Fi visibles en el espectro ambiental.
    /// 3. Subred e IP pública de salida.
    /// Esta firma vincula múltiples dispositivos físicamente situados en el mismo lugar.
    /// </summary>
    public class PhysicalLocationSignature
    {
        public string PublicIp { get; set; } = "";
        public string PublicSubnetHash { get; set; } = "";
        public string GatewayIp { get; set; } = "";
        public string GatewayMacAddress { get; set; } = "";
        public string WifiClusterHash { get; set; } = "";
        public string DeviceMachineGuid { get; set; } = "";

        /// <summary>
        /// Hash maestro criptográfico de ubicación física (SHA-256 de Gateway MAC + Wi-Fi Cluster + Subred WAN).
        /// Todos los dispositivos en el mismo router o recinto físico compartirán este hash.
        /// </summary>
        public string LocationClusterHash { get; set; } = "";

        public DateTime TimestampUtc { get; set; } = DateTime.UtcNow;

        public override string ToString() =>
            $"LocationHash: {LocationClusterHash[..Math.Min(16, LocationClusterHash.Length)]}... (Gateway: {GatewayMacAddress}, WAN: {PublicIp})";
    }

    /// <summary>
    /// Registro persistente de una cuenta creada en una ubicación física determinada.
    /// </summary>
    public class LocationAccountRecord
    {
        public string AccountUuid { get; set; } = "";
        public string AccountName { get; set; } = "";
        public string LocationClusterHash { get; set; } = "";
        public string GatewayMac { get; set; } = "";
        public string PublicIpHash { get; set; } = "";
        public string DeviceHardwareHash { get; set; } = "";
        public DateTime RegisteredAtUtc { get; set; } = DateTime.UtcNow;
        public string Status { get; set; } = "Activo"; // Activo, Suspendido, EnObservacion
    }

    /// <summary>
    /// Políticas de seguridad configurables para la prevención multi-cuenta y anti-evasión.
    /// </summary>
    public class SmtplcPolicy
    {
        /// <summary>
        /// Máximo de cuentas permitidas por ubicación física (Por defecto: 1 cuenta por ubicación).
        /// </summary>
        public int MaxAccountsPerLocation { get; set; } = 1;

        /// <summary>
        /// Período de enfriamiento (cooldown) en minutos entre la creación de cuentas en la misma ubicación.
        /// Por defecto: 4320 minutos (72 horas / 3 días).
        /// </summary>
        public int CooldownMinutesBetweenAccounts { get; set; } = 4320;

        /// <summary>
        /// Bloquear terminantemente el registro si se detecta Máquina Virtual.
        /// </summary>
        public bool BlockVirtualMachines { get; set; } = true;

        /// <summary>
        /// Bloquear terminantemente el registro si se detecta VPN, Proxy o Túnel de anonimización.
        /// </summary>
        public bool BlockVpnAndProxies { get; set; } = true;

        /// <summary>
        /// Nivel de confianza mínimo requerido para activar el bloqueo de VM (0.0 a 1.0).
        /// </summary>
        public double VmConfidenceThreshold { get; set; } = 0.50;

        /// <summary>
        /// Nivel de confianza mínimo requerido para activar el bloqueo de VPN (0.0 a 1.0).
        /// </summary>
        public double VpnConfidenceThreshold { get; set; } = 0.40;

        /// <summary>
        /// Forzar resolución ARP del Gateway y análisis Wi-Fi ambiental.
        /// </summary>
        public bool EnforcePhysicalSignatures { get; set; } = true;
    }

    /// <summary>
    /// Evaluación integral del intento de registro.
    /// </summary>
    public class SecurityEvaluationResult
    {
        public bool IsAllowed { get; set; }
        public DenialReasonCode Code { get; set; } = DenialReasonCode.Allowed;
        public string DenialTitle { get; set; } = "Permitido";
        public string DenialReason { get; set; } = "Verificación de seguridad superada satisfactoriamente.";
        public VmDetectionResult VmResult { get; set; } = new();
        public VpnDetectionResult VpnResult { get; set; } = new();
        public PhysicalLocationSignature LocationSignature { get; set; } = new();
        public int ExistingAccountsInLocation { get; set; }
        public List<LocationAccountRecord> ConflictingAccounts { get; set; } = new();
        public DateTime EvaluatedAtUtc { get; set; } = DateTime.UtcNow;

        [JsonIgnore]
        public bool IsVmViolation => VmResult.IsVm;

        [JsonIgnore]
        public bool IsVpnViolation => VpnResult.IsVpnOrProxy;

        [JsonIgnore]
        public bool IsMultiAccountViolation =>
            Code == DenialReasonCode.MultipleAccountsInSameLocation ||
            Code == DenialReasonCode.LocationCooldownActive;
    }
}
