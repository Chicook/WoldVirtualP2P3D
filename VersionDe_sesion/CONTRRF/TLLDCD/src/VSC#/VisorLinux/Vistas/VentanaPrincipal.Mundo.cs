using System;
using System.Collections.Generic;
using System.IO;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.Primitives;
using Avalonia.Layout;
using Avalonia.Media;
using Visor3D.Linux;

namespace Visor3D.Linux.Vistas
{
    public sealed partial class VentanaPrincipal
    {
        private readonly TextBlock _txtMundoEstado = Interfaz.T("Motor detenido.", 15, Interfaz.Suave, true);
        private readonly TextBlock _txtMundoRutas = Interfaz.Parrafo("—", Interfaz.Suave, 12);
        private readonly TextBlock _txtConsolaMotor = new()
        {
            FontFamily = new FontFamily("Consolas, DejaVu Sans Mono, monospace"),
            FontSize = 12,
            Foreground = Interfaz.Suave,
            TextWrapping = TextWrapping.Wrap,
        };
        private readonly List<string> _consolaMotor = new();
        private TextBox _mundoDestino = null!;
        private bool _preparandoMotor;

        private Control ConstruirMundo()
        {
            _mundoDestino = Interfaz.Campo("Enlace del anfitrión o IP:8911 (vacío = abrir tu propio mundo)", _destino, 560);

            var motor = Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Motor 3D", 17, Interfaz.Texto, true),
                _txtMundoEstado,
                _txtMundoRutas,
                Interfaz.Parrafo(
                    "El motor (Godot 4.7.2) y el mundo viajan dentro del visor y se extraen la primera vez " +
                    "(≈1,2 GB). Se abren en su propia ventana: anfitrión = mundo propio y túnel; " +
                    "invitado = entra al mundo de quien te pasó el enlace.", Interfaz.Suave, 12),
                Interfaz.Horizontal(
                    10,
                    Interfaz.Boton("Abrir como anfitrión", LanzarComoAnfitrion, principal: true),
                    Interfaz.Boton("Abrir como invitado", LanzarComoInvitado),
                    Interfaz.Boton("Preparar mundo 3D", () => _ = PrepararMotorAsync()),
                    Interfaz.Boton("Detener motor", DetenerMotor))));

            var destino = Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Destino del invitado", 16, Interfaz.Texto, true),
                Interfaz.Parrafo(
                    "Pega el enlace de invitación que te dio el anfitrión (lleva el token) o su IP en la red local. " +
                    "La pestaña Red P2P también puede rellenarlo.", Interfaz.Suave, 12),
                _mundoDestino,
                Interfaz.Horizontal(
                    10,
                    Interfaz.Boton("Usar como destino", FijarDestinoManual),
                    Interfaz.Boton("Limpiar", () => { _mundoDestino.Text = ""; _destino = ""; }))));

            var consola = Interfaz.Tarjeta(Interfaz.Vertical(
                8,
                Interfaz.T("Registro del motor", 16, Interfaz.Texto, true),
                new ScrollViewer
                {
                    Height = 200,
                    Content = _txtConsolaMotor,
                    HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
                },
                Interfaz.Horizontal(10, Interfaz.Boton("Vaciar registro", VaciarConsolaMotor))));

            return Interfaz.Vertical(12, motor, destino, consola);
        }

        private void ActualizarEstadoMotor()
        {
            string? problema = LanzadorMundo.MotivoNoDisponible();
            string motor = RutasLinux.MotorExe
                ?? (RuntimeLinux.TieneMotorEmbebido ? "embebido (se extrae al preparar el mundo)" : "(no encontrado)");
            string mundo = RutasLinux.Pck
                ?? (RuntimeLinux.TienePckEmbebido ? "embebido (se extrae al preparar el mundo)" : "(no encontrado)");
            _txtMundoRutas.Text =
                $"Motor: {motor}\n" +
                $"Mundo: {mundo}\n" +
                $"Datos del motor: {RutasLinux.GodotUserDir}";

            if (_motor.EnEjecucion)
            {
                _txtMundoEstado.Text = $"Motor en ejecución (PID {_motor.IdProceso}).";
                _txtMundoEstado.Foreground = Interfaz.Bien;
            }
            else if (_preparandoMotor)
            {
                _txtMundoEstado.Text = "Extrayendo el motor y el mundo del visor (≈1,2 GB)…";
                _txtMundoEstado.Foreground = Interfaz.Suave;
            }
            else if (problema != null)
            {
                _txtMundoEstado.Text = problema;
                _txtMundoEstado.Foreground = Interfaz.Mal;
            }
            else if (!RuntimeLinux.Extraido && RuntimeLinux.TieneMotorEmbebido)
            {
                _txtMundoEstado.Text = "Motor y mundo listos para extraer (≈1,2 GB la primera vez).";
                _txtMundoEstado.Foreground = Interfaz.Suave;
            }
            else
            {
                _txtMundoEstado.Text = "Motor detenido.";
                _txtMundoEstado.Foreground = Interfaz.Suave;
            }
        }

        /// <summary>
        /// Deja delante el motor y el mundo. Si vienen dentro del visor y todavía
        /// no están en disco, los extrae fuera del hilo de interfaz.
        /// </summary>
        private async System.Threading.Tasks.Task<bool> PrepararMotorAsync()
        {
            if (RuntimeLinux.Extraido) return true;
            if (!RuntimeLinux.TieneMotorEmbebido || !RuntimeLinux.TienePckEmbebido) return true;
            if (_preparandoMotor) return false;

            _preparandoMotor = true;
            ActualizarEstadoMotor();
            Estado("Extrayendo el motor y el mundo del visor (≈1,2 GB)…");

            string? error = null;
            await System.Threading.Tasks.Task.Run(() => RuntimeLinux.Asegurar(out error));

            _preparandoMotor = false;
            ActualizarEstadoMotor();
            if (error != null)
            {
                Estado("No se pudo preparar el mundo 3D: " + error, error: true);
                AnadirConsolaMotor("[visor] " + error);
                return false;
            }

            Estado($"Mundo 3D preparado en {RuntimeLinux.Dir}");
            return true;
        }

        private void AnadirConsolaMotor(string linea)
        {
            _consolaMotor.Add(linea);
            if (_consolaMotor.Count > 400) _consolaMotor.RemoveRange(0, _consolaMotor.Count - 400);
            _txtConsolaMotor.Text = string.Join(Environment.NewLine, _consolaMotor);
        }

        private void VaciarConsolaMotor()
        {
            _consolaMotor.Clear();
            _txtConsolaMotor.Text = "";
        }

        private void FijarDestinoManual()
        {
            string texto = (_mundoDestino.Text ?? "").Trim();
            if (texto.Length == 0 || !LanzadorMundo.TryParsearDestino(texto, out _, out _))
            {
                Estado("Escribe un enlace o una dirección válida (p. ej. 192.168.1.20:8911).", error: true);
                return;
            }

            _destino = texto;
            Estado($"Destino fijado: {texto}");
        }

        private bool PrepararSesion()
        {
            if (!_dentro)
            {
                Estado("Inicia sesión en la pestaña Cuenta antes de abrir el mundo.", error: true);
                _pestanas.SelectedIndex = 0;
                return false;
            }

            if (_portal.IsRunning) return true;

            _portal.Start();
            ActualizarPortal();
            if (_portal.IsRunning) return true;

            Estado($"El portal no está disponible ({_portal.StartError}); se abre el mundo sin invitación.", error: true);
            return true;
        }

        private async void LanzarComoAnfitrion()
        {
            if (!PrepararSesion()) return;
            if (!await PrepararMotorAsync()) return;

            if (_motor.Lanzar(_nick, null, _portal.TokenInvitacion, _portal.PublicTunnelUrl))
                Estado("Mundo abierto como anfitrión. Comparte el enlace de la pestaña Portal.");
            else
                Estado("No se pudo abrir el motor; mira el registro del motor.", error: true);

            ActualizarEstadoMotor();
        }

        private async void LanzarComoInvitado()
        {
            if (!PrepararSesion()) return;

            string texto = (_mundoDestino.Text ?? _destino ?? "").Trim();
            if (!LanzadorMundo.TryParsearDestino(texto, out string host, out int puerto))
            {
                Estado("Escribe el enlace de invitación o la IP del anfitrión antes de entrar como invitado.", error: true);
                return;
            }

            if (!await PrepararMotorAsync()) return;

            _destino = texto;
            string token = LanzadorMundo.ExtraerInvitacion(texto);
            if (token.Length == 0 && _portal.PublicTunnelUrl != null && !texto.Contains("://", StringComparison.Ordinal))
                token = _portal.TokenInvitacion;

            if (_motor.Lanzar(_nick, texto, token, _portal.PublicTunnelUrl))
                Estado($"Entrando al mundo de {host}:{puerto}.");
            else
                Estado("No se pudo abrir el motor; mira el registro del motor.", error: true);

            ActualizarEstadoMotor();
        }

        private void DetenerMotor()
        {
            if (!_motor.EnEjecucion)
            {
                Estado("El motor ya estaba detenido.");
                return;
            }

            _motor.Detener();
            Estado("Motor detenido.");
            ActualizarEstadoMotor();
        }
    }
}
