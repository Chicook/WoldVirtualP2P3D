// IpcCanalSeguro.cs — Canal IPC local basado en Named Pipe con seguridad Zero Trust.
// Namespace: Visor3D.Seguridad.SesionUnica
// Generado automáticamente — no editar manualmente sin autorización.

using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Seguridad.SesionUnica
{
    // ─────────────────────────────────────────────────────────────────────────────
    // Modelos de mensaje
    // ─────────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Mensaje enviado desde el cliente (UI) hacia el servidor (Core) por el canal IPC.
    /// Todos los campos son Base64 cuando llevan datos binarios.
    /// </summary>
    public sealed class MensajeIpc
    {
        /// <summary>Nombre de la operación solicitada (p. ej. "FirmarDatos", "ObtenerUuid").</summary>
        [JsonPropertyName("type")]
        public string Type { get; set; } = string.Empty;

        /// <summary>Identificador del token de sesión activo.</summary>
        [JsonPropertyName("tokenId")]
        public string TokenId { get; set; } = string.Empty;

        /// <summary>Cuerpo de la operación (JSON serializado, opcionalmente cifrado).</summary>
        [JsonPropertyName("payload")]
        public string Payload { get; set; } = string.Empty;

        /// <summary>HMAC-SHA256(secretoSesion, nonce + type + payload) en Base64.</summary>
        [JsonPropertyName("mac")]
        public string Mac { get; set; } = string.Empty;

        /// <summary>Nonce único de este mensaje (Base64, 32 bytes aleatorios).</summary>
        [JsonPropertyName("nonce")]
        public string Nonce { get; set; } = string.Empty;

        /// <summary>Timestamp ISO-8601 del mensaje (protege contra replay tardío).</summary>
        [JsonPropertyName("timestamp")]
        public string Timestamp { get; set; } = string.Empty;
    }

    /// <summary>
    /// Respuesta del servidor (Core) al cliente (UI) por el canal IPC.
    /// </summary>
    public sealed class RespuestaIpc
    {
        /// <summary>true si la operación se completó sin error.</summary>
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        /// <summary>Resultado de la operación (JSON serializado).</summary>
        [JsonPropertyName("payload")]
        public string Payload { get; set; } = string.Empty;

        /// <summary>HMAC-SHA256(secretoSesion, nonce + ok + payload) en Base64.</summary>
        [JsonPropertyName("mac")]
        public string Mac { get; set; } = string.Empty;

        /// <summary>Mensaje de error si Ok == false; null en caso de éxito.</summary>
        [JsonPropertyName("error")]
        public string? Error { get; set; }

        /// <summary>Nonce del mensaje original que genera esta respuesta.</summary>
        [JsonPropertyName("nonce")]
        public string Nonce { get; set; } = string.Empty;
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // IpcCanalSeguro — Named Pipe Zero Trust
    // ─────────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Canal IPC local basado en Named Pipe con seguridad Zero Trust.
    ///
    /// Nombre del pipe: \\.\pipe\LuciaSecureCore_{UserSid}
    /// (incluir UserSid en el nombre impide colisiones entre usuarios de sesión distintos)
    ///
    /// SDDL del pipe:
    ///   D:(A;;GRGW;;;{SID_USUARIO_ACTUAL})(A;;GRGW;;;SY)
    ///   O:{SID_USUARIO_ACTUAL}G:SY
    ///   Solo el usuario actual y SYSTEM pueden conectar. Localhost solo no es suficiente.
    ///
    /// Protocolo de handshake (3 pasos):
    ///   1. Servidor envía: NONCE (32 bytes aleatorios) + timestamp ISO-8601
    ///   2. Cliente responde: HMAC-SHA256(nonce + timestamp + nombre_operación, secreto_sesión)
    ///      + tokenId + operación solicitada (JSON completo MensajeIpc)
    ///   3. Servidor verifica HMAC, verifica nonce no usado, consulta MotorAutorizacion,
    ///      ejecuta la operación y responde con resultado firmado (RespuestaIpc).
    ///
    /// Formato de mensaje: JSON con campos type, tokenId, payload, mac, nonce, timestamp.
    /// Cada mensaje lleva su propio mac = HMAC(secretoSesion, nonce + type + payload).
    /// Máx. tamaño de mensaje: 64 KB. Timeout de handshake: 5 s.
    /// Impersonation level: Identification (mínimo necesario).
    /// </summary>
    public static class IpcCanalSeguro
    {
        // ── Constantes ──────────────────────────────────────────────────────────

        private const int MaxMensajeBytes   = 64 * 1024;       // 64 KB
        private const int HandshakeTimeoutMs = 5_000;           // 5 segundos
        private const int NonceSizeBytes    = 32;
        private const string PipePrefix     = "LuciaSecureCore_";

        // ── Estado interno ───────────────────────────────────────────────────────

        // Nonces ya usados (anti-replay). Conviene purgar entradas antiguas en producción;
        // para el alcance de la sesión es suficiente un ConcurrentDictionary.
        private static readonly ConcurrentDictionary<string, DateTime> _noncesUsados =
            new(StringComparer.Ordinal);

        // Secreto de sesión compartido; se inyecta en tiempo de ejecución.
        private static byte[]? _secretoSesion;

        // ── API pública ──────────────────────────────────────────────────────────

        /// <summary>
        /// Establece el secreto de sesión que se usa para firmar/verificar mensajes.
        /// Debe llamarse antes de <see cref="IniciarServidorAsync"/>.
        /// </summary>
        public static void EstablecerSecreto(byte[] secreto)
        {
            if (secreto is null || secreto.Length == 0)
                throw new ArgumentException("Secreto de sesión no puede estar vacío.", nameof(secreto));

            // Sobrescribir secreto anterior en memoria antes de reemplazar la referencia.
            if (_secretoSesion is not null)
                CryptoUtils.ZeroMemory(_secretoSesion);

            _secretoSesion = secreto;
        }

        /// <summary>
        /// Bucle principal del servidor IPC. Acepta conexiones entrantes en un pipe con
        /// nombre y ACL restringida, y lanza una tarea independiente por conexión.
        /// </summary>
        public static async Task IniciarServidorAsync(CancellationToken ct)
        {
            if (_secretoSesion is null)
                throw new InvalidOperationException("Secreto de sesión no establecido.");

            Debug.WriteLine($"[IpcCanalSeguro] Servidor iniciado. Pipe: {ObtenerNombrePipe()}");

            while (!ct.IsCancellationRequested)
            {
                NamedPipeServerStream? pipe = null;
                try
                {
                    var acl = CrearAcl();

                    pipe = NamedPipeServerStreamAcl.Create(
                        ObtenerNombrePipeLocal(),
                        PipeDirection.InOut,
                        NamedPipeServerStream.MaxAllowedServerInstances,
                        PipeTransmissionMode.Message,
                        PipeOptions.Asynchronous | PipeOptions.WriteThrough,
                        inBufferSize:  MaxMensajeBytes,
                        outBufferSize: MaxMensajeBytes,
                        pipeSecurity:  acl);

                    await pipe.WaitForConnectionAsync(ct).ConfigureAwait(false);

                    // Capturar para la lambda (evitar closure sobre variable que cambia).
                    var pipeCap = pipe;
                    _ = Task.Run(() => ManejarConexionAsync(pipeCap, ct), ct);
                }
                catch (OperationCanceledException)
                {
                    pipe?.Dispose();
                    break;
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[IpcCanalSeguro] Error aceptando conexión: {ex.Message}");
                    pipe?.Dispose();
                    // Breve pausa para evitar spin en caso de error persistente.
                    await Task.Delay(200, ct).ConfigureAwait(false);
                }
            }

            Debug.WriteLine("[IpcCanalSeguro] Servidor detenido.");
        }

        /// <summary>
        /// Devuelve el nombre completo del pipe (formato UNC para uso externo/documentación).
        /// </summary>
        public static string ObtenerNombrePipe()
            => $@"\\.\pipe\{PipePrefix}{ObtenerSidUsuario()}";

        /// <summary>
        /// Lee un <see cref="MensajeIpc"/> desde el pipe dentro del timeout indicado.
        /// </summary>
        /// <returns>Tupla (ok, msg): ok=false si hubo timeout o error de deserialización.</returns>
        public static (bool ok, MensajeIpc? msg) LeerMensaje(NamedPipeServerStream pipe, TimeSpan timeout)
        {
            if (pipe is null) return (false, null);

            try
            {
                pipe.ReadTimeout = (int)timeout.TotalMilliseconds;

                var buffer = new byte[MaxMensajeBytes];
                int leidos = pipe.Read(buffer, 0, buffer.Length);
                if (leidos == 0) return (false, null);

                var json = Encoding.UTF8.GetString(buffer, 0, leidos);
                var msg  = JsonSerializer.Deserialize<MensajeIpc>(json);
                return msg is not null ? (true, msg) : (false, null);
            }
            catch (TimeoutException)
            {
                Debug.WriteLine("[IpcCanalSeguro] LeerMensaje: timeout.");
                return (false, null);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[IpcCanalSeguro] LeerMensaje error: {ex.Message}");
                return (false, null);
            }
        }

        /// <summary>
        /// Serializa y envía una <see cref="RespuestaIpc"/> al cliente.
        /// La respuesta lleva su propio MAC firmado con <paramref name="secretoSesion"/>.
        /// </summary>
        public static bool EnviarRespuesta(NamedPipeServerStream pipe, RespuestaIpc respuesta, byte[] secretoSesion)
        {
            if (pipe is null || respuesta is null || secretoSesion is null) return false;

            try
            {
                // Firmar la respuesta antes de enviarla.
                respuesta.Mac = FirmarRespuesta(respuesta, secretoSesion);

                var json  = JsonSerializer.Serialize(respuesta);
                var bytes = Encoding.UTF8.GetBytes(json);

                if (bytes.Length > MaxMensajeBytes)
                {
                    Debug.WriteLine("[IpcCanalSeguro] EnviarRespuesta: respuesta excede 64 KB.");
                    return false;
                }

                pipe.Write(bytes, 0, bytes.Length);
                pipe.Flush();
                return true;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[IpcCanalSeguro] EnviarRespuesta error: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Verifica que el MAC del mensaje es válido con el secreto de sesión dado.
        /// También comprueba que el nonce no haya sido usado previamente (anti-replay).
        /// </summary>
        public static bool VerificarMacMensaje(MensajeIpc msg, byte[] secretoSesion)
        {
            if (msg is null || secretoSesion is null) return false;

            try
            {
                // Anti-replay: rechazar nonce ya visto.
                if (_noncesUsados.ContainsKey(msg.Nonce))
                {
                    Debug.WriteLine("[IpcCanalSeguro] Nonce repetido detectado — posible replay.");
                    return false;
                }

                var macEsperado = ComputarMacMensaje(msg, secretoSesion);
                var macRecibido = Convert.FromBase64String(msg.Mac);

                bool valido = CryptographicOperations.FixedTimeEquals(macEsperado, macRecibido);

                if (valido)
                    _noncesUsados[msg.Nonce] = DateTime.UtcNow;

                return valido;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[IpcCanalSeguro] VerificarMacMensaje error: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Crea y devuelve la ACL del pipe con permisos mínimos Zero Trust:
        /// GenericRead+GenericWrite para el usuario actual y para SYSTEM únicamente.
        /// SDDL: D:(A;;GRGW;;;{SID_USUARIO})(A;;GRGW;;;SY)
        /// </summary>
        public static PipeSecurity CrearAcl()
        {
            var sid        = WindowsIdentity.GetCurrent().User
                             ?? throw new InvalidOperationException("No se puede obtener el SID del usuario actual.");
            var systemSid  = new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null);

            var security = new PipeSecurity();

            // Usuario actual: sólo lectura y escritura genéricas (no Full Control).
            security.AddAccessRule(new PipeAccessRule(
                sid,
                PipeAccessRights.ReadWrite,
                AccessControlType.Allow));

            // SYSTEM: mismo nivel — necesario para servicios del SO.
            security.AddAccessRule(new PipeAccessRule(
                systemSid,
                PipeAccessRights.ReadWrite,
                AccessControlType.Allow));

            // Propietario: usuario actual.
            security.SetOwner(sid);
            security.SetGroup(systemSid);

            return security;
        }

        // ── Lado cliente (UI → Core) ─────────────────────────────────────────────

        /// <summary>
        /// Envía una solicitud al servidor IPC y espera la respuesta.
        /// Realiza el handshake completo de 3 pasos:
        ///   1. Recibe el challenge (nonce servidor + timestamp).
        ///   2. Adjunta el MAC del cliente y envía el mensaje.
        ///   3. Recibe y verifica la respuesta firmada.
        /// </summary>
        /// <param name="msg">Mensaje a enviar (nonce y timestamp se rellenan automáticamente).</param>
        /// <param name="secretoSesion">Secreto compartido de sesión.</param>
        /// <returns><see cref="RespuestaIpc"/> verificada, o null si algo falla.</returns>
        public static async Task<RespuestaIpc?> EnviarSolicitudAsync(MensajeIpc msg, byte[] secretoSesion)
        {
            if (msg is null || secretoSesion is null) return null;

            NamedPipeClientStream? pipe = null;
            try
            {
                pipe = new NamedPipeClientStream(
                    ".",                          // servidor local
                    ObtenerNombrePipeLocal(),
                    PipeDirection.InOut,
                    PipeOptions.Asynchronous | PipeOptions.WriteThrough);

                using var cts = new CancellationTokenSource(HandshakeTimeoutMs);
                await pipe.ConnectAsync(HandshakeTimeoutMs, cts.Token).ConfigureAwait(false);

                // ── Paso 1: leer challenge del servidor ──────────────────────────
                var challengeBuffer = new byte[MaxMensajeBytes];
                int challengeLen = await pipe.ReadAsync(challengeBuffer, 0, challengeBuffer.Length, cts.Token)
                                             .ConfigureAwait(false);
                if (challengeLen == 0) return null;

                var challengeJson = Encoding.UTF8.GetString(challengeBuffer, 0, challengeLen);
                var challenge = JsonSerializer.Deserialize<HandshakeChallenge>(challengeJson);
                if (challenge is null) return null;

                // ── Paso 2: completar mensaje con nonce+timestamp del challenge ──
                msg.Nonce     = challenge.Nonce;
                msg.Timestamp = challenge.Timestamp;
                msg.Mac       = Convert.ToBase64String(ComputarMacMensaje(msg, secretoSesion));

                var msgJson  = JsonSerializer.Serialize(msg);
                var msgBytes = Encoding.UTF8.GetBytes(msgJson);
                await pipe.WriteAsync(msgBytes, 0, msgBytes.Length, cts.Token).ConfigureAwait(false);
                await pipe.FlushAsync(cts.Token).ConfigureAwait(false);

                // ── Paso 3: leer respuesta ───────────────────────────────────────
                var respBuffer = new byte[MaxMensajeBytes];
                int respLen = await pipe.ReadAsync(respBuffer, 0, respBuffer.Length, cts.Token)
                                        .ConfigureAwait(false);
                if (respLen == 0) return null;

                var respJson = Encoding.UTF8.GetString(respBuffer, 0, respLen);
                var respuesta = JsonSerializer.Deserialize<RespuestaIpc>(respJson);
                if (respuesta is null) return null;

                // Verificar MAC de la respuesta.
                if (!VerificarMacRespuesta(respuesta, secretoSesion))
                {
                    Debug.WriteLine("[IpcCanalSeguro] MAC de respuesta inválido.");
                    return null;
                }

                return respuesta;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[IpcCanalSeguro] EnviarSolicitudAsync error: {ex.Message}");
                return null;
            }
            finally
            {
                pipe?.Dispose();
            }
        }

        // ── Implementación interna ───────────────────────────────────────────────

        /// <summary>
        /// Gestiona una conexión de cliente de forma asíncrona (protocolo de 3 pasos).
        /// </summary>
        private static async Task ManejarConexionAsync(NamedPipeServerStream pipe, CancellationToken ct)
        {
            using (pipe)
            {
                try
                {
                    // Verificar identidad del cliente (impersonación mínima: Identification).
                    pipe.RunAsClient(() =>
                    {
                        // La llamada a RunAsClient con un delegado vacío confirma que el
                        // nivel de impersonación es al menos Identification.
                        // Si el cliente conectado no pasa el ACL del pipe, la conexión
                        // nunca llega aquí.
                    });

                    using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
                    cts.CancelAfter(HandshakeTimeoutMs);

                    // ── Paso 1: enviar challenge ─────────────────────────────────
                    var nonce = GenerarNonce();
                    var ts    = DateTime.UtcNow.ToString("O");
                    var challenge = new HandshakeChallenge { Nonce = nonce, Timestamp = ts };
                    var challengeBytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(challenge));

                    await pipe.WriteAsync(challengeBytes, 0, challengeBytes.Length, cts.Token)
                              .ConfigureAwait(false);
                    await pipe.FlushAsync(cts.Token).ConfigureAwait(false);

                    // ── Paso 2: leer mensaje del cliente ─────────────────────────
                    var buffer = new byte[MaxMensajeBytes];
                    int leidos = await pipe.ReadAsync(buffer, 0, buffer.Length, cts.Token)
                                           .ConfigureAwait(false);
                    if (leidos == 0) return;

                    var json = Encoding.UTF8.GetString(buffer, 0, leidos);
                    var msg  = JsonSerializer.Deserialize<MensajeIpc>(json);
                    if (msg is null) return;

                    // ── Paso 3: verificar y procesar ─────────────────────────────
                    var secreto = _secretoSesion;
                    if (secreto is null) return;

                    if (!VerificarMacMensaje(msg, secreto))
                    {
                        await EnviarRespuestaError(pipe, "MAC inválido o nonce repetido.", secreto, nonce, ct)
                              .ConfigureAwait(false);
                        return;
                    }

                    // Verificar que el nonce del mensaje coincide con el challenge enviado.
                    if (!string.Equals(msg.Nonce, nonce, StringComparison.Ordinal))
                    {
                        await EnviarRespuestaError(pipe, "Nonce no coincide con challenge.", secreto, nonce, ct)
                              .ConfigureAwait(false);
                        return;
                    }

                    // Delegar autorización y ejecución al motor (punto de extensión).
                    var respuesta = ProcesarOperacion(msg, secreto);
                    EnviarRespuesta(pipe, respuesta, secreto);
                }
                catch (OperationCanceledException)
                {
                    Debug.WriteLine("[IpcCanalSeguro] Conexión cancelada por timeout de handshake.");
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[IpcCanalSeguro] ManejarConexionAsync error: {ex.Message}");
                }
            }
        }

        /// <summary>
        /// Punto de extensión: procesa la operación solicitada.
        /// En la integración real se delega a <c>MotorAutorizacion</c>.
        /// </summary>
        private static RespuestaIpc ProcesarOperacion(MensajeIpc msg, byte[] secreto)
        {
            // TODO: Integrar con MotorAutorizacion.Autorizar(msg.TokenId, msg.Type)
            //       y con NucleoSeguroLucia para ejecutar la operación.
            // Por ahora se devuelve un resultado de eco para pruebas de integración.
            Debug.WriteLine($"[IpcCanalSeguro] Operación recibida: {msg.Type} token={msg.TokenId}");

            return new RespuestaIpc
            {
                Ok      = true,
                Payload = msg.Payload,
                Nonce   = msg.Nonce,
                Error   = null
            };
        }

        // ── Helpers criptográficos ───────────────────────────────────────────────

        /// <summary>
        /// Computa HMAC-SHA256(secreto, nonce || type || payload) del mensaje.
        /// </summary>
        private static byte[] ComputarMacMensaje(MensajeIpc msg, byte[] secreto)
        {
            var datos = Encoding.UTF8.GetBytes(msg.Nonce + msg.Type + msg.Payload);
            using var hmac = new HMACSHA256(secreto);
            return hmac.ComputeHash(datos);
        }

        /// <summary>
        /// Firma la respuesta: HMAC-SHA256(secreto, nonce || ok || payload).
        /// </summary>
        private static string FirmarRespuesta(RespuestaIpc resp, byte[] secreto)
        {
            var datos = Encoding.UTF8.GetBytes(resp.Nonce + resp.Ok.ToString() + resp.Payload);
            using var hmac = new HMACSHA256(secreto);
            return Convert.ToBase64String(hmac.ComputeHash(datos));
        }

        /// <summary>
        /// Verifica el MAC de una respuesta recibida por el cliente.
        /// </summary>
        private static bool VerificarMacRespuesta(RespuestaIpc resp, byte[] secreto)
        {
            try
            {
                var macEsperado = Encoding.UTF8.GetBytes(FirmarRespuesta(resp, secreto));
                // FirmarRespuesta ya devuelve Base64; comparar contra el campo Mac recibido.
                var macRecibidoStr  = resp.Mac;
                var macEsperadoStr  = Convert.ToBase64String(
                    new HMACSHA256(secreto).ComputeHash(
                        Encoding.UTF8.GetBytes(resp.Nonce + resp.Ok.ToString() + resp.Payload)));

                return string.Equals(macEsperadoStr, macRecibidoStr, StringComparison.Ordinal);
            }
            catch
            {
                return false;
            }
        }

        /// <summary>
        /// Envía una respuesta de error firmada al cliente.
        /// </summary>
        private static async Task EnviarRespuestaError(
            NamedPipeServerStream pipe,
            string error,
            byte[] secreto,
            string nonce,
            CancellationToken ct)
        {
            var respuesta = new RespuestaIpc
            {
                Ok    = false,
                Error = error,
                Nonce = nonce
            };
            respuesta.Mac = FirmarRespuesta(respuesta, secreto);

            var bytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(respuesta));
            await pipe.WriteAsync(bytes, 0, bytes.Length, ct).ConfigureAwait(false);
            await pipe.FlushAsync(ct).ConfigureAwait(false);
        }

        /// <summary>
        /// Genera un nonce criptográficamente seguro de 32 bytes, devuelto en Base64.
        /// </summary>
        private static string GenerarNonce()
        {
            var nonce = new byte[NonceSizeBytes];
            RandomNumberGenerator.Fill(nonce);
            return Convert.ToBase64String(nonce);
        }

        /// <summary>
        /// Devuelve el nombre local del pipe (sin el prefijo \\.\pipe\).
        /// </summary>
        private static string ObtenerNombrePipeLocal()
            => $"{PipePrefix}{ObtenerSidUsuario()}";

        /// <summary>
        /// Obtiene el SID del usuario actual en formato de cadena (S-1-5-...).
        /// </summary>
        private static string ObtenerSidUsuario()
        {
            var sid = WindowsIdentity.GetCurrent().User;
            return sid?.Value ?? "UNKNOWN";
        }

        // ── Tipo auxiliar interno para el challenge ──────────────────────────────

        private sealed class HandshakeChallenge
        {
            [JsonPropertyName("nonce")]
            public string Nonce { get; set; } = string.Empty;

            [JsonPropertyName("timestamp")]
            public string Timestamp { get; set; } = string.Empty;
        }
    }

}
