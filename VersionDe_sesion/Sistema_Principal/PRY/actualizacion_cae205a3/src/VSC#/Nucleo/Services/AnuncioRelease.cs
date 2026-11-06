using System;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Threading.Tasks;

namespace Visor3D.Services
{
    /// <summary>
    /// Qué anuncia el portal que se puede descargar y desde dónde. Es la única
    /// copia de este estado en el proceso: el nombre, la URL, el tamaño y la
    /// versión del binario vigente.
    ///
    /// Dos fuentes, en este orden:
    ///   1. La release vigente real, consultada a GitHub con el mismo criterio
    ///      que el botón de actualización (<see cref="Visor3D.Update.UpdateChecker"/>).
    ///   2. El <c>release.json</c> empaquetado junto al .exe, y si tampoco lo hay,
    ///      un nombre derivado de la versión del visor en ejecución.
    ///
    /// Se separó de <see cref="WebNodoService"/> porque su ciclo de vida no es el
    /// del nodo HTTP: sobrevive a reinicios del portal y lo leen rutas distintas.
    /// </summary>
    internal static class AnuncioRelease
    {
        /// <summary>
        /// Versión del visor que se ejecuta. Se lee del ensamblado de ENTRADA y no
        /// del de esta librería: <c>WoldVirtualNucleo.dll</c> es común a los dos
        /// visores y no declara versión, así que reportaría 1.0.0 y el portal
        /// anunciaría un binario inexistente (y una versión instalada falsa).
        /// </summary>
        private static string ObtenerVersionEnsamblado()
        {
            var asm = Assembly.GetEntryAssembly() ?? typeof(AnuncioRelease).Assembly;

            var info = asm.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion;
            if (!string.IsNullOrWhiteSpace(info))
            {
                int plus = info.IndexOf('+');
                return (plus >= 0 ? info.Substring(0, plus) : info).Trim();
            }
            // Sin InformationalVersion se usa la Version del ensamblado (2.7.7.0 -> «2.7.7»):
            // ningún literal de versión queda cableado en el código.
            var ver = asm.GetName().Version;
            return ver is null ? "0.0.0" : $"{ver.Major}.{ver.Minor}.{ver.Build}";
        }

        private static string ExeNameFallback => $"DMWoldVirtualP2P3Dv{ObtenerVersionEnsamblado()}.exe";
        private static string ExeUrlFallback =>
            $"https://github.com/Chicook/WoldVirtualP2P3D/releases/download/v{ObtenerVersionEnsamblado()}/{ExeNameFallback}";

        // Valor de arranque: el release.json empaquetado junto al .exe. En cuanto el
        // nodo arranca, Refrescar() lo sustituye por la release vigente real consultada
        // a GitHub.
        private static readonly (string Name, string Url, string SizeMb, string Version) ReleaseLocal = LeerReleaseLocal();
        private static (string Name, string Url, string SizeMb, string Version) ReleaseActiva = ReleaseLocal;
        private static readonly object _releaseLock = new object();

        /// <summary>Consultas a GitHub por sesión antes de rendirse.</summary>
        private const int IntentosRelease = 3;

        /// <summary>Espera entre intentos; crece con cada reintento.</summary>
        private static readonly TimeSpan EsperaReintentoBase = TimeSpan.FromSeconds(5);

        /// <summary>
        /// Intervalo mínimo entre consultas a GitHub. Antes el anuncio se congelaba
        /// toda la vida del proceso; ahora se re-consulta por sesión sin llegar a
        /// agotar el límite de la API al abrir el portal varias veces.
        /// </summary>
        private static readonly TimeSpan IntervaloRefresco = TimeSpan.FromMinutes(5);

        private static DateTime _ultimaConsulta = DateTime.MinValue;
        private static bool _consultaEnCurso;

        internal static string ExeName { get { lock (_releaseLock) return ReleaseActiva.Name; } }
        internal static string ExeUrl { get { lock (_releaseLock) return ReleaseActiva.Url; } }
        internal static string ExeSizeMb { get { lock (_releaseLock) return ReleaseActiva.SizeMb; } }
        internal static string ExeVersion { get { lock (_releaseLock) return ReleaseActiva.Version; } }

        /// <summary>Versión del visor en ejecución (la realmente instalada).</summary>
        internal static string VersionInstalada => ObtenerVersionEnsamblado();

        /// <summary>
        /// Binario del visor que este proceso ejecuta (o null si no se halla).
        /// </summary>
        internal static string? RutaBinarioEnEjecucion => BinarioEnEjecucion();

        /// <summary>
        /// Costura de prueba: lee un <c>release.json</c> concreto sin depender de la
        /// ruta de instalación. La usan <c>--webnodo-selftest</c> y los xUnit para
        /// validar de forma determinista el esquema publicado (<c>{ assets[] }</c>).
        /// </summary>
        internal static (string Name, string Url, string SizeMb, string Version)
            LeerReleaseParaPrueba(string ruta) => LeerReleaseLocal(ruta);

        /// <summary>
        /// Costura de prueba: fija el anuncio del portal y marca la consulta remota
        /// como reciente, de modo que <c>Start()</c> no dispare una consulta a GitHub
        /// a mitad de la autoprueba.
        /// </summary>
        internal static void SembrarReleaseParaPrueba(string nombre, string url, string sizeMb, string version)
        {
            lock (_releaseLock)
            {
                ReleaseActiva = (nombre, url, sizeMb, version);
                _ultimaConsulta = DateTime.UtcNow;
            }
        }

        /// <summary>
        /// Ruta del binario que este proceso está ejecutando: el apphost si se arrancó
        /// directamente, o el <c>.exe</c> junto al ensamblado. Se compara contra el
        /// nombre del ensamblado de entrada, no contra el nombre anunciado, porque tras
        /// un OTA el fichero en disco CONSERVA el nombre antiguo mientras el interior ya
        /// es la versión nueva. Devuelve null si no se encuentra (p. ej. sin apphost).
        /// </summary>
        private static string? BinarioEnEjecucion()
        {
            string? entrada = Assembly.GetEntryAssembly()?.GetName()?.Name;
            if (string.IsNullOrWhiteSpace(entrada)) return null;

            string self = Environment.ProcessPath ?? "";
            if (string.Equals(Path.GetFileNameWithoutExtension(self), entrada, StringComparison.OrdinalIgnoreCase) &&
                File.Exists(self))
                return self;

            string vecino = Path.Combine(AppContext.BaseDirectory, entrada + ".exe");
            return File.Exists(vecino) ? vecino : null;
        }

        /// <summary>
        /// Refresca la release vigente consultando GitHub con el MISMO criterio que
        /// el botón de actualización (UpdateChecker). Sin esto, el portal seguiría
        /// anunciando el binario empaquetado con el visor aunque el OTA ya instaló
        /// uno más nuevo.
        /// Se re-consulta por sesión (con un intervalo mínimo entre consultas) en
        /// lugar de una sola vez por proceso: el anuncio deja de congelarse hasta
        /// reiniciar el visor.
        /// </summary>
        internal static void Refrescar(bool forzar = false)
        {
            lock (_releaseLock)
            {
                if (_consultaEnCurso) return;
                if (!forzar && DateTime.UtcNow - _ultimaConsulta < IntervaloRefresco) return;
                _consultaEnCurso = true;
                _ultimaConsulta = DateTime.UtcNow;
            }

            _ = Task.Run(RefrescarAsync);
        }

        private static async Task RefrescarAsync()
        {
            try
            {
                for (int intento = 1; intento <= IntentosRelease; intento++)
                {
                    try
                    {
                        var info = await new Visor3D.Update.UpdateChecker().GetLatestReleaseAsync();
                        if (info == null || string.IsNullOrWhiteSpace(info.AssetName) ||
                            string.IsNullOrWhiteSpace(info.AssetUrl))
                        {
                            VisorLog.Info("WebNodo: GitHub no informa de release vigente; se mantiene la local.");
                            return;
                        }

                        string mb = info.AssetSize > 0
                            ? (info.AssetSize / 1048576.0).ToString("0.0", CultureInfo.InvariantCulture)
                            : "—";
                        var nueva = (Name: info.AssetName!, Url: info.AssetUrl!, SizeMb: mb,
                                     Version: string.IsNullOrWhiteSpace(info.Version)
                                              ? ObtenerVersionEnsamblado() : info.Version!);
                        lock (_releaseLock) ReleaseActiva = nueva;
                        VisorLog.Info($"WebNodo: release vigente → {nueva.Name} ({nueva.SizeMb} MB, v{nueva.Version})");
                        return;
                    }
                    catch (Exception ex)
                    {
                        if (intento < IntentosRelease)
                        {
                            var espera = TimeSpan.FromSeconds(EsperaReintentoBase.TotalSeconds * intento);
                            VisorLog.Info($"WebNodo: consulta de release falló (intento {intento}/{IntentosRelease}: {ex.Message}); reintento en {espera.TotalSeconds:0} s.");
                            await Task.Delay(espera);
                            continue;
                        }

                        VisorLog.Info($"WebNodo: no se pudo leer la release vigente tras {IntentosRelease} intentos ({ex.Message}); se mantiene la local.");
                    }
                }
            }
            finally
            {
                // Se libera el cerrojo de consulta para que un Start() posterior
                // (reinicio del portal) o el próximo intervalo vuelvan a intentarlo.
                lock (_releaseLock) _consultaEnCurso = false;
            }
        }

        private static (string Name, string Url, string SizeMb, string Version) LeerReleaseLocal(string? ruta = null)
        {
            try
            {
                string path = ruta ?? Path.Combine(AppContext.BaseDirectory, "release.json");
                if (File.Exists(path))
                {
                    using var doc = JsonDocument.Parse(File.ReadAllText(path));
                    var root = doc.RootElement;

                    // Esquema publicado por el pipeline: { tag_name, name, version, assets[] }.
                    string version = root.TryGetProperty("version", out var v) && v.ValueKind == JsonValueKind.String
                        ? (v.GetString() ?? "").Trim()
                        : "";
                    if (string.IsNullOrWhiteSpace(version) &&
                        root.TryGetProperty("tag_name", out var t) && t.ValueKind == JsonValueKind.String)
                        version = (t.GetString() ?? "").Trim().TrimStart('v', 'V');

                    if (root.TryGetProperty("assets", out var assets) && assets.ValueKind == JsonValueKind.Array)
                    {
                        foreach (var asset in assets.EnumerateArray())
                        {
                            string? nombre = asset.TryGetProperty("name", out var n) ? n.GetString() : null;
                            if (string.IsNullOrWhiteSpace(nombre) ||
                                !nombre!.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
                                continue;

                            string? url = asset.TryGetProperty("url", out var u) ? u.GetString() : null;
                            double mb = 0;
                            if (asset.TryGetProperty("size", out var s) && s.TryGetDouble(out var bytes))
                                mb = bytes / 1048576.0;

                            return (nombre!,
                                    string.IsNullOrWhiteSpace(url) ? ExeUrlFallback : url!,
                                    mb > 0 ? mb.ToString("0.0", CultureInfo.InvariantCulture) : "—",
                                    string.IsNullOrWhiteSpace(version) ? ObtenerVersionEnsamblado() : version);
                        }
                    }
                }
                if (File.Exists(path))
                    VisorLog.Info($"WebNodo: release.json en {path} no anuncia un asset .exe; se anuncian los valores del ensamblado.");
            }
            catch (Exception ex)
            {
                // DT-13: el fallo era silencioso (`catch { }`) y el portal anunciaba un binario
                // distinto del que se estaba sirviendo sin dejar rastro. El respaldo es legitimo;
                // callar, no.
                VisorLog.Info($"WebNodo: no se pudo leer release.json ({ex.Message}); se anuncian los valores del ensamblado.");
            }

            return (ExeNameFallback, ExeUrlFallback, "—", ObtenerVersionEnsamblado());
        }
    }
}
