using System;
using System.Diagnostics;
using System.IO;

namespace Visor3D.RedP2P
{
    /// <summary>
    /// Persiste en disco el PID del proceso del túnel efímero y elimina los restos
    /// (procesos huérfanos) de ejecuciones anteriores.
    ///
    /// Motivación: el visor se distribuye como un único .exe. Si el usuario lo finaliza
    /// desde el Administrador de tareas, o el sistema lo mata, el evento de cierre nunca
    /// se ejecuta y los procesos hijos del túnel (<c>ssh.exe</c> / <c>cloudflared.exe</c>)
    /// quedan vivos: el puerto local sigue ocupado y el túnel público permanece activo en
    /// segundo plano. Al persistir el PID y validar el nombre del proceso y su hora de
    /// arranque, podemos matar exactamente ese proceso en el siguiente arranque sin riesgo
    /// de matar un proceso ajeno que hubiera reciclado el mismo PID.
    ///
    /// Se usa un "<c>slot</c>" por túnel para poder gestionar varios a la vez
    /// (p. ej. "p2p" para la API P2P y "webnodo" para el portal del metaverso).
    /// </summary>
    internal static class TunnelProcessRegistry
    {
        private static readonly string Carpeta = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WoldVirtualP2P3D");

        private static string Archivo(string slot)
        {
            try { Directory.CreateDirectory(Carpeta); } catch { }
            return Path.Combine(Carpeta, $"tunnel-{slot}.pid");
        }

        /// <summary>Registra el PID y su hora de arranque para poder validarlo más adelante.</summary>
        public static void Persistir(string slot, int pid)
        {
            try
            {
                long ticks = 0;
                try { ticks = Process.GetProcessById(pid).StartTime.ToUniversalTime().Ticks; } catch { }
                File.WriteAllText(Archivo(slot), $"{pid}|{ticks}");
            }
            catch { }
        }

        /// <summary>Olvida el PID registrado (tras un cierre limpio).</summary>
        public static void Olvidar(string slot)
        {
            try
            {
                string ruta = Archivo(slot);
                if (File.Exists(ruta)) File.Delete(ruta);
            }
            catch { }
        }

        /// <summary>
        /// Mata el proceso de túnel dejado por una ejecución anterior, validando que sea
        /// realmente un proceso de túnel (ssh/cloudflared) y que la hora de arranque
        /// coincida, para no matar un proceso ajeno con el PID reciclado.
        /// </summary>
        public static void BarrerHuerfano(string slot)
        {
            try
            {
                string ruta = Archivo(slot);
                if (!File.Exists(ruta)) return;

                string txt = File.ReadAllText(ruta).Trim();
                Olvidar(slot);

                var partes = txt.Split('|');
                if (partes.Length < 1 || !int.TryParse(partes[0], out int pid)) return;

                Process viejo;
                try { viejo = Process.GetProcessById(pid); }
                catch { return; }   // el proceso ya no existe

                string nombre = viejo.ProcessName.ToLowerInvariant();
                bool esTunel = nombre.Contains("ssh") || nombre.Contains("cloudflared");
                if (!esTunel) return;

                if (partes.Length >= 2 && long.TryParse(partes[1], out long ticks) && ticks > 0)
                {
                    long real = viejo.StartTime.ToUniversalTime().Ticks;
                    if (Math.Abs(real - ticks) > TimeSpan.FromSeconds(5).Ticks) return; // PID reciclado
                }

                viejo.Kill(entireProcessTree: true);
                Debug.WriteLine($"[Túnel] Proceso huérfano '{nombre}' (PID {pid}) eliminado al arrancar.");
            }
            catch { }
        }

        /// <summary>Mata un proceso de túnel de forma defensiva, lo libera y olvida su PID.</summary>
        public static void MatarYOlvidar(string slot, Process? proc)
        {
            try
            {
                if (proc != null && !proc.HasExited)
                    proc.Kill(entireProcessTree: true);
            }
            catch { }
            try { proc?.Dispose(); } catch { }
            Olvidar(slot);
        }
    }
}
