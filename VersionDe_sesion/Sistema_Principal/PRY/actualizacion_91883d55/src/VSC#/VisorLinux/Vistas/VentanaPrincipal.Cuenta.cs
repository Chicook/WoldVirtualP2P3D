using System;
using System.Collections.Generic;
using Avalonia.Controls;
using Visor3D.Linux;
using Visor3D.Seguridad;
using Visor3D.Seguridad.SesionUnica;

namespace Visor3D.Linux.Vistas
{
    public sealed partial class VentanaPrincipal
    {
        private readonly ContentControl _hostCuenta = new();
        private TextBox _altaNombre = null!;
        private TextBox _altaPass = null!;
        private TextBox _altaPass2 = null!;
        private TextBox _loginNombre = null!;
        private TextBox _loginPass = null!;
        private readonly TextBlock _txtSemilla = Interfaz.Parrafo("(sin generar)", Interfaz.Suave, 12);

        private Control ConstruirCuenta() => Interfaz.Vertical(
            12,
            Interfaz.Parrafo(
                "La cuenta es local a este equipo y única por PC: se guarda en la carpeta de usuario del visor, " +
                "nunca dentro del mundo 3D. El avatar y el nick del mundo se eligen en el carrusel del motor.",
                Interfaz.Suave, 13),
            _hostCuenta);

        private void RefrescarCuenta()
        {
            if (_dentro)
            {
                _hostCuenta.Content = PanelSesion();
                return;
            }

            var estado = CuentaLinux.Estado(out string motivo);
            _hostCuenta.Content = estado == EstadoCuenta.Completa
                ? PanelAcceso(motivo)
                : PanelAlta(estado, motivo);
        }

        private Control PanelAlta(EstadoCuenta estado, string motivo)
        {
            string nickGodot = CuentaLinux.NickDeGodot();
            _altaNombre = Interfaz.Campo("Nombre de usuario (mínimo 3)", nickGodot);
            _altaPass = Interfaz.Campo("Contraseña (mínimo 6)", contrasena: true);
            _altaPass2 = Interfaz.Campo("Repite la contraseña", contrasena: true);

            var hijos = new List<Control>
            {
                Interfaz.T("Crear la cuenta de este equipo", 17, Interfaz.Texto, true),
                Interfaz.Parrafo(estado == EstadoCuenta.Incompleta
                    ? $"Hay restos de una cuenta sin acceso utilizables ({motivo}). Puedes archivarlos y registrar una cuenta nueva."
                    : "Todavía no hay cuenta en este equipo. Elige nombre y contraseña; el avatar y el nick del mundo se eligen al abrirlo."),
                _altaNombre,
                _altaPass,
                _altaPass2,
                Interfaz.Horizontal(10, Interfaz.Boton("Crear cuenta", CrearCuenta, principal: true)),
            };

            if (!string.IsNullOrWhiteSpace(nickGodot))
                hijos.Insert(2, Interfaz.Parrafo($"El motor ya tiene el nick «{nickGodot}»; se propone ese nombre.", Interfaz.Aviso, 12));

            if (estado == EstadoCuenta.Incompleta)
                hijos.Add(Interfaz.Horizontal(10, Interfaz.Boton("Archivar restos y empezar de cero", ArchivarRestos)));

            return Interfaz.Tarjeta(Interfaz.Vertical(10, hijos.ToArray()));
        }

        private Control PanelAcceso(string motivo)
        {
            _loginNombre = Interfaz.Campo("Nombre de usuario", CuentaLinux.NombreGuardado());
            _loginPass = Interfaz.Campo("Contraseña", contrasena: true);

            var acceso = Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Entrar al mundo", 17, Interfaz.Texto, true),
                Interfaz.Parrafo($"Cuenta local utilizable ({motivo})."),
                _loginNombre,
                _loginPass,
                Interfaz.Horizontal(10, Interfaz.Boton("Entrar", () => Entrar(_loginNombre.Text ?? "", _loginPass.Text ?? ""), principal: true))));

            var semilla = Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Frase semilla de recuperación", 16, Interfaz.Texto, true),
                Interfaz.Parrafo(
                    "12 palabras BIP-39 para guardar fuera del equipo. Quien las tenga puede recuperar el acceso: no las compartas.",
                    Interfaz.Suave, 12),
                _txtSemilla,
                Interfaz.Horizontal(10,
                    Interfaz.Boton("Generar frase", GenerarSemilla),
                    Interfaz.Boton("Copiar", () => Copiar(_txtSemilla.Text ?? "")))));

            var peligro = Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Reiniciar la cuenta local", 16, Interfaz.Mal, true),
                Interfaz.Parrafo(
                    "Archiva perfil, credenciales, sello de equipo y el registro del motor en respaldo_cuenta, y deja el equipo como nuevo. No borra logs ni el mundo.",
                    Interfaz.Suave, 12),
                Interfaz.Horizontal(10, Interfaz.Boton("Reiniciar cuenta (archiva)", ReiniciarCuenta))));

            return Interfaz.Vertical(12, acceso, semilla, peligro);
        }

        private Control PanelSesion() => Interfaz.Tarjeta(Interfaz.Vertical(
            10,
            Interfaz.T("Sesión iniciada", 17, Interfaz.Bien, true),
            Interfaz.Parrafo($"Usuario: {_nick}"),
            Interfaz.Parrafo($"Identidad: {Corto(_uuid)}"),
            Interfaz.Parrafo("El motor abre el mundo en una ventana aparte; esta ventana mantiene el portal, la red P2P y el chat.", Interfaz.Suave, 12),
            Interfaz.Horizontal(
                10,
                Interfaz.Boton("Ir a Mundo", () => _pestanas.SelectedIndex = 1, principal: true),
                Interfaz.Boton("Cerrar sesión", SalirSesion))));

        private void CrearCuenta()
        {
            string nombre = (_altaNombre.Text ?? "").Trim();
            string password = _altaPass.Text ?? "";
            var resultado = CuentaLinux.Crear(nombre, password, _altaPass2.Text ?? "");
            if (!resultado.Ok)
            {
                Estado(resultado.Mensaje, error: true);
                return;
            }

            Estado("Cuenta creada. Iniciando sesión…");
            Entrar(nombre, password);
        }

        private async void ArchivarRestos()
        {
            bool seguir = await Dialogo.PreguntarAsync(
                this, "Archivar restos",
                "Se moverán los restos de la cuenta y el registro del motor a respaldo_cuenta. ¿Continuar?",
                "Archivar");
            if (!seguir) return;

            bool ok = ReinicioCuenta.EjecutarResetTotal(RutasLinux.Version, null, RutasLinux.GodotUserDir);
            Estado(ok ? "Restos archivados. Crea la cuenta nueva." : "No se pudo archivar todo; revisa el diagnóstico.", error: !ok);
            RefrescarCuenta();
        }

        private async void ReiniciarCuenta()
        {
            bool seguir = await Dialogo.PreguntarAsync(
                this, "Reiniciar cuenta",
                "Se archivará la cuenta de este equipo (perfil, credenciales, sello y registro del motor) en respaldo_cuenta " +
                "y el visor volverá al registro completo. ¿Continuar?",
                "Reiniciar");
            if (!seguir) return;

            bool ok = ReinicioCuenta.EjecutarSiProcede(
                "manual-" + DateTime.UtcNow.ToString("yyyyMMddHHmmss"), null, RutasLinux.GodotUserDir);

            _dentro = false;
            _nick = "";
            _uuid = "";
            DetenerChat();
            DetenerRedP2P();
            _txtUsuario.Text = "Sin sesión";
            _txtUsuario.Foreground = Interfaz.Suave;
            _txtSesion.Text = "Crea la cuenta local para entrar al mundo.";
            _txtSesion.Foreground = Interfaz.Suave;

            Estado(ok ? "Cuenta archivada en respaldo_cuenta." : "No se pudo archivar todo; revisa el diagnóstico.", error: !ok);
            RefrescarCuenta();
        }

        private void GenerarSemilla()
        {
            _txtSemilla.Text = CuentaLinux.SemillaNueva();
            _txtSemilla.Foreground = Interfaz.Aviso;
            Estado("Frase semilla generada. Guárdala en papel y no la compartas.");
        }
    }
}
