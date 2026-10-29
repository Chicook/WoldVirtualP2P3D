using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Visor3D.Seguridad.SMTPLC
{
    /// <summary>
    /// Libro Mayor (Ledger) de Auditoría de Cuentas por Ubicación Física.
    /// Registra y valida el historial de cuentas creadas bajo una misma firma de ubicación física,
    /// aplicando límites de cuota (máximo de cuentas por hogar/oficina), períodos de enfriamiento (cooldown)
    /// y protección contra manipulación mediante HMAC-SHA256.
    /// </summary>
    public class LocationAccountLedger
    {
        private static readonly object _syncLock = new();
        private readonly string _ledgerFilePath;
        private readonly byte[] _hmacSecretKey;
        private List<LocationAccountRecord> _records = new();

        public LocationAccountLedger(string? customPath = null)
        {
            if (string.IsNullOrWhiteSpace(customPath))
            {
                string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                string securityDir = Path.Combine(localAppData, "WoldVirtualP2P3D", "security");
                Directory.CreateDirectory(securityDir);
                _ledgerFilePath = Path.Combine(securityDir, "smtplc_location_ledger.dat");
            }
            else
            {
                _ledgerFilePath = customPath;
                string? dir = Path.GetDirectoryName(_ledgerFilePath);
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            }

            // Clave HMAC derivada del hardware base del sistema para sellar integridad local
            _hmacSecretKey = DeriveLocalHmacKey();
            LoadLedger();
        }

        /// <summary>
        /// Obtiene todas las cuentas previamente registradas en la misma ubicación física dada por la firma.
        /// </summary>
        public List<LocationAccountRecord> GetAccountsInLocation(PhysicalLocationSignature signature)
        {
            lock (_syncLock)
            {
                return _records
                    .Where(r => r.LocationClusterHash.Equals(signature.LocationClusterHash, StringComparison.OrdinalIgnoreCase) ||
                                (!string.IsNullOrEmpty(r.GatewayMac) &&
                                 !r.GatewayMac.Equals("00:00:00:00:00:00") &&
                                 r.GatewayMac.Equals(signature.GatewayMacAddress, StringComparison.OrdinalIgnoreCase)))
                    .ToList();
            }
        }

        /// <summary>
        /// Evalúa si una nueva cuenta puede registrarse en la ubicación física según la política SMTPLC.
        /// </summary>
        public (bool Allowed, DenialReasonCode Code, string Reason, List<LocationAccountRecord> Conflicts) EvaluateLocationQuota(
            PhysicalLocationSignature signature,
            SmtplcPolicy policy)
        {
            lock (_syncLock)
            {
                var existingAccounts = GetAccountsInLocation(signature);

                // 1. Validar cuota máxima de cuentas por ubicación física
                if (existingAccounts.Count >= policy.MaxAccountsPerLocation)
                {
                    string accountNames = string.Join(", ", existingAccounts.Select(a => $"'{a.AccountName}'"));
                    string reason = $"Se ha alcanzado el límite máximo de {policy.MaxAccountsPerLocation} cuenta(s) para esta ubicación física " +
                                   $"(Red Gateway: {signature.GatewayMacAddress}). Cuentas ya asociadas: {accountNames}. " +
                                   $"No se permite crear múltiples cuentas desde diferentes dispositivos en la misma ubicación.";

                    return (false, DenialReasonCode.MultipleAccountsInSameLocation, reason, existingAccounts);
                }

                // 2. Validar período de enfriamiento (cooldown) si ya existe alguna cuenta en la ubicación
                if (existingAccounts.Count > 0 && policy.CooldownMinutesBetweenAccounts > 0)
                {
                    var lastRegistration = existingAccounts.MaxBy(a => a.RegisteredAtUtc);
                    if (lastRegistration != null)
                    {
                        var elapsed = DateTime.UtcNow - lastRegistration.RegisteredAtUtc;
                        if (elapsed.TotalMinutes < policy.CooldownMinutesBetweenAccounts)
                        {
                            double remainingMinutes = policy.CooldownMinutesBetweenAccounts - elapsed.TotalMinutes;
                            int remainingHours = (int)Math.Ceiling(remainingMinutes / 60.0);
                            string reason = $"Período de enfriamiento activo en esta ubicación física. Debe transcurrir al menos " +
                                           $"{policy.CooldownMinutesBetweenAccounts / 60} horas entre registros. " +
                                           $"Tiempo restante aproximado: {remainingHours} horas.";

                            return (false, DenialReasonCode.LocationCooldownActive, reason, existingAccounts);
                        }
                    }
                }

                return (true, DenialReasonCode.Allowed, "Ubicación verificada y habilitada para creación de cuenta.", existingAccounts);
            }
        }

        /// <summary>
        /// Registra de forma definitiva una cuenta en el Ledger vinculándola a su firma de ubicación física.
        /// </summary>
        public void RecordAccount(
            string accountUuid,
            string accountName,
            PhysicalLocationSignature signature,
            string deviceHardwareHash)
        {
            lock (_syncLock)
            {
                var record = new LocationAccountRecord
                {
                    AccountUuid = accountUuid,
                    AccountName = accountName,
                    LocationClusterHash = signature.LocationClusterHash,
                    GatewayMac = signature.GatewayMacAddress,
                    PublicIpHash = ComputeSha256(signature.PublicIp),
                    DeviceHardwareHash = deviceHardwareHash,
                    RegisteredAtUtc = DateTime.UtcNow,
                    Status = "Activo"
                };

                // Evitar duplicar el mismo UUID
                _records.RemoveAll(r => r.AccountUuid.Equals(accountUuid, StringComparison.OrdinalIgnoreCase));
                _records.Add(record);

                SaveLedger();
            }
        }

        /// <summary>
        /// Exporta la lista de registros para sincronización distribuida o P2P (hashes anonimizados).
        /// </summary>
        public string ExportJson()
        {
            lock (_syncLock)
            {
                return JsonSerializer.Serialize(_records, new JsonSerializerOptions { WriteIndented = true });
            }
        }

        /// <summary>
        /// Importa registros de ubicaciones provenientes de otros nodos de la red P2P.
        /// </summary>
        public int MergeExternalRecords(string json)
        {
            lock (_syncLock)
            {
                try
                {
                    var incoming = JsonSerializer.Deserialize<List<LocationAccountRecord>>(json);
                    if (incoming == null) return 0;

                    int mergedCount = 0;
                    foreach (var record in incoming)
                    {
                        if (!_records.Any(r => r.AccountUuid.Equals(record.AccountUuid, StringComparison.OrdinalIgnoreCase)))
                        {
                            _records.Add(record);
                            mergedCount++;
                        }
                    }

                    if (mergedCount > 0)
                    {
                        SaveLedger();
                    }

                    return mergedCount;
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"[SMTPLC] Error fusionando registros externos: {ex.Message}");
                    return 0;
                }
            }
        }

        private void LoadLedger()
        {
            lock (_syncLock)
            {
                if (!File.Exists(_ledgerFilePath))
                {
                    _records = new List<LocationAccountRecord>();
                    return;
                }

                try
                {
                    byte[] fileBytes = File.ReadAllBytes(_ledgerFilePath);
                    if (fileBytes.Length < 32)
                    {
                        // Archivo corrupto o alterado
                        _records = new List<LocationAccountRecord>();
                        return;
                    }

                    // Separar HMAC (primeros 32 bytes) del contenido payload
                    byte[] storedHmac = fileBytes.Take(32).ToArray();
                    byte[] payload = fileBytes.Skip(32).ToArray();

                    using var hmac = new HMACSHA256(_hmacSecretKey);
                    byte[] computedHmac = hmac.ComputeHash(payload);

                    if (!storedHmac.SequenceEqual(computedHmac))
                    {
                        System.Diagnostics.Debug.WriteLine("[SMTPLC] ADVERTENCIA: La firma HMAC del Ledger de ubicaciones no coincide (posible manipulación).");
                        // En caso de corrupción o manipulación, no cargamos datos inválidos
                        _records = new List<LocationAccountRecord>();
                        return;
                    }

                    string json = Encoding.UTF8.GetString(payload);
                    _records = JsonSerializer.Deserialize<List<LocationAccountRecord>>(json) ?? new List<LocationAccountRecord>();
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"[SMTPLC] Error cargando ledger: {ex.Message}");
                    _records = new List<LocationAccountRecord>();
                }
            }
        }

        private void SaveLedger()
        {
            lock (_syncLock)
            {
                try
                {
                    string json = JsonSerializer.Serialize(_records, new JsonSerializerOptions { WriteIndented = false });
                    byte[] payload = Encoding.UTF8.GetBytes(json);

                    using var hmac = new HMACSHA256(_hmacSecretKey);
                    byte[] computedHmac = hmac.ComputeHash(payload);

                    byte[] combined = new byte[computedHmac.Length + payload.Length];
                    Buffer.BlockCopy(computedHmac, 0, combined, 0, computedHmac.Length);
                    Buffer.BlockCopy(payload, 0, combined, computedHmac.Length, payload.Length);

                    File.WriteAllBytes(_ledgerFilePath, combined);
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"[SMTPLC] Error guardando ledger: {ex.Message}");
                }
            }
        }

        private static byte[] DeriveLocalHmacKey()
        {
            string seed = $"{Environment.MachineName}_SMTPLC_LEDGER_SALT_{Environment.UserName}";
            using var sha = SHA256.Create();
            return sha.ComputeHash(Encoding.UTF8.GetBytes(seed));
        }

        private static string ComputeSha256(string input)
        {
            using var sha = SHA256.Create();
            byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(input ?? ""));
            return Convert.ToHexString(hash);
        }
    }
}
