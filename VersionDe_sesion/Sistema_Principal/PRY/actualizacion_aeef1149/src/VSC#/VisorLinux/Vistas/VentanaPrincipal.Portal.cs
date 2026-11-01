using System;
using Avalonia.Controls;
using Visor3D.Linux;

namespace Visor3D.Linux.Vistas
{
    public sealed partial class VentanaPrincipal
    {
        private readonly TextBlock _txtPortalEstado = Interfaz.T("Portal detenido.", 15, Interfaz.Suave, true);
        private readonly TextBlock _txtPortalUrl = Interfaz.Parrafo("—", Interfaz.Acento, 13);
        private readonly TextBlock _txtPortalTunel = Interfaz.Parrafo("—", Interfaz.Suave, 12);
        private readonly TextBlock _txtPortalEnlace = Interfaz.Parrafo("—", Interfaz.Aviso, 12);
        private readonly TextBlock _txtPortalChat = Interfaz.Parrafo("Chat: parado.", Interfaz.Suave, 12);

        private Control ConstruirPortal() => Interfaz.Vertical(
            12,
            Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Portal WebNodo", 17, Interfaz.Texto, true),
                Interfaz.Parrafo(
                    "Servidor de descarga e invitación embebido en el visor. Desde este portal un amigo puede " +
                    "descargar el visor y entrar a tu mundo si viaja por el túnel.", Interfaz.Suave, 12),
                _txtPortalEstado,
                _txtPortalUrl,
                _txtPortalChat,
                Interfaz.Horizontal(
                    10,
                    Interfaz.Boton("Abrir en el navegador", AbrirPortal, principal: true),
                    Interfaz.Boton("Reiniciar portal", ReiniciarPortal)))),

            Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Túnel público", 16, Interfaz.Texto, true),
                Interfaz.Parrafo(
                    "URL efímera que abre tu mundo en internet. Se obtiene al iniciar el nodo P2P (pestaña Red P2P) " +
                    "y cambia en cada sesión.", Interfaz.Suave, 12),
                _txtPortalTunel,
                Interfaz.Horizontal(
                    10,
                    Interfaz.Boton("Copiar URL del túnel", () => Copiar(_portal.PublicTunnelUrl ?? "")),
                    Interfaz.Boton("Ir a Red P2P", () => _pestanas.SelectedIndex = 3)))),

            Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Enlace de invitación", 16, Interfaz.Texto, true),
                Interfaz.Parrafo(
                    "Este enlace lleva el token de la sesión: sin él, el portal rechaza el WebSocket del mundo y del chat. " +
                    "Mándalo sólo a quien quieras invitar.", Interfaz.Suave, 12),
                _txtPortalEnlace,
                Interfaz.Horizontal(
                    10,
                    Interfaz.Boton("Copiar enlace", () => Copiar(EnlaceInvitacion()), principal: true),
                    Interfaz.Boton("Copiar token", () => Copiar(_portal.TokenInvitacion))))));

        private void ActualizarPortal()
        {
            // El visor publica en su propia página el mismo túnel que anuncia el nodo.
            if (_red?.UrlPublicaPropia is string tunel) _portal.PublicTunnelUrl = tunel;

            if (_portal.IsRunning)
            {
                _txtPortalEstado.Text = $"Portal en marcha en el puerto {_portal.ActivePort}.";
                _txtPortalEstado.Foreground = Interfaz.Bien;
                _txtPortalUrl.Text = $"http://localhost:{_portal.ActivePort}/";
            }
            else
            {
                _txtPortalEstado.Text = _portal.StartError == null
                    ? "Portal detenido."
                    : $"Portal no disponible: {_portal.StartError}";
                _txtPortalEstado.Foreground = Interfaz.Mal;
                _txtPortalUrl.Text = "—";
            }

            _txtPortalTunel.Text = string.IsNullOrWhiteSpace(_portal.PublicTunnelUrl)
                ? "Sin túnel activo (el mundo sólo es accesible en la red local)."
                : _portal.PublicTunnelUrl!;

            _txtPortalChat.Text = _portal.ChatEnabled
                ? $"Chat: relay en el puerto {_portal.ChatLocalPort}, enrutado por /chat."
                : "Chat: relay parado.";
            _txtPortalChat.Foreground = _portal.ChatEnabled ? Interfaz.Bien : Interfaz.Suave;

            _txtPortalEnlace.Text = EnlaceInvitacion();
        }

        private string EnlaceInvitacion()
        {
            if (!_portal.IsRunning) return "—";
            string baseUrl = string.IsNullOrWhiteSpace(_portal.PublicTunnelUrl)
                ? $"http://localhost:{_portal.ActivePort}/"
                : _portal.PublicTunnelUrl!.TrimEnd('/') + "/";
            string separador = baseUrl.Contains('?') ? "&" : "?";
            return $"{baseUrl}{separador}invitacion={_portal.TokenInvitacion}";
        }

        private void AbrirPortal()
        {
            if (!_portal.IsRunning)
            {
                _portal.Start();
                ActualizarPortal();
            }

            if (!_portal.IsRunning)
            {
                Estado($"No se pudo abrir el portal: {_portal.StartError}", error: true);
                return;
            }

            AbrirEnNavegador($"http://localhost:{_portal.ActivePort}/");
        }

        private void ReiniciarPortal()
        {
            _portal.Stop();
            _portal.Start();
            ActualizarPortal();
            Estado(_portal.IsRunning
                ? $"Portal reiniciado en el puerto {_portal.ActivePort}."
                : $"No se pudo reiniciar el portal: {_portal.StartError}",
                error: !_portal.IsRunning);
        }
    }
}
