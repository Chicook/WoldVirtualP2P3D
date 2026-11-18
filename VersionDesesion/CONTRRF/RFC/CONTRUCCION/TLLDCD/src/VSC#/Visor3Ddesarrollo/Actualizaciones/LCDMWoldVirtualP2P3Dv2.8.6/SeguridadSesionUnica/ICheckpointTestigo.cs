// =============================================================================
// ICheckpointTestigo.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Checkpoints Canónicos y Contratos de Testigos Futuros (P2P)
// =============================================================================

using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Seguridad.SesionUnica
{
    public sealed record FirmaTestigo(
        [property: JsonPropertyName("testigoId")] string TestigoId,
        [property: JsonPropertyName("clavePublicaSpki")] string ClavePublicaSpki,
        [property: JsonPropertyName("timestampUtc")] long TimestampUtc,
        [property: JsonPropertyName("firmaBase64")] string FirmaBase64);

    /// <summary>
    /// Modelo canónico de un Checkpoint de la cadena local para atestación futura o P2P.
    /// Define un punto de control inmutable firmado por el nodo y cofirmado por testigos.
    /// </summary>
    public sealed class CheckpointCanonico
    {
        public const string OriginCanonico = "WoldVirtualP2P3D::NodeLocal::v3";

        [JsonPropertyName("origin")]
        public string Origin { get; set; } = OriginCanonico;

        [JsonPropertyName("idCuentaHash")]
        public string IdCuentaHash { get; set; } = "";

        [JsonPropertyName("tamanioCadena")]
        public long TamanioCadena { get; set; } = 0;

        [JsonPropertyName("hashCabeza")]
        public string HashCabeza { get; set; } = "";

        [JsonPropertyName("contadorMonotonico")]
        public long ContadorMonotonico { get; set; } = 0;

        [JsonPropertyName("timestampUtc")]
        public long TimestampUtc { get; set; } = DateTimeOffset.UtcNow.ToUnixTimeSeconds();

        [JsonPropertyName("keyId")]
        public string KeyId { get; set; } = "k1_ecdsa_p256";

        [JsonPropertyName("firmaEcdsa")]
        public string FirmaEcdsa { get; set; } = "";

        [JsonPropertyName("cofirmasTestigos")]
        public List<FirmaTestigo> CofirmasTestigos { get; set; } = new();

        /// <summary>
        /// Representación canónica delimitada para cálculo determinista de hash y firma.
        /// </summary>
        public string ObtenerTextoCanonico()
        {
            return $"ORIGIN:{Origin}|ID:{IdCuentaHash}|LEN:{TamanioCadena}|HEAD:{HashCabeza}|" +
                   $"CNT:{ContadorMonotonico}|TS:{TimestampUtc}|KEY:{KeyId}";
        }

        public byte[] ObtenerBytesCanonicos() => Encoding.UTF8.GetBytes(ObtenerTextoCanonico());

        public void FirmarNodo(ECDsa clavePrivada)
        {
            byte[] payload = ObtenerBytesCanonicos();
            byte[] sig = clavePrivada.SignData(payload, HashAlgorithmName.SHA256);
            FirmaEcdsa = Convert.ToBase64String(sig);
        }

        public bool VerificarFirmaNodo(string clavePublicaSpkiBase64)
        {
            if (string.IsNullOrWhiteSpace(FirmaEcdsa)) return false;
            try
            {
                byte[] payload = ObtenerBytesCanonicos();
                byte[] sig = Convert.FromBase64String(FirmaEcdsa);
                return ProveedorClaves.VerificarFirma(payload, sig, clavePublicaSpkiBase64);
            }
            catch
            {
                return false;
            }
        }

        public string Serializar() =>
            JsonSerializer.Serialize(this, new JsonSerializerOptions { WriteIndented = true });
    }

    public sealed record ResultadoAtestacionCheckpoint(
        bool Exitoso,
        string TestigoId,
        FirmaTestigo? Firma,
        string Mensaje);

    /// <summary>
    /// Contrato de testigo independiente para verificar frescura y prevenir bifurcaciones en fase P2P.
    /// NOTA DE ARQUITECTURA: En la fase actual (100% offline), no se abren sockets ni conexiones de red.
    /// </summary>
    public interface ICheckpointTestigo
    {
        string TestigoId { get; }
        Task<ResultadoAtestacionCheckpoint> AtestarCheckpointAsync(
            CheckpointCanonico checkpoint,
            CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Simulador local en memoria de testigo para pruebas de quórum y cofirmas.
    /// No abre sockets de red. Documentado explícitamente: una co-firma simulada local
    /// NO otorga frescura externa real ni mitiga un rollback del sistema operativo local.
    /// </summary>
    public sealed class SimuladorTestigoLocal : ICheckpointTestigo, IDisposable
    {
        private readonly ECDsa _claveTestigo;
        private readonly string _spkiBase64;

        public string TestigoId { get; }

        public SimuladorTestigoLocal(string testigoId = "simulador_testigo_local_01")
        {
            TestigoId = testigoId;
            _claveTestigo = ECDsa.Create(ECCurve.NamedCurves.nistP256);
            _spkiBase64 = Convert.ToBase64String(_claveTestigo.ExportSubjectPublicKeyInfo());
        }

        public Task<ResultadoAtestacionCheckpoint> AtestarCheckpointAsync(
            CheckpointCanonico checkpoint,
            CancellationToken cancellationToken = default)
        {
            if (checkpoint == null || string.IsNullOrWhiteSpace(checkpoint.HashCabeza))
            {
                return Task.FromResult(new ResultadoAtestacionCheckpoint(
                    Exitoso: false,
                    TestigoId: TestigoId,
                    Firma: null,
                    Mensaje: "Checkpoint inválido o sin cabeza de cadena."));
            }

            // Simular firma de atestación del checkpoint
            byte[] payload = checkpoint.ObtenerBytesCanonicos();
            byte[] sig = _claveTestigo.SignData(payload, HashAlgorithmName.SHA256);
            long now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();

            var firma = new FirmaTestigo(
                TestigoId: TestigoId,
                ClavePublicaSpki: _spkiBase64,
                TimestampUtc: now,
                FirmaBase64: Convert.ToBase64String(sig));

            return Task.FromResult(new ResultadoAtestacionCheckpoint(
                Exitoso: true,
                TestigoId: TestigoId,
                Firma: firma,
                Mensaje: "Atestación simulada local generada con éxito (Aviso: no sustituye a testigo de red externo)."));
        }

        public void Dispose()
        {
            _claveTestigo.Dispose();
        }
    }
}
