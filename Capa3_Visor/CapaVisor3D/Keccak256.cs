using System;

namespace VisorSingularity
{
    internal static class Keccak256
    {
        private const int RateBytes = 136;

        public static byte[] ComputeHash(byte[] input)
        {
            if (input == null) throw new ArgumentNullException(nameof(input));

            ulong[] state = new ulong[25];
            int offset = 0;
            int remaining = input.Length;

            while (remaining >= RateBytes)
            {
                AbsorbBlock(state, input, offset);
                KeccakF1600(state);
                offset += RateBytes;
                remaining -= RateBytes;
            }

            Span<byte> block = stackalloc byte[RateBytes];
            if (remaining > 0)
                new ReadOnlySpan<byte>(input, offset, remaining).CopyTo(block);

            block[remaining] = 0x01;
            block[RateBytes - 1] |= 0x80;

            AbsorbBlock(state, block);
            KeccakF1600(state);

            byte[] output = new byte[32];
            Squeeze(state, output);
            return output;
        }

        private static void AbsorbBlock(ulong[] state, ReadOnlySpan<byte> block)
        {
            for (int i = 0; i < RateBytes / 8; i++)
            {
                state[i] ^= ToUInt64Little(block, i * 8);
            }
        }

        private static void AbsorbBlock(ulong[] state, byte[] input, int offset)
        {
            for (int i = 0; i < RateBytes / 8; i++)
            {
                state[i] ^= ToUInt64Little(input, offset + i * 8);
            }
        }

        private static void Squeeze(ulong[] state, Span<byte> output)
        {
            int outOffset = 0;
            int i = 0;
            while (outOffset < output.Length)
            {
                ulong lane = state[i++];
                for (int b = 0; b < 8 && outOffset < output.Length; b++)
                {
                    output[outOffset++] = (byte)(lane & 0xFF);
                    lane >>= 8;
                }
            }
        }

        private static ulong ToUInt64Little(ReadOnlySpan<byte> src, int offset)
        {
            return
                ((ulong)src[offset + 0]) |
                ((ulong)src[offset + 1] << 8) |
                ((ulong)src[offset + 2] << 16) |
                ((ulong)src[offset + 3] << 24) |
                ((ulong)src[offset + 4] << 32) |
                ((ulong)src[offset + 5] << 40) |
                ((ulong)src[offset + 6] << 48) |
                ((ulong)src[offset + 7] << 56);
        }

        private static ulong ToUInt64Little(byte[] src, int offset)
        {
            return
                ((ulong)src[offset + 0]) |
                ((ulong)src[offset + 1] << 8) |
                ((ulong)src[offset + 2] << 16) |
                ((ulong)src[offset + 3] << 24) |
                ((ulong)src[offset + 4] << 32) |
                ((ulong)src[offset + 5] << 40) |
                ((ulong)src[offset + 6] << 48) |
                ((ulong)src[offset + 7] << 56);
        }

        private static ulong RotL(ulong x, int n) => (x << n) | (x >> (64 - n));

        private static void KeccakF1600(ulong[] s)
        {
            for (int round = 0; round < 24; round++)
            {
                ulong c0 = s[0] ^ s[5] ^ s[10] ^ s[15] ^ s[20];
                ulong c1 = s[1] ^ s[6] ^ s[11] ^ s[16] ^ s[21];
                ulong c2 = s[2] ^ s[7] ^ s[12] ^ s[17] ^ s[22];
                ulong c3 = s[3] ^ s[8] ^ s[13] ^ s[18] ^ s[23];
                ulong c4 = s[4] ^ s[9] ^ s[14] ^ s[19] ^ s[24];

                ulong d0 = c4 ^ RotL(c1, 1);
                ulong d1 = c0 ^ RotL(c2, 1);
                ulong d2 = c1 ^ RotL(c3, 1);
                ulong d3 = c2 ^ RotL(c4, 1);
                ulong d4 = c3 ^ RotL(c0, 1);

                s[0] ^= d0; s[5] ^= d0; s[10] ^= d0; s[15] ^= d0; s[20] ^= d0;
                s[1] ^= d1; s[6] ^= d1; s[11] ^= d1; s[16] ^= d1; s[21] ^= d1;
                s[2] ^= d2; s[7] ^= d2; s[12] ^= d2; s[17] ^= d2; s[22] ^= d2;
                s[3] ^= d3; s[8] ^= d3; s[13] ^= d3; s[18] ^= d3; s[23] ^= d3;
                s[4] ^= d4; s[9] ^= d4; s[14] ^= d4; s[19] ^= d4; s[24] ^= d4;

                ulong b00 = s[0];
                ulong b10 = RotL(s[6], 44);
                ulong b20 = RotL(s[12], 43);
                ulong b30 = RotL(s[18], 21);
                ulong b40 = RotL(s[24], 14);

                ulong b01 = RotL(s[3], 28);
                ulong b11 = RotL(s[9], 20);
                ulong b21 = RotL(s[10], 3);
                ulong b31 = RotL(s[16], 45);
                ulong b41 = RotL(s[22], 61);

                ulong b02 = RotL(s[1], 1);
                ulong b12 = RotL(s[7], 6);
                ulong b22 = RotL(s[13], 25);
                ulong b32 = RotL(s[19], 8);
                ulong b42 = RotL(s[20], 18);

                ulong b03 = RotL(s[4], 27);
                ulong b13 = RotL(s[5], 36);
                ulong b23 = RotL(s[11], 10);
                ulong b33 = RotL(s[17], 15);
                ulong b43 = RotL(s[23], 56);

                ulong b04 = RotL(s[2], 62);
                ulong b14 = RotL(s[8], 55);
                ulong b24 = RotL(s[14], 39);
                ulong b34 = RotL(s[15], 41);
                ulong b44 = RotL(s[21], 2);

                s[0] = b00 ^ (~b10 & b20);
                s[1] = b10 ^ (~b20 & b30);
                s[2] = b20 ^ (~b30 & b40);
                s[3] = b30 ^ (~b40 & b00);
                s[4] = b40 ^ (~b00 & b10);

                s[5] = b01 ^ (~b11 & b21);
                s[6] = b11 ^ (~b21 & b31);
                s[7] = b21 ^ (~b31 & b41);
                s[8] = b31 ^ (~b41 & b01);
                s[9] = b41 ^ (~b01 & b11);

                s[10] = b02 ^ (~b12 & b22);
                s[11] = b12 ^ (~b22 & b32);
                s[12] = b22 ^ (~b32 & b42);
                s[13] = b32 ^ (~b42 & b02);
                s[14] = b42 ^ (~b02 & b12);

                s[15] = b03 ^ (~b13 & b23);
                s[16] = b13 ^ (~b23 & b33);
                s[17] = b23 ^ (~b33 & b43);
                s[18] = b33 ^ (~b43 & b03);
                s[19] = b43 ^ (~b03 & b13);

                s[20] = b04 ^ (~b14 & b24);
                s[21] = b14 ^ (~b24 & b34);
                s[22] = b24 ^ (~b34 & b44);
                s[23] = b34 ^ (~b44 & b04);
                s[24] = b44 ^ (~b04 & b14);

                s[0] ^= RoundConstants[round];
            }
        }

        private static readonly ulong[] RoundConstants =
        [
            0x0000000000000001UL, 0x0000000000008082UL, 0x800000000000808AUL, 0x8000000080008000UL,
            0x000000000000808BUL, 0x0000000080000001UL, 0x8000000080008081UL, 0x8000000000008009UL,
            0x000000000000008AUL, 0x0000000000000088UL, 0x0000000080008009UL, 0x000000008000000AUL,
            0x000000008000808BUL, 0x800000000000008BUL, 0x8000000000008089UL, 0x8000000000008003UL,
            0x8000000000008002UL, 0x8000000000000080UL, 0x000000000000800AUL, 0x800000008000000AUL,
            0x8000000080008081UL, 0x8000000000008080UL, 0x0000000080000001UL, 0x8000000080008008UL
        ];
    }
}
