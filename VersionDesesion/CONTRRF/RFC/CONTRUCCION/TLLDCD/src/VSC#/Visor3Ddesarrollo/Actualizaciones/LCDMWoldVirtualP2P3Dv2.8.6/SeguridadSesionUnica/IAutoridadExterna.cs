using System;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Seguridad.SesionUnica
{
    public enum EstadoValidacionExterna
    {
        ValidoOffline,
        ConfirmadoPorAutoridad,
        RechazadoPorAutoridad,
        DispositivoDuplicado,
        ErrorComunicacion
    }

    public sealed record ResultadoValidacionExterna(
        EstadoValidacionExterna Estado,
        string Mensaje,
        long? UltimoContadorConocido = null);

    /// <summary>
    /// Contrato desacoplado para validar el bloque local contra una autoridad
    /// externa o local (por ejemplo, el servidor local descentralizado de LucIA).
    /// </summary>
    public interface IAutoridadExterna
    {
        Task<ResultadoValidacionExterna> ValidarBloqueAsync(
            string cuentaId,
            string bloqueId,
            long contador,
            byte[] huellaComprometida,
            CancellationToken ct = default);

        Task<bool> NotificarActualizacionBloqueAsync(
            string cuentaId,
            long nuevoContador,
            CancellationToken ct = default);
    }
}
