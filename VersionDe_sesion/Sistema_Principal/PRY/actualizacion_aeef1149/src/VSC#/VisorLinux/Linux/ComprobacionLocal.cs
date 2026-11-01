using System;
using System.Diagnostics;
using System.Net.Http;
using System.Threading.Tasks;
using Visor3D.Seguridad;
using Visor3D.Services;

namespace Visor3D.Linux
{
    /// <summary>
    /// Comprobación sin ventana (<c>woldvirtual-linux --comprobar</c>): rutas del
    /// paquete, estado de la cuenta, portal WebNodo y baliza LAN. No escribe en
    /// el perfil ni lanza el motor; sirve para validar un despliegue.
    /// </summary>
    public static class ComprobacionLocal
    {
        /// <summary>
        /// Extrae motor y mundo del propio visor (<c>--extraer</c>) y escribe sus
        /// rutas en stdout como <c>MOTOR=…</c> y <c>PCK=…</c>. Lo consume
        /// <c>woldvirtual-linux.sh</c> para el modo mundo directo.
        /// </summary>
        public static int Extraer()
        {
            Console.WriteLine($"WoldVirtualP2P3D — visor Linux {RutasLinux.Version}");
            if (!RuntimeLinux.Asegurar(out string? error, aviso => Console.Error.WriteLine(aviso)))
            {
                Console.Error.WriteLine("FALLO  " + error);
                return 1;
            }

            Console.WriteLine($"MOTOR={RuntimeLinux.MotorPath}");
            Console.WriteLine($"PCK={RuntimeLinux.PckPath}");
            return 0;
        }

        public static int Ejecutar()
        {
            int fallos = 0;
            Console.WriteLine($"WoldVirtualP2P3D — visor Linux {RutasLinux.Version}");
            Console.WriteLine($"directorio: {RutasLinux.BaseDir}");
            Console.WriteLine(RutasLinux.Resumen());
            Console.WriteLine();

            if (RutasLinux.MotorExe != null)
                Console.WriteLine($"OK     motor encontrado: {RutasLinux.MotorExe}");
            else if (RuntimeLinux.TieneMotorEmbebido)
                Console.WriteLine("OK     motor embebido en el visor (se extrae al preparar el mundo)");
            else
            {
                Console.WriteLine("FALLO  motor Linux no encontrado");
                fallos++;
            }

            if (RutasLinux.Pck != null)
                Console.WriteLine($"OK     mundo encontrado: {RutasLinux.Pck}");
            else if (RuntimeLinux.TienePckEmbebido)
                Console.WriteLine("OK     mundo embebido en el visor (wvp3d.pck)");
            else
            {
                Console.WriteLine("FALLO  mundo (wvp3d.pck) no encontrado");
                fallos++;
            }

            Console.WriteLine($"runtime: {(RuntimeLinux.Extraido ? "extraído en " + RuntimeLinux.Dir : "sin extraer (" + RuntimeLinux.Dir + ")")}");

            var estado = PerfilUsuario.Diagnosticar(out string motivo);
            Console.WriteLine($"cuenta: {estado} — {motivo}");
            Console.WriteLine($"user:// del motor: {(System.IO.Directory.Exists(RutasLinux.GodotUserDir) ? "existe" : "todavía no creado")}");
            Console.WriteLine();

            using (var portal = new WebNodoService())
            {
                portal.Start();
                if (!portal.IsRunning)
                {
                    Console.WriteLine($"FALLO  portal WebNodo no arrancó: {portal.StartError}");
                    fallos++;
                }
                else
                {
                    Console.WriteLine($"OK     portal WebNodo en http://localhost:{portal.ActivePort}/");
                    if (ConsultarPresencia(portal.ActivePort).GetAwaiter().GetResult())
                        Console.WriteLine("OK     /api/p2p-status responde");
                    else
                    {
                        Console.WriteLine("FALLO  /api/p2p-status no responde");
                        fallos++;
                    }
                }
            }

            var actualizador = new ActualizadorLinux();
            var paquete = actualizador.BuscarAsync(RutasLinux.Version).GetAwaiter().GetResult();
            if (actualizador.UltimoError != null)
                Console.WriteLine($"AVISO  actualizaciones: {actualizador.UltimoError}");
            else if (paquete == null)
                Console.WriteLine("OK     actualizaciones: no hay paquete Linux más reciente");
            else
                Console.WriteLine($"OK     actualizaciones: paquete Linux {paquete.Version} ({paquete.AssetName})");

            var lan = DescubrimientoP2P.BuscarEnLanAsync(1200).GetAwaiter().GetResult();
            if (lan.Error != null)
            {
                Console.WriteLine($"FALLO  baliza LAN: {lan.Error}");
                fallos++;
            }
            else
            {
                Console.WriteLine(lan.Nodos.Count == 0
                    ? "OK     baliza LAN escuchada (sin anfitriones en la red)"
                    : $"OK     baliza LAN: {string.Join(", ", lan.Nodos)}");
            }

            Console.WriteLine();
            Console.WriteLine(fallos == 0 ? "== comprobación correcta ==" : $"== {fallos} fallo(s) ==");
            return fallos == 0 ? 0 : 1;
        }

        private static async Task<bool> ConsultarPresencia(int puerto)
        {
            try
            {
                using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(4) };
                string json = await http.GetStringAsync($"http://localhost:{puerto}/api/p2p-status");
                return json.Contains("\"online\"", StringComparison.Ordinal);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[comprobar] {ex.Message}");
                return false;
            }
        }
    }
}
