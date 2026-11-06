using System;
using System.Security.Cryptography;
using System.Text;

namespace Visor3D.Chat
{
    /// <summary>
    /// Token único de sesión para autenticar el chat (diseño S2, hueco G1).
    /// Es la misma credencial que la invitación de la sesión P2P: quien tiene la
    /// invitación tiene el token de chat, y nadie más. Relay, cliente local,
    /// proxy del túnel (WebNodoService) y visor Linux comparten este único valor
    /// dentro del proceso anfitrión a través de esta clase.
    /// Solo vive en memoria: no se persiste en disco, no se escribe en logs y no
    /// lleva ningún valor fijado en el código; se genera con aleatoriedad
    /// criptográfica en el arranque de la sesión (primer acceso a <see cref="Actual"/>).
    /// Todos los accesos al token vigente están sincronizados, así que la clase
    /// es segura frente a accesos concurrentes de varios hilos.
    /// </summary>
    public static class TokenSesionChat
    {
        // 16 bytes de entropía, representados como 32 hexadecimales en minúscula.
        private const int TokenBytes = 16;
        private const int TokenChars = 32;

        private static readonly object _candado = new();
        private static string? _actual;

        /// <summary>
        /// Token vigente de la sesión. Es perezoso: si aún no hay ninguno (ni
        /// generado ni adoptado con <see cref="Establecer"/>), genera uno nuevo,
        /// lo adopta como vigente y lo devuelve. Nunca devuelve null.
        /// </summary>
        public static string Actual
        {
            get
            {
                lock (_candado)
                {
                    return _actual ??= Generar();
                }
            }
        }

        /// <summary>
        /// Genera un token nuevo con <see cref="RandomNumberGenerator"/>:
        /// 16 bytes de entropía en hexadecimal minúscula (32 caracteres).
        /// Generar NO cambia el token vigente; para sustituirlo hay que usar
        /// <see cref="Renovar"/> (genera y adopta) o <see cref="Establecer"/>.
        /// </summary>
        public static string Generar()
        {
            byte[] bytes = RandomNumberGenerator.GetBytes(TokenBytes);
            return Convert.ToHexString(bytes).ToLowerInvariant();
        }

        /// <summary>
        /// Adopta <paramref name="token"/> como token vigente de la sesión, pero
        /// solo si cumple <see cref="FormatoValido"/>; cualquier otro valor
        /// (null, vacío o con formato incorrecto) se ignora en silencio y el
        /// token vigente queda como estaba.
        /// </summary>
        public static void Establecer(string? token)
        {
            if (!FormatoValido(token)) return;

            lock (_candado)
            {
                _actual = token;
            }
        }

        /// <summary>
        /// Genera un token nuevo, lo adopta como vigente y lo devuelve. La
        /// generación y la adopción se hacen dentro del mismo bloqueo, así que
        /// el valor devuelto es exactamente el que queda como <see cref="Actual"/>.
        /// </summary>
        public static string Renovar()
        {
            lock (_candado)
            {
                _actual = Generar();
                return _actual;
            }
        }

        /// <summary>
        /// Comprueba si <paramref name="token"/> es el token vigente de la sesión.
        /// Primero se exige el formato (32 hexadecimales en minúscula) y después
        /// se compara en tiempo fijo con <see cref="CryptographicOperations.FixedTimeEquals"/>
        /// para no filtrar por temporización cuánto coincide el acierto.
        /// </summary>
        public static bool EsValido(string? token)
        {
            if (!FormatoValido(token)) return false;

            string actual = Actual;
            return CryptographicOperations.FixedTimeEquals(
                Encoding.ASCII.GetBytes(token!),
                Encoding.ASCII.GetBytes(actual));
        }

        /// <summary>
        /// Formato exacto del token de sesión: 32 caracteres, todos dígitos o
        /// letras hexadecimales en minúscula (0-9, a-f). Las mayúsculas no valen.
        /// </summary>
        public static bool FormatoValido(string? token)
        {
            if (token is null || token.Length != TokenChars) return false;

            foreach (char c in token)
            {
                bool esDigito = c >= '0' && c <= '9';
                bool esHexMinuscula = c >= 'a' && c <= 'f';
                if (!esDigito && !esHexMinuscula) return false;
            }
            return true;
        }
    }
}
