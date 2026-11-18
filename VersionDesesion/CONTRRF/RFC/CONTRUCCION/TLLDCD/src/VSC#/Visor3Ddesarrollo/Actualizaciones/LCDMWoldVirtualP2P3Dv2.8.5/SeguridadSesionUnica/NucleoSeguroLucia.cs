// =============================================================================
// NucleoSeguroLucia.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Secure Core de LucIA (Implementación de INucleoSeguro)
// =============================================================================

using System;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Seguridad.SesionUnica
{
    // =========================================================================
    // DTOs y Modelos de Diagnóstico
    // =========================================================================

    public sealed class ResultadoInicioNucleo
    {
        public bool Ok { get; init; }
        public string[] Advertencias { get; init; } = Array.Empty<string>();
        public string? ErrorFatal { get; init; }
        public EstadoVerificacionSello EstadoSello { get; init; }
        public bool TpmActivo { get; init; }
        public bool VbsActivo { get; init; }
        public string ModoAntiRollback { get; init; } = "";
    }

    public sealed class DiagnosticoNucleo
    {
        public bool Inicializado { get; init; }
        public EstadoVerificacionSello Estado { get; init; }
        public bool TpmActivo { get; init; }
        public bool VbsDetectado { get; init; }
        public bool DepuradorDetectado { get; init; }
        public int TokenesActivos { get; init; }
        public long UltimoContadorRollback { get; init; }
        public string ModoAntiRollback { get; init; } = "";
        public bool CadenaIntegra { get; init; }
        public int TotalBloquesCadena { get; init; }
        public DateTime UltimaVerificacion { get; init; }
    }

    // =========================================================================
    // NucleoSeguroLucia — Orquestador Principal Zero Trust
    // =========================================================================

    /// <summary>
    /// Punto de entrada del subsistema de seguridad de LucIA.
    ///
    /// Principios de aislamiento:
    ///   - La interfaz gráfica (WPF) y los motores de IA llaman a esta API a través de INucleoSeguro.
    ///   - Ningún modelo de IA ni componente externo tiene acceso directo a AlmacenSeguro,
    ///     GestorClavesTPM, AntiRollbackGuardia ni al material criptográfico en bruto.
    ///   - Toda operación sensible exige un token de sesión emitido por MotorAutorizacion.
    /// </summary>
    public static class NucleoSeguroLucia
    {
        private static volatile bool _inicializado = false;
        private static string? _tokenSesionActivoId = null;
        private static ResultadoRevision? _ultimoResultadoSello = null;
        private static bool _tpmActivo = false;
        private static bool _vbsActivo = false;
        private static DateTime _ultimaVerificacion = DateTime.MinValue;
        private static readonly object _lock = new();

        /// <summary>Instancia compartida que implementa INucleoSeguro para la capa de presentación.</summary>
        public static readonly INucleoSeguro Instancia = new NucleoSeguroInstancia();

        public static bool EstaInicializado => _inicializado;
        public static string? TokenSesionActivo => _tokenSesionActivoId;

        /// <summary>
        /// Inicializa el núcleo seguro en secuencia fail-fast:
        /// 1. Diagnóstico de plataforma (telemetría local como señales de riesgo)
        /// 2. Verificación de sellos duales y matriz de seguridad
        /// 3. Verificación de rollback hardware/local
        /// 4. Detección y preparación de TPM 2.0
        /// 5. Registro auditable con hash chain
        /// </summary>
        public static ResultadoInicioNucleo Inicializar()
        {
            lock (_lock)
            {
                if (_inicializado)
                {
                    return new ResultadoInicioNucleo
                    {
                        Ok = true,
                        Advertencias = new[] { "NucleoSeguroLucia ya se encontraba inicializado." },
                        EstadoSello = _ultimoResultadoSello?.Estado ?? EstadoVerificacionSello.SinSelloNuevoRegistro,
                        TpmActivo = _tpmActivo,
                        VbsActivo = _vbsActivo,
                        ModoAntiRollback = AntiRollbackGuardia.ObtenerModoActivo()
                    };
                }

                var advertencias = new System.Collections.Generic.List<string>();

                try
                {
                    // 0. Endurecimiento de proceso nativo de Windows (DLL Search Order y DEP)
                    EndurecimientoProceso.AplicarMitigaciones();

                    // 1. Diagnóstico de plataforma (señal de riesgo heurística)
                    if (DiagnosticoPlataforma.DepuradorActivo())
                    {
                        AuditoriaSeguridad.Registrar(
                            EventoAuditoria.ErrorCritico,
                            "NucleoSeguroLucia",
                            "Abortado",
                            "Depurador activo detectado durante la inicialización.");

                        return new ResultadoInicioNucleo
                        {
                            Ok = false,
                            ErrorFatal = "Se ha detectado un depurador activo en el sistema. Inicialización denegada por política de seguridad.",
                            EstadoSello = EstadoVerificacionSello.BloqueadoRequiereRecuperacion
                        };
                    }

                    _vbsActivo = DiagnosticoPlataforma.VbsActivoRapido();
                    if (!_vbsActivo)
                    {
                        advertencias.Add("VBS/HVCI no activo. Se recomienda habilitar aislamiento por virtualización.");
                    }

                    // 2. Verificación de sellos y matriz de estados
                    _ultimoResultadoSello = VerificadorSello.EvaluarMatrizSeguridad();
                    _ultimaVerificacion = DateTime.UtcNow;

                    if (_ultimoResultadoSello.Estado == EstadoVerificacionSello.RollbackDetectado)
                    {
                        AuditoriaSeguridad.Registrar(
                            EventoAuditoria.RollbackDetectado,
                            "NucleoSeguroLucia",
                            "Bloqueado",
                            _ultimoResultadoSello.MensajeAuditoria);

                        return new ResultadoInicioNucleo
                        {
                            Ok = false,
                            ErrorFatal = "Detección de rollback en el estado de seguridad. Sistema bloqueado.",
                            EstadoSello = _ultimoResultadoSello.Estado
                        };
                    }

                    if (_ultimoResultadoSello.Estado == EstadoVerificacionSello.CadenaCorrupta)
                    {
                        AuditoriaSeguridad.Registrar(
                            EventoAuditoria.ManipulacionDetectada,
                            "NucleoSeguroLucia",
                            "Bloqueado",
                            _ultimoResultadoSello.MensajeAuditoria);

                        return new ResultadoInicioNucleo
                        {
                            Ok = false,
                            ErrorFatal = "Cadena local corrupta o manipulada. Acceso suspendido.",
                            EstadoSello = _ultimoResultadoSello.Estado
                        };
                    }

                    if (_ultimoResultadoSello.Estado == EstadoVerificacionSello.BloqueadoRequiereRecuperacion)
                    {
                        AuditoriaSeguridad.Registrar(
                            EventoAuditoria.BloqueoCuenta,
                            "NucleoSeguroLucia",
                            "Bloqueado",
                            _ultimoResultadoSello.MensajeAuditoria);

                        advertencias.Add("Equipo bloqueado. Se requiere código de recuperación para restaurar el acceso.");
                    }

                    // 3. TPM 2.0 y Modo Anti-Rollback
                    _tpmActivo = GestorClavesTPM.TpmDisponible();
                    string modoRollback = AntiRollbackGuardia.ObtenerModoActivo();
                    if (!_tpmActivo)
                    {
                        advertencias.Add($"TPM 2.0 no disponible en esta máquina; operando con DPAPI nativo. Anti-Rollback: {modoRollback}.");
                    }

                    // 4. Auditoría inicial
                    AuditoriaSeguridad.Registrar(
                        EventoAuditoria.InicioVerificacion,
                        "NucleoSeguroLucia",
                        "Exito",
                        $"TPM={_tpmActivo}|VBS={_vbsActivo}|Sello={_ultimoResultadoSello.Estado}|RollbackMode={modoRollback}");

                    _inicializado = true;

                    return new ResultadoInicioNucleo
                    {
                        Ok = true,
                        Advertencias = advertencias.ToArray(),
                        EstadoSello = _ultimoResultadoSello.Estado,
                        TpmActivo = _tpmActivo,
                        VbsActivo = _vbsActivo,
                        ModoAntiRollback = modoRollback
                    };
                }
                catch (Exception ex)
                {
                    AuditoriaSeguridad.Registrar(
                        EventoAuditoria.ErrorCritico,
                        "NucleoSeguroLucia",
                        "Fallo",
                        ex.Message);

                    return new ResultadoInicioNucleo
                    {
                        Ok = false,
                        ErrorFatal = $"Error crítico de inicialización: {ex.Message}",
                        EstadoSello = EstadoVerificacionSello.BloqueadoRequiereRecuperacion
                    };
                }
            }
        }

        public static (bool ok, string? tokenId) AutenticarUsuario(string idCuentaHash)
        {
            if (!_inicializado)
            {
                var init = Inicializar();
                if (!init.Ok) return (false, null);
            }

            _ultimoResultadoSello = VerificadorSello.EvaluarMatrizSeguridad();
            _ultimaVerificacion = DateTime.UtcNow;

            if (_ultimoResultadoSello.Estado != EstadoVerificacionSello.Valido &&
                _ultimoResultadoSello.Estado != EstadoVerificacionSello.AutorreparadoDesdeArchivo &&
                _ultimoResultadoSello.Estado != EstadoVerificacionSello.AutorreparadoDesdeRegistro &&
                _ultimoResultadoSello.Estado != EstadoVerificacionSello.CadenaIntegraRequiereConfirmacionRiesgo)
            {
                AuditoriaSeguridad.Registrar(
                    EventoAuditoria.BloqueoCuenta,
                    "NucleoSeguroLucia",
                    "AutenticacionDenegada",
                    $"Estado={_ultimoResultadoSello.Estado} Cuenta={idCuentaHash}");
                return (false, null);
            }

            var token = MotorAutorizacion.EmitirToken(idCuentaHash, _ultimoResultadoSello, TimeSpan.FromHours(8));
            if (token == null)
            {
                return (false, null);
            }

            _tokenSesionActivoId = token.Id;

            AuditoriaSeguridad.Registrar(
                EventoAuditoria.SelloValido,
                "NucleoSeguroLucia",
                "SesionIniciada",
                $"Token={token.Id[..Math.Min(8, token.Id.Length)]}… Cuenta={idCuentaHash}");

            return (true, token.Id);
        }

        public static (bool ok, byte[]? firma) FirmarDatosUsuario(string tokenId, byte[] datos)
        {
            if (!_inicializado || string.IsNullOrWhiteSpace(tokenId) || datos == null)
                return (false, null);

            byte[] nonce = new byte[16];
            RandomNumberGenerator.Fill(nonce);

            var (autorizado, razon) = MotorAutorizacion.AutorizarOperacion(
                tokenId,
                OperacionSegura.FirmarOperacion,
                nonce);

            if (!autorizado)
            {
                AuditoriaSeguridad.Registrar(
                    EventoAuditoria.OperacionIPC,
                    "NucleoSeguroLucia",
                    "FirmaDenegada",
                    razon);
                return (false, null);
            }

            string nombreClave = $"LuciaSecureCore_v1_{Sanitizar(tokenId)}";
            byte[]? firma = GestorClavesTPM.FirmarConClavePermanente(nombreClave, datos);

            if (firma == null)
            {
                byte[] secreto = AlmacenSeguro.ObtenerOcrearSecretoMaestro();
                try
                {
                    using var hmac = new HMACSHA256(secreto);
                    firma = hmac.ComputeHash(datos);
                }
                finally
                {
                    CryptographicOperations.ZeroMemory(secreto);
                }
            }

            return (true, firma);
        }

        public static (bool ok, string? uuid) ObtenerUuidAutenticado(string tokenId)
        {
            if (!_inicializado || string.IsNullOrWhiteSpace(tokenId))
                return (false, null);

            if (!string.Equals(_tokenSesionActivoId, tokenId, StringComparison.Ordinal))
                return (false, null);

            string? uuidSellado = _ultimoResultadoSello?.SelloActivo?.IdCuentaHash;
            return (!string.IsNullOrWhiteSpace(uuidSellado), uuidSellado);
        }

        public static void CerrarSesion(string tokenId)
        {
            if (string.IsNullOrWhiteSpace(tokenId)) return;

            MotorAutorizacion.RevocarToken(tokenId);

            if (string.Equals(_tokenSesionActivoId, tokenId, StringComparison.Ordinal))
            {
                _tokenSesionActivoId = null;
            }

            AuditoriaSeguridad.Registrar(
                EventoAuditoria.OperacionIPC,
                "NucleoSeguroLucia",
                "SesionCerrada",
                $"Token={tokenId[..Math.Min(8, tokenId.Length)]}…");
        }

        public static void Apagar()
        {
            lock (_lock)
            {
                if (_tokenSesionActivoId != null)
                {
                    MotorAutorizacion.RevocarToken(_tokenSesionActivoId);
                    _tokenSesionActivoId = null;
                }

                AuditoriaSeguridad.Registrar(
                    EventoAuditoria.OperacionIPC,
                    "NucleoSeguroLucia",
                    "Apagado",
                    "Cierre ordenado del núcleo de seguridad.");

                _inicializado = false;
            }
        }

        public static ResultadoRevision EvaluarSeguridad()
        {
            _ultimoResultadoSello = VerificadorSello.EvaluarMatrizSeguridad();
            _ultimaVerificacion = DateTime.UtcNow;
            return _ultimoResultadoSello;
        }

        public static ResultadoVerificacionCadena VerificarCadenaLocal()
        {
            byte[] secreto = AlmacenSeguro.ObtenerOcrearSecretoMaestro();
            byte[] huellaBytes = Encoding.UTF8.GetBytes(MaquinaHuellaDigital.Obtener());
            var claveEcdsa = ProveedorClaves.Instancia.ObtenerOCrearClaveEcdsa();
            try
            {
                return VerificadorSello.VerificarCadenaLocal(secreto, huellaBytes, claveEcdsa);
            }
            finally
            {
                CryptographicOperations.ZeroMemory(secreto);
            }
        }

        public static (bool ok, string nuevoCodigoBase32, string mensaje) RecuperarCuentaConCodigo(
            string idCuentaHash,
            string codigoBase32)
        {
            return VerificadorSello.EjecutarRecuperacionNivel3(idCuentaHash, codigoBase32);
        }

        public static async Task IniciarSupervisionAsync(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    await Task.Delay(TimeSpan.FromMinutes(5), ct).ConfigureAwait(false);

                    if (_inicializado)
                    {
                        var res = VerificadorSello.EvaluarMatrizSeguridad();
                        _ultimoResultadoSello = res;
                        _ultimaVerificacion = DateTime.UtcNow;

                        MotorAutorizacion.LimpiarTokensExpirados();

                        if (res.Estado == EstadoVerificacionSello.RollbackDetectado ||
                            res.Estado == EstadoVerificacionSello.BloqueadoRequiereRecuperacion ||
                            res.Estado == EstadoVerificacionSello.CadenaCorrupta)
                        {
                            AuditoriaSeguridad.Registrar(
                                EventoAuditoria.BloqueoCuenta,
                                "NucleoSeguroLucia",
                                "SupervisionAlerta",
                                res.MensajeAuditoria);

                            if (_tokenSesionActivoId != null)
                            {
                                MotorAutorizacion.RevocarToken(_tokenSesionActivoId);
                                _tokenSesionActivoId = null;
                            }
                        }
                    }
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"[NucleoSupervision] Error: {ex.Message}");
                }
            }
        }

        public static DiagnosticoNucleo ObtenerDiagnostico()
        {
            var resCadena = VerificarCadenaLocal();
            return new DiagnosticoNucleo
            {
                Inicializado = _inicializado,
                Estado = _ultimoResultadoSello?.Estado ?? EstadoVerificacionSello.SinSelloNuevoRegistro,
                TpmActivo = _tpmActivo,
                VbsDetectado = _vbsActivo,
                DepuradorDetectado = DiagnosticoPlataforma.DepuradorActivo(),
                TokenesActivos = MotorAutorizacion.TokenesActivosCount,
                UltimoContadorRollback = AntiRollbackGuardia.ObtenerContadorActual(),
                ModoAntiRollback = AntiRollbackGuardia.ObtenerModoActivo(),
                CadenaIntegra = resCadena.Integra,
                TotalBloquesCadena = resCadena.BloquesVerificados,
                UltimaVerificacion = _ultimaVerificacion
            };
        }

        private static string Sanitizar(string entrada)
        {
            if (string.IsNullOrEmpty(entrada)) return "anon";
            var sb = new StringBuilder(Math.Min(entrada.Length, 32));
            foreach (char c in entrada)
            {
                if (char.IsLetterOrDigit(c) || c == '_' || c == '-')
                    sb.Append(c);
            }
            return sb.ToString();
        }
    }

    /// <summary>
    /// Envoltorio de instancia que implementa INucleoSeguro delegando en las operaciones
    /// aisladas del núcleo.
    /// </summary>
    public sealed class NucleoSeguroInstancia : INucleoSeguro
    {
        public bool EstaInicializado => NucleoSeguroLucia.EstaInicializado;
        public string? TokenSesionActivo => NucleoSeguroLucia.TokenSesionActivo;

        public ResultadoInicioNucleo Inicializar() => NucleoSeguroLucia.Inicializar();

        public (bool ok, string? tokenId) AutenticarUsuario(string idCuentaHash) =>
            NucleoSeguroLucia.AutenticarUsuario(idCuentaHash);

        public (bool ok, byte[]? firma) FirmarDatosUsuario(string tokenId, byte[] datos) =>
            NucleoSeguroLucia.FirmarDatosUsuario(tokenId, datos);

        public (bool ok, string? idCuentaHash) ObtenerIdCuentaAutenticado(string tokenId) =>
            NucleoSeguroLucia.ObtenerUuidAutenticado(tokenId);

        public void CerrarSesion(string tokenId) =>
            NucleoSeguroLucia.CerrarSesion(tokenId);

        public void Apagar() => NucleoSeguroLucia.Apagar();

        public DiagnosticoNucleo ObtenerDiagnostico() =>
            NucleoSeguroLucia.ObtenerDiagnostico();

        public ResultadoRevision EvaluarSeguridad() =>
            NucleoSeguroLucia.EvaluarSeguridad();

        public ResultadoVerificacionCadena VerificarCadenaLocal() =>
            NucleoSeguroLucia.VerificarCadenaLocal();

        public (bool ok, string nuevoCodigoBase32, string mensaje) RecuperarCuentaConCodigo(string idCuentaHash, string codigoBase32) =>
            NucleoSeguroLucia.RecuperarCuentaConCodigo(idCuentaHash, codigoBase32);
    }
}
