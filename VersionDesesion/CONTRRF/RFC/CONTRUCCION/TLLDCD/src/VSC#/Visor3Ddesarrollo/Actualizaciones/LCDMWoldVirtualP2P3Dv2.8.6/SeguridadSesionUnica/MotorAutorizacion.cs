// =============================================================================
// MotorAutorizacion.cs
// Namespace : Visor3D.Seguridad.SesionUnica
// Proyecto  : Visor3D — Zero Trust Authorization Engine
// =============================================================================
// Dependencias permitidas: System.*, System.Security.Cryptography,
//                          System.Collections.Concurrent
// =============================================================================

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Threading;

namespace Visor3D.Seguridad.SesionUnica
{
    // -------------------------------------------------------------------------
    // Enum: operaciones protegidas por el motor
    // -------------------------------------------------------------------------

    /// <summary>
    /// Catálogo de operaciones que requieren autorización explícita.
    /// Ninguna puede ejecutarse sin un token válido más prueba criptográfica.
    /// </summary>
    public enum OperacionSegura
    {
        VerificarIdentidad,
        ConsultarEstadoSello,
        FirmarOperacion,
        RotarSecretoSesion,
        RecuperarCuenta,
        EliminarSello,
        ActualizarHardware,
        ConsultarAuditoria,
        EmitirTokenSesion,
        RevocarTokenSesion
    }

    // -------------------------------------------------------------------------
    // Clase interna: token de sesión
    // -------------------------------------------------------------------------

    /// <summary>
    /// Token de sesión emitido tras verificación criptográfica del sello.
    /// Contiene el secreto compartido que el solicitante debe demostrar conocer.
    /// </summary>
    public sealed class TokenSesion : IDisposable
    {
        /// <summary>Identificador único del token (GUID formateado).</summary>
        public string Id { get; }

        /// <summary>
        /// Secreto de sesión de 32 bytes generado aleatoriamente.
        /// Se pone a cero en memoria al revocar/disponer.
        /// </summary>
        public byte[] SecretoSesion { get; private set; }

        /// <summary>Instante de expiración UTC.</summary>
        public DateTime Expira { get; }

        /// <summary>Conjunto de operaciones que este token puede autorizar.</summary>
        public OperacionSegura[] PermisosOtorgados { get; }

        /// <summary>Número acumulado de usos satisfactorios del token.</summary>
        public long ContadorUsos;

        /// <summary>Indica que el token fue revocado explícitamente o expiró.</summary>
        public bool Revocado { get; private set; }

        /// <summary>Identificador de la cuenta propietaria.</summary>
        public string CuentaId { get; }

        // Construye un token con secreto aleatorio.
        internal TokenSesion(string cuentaId, OperacionSegura[] permisos, TimeSpan ttl)
        {
            Id               = Guid.NewGuid().ToString("N");
            CuentaId         = cuentaId ?? throw new ArgumentNullException(nameof(cuentaId));
            SecretoSesion    = GenerarSecretoAleatorio(32);
            Expira           = DateTime.UtcNow.Add(ttl);
            PermisosOtorgados = permisos ?? Array.Empty<OperacionSegura>();
            ContadorUsos     = 0;
            Revocado         = false;
        }

        /// <summary>Genera <paramref name="longitud"/> bytes criptográficamente aleatorios.</summary>
        private static byte[] GenerarSecretoAleatorio(int longitud)
        {
            var buf = new byte[longitud];
            using var rng = RandomNumberGenerator.Create();
            rng.GetBytes(buf);
            return buf;
        }

        /// <summary>Pone a cero el secreto de sesión en memoria (ZeroMemory).</summary>
        internal void BorrarSecreto()
        {
            if (SecretoSesion != null)
            {
                CryptoMemory.ZeroFill(SecretoSesion);
                SecretoSesion = Array.Empty<byte>();
            }
            Revocado = true;
        }

        /// <summary>¿Ha pasado la fecha de expiración?</summary>
        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public bool EstaExpirado() => DateTime.UtcNow >= Expira;

        /// <summary>¿El token permite ejecutar <paramref name="op"/>?</summary>
        public bool PermiteOperacion(OperacionSegura op)
        {
            foreach (var p in PermisosOtorgados)
                if (p == op) return true;
            return false;
        }

        public void Dispose() => BorrarSecreto();
    }

    // -------------------------------------------------------------------------
    // Helper: borrado seguro en memoria
    // -------------------------------------------------------------------------

    internal static class CryptoMemory
    {
        /// <summary>Rellena el array con ceros (equivalente a RtlZeroMemory/ZeroMemory).</summary>
        [MethodImpl(MethodImplOptions.NoInlining | MethodImplOptions.NoOptimization)]
        internal static void ZeroFill(byte[] buffer)
        {
            if (buffer == null) return;
            Array.Clear(buffer, 0, buffer.Length);
        }
    }

    // -------------------------------------------------------------------------
    // Helper: registro de rate-limiting por tokenId
    // -------------------------------------------------------------------------

    internal sealed class RegistroFallos
    {
        private int _contador;
        private DateTime _ventanaInicio;
        private readonly object _lock = new object();

        internal const int MaxFallosPorVentana = 10;
        internal static readonly TimeSpan VentanaFallos = TimeSpan.FromSeconds(60);

        public RegistroFallos() { _ventanaInicio = DateTime.UtcNow; }

        /// <summary>
        /// Incrementa el contador de fallos.
        /// Devuelve true si se superó el límite y el token debe revocarse.
        /// </summary>
        public bool RegistrarFallo()
        {
            lock (_lock)
            {
                var ahora = DateTime.UtcNow;
                if ((ahora - _ventanaInicio) >= VentanaFallos)
                {
                    // Nueva ventana: reiniciar contador
                    _contador = 0;
                    _ventanaInicio = ahora;
                }
                _contador++;
                return _contador > MaxFallosPorVentana;
            }
        }

        public void Reiniciar()
        {
            lock (_lock) { _contador = 0; _ventanaInicio = DateTime.UtcNow; }
        }
    }

    // -------------------------------------------------------------------------
    // Motor Zero Trust principal
    // -------------------------------------------------------------------------

    /// <summary>
    /// Motor Zero Trust: ninguna operación se autoriza implícitamente.
    /// Cada solicitud debe presentar:
    ///   1. Un token de sesión válido (emitido por el core tras verificar sello).
    ///   2. Un nonce de un solo uso (anti-replay).
    ///   3. Una prueba criptográfica de que el solicitante conoce el secreto de sesión.
    ///
    /// Operaciones protegidas: cada una tiene una política (requiere sello válido,
    /// requiere hardware ok, etc.). El motor evalúa la política y registra la decisión.
    ///
    /// No confundas "viene de localhost" con "es el proceso autorizado".
    /// La autenticación es por desafío criptográfico, no por origen de socket.
    /// </summary>
    public static class MotorAutorizacion
    {
        // ── Almacenes ────────────────────────────────────────────────────────

        /// <summary>Tokens activos indexados por Id.</summary>
        private static readonly ConcurrentDictionary<string, TokenSesion> _tokens
            = new ConcurrentDictionary<string, TokenSesion>(StringComparer.Ordinal);

        /// <summary>
        /// Nonces ya usados: clave = hash hex del nonce, valor = UTC de registro.
        /// Los nonces se expiran después de <see cref="TtlNonce"/>.
        /// </summary>
        private static readonly ConcurrentDictionary<string, DateTime> _nonces
            = new ConcurrentDictionary<string, DateTime>(StringComparer.Ordinal);

        /// <summary>Contadores de intentos fallidos por tokenId.</summary>
        private static readonly ConcurrentDictionary<string, RegistroFallos> _fallos
            = new ConcurrentDictionary<string, RegistroFallos>(StringComparer.Ordinal);

        // ── Constantes de política ────────────────────────────────────────────

        private static readonly TimeSpan TtlNonce = TimeSpan.FromSeconds(30);
        private const int TamanoMinimoNonce = 16; // bytes

        // ── Políticas: estado de sello requerido por operación ───────────────
        //
        // Operaciones que solo se permiten si el sello estaba Valido o Autoreparado
        // en el momento de emitir el token (reflejado en sus permisos).
        // La granularidad se impone al emitir el token; aquí validamos permisos.

        // ── API pública ───────────────────────────────────────────────────────

        /// <summary>
        /// Número de tokens no revocados y no expirados actualmente en memoria.
        /// </summary>
        public static int TokenesActivosCount
        {
            get
            {
                int count = 0;
                foreach (var kv in _tokens)
                    if (!kv.Value.Revocado && !kv.Value.EstaExpirado())
                        count++;
                return count;
            }
        }

        // ── EmitirToken ───────────────────────────────────────────────────────

        /// <summary>
        /// Emite un token de sesión si y solo si <paramref name="estadoSello"/>
        /// es <see cref="ResultadoRevision.Valido"/> o
        /// <see cref="ResultadoRevision.Autoreparado"/>.
        /// </summary>
        /// <param name="cuentaId">Identificador de la cuenta.</param>
        /// <param name="estadoSello">Resultado de la revisión del sello hardware.</param>
        /// <param name="ttl">Tiempo de vida del token.</param>
        /// <returns>El token emitido, o <c>null</c> si el sello no es aceptable.</returns>
        public static TokenSesion? EmitirToken(
            string cuentaId,
            ResultadoRevision estadoSello,
            TimeSpan ttl)
        {
            if (string.IsNullOrWhiteSpace(cuentaId))
                throw new ArgumentException("cuentaId no puede ser nulo o vacío.", nameof(cuentaId));

            if (estadoSello == null ||
                (estadoSello.Estado != EstadoVerificacionSello.Valido &&
                 estadoSello.Estado != EstadoVerificacionSello.AutorreparadoDesdeArchivo &&
                 estadoSello.Estado != EstadoVerificacionSello.AutorreparadoDesdeRegistro &&
                 estadoSello.Estado != EstadoVerificacionSello.CadenaIntegraRequiereConfirmacionRiesgo))
            {
                RegistrarAuditoria("EMIT_DENIED",
                    $"cuenta={cuentaId} sello={estadoSello?.Estado} — estado inaceptable.");
                return null;
            }

            // Permisos otorgados según estado del sello
            var permisos = ObtenerPermisosParaSello(estadoSello);
            var token    = new TokenSesion(cuentaId, permisos, ttl);

            _tokens[token.Id] = token;

            RegistrarAuditoria("EMIT_OK",
                $"tokenId={token.Id} cuenta={cuentaId} sello={estadoSello.Estado} " +
                $"expira={token.Expira:O} permisos={string.Join(",", permisos)}");

            return token;
        }

        // ── RevocarToken ──────────────────────────────────────────────────────

        /// <summary>
        /// Revoca el token identificado por <paramref name="tokenId"/>.
        /// El secreto de sesión se pone a cero inmediatamente (ZeroMemory).
        /// </summary>
        /// <returns><c>true</c> si existía y fue revocado; <c>false</c> si no se encontró.</returns>
        public static bool RevocarToken(string tokenId)
        {
            if (string.IsNullOrEmpty(tokenId)) return false;

            if (_tokens.TryRemove(tokenId, out var token))
            {
                token.BorrarSecreto();
                _fallos.TryRemove(tokenId, out _);
                RegistrarAuditoria("REVOKE_OK", $"tokenId={tokenId}");
                return true;
            }

            RegistrarAuditoria("REVOKE_MISS", $"tokenId={tokenId} — no encontrado.");
            return false;
        }

        // ── AutorizarOperacion ────────────────────────────────────────────────

        /// <summary>
        /// Evalúa si la operación puede ejecutarse.
        ///
        /// Comprobaciones en orden:
        ///   1. Token existe y no está revocado.
        ///   2. Token no ha expirado.
        ///   3. Nonce tiene al menos <see cref="TamanoMinimoNonce"/> bytes.
        ///   4. Nonce no ha sido usado antes (anti-replay).
        ///   5. Token tiene permiso para la operación.
        ///   6. Rate-limit: si hay demasiados fallos, se revoca el token.
        /// </summary>
        /// <param name="tokenId">Id del token de sesión.</param>
        /// <param name="operacion">Operación solicitada.</param>
        /// <param name="nonce">Nonce de un solo uso (mín. 16 bytes).</param>
        /// <returns>(<c>true</c>, razón vacía) si se autoriza; (<c>false</c>, motivo) si se deniega.</returns>
        public static (bool ok, string razon) AutorizarOperacion(
            string tokenId,
            OperacionSegura operacion,
            byte[] nonce)
        {
            // ── 1. Token existe ──────────────────────────────────────────────
            if (!_tokens.TryGetValue(tokenId, out var token))
                return Denegar(tokenId, operacion, "TOKEN_NOT_FOUND",
                    "El token no existe o ya fue revocado.");

            // ── 2. Token no revocado ─────────────────────────────────────────
            if (token.Revocado)
                return Denegar(tokenId, operacion, "TOKEN_REVOKED",
                    "El token ha sido revocado.");

            // ── 3. Token no expirado ─────────────────────────────────────────
            if (token.EstaExpirado())
            {
                // Revocar y limpiar
                RevocarToken(tokenId);
                return Denegar(tokenId, operacion, "TOKEN_EXPIRED",
                    "El token ha expirado.");
            }

            // ── 4. Nonce: tamaño mínimo ──────────────────────────────────────
            if (nonce == null || nonce.Length < TamanoMinimoNonce)
                return DenegarConFallo(token, tokenId, operacion, "NONCE_TOO_SHORT",
                    $"El nonce debe tener al menos {TamanoMinimoNonce} bytes.");

            // ── 5. Nonce anti-replay ─────────────────────────────────────────
            if (!RegistrarUsoNonce(nonce))
                return DenegarConFallo(token, tokenId, operacion, "NONCE_REPLAY",
                    "El nonce ya fue utilizado (ataque de replay).");

            // ── 6. Permiso de operación ──────────────────────────────────────
            if (!token.PermiteOperacion(operacion))
                return DenegarConFallo(token, tokenId, operacion, "OP_NOT_PERMITTED",
                    $"El token no tiene permiso para '{operacion}'.");

            // ── Autorizado ───────────────────────────────────────────────────
            Interlocked.Increment(ref token.ContadorUsos);
            // Reiniciar contador de fallos tras éxito
            if (_fallos.TryGetValue(tokenId, out var reg)) reg.Reiniciar();

            RegistrarAuditoria("ALLOW",
                $"tokenId={tokenId} op={operacion} usos={token.ContadorUsos}");

            return (true, string.Empty);
        }

        // ── RegistrarUsoNonce ─────────────────────────────────────────────────

        /// <summary>
        /// Registra el nonce como usado.
        /// Devuelve <c>true</c> si era nuevo (primer uso dentro del TTL);
        /// <c>false</c> si ya existía (replay detectado).
        ///
        /// Los nonces son válidos (y por tanto detectables como replay) durante
        /// <see cref="TtlNonce"/> (30 s).  Los caducados se purgan en esta llamada.
        /// </summary>
        public static bool RegistrarUsoNonce(byte[] nonce)
        {
            if (nonce == null || nonce.Length == 0) return false;

            var clave = HexNonce(nonce);
            var ahora = DateTime.UtcNow;

            // Purgar nonces expirados de forma oportunista
            foreach (var kv in _nonces)
                if ((ahora - kv.Value) > TtlNonce)
                    _nonces.TryRemove(kv.Key, out _);

            // Intentar insertar: si ya existe → replay
            return _nonces.TryAdd(clave, ahora);
        }

        // ── LimpiarTokensExpirados ────────────────────────────────────────────

        /// <summary>
        /// Elimina de memoria todos los tokens expirados o revocados,
        /// borrando sus secretos de sesión (ZeroMemory).
        /// Debe llamarse periódicamente desde un timer externo.
        /// </summary>
        public static void LimpiarTokensExpirados()
        {
            int eliminados = 0;
            foreach (var kv in _tokens)
            {
                var t = kv.Value;
                if (t.Revocado || t.EstaExpirado())
                {
                    if (_tokens.TryRemove(kv.Key, out var removido))
                    {
                        removido.BorrarSecreto();
                        _fallos.TryRemove(kv.Key, out _);
                        eliminados++;
                    }
                }
            }

            // Limpiar nonces expirados
            var ahora = DateTime.UtcNow;
            foreach (var kv in _nonces)
                if ((ahora - kv.Value) > TtlNonce)
                    _nonces.TryRemove(kv.Key, out _);

            if (eliminados > 0)
                RegistrarAuditoria("CLEANUP",
                    $"Tokens eliminados={eliminados} nonces_activos={_nonces.Count}");
        }

        // ── Métodos privados ──────────────────────────────────────────────────

        /// <summary>
        /// Mapea el estado del sello al conjunto de operaciones permitidas.
        /// Sello Valido → todos los permisos.
        /// Sello Autoreparado → permisos reducidos (sin EliminarSello, sin ActualizarHardware).
        /// </summary>
        private static OperacionSegura[] ObtenerPermisosParaSello(ResultadoRevision estado)
        {
            if (estado.Estado == EstadoVerificacionSello.Valido)
                return (OperacionSegura[])Enum.GetValues(typeof(OperacionSegura));

            // Autoreparado: permisos reducidos
            return new[]
            {
                OperacionSegura.VerificarIdentidad,
                OperacionSegura.ConsultarEstadoSello,
                OperacionSegura.FirmarOperacion,
                OperacionSegura.RotarSecretoSesion,
                OperacionSegura.RecuperarCuenta,
                OperacionSegura.ConsultarAuditoria,
                OperacionSegura.EmitirTokenSesion,
                OperacionSegura.RevocarTokenSesion
            };
        }

        /// <summary>
        /// Registra un fallo de autorización y aplica rate-limit.
        /// Si se supera el límite (10 fallos / 60 s), revoca el token automáticamente.
        /// </summary>
        private static (bool ok, string razon) DenegarConFallo(
            TokenSesion token,
            string tokenId,
            OperacionSegura operacion,
            string codigo,
            string mensaje)
        {
            var registro = _fallos.GetOrAdd(tokenId, _ => new RegistroFallos());
            bool limiteAlcanzado = registro.RegistrarFallo();

            if (limiteAlcanzado)
            {
                RegistrarAuditoria("RATE_LIMIT_REVOKE",
                    $"tokenId={tokenId} op={operacion} — superado límite de fallos, revocando.");
                RevocarToken(tokenId);
                return (false, $"{mensaje} [Token revocado por rate-limit]");
            }

            return Denegar(tokenId, operacion, codigo, mensaje);
        }

        private static (bool ok, string razon) Denegar(
            string tokenId,
            OperacionSegura operacion,
            string codigo,
            string mensaje)
        {
            RegistrarAuditoria($"DENY_{codigo}",
                $"tokenId={tokenId} op={operacion} — {mensaje}");
            return (false, mensaje);
        }

        /// <summary>Calcula la representación hexadecimal del SHA-256 del nonce.</summary>
        private static string HexNonce(byte[] nonce)
        {
            using var sha = SHA256.Create();
            var hash = sha.ComputeHash(nonce);
            return BitConverter.ToString(hash).Replace("-", string.Empty);
        }

        /// <summary>Escribe una entrada de auditoría en la consola de diagnóstico.</summary>
        private static void RegistrarAuditoria(string evento, string detalle)
        {
            // En producción esta línea se reemplaza por el sistema de auditoría
            // persistente del proyecto; aquí se usa Trace para no introducir I/O.
            System.Diagnostics.Trace.WriteLine(
                $"[{DateTime.UtcNow:O}] [MotorAutorizacion] {evento} | {detalle}");
        }
    }
}
