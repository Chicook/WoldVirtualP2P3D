using System;
using System.IO;
using Visor3D.Seguridad;

namespace Visor3D.Services
{
    /// <summary>
    /// Una sola ventana por instalación en Linux, mediante un fichero de bloqueo
    /// exclusivo. La segunda ejecución sale sin tocar nada; la sesión sigue en
    /// la ventana que ya estaba abierta.
    /// </summary>
    internal static class InstanciaUnica
    {
        private static FileStream? _bloqueo;

        public static bool EsPrimeraInstancia()
        {
            try
            {
                Directory.CreateDirectory(PerfilUsuario.BaseDir);
                _bloqueo = new FileStream(
                    Path.Combine(PerfilUsuario.BaseDir, "visor.lock"),
                    FileMode.OpenOrCreate,
                    FileAccess.ReadWrite,
                    FileShare.None);
                _bloqueo.SetLength(0);
                _bloqueo.Write(System.Text.Encoding.UTF8.GetBytes(Environment.ProcessId.ToString()));
                _bloqueo.Flush();
                return true;
            }
            catch (IOException)
            {
                return false;
            }
            catch (UnauthorizedAccessException)
            {
                // Sin permiso para el fichero: no se bloquea al usuario por esto.
                return true;
            }
        }

        /// <summary>
        /// Linux no ofrece una API portable para subir la ventana de otro
        /// proceso; se deja constancia y se cierra esta ejecución.
        /// </summary>
        public static void EnfocarInstanciaExistente()
        {
            VisorLog.Info("[visor] Ya hay una instancia abierta; esta ejecución termina sin abrir otra ventana.");
        }
    }
}
