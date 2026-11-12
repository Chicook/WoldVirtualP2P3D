using System;
using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Visor3D.Chat
{
    /// <summary>
    /// Formato compartido por el relay y los clientes del chat.
    /// Texto: JSON UTF-8. Audio/vídeo: trama binaria
    ///   cliente -> servidor: [tipo][payload]
    ///   servidor -> cliente: [tipo][id emisor uint32 LE][payload]
    /// </summary>
    public static class ChatProtocol
    {
        public const int KindAudio = 1;
        public const int KindVideo = 2;

        public const int SampleRate = 16000;
        public const int AudioFrameBytes = 640;      // 20 ms PCM16 mono 16 kHz
        public const int MaxAudioBytes = 8 * 1024;
        public const int MaxVideoBytes = 640 * 1024;
        public const int MaxFrameBytes = 700 * 1024;
        public const int MaxTextChars = 500;
        public const int MaxNameChars = 40;
        public const int MaxUidChars = 64;
        public const int MaxFriendNoteChars = 120;
        public const int MaxClients = 16;

        public const int VideoWidth = 320;
        public const int VideoHeight = 180;
        public const int VideoFps = 4;

        public static byte[] TextFrame(object payload) => JsonSerializer.SerializeToUtf8Bytes(payload);

        public static string CleanName(string? name)
        {
            string limpio = (name ?? "").Trim();
            if (limpio.Length == 0) limpio = "Invitado";
            if (limpio.Length > MaxNameChars) limpio = limpio[..MaxNameChars];
            return StripControls(limpio);
        }

        public static string CleanText(string? text)
        {
            string limpio = (text ?? "").Trim();
            if (limpio.Length > MaxTextChars) limpio = limpio[..MaxTextChars];
            return StripControls(limpio);
        }

        /// <summary>
        /// Identidad estable del usuario durante la sesión. Se normaliza a
        /// minúsculas y solo admite letras, números y separadores habituales.
        /// </summary>
        public static string CleanUid(string? uid)
        {
            string limpio = (uid ?? "").Trim().ToLowerInvariant();
            var buffer = new StringBuilder(Math.Min(limpio.Length, MaxUidChars));
            foreach (char c in limpio)
            {
                if (char.IsLetterOrDigit(c) || c == '-' || c == '_' || c == '.' || c == ':' || c == '@')
                    buffer.Append(c);
                if (buffer.Length >= MaxUidChars) break;
            }
            return buffer.ToString();
        }

        /// <summary>
        /// Código corto y determinista para compartir con otra persona. No es
        /// reversible; el relay lo compara con el uid de los clientes conectados.
        /// </summary>
        public static string BuildFriendCode(string? uid)
        {
            string limpio = CleanUid(uid);
            if (limpio.Length == 0) return "";

            byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes("wvp3d-friend:" + limpio));
            const string alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
            var salida = new StringBuilder(8);
            int acumulador = 0;
            int bits = 0;
            for (int i = 0; i < hash.Length && salida.Length < 8; i++)
            {
                acumulador = (acumulador << 8) | hash[i];
                bits += 8;
                while (bits >= 5 && salida.Length < 8)
                {
                    bits -= 5;
                    salida.Append(alfabeto[(acumulador >> bits) & 0x1F]);
                }
            }
            return salida.ToString();
        }

        /// <summary>
        /// Identidad local para perfiles antiguos sin uuid. Es estable por nombre,
        /// pero no identifica de forma única a dos personas con el mismo alias.
        /// </summary>
        public static string BuildFallbackUid(string? name)
        {
            string limpio = CleanName(name).ToLowerInvariant();
            byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes("wvp3d-user:" + limpio));
            return "local-" + Convert.ToHexString(hash.AsSpan(0, 8)).ToLowerInvariant();
        }

        private static string StripControls(string texto)
        {
            var buffer = new char[texto.Length];
            int n = 0;
            foreach (char c in texto)
            {
                if (char.IsControl(c) && c != '\n' && c != '\t') continue;
                buffer[n++] = c;
            }
            return new string(buffer, 0, n);
        }

        public static byte[] BuildClientFrame(int kind, ReadOnlySpan<byte> payload)
        {
            byte[] frame = new byte[1 + payload.Length];
            frame[0] = (byte)kind;
            payload.CopyTo(frame.AsSpan(1));
            return frame;
        }

        public static byte[] BuildServerFrame(int kind, int senderId, ReadOnlySpan<byte> payload)
        {
            byte[] frame = new byte[5 + payload.Length];
            frame[0] = (byte)kind;
            BinaryPrimitives.WriteInt32LittleEndian(frame.AsSpan(1, 4), senderId);
            payload.CopyTo(frame.AsSpan(5));
            return frame;
        }

        public static bool TryReadServerFrame(ReadOnlySpan<byte> frame, out int kind, out int senderId, out int payloadOffset)
        {
            kind = 0;
            senderId = 0;
            payloadOffset = 0;
            if (frame.Length < 5) return false;

            int k = frame[0];
            if (k != KindAudio && k != KindVideo) return false;

            int id = BinaryPrimitives.ReadInt32LittleEndian(frame[1..5]);
            if (id <= 0) return false;

            kind = k;
            senderId = id;
            payloadOffset = 5;
            return true;
        }
    }
}
