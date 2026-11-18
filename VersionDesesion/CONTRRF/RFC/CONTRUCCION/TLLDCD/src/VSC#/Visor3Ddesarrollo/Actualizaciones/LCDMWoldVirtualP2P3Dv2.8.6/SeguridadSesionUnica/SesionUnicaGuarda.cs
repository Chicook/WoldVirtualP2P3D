// =============================================================================
// SesionUnicaGuarda.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Puerta de Entrada y Control de Sesión Única (Zero Trust)
// =============================================================================

using System;
using System.IO;
using System.Windows;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Puerta de enlace entre la interfaz gráfica (WPF) y el subsistema de seguridad Zero Trust.
    ///
    /// Puntos de control en el flujo de usuario:
    ///   1. <see cref="ComprobarAntesDeRegistro"/>: ANTES de abrir la ventana de registro.
    ///   2. <see cref="SellarDespuesDeRegistro"/>: INMEDIATAMENTE después de crear el usuario.
    ///   3. <see cref="ComprobarSesionActivaEnPc"/>: EN EL LOGIN, antes de validar "La Llave".
    /// </summary>
    public static class SesionUnicaGuarda
    {
        // ─────────────────────────────────────────────────────────────────────
        // Punto 1: Comprobar ANTES de abrir el registro
        // ─────────────────────────────────────────────────────────────────────

        public static bool ComprobarAntesDeRegistro(Window? owner = null)
        {
            try
            {
                var revision = NucleoSeguroLucia.Instancia.EvaluarSeguridad();

                if (revision.Estado == EstadoVerificacionSello.SinSelloNuevoRegistro)
                {
                    return true; // Libre para registrar
                }

                if (revision.Estado == EstadoVerificacionSello.Valido ||
                    revision.Estado == EstadoVerificacionSello.AutorreparadoDesdeArchivo ||
                    revision.Estado == EstadoVerificacionSello.AutorreparadoDesdeRegistro ||
                    revision.Estado == EstadoVerificacionSello.CadenaIntegraRequiereConfirmacionRiesgo)
                {
                    string uuid = RegistroPcUnico.ObtenerUuidRegistrado() ?? "(vinculado)";
                    string uuidCorto = uuid[..Math.Min(8, uuid.Length)];

                    MessageBox.Show(
                        owner,
                        "⚠ Este equipo ya cuenta con un usuario registrado en Wold Virtual P2P 3D.\n\n" +
                        "La política del sistema autoriza una única cuenta activa por dispositivo físico.\n\n" +
                        "Si necesitas recuperar tu acceso, utiliza tu código de recuperación.\n\n" +
                        $"Identificador de cuenta: {uuidCorto}…",
                        "Equipo ya registrado — Acceso Bloqueado",
                        MessageBoxButton.OK,
                        MessageBoxImage.Warning);

                    Log($"[SesionUnica] Registro denegado: PC ya vinculado a cuenta {uuidCorto}");
                    return false;
                }

                // Estados de anomalía o bloqueo
                MessageBox.Show(
                    owner,
                    "Se ha detectado una inconsistencia de seguridad en este equipo.\n\n" +
                    "Por motivos de protección, el registro de nuevas cuentas está suspendido.\n\n" +
                    "Si eres el propietario legítimo, utiliza la opción de recuperación de cuenta.",
                    "Verificación de Seguridad Requerida",
                    MessageBoxButton.OK,
                    MessageBoxImage.Error);

                Log($"[SesionUnica] Registro bloqueado: Estado={revision.Estado} — {revision.MensajeAuditoria}");
                return false;
            }
            catch (Exception ex)
            {
                Log($"[SesionUnica] Error crítico en ComprobarAntesDeRegistro: {ex.Message}");
                MessageBox.Show(
                    owner,
                    "No se pudo completar la verificación de seguridad del equipo.\n\n" +
                    "Contacta con soporte técnico si el error persiste.",
                    "Error de Seguridad",
                    MessageBoxButton.OK,
                    MessageBoxImage.Error);

                return false;
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // Punto 2: Sellar DESPUÉS del registro
        // ─────────────────────────────────────────────────────────────────────

        public static bool SellarDespuesDeRegistro(string uuid)
        {
            try
            {
                RegistroPcUnico.RegistrarCuenta(uuid, out string codigoBase32);
                Log($"[SesionUnica] Bloque génesis guardado satisfactoriamente para cuenta {uuid[..Math.Min(8, uuid.Length)]}…");

                // Mostrar al usuario su código de recuperación UNA SOLA VEZ
                MessageBox.Show(
                    null,
                    "🔐 GUARDA ESTE CÓDIGO DE RECUPERACIÓN EN UN LUGAR SEGURO.\n\n" +
                    "No se volverá a mostrar y no se almacena en el equipo:\n\n" +
                    $"{codigoBase32}\n\n" +
                    "Lo necesitarás si alguna vez reinstalas el sistema o cambias de hardware.",
                    "Código de Recuperación de Cuenta — Guardar en Lugar Seguro",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);

                return true;
            }
            catch (InvalidOperationException ex)
            {
                Log($"[SesionUnica] Intento de sobreescritura rechazado: {ex.Message}");
                return false;
            }
            catch (Exception ex)
            {
                Log($"[SesionUnica] Error al sellar cuenta: {ex.Message}");
                return false;
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // Punto 3: Comprobación de seguridad en el LOGIN
        // ─────────────────────────────────────────────────────────────────────

        public static bool ComprobarSesionActivaEnPc(string uuid, Window? owner = null)
        {
            try
            {
                var revision = NucleoSeguroLucia.Instancia.EvaluarSeguridad();

                // Caso sin sello previo: permitir acceso si es cuenta antigua e intentar sellar
                if (revision.Estado == EstadoVerificacionSello.SinSelloNuevoRegistro)
                {
                    if (!string.IsNullOrWhiteSpace(uuid))
                    {
                        try { RegistroPcUnico.RegistrarCuenta(uuid); }
                        catch { /* Ignorar colisiones concurrentes */ }
                    }
                    return true;
                }

                // Caso de anomalía de seguridad: rollback o manipulación detectada
                if (revision.Estado == EstadoVerificacionSello.RollbackDetectado ||
                    revision.Estado == EstadoVerificacionSello.CadenaCorrupta ||
                    revision.Estado == EstadoVerificacionSello.BloqueadoRequiereRecuperacion ||
                    revision.Estado == EstadoVerificacionSello.BloqueadoPorExcesoIntentos)
                {
                    Log($"[SesionUnica] Login denegado por inconsistencia: {revision.Estado} — {revision.MensajeAuditoria}");

                    MessageBox.Show(
                        owner,
                        "🔒 El estado de seguridad de este equipo requiere verificación.\n\n" +
                        "No es posible iniciar sesión hasta completar la recuperación de la identidad local.",
                        "Seguridad del Dispositivo — Acceso Restringido",
                        MessageBoxButton.OK,
                        MessageBoxImage.Stop);

                    return false;
                }

                // Sello activo: comprobar identificador vinculado
                string uuidSellado = revision.SelloActivo?.IdCuentaHash ?? RegistroPcUnico.ObtenerUuidRegistrado() ?? "";

                if (string.IsNullOrWhiteSpace(uuidSellado) || string.IsNullOrWhiteSpace(uuid))
                {
                    return true;
                }

                if (string.Equals(uuidSellado, uuid, StringComparison.OrdinalIgnoreCase) ||
                    uuidSellado.StartsWith(uuid, StringComparison.OrdinalIgnoreCase) ||
                    uuid.StartsWith(uuidSellado, StringComparison.OrdinalIgnoreCase))
                {
                    var (ok, _) = NucleoSeguroLucia.Instancia.AutenticarUsuario(uuid);
                    if (ok)
                    {
                        Log($"[SesionUnica] Sesión autorizada en NucleoSeguroLucia para cuenta {uuid[..Math.Min(8, uuid.Length)]}…");
                    }
                    return true;
                }

                // Usuario diferente en equipo sellado: bloqueo estricto
                string uuidCorto = uuidSellado[..Math.Min(8, uuidSellado.Length)];
                MessageBox.Show(
                    owner,
                    "🔒 Este dispositivo ya está vinculado a otra cuenta en Wold Virtual P2P 3D.\n\n" +
                    "La arquitectura de autocustodia no permite alternar múltiples identidades en este PC.\n\n" +
                    $"Cuenta asociada al equipo: {uuidCorto}…",
                    "Dispositivo en uso — Acceso Bloqueado",
                    MessageBoxButton.OK,
                    MessageBoxImage.Stop);

                Log($"[SesionUnica] Login bloqueado: Intento de cuenta {uuid[..Math.Min(8, uuid.Length)]} en equipo de {uuidCorto}");
                return false;
            }
            catch (Exception ex)
            {
                Log($"[SesionUnica] Error evaluando sesión activa: {ex.Message}");
                return true;
            }
        }

        private static void Log(string mensaje)
        {
            try
            {
                string dir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "WoldVirtualP2P3D");
                Directory.CreateDirectory(dir);

                string logPath = Path.Combine(dir, "sesion_unica.log");
                File.AppendAllText(logPath, $"[{DateTime.UtcNow:yyyy-MM-dd HH:mm:ss}Z] {mensaje}{Environment.NewLine}");
            }
            catch { }
        }
    }
}
