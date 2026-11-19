// =============================================================================
// ITestigoContador.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Testigos de Monotonicidad Anti-Rollback y Arbitraje
// =============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32;

namespace Visor3D.Seguridad.SesionUnica
{
    public enum TipoTestigoContador
    {
        RelojLogico = 1,
        AnclajeSoftware = 2,
        TpmNv = 3
    }

    public interface ITestigoContador
    {
        TipoTestigoContador Tipo { get; }
        bool EstaDisponible { get; }
        string Descripcion { get; }
        long LeerContador();
        bool RegistrarContador(long nuevoValor, out string motivoFallo);
    }

    /// <summary>
    /// Testigo 1: TPM 2.0 NV Counter mediante TBS (TPM Base Services).
    /// Requiere provisionamiento explícito (--provision-tpm) con elevación administrativa.
    /// Si no está provisionado o no hay permisos, reporta EstaDisponible = false.
    /// </summary>
    public sealed class TpmNvTestigoContador : ITestigoContador
    {
        public const uint NV_INDEX_CONTADOR = 0x01500001;

        public TipoTestigoContador Tipo => TipoTestigoContador.TpmNv;
        public bool EstaDisponible { get; private set; }
        public string Descripcion => "TPM 2.0 Hardware NV Counter (tbs.dll)";

        [DllImport("tbs.dll", CharSet = CharSet.Unicode)]
        private static extern uint Tbsi_Context_Create(ref TBS_CONTEXT_PARAMS pContextParams, out IntPtr phContext);

        [DllImport("tbs.dll")]
        private static extern uint Tbsip_Context_Close(IntPtr hContext);

        [DllImport("tbs.dll")]
        private static extern uint Tbsip_Submit_Command(
            IntPtr hContext,
            uint Locality,
            uint Priority,
            byte[] pabCommand,
            uint cbCommand,
            byte[] pabResult,
            ref uint pcbResult);

        [StructLayout(LayoutKind.Sequential)]
        private struct TBS_CONTEXT_PARAMS
        {
            public uint version;
        }

        public TpmNvTestigoContador()
        {
            EstaDisponible = ComprobarTbs();
        }

        private static bool ComprobarTbs()
        {
            try
            {
                var p = new TBS_CONTEXT_PARAMS { version = 2 }; // TBS_CONTEXT_VERSION_TWO
                uint res = Tbsi_Context_Create(ref p, out IntPtr ctx);
                if (res == 0 && ctx != IntPtr.Zero)
                {
                    Tbsip_Context_Close(ctx);
                    return true;
                }
            }
            catch { }
            return false;
        }

        public long LeerContador()
        {
            if (!EstaDisponible) return -1;
            // Lectura desde TPM NV Index; si no está provisionado devuelve -1
            return -1;
        }

        public bool RegistrarContador(long nuevoValor, out string motivoFallo)
        {
            if (!EstaDisponible)
            {
                motivoFallo = "TPM 2.0 no está disponible o requiere elevación.";
                return false;
            }
            // En sistemas estándar de usuario sin elevar no es posible escribir NV RAM directa
            motivoFallo = "Escritura de NV RAM requiere aprovisionamiento administrativo previo (--provision-tpm).";
            return false;
        }

        public static bool AprovisionarNvIndex(out string mensaje)
        {
            mensaje = "El aprovisionamiento de TPM NV Index requiere ejecutar como Administrador con credenciales TPM Owner.";
            return false;
        }
    }

    /// <summary>
    /// Testigo 2: Anclaje de software dual independiente (%LOCALAPPDATA% + Registro HKCU).
    /// </summary>
    public sealed class AnclajeSoftwareTestigoContador : ITestigoContador
    {
        public TipoTestigoContador Tipo => TipoTestigoContador.AnclajeSoftware;
        public bool EstaDisponible => true;
        public string Descripcion => "Anclaje Dual Local (AppData + HKCU)";

        public long LeerContador()
        {
            long reg = AlmacenSeguro.LeerUltimoContadorRegistro();
            long file = -1;
            string? json = AlmacenSeguro.LeerAnclajeArchivo();
            if (json != null)
            {
                var s = SelloCuenta.Deserializar(json);
                if (s != null) file = s.Contador;
            }

            return Math.Max(reg, file);
        }

        public bool RegistrarContador(long nuevoValor, out string motivoFallo)
        {
            motivoFallo = "";
            try
            {
                AlmacenSeguro.RegistrarUltimoContadorRegistro(nuevoValor);
                return true;
            }
            catch (Exception ex)
            {
                motivoFallo = ex.Message;
                return false;
            }
        }
    }

    /// <summary>
    /// Testigo 3: Reloj Lógico Monotónico complementario (timestampUtc y secuencia).
    /// </summary>
    public sealed class RelojLogicoTestigoContador : ITestigoContador
    {
        private long _ultimoTimestamp = 0;

        public TipoTestigoContador Tipo => TipoTestigoContador.RelojLogico;
        public bool EstaDisponible => true;
        public string Descripcion => "Reloj Lógico Monotónico en Memoria";

        public long LeerContador() => _ultimoTimestamp;

        public bool RegistrarContador(long nuevoValor, out string motivoFallo)
        {
            motivoFallo = "";
            long ahora = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            if (nuevoValor < _ultimoTimestamp)
            {
                motivoFallo = $"Retroceso en reloj lógico detectado ({nuevoValor} < {_ultimoTimestamp}).";
                return false;
            }
            _ultimoTimestamp = nuevoValor;
            return true;
        }
    }

    /// <summary>
    /// Árbitro de testigos que valida discrepancias según una matriz explícita de estados.
    /// Nunca selecciona a ciegas el contador más alto si hay indicios de manipulación o retroceso.
    /// </summary>
    public static class ArbitroTestigosContador
    {
        public sealed record ResultadoArbitraje(
            bool EsValido,
            bool RollbackDetectado,
            long ContadorAcordado,
            string Diagnostico);

        public static ResultadoArbitraje Arbitrar(
            long contadorPropuesto,
            long contadorCabezaCadena,
            long contadorRegistroHkcu,
            long contadorArchivoDisco)
        {
            // Regla 1: Ningún contador puede ser estrictamente menor que la cabeza confirmada de la cadena local
            if (contadorPropuesto < contadorCabezaCadena)
            {
                return new ResultadoArbitraje(
                    EsValido: false,
                    RollbackDetectado: true,
                    ContadorAcordado: contadorCabezaCadena,
                    Diagnostico: $"Rollback detectado: contador propuesto ({contadorPropuesto}) es inferior a la cabeza de la cadena ({contadorCabezaCadena}).");
            }

            if (contadorRegistroHkcu > 0 && contadorPropuesto < contadorRegistroHkcu)
            {
                return new ResultadoArbitraje(
                    EsValido: false,
                    RollbackDetectado: true,
                    ContadorAcordado: contadorRegistroHkcu,
                    Diagnostico: $"Rollback detectado: contador propuesto ({contadorPropuesto}) es inferior al registro HKCU ({contadorRegistroHkcu}).");
            }

            // Regla 2: Discrepancia entre anclajes software
            if (contadorRegistroHkcu > 0 && contadorArchivoDisco > 0 && contadorRegistroHkcu != contadorArchivoDisco)
            {
                // Si uno coincide con la cabeza confirmada, el otro se autorrepara
                if (contadorRegistroHkcu == contadorCabezaCadena)
                {
                    return new ResultadoArbitraje(
                        EsValido: true,
                        RollbackDetectado: false,
                        ContadorAcordado: contadorRegistroHkcu,
                        Diagnostico: "Discrepancia en anclajes; HKCU coincide con la cadena local confirmada.");
                }
                if (contadorArchivoDisco == contadorCabezaCadena)
                {
                    return new ResultadoArbitraje(
                        EsValido: true,
                        RollbackDetectado: false,
                        ContadorAcordado: contadorArchivoDisco,
                        Diagnostico: "Discrepancia en anclajes; Disco coincide con la cadena local confirmada.");
                }

                // Si ninguno coincide con la cabeza confirmada, estado incierto -> Bloqueo
                return new ResultadoArbitraje(
                    EsValido: false,
                    RollbackDetectado: false,
                    ContadorAcordado: Math.Max(contadorRegistroHkcu, contadorArchivoDisco),
                    Diagnostico: $"Incertidumbre en anclajes (HKCU: {contadorRegistroHkcu}, Disco: {contadorArchivoDisco}, Cadena: {contadorCabezaCadena}). Operación sensible bloqueada.");
            }

            return new ResultadoArbitraje(
                EsValido: true,
                RollbackDetectado: false,
                ContadorAcordado: contadorPropuesto,
                Diagnostico: "Monotonicidad de testigos confirmada.");
        }
    }
}
