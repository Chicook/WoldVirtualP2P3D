using System;
using System.Threading.Tasks;

namespace Visor3D.RedP2P
{
    /// <summary>
    /// Coordina el nodo local y el túnel efímero.
    /// Se instancia una sola vez al entrar al mundo 3D y se destruye al cerrar sesión.
    /// </summary>
    public class RedP2PServicio : IDisposable
    {
        private bool _disposed;

        public P2PNodo     Nodo    { get; }
        public P2PTunnelManager Tunel { get; }

        public string? UrlPublicaPropia  => Tunel.UrlPublica;
        public bool    TunnelActivo      => UrlPublicaPropia != null;

        /// <summary>
        /// Credencial de la sesión que el nodo exige para registrar pares
        /// (POST /peer). Traspaso directo a <see cref="P2PNodo.TokenInvitacion"/>:
        /// el visor la fija con la invitación vigente de la sesión (la propia
        /// si abre la sesión; la adoptada del anfitrión raíz si es invitado).
        /// </summary>
        public string TokenInvitacion
        {
            get => Nodo.TokenInvitacion;
            set => Nodo.TokenInvitacion = value;
        }

        /// <summary>Disparado cuando el túnel ya tiene URL pública lista.</summary>
        public event Action<string>? UrlTunnelLista;

        /// <summary>Disparado cuando se descubre / conecta un nuevo par.</summary>
        public event Action<string>? NuevoPar;

        /// <summary>Disparado cuando el túnel se ha caído y va a reconectarse (host afectado).</summary>
        public event Action<string>? TunelCaido;

        /// <summary>Disparado antes de cada reintento de reconexión (intento, segundos de espera).</summary>
        public event Action<int, int>? TunelReintentando;

        public RedP2PServicio(string nombreUsuario, int puertoLocal = ConfigRed.PuertoApiP2P)
        {
            Nodo  = new P2PNodo(puertoLocal, nombreUsuario);
            Tunel = new P2PTunnelManager(puertoLocal);

            Tunel.UrlObtenida += url =>
            {
                UrlTunnelLista?.Invoke(url);
            };

            Tunel.TunnelMuerto += host => TunelCaido?.Invoke(host);
            Tunel.Reintentando += (intento, espera) => TunelReintentando?.Invoke(intento, espera);

            Nodo.NuevoPar += url => NuevoPar?.Invoke(url);
        }

        /// <summary>
        /// Arranca el nodo HTTP local y el túnel SSH.
        /// La URL pública llega más tarde vía <see cref="UrlTunnelLista"/>.
        /// </summary>
        public async Task IniciarAsync()
        {
            await Nodo.IniciarAsync().ConfigureAwait(false);
            await Tunel.IniciarAsync().ConfigureAwait(false);
        }

        /// <summary>
        /// Si el usuario pegó la URL de un amigo, intenta hacer ping y luego anuncio.
        /// El anuncio lleva la invitación de la sesión del amigo
        /// (<paramref name="tokenInvitacion"/>, extraída de su enlace de
        /// invitación) para que su nodo admita el registro; sin ella, un
        /// nodo protegido lo rechazará.
        /// </summary>
        public async Task<bool> ConectarConParAsync(string urlPar, string? tokenInvitacion = null)
        {
            if (string.IsNullOrWhiteSpace(urlPar)) return false;

            bool vivo = await P2PNodo.PingParAsync(urlPar).ConfigureAwait(false);
            if (vivo && UrlPublicaPropia != null)
                await Nodo.AnunciarseAlParAsync(urlPar, UrlPublicaPropia, tokenInvitacion).ConfigureAwait(false);

            return vivo;
        }

        public void Detener()
        {
            Tunel.Detener();
            Nodo.Detener();
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            Detener();
            Tunel.Dispose();
            Nodo.Dispose();
        }
    }
}
