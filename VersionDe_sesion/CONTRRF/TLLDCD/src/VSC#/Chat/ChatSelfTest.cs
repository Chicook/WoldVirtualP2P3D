using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using Visor3D.Services;

namespace Visor3D.Chat
{
    /// <summary>
    /// Prueba de humo sin interfaz: relay, dos clientes, audio/vídeo, límite de
    /// texto y enrutado del túnel WebNodo hacia /chat. Se lanza con
    /// <c>--chat-selftest</c> y deja el resultado en %TEMP%.
    /// </summary>
    public static class ChatSelfTest
    {
        public static int Run()
        {
            var log = new StringBuilder();
            int fallos = 0;

            void Check(bool ok, string texto)
            {
                log.AppendLine((ok ? "OK   " : "FALLO ") + texto);
                if (!ok) fallos++;
            }

            try
            {
                // En un WinExe, OnStartup corre en el hilo de UI con SynchronizationContext:
                // ejecutar la prueba en el pool evita el bloqueo mutuo con el dispatcher.
                Task.Run(() => EjecutarAsync(Check)).GetAwaiter().GetResult();
            }
            catch (Exception ex)
            {
                log.AppendLine("EXCEPCION " + ex);
                fallos++;
            }

            try
            {
                int mics = ChatVoice.MicrophoneCount;
                var cams = ChatWebcam.ListDevices();
                log.AppendLine($"INFO micrófonos={mics} webcams={cams.Count}");
            }
            catch (Exception ex)
            {
                log.AppendLine("INFO no se pudieron sondear los dispositivos: " + ex.Message);
            }

            log.AppendLine($"== fin, fallos={fallos} ==");
            string salida = log.ToString();
            try { File.WriteAllText(Path.Combine(Path.GetTempPath(), "woldvirtual_chat_selftest.log"), salida, Encoding.UTF8); } catch { }
            try { Console.WriteLine(salida); } catch { }
            return fallos == 0 ? 0 : 1;
        }

        private static async Task EjecutarAsync(Action<bool, string> check)
        {
            // ── Identidad y código de amigo ──────────────────────────
            string codigoAna = ChatProtocol.BuildFriendCode("uid-ana");
            string codigoBeto = ChatProtocol.BuildFriendCode("uid-beto");
            check(codigoAna.Length == 8, "el código de amigo tiene 8 caracteres");
            check(ChatProtocol.BuildFriendCode("  UID-ANA  ") == codigoAna,
                "el código de amigo es estable e insensible a mayúsculas");
            check(ChatProtocol.CleanUid("  AbC-123_x  ") == "abc-123_x",
                "el uid se normaliza y limita a caracteres seguros");

            // ── Persistencia local de amigos ─────────────────────────
            string carpeta = Path.Combine(Path.GetTempPath(), "wv_friends_" + Guid.NewGuid().ToString("N"));
            try
            {
                var almacen = FriendsStore.Load("uid-ana", carpeta);
                almacen.AgregarAmigo("uid-beto", "Beto");
                almacen.AgregarEntrante("uid-carla", "Carla");
                almacen.RegistrarSaliente("", "ABCD2345", "");
                check(almacen.Guardar(), "la lista de amigos se guarda en disco");

                var recargado = FriendsStore.Load("uid-ana", carpeta);
                check(recargado.EsAmigo("uid-beto") &&
                      recargado.Incoming.Count == 1 &&
                      recargado.Outgoing.Count == 1,
                    "la lista de amigos se recupera tras recargar");

                recargado.ResolverSaliente("abcd2345", "uid-carla", "Carla");
                check(recargado.Outgoing.Count == 1 &&
                      recargado.Outgoing[0].Uid == "uid-carla" &&
                      recargado.Outgoing[0].Code == "",
                    "una solicitud por código se resuelve al uid real");
            }
            finally
            {
                try { Directory.Delete(carpeta, true); } catch { }
            }

            using var relay = new ChatRelayServer();
            if (!relay.Start(18920, 20))
            {
                check(false, "el relay abre un puerto local");
                return;
            }
            check(true, $"relay escucha en {relay.Port}");

            using var ana = new ChatClient("Ana", "uid-ana");
            using var beto = new ChatClient("Beto", "uid-beto");

            var anaVeBeto = new TaskCompletionSource<(int Id, string Nombre, string Uid)>();
            ana.PeerJoined += (id, nombre, uid) =>
            {
                if (uid == "uid-beto") anaVeBeto.TrySetResult((id, nombre, uid));
            };

            var textoBeto = new TaskCompletionSource<(int Id, string Nombre, string Texto)>();
            beto.TextReceived += (id, nombre, texto) => textoBeto.TrySetResult((id, nombre, texto));

            var mediaBeto = new TaskCompletionSource<(int Kind, int Emisor, byte[] Payload)>();
            beto.MediaReceived += (kind, payload, emisor) => mediaBeto.TrySetResult((kind, emisor, payload));

            bool okAna = await ana.ConnectAsync($"ws://127.0.0.1:{relay.Port}/chat");
            bool okBeto = await beto.ConnectAsync($"ws://127.0.0.1:{relay.Port}/chat");
            check(okAna && okBeto, "dos clientes conectan al relay");
            if (!okAna || !okBeto) return;

            await EsperarAsync(() => ana.MyId > 0 && beto.MyId > 0, 3000);
            check(ana.MyId > 0 && beto.MyId > 0, "ambos reciben identificador del relay");

            var (okPresencia, presencia) = await ConTimeoutAsync(anaVeBeto.Task, 3000);
            check(okPresencia && presencia.Nombre == "Beto" && presencia.Uid == "uid-beto",
                "la presencia incluye el uid estable del recién llegado");

            // ── Solicitud de amistad por código ──────────────────────
            var solicitudBeto = new TaskCompletionSource<(string Uid, string Nombre, string Nota)>();
            beto.FriendRequestReceived += (uid, nombre, nota) =>
                solicitudBeto.TrySetResult((uid, nombre, nota));

            var ackAna = new TaskCompletionSource<(string Uid, string Nombre, string Destino)>();
            ana.FriendRequestSent += (uid, nombre, destino) =>
                ackAna.TrySetResult((uid, nombre, destino));

            await ana.SendFriendRequestAsync(codigoBeto, "hola");
            var (okSolicitud, solicitud) = await ConTimeoutAsync(solicitudBeto.Task, 3000);
            check(okSolicitud &&
                  solicitud.Uid == "uid-ana" &&
                  solicitud.Nombre == "Ana" &&
                  solicitud.Nota == "hola",
                "la solicitud de amistad llega solo al destino y con el uid del emisor");

            var (okAck, ack) = await ConTimeoutAsync(ackAna.Task, 3000);
            check(okAck && ack.Uid == "uid-beto" && ack.Nombre == "Beto",
                "el emisor recibe el uid real resuelto desde el código");

            var aceptadaAna = new TaskCompletionSource<(string Uid, string Nombre)>();
            ana.FriendAccepted += (uid, nombre) => aceptadaAna.TrySetResult((uid, nombre));
            await beto.SendFriendResponseAsync("uid-ana", true);
            var (okAceptada, aceptada) = await ConTimeoutAsync(aceptadaAna.Task, 3000);
            check(okAceptada && aceptada.Uid == "uid-beto",
                "la aceptación de amistad se entrega al remitente");

            var rechazoNoEsperado = new TaskCompletionSource<bool>();
            beto.FriendDeclined += (uid, nombre) => rechazoNoEsperado.TrySetResult(true);
            var (okSinRechazo, _) = await ConTimeoutAsync(rechazoNoEsperado.Task, 400);
            check(!okSinRechazo, "la aceptación no se confunde con un rechazo");

            // ── Mensaje privado dirigido ─────────────────────────────
            var privadoBeto = new TaskCompletionSource<(string Uid, string Nombre, string Texto)>();
            beto.DirectMessageReceived += (uid, nombre, texto, ts) =>
                privadoBeto.TrySetResult((uid, nombre, texto));

            var ecoNoEsperado = new TaskCompletionSource<string>();
            ana.TextReceived += (id, nombre, texto) =>
            {
                if (texto == "privado") ecoNoEsperado.TrySetResult(texto);
            };

            await ana.SendDirectAsync("uid-beto", "privado");
            var (okPrivado, privado) = await ConTimeoutAsync(privadoBeto.Task, 3000);
            check(okPrivado &&
                  privado.Uid == "uid-ana" &&
                  privado.Texto == "privado",
                "el mensaje privado llega al destinatario con su autor");

            var (okEco, _) = await ConTimeoutAsync(ecoNoEsperado.Task, 600);
            check(!okEco, "el mensaje privado no se difunde a la sala");

            var falloPrivado = new TaskCompletionSource<(string Uid, string Motivo)>();
            ana.DirectMessageFailed += (uid, motivo) => falloPrivado.TrySetResult((uid, motivo));
            await ana.SendDirectAsync("uid-nadie", "hola");
            var (okFalloPrivado, fallo) = await ConTimeoutAsync(falloPrivado.Task, 3000);
            check(okFalloPrivado && fallo.Uid == "uid-nadie" && fallo.Motivo.Length > 0,
                "un privado a alguien ausente avisa al emisor");

            var falloSolicitud = new TaskCompletionSource<(string Uid, string Motivo)>();
            ana.FriendRequestFailed += (uid, motivo) => falloSolicitud.TrySetResult((uid, motivo));
            await ana.SendFriendRequestAsync("00000000", "");
            var (okFallaSolicitud, falloSol) = await ConTimeoutAsync(falloSolicitud.Task, 3000);
            check(okFallaSolicitud && falloSol.Motivo.Length > 0,
                "una solicitud a un código ausente avisa al emisor");

            await ana.SendTextAsync("hola mundo");
            var (okTexto, texto) = await ConTimeoutAsync(textoBeto.Task, 3000);
            check(okTexto && texto.Nombre == "Ana" && texto.Texto == "hola mundo",
                "el texto llega al otro cliente con emisor correcto");

            byte[] pcm = new byte[ChatProtocol.AudioFrameBytes];
            for (int i = 0; i < pcm.Length; i++) pcm[i] = (byte)(i & 0xFF);
            await ana.SendMediaAsync(ChatProtocol.KindAudio, pcm);
            var (okAudio, audio) = await ConTimeoutAsync(mediaBeto.Task, 3000);
            check(okAudio && audio.Kind == ChatProtocol.KindAudio && audio.Emisor == ana.MyId &&
                  audio.Payload.Length == ChatProtocol.AudioFrameBytes,
                "el audio se retransmite con el emisor correcto");

            var mediaVideo = new TaskCompletionSource<(int Kind, int Emisor, byte[] Payload)>();
            beto.MediaReceived += (kind, payload, emisor) =>
            {
                if (kind == ChatProtocol.KindVideo) mediaVideo.TrySetResult((kind, emisor, payload));
            };
            byte[] jpeg = new byte[128];
            jpeg[0] = 0xFF; jpeg[1] = 0xD8; jpeg[2] = 0xFF; jpeg[^1] = 0xD9;
            await ana.SendMediaAsync(ChatProtocol.KindVideo, jpeg);
            var (okVideo, video) = await ConTimeoutAsync(mediaVideo.Task, 3000);
            check(okVideo && video.Kind == ChatProtocol.KindVideo && video.Payload.Length == jpeg.Length,
                "el vídeo JPEG se retransmite");

            var textoLargo = new TaskCompletionSource<string>();
            beto.TextReceived += (id, nombre, texto) =>
            {
                if (texto.Length >= ChatProtocol.MaxTextChars) textoLargo.TrySetResult(texto);
            };
            await ana.SendTextAsync(new string('x', ChatProtocol.MaxTextChars + 50));
            var (okRecorte, recortado) = await ConTimeoutAsync(textoLargo.Task, 3000);
            check(okRecorte && recortado.Length == ChatProtocol.MaxTextChars,
                "el texto se recorta a 500 caracteres");

            using var web = new WebNodoService();
            web.Start();
            if (!web.IsRunning)
            {
                check(false, "WebNodo abre un puerto para la prueba de túnel");
                return;
            }
            web.ChatLocalPort = relay.Port;
            web.ChatEnabled = true;

            using var carla = new ChatClient("Carla", "uid-carla");
            var textoCarla = new TaskCompletionSource<string>();
            carla.TextReceived += (id, nombre, texto) =>
            {
                if (texto == "via webnodo") textoCarla.TrySetResult(texto);
            };
            bool okCarla = await carla.ConnectAsync($"ws://127.0.0.1:{web.ActivePort}/chat");
            check(okCarla, "el cliente entra por la ruta /chat del WebNodo");
            if (okCarla)
            {
                await EsperarAsync(() => carla.MyId > 0, 3000);
                await ana.SendTextAsync("via webnodo");
                var (okViaWeb, viaWeb) = await ConTimeoutAsync(textoCarla.Task, 4000);
                check(okViaWeb && viaWeb == "via webnodo", "el texto cruza el proxy /chat del WebNodo");
                await carla.CloseAsync();
            }

            web.ChatEnabled = false;
            web.Stop();

            await ana.CloseAsync();
            await beto.CloseAsync();
        }

        private static async Task EsperarAsync(Func<bool> condicion, int timeoutMs)
        {
            int esperado = 0;
            while (!condicion() && esperado < timeoutMs)
            {
                await Task.Delay(50);
                esperado += 50;
            }
        }

        private static async Task<(bool Ok, T Value)> ConTimeoutAsync<T>(Task<T> tarea, int timeoutMs)
        {
            var completada = await Task.WhenAny(tarea, Task.Delay(timeoutMs));
            if (completada != tarea) return (false, default!);
            return (true, await tarea);
        }
    }
}
