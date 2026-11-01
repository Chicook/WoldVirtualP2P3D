using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Avalonia.Controls.Primitives;
using Avalonia.Layout;
using Visor3D.Chat;
using Visor3D.Linux;
using Visor3D.Services;

namespace Visor3D.Linux.Vistas
{
    public sealed partial class VentanaPrincipal
    {
        private readonly StackPanel _chatMensajes = Interfaz.Vertical(4);
        private readonly ScrollViewer _chatScroll = new()
        {
            Height = 260,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
        };
        private readonly TextBlock _txtChatEstado = Interfaz.T("Chat desconectado.", 14, Interfaz.Suave, true);
        private readonly TextBlock _txtMiCodigo = Interfaz.T("—", 16, Interfaz.Acento, true);
        private readonly TextBlock _txtPrivado = Interfaz.Parrafo("Mensajes para todos los presentes.", Interfaz.Suave, 12);
        private readonly StackPanel _panelPresentes = Interfaz.Vertical(3);
        private readonly StackPanel _panelAmigos = Interfaz.Vertical(3);
        private readonly StackPanel _panelSolicitudes = Interfaz.Vertical(3);
        private readonly Dictionary<int, string> _presentes = new();
        private readonly Dictionary<int, bool> _estadoPares = new();

        private TextBox _chatEntrada = null!;
        private TextBox _chatCodigoAmigo = null!;
        private bool _chatConectando;
        private DateTime _chatProximoIntento = DateTime.MinValue;
        private string _chatPrivadoUid = "";
        private string _chatPrivadoNombre = "";

        private Control ConstruirChat()
        {
            _chatEntrada = Interfaz.Campo("Escribe un mensaje…", "", 560);
            _chatCodigoAmigo = Interfaz.Campo("Código de amigo (WPV-…)", "", 300);

            _chatScroll.Content = _chatMensajes;

            var sesion = Interfaz.Tarjeta(Interfaz.Vertical(
                8,
                Interfaz.T("Chat del metaverso", 17, Interfaz.Texto, true),
                Interfaz.Parrafo(
                    "Texto entre los visores conectados al mismo mundo. El anfitrión retransmite a través del " +
                    "túnel, así que no hace falta abrir puertos. Voz y webcam no están disponibles en Linux.",
                    Interfaz.Suave, 12),
                _txtChatEstado,
                Interfaz.Horizontal(10,
                    Interfaz.T("Tu código:", 13, Interfaz.Suave),
                    _txtMiCodigo,
                    Interfaz.Boton("Copiar", () => Copiar(ChatProtocol.BuildFriendCode(_uuid)))),
                _panelPresentes));

            var mensajes = Interfaz.Tarjeta(Interfaz.Vertical(
                8,
                _chatScroll,
                _txtPrivado,
                Interfaz.Horizontal(10,
                    _chatEntrada,
                    Interfaz.Boton("Enviar", EnviarMensaje, principal: true),
                    Interfaz.Boton("Volver a todos", () =>
                    {
                        _chatPrivadoUid = "";
                        _chatPrivadoNombre = "";
                        _txtPrivado.Text = "Mensajes para todos los presentes.";
                        _txtPrivado.Foreground = Interfaz.Suave;
                        RefrescarAmigos();
                    }))));

            var amigos = Interfaz.Tarjeta(Interfaz.Vertical(
                8,
                Interfaz.T("Amigos", 16, Interfaz.Texto, true),
                Interfaz.Parrafo(
                    "Cada cuenta tiene un código único. Añade el de tu amigo: la solicitud viaja por el chat " +
                    "y ambos podréis escribir en privado.", Interfaz.Suave, 12),
                Interfaz.Horizontal(10,
                    _chatCodigoAmigo,
                    Interfaz.Boton("Enviar solicitud", EnviarSolicitudAmistad)),
                Interfaz.T("Solicitudes recibidas", 14, Interfaz.Texto, true),
                _panelSolicitudes,
                Interfaz.T("Tus amigos", 14, Interfaz.Texto, true),
                _panelAmigos));

            return Interfaz.Vertical(12, sesion, mensajes, amigos);
        }

        private void IniciarChat()
        {
            if (!_dentro) return;

            DetenerChat();

            try
            {
                _amigos = FriendsStore.Load(_uuid);
            }
            catch (Exception ex)
            {
                _amigos = null;
                VisorLog.Warn($"[chat] No se pudo cargar la lista de amigos: {ex.Message}");
            }

            try
            {
                _relay = new ChatRelayServer();
                _relay.Log += mensaje => VisorLog.Info($"[chat] {mensaje}");
                bool ok = _relay.Start(8920, 10);
                VisorLog.Info(ok
                    ? $"[chat] Relay local escuchando en el puerto {_relay.Port}."
                    : "[chat] Sin relay local: este visor sólo podrá unirse como invitado.");
            }
            catch (Exception ex)
            {
                _relay = null;
                VisorLog.Warn($"[chat] Relay local no disponible: {ex.Message}");
            }

            _portal.ChatEnabled = _relay?.IsRunning == true;
            _portal.ChatLocalPort = _relay?.IsRunning == true ? _relay!.Port : 0;

            _txtMiCodigo.Text = ChatProtocol.BuildFriendCode(_uuid);
            _txtChatEstado.Text = "Conectando al chat…";
            _txtChatEstado.Foreground = Interfaz.Aviso;
            _chatProximoIntento = DateTime.MinValue;

            RefrescarAmigos();
            _ = ConectarChatAsync();
        }

        private void DetenerChat()
        {
            try { _amigos?.Guardar(); } catch { }
            _amigos = null;

            var cliente = _chat;
            _chat = null;
            try { cliente?.Dispose(); } catch { }

            try { _relay?.Dispose(); } catch { }
            _relay = null;

            _portal.ChatEnabled = false;
            _portal.ChatLocalPort = 0;

            _presentes.Clear();
            _estadoPares.Clear();
            _chatPrivadoUid = "";
            _chatPrivadoNombre = "";
            _chatConectando = false;

            _chatMensajes.Children.Clear();
            _panelPresentes.Children.Clear();
            _panelAmigos.Children.Clear();
            _panelSolicitudes.Children.Clear();
            _txtMiCodigo.Text = "—";
            _txtChatEstado.Text = "Chat desconectado.";
            _txtChatEstado.Foreground = Interfaz.Suave;
            _txtPrivado.Text = "Mensajes para todos los presentes.";
            _txtPrivado.Foreground = Interfaz.Suave;
        }

        /// <summary>
        /// Mantiene el chat conectado: si se cae la conexión, reintenta cada 5 s.
        /// Lo llama el latido de la ventana.
        /// </summary>
        private void MantenerChatSesion()
        {
            if (!_dentro) return;
            if (_chat is { IsConnected: true }) return;
            if (DateTime.UtcNow < _chatProximoIntento) return;
            _ = ConectarChatAsync();
        }

        private string ResolverEndpointChat()
        {
            int puertoLocal = _relay?.Port ?? 8920;
            string destino = (_destino ?? "").Trim();
            if (destino.Length == 0) return $"ws://127.0.0.1:{puertoLocal}/chat";

            if (Uri.TryCreate(destino, UriKind.Absolute, out Uri? uri) &&
                (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps))
            {
                string esquema = uri.Scheme == Uri.UriSchemeHttps ? "wss" : "ws";
                string token = LanzadorMundo.ExtraerInvitacion(destino);
                string consulta = token.Length == 0 ? "" : $"?invitacion={Uri.EscapeDataString(token)}";
                return $"{esquema}://{uri.Authority}/chat{consulta}";
            }

            // IP de la red local: el relay del anfitrión escucha en 8920.
            if (LanzadorMundo.TryParsearDestino(destino, out string host, out _))
                return $"ws://{host}:8920/chat";

            return $"ws://127.0.0.1:{puertoLocal}/chat";
        }

        private async Task ConectarChatAsync()
        {
            if (!_dentro || _chatConectando) return;

            string endpoint = ResolverEndpointChat();
            var actual = _chat;
            if (actual is { IsConnected: true } &&
                string.Equals(actual.EndPoint, endpoint, StringComparison.OrdinalIgnoreCase))
                return;

            _chatConectando = true;
            try
            {
                if (actual != null)
                {
                    _chat = null;
                    try { actual.Dispose(); } catch { }
                }

                _presentes.Clear();
                _estadoPares.Clear();
                RefrescarPresentes();

                var cliente = new ChatClient(_nick, _uuid);
                SuscribirEventosChat(cliente);
                _chat = cliente;

                VisorLog.Info($"[chat] Conectando a {endpoint}…");
                bool ok = await cliente.ConnectAsync(endpoint).ConfigureAwait(false);
                if (!ok)
                {
                    if (ReferenceEquals(_chat, cliente)) _chat = null;
                    try { cliente.Dispose(); } catch { }
                    _chatProximoIntento = DateTime.UtcNow.AddSeconds(5);
                    EnUi(() =>
                    {
                        _txtChatEstado.Text = "Sin conexión con el anfitrión del chat; reintentando…";
                        _txtChatEstado.Foreground = Interfaz.Mal;
                    });
                    return;
                }

                _chatProximoIntento = DateTime.MinValue;
            }
            catch (Exception ex)
            {
                VisorLog.Warn($"[chat] Error al conectar: {ex.Message}");
                _chatProximoIntento = DateTime.UtcNow.AddSeconds(5);
            }
            finally
            {
                _chatConectando = false;
            }
        }

        private void SuscribirEventosChat(ChatClient cliente)
        {
            cliente.Connected += _ => EnUi(() =>
            {
                _txtChatEstado.Text = "Chat conectado.";
                _txtChatEstado.Foreground = Interfaz.Bien;
                AnadirMensajeSistema("Conectado al chat del metaverso.");
            });

            cliente.Disconnected += motivo => EnUi(() =>
            {
                _presentes.Clear();
                _estadoPares.Clear();
                RefrescarPresentes();
                _txtChatEstado.Text = "Chat desconectado; reintentando…";
                _txtChatEstado.Foreground = Interfaz.Mal;
                AnadirMensajeSistema($"Chat desconectado ({motivo}).");
                _chatProximoIntento = DateTime.UtcNow.AddSeconds(5);
            });

            cliente.TextReceived += (id, nombre, texto) => EnUi(() =>
            {
                bool propio = id == (_chat?.MyId ?? -1);
                AnadirMensajeChat(propio ? "Tú" : ChatProtocol.CleanName(nombre), texto,
                    propio ? Interfaz.Bien : Interfaz.Acento);
            });

            cliente.DirectMessageReceived += (uid, nombre, texto, _) => EnUi(() =>
            {
                if (_amigos != null && !_amigos.EsAmigo(uid))
                {
                    AnadirMensajeSistema($"{ChatProtocol.CleanName(nombre)} te escribió en privado; añádelo como amigo para responder.");
                    if (_amigos.TieneEntrante(uid)) return;
                    _amigos.AgregarEntrante(uid, nombre);
                    _amigos.Guardar();
                    RefrescarAmigos();
                    return;
                }

                AnadirMensajeChat($"{ChatProtocol.CleanName(nombre)} (privado)", texto, Interfaz.Aviso);
            });

            cliente.DirectMessageFailed += (_, motivo) => EnUi(() =>
                AnadirMensajeSistema($"No se pudo enviar el privado: {motivo}"));

            cliente.SystemReceived += texto => EnUi(() => AnadirMensajeSistema(texto));

            cliente.PeerJoined += (id, nombre, uid) => EnUi(() =>
            {
                _presentes[id] = ChatProtocol.CleanName(nombre);
                RefrescarPresentes();
            });

            cliente.PeerLeft += (id, uid) => EnUi(() =>
            {
                _presentes.Remove(id);
                _estadoPares.Remove(id);
                RefrescarPresentes();
            });

            cliente.PeerState += (id, nombre, audio, video) => EnUi(() =>
            {
                if (!string.IsNullOrWhiteSpace(nombre)) _presentes[id] = ChatProtocol.CleanName(nombre);
                _estadoPares[id] = video;
                RefrescarPresentes();
            });

            cliente.FriendRequestReceived += (uid, nombre, nota) => EnUi(() =>
            {
                if (_amigos == null) return;
                _amigos.AgregarEntrante(uid, nombre);
                _amigos.Guardar();
                RefrescarAmigos();
                AnadirMensajeSistema(string.IsNullOrWhiteSpace(nota)
                    ? $"{ChatProtocol.CleanName(nombre)} quiere ser tu amigo."
                    : $"{ChatProtocol.CleanName(nombre)} quiere ser tu amigo: «{nota}»");
            });

            cliente.FriendRequestSent += (uid, nombre, destino) => EnUi(() =>
            {
                if (_amigos == null) return;
                _amigos.ResolverSaliente(destino, uid, nombre);
                _amigos.Guardar();
                RefrescarAmigos();
            });

            cliente.FriendRequestFailed += (destino, motivo) => EnUi(() =>
            {
                if (_amigos != null)
                {
                    _amigos.QuitarSaliente(destino);
                    _amigos.Guardar();
                    RefrescarAmigos();
                }
                Estado($"Solicitud de amistad no entregada: {motivo}", error: true);
            });

            cliente.FriendAccepted += (uid, nombre) => EnUi(() =>
            {
                if (_amigos == null) return;
                _amigos.QuitarSaliente(uid);
                _amigos.QuitarSaliente(ChatProtocol.BuildFriendCode(uid));
                _amigos.QuitarEntrante(uid);
                _amigos.AgregarAmigo(uid, nombre);
                _amigos.Guardar();
                RefrescarAmigos();
                AnadirMensajeSistema($"{ChatProtocol.CleanName(nombre)} ha aceptado tu solicitud.");
            });

            cliente.FriendDeclined += (uid, nombre) => EnUi(() =>
            {
                if (_amigos != null)
                {
                    _amigos.QuitarSaliente(uid);
                    _amigos.QuitarSaliente(ChatProtocol.BuildFriendCode(uid));
                    _amigos.Guardar();
                    RefrescarAmigos();
                }
                AnadirMensajeSistema($"{ChatProtocol.CleanName(nombre)} ha rechazado tu solicitud.");
            });

            cliente.ErrorReceived += texto => EnUi(() => AnadirMensajeSistema(texto));
        }

        private void EnviarMensaje()
        {
            string texto = (_chatEntrada.Text ?? "").Trim();
            if (texto.Length == 0) return;

            var cliente = _chat;
            if (cliente == null || !cliente.IsConnected)
            {
                Estado("El chat no está conectado.", error: true);
                return;
            }

            _chatEntrada.Text = "";

            if (_chatPrivadoUid.Length > 0)
            {
                string destino = _chatPrivadoNombre;
                _ = cliente.SendDirectAsync(_chatPrivadoUid, texto);
                AnadirMensajeChat($"Tú → {destino} (privado)", texto, Interfaz.Bien);
                return;
            }

            _ = cliente.SendTextAsync(texto);
        }

        private void EnviarSolicitudAmistad()
        {
            string codigo = (_chatCodigoAmigo.Text ?? "").Trim();
            if (codigo.Length == 0)
            {
                Estado("Escribe el código de amigo.", error: true);
                return;
            }

            if (codigo.Equals(ChatProtocol.BuildFriendCode(_uuid), StringComparison.OrdinalIgnoreCase))
            {
                Estado("Ese código es el tuyo.", error: true);
                return;
            }

            var cliente = _chat;
            if (cliente == null || !cliente.IsConnected)
            {
                Estado("Conecta el chat antes de enviar solicitudes.", error: true);
                return;
            }

            if (_amigos == null)
            {
                Estado("No se pudo cargar la lista de amigos.", error: true);
                return;
            }

            if (_amigos.TieneSaliente(codigo))
            {
                Estado("Ya hay una solicitud pendiente con ese código.");
                return;
            }

            _amigos.RegistrarSaliente("", codigo, "");
            _amigos.Guardar();
            _ = cliente.SendFriendRequestAsync(codigo);
            _chatCodigoAmigo.Text = "";
            RefrescarAmigos();
            Estado("Solicitud enviada.");
        }

        private void RefrescarPresentes()
        {
            _panelPresentes.Children.Clear();
            if (_presentes.Count == 0)
            {
                _panelPresentes.Children.Add(Interfaz.Parrafo("Nadie más en el chat.", Interfaz.Suave, 12));
                return;
            }

            foreach (var par in _presentes)
            {
                bool video = _estadoPares.TryGetValue(par.Key, out bool v) && v;
                _panelPresentes.Children.Add(Interfaz.Horizontal(
                    8,
                    Interfaz.T(par.Value, 13, Interfaz.Texto),
                    Interfaz.T(video ? "cámara" : "texto", 11, Interfaz.Suave)));
            }
        }

        private void RefrescarAmigos()
        {
            _panelSolicitudes.Children.Clear();
            _panelAmigos.Children.Clear();

            if (_amigos == null)
            {
                _panelAmigos.Children.Add(Interfaz.Parrafo("Sin lista de amigos.", Interfaz.Suave, 12));
                return;
            }

            foreach (var solicitud in new List<FriendRequestRecord>(_amigos.Incoming))
            {
                string uid = solicitud.Uid;
                string nombre = string.IsNullOrWhiteSpace(solicitud.Name) ? uid[..Math.Min(8, uid.Length)] : solicitud.Name;
                _panelSolicitudes.Children.Add(Interfaz.Horizontal(
                    8,
                    Interfaz.T(nombre, 13, Interfaz.Texto),
                    Interfaz.Boton("Aceptar", () => ResponderSolicitud(uid, true)),
                    Interfaz.Boton("Rechazar", () => ResponderSolicitud(uid, false))));
            }

            if (_amigos.Incoming.Count == 0)
                _panelSolicitudes.Children.Add(Interfaz.Parrafo("Sin solicitudes pendientes.", Interfaz.Suave, 12));

            foreach (var amigo in new List<FriendRecord>(_amigos.Friends))
            {
                string uid = amigo.Uid;
                string nombre = string.IsNullOrWhiteSpace(amigo.Name) ? uid : amigo.Name;
                bool enLinea = _presentes.Values.Contains(nombre);

                _panelAmigos.Children.Add(Interfaz.Horizontal(
                    8,
                    Interfaz.T(nombre, 13, enLinea ? Interfaz.Bien : Interfaz.Suave),
                    Interfaz.Parrafo(enLinea ? "(en línea)" : "(sin conexión)", Interfaz.Suave, 11),
                    Interfaz.Boton("Privado", () => FijarPrivado(uid, nombre)),
                    Interfaz.Boton("Quitar", () => QuitarAmigo(uid, nombre))));
            }

            if (_amigos.Friends.Count == 0)
                _panelAmigos.Children.Add(Interfaz.Parrafo("Todavía no tienes amigos añadidos.", Interfaz.Suave, 12));

            foreach (var pendiente in new List<FriendRequestRecord>(_amigos.Outgoing))
            {
                string etiqueta = string.IsNullOrWhiteSpace(pendiente.Name) ? pendiente.Code : pendiente.Name;
                _panelAmigos.Children.Add(Interfaz.Parrafo($"Solicitud pendiente: {etiqueta}", Interfaz.Aviso, 12));
            }
        }

        private void ResponderSolicitud(string uid, bool aceptar)
        {
            if (_amigos == null) return;

            if (aceptar)
            {
                var solicitud = _amigos.Incoming.FirstOrDefault(s => s.Uid == uid);
                _amigos.AgregarAmigo(uid, solicitud?.Name ?? uid);
            }
            _amigos.QuitarEntrante(uid);
            _amigos.QuitarSaliente(uid);
            _amigos.Guardar();
            _ = _chat?.SendFriendResponseAsync(uid, aceptar);
            RefrescarAmigos();
            Estado(aceptar ? "Solicitud aceptada." : "Solicitud rechazada.");
        }

        private void QuitarAmigo(string uid, string nombre)
        {
            if (_amigos == null) return;
            _amigos.QuitarAmigo(uid);
            _amigos.Guardar();
            if (_chatPrivadoUid == uid)
            {
                _chatPrivadoUid = "";
                _chatPrivadoNombre = "";
                _txtPrivado.Text = "Mensajes para todos los presentes.";
                _txtPrivado.Foreground = Interfaz.Suave;
            }
            RefrescarAmigos();
            Estado($"{nombre} ya no está en tu lista de amigos.");
        }

        private void FijarPrivado(string uid, string nombre)
        {
            _chatPrivadoUid = uid;
            _chatPrivadoNombre = nombre;
            _txtPrivado.Text = $"Conversación privada con {nombre}. «Volver a todos» para salir.";
            _txtPrivado.Foreground = Interfaz.Aviso;
        }

        private void AnadirMensajeChat(string autor, string texto, Avalonia.Media.IBrush color)
        {
            _chatMensajes.Children.Add(Interfaz.Vertical(
                1,
                Interfaz.T(autor, 12, color, true),
                Interfaz.T(texto, 13, Interfaz.Texto)));
            RecortarMensajes();
            _chatScroll.ScrollToEnd();
        }

        private void AnadirMensajeSistema(string texto)
        {
            _chatMensajes.Children.Add(Interfaz.Parrafo("· " + texto, Interfaz.Suave, 12));
            RecortarMensajes();
            _chatScroll.ScrollToEnd();
        }

        private void RecortarMensajes()
        {
            while (_chatMensajes.Children.Count > 300)
                _chatMensajes.Children.RemoveAt(0);
        }
    }
}
