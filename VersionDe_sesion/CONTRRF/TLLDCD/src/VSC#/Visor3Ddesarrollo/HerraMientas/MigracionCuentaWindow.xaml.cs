using System;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;
using Microsoft.Win32;
using Visor3D.Seguridad;

namespace Visor3D
{
    /// <summary>
    /// Migración de cuenta (F9): sustituye la llave de acceso, el hash del registro
    /// del PC y la frase semilla por un único hash de cuenta generado por un bloque
    /// privado de la blockchain local (POST /alta-cuenta). El hash se entrega en un
    /// .zip con cuenta.json y sirve en este PC o en cualquier otro desde el que el
    /// jugador se conecte.
    /// </summary>
    public partial class MigracionCuentaWindow : Window
    {
        private const string BksvcbAlta = "http://127.0.0.1:8545/alta-cuenta";

        private readonly string _nick;
        private string _cuentaHash = "";

        public MigracionCuentaWindow()
        {
            InitializeComponent();

            _nick = LeerNickLegado();

            this.Loaded += OnLoaded;
            BtnMigrar.Click += OnMigrarClicked;
            BtnDescargarZip.Click += OnDescargarZipClicked;
            BtnCerrar.Click += OnCerrarClicked;
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            TxtNick.Text = string.IsNullOrWhiteSpace(_nick) ? "(sin cuenta antigua detectada)" : _nick;
            if (string.IsNullOrWhiteSpace(_nick))
            {
                TxtEstado.Text = "No se encontró llave_acceso.json en este PC. Si ya usas la nueva arquitectura, tu cuenta.json ya existe.";
                BtnMigrar.IsEnabled = false;
            }
        }

        private void OnCerrarClicked(object sender, RoutedEventArgs e) => Close();

        private async void OnMigrarClicked(object sender, RoutedEventArgs e)
        {
            if (string.IsNullOrWhiteSpace(_nick)) return;

            string huella = ObtenerHuellaLocal();
            if (string.IsNullOrWhiteSpace(huella))
            {
                TxtEstado.Text = "No se pudo obtener la huella local del equipo (identidad Godot).";
                return;
            }

            BtnMigrar.IsEnabled = false;
            TxtEstado.Text = "Solicitando el bloque de cuenta a la blockchain local…";

            try
            {
                using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
                var payload = JsonSerializer.Serialize(new { nick = _nick, huella, ubicacion_hash = LeerUbicacionHash() });
                using var content = new StringContent(payload, Encoding.UTF8, "application/json");
                using var resp = await http.PostAsync(BksvcbAlta, content);
                string cuerpo = await resp.Content.ReadAsStringAsync();

                using var doc = JsonDocument.Parse(cuerpo);
                var root = doc.RootElement;

                if ((int)resp.StatusCode != 201)
                {
                    string error = root.TryGetProperty("error", out var er) ? er.GetString() ?? "" : "respuesta inválida";
                    TxtEstado.Text = $"La blockchain rechazó la migración ({(int)resp.StatusCode}): {error}";
                    BtnMigrar.IsEnabled = true;
                    return;
                }

                _cuentaHash = root.TryGetProperty("cuenta_hash", out var ch) ? ch.GetString() ?? "" : "";
                if (string.IsNullOrWhiteSpace(_cuentaHash))
                {
                    TxtEstado.Text = "La cadena no devolvió un hash de cuenta.";
                    BtnMigrar.IsEnabled = true;
                    return;
                }

                GuardarCuentaLocal();
                TxtHashCuenta.Text = _cuentaHash;
                TxtEstado.Text = "✔ Cuenta migrada. Descarga el .zip con tu hash único y guárdalo en un lugar seguro.";
                BtnDescargarZip.IsEnabled = true;
            }
            catch (Exception ex)
            {
                TxtEstado.Text = $"No se pudo contactar con la blockchain local (127.0.0.1:8545): {ex.Message}";
                BtnMigrar.IsEnabled = true;
            }
        }

        private void OnDescargarZipClicked(object sender, RoutedEventArgs e)
        {
            if (string.IsNullOrWhiteSpace(_cuentaHash)) return;

            var dialog = new SaveFileDialog
            {
                Title = "Guardar hash único de cuenta (.zip)",
                FileName = $"cuenta_{_nick}_{_cuentaHash[..8]}.zip",
                DefaultExt = ".zip",
                Filter = "Archivo ZIP (*.zip)|*.zip"
            };

            if (dialog.ShowDialog() != true) return;

            try
            {
                CrearZipCuenta(dialog.FileName);
                MessageBox.Show(
                    $"Hash único de cuenta guardado en:\n{dialog.FileName}",
                    "Cuenta exportada", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al exportar el .zip:\n{ex.Message}",
                                "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        /// <summary>Lee el nick de la cuenta antigua desde llave_acceso.json.</summary>
        private static string LeerNickLegado()
        {
            try
            {
                if (!File.Exists(PerfilUsuario.LlavePath)) return "";
                using var doc = JsonDocument.Parse(File.ReadAllText(PerfilUsuario.LlavePath));
                var root = doc.RootElement;
                return root.TryGetProperty("usuario", out var u) ? u.GetString() ?? "" : "";
            }
            catch { return ""; }
        }

        /// <summary>
        /// Huella local = identidad Godot (uuid de registro.cfg). Es la misma que usa
        /// el alta nueva desde Godot, para que la cuota «un bloque por PC» coincida.
        /// </summary>
        private static string ObtenerHuellaLocal()
        {
            string uuid = LeerUuidGodot();
            if (string.IsNullOrEmpty(uuid))
            {
                uuid = Convert.ToHexString(RandomNumberGenerator.GetBytes(16)).ToLowerInvariant();
                AsegurarUuidGodot(uuid);
            }
            return uuid;
        }

        /// <summary>
        /// Hash de ubicación SMTPLC que el visor dejó al arrancar en el user:// del
        /// motor (ubicacion_smtplc.json). Vacío si falta o no es un SHA-256 de 64 hex:
        /// el servidor aplica entonces solo la cuota «un bloque por PC».
        /// </summary>
        private static string LeerUbicacionHash()
        {
            try
            {
                string ruta = Path.Combine(EstadoGlobal.MotorDir, "ubicacion_smtplc.json");
                if (!File.Exists(ruta)) return "";
                using var doc = JsonDocument.Parse(File.ReadAllText(ruta));
                string h = doc.RootElement.TryGetProperty("ubicacion_hash", out var v) ? v.GetString() ?? "" : "";
                h = h.Trim();
                return h.Length == 64 && h.All(EsHex) ? h.ToLowerInvariant() : "";
            }
            catch { return ""; }
        }

        private static string LeerUuidGodot()
        {
            string ruta = Path.Combine(EstadoGlobal.MotorDir, "registro.cfg");
            if (!File.Exists(ruta)) return "";
            bool enIdentidad = false;
            foreach (var linea in File.ReadAllLines(ruta))
            {
                var l = linea.Trim();
                if (l.StartsWith("[") && l.EndsWith("]"))
                {
                    enIdentidad = l.Equals("[identidad]", StringComparison.OrdinalIgnoreCase);
                    continue;
                }
                if (!enIdentidad || !l.StartsWith("uuid", StringComparison.OrdinalIgnoreCase)) continue;
                int idx = l.IndexOf('=');
                if (idx < 0) continue;
                var valor = l[(idx + 1)..].Trim().Trim('"');
                if (valor.Length == 32 && valor.All(EsHex)) return valor;
            }
            return "";
        }

        /// <summary>Escribe el uuid de identidad en registro.cfg sin tocar el resto del fichero.</summary>
        private static void AsegurarUuidGodot(string uuid)
        {
            string ruta = Path.Combine(EstadoGlobal.MotorDir, "registro.cfg");
            Directory.CreateDirectory(EstadoGlobal.MotorDir);
            var lineas = File.Exists(ruta) ? File.ReadAllLines(ruta).ToList() : new System.Collections.Generic.List<string>();

            int idxIdentidad = lineas.FindIndex(l => l.Trim().Equals("[identidad]", StringComparison.OrdinalIgnoreCase));
            if (idxIdentidad < 0)
            {
                if (lineas.Count > 0 && lineas[^1].Trim().Length > 0) lineas.Add("");
                lineas.Add("[identidad]");
                idxIdentidad = lineas.Count - 1;
            }

            int idxUuid = -1;
            for (int i = idxIdentidad + 1; i < lineas.Count; i++)
            {
                var l = lineas[i].Trim();
                if (l.StartsWith("[") && l.EndsWith("]")) break;
                if (l.StartsWith("uuid", StringComparison.OrdinalIgnoreCase) && l.Contains('='))
                { idxUuid = i; break; }
            }

            string nueva = $"uuid=\"{uuid}\"";
            if (idxUuid >= 0) lineas[idxUuid] = nueva;
            else lineas.Insert(idxIdentidad + 1, nueva);

            File.WriteAllLines(ruta, lineas, Encoding.UTF8);
        }

        /// <summary>Escribe cuenta.json en el user:// del motor y en el perfil C#.</summary>
        private void GuardarCuentaLocal()
        {
            var datos = new
            {
                nick = _nick,
                cuenta_hash = _cuentaHash,
                red = "WoldVirtualP2P3D",
                fecha_alta = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
            };
            string json = JsonSerializer.Serialize(datos, new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            });

            Directory.CreateDirectory(PerfilUsuario.UserDir);
            File.WriteAllText(Path.Combine(PerfilUsuario.UserDir, "cuenta.json"), json, Encoding.UTF8);

            Directory.CreateDirectory(EstadoGlobal.MotorDir);
            File.WriteAllText(Path.Combine(EstadoGlobal.MotorDir, "cuenta.json"), json, Encoding.UTF8);
        }

        private void CrearZipCuenta(string rutaZip)
        {
            string json = JsonSerializer.Serialize(new
            {
                nick = _nick,
                cuenta_hash = _cuentaHash,
                red = "WoldVirtualP2P3D",
                fecha_alta = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
            }, new JsonSerializerOptions { WriteIndented = true });

            using var fs = new FileStream(rutaZip, FileMode.Create, FileAccess.Write);
            using var zip = new ZipArchive(fs, ZipArchiveMode.Create);
            var entrada = zip.CreateEntry("cuenta.json", CompressionLevel.Optimal);
            using var sw = new StreamWriter(entrada.Open(), new UTF8Encoding(false));
            sw.Write(json);
        }

        private static bool EsHex(char c) =>
            (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
    }
}
