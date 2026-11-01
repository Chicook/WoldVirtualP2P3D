using System;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Visor3D.RedP2P;
using Visor3D.Services;

namespace Visor3D.Linux.Vistas
{
    public sealed partial class VentanaPrincipal
    {
        private readonly TextBlock _txtRedEstado = Interfaz.T("Nodo P2P detenido.", 15, Interfaz.Suave, true);
        private readonly TextBlock _txtRedTunel = Interfaz.Parrafo("—", Interfaz.Suave, 12);
        private readonly TextBlock _txtRedPares = Interfaz.Parrafo("Sin pares anunciados.", Interfaz.Suave, 12);
        private readonly StackPanel _panelNodos = Interfaz.Vertical(6);
        private TextBox _redManual = null!;
        private bool _buscandoNodos;

        private Control ConstruirRed()
        {
            _redManual = Interfaz.Campo("Enlace del portal o IP:8911 del anfitrión", "", 420);

            var nodo = Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Nodo y túnel", 17, Interfaz.Texto, true),
                Interfaz.Parrafo(
                    "El nodo local publica tu presencia en la LAN y abre un túnel SSH efímero para que tu mundo " +
                    "se pueda alcanzar desde internet. Es lo que permite invitar sin abrir puertos.", Interfaz.Suave, 12),
                _txtRedEstado,
                _txtRedTunel,
                Interfaz.Horizontal(
                    10,
                    Interfaz.Boton("Iniciar nodo y túnel", () => _ = IniciarRedP2PAsync(), principal: true),
                    Interfaz.Boton("Detener", DetenerRedP2P),
                    Interfaz.Boton("Copiar URL pública", () => Copiar(_red?.UrlPublicaPropia ?? "")))));

            var lan = Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Nodos en la red local", 16, Interfaz.Texto, true),
                Interfaz.Parrafo(
                    "Escucha el aviso que difunden otros visores en el puerto 8912 (UDP).",
                    Interfaz.Suave, 12),
                Interfaz.Horizontal(10, Interfaz.Boton("Buscar nodos", () => _ = BuscarNodosLanAsync())),
                _panelNodos));

            var conectar = Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Conectar con un amigo", 16, Interfaz.Texto, true),
                Interfaz.Parrafo(
                    "Pega su enlace de invitación (con token) o su IP local. Se fija como destino y el mundo " +
                    "se abre como invitado desde la pestaña Mundo.", Interfaz.Suave, 12),
                _redManual,
                Interfaz.Horizontal(
                    10,
                    Interfaz.Boton("Fijar como destino", () => UsarNodoComoDestino(_redManual.Text ?? ""), principal: true),
                    Interfaz.Boton("Comprobar nodo", () => _ = ComprobarNodoAsync(_redManual.Text ?? "")))));

            var pares = Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Pares anunciados", 16, Interfaz.Texto, true),
                _txtRedPares));

            return Interfaz.Vertical(12, nodo, lan, conectar, pares);
        }

        private async Task IniciarRedP2PAsync()
        {
            if (_red != null) return;

            if (_nick.Length == 0)
            {
                Estado("Inicia sesión para arrancar el nodo P2P.", error: true);
                return;
            }

            var red = new RedP2PServicio(_nick, 7890);
            red.UrlTunnelLista += url => EnUi(() =>
            {
                _portal.PublicTunnelUrl = url;
                ActualizarPortal();
                ActualizarRedP2P();
                Estado($"Túnel público listo: {url}");
            });
            red.TunelCaido += host => EnUi(() =>
            {
                ActualizarRedP2P();
                Estado($"El túnel «{host}» se ha caído; el nodo reintentará la conexión.", error: true);
            });
            red.TunelReintentando += (intento, espera) => EnUi(() =>
                Estado($"Reintentando túnel (intento {intento}, en {espera} s)…"));
            red.NuevoPar += url => EnUi(() =>
            {
                ActualizarRedP2P();
                Estado($"Nuevo par conectado: {url}");
            });

            _red = red;
            ActualizarRedP2P();
            VisorLog.Info($"[red] Arrancando nodo P2P de «{_nick}» (puerto local 7890).");

            try
            {
                await red.IniciarAsync().ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                VisorLog.Error("[red] No se pudo arrancar el nodo P2P", ex);
                EnUi(() => Estado($"No se pudo arrancar el nodo P2P: {ex.Message}", error: true));
            }
            finally
            {
                EnUi(ActualizarRedP2P);
            }
        }

        private void DetenerRedP2P()
        {
            var red = _red;
            _red = null;
            try { red?.Dispose(); } catch { }
            _portal.PublicTunnelUrl = null;
            EnUi(() =>
            {
                ActualizarRedP2P();
                ActualizarPortal();
            });
            if (red != null) Estado("Nodo P2P detenido.");
        }

        private void ActualizarRedP2P()
        {
            var red = _red;
            if (red == null)
            {
                _txtRedEstado.Text = "Nodo P2P detenido.";
                _txtRedEstado.Foreground = Interfaz.Suave;
                _txtRedTunel.Text = "Sin túnel.";
                _txtRedPares.Text = "Sin pares anunciados.";
                return;
            }

            string? tunel = red.UrlPublicaPropia;
            _txtRedEstado.Text = tunel == null
                ? "Nodo en marcha; esperando túnel público…"
                : "Nodo en marcha con túnel público.";
            _txtRedEstado.Foreground = tunel == null ? Interfaz.Aviso : Interfaz.Bien;
            _txtRedTunel.Text = tunel == null ? "Túnel: pendiente o no disponible." : $"Túnel: {tunel}";

            var pares = red.Nodo.Pares;
            _txtRedPares.Text = pares.Count == 0
                ? "Sin pares anunciados."
                : $"Pares ({pares.Count}):{Environment.NewLine}{string.Join(Environment.NewLine, pares)}";
        }

        private async Task BuscarNodosLanAsync()
        {
            if (_buscandoNodos) return;
            _buscandoNodos = true;

            _panelNodos.Children.Clear();
            _panelNodos.Children.Add(Interfaz.Parrafo("Buscando visores en la red local…"));

            try
            {
                var resultado = await DescubrimientoP2P.BuscarEnLanAsync(1600).ConfigureAwait(false);
                EnUi(() =>
                {
                    _panelNodos.Children.Clear();

                    if (resultado.Error != null)
                    {
                        _panelNodos.Children.Add(Interfaz.Parrafo(resultado.Error, Interfaz.Mal));
                        Estado(resultado.Error, error: true);
                        return;
                    }

                    if (resultado.Nodos.Count == 0)
                    {
                        _panelNodos.Children.Add(Interfaz.Parrafo("No se ha anunciado ningún nodo.", Interfaz.Suave));
                        Estado("No se ha encontrado ningún nodo en la red local.");
                        return;
                    }

                    foreach (string ip in resultado.Nodos.OrderBy(n => n, StringComparer.OrdinalIgnoreCase))
                    {
                        string destino = $"{ip}:{DescubrimientoP2P.PuertoGodot}";
                        _panelNodos.Children.Add(Interfaz.Horizontal(
                            10,
                            Interfaz.T(ip, 13, Interfaz.Texto),
                            Interfaz.Boton("Usar como destino", () => UsarNodoComoDestino(destino))));
                    }

                    Estado($"{resultado.Nodos.Count} nodo(s) encontrado(s) en la red local.");
                });
            }
            catch (Exception ex)
            {
                EnUi(() => Estado($"No se pudo buscar en la LAN: {ex.Message}", error: true));
            }
            finally
            {
                _buscandoNodos = false;
            }
        }

        private async Task ComprobarNodoAsync(string entrada)
        {
            if (string.IsNullOrWhiteSpace(entrada))
            {
                Estado("Escribe un enlace o una dirección para comprobarla.", error: true);
                return;
            }

            Estado($"Comprobando {entrada}…");
            bool vivo = await DescubrimientoP2P.SondearAsync(entrada).ConfigureAwait(false);
            EnUi(() => Estado(vivo
                ? $"El nodo {entrada} responde."
                : $"El nodo {entrada} no responde.", error: !vivo));
        }

        private void UsarNodoComoDestino(string entrada)
        {
            string texto = (entrada ?? "").Trim();
            if (texto.Length == 0)
            {
                Estado("Escribe el enlace o la IP del anfitrión.", error: true);
                return;
            }

            _destino = texto;
            _mundoDestino.Text = texto;
            _redManual.Text = texto;
            _pestanas.SelectedIndex = 1;
            Estado($"Destino fijado: {texto}. Abre el mundo como invitado.");
        }
    }
}
