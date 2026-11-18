// =============================================================================
// VerificadorSello.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Motor de Verificación, Cadena Local y Política de 3 Niveles (v3)
// =============================================================================

using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;

namespace Visor3D.Seguridad.SesionUnica
{
    public enum EstadoVerificacionSello
    {
        Valido,
        AutorreparadoDesdeArchivo,
        AutorreparadoDesdeRegistro,
        CadenaIntegraRequiereConfirmacionRiesgo,
        RollbackDetectado,
        BloqueadoRequiereRecuperacion,
        BloqueadoPorExcesoIntentos,
        SinSelloNuevoRegistro,
        CadenaCorrupta
    }

    public sealed record ResultadoRevision(
        EstadoVerificacionSello Estado,
        SelloCuenta? SelloActivo,
        string MensajeAuditoria);

    public sealed record ResultadoVerificacionCadena(
        bool Integra,
        int BloquesVerificados,
        SelloCuenta? Cabeza,
        string Mensaje,
        bool HuboRecuperacionInterrupcion);

    /// <summary>
    /// Motor de validación y política de recuperación de tres niveles:
    ///   - Nivel 1: Existe un anclaje válido -> autorreparación automática sin código.
    ///   - Nivel 2: Faltan anclajes pero cadena íntegra -> evaluación difusa de hardware (3/5)
    ///              como señal de riesgo; requiere confirmación para evitar elevación no autorizada.
    ///   - Nivel 3: Pérdida total o máquina alterada -> exige código Base32 con comparación
    ///              en tiempo constante, rotación de bloque e invalidación de código anterior.
    ///   - Anti-rollback: arbitraje de testigos y detección estricta de retroceso.
    /// </summary>
    public static class VerificadorSello
    {
        public static ResultadoRevision EvaluarMatrizSeguridad()
        {
            if (AlmacenSeguro.EstaBloqueadoPorBackoff(out long segs))
            {
                return new ResultadoRevision(
                    EstadoVerificacionSello.BloqueadoPorExcesoIntentos,
                    null,
                    $"Recuperación bloqueada por intentos fallidos recurrentes. Reintentar en {segs}s.");
            }

            // Comprobar endurecimiento de proceso
            var estadoProc = EndurecimientoProceso.Diagnosticar();
            if (estadoProc.DepuradorPresente)
            {
                AuditoriaSeguridad.Registrar(
                    EventoAuditoria.ErrorCritico,
                    "VerificadorSello",
                    "DepuradorDetectado",
                    estadoProc.Diagnostico);
            }

            byte[] secretoHmac = AlmacenSeguro.ObtenerOcrearSecretoMaestro();
            byte[] huellaBytes = Encoding.UTF8.GetBytes(MaquinaHuellaDigital.Obtener());
            var provClaves = ProveedorClaves.Instancia;
            var claveEcdsa = provClaves.ObtenerOCrearClaveEcdsa();

            try
            {
                string? jsonArchivo = AlmacenSeguro.LeerAnclajeArchivo();
                string? jsonRegistro = AlmacenSeguro.LeerAnclajeRegistro();
                long contadorHistorico = AlmacenSeguro.LeerUltimoContadorRegistro();

                // Soporte de migración transparente si se detecta sello v1
                if (jsonArchivo != null && SelloCuenta.EsFormatoV1(jsonArchivo))
                {
                    var migrado = SelloCuenta.MigrarDesdeV1(jsonArchivo, claveEcdsa, huellaBytes, out string codigoBase32);
                    AlmacenSeguro.GuardarDualV3(migrado, claveEcdsa, huellaBytes);
                    AuditoriaSeguridad.Registrar(EventoAuditoria.NuevoRegistro, "VerificadorSello", "MigradoV1aV3",
                        $"Código de recuperación generado por migración: {codigoBase32[..7]}…");
                    jsonArchivo = migrado.Serializar();
                }

                SelloCuenta? selloArchivo = jsonArchivo != null ? SelloCuenta.Deserializar(jsonArchivo) : null;
                SelloCuenta? selloRegistro = jsonRegistro != null ? SelloCuenta.Deserializar(jsonRegistro) : null;

                bool archivoValido = selloArchivo != null && selloArchivo.VerificarAutenticidad(secretoHmac, huellaBytes, claveEcdsa);
                bool registroValido = selloRegistro != null && selloRegistro.VerificarAutenticidad(secretoHmac, huellaBytes, claveEcdsa);

                // Caso 0: Sin anclajes ni historial previo
                if (selloArchivo == null && selloRegistro == null && contadorHistorico == 0)
                {
                    var resCadena = VerificarCadenaLocal(secretoHmac, huellaBytes, claveEcdsa);
                    if (resCadena.BloquesVerificados == 0)
                    {
                        return new ResultadoRevision(EstadoVerificacionSello.SinSelloNuevoRegistro, null, "Equipo libre para registro 1:1.");
                    }
                }

                // ── NIVEL 1: Existe al menos un anclaje válido ─────────────────
                if (archivoValido && registroValido && selloArchivo != null && selloRegistro != null)
                {
                    // Arbitraje anti-rollback con matriz de testigos
                    long contadorDisco = selloArchivo.Contador;
                    long contadorReg = selloRegistro.Contador;
                    var arb = ArbitroTestigosContador.Arbitrar(
                        contadorDisco,
                        contadorHistorico,
                        contadorReg,
                        contadorDisco);

                    if (arb.RollbackDetectado)
                    {
                        return new ResultadoRevision(EstadoVerificacionSello.RollbackDetectado, null, arb.Diagnostico);
                    }

                    if (selloArchivo.Contador != selloRegistro.Contador ||
                        selloArchivo.IdCuentaHash != selloRegistro.IdCuentaHash)
                    {
                        return new ResultadoRevision(EstadoVerificacionSello.RollbackDetectado, null,
                            "Incoherencia de estado entre anclajes duales.");
                    }

                    // Coincidencia difusa de hardware (señal de riesgo)
                    var hwActual = MaquinaHuellaDigital.ObtenerComponentes().ObtenerLista();
                    if (!MaquinaHuellaDigital.CoincideFuzzy(selloArchivo.ComponentesHardware, hwActual, umbral: 3))
                    {
                        return new ResultadoRevision(EstadoVerificacionSello.BloqueadoRequiereRecuperacion, null,
                            "Discrepancia mayor en hardware del equipo (<3 de 5 componentes). Requiere recuperación.");
                    }

                    // Migración transparente v2 -> v3 si procede
                    if (selloArchivo.VersionFormato == 2)
                    {
                        var migradoV3 = SelloCuenta.MigrarDesdeV2(selloArchivo, claveEcdsa, huellaBytes);
                        AlmacenSeguro.GuardarDualV3(migradoV3, claveEcdsa, huellaBytes);
                        selloArchivo = migradoV3;
                    }

                    return new ResultadoRevision(EstadoVerificacionSello.Valido, selloArchivo,
                        "Sello de anclaje dual coherente y validado.");
                }

                if (archivoValido && selloArchivo != null && !registroValido)
                {
                    // Nivel 1: Autorreparar hacia registro
                    if (selloArchivo.VersionFormato >= 3)
                        AlmacenSeguro.GuardarDualV3(selloArchivo, claveEcdsa, huellaBytes);
                    else
                        AlmacenSeguro.GuardarDual(selloArchivo, secretoHmac, huellaBytes);

                    AuditoriaSeguridad.Registrar(EventoAuditoria.SelloAutorreparado, "VerificadorSello", "RegistroReparado");
                    return new ResultadoRevision(EstadoVerificacionSello.AutorreparadoDesdeArchivo, selloArchivo,
                        "Anclaje de registro HKCU autorreparado desde archivo local.");
                }

                if (registroValido && selloRegistro != null && !archivoValido)
                {
                    // Nivel 1: Autorreparar hacia archivo
                    if (selloRegistro.VersionFormato >= 3)
                        AlmacenSeguro.GuardarDualV3(selloRegistro, claveEcdsa, huellaBytes);
                    else
                        AlmacenSeguro.GuardarDual(selloRegistro, secretoHmac, huellaBytes);

                    AuditoriaSeguridad.Registrar(EventoAuditoria.SelloAutorreparado, "VerificadorSello", "ArchivoReparado");
                    return new ResultadoRevision(EstadoVerificacionSello.AutorreparadoDesdeRegistro, selloRegistro,
                        "Archivo local autorreparado desde anclaje protegido DPAPI.");
                }

                // ── NIVEL 2: Faltan ambos anclajes, pero la cadena local está íntegra ──
                var cadena = VerificarCadenaLocal(secretoHmac, huellaBytes, claveEcdsa);
                if (!cadena.Integra && cadena.BloquesVerificados > 0)
                {
                    AuditoriaSeguridad.Registrar(EventoAuditoria.ManipulacionDetectada, "VerificadorSello", "CadenaCorrupta", cadena.Mensaje);
                    return new ResultadoRevision(EstadoVerificacionSello.CadenaCorrupta, null,
                        $"Cadena local manipulada o corrupta: {cadena.Mensaje}");
                }

                if (cadena.Integra && cadena.Cabeza != null)
                {
                    var hwActual = MaquinaHuellaDigital.ObtenerComponentes().ObtenerLista();
                    bool hwCoincide = MaquinaHuellaDigital.CoincideFuzzy(cadena.Cabeza.ComponentesHardware, hwActual, umbral: 3);

                    if (hwCoincide)
                    {
                        return new ResultadoRevision(
                            EstadoVerificacionSello.CadenaIntegraRequiereConfirmacionRiesgo,
                            cadena.Cabeza,
                            "Anclajes ausentes. Cadena local íntegra y hardware coincidente (3/5). Confirmación requerida.");
                    }
                }

                // ── NIVEL 3: Pérdida total o discrepancia crítica ──────────────
                return new ResultadoRevision(
                    EstadoVerificacionSello.BloqueadoRequiereRecuperacion,
                    cadena.Cabeza,
                    "Anclajes ausentes o discrepancia de hardware. Se requiere código de recuperación Base32.");
            }
            finally
            {
                CryptographicOperations.ZeroMemory(secretoHmac);
            }
        }

        /// <summary>
        /// Ejecuta el proceso de recuperación de Nivel 3 utilizando el código Base32 del usuario.
        /// Valida en tiempo constante, rota el bloque generando nuevo código e invalida el anterior.
        /// </summary>
        public static (bool ok, string nuevoCodigoBase32, string mensaje) EjecutarRecuperacionNivel3(
            string idCuentaHash,
            string codigoBase32)
        {
            if (AlmacenSeguro.EstaBloqueadoPorBackoff(out long segsRestantes))
            {
                return (false, string.Empty, $"Sistema bloqueado por intentos fallidos. Espere {segsRestantes} segundos.");
            }

            if (string.IsNullOrWhiteSpace(codigoBase32))
            {
                AlmacenSeguro.RegistrarFalloRecuperacionPersistente();
                return (false, string.Empty, "Código de recuperación no proporcionado.");
            }

            byte[] secretoHmac = AlmacenSeguro.ObtenerOcrearSecretoMaestro();
            byte[] huellaBytes = Encoding.UTF8.GetBytes(MaquinaHuellaDigital.Obtener());
            var provClaves = ProveedorClaves.Instancia;
            var claveEcdsa = provClaves.ObtenerOCrearClaveEcdsa();

            try
            {
                var cadena = VerificarCadenaLocal(secretoHmac, huellaBytes, claveEcdsa);
                SelloCuenta? cabeza = cadena.Cabeza;

                if (cabeza == null)
                {
                    string? json = AlmacenSeguro.LeerAnclajeArchivo() ?? AlmacenSeguro.LeerAnclajeRegistro();
                    if (json != null) cabeza = SelloCuenta.Deserializar(json);
                }

                if (cabeza == null || string.IsNullOrWhiteSpace(cabeza.CompromisoRecuperacion))
                {
                    AlmacenSeguro.RegistrarFalloRecuperacionPersistente();
                    return (false, string.Empty, "No existe registro de compromiso de recuperación previo.");
                }

                // Validación criptográfica en tiempo constante
                bool valido = SelloCuenta.VerificarCodigoRecuperacion(codigoBase32, cabeza.Salt, cabeza.CompromisoRecuperacion);
                if (!valido)
                {
                    AlmacenSeguro.RegistrarFalloRecuperacionPersistente();
                    AuditoriaSeguridad.Registrar(EventoAuditoria.BloqueoCuenta, "VerificadorSello", "CodigoRecuperacionInvalido");
                    return (false, string.Empty, "Código de recuperación inválido o checksum erróneo.");
                }

                // Éxito: Reiniciar backoff de fallos
                AlmacenSeguro.ReiniciarBloqueoRecuperacion();

                // Generar nuevo código de recuperación y nueva sal para el nuevo ciclo
                SelloCuenta.GenerarNuevoParRecuperacion(
                    out byte[] rawCode,
                    out string nuevaSalt,
                    out string nuevoCompromiso,
                    out string nuevoCodigoBase32);

                CryptographicOperations.ZeroMemory(rawCode);

                long nuevoContador = Math.Max(cabeza.Contador + 1, AntiRollbackGuardia.ObtenerContadorActual() + 1);
                var hwLista = MaquinaHuellaDigital.ObtenerComponentes().ObtenerLista();

                var nuevoBloque = new SelloCuenta
                {
                    VersionFormato = SelloCuenta.VersionActual,
                    IdCuentaHash = cabeza.IdCuentaHash,
                    Indice = cabeza.Indice + 1,
                    HashPrevio = cabeza.HashBloque,
                    Contador = nuevoContador,
                    TimestampUtc = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
                    HuellaAnonimizada = MaquinaHuellaDigital.Obtener(),
                    Salt = nuevaSalt,
                    CompromisoRecuperacion = nuevoCompromiso,
                    KeyId = "k1_ecdsa_p256",
                    ComponentesHardware = new List<string>(hwLista),
                    Nota = "Bloque de Recuperación de Nivel 3 v3 — WoldVirtualP2P3D"
                };

                nuevoBloque.FirmarEcdsa(claveEcdsa, huellaBytes);

                // Guardar en anclajes duales y cadena local
                AlmacenSeguro.GuardarDualV3(nuevoBloque, claveEcdsa, huellaBytes);
                AntiRollbackGuardia.IncrementarContador(nuevoContador, secretoHmac);

                AuditoriaSeguridad.Registrar(EventoAuditoria.RecuperacionSolicitada, "VerificadorSello", "ExitoNivel3",
                    $"Cuenta={cabeza.IdCuentaHash[..Math.Min(8, cabeza.IdCuentaHash.Length)]}… NuevoBloqueIndice={nuevoBloque.Indice}");

                return (true, nuevoCodigoBase32, "Recuperación completada con éxito. Guarde su nuevo código.");
            }
            finally
            {
                CryptographicOperations.ZeroMemory(secretoHmac);
            }
        }

        /// <summary>
        /// Verifica la cadena local completa de principio a fin soportando bloques v2 y v3.
        /// Si detecta una interrupción final en la escritura (crash recovery), repara truncando
        /// los bytes no confirmados sin tocar los bloques válidos.
        /// Si detecta manipulación en un bloque confirmado, reporta fallo íntegro sin autorreparación silenciosa.
        /// </summary>
        public static ResultadoVerificacionCadena VerificarCadenaLocal(
            byte[] secretoClave,
            byte[] huellaBytes,
            ECDsa? claveEcdsa = null)
        {
            var bloques = AlmacenSeguro.LeerCadenaCompleta(out bool huboInterrupcion);
            if (bloques.Count == 0)
            {
                return new ResultadoVerificacionCadena(true, 0, null, "Cadena local vacía.", huboInterrupcion);
            }

            string hashEsperadoAnterior = new string('0', 64);
            long contadorAnterior = 0;

            for (int i = 0; i < bloques.Count; i++)
            {
                var b = bloques[i];

                if (b.Indice != i)
                {
                    return new ResultadoVerificacionCadena(false, i, null,
                        $"Discrepancia de índice en bloque {i}: esperado {i}, encontrado {b.Indice}.", huboInterrupcion);
                }

                if (i > 0 && !string.Equals(b.HashPrevio, hashEsperadoAnterior, StringComparison.OrdinalIgnoreCase))
                {
                    return new ResultadoVerificacionCadena(false, i, null,
                        $"Ruptura de encadenamiento en bloque {i}: HashPrevio no coincide con bloque anterior.", huboInterrupcion);
                }

                if (b.Contador < contadorAnterior)
                {
                    return new ResultadoVerificacionCadena(false, i, null,
                        $"Retroceso de contador en bloque {i}: {b.Contador} < {contadorAnterior}.", huboInterrupcion);
                }

                // Verificar firma (ECDSA para v3, HMAC para v2)
                if (!b.VerificarAutenticidad(secretoClave, huellaBytes, claveEcdsa))
                {
                    return new ResultadoVerificacionCadena(false, i, null,
                        $"Firma o autenticidad inválida en bloque {i} (Versión {b.VersionFormato}).", huboInterrupcion);
                }

                hashEsperadoAnterior = b.HashBloque;
                contadorAnterior = b.Contador;
            }

            var cabeza = bloques[^1];
            return new ResultadoVerificacionCadena(true, bloques.Count, cabeza, "Cadena íntegra y confirmada.", huboInterrupcion);
        }
    }
}
