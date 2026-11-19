// =============================================================================
// INucleoSeguro.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Contrato de Aislamiento del Núcleo Seguro de LucIA
// =============================================================================

using System;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Contrato de seguridad desacoplado para el núcleo de LucIA (Zero Trust).
    ///
    /// Principio de diseño:
    ///   - La interfaz gráfica (WPF) y los motores de IA interactúan ÚNICAMENTE a través
    ///     de esta interfaz, sin acceso a claves maestras, DPAPI, TPM ni AlmacenSeguro.
    ///   - Permite una futura extracción transparente del núcleo a un servicio de Windows
    ///     o enclave aislado sin modificar la capa cliente.
    /// </summary>
    public interface INucleoSeguro
    {
        /// <summary>Indica si el núcleo ha completado su secuencia de inicio fail-fast.</summary>
        bool EstaInicializado { get; }

        /// <summary>Identificador opaco del token de sesión activo, o null si no hay sesión.</summary>
        string? TokenSesionActivo { get; }

        /// <summary>Ejecuta la inicialización de seguridad en secuencia fail-fast.</summary>
        ResultadoInicioNucleo Inicializar();

        /// <summary>Autentica al usuario mediante su ID público y emite un token de sesión Zero Trust.</summary>
        (bool ok, string? tokenId) AutenticarUsuario(string idCuentaHash);

        /// <summary>Firma datos utilizando la clave persistente respaldada por hardware/KSP.</summary>
        (bool ok, byte[]? firma) FirmarDatosUsuario(string tokenId, byte[] datos);

        /// <summary>Devuelve el identificador de cuenta vinculado a un token de sesión activo.</summary>
        (bool ok, string? idCuentaHash) ObtenerIdCuentaAutenticado(string tokenId);

        /// <summary>Cierra y revoca un token de sesión activo, purgando secretos en memoria.</summary>
        void CerrarSesion(string tokenId);

        /// <summary>Apagado ordenado del núcleo de seguridad y revocación de todos los tokens.</summary>
        void Apagar();

        /// <summary>Diagnóstico de seguridad sin exposición de claves ni datos sensibles.</summary>
        DiagnosticoNucleo ObtenerDiagnostico();

        /// <summary>Evalúa la matriz de estados de los anclajes y la cadena local.</summary>
        ResultadoRevision EvaluarSeguridad();

        /// <summary>Verifica la integridad de la cadena local de bloques de extremo a extremo.</summary>
        ResultadoVerificacionCadena VerificarCadenaLocal();

        /// <summary>
        /// Ejecuta el flujo de recuperación de nivel 3 mediante código Base32.
        /// Si tiene éxito, rota el código e invalida el bloque anterior.
        /// </summary>
        (bool ok, string nuevoCodigoBase32, string mensaje) RecuperarCuentaConCodigo(string idCuentaHash, string codigoBase32);
    }
}
