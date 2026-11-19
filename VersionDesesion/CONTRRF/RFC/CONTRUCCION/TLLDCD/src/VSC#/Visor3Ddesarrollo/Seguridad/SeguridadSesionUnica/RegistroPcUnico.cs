// =============================================================================
// RegistroPcUnico.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Adaptador de Cuenta Única por PC y Cadena Local (v2)
// =============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Adaptador de alto nivel para el registro y consulta de cuenta única por PC (1 bloque = 1 PC).
    ///
    /// Mantiene compatibilidad total con la API previa consumida por MainWindow, FormularioUsuarioWindow
    /// y PerfilUsuario, integrando el modelo de cadena local, separación estricta de dominios
    /// y recuperación de tres niveles.
    /// </summary>
    public static class RegistroPcUnico
    {
        /// <summary>
        /// Comprueba si ya existe una cuenta registrada en este PC.
        /// Devuelve true si el sello o bloque génesis existe y es válido, o si se encuentra en anomalía.
        /// Devuelve false únicamente si el equipo está libre para un registro nuevo (ambos anclajes y cadena ausentes).
        /// </summary>
        public static bool YaExisteCuentaEnEstePc()
        {
            try
            {
                var resultado = VerificadorSello.EvaluarMatrizSeguridad();

                switch (resultado.Estado)
                {
                    case EstadoVerificacionSello.SinSelloNuevoRegistro:
                        return false;

                    case EstadoVerificacionSello.Valido:
                    case EstadoVerificacionSello.AutorreparadoDesdeArchivo:
                    case EstadoVerificacionSello.AutorreparadoDesdeRegistro:
                    case EstadoVerificacionSello.CadenaIntegraRequiereConfirmacionRiesgo:
                        return true;

                    case EstadoVerificacionSello.RollbackDetectado:
                    case EstadoVerificacionSello.BloqueadoRequiereRecuperacion:
                    case EstadoVerificacionSello.BloqueadoPorExcesoIntentos:
                    case EstadoVerificacionSello.CadenaCorrupta:
                        // En cualquier estado anómalo o de bloqueo se impide crear una nueva cuenta
                        return true;

                    default:
                        return true;
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[RegistroPcUnico] Error evaluando estado: {ex.Message}");
                return true;
            }
        }

        /// <summary>
        /// Registra la cuenta recién creada en este PC (modelo 1 bloque = 1 usuario).
        /// </summary>
        /// <param name="uuid">UUID único del usuario recién creado.</param>
        public static void RegistrarCuenta(string uuid)
        {
            RegistrarCuenta(uuid, out _);
        }

        /// <summary>
        /// Registra la cuenta recién creada generando el bloque génesis en la cadena local
        /// y entregando el código de recuperación en Base32 con checksum (para mostrar una sola vez).
        /// </summary>
        public static void RegistrarCuenta(string uuid, out string codigoRecuperacionBase32)
        {
            if (string.IsNullOrWhiteSpace(uuid))
                throw new ArgumentException("El UUID de cuenta no puede ser nulo o vacío.", nameof(uuid));

            if (YaExisteCuentaEnEstePc())
                throw new InvalidOperationException("Ya existe una cuenta registrada en este equipo.");

            byte[] secretoMaestro = AlmacenSeguro.ObtenerOcrearSecretoMaestro();
            byte[] huellaBytes = MaquinaHuellaDigital.ObtenerBytes();

            try
            {
                // Derivar idCuentaHash estable a partir del uuid con separación de dominios
                byte[] uuidBytes = Encoding.UTF8.GetBytes(uuid);
                byte[] domBytes = Encoding.UTF8.GetBytes(SelloCuenta.DominioCuentaId);
                byte[] payloadId = new byte[domBytes.Length + uuidBytes.Length];
                Buffer.BlockCopy(domBytes, 0, payloadId, 0, domBytes.Length);
                Buffer.BlockCopy(uuidBytes, 0, payloadId, domBytes.Length, uuidBytes.Length);
                using var sha = SHA256.Create();
                string idCuentaHash = Convert.ToHexString(sha.ComputeHash(payloadId)).ToLowerInvariant();

                // Generar código de recuperación de 32 bytes y sal de 32 bytes
                SelloCuenta.GenerarNuevoParRecuperacion(
                    out byte[] rawCode,
                    out string saltHex,
                    out string compromisoHex,
                    out codigoRecuperacionBase32);

                CryptographicOperations.ZeroMemory(rawCode);

                long ultimoContador = AlmacenSeguro.LeerUltimoContadorRegistro();
                long nuevoContador = Math.Max(1, ultimoContador + 1);

                var hwLista = MaquinaHuellaDigital.ObtenerComponentes().ObtenerLista();

                var claveEcdsa = ProveedorClaves.Instancia.ObtenerOCrearClaveEcdsa();

                var nuevoBloque = new SelloCuenta
                {
                    VersionFormato = SelloCuenta.VersionActual,
                    IdCuentaHash = idCuentaHash,
                    Indice = 0,
                    HashPrevio = new string('0', 64),
                    Contador = nuevoContador,
                    TimestampUtc = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
                    HuellaAnonimizada = MaquinaHuellaDigital.Obtener(),
                    Salt = saltHex,
                    CompromisoRecuperacion = compromisoHex,
                    KeyId = "k1_ecdsa_p256",
                    ComponentesHardware = new List<string>(hwLista),
                    Nota = "Bloque Génesis 1:1 — WoldVirtualP2P3D Zero Trust v3"
                };

                // Guardar en anclajes duales y cadena local append-only con firma ECDSA v3
                AlmacenSeguro.GuardarDualV3(nuevoBloque, claveEcdsa, huellaBytes);

                // Incrementar contador en guardia anti-rollback
                AntiRollbackGuardia.IncrementarContador(nuevoContador, secretoMaestro);

                AuditoriaSeguridad.Registrar(
                    EventoAuditoria.NuevoRegistro,
                    "RegistroPcUnico",
                    "BloqueGénesisCreado",
                    $"IdCuenta={idCuentaHash[..Math.Min(8, idCuentaHash.Length)]}… Contador={nuevoContador}");
            }
            finally
            {
                CryptographicOperations.ZeroMemory(secretoMaestro);
            }
        }

        /// <summary>
        /// Devuelve el identificador de cuenta guardado en el bloque activo, o null si no hay sello legible.
        /// </summary>
        public static string? ObtenerUuidRegistrado()
        {
            try
            {
                var revision = VerificadorSello.EvaluarMatrizSeguridad();
                if (revision.SelloActivo != null && !string.IsNullOrWhiteSpace(revision.SelloActivo.IdCuentaHash))
                {
                    return revision.SelloActivo.IdCuentaHash;
                }

                string? jsonArchivo = AlmacenSeguro.LeerAnclajeArchivo();
                if (!string.IsNullOrWhiteSpace(jsonArchivo))
                {
                    var sello = SelloCuenta.Deserializar(jsonArchivo);
                    return sello?.IdCuentaHash;
                }

                string? jsonRegistro = AlmacenSeguro.LeerAnclajeRegistro();
                if (!string.IsNullOrWhiteSpace(jsonRegistro))
                {
                    var sello = SelloCuenta.Deserializar(jsonRegistro);
                    return sello?.IdCuentaHash;
                }

                return null;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        /// Elimina los anclajes y la cadena local del PC actual.
        /// Solo debe usarse en escenarios administrados de reinicio limpio o soporte técnico.
        /// </summary>
        public static void EliminarSello()
        {
            AlmacenSeguro.EliminarAnclajesParaSoporte();
            AuditoriaSeguridad.Registrar(
                EventoAuditoria.OperacionIPC,
                "RegistroPcUnico",
                "SelloEliminado",
                "Anclajes duales y cadena purgados por soporte.");
        }

        /// <summary>
        /// Devuelve la huella digital hardware del equipo actual (HKDF SHA-256 en hex).
        /// </summary>
        public static string Obtener() => MaquinaHuellaDigital.Obtener();
    }
}
