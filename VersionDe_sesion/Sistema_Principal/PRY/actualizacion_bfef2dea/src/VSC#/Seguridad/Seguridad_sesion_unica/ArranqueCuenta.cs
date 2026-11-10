using Visor3D.Seguridad;
using Visor3D.Services;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Deja el equipo listo para el ciclo de registro completo (bienvenida →
    /// crear cuenta → carrusel → nick) cuando no tiene una cuenta utilizable:
    /// restos de una instalación a medias o una carpeta de datos copiada de
    /// otro PC. Nunca toca una cuenta con credenciales válidas.
    /// </summary>
    public static class ArranqueCuenta
    {
        public static void AsegurarCicloRegistro(string? baseDir = null, string? godotDir = null)
        {
            var estado = PerfilUsuario.Diagnosticar(out string motivo, baseDir);

            switch (estado)
            {
                case EstadoCuenta.Completa:
                    VisorLog.Info($"[cuenta] Cuenta local utilizable ({motivo}); se mantiene el acceso.");
                    return;

                case EstadoCuenta.SinIdentidad:
                    bool archivado = ReinicioCuenta.LimpiarEstadoGodot("sin-cuenta", baseDir, godotDir);
                    VisorLog.Info(archivado
                        ? "[cuenta] Equipo sin cuenta: estado del motor archivado; arranca el ciclo de registro completo."
                        : "[cuenta] Equipo sin cuenta: arranca el ciclo de registro completo.");
                    return;

                default:
                    string marca = "auto-incompleta-" + System.DateTime.UtcNow.ToString("yyyyMMddHHmmss");
                    bool reiniciada = ReinicioCuenta.EjecutarSiProcede(marca, baseDir, godotDir);
                    VisorLog.Info(reiniciada
                        ? $"[cuenta] Identidad incompleta ({motivo}); archivada en respaldo_cuenta y ciclo de registro reiniciado."
                        : $"[cuenta] Identidad incompleta ({motivo}); no se pudo archivar del todo, se reintentará al próximo arranque.");
                    return;
            }
        }
    }
}
