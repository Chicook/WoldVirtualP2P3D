using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Almacena y verifica el registro de "cuenta única por PC".
    ///
    /// Flujo:
    ///   1. Al crear una cuenta, se llama a <see cref="RegistrarCuenta"/>.
    ///      Se serializa un "sello" con el identificador de máquina (HKDF) y
    ///      el UUID del usuario, firmado con HMAC-SHA256 para detectar
    ///      manipulaciones del JSON.
    ///   2. Al abrir <see cref="RegistroWindow"/>, se llama a
    ///      <see cref="YaExisteCuentaEnEstePc"/>. Si devuelve true, se bloquea
    ///      la pantalla de registro.
    ///   3. El sello vive en AppData (no junto al .exe) para persistir aunque
    ///      el usuario borre/mueva el ejecutable.
    ///
    /// Seguridad:
    ///   • El sello es un JSON firmado con HMAC-SHA256. Modificarlo a mano
    ///     invalida la firma y el visor lo detecta (⇒ se trata como sello
    ///     presente pero corrupto → tampoco deja crear cuenta nueva).
    ///   • El identificador de máquina (HKDF) nunca se guarda en texto plano;
    ///     solo se guarda el HMAC del sello completo.
    ///   • La comprobación usa comparación de tiempo constante para evitar
    ///     ataques de timing.
    /// </summary>
    public static class RegistroPcUnico
    {
        // ── Rutas ────────────────────────────────────────────────────────────

        /// <summary>
        /// Directorio donde se guarda el sello. Usar LocalApplicationData
        /// garantiza que persiste entre versiones del visor.
        /// </summary>
        private static readonly string SelloDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WoldVirtualP2P3D", "Seguridad");

        private static string SelloPath => Path.Combine(SelloDir, "pc_sello.json");

        // ── Clave de firma (derivada de la huella + salt fijo) ────────────────
        // La clave HMAC no se guarda en disco: se recalcula siempre desde WMI.
        // Un atacante que copie pc_sello.json a otro PC obtiene una clave HMAC
        // diferente → la firma no coincide → se rechaza.
        private static byte[] ClaveFirma()
        {
            byte[] idBytes = Encoding.UTF8.GetBytes(MaquinaHuellaDigital.Obtener());
            byte[] appSalt = Encoding.UTF8.GetBytes("WoldVirtualP2P3D::HmacFirma::v1");
            return HKDF.DeriveKey(HashAlgorithmName.SHA256, idBytes, 32, appSalt,
                                  Encoding.UTF8.GetBytes("sello-firma"));
        }

        // ─────────────────────────────────────────────────────────────────────
        //  API pública
        // ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// Comprueba si ya existe una cuenta registrada en este PC.
        /// Devuelve true si el sello existe Y es válido para esta máquina.
        /// Si el sello está corrupto/manipulado también devuelve true (no
        /// permite crear una segunda cuenta aunque el sello esté dañado).
        /// </summary>
        public static bool YaExisteCuentaEnEstePc()
        {
            if (!File.Exists(SelloPath)) return false;

            try
            {
                string json = File.ReadAllText(SelloPath, Encoding.UTF8);
                var sello = JsonSerializer.Deserialize<SelloJson>(json);
                if (sello == null) return true; // JSON corrupto → bloqueamos

                // Verificar firma HMAC con comparación de tiempo constante
                byte[] firmaEsperada = ComputarFirma(sello.maquina_id, sello.uuid, sello.creado);
                byte[] firmaLeida    = Convert.FromHexString(sello.firma ?? "");

                if (!CryptographicOperations.FixedTimeEquals(firmaEsperada, firmaLeida))
                    return true; // firma inválida → sello presente pero manipulado → bloqueamos

                // Comprobar que el sello es de ESTA máquina
                // (si lo copiaron de otro PC, el HMAC ya falló; esta es defensa adicional)
                string idActual = MaquinaHuellaDigital.Obtener();
                byte[] idEsperado = Encoding.UTF8.GetBytes(idActual);
                byte[] idGuardado = Encoding.UTF8.GetBytes(sello.maquina_id ?? "");
                if (!CryptographicOperations.FixedTimeEquals(idEsperado, idGuardado))
                    return false; // sello de otra máquina (hardware diferente) → OK crear cuenta

                return true; // sello válido y de esta máquina → bloqueamos
            }
            catch
            {
                // Error leyendo/parseando: sello presente pero ilegible → bloqueamos
                return true;
            }
        }

        /// <summary>
        /// Registra la cuenta recién creada en este PC.
        /// Debe llamarse JUSTO DESPUÉS de que el usuario complete el registro
        /// (al final de <see cref="FormularioUsuarioWindow"/>).
        /// </summary>
        /// <param name="uuid">UUID único del usuario recién creado.</param>
        /// <exception cref="InvalidOperationException">
        /// Si ya existe una cuenta registrada en este PC.
        /// </exception>
        public static void RegistrarCuenta(string uuid)
        {
            if (YaExisteCuentaEnEstePc())
                throw new InvalidOperationException(
                    "Ya existe una cuenta registrada en este equipo.");

            string maquinaId = MaquinaHuellaDigital.Obtener();
            string creado     = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
            string firma      = Convert.ToHexString(ComputarFirma(maquinaId, uuid, creado));

            var sello = new SelloJson
            {
                maquina_id = maquinaId,
                uuid       = uuid,
                creado     = creado,
                firma      = firma,
                nota       = "Sello de cuenta única por PC — WoldVirtualP2P3D v1"
            };

            string json = JsonSerializer.Serialize(sello, new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            });

            Directory.CreateDirectory(SelloDir);
            // Escritura atómica: escribimos a .tmp y luego renombramos
            string tmp = SelloPath + ".tmp";
            File.WriteAllText(tmp, json, Encoding.UTF8);
            File.Move(tmp, SelloPath, overwrite: true);
        }

        /// <summary>
        /// Elimina el sello del PC actual. Solo debe usarse en escenarios
        /// administrados (soporte técnico, reinstalación limpia autorizada).
        /// </summary>
        public static void EliminarSello()
        {
            if (File.Exists(SelloPath))
                File.Delete(SelloPath);
        }

        /// <summary>
        /// Devuelve el UUID guardado en el sello, o null si no hay sello válido.
        /// </summary>
        public static string? ObtenerUuidRegistrado()
        {
            if (!File.Exists(SelloPath)) return null;
            try
            {
                string json = File.ReadAllText(SelloPath, Encoding.UTF8);
                var sello = JsonSerializer.Deserialize<SelloJson>(json);
                return sello?.uuid;
            }
            catch { return null; }
        }

        // ─────────────────────────────────────────────────────────────────────
        //  Helpers privados
        // ─────────────────────────────────────────────────────────────────────

        private static byte[] ComputarFirma(string? maquinaId, string? uuid, string? creado)
        {
            string mensaje = $"{maquinaId}|{uuid}|{creado}";
            byte[] msgBytes = Encoding.UTF8.GetBytes(mensaje);
            using var hmac = new HMACSHA256(ClaveFirma());
            return hmac.ComputeHash(msgBytes);
        }

        // DTO de serialización — campos en snake_case para legibilidad del JSON
        private sealed class SelloJson
        {
            public string? maquina_id { get; set; }
            public string? uuid       { get; set; }
            public string? creado     { get; set; }
            public string? firma      { get; set; }
            public string? nota       { get; set; }
        }
    }
}
