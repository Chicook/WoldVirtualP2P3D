// =============================================================================
// SeguridadSelfTest.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Suite Integral de Pruebas de Seguridad y Resiliencia (v3)
// =============================================================================

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using Visor3D.Services;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Suite de autodiagnóstico integral para el subsistema Zero Trust y la cadena local.
    /// Ejecutable mediante Visor3D --seguridad-selftest.
    /// </summary>
    public static class SeguridadSelfTest
    {
        public static int Run()
        {
            var salida = new StringBuilder();
            int fallos = 0;

            void Check(string nombre, bool ok, string detalle = "")
            {
                if (!ok) fallos++;
                string linea = $"[{(ok ? "OK" : "FALLO")}] {nombre}" +
                               (string.IsNullOrWhiteSpace(detalle) ? "" : $" — {detalle}");
                salida.AppendLine(linea);
                VisorLog.Info($"[seguridad-selftest] {linea}");
            }

            VisorLog.Info("[seguridad-selftest] Iniciando suite exhaustiva de seguridad y cadena local v3...");

            // ── Test 1: Manipulación de firma HMAC (Tampering) ─────────────────
            try
            {
                byte[] secreto = new byte[32];
                RandomNumberGenerator.Fill(secreto);
                byte[] huella = Encoding.UTF8.GetBytes("test-machine-fingerprint-123");

                var bloque = new SelloCuenta
                {
                    VersionFormato = 2,
                    IdCuentaHash = "acc-test-1",
                    Indice = 0,
                    Contador = 1
                };

                bloque.FirmarHmac(secreto, huella);
                bool firmaValida = bloque.VerificarMac(secreto, huella);

                // Modificar MAC
                bloque.Mac = "ff" + bloque.Mac.Substring(2);
                bool firmaInvalida = !bloque.VerificarMac(secreto, huella);

                Check("HMAC_Tampering_Deteccion", firmaValida && firmaInvalida, "Detección exacta de MAC alterado");
                CryptographicOperations.ZeroMemory(secreto);
            }
            catch (Exception ex)
            {
                Check("HMAC_Tampering_Deteccion", false, ex.Message);
            }

            // ── Test 2: Codificador Base32 con Checksum Crockford ─────────────
            try
            {
                byte[] datos = new byte[32];
                RandomNumberGenerator.Fill(datos);

                string codificado = CodificadorBase32.CodificarConChecksum(datos);
                byte[]? decodificado = CodificadorBase32.DecodificarConChecksum(codificado);

                bool match = decodificado != null && CryptographicOperations.FixedTimeEquals(datos, decodificado);

                // Probar rechazo con alteración garantizada de bits de datos
                char first = codificado[0];
                char replacement = (first == 'A') ? 'B' : 'A';
                string alterado = replacement + codificado.Substring(1);
                byte[]? decAlterado = CodificadorBase32.DecodificarConChecksum(alterado);

                string diag = $"match={match}, decNull={decodificado == null}, altNull={decAlterado == null}";
                Check("Base32_Checksum_Validacion", match && decAlterado == null, $"Codificación y verificación de checksum en Base32 ({diag})");
                CryptographicOperations.ZeroMemory(datos);
                if (decodificado != null) CryptographicOperations.ZeroMemory(decodificado);
            }
            catch (Exception ex)
            {
                Check("Base32_Checksum_Validacion", false, ex.Message);
            }

            // ── Test 3: Coincidencia difusa de Hardware (3 de 5 y 2 de 5) ──────
            try
            {
                var original = new List<string> { "mb_1", "cpu_1", "bios_1", "disk_1", "guid_1" };
                var con3 = new List<string> { "mb_1", "cpu_1", "nuevo_bios", "nuevo_disk", "guid_1" };
                var con2 = new List<string> { "mb_1", "nuevo_cpu", "nuevo_bios", "nuevo_disk", "guid_1" };

                bool acepta3 = MaquinaHuellaDigital.CoincideFuzzy(original, con3, umbral: 3);
                bool rechaza2 = !MaquinaHuellaDigital.CoincideFuzzy(original, con2, umbral: 3);

                Check("Hardware_CoincidenciaDifusa", acepta3 && rechaza2, "3/5 aceptado como señal de riesgo, 2/5 rechazado");
            }
            catch (Exception ex)
            {
                Check("Hardware_CoincidenciaDifusa", false, ex.Message);
            }

            // ── Test 4: Recuperación Nivel 3 con código correcto e incorrecto ───
            try
            {
                SelloCuenta.GenerarNuevoParRecuperacion(
                    out byte[] rawCode,
                    out string saltHex,
                    out string compromisoHex,
                    out string base32Legible);

                bool validaBien = SelloCuenta.VerificarCodigoRecuperacion(base32Legible, saltHex, compromisoHex);
                bool rechazaMal = !SelloCuenta.VerificarCodigoRecuperacion("ABCDEF-GHIJKL-MNOPQR", saltHex, compromisoHex);

                Check("Recuperacion_Nivel3_Codigo", validaBien && rechazaMal, "Validación de compromiso de código Base32");
                CryptographicOperations.ZeroMemory(rawCode);
            }
            catch (Exception ex)
            {
                Check("Recuperacion_Nivel3_Codigo", false, ex.Message);
            }

            // ── Test 5: Persistencia de Bloqueo por Backoff ───────────────────
            try
            {
                AlmacenSeguro.ReiniciarBloqueoRecuperacion();
                bool noBloqueadoInicial = !AlmacenSeguro.EstaBloqueadoPorBackoff(out _);

                AlmacenSeguro.RegistrarFalloRecuperacionPersistente();
                AlmacenSeguro.RegistrarFalloRecuperacionPersistente();
                AlmacenSeguro.RegistrarFalloRecuperacionPersistente();
                AlmacenSeguro.RegistrarFalloRecuperacionPersistente();

                bool bloqueado = AlmacenSeguro.EstaBloqueadoPorBackoff(out long segsRestantes);
                AlmacenSeguro.ReiniciarBloqueoRecuperacion();

                Check("Recuperacion_BackoffPersistente", noBloqueadoInicial && bloqueado && segsRestantes > 0,
                    $"Backoff persistente activo ({segsRestantes}s)");
            }
            catch (Exception ex)
            {
                Check("Recuperacion_BackoffPersistente", false, ex.Message);
            }

            // ── Test 6: Detección de Rollback (Contador retrocedido) ───────────
            try
            {
                byte[] secreto = new byte[32];
                RandomNumberGenerator.Fill(secreto);

                AntiRollbackGuardia.IncrementarContador(20, secreto);
                var retroceso = AntiRollbackGuardia.VerificarNoRetroceso(15, secreto);

                Check("AntiRollback_RetrocesoContador", retroceso == ResultadoAntiRollback.ContadorRetrocedido,
                    "Contador inferior bloqueado como rollback");
                CryptographicOperations.ZeroMemory(secreto);
            }
            catch (Exception ex)
            {
                Check("AntiRollback_RetrocesoContador", false, ex.Message);
            }

            // ── Test 7: Firma ECDSA P-256 v3 y Verificación con Clave Pública ──
            try
            {
                using var ecdsa = ECDsa.Create(ECCurve.NamedCurves.nistP256);
                byte[] huella = Encoding.UTF8.GetBytes("hw-fingerprint-v3");

                var bloqueV3 = new SelloCuenta
                {
                    VersionFormato = 3,
                    IdCuentaHash = "acc-v3-test",
                    Indice = 0,
                    Contador = 1
                };

                bloqueV3.FirmarEcdsa(ecdsa, huella);
                bool ecdsaValida = bloqueV3.VerificarEcdsa(huella);

                // Modificar firma
                bloqueV3.FirmaEcdsa = Convert.ToBase64String(Encoding.UTF8.GetBytes("firma_falsa_manipulada"));
                bool ecdsaInvalida = !bloqueV3.VerificarEcdsa(huella);

                Check("ECDSA_P256_FirmaYVerificacion", ecdsaValida && ecdsaInvalida, "Firma ECDSA P-256 válida y rechazo de alteración");
            }
            catch (Exception ex)
            {
                Check("ECDSA_P256_FirmaYVerificacion", false, ex.Message);
            }

            // ── Test 8: Migración Transparente v1 -> v2 -> v3 ──────────────────
            try
            {
                string jsonV1 = "{\"maquina_id\":\"wmi_hash_v1\",\"uuid\":\"user-uuid-legacy-1234\",\"creado\":\"2026-01-01\",\"firma\":\"112233\"}";
                using var ecdsa = ECDsa.Create(ECCurve.NamedCurves.nistP256);
                byte[] huella = Encoding.UTF8.GetBytes("test-hw-migracion");

                var bloqueV3 = SelloCuenta.MigrarDesdeV1(jsonV1, ecdsa, huella, out string code32);
                bool migradoV3Ok = bloqueV3.VersionFormato == 3 &&
                                   bloqueV3.VerificarEcdsa(huella) &&
                                   !string.IsNullOrWhiteSpace(code32);

                Check("Migracion_Sello_V1_a_V3", migradoV3Ok, "Migración directa de formato legado v1 a bloque v3 con ECDSA");
            }
            catch (Exception ex)
            {
                Check("Migracion_Sello_V1_a_V3", false, ex.Message);
            }

            // ── Test 9: Proveedor de Claves por Capacidades y Fallback ─────────
            try
            {
                var prov = ProveedorClaves.Instancia;
                var nivel = prov.NivelActivo;
                string spki = prov.ObtenerClavePublicaSpkiBase64();

                byte[] payload = Encoding.UTF8.GetBytes("test-payload-cng-dpapi");
                byte[] firma = prov.FirmarPayload(payload);
                bool verifOk = ProveedorClaves.VerificarFirma(payload, firma, spki);

                Check("ProveedorClaves_Capacidades", verifOk && !string.IsNullOrWhiteSpace(spki),
                    $"Nivel activo: {nivel} ({prov.MotivoDegradacion})");
            }
            catch (Exception ex)
            {
                Check("ProveedorClaves_Capacidades", false, ex.Message);
            }

            // ── Test 10: Endurecimiento de Proceso y Diagnóstico de Depurador ──
            try
            {
                EndurecimientoProceso.AplicarMitigaciones();
                var estadoProc = EndurecimientoProceso.Diagnosticar();
                bool procOk = estadoProc != null && !string.IsNullOrWhiteSpace(estadoProc.Diagnostico);

                Check("EndurecimientoProceso_Mitigaciones", procOk,
                    $"DEP={estadoProc.DepHabilitado}|DllSearch={estadoProc.DllSearchRestringido}|Depurador={estadoProc.DepuradorPresente}");
            }
            catch (Exception ex)
            {
                Check("EndurecimientoProceso_Mitigaciones", false, ex.Message);
            }

            // ── Test 11: Árbitro de Testigos Anti-Rollback ─────────────────────
            try
            {
                // Caso A: Rollback evidente
                var arbRollback = ArbitroTestigosContador.Arbitrar(
                    contadorPropuesto: 5,
                    contadorCabezaCadena: 10,
                    contadorRegistroHkcu: 10,
                    contadorArchivoDisco: 10);

                // Caso B: Normal
                var arbNormal = ArbitroTestigosContador.Arbitrar(
                    contadorPropuesto: 11,
                    contadorCabezaCadena: 10,
                    contadorRegistroHkcu: 10,
                    contadorArchivoDisco: 10);

                bool arbitrajeOk = arbRollback.RollbackDetectado && arbNormal.EsValido && !arbNormal.RollbackDetectado;
                Check("ArbitroTestigos_Rollback", arbitrajeOk, "Arbitraje de discrepancias en testigos y rechazo de retroceso");
            }
            catch (Exception ex)
            {
                Check("ArbitroTestigos_Rollback", false, ex.Message);
            }

            // ── Test 12: Checkpoint Canónico y Simulador de Testigo P2P ────────
            try
            {
                var cp = new CheckpointCanonico
                {
                    IdCuentaHash = "acc-checkpoint-01",
                    TamanioCadena = 5,
                    HashCabeza = new string('a', 64),
                    ContadorMonotonico = 5
                };

                using var claveNodo = ECDsa.Create(ECCurve.NamedCurves.nistP256);
                string spkiNodo = Convert.ToBase64String(claveNodo.ExportSubjectPublicKeyInfo());
                cp.FirmarNodo(claveNodo);
                bool nodoValido = cp.VerificarFirmaNodo(spkiNodo);

                using var testigo = new SimuladorTestigoLocal("testigo_p2p_simulado");
                var resAtestacion = testigo.AtestarCheckpointAsync(cp).GetAwaiter().GetResult();
                bool atestacionOk = resAtestacion.Exitoso && resAtestacion.Firma != null;

                Check("CheckpointCanonico_Y_TestigoP2P", nodoValido && atestacionOk, "Firma de checkpoint y co-firma de testigo simulado");
            }
            catch (Exception ex)
            {
                Check("CheckpointCanonico_Y_TestigoP2P", false, ex.Message);
            }

            // ── Test 13: Cifrado y Descifrado Autenticado AES-GCM (256 bits) ───
            try
            {
                byte[] claveAes = new byte[32];
                RandomNumberGenerator.Fill(claveAes);
                byte[] secretoClaro = Encoding.UTF8.GetBytes("estado_sensible_usuario_p2p_lucia");

                byte[] cipher = AlmacenSeguro.CifrarDatosSensibles(secretoClaro, claveAes, out byte[] nonce, out byte[] tag);
                byte[] recovered = AlmacenSeguro.DescifrarDatosSensibles(cipher, claveAes, nonce, tag);

                bool aesOk = CryptographicOperations.FixedTimeEquals(secretoClaro, recovered);
                Check("Cifrado_AesGcm_DatosSensibles", aesOk, "Cifrado y descifrado autenticado AES-GCM con verificación de tag");
                CryptographicOperations.ZeroMemory(claveAes);
                CryptographicOperations.ZeroMemory(secretoClaro);
                CryptographicOperations.ZeroMemory(recovered);
            }
            catch (Exception ex)
            {
                Check("Cifrado_AesGcm_DatosSensibles", false, ex.Message);
            }

            // ── Test 14: Rendimiento de Huella: SMBIOS Nativo y Caché ──────────
            try
            {
                var sw = Stopwatch.StartNew();
                string huella1 = MaquinaHuellaDigital.Obtener();
                sw.Stop();
                double tFrioMs = sw.Elapsed.TotalMilliseconds;

                sw.Restart();
                string huella2 = MaquinaHuellaDigital.Obtener();
                sw.Stop();
                double tCalienteMs = sw.Elapsed.TotalMilliseconds;

                bool cacheOk = string.Equals(huella1, huella2, StringComparison.Ordinal) && tCalienteMs < 0.1;
                Check("Rendimiento_Huella_Cache", cacheOk,
                    $"Huella caliente: {tCalienteMs:F4}ms (Frío inicial: {tFrioMs:F2}ms)");
            }
            catch (Exception ex)
            {
                Check("Rendimiento_Huella_Cache", false, ex.Message);
            }

            string resumen = fallos == 0 ? "RESULTADO SEGURIDAD: OK (14/14 superadas)" : $"RESULTADO SEGURIDAD: {fallos} FALLO(S)";
            salida.AppendLine(resumen);
            Console.WriteLine(salida.ToString());
            VisorLog.Info($"[seguridad-selftest] {resumen}");

            try
            {
                string localLog = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "seguridad-selftest.log");
                File.WriteAllText(localLog, salida.ToString(), Encoding.UTF8);
            }
            catch { }

            try
            {
                Directory.CreateDirectory(VisorLog.Carpeta);
                File.WriteAllText(Path.Combine(VisorLog.Carpeta, "seguridad-selftest.log"), salida.ToString(), Encoding.UTF8);
            }
            catch { }

            return fallos == 0 ? 0 : 1;
        }
    }
}
