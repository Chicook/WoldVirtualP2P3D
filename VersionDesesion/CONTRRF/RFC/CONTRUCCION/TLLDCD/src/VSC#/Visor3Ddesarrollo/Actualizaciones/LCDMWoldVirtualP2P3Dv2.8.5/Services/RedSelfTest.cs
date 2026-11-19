using System;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Threading;

namespace Visor3D.Services
{
    /// <summary>
    /// Autoprueba del descubrimiento P2P (<c>--red-selftest</c>). No necesita el
    /// motor ni el PCK: valida la escucha de la baliza LAN con paquetes inyectados
    /// y la consulta de presencia del portal, incluido que el resto de la API
    /// siga exigiendo token. Devuelve 0 sólo si todo pasa.
    /// </summary>
    public static class RedSelfTest
    {
        public static int Run()
        {
            int fallos = 0;
            var salida = new StringBuilder();

            void Check(string nombre, bool ok, string detalle = "")
            {
                if (!ok) fallos++;
                string linea = $"[{(ok ? "OK" : "FALLO")}] {nombre}" +
                               (string.IsNullOrWhiteSpace(detalle) ? "" : $" — {detalle}");
                salida.AppendLine(linea);
                VisorLog.Info($"[red] {linea}");
            }

            try
            {
                ComprobarDescubrimiento(Check);
                ComprobarPresencia(Check);
            }
            catch (Exception ex)
            {
                Check("Autoprueba de red", false, $"{ex.GetType().Name}: {ex.Message}");
            }

            Cerrar(salida, fallos);
            return fallos == 0 ? 0 : 1;
        }

        /// <summary>
        /// Escucha la baliza y comprueba que detecta un nodo válido e ignora
        /// paquetes ajenos. El paquete se inyecta por loopback desde este equipo.
        /// </summary>
        public static void ComprobarDescubrimiento(Action<string, bool, string> check)
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(8));
            var tarea = DescubrimientoP2P.BuscarEnLanAsync(1500, cts.Token, incluirPropio: true);
            Thread.Sleep(250);

            try
            {
                using var emisor = new System.Net.Sockets.UdpClient(
                    System.Net.Sockets.AddressFamily.InterNetwork);
                byte[] baliza = Encoding.UTF8.GetBytes("WOLDVIRTUAL_HOST_WS_8911");
                emisor.Send(baliza, baliza.Length,
                            new System.Net.IPEndPoint(System.Net.IPAddress.Loopback, DescubrimientoP2P.PuertoBeacon));
                byte[] ajeno = Encoding.UTF8.GetBytes("PAQUETE_AJENO");
                emisor.Send(ajeno, ajeno.Length,
                            new System.Net.IPEndPoint(System.Net.IPAddress.Loopback, DescubrimientoP2P.PuertoBeacon));
            }
            catch (Exception ex)
            {
                check("Baliza de prueba enviada", false, ex.Message);
                return;
            }

            var res = tarea.GetAwaiter().GetResult();
            check("Escucha de baliza UDP 8912", res.Error == null, res.Error ?? $"{res.Nodos.Count} nodo(s)");
            check("Detecta el nodo por la baliza", res.Nodos.Contains("127.0.0.1"), string.Join(",", res.Nodos));
            check("Ignora paquetes ajenos", res.Nodos.Count == 1, $"nodos={res.Nodos.Count}");
        }

        /// <summary>
        /// Levanta un WebNodo y verifica que su presencia es legible sin token
        /// mientras <c>/api/info</c> sigue cerrado.
        /// </summary>
        private static void ComprobarPresencia(Action<string, bool, string> check)
        {
            var nodo = new WebNodoService();
            try
            {
                nodo.Start();
                check("Portal WebNodo escucha", nodo.IsRunning,
                      nodo.IsRunning ? $"http://localhost:{nodo.ActivePort}/" : nodo.StartError ?? "sin detalle");
                if (!nodo.IsRunning) return;

                string baseUrl = $"http://127.0.0.1:{nodo.ActivePort}";
                nodo.PublicTunnelUrl = "https://nodo.invalid";

                bool presencia = DescubrimientoP2P.ConsultarNodoAsync(baseUrl).GetAwaiter().GetResult();
                check("/api/p2p-status sin token (presencia)", presencia, baseUrl);

                using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
                int codigo = (int)http.GetAsync($"{baseUrl}/api/info").GetAwaiter().GetResult().StatusCode;
                check("/api/info sigue exigiendo token", codigo == 403, $"HTTP {codigo}");
            }
            catch (Exception ex)
            {
                check("Presencia del portal", false, $"{ex.GetType().Name}: {ex.Message}");
            }
            finally
            {
                try { nodo.Dispose(); } catch { }
            }
        }

        private static void Cerrar(StringBuilder salida, int fallos)
        {
            string resumen = $"RESULTADO RED: {salida.ToString().Split('\n').Length} líneas, {fallos} fallos";
            salida.AppendLine(resumen);
            Console.WriteLine(salida.ToString());
            try
            {
                string dir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "WoldVirtualP2P3D", "logs");
                Directory.CreateDirectory(dir);
                File.WriteAllText(Path.Combine(dir, "red-selftest.log"), salida.ToString(), Encoding.UTF8);
            }
            catch { }
        }
    }
}
