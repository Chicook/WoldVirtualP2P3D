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

        /// <summary>Disparado cuando el túnel ya tiene URL pública lista.</summary>
        public event Action<string>? UrlTunnelLista;

        /// <summary>Disparado cuando se descubre / conecta un nuevo par.</summary>
        public event Action<string>? NuevoPar;

        public RedP2PServicio(string nombreUsuario, int puertoLocal = 7890)
        {
            Nodo  = new P2PNodo(puertoLocal, nombreUsuario);
            Tunel = new P2PTunnelManager(puertoLocal);

            Tunel.UrlObtenida += url =>
            {
                UrlTunnelLista?.Invoke(url);
            };

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
        /// </summary>
        public async Task<bool> ConectarConParAsync(string urlPar)
        {
            if (string.IsNullOrWhiteSpace(urlPar)) return false;

            bool vivo = await P2PNodo.PingParAsync(urlPar).ConfigureAwait(false);
            if (vivo && UrlPublicaPropia != null)
                await Nodo.AnunciarseAlParAsync(urlPar, UrlPublicaPropia).ConfigureAwait(false);

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
