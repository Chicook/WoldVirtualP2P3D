using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Sello de «una cuenta por equipo» en Linux. Misma estructura y formato que
    /// el sello de Windows (<c>pc_sello.json</c> firmado con HMAC-SHA256), pero
    /// la huella sale de <c>/etc/machine-id</c> en lugar de WMI.
    ///
    /// La clave HMAC no se guarda: se deriva del identificador del equipo, así
    /// que copiar el JSON a otra máquina invalida la firma.
    /// </summary>
    public static class RegistroPcUnico
    {
        private const string RutaMachineId = "/etc/machine-id";
        private const string RutaDbusId = "/var/lib/dbus/machine-id";

        private static readonly byte[] AppSalt = Encoding.UTF8.GetBytes("WoldVirtualP2P3D::SesionUnica::v1");

        private static string SelloDir => Path.Combine(PerfilUsuario.BaseDir, "Seguridad");
        private static string SelloPath => Path.Combine(SelloDir, "pc_sello.json");

        /// <summary>Identificador estable del equipo, derivado con HKDF-SHA256 (64 hex).</summary>
        public static string Obtener()
        {
            string crudo = LeerMachineId() ?? $"linux|{Environment.MachineName}|{Environment.GetFolderPath(Environment.SpecialFolder.UserProfile)}";
            byte[] derivado = HKDF.DeriveKey(
                hashAlgorithmName: HashAlgorithmName.SHA256,
                ikm: Encoding.UTF8.GetBytes(crudo.Trim().ToLowerInvariant()),
                outputLength: 32,
                salt: AppSalt,
                info: Encoding.UTF8.GetBytes("machine-id"));
            return Convert.ToHexString(derivado).ToLowerInvariant();
        }

        public static bool YaExisteCuentaEnEstePc()
        {
            if (!File.Exists(SelloPath)) return false;

            try
            {
                var sello = JsonSerializer.Deserialize<SelloJson>(File.ReadAllText(SelloPath, Encoding.UTF8));
                if (sello == null) return true;

                byte[] esperada = ComputarFirma(sello.maquina_id, sello.uuid, sello.creado);
                byte[] leida;
                try { leida = Convert.FromHexString(sello.firma ?? ""); }
                catch { return true; }

                if (!CryptographicOperations.FixedTimeEquals(esperada, leida))
                    return true; // sello manipulado: no se permite una segunda cuenta

                byte[] actual = Encoding.UTF8.GetBytes(Obtener());
                byte[] guardada = Encoding.UTF8.GetBytes(sello.maquina_id ?? "");
                if (!CryptographicOperations.FixedTimeEquals(actual, guardada))
                    return false; // sello de otro equipo

                return true;
            }
            catch
            {
                return true;
            }
        }

        public static void RegistrarCuenta(string uuid)
        {
            if (YaExisteCuentaEnEstePc())
                throw new InvalidOperationException("Ya existe una cuenta registrada en este equipo.");

            string maquina = Obtener();
            string creado = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
            var sello = new SelloJson
            {
                maquina_id = maquina,
                uuid = uuid,
                creado = creado,
                firma = Convert.ToHexString(ComputarFirma(maquina, uuid, creado)),
                nota = "Sello de cuenta única por equipo — WoldVirtualP2P3D v1 (Linux)"
            };

            Directory.CreateDirectory(SelloDir);
            string json = JsonSerializer.Serialize(sello, new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            });

            string temporal = SelloPath + ".tmp";
            File.WriteAllText(temporal, json, new UTF8Encoding(false));
            File.Move(temporal, SelloPath, overwrite: true);
        }

        public static void EliminarSello()
        {
            try { if (File.Exists(SelloPath)) File.Delete(SelloPath); }
            catch { /* soporte: si no se puede borrar, el aviso lo dará el arranque */ }
        }

        public static string? ObtenerUuidRegistrado()
        {
            try
            {
                if (!File.Exists(SelloPath)) return null;
                var sello = JsonSerializer.Deserialize<SelloJson>(File.ReadAllText(SelloPath, Encoding.UTF8));
                return sello?.uuid;
            }
            catch { return null; }
        }

        private static byte[] ClaveFirma()
        {
            byte[] id = Encoding.UTF8.GetBytes(Obtener());
            return HKDF.DeriveKey(
                hashAlgorithmName: HashAlgorithmName.SHA256,
                ikm: id,
                outputLength: 32,
                salt: Encoding.UTF8.GetBytes("WoldVirtualP2P3D::HmacFirma::v1"),
                info: Encoding.UTF8.GetBytes("sello-firma"));
        }

        private static byte[] ComputarFirma(string? maquina, string? uuid, string? creado)
        {
            using var hmac = new HMACSHA256(ClaveFirma());
            return hmac.ComputeHash(Encoding.UTF8.GetBytes($"{maquina}|{uuid}|{creado}"));
        }

        private static string? LeerMachineId()
        {
            foreach (string ruta in new[] { RutaMachineId, RutaDbusId })
            {
                try
                {
                    if (!File.Exists(ruta)) continue;
                    string texto = File.ReadAllText(ruta).Trim();
                    if (texto.Length > 0) return texto;
                }
                catch { /* sin permiso de lectura: se prueba la siguiente fuente */ }
            }
            return null;
        }

        private sealed class SelloJson
        {
            public string? maquina_id { get; set; }
            public string? uuid { get; set; }
            public string? creado { get; set; }
            public string? firma { get; set; }
            public string? nota { get; set; }
        }
    }
}
