using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using Visor3D.Seguridad.SMTPLC;
using Xunit;

namespace Visor3D.Tests
{
    /// <summary>
    /// Ledger de ubicaciones (F1 del issue #26): sello HMAC, cuota por ubicación, enfriamiento y
    /// fusión de registros externos. Ninguna prueba toca %LOCALAPPDATA% — el camino del ledger se
    /// pasa a mano y vive en un directorio temporal que se borra al terminar.
    ///
    /// Nota medida, no corregida aqui: la clave HMAC se deriva de Environment.MachineName +
    /// Environment.UserName (LocationAccountLedger.DeriveLocalHmacKey). Es predecible para
    /// cualquier proceso del mismo usuario, así que el sello detecta corrupción accidental pero
    /// no resiste a un atacante local. Los casos de abajo afirman contra la conducta real
    /// (fallar cerrado) y dejan la fortaleza como deuda de #26.
    /// </summary>
    public sealed class LedgerPruebas : IDisposable
    {
        private readonly string _carpeta;

        public LedgerPruebas()
        {
            _carpeta = Path.Combine(Path.GetTempPath(), "wvp_ledger_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_carpeta);
        }

        public void Dispose()
        {
            try { Directory.Delete(_carpeta, recursive: true); } catch { }
        }

        private string RutaLedger(string nombre = "ledger.dat") => Path.Combine(_carpeta, nombre);

        private static PhysicalLocationSignature Firma(string cluster, string mac = "AA:BB:CC:DD:EE:01") =>
            new()
            {
                LocationClusterHash = cluster,
                GatewayMacAddress = mac,
                GatewayIp = "192.168.1.1",
                PublicIp = "203.0.113.9",
                PublicSubnetHash = "SUBNET",
                WifiClusterHash = "WIFI",
                DeviceMachineGuid = "GUID",
            };

        private static SmtplcPolicy Politica(int cuota = 1, int enfriamientoMin = 0) =>
            new() { MaxAccountsPerLocation = cuota, CooldownMinutesBetweenAccounts = enfriamientoMin };

        private static LocationAccountLedger ConCuenta(string ruta, string uuid, string cluster)
        {
            var ledger = new LocationAccountLedger(ruta);
            ledger.RecordAccount(uuid, "cuenta-" + uuid, Firma(cluster), "HARDWARE");
            return ledger;
        }

        [Fact]
        public void Registro_scrita_y_leida_por_otra_instancia_se_conserva()
        {
            string ruta = RutaLedger();
            ConCuenta(ruta, "uuid-1", "CLUSTER-A");

            var recargado = new LocationAccountLedger(ruta);
            Assert.Single(recargado.GetAccountsInLocation(Firma("CLUSTER-A")));
        }

        [Fact]
        public void Manipular_el_contenido_deja_el_ledger_vacio()
        {
            string ruta = RutaLedger();
            ConCuenta(ruta, "uuid-2", "CLUSTER-B");

            // Los primeros 32 bytes son el HMAC; el resto es el JSON sellado.
            byte[] bytes = File.ReadAllBytes(ruta);
            bytes[40] ^= 0xFF;
            File.WriteAllBytes(ruta, bytes);

            var manipulada = new LocationAccountLedger(ruta);
            Assert.Empty(manipulada.GetAccountsInLocation(Firma("CLUSTER-B")));
        }

        [Fact]
        public void Archivo_mas_corto_que_el_HMAC_no_rompe_nada()
        {
            string ruta = RutaLedger("roto.dat");
            File.WriteAllBytes(ruta, Encoding.UTF8.GetBytes("trunca"));

            var ledger = new LocationAccountLedger(ruta);
            Assert.Empty(ledger.GetAccountsInLocation(Firma("CLUSTER-C")));
        }

        [Fact]
        public void Cuota_de_una_cuenta_bloquea_la_segunda_en_la_misma_ubicacion()
        {
            string ruta = RutaLedger();
            var ledger = ConCuenta(ruta, "uuid-3", "CLUSTER-D");

            var (permitido, codigo, motivo, conflictos) =
                ledger.EvaluateLocationQuota(Firma("CLUSTER-D"), Politica(cuota: 1));

            Assert.False(permitido);
            Assert.Equal(DenialReasonCode.MultipleAccountsInSameLocation, codigo);
            Assert.Single(conflictos);
            Assert.Contains("límite máximo", motivo);
        }

        [Fact]
        public void Enfriamiento_activo_entre_registros_de_la_misma_ubicacion()
        {
            string ruta = RutaLedger();
            var ledger = ConCuenta(ruta, "uuid-4", "CLUSTER-E");

            var (permitido, codigo, _, _) =
                ledger.EvaluateLocationQuota(Firma("CLUSTER-E"), Politica(cuota: 5, enfriamientoMin: 4320));

            Assert.False(permitido);
            Assert.Equal(DenialReasonCode.LocationCooldownActive, codigo);
        }

        [Fact]
        public void Ubicacion_distinta_no_consume_la_cuota()
        {
            string ruta = RutaLedger();
            var ledger = ConCuenta(ruta, "uuid-5", "CLUSTER-F");

            var (permitido, codigo, _, _) =
                ledger.EvaluateLocationQuota(Firma("CLUSTER-OTRA", mac: "11:22:33:44:55:66"), Politica(cuota: 1));

            Assert.True(permitido);
            Assert.Equal(DenialReasonCode.Allowed, codigo);
        }

        [Fact]
        public void Fusion_externa_no_duplica_uuid_y_sobrevive_a_json_roto()
        {
            string ruta = RutaLedger();
            var ledger = ConCuenta(ruta, "uuid-6", "CLUSTER-G");

            string externo = JsonSerializer.Serialize(new[]
            {
                new LocationAccountRecord { AccountUuid = "uuid-6", AccountName = "duplicada", LocationClusterHash = "CLUSTER-G" },
                new LocationAccountRecord { AccountUuid = "uuid-nueva", AccountName = "ajena", LocationClusterHash = "CLUSTER-H" },
            });

            Assert.Equal(1, ledger.MergeExternalRecords(externo));
            Assert.Equal(0, ledger.MergeExternalRecords("{ esto no es json"));

            // Ojo: GetAccountsInLocation también agrupa por MAC de puerta de enlace, así que para
            // aislar por clúster hay que preguntar con una MAC que no sea la del alta original.
            var otraMac = Firma("CLUSTER-H", mac: "EE:EE:EE:EE:EE:EE");
            Assert.Single(ledger.GetAccountsInLocation(Firma("CLUSTER-G")));
            Assert.Single(ledger.GetAccountsInLocation(otraMac));

            // La fusion se persiste: otra instancia sobre el mismo fichero ve los dos registros.
            // El fichero son 32 bytes de HMAC + payload UTF-8, asi que se corta por bytes, no por
            // caracteres (leer el HMAC como texto descoloca el limite).
            byte[] sellado = File.ReadAllBytes(ruta);
            var relido = new LocationAccountLedger(ruta);
            Assert.Equal(2, JsonSerializer.Deserialize<LocationAccountRecord[]>(
                Encoding.UTF8.GetString(sellado, 32, sellado.Length - 32))?.Length);
            Assert.Single(relido.GetAccountsInLocation(otraMac));
        }

        [Fact]
        public void Exportar_y_fusionar_lleva_el_registro_a_otro_nodo()
        {
            string origen = RutaLedger("origen.dat");
            string destino = RutaLedger("destino.dat");

            string json;
            var emisor = ConCuenta(origen, "uuid-7", "CLUSTER-I");
            json = emisor.ExportJson();

            var receptor = new LocationAccountLedger(destino);
            Assert.Empty(receptor.GetAccountsInLocation(Firma("CLUSTER-I")));
            Assert.Equal(1, receptor.MergeExternalRecords(json));
            Assert.Single(receptor.GetAccountsInLocation(Firma("CLUSTER-I")));
        }

        [Fact]
        public void El_public_IP_viaja_hashed_al_escribirse()
        {
            // #48 F1 y el issue #57 (G4): la IP publica no debe quedar en claro en el archivo.
            string ruta = RutaLedger();
            ConCuenta(ruta, "uuid-8", "CLUSTER-J");

            byte[] sellado = File.ReadAllBytes(ruta);
            string contenido = Encoding.UTF8.GetString(sellado, 32, sellado.Length - 32);
            Assert.DoesNotContain("203.0.113.9", contenido);
            Assert.Contains("PublicIpHash", contenido);
        }
    }
}
