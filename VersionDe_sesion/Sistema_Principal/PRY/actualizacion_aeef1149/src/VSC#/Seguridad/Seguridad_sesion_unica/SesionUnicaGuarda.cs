using System;
using System.IO;
using System.Windows;
using Visor3D.Seguridad.SesionUnica;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Puerta de entrada al subsistema de sesión única.
    /// Protege en TRES puntos del flujo:
    ///
    ///   1. <see cref="ComprobarAntesDeRegistro"/> — en <c>OnCrearCuentaClicked</c>
    ///      (MainWindow), ANTES de abrir <c>RegistroWindow</c>.
    ///
    ///   2. <see cref="SellarDespuesDeRegistro"/> — al final de
    ///      <c>FormularioUsuarioWindow.OnCrearUsuarioClicked</c>.
    ///
    ///   3. <see cref="ComprobarSesionActivaEnPc"/> — en <c>OnLoginClicked</c>
    ///      (MainWindow), justo después de validar credenciales y ANTES de
    ///      solicitar «La Llave». Segunda barrera por si el sello falló al crear.
    /// </summary>
    public static class SesionUnicaGuarda
    {
        // ─────────────────────────────────────────────────────────────────────
        //  Punto 1 — Comprobar ANTES de abrir el formulario de registro
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Comprueba si este PC ya tiene una cuenta registrada (sello en disco).
        /// </summary>
        /// <returns>
        /// <c>true</c>  → sin cuenta previa, puede continuar al registro.<br/>
        /// <c>false</c> → ya existe una cuenta; muestra diálogo y bloquea.
        /// </returns>
        public static bool ComprobarAntesDeRegistro(Window? owner = null)
        {
            try
            {
                if (!RegistroPcUnico.YaExisteCuentaEnEstePc())
                    return true; // libre para registrar

                string uuid = RegistroPcUnico.ObtenerUuidRegistrado() ?? "(desconocido)";

                MessageBox.Show(
                    owner,
                    "⚠ Este equipo ya tiene una cuenta registrada en Wold Virtual P2P 3D.\n\n" +
                    "Solo se permite UNA cuenta por PC.\n\n" +
                    "Si olvidaste tus credenciales, usa la opción\n" +
                    "«Recuperar acceso» con tu frase semilla BIP-39.\n\n" +
                    $"ID de usuario vinculado: {uuid[..Math.Min(8, uuid.Length)]}…",
                    "PC ya registrado — Acceso Bloqueado",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);

                return false;
            }
            catch (Exception ex)
            {
                // Error WMI/IO: por seguridad bloqueamos
                MessageBox.Show(
                    owner,
                    "No se pudo verificar el registro de este equipo.\n\n" +
                    $"Error: {ex.Message}\n\n" +
                    "Contacta con soporte si el problema persiste.",
                    "Error de verificación",
                    MessageBoxButton.OK,
                    MessageBoxImage.Error);

                return false;
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        //  Punto 2 — Sellar DESPUÉS de completar el registro
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Registra el sello de cuenta única en este PC.
        /// Debe llamarse justo después de guardar <c>user_profile.json</c>.
        /// </summary>
        public static bool SellarDespuesDeRegistro(string uuid)
        {
            try
            {
                RegistroPcUnico.RegistrarCuenta(uuid);
                Log($"[SesionUnica] Sello guardado para UUID {uuid[..Math.Min(8, uuid.Length)]}…");
                return true;
            }
            catch (InvalidOperationException ex)
            {
                Log($"[SesionUnica] Intento de doble registro rechazado: {ex.Message}");
                return false;
            }
            catch (Exception ex)
            {
                Log($"[SesionUnica] Error guardando sello: {ex.Message}");
                return false;
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        //  Punto 3 — Segunda barrera en el LOGIN (refuerzo si el sello falló)
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Comprueba en el momento del login si este PC puede iniciar sesión
        /// con el usuario indicado.
        ///
        /// Escenarios:
        ///   • Sin sello → la cuenta es anterior al sistema de sello o el sello
        ///     no se pudo guardar. Se PERMITE el acceso (no rompe cuentas viejas)
        ///     pero se intenta sellar ahora con el uuid obtenido del perfil.
        ///   • Sello del mismo usuario → OK, acceso permitido.
        ///   • Sello de OTRO usuario   → BLOQUEADO: este PC ya está vinculado a
        ///     otra cuenta ("este PC ya está conectado, cierre la sesión anterior").
        /// </summary>
        /// <param name="uuid">
        /// UUID del usuario que intenta iniciar sesión (leído de su perfil local).
        /// Puede ser cadena vacía si no se pudo obtener (en ese caso se omite la
        /// comprobación cruzada por UUID).
        /// </param>
        /// <param name="owner">Ventana propietaria del MessageBox.</param>
        /// <returns>
        /// <c>true</c>  → puede continuar al paso de «La Llave».<br/>
        /// <c>false</c> → bloqueado; el mensaje ya fue mostrado.
        /// </returns>
        public static bool ComprobarSesionActivaEnPc(string uuid, Window? owner = null)
        {
            try
            {
                // Sin sello: permitir acceso (cuenta antigua / sello perdido)
                if (!RegistroPcUnico.YaExisteCuentaEnEstePc())
                {
                    // Intentar sellar en diferido para reforzar la próxima vez
                    if (!string.IsNullOrEmpty(uuid))
                    {
                        try { RegistroPcUnico.RegistrarCuenta(uuid); }
                        catch { /* no forzar: puede que ya haya otro intento */ }
                    }
                    return true;
                }

                // Sello presente: comprobar a qué usuario pertenece
                string uuidSellado = RegistroPcUnico.ObtenerUuidRegistrado() ?? "";

                // Sin UUID en el sello o sin UUID local → permitir (no podemos comparar)
                if (string.IsNullOrEmpty(uuidSellado) || string.IsNullOrEmpty(uuid))
                    return true;

                // Mismo usuario → OK
                if (string.Equals(uuidSellado, uuid, StringComparison.OrdinalIgnoreCase))
                    return true;

                // ─── Usuario diferente: ESTE PC ya está vinculado a otra cuenta ───
                string uuidCorto = uuidSellado[..Math.Min(8, uuidSellado.Length)];
                MessageBox.Show(
                    owner,
                    "🔒 Este equipo ya está vinculado a otra cuenta en Wold Virtual P2P 3D.\n\n" +
                    "No es posible iniciar sesión con una cuenta diferente en este PC.\n\n" +
                    "Si eres el propietario de este equipo, cierra sesión en la cuenta\n" +
                    "activa antes de intentarlo de nuevo.\n\n" +
                    $"Cuenta vinculada al PC: {uuidCorto}…",
                    "PC ya conectado — Acceso Bloqueado",
                    MessageBoxButton.OK,
                    MessageBoxImage.Stop);

                Log($"[SesionUnica] Login bloqueado: intento de cuenta {uuid[..Math.Min(8, uuid.Length)]} en PC sellado para {uuidCorto}");
                return false;
            }
            catch (Exception ex)
            {
                // Error inesperado: registrar pero NO bloquear (no romper logins legítimos)
                Log($"[SesionUnica] Error en ComprobarSesionActivaEnPc: {ex.Message}");
                return true;
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        //  Log auxiliar
        // ─────────────────────────────────────────────────────────────────────
        private static void Log(string mensaje)
        {
            try
            {
                string dir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "WoldVirtualP2P3D");
                Directory.CreateDirectory(dir);
                File.AppendAllText(
                    Path.Combine(dir, "sesion_unica.log"),
                    $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {mensaje}{Environment.NewLine}");
            }
            catch { }
        }
    }
}
