using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Implementación nula para funcionamiento 100 % local y offline sin dependencias externas.
    /// Diseñada para sustituirse por el cliente RPC/Socket del servidor local de LucIA en fases posteriores.
    /// </summary>
    public sealed class AutoridadNula : IAutoridadExterna
    {
        public static readonly AutoridadNula Instancia = new();

        private AutoridadNula() { }

        public Task<ResultadoValidacionExterna> ValidarBloqueAsync(
            string cuentaId,
            string bloqueId,
            long contador,
            byte[] huellaComprometida,
            CancellationToken ct = default)
        {
            // En modo puramente local, la autoridad valida siempre en modo offline
            return Task.FromResult(new ResultadoValidacionExterna(
                EstadoValidacionExterna.ValidoOffline,
                "Validación offline local activa (sin autoridad externa requerida).",
                contador));
        }

        public Task<bool> NotificarActualizacionBloqueAsync(
            string cuentaId,
            long nuevoContador,
            CancellationToken ct = default)
        {
            return Task.FromResult(true);
        }
    }
}
