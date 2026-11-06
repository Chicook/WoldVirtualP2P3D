using System;

namespace Visor3D.RedP2P
{
    /// <summary>
    /// Tabla única de puertos del producto. Todo el C# funcional lee aquí; los
    /// números ya no se repiten por los ficheros. El lado Godot tiene su tabla
    /// espejo en <c>gdscrip/Red.gd</c> (<c>PUERTO_WS</c>, <c>PUERTO_BEACON</c>,
    /// <c>PUERTO_PORTAL_MIN/MAX</c>, <c>PUERTO_API_P2P</c>) y <c>tests/test_config_red.py</c>
    /// falla si las dos tablas dejan de coincidir: es la única forma de que un
    /// literal compartido entre dos lenguajes tenga un dueño verificable sin
    /// fichero de configuración en tiempo de ejecución (un JSON leído por ambos
    /// añadiría un modo de fallo nuevo — ausencia de fichero, export al PCK — y
    /// el C# no puede leer <c>res://</c>).
    /// </summary>
    public static class ConfigRed
    {
        /// WebSocket del motor Godot (TCP). Único canal del mundo: los túneles
        /// HTTP no llevan UDP, así que el ENet 8910 quedó descartado.
        public const int PuertoMotorWs = 8911;

        /// Baliza UDP de autodescubrimiento en LAN que emite el anfitrión y
        /// escucha <c>Red.buscar_host_en_lan</c> / <c>DescubrimientoP2P</c>.
        public const int PuertoBalizaUdp = 8912;

        /// API del nodo P2P local (loopback).
        public const int PuertoApiP2P = 7890;

        /// Portal WebNodo: primer puerto intentado y fin del rango [3030..3040].
        public const int PuertoPortal = 3030;
        public const int PuertoPortalMax = 3040;

        /// Proxy interno del portal: puerto del portal + este desplazamiento.
        public const int DesplazamientoProxyInterno = 100;

        /// Relay de chat en LAN: primer puerto intentado y tamaño del rango.
        public const int PuertoChat = 8920;
        public const int RangoChat = 10;

        /// Los enlaces que reparte el portal apuntan al portal (3030-3040), a la
        /// API P2P (7890) o a HTTP/HTTPS estándar (80/443). Ninguno de esos
        /// puertos escucha el mundo: el tráfico del motor viaja por el WebSocket
        /// de <see cref="PuertoMotorWs"/>, así que la dirección se conserva y el
        /// puerto se reescribe. Regla espejo de <c>Red.parsear_url_host_puerto</c>.
        public static bool EsPuertoReescribibleAlMotor(int puerto)
        {
            return (puerto >= PuertoPortal && puerto <= PuertoPortalMax)
                || puerto == PuertoApiP2P
                || puerto == 80
                || puerto == 443;
        }

        /// Puerto de mundo efectivo para una dirección leída de un enlace:
        /// el del enlace salvo que sea uno de los reescribibles, en cuyo caso
        /// <see cref="PuertoMotorWs"/>.
        public static int PuertoMotorDesde(int puertoLeido)
        {
            if (puertoLeido <= 0 || puertoLeido > 65535)
                return PuertoMotorWs;
            return EsPuertoReescribibleAlMotor(puertoLeido) ? PuertoMotorWs : puertoLeido;
        }

        /// Rango [3030..3040] por el que el portal intenta encajar el listener.
        public static int[] PuertosPortalCandidatos()
        {
            var lista = new int[PuertoPortalMax - PuertoPortal + 1];
            for (int i = 0; i < lista.Length; i++)
                lista[i] = PuertoPortal + i;
            return lista;
        }

        /// <summary>
        /// Destino de mundo a partir de lo que escribe el usuario (enlace del
        /// portal, <c>ip:puerto</c> o URL con esquema). Un único parser para los
        /// dos visores: antes existían tres copias (WPF <c>TryParseConnectionTarget</c>,
        /// Avalonia <c>LanzadorMundo.TryParsearDestino</c> y
        /// <c>Red.parsear_url_host_puerto</c> en Godot) con reglas distintas.
        /// Corta el esquema, quita el camino y reescribe el puerto con
        /// <see cref="PuertoMotorDesde"/>. Devuelve false si no queda host.
        /// </summary>
        public static bool ProbarDestino(string? entrada, out string host, out int puerto)
        {
            host = "";
            puerto = PuertoMotorWs;
            if (string.IsNullOrWhiteSpace(entrada)) return false;

            string s = entrada.Trim().Trim('"', '\'');
            foreach (var esquema in new[] { "https://", "http://", "woldvirtual://", "wss://", "ws://" })
            {
                if (s.StartsWith(esquema, StringComparison.OrdinalIgnoreCase))
                {
                    s = s.Substring(esquema.Length);
                    break;
                }
            }

            int barra = s.IndexOf('/');
            if (barra >= 0) s = s.Substring(0, barra);

            int dosPuntos = s.LastIndexOf(':');
            if (dosPuntos > 0 && dosPuntos < s.Length - 1
                && int.TryParse(s.Substring(dosPuntos + 1), out int puertoLeido))
            {
                puerto = PuertoMotorDesde(puertoLeido);
                s = s.Substring(0, dosPuntos);
            }

            host = s.Trim();
            return host.Length > 0;
        }
    }
}
