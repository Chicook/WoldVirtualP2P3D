using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;

namespace Visor3D.Seguridad
{
    /// <summary>
    /// Generación de frases semilla según BIP-39 (lista oficial de 2048 palabras,
    /// 12 palabras = 128 bits de entropía + 4 de checksum).
    /// </summary>
    public static class Bip39
    {
        private static readonly string[] Palabras = CargarLista();

        private static string[] CargarLista()
        {
            var asm = Assembly.GetExecutingAssembly();
            using Stream? stream = asm.GetManifestResourceStream("Visor3D.Seguridad.bip39-english.txt")
                ?? throw new InvalidOperationException("No está embebida la lista BIP-39.");

            using var reader = new StreamReader(stream);
            var lista = new List<string>(2048);
            string? linea;
            while ((linea = reader.ReadLine()) != null)
            {
                linea = linea.Trim();
                if (linea.Length > 0) lista.Add(linea);
            }

            if (lista.Count != 2048)
                throw new InvalidOperationException($"Lista BIP-39 inválida: {lista.Count} palabras.");

            return lista.ToArray();
        }

        /// <summary>Genera 12 o 24 palabras BIP-39 con entropía criptográfica.</summary>
        public static IReadOnlyList<string> Generate(int cantidadPalabras = 12)
        {
            if (cantidadPalabras != 12 && cantidadPalabras != 24)
                throw new ArgumentOutOfRangeException(nameof(cantidadPalabras), "BIP-39 admite 12 o 24 palabras.");

            int bitsEntropia = cantidadPalabras == 12 ? 128 : 256;
            int bitsChecksum = bitsEntropia / 32;

            byte[] entropia = RandomNumberGenerator.GetBytes(bitsEntropia / 8);
            byte[] checksum = SHA256.HashData(entropia);

            var bits = new bool[bitsEntropia + bitsChecksum];
            for (int i = 0; i < bitsEntropia; i++)
                bits[i] = ((entropia[i / 8] >> (7 - (i % 8))) & 1) == 1;
            for (int i = 0; i < bitsChecksum; i++)
                bits[bitsEntropia + i] = ((checksum[i / 8] >> (7 - (i % 8))) & 1) == 1;

            var resultado = new List<string>(cantidadPalabras);
            for (int w = 0; w < cantidadPalabras; w++)
            {
                int indice = 0;
                for (int b = 0; b < 11; b++)
                    indice = (indice << 1) | (bits[w * 11 + b] ? 1 : 0);

                resultado.Add(Palabras[indice]);
            }

            return resultado;
        }
    }
}
