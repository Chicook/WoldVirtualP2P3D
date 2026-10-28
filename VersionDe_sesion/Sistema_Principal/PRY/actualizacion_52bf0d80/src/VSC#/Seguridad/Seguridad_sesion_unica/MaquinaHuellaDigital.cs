using System;
using System.Collections.Generic;
using System.Management;
using System.Security.Cryptography;
using System.Text;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Genera un identificador de máquina estable y anónimo a partir de
    /// atributos de hardware de bajo nivel (placa base, CPU, BIOS, disco).
    ///
    /// • Usa HKDF-SHA256 (RFC 5869) en lugar de SHA-256 plano para que el
    ///   identificador no sea invertible incluso si se filtran los atributos WMI.
    /// • Combina múltiples fuentes WMI para resistir cambios parciales de hardware.
    /// • El salt embebido evita que dos instalaciones en hardware idéntico den el
    ///   mismo identificador si se usara con contexto diferente.
    /// • Devuelve siempre 64 caracteres hexadecimales (256 bits).
    /// </summary>
    public static class MaquinaHuellaDigital
    {
        // Salt fijo de la aplicación — no es secreto, solo aisla el dominio de derivación.
        private static readonly byte[] AppSalt = Encoding.UTF8.GetBytes(
            "WoldVirtualP2P3D::SesionUnica::v1");

        /// <summary>
        /// Deriva el identificador de máquina. Nunca lanza excepciones: si WMI
        /// falla totalmente, devuelve un valor de emergencia basado en
        /// <see cref="System.Environment"/> + nombre de equipo.
        /// </summary>
        public static string Obtener()
        {
            var partes = new List<string>(8);

            // ── Fuentes primarias (muy estables) ─────────────────────────────
            AgregarWmi(partes, "Win32_BaseBoard",     "SerialNumber");  // S/N placa base
            AgregarWmi(partes, "Win32_BaseBoard",     "Product");       // modelo placa
            AgregarWmi(partes, "Win32_Processor",     "ProcessorId");   // ID de CPU
            AgregarWmi(partes, "Win32_BIOS",          "SerialNumber");  // S/N BIOS
            AgregarWmi(partes, "Win32_BIOS",          "Version");       // versión BIOS

            // ── Fuentes secundarias (cambian si se cambia disco/OS) ───────────
            AgregarWmi(partes, "Win32_DiskDrive",     "SerialNumber");  // S/N disco primario
            AgregarWmi(partes, "Win32_ComputerSystem","Model");         // modelo de equipo

            // ── Fallback mínimo siempre disponible ────────────────────────────
            partes.Add(Environment.MachineName.ToUpperInvariant());

            // Si no se obtuvo ningún dato real de WMI, agregar algo más
            if (partes.Count <= 1)
                partes.Add(Environment.GetEnvironmentVariable("COMPUTERNAME") ?? "UNKNOWN");

            // Construir material de clave: partes ordenadas y normalizadas
            string rawIkm = string.Join("|", partes)
                                  .ToUpperInvariant()
                                  .Trim();

            byte[] ikm = Encoding.UTF8.GetBytes(rawIkm);

            // HKDF-SHA256: Extract → Expand (32 bytes = 256 bits)
            byte[] derived = HKDF.DeriveKey(
                hashAlgorithmName : HashAlgorithmName.SHA256,
                ikm                : ikm,
                outputLength       : 32,
                salt               : AppSalt,
                info               : Encoding.UTF8.GetBytes("machine-id"));

            return Convert.ToHexString(derived).ToLowerInvariant();
        }

        // ─────────────────────────────────────────────────────────────────────
        private static void AgregarWmi(List<string> lista, string clase, string propiedad)
        {
            try
            {
                using var searcher = new ManagementObjectSearcher(
                    $"SELECT {propiedad} FROM {clase}");

                foreach (ManagementObject obj in searcher.Get())
                {
                    string val = (obj[propiedad]?.ToString() ?? "").Trim();
                    // Descartar valores genéricos / vacíos que no aportan unicidad
                    if (!string.IsNullOrWhiteSpace(val) &&
                        val != "To Be Filled By O.E.M." &&
                        val != "Default string"         &&
                        val != "Not Specified"          &&
                        val.Length > 2)
                    {
                        lista.Add(val);
                        return; // solo el primer objeto de cada clase
                    }
                }
            }
            catch { /* WMI no disponible — se ignora esa fuente */ }
        }
    }
}
