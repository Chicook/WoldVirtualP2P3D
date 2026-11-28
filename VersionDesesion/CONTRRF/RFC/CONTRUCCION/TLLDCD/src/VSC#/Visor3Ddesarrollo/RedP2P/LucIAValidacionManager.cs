using System;                      // Tipos base / Base types (Action, Console, IDisposable)
using System.IO;                   // Archivos y rutas / Files and paths
using System.Text.Json;            // Serialización JSON / JSON serialization
using System.Threading;            // CancellationTokenSource
using System.Threading.Tasks;      // Task, Task.Run, Task.Delay

namespace Visor3D.RedP2P
{
    /// <summary>
    /// ES: Gestor de conexión P2P con LucIA — v2.9.3.
    ///     Lucía es el HOST del túnel efímero. Al llamar a Iniciar() se arrancan
    ///     dos túneles (isla/WebNodo y DAO). Cuando cada túnel obtiene su URL pública,
    ///     se escribe un archivo JSON en user:// que Godot lee por polling.
    ///
    /// EN: P2P connection manager for LucIA — v2.9.3.
    ///     Lucía is the HOST of the ephemeral tunnel. Calling Iniciar() starts two
    ///     tunnels (island/WebNode and DAO). When each tunnel gets its public URL,
    ///     a JSON file is written to user:// which Godot reads by polling.
    ///
    /// Flujo / Flow:
    ///   C# arranca → IniciarAsync() → túnel SSH → URL pública → archivo JSON
    ///   Godot polling → lee JSON → botón "CONECTAR" muestra URL → "CONECTADO"
    /// </summary>
    public class LucIAValidacionManager : IDisposable
    {
        // ES: Carpeta user:// de Godot y ruta del JSON del túnel principal.
        // EN: Godot's user:// folder and path of the main tunnel's JSON.
        private readonly string _godotUserDir;
        private readonly string _rutaTunelUrl;

        // ES: Rutas del flujo antiguo (compatibilidad); ya no se usan en el flujo principal.
        // EN: Legacy-flow paths (compatibility); no longer used by the main flow.
        private readonly string _rutaValidacion;
        private readonly string _rutaResultado;

        // ES: Vigila el archivo legado de solicitud de validación.
        // EN: Watches the legacy validation-request file.
        private FileSystemWatcher? _watcherLegado;

        // ES: Gestor del túnel principal (isla / WebNodo, puerto 8545).
        // EN: Main tunnel manager (island / WebNode, port 8545).
        private P2PTunnelManager? _tunnelManager;

        // ES: Gestor del túnel Cloudflare de la DAO (puerto 8766).
        // EN: Cloudflare tunnel manager for the DAO (port 8766).
        private P2PTunnelManager? _tunnelManagerDao;
        private readonly string   _rutaTunelDaoUrl;

        // ES: Token para cancelar operaciones en segundo plano.
        // EN: Token to cancel background operations.
        private CancellationTokenSource? _cts;

        // ES: Indica si el objeto ya fue liberado.
        // EN: Indicates whether the object has already been disposed.
        private bool _disposeado;

        // ES: Candado para proteger el estado compartido entre hilos.
        // EN: Lock protecting state shared between threads.
        private readonly object _sync = new();

        /// <summary>
        /// ES: Se dispara cuando el túnel obtiene (o pierde) URL pública.
        ///     bool = éxito, string = mensaje.
        /// EN: Raised when the tunnel gets (or loses) its public URL.
        ///     bool = success, string = message.
        /// </summary>
        public event Action<bool, string>? ValidacionCompletada;

        /// <summary>
        /// ES: Ruta del directorio user:// de Godot en Windows (%APPDATA%/Godot/app_userdata/...).
        /// EN: Path of Godot's user:// directory on Windows (%APPDATA%/Godot/app_userdata/...).
        /// </summary>
        public static string GodotUserDir => Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "Godot", "app_userdata", "WoldVirtualP2P3D");

        /// <summary>
        /// ES: Constructor: calcula todas las rutas y crea la carpeta si no existe.
        /// EN: Constructor: computes all paths and creates the folder if missing.
        /// </summary>
        public LucIAValidacionManager()
        {
            _godotUserDir    = GodotUserDir;
            _rutaTunelUrl    = Path.Combine(_godotUserDir, "tunel_lucia_url.json");
            _rutaTunelDaoUrl = Path.Combine(_godotUserDir, "tunel_dao_url.json");
            _rutaValidacion  = Path.Combine(_godotUserDir, "validacion_conexion.json");
            _rutaResultado   = Path.Combine(_godotUserDir, "validacion_resultado.json");

            Directory.CreateDirectory(_godotUserDir);
        }

        /// <summary>
        /// ES: Inicia los túneles efímeros (Lucía = HOST). Es idempotente: si ya hay
        ///     un túnel activo, no hace nada.
        /// EN: Starts the ephemeral tunnels (Lucía = HOST). Idempotent: if a tunnel
        ///     is already active, it does nothing.
        /// </summary>
        public void Iniciar()
        {
            lock (_sync)
            {
                // ES: Salir si ya se liberó o ya hay túnel. / EN: Exit if disposed or already running.
                if (_disposeado || _tunnelManager != null) return;

                Console.WriteLine($"[LucIAValidacion] Iniciando túnel HOST (Lucía) en {_godotUserDir}");

                _cts = new CancellationTokenSource();

                // ES: Túnel principal en el puerto 8545 (servidor blockchain, el mismo
                //     puerto por defecto de P2PTunnelManager).
                // EN: Main tunnel on port 8545 (blockchain server, same default port
                //     as P2PTunnelManager).
                _tunnelManager = new P2PTunnelManager(puertoLocal: 8545);

                // ES: Al obtener URL pública → escribir JSON para Godot y avisar al suscriptor.
                // EN: On public URL → write JSON for Godot and notify the subscriber.
                _tunnelManager.UrlObtenida += url =>
                {
                    Console.WriteLine($"[LucIAValidacion] Túnel HOST activo: {url}");
                    EscribirTunelUrl(true, url, $"Túnel WebNodo activo: {url}");
                    ValidacionCompletada?.Invoke(true, $"Túnel WebNodo activo: {url}");
                };

                // ES: Si el túnel cae → marcarlo inactivo en el JSON y avisar.
                // EN: If the tunnel dies → mark it inactive in the JSON and notify.
                _tunnelManager.TunnelMuerto += host =>
                {
                    Console.WriteLine($"[LucIAValidacion] Túnel HOST caído ({host}), reconectando…");
                    EscribirTunelUrl(false, "", $"Reconectando túnel (host: {host})…");
                    ValidacionCompletada?.Invoke(false, $"Túnel desconectado (host: {host})");
                };

                // ES: Ejecutar el bucle del túnel en segundo plano (sin bloquear).
                // EN: Run the tunnel loop in the background (non-blocking).
                _ = Task.Run(() => _tunnelManager.IniciarAsync());

                // ── Túnel Cloudflare de la DAO (puerto 8766) ──────────────────
                // ES: Mismo cloudflared, otro puerto → URL pública propia de la DAO.
                //     Godot la lee desde user://tunel_dao_url.json.
                // EN: Same cloudflared, different port → the DAO's own public URL.
                //     Godot reads it from user://tunel_dao_url.json.
                _tunnelManagerDao = new P2PTunnelManager(puertoLocal: 8766);

                _tunnelManagerDao.UrlObtenida += url =>
                {
                    Console.WriteLine($"[LucIAValidacion] Túnel DAO activo: {url}");
                    EscribirTunelDaoUrl(true, url, $"DAO activa: {url}");
                };

                _tunnelManagerDao.TunnelMuerto += host =>
                {
                    Console.WriteLine($"[LucIAValidacion] Túnel DAO caído ({host}), reconectando…");
                    EscribirTunelDaoUrl(false, "", $"Reconectando DAO (host: {host})…");
                };

                _ = Task.Run(() => _tunnelManagerDao.IniciarAsync());
                // ─────────────────────────────────────────────────────────────

                // ES: Mantener el watcher legado por compatibilidad con versiones anteriores.
                // EN: Keep the legacy watcher for backward compatibility.
                _IniciarWatcherLegado();
            }
        }

        /// <summary>
        /// ES: Escribe user://tunel_lucia_url.json con el estado del túnel principal.
        ///     Godot lo lee cada 0.5 s desde _poll_conexion().
        /// EN: Writes user://tunel_lucia_url.json with the main tunnel's state.
        ///     Godot reads it every 0.5 s from _poll_conexion().
        /// </summary>
        private void EscribirTunelUrl(bool exito, string url, string mensaje)
        {
            try
            {
                // ES: Construir el objeto con estado, URL, mensaje y hora UNIX.
                // EN: Build the object with state, URL, message and UNIX time.
                var resultado = new TunelLuciaUrl
                {
                    Exito   = exito,
                    Url     = url,
                    Mensaje = mensaje,
                    Timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
                };

                // ES: Escritura atómica: archivo temporal + renombrar, para que Godot
                //     nunca lea un archivo a medio escribir.
                // EN: Atomic write: temp file + rename, so Godot never reads a
                //     half-written file.
                string temporal = _rutaTunelUrl + ".tmp";
                string json = JsonSerializer.Serialize(resultado, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(temporal, json);
                File.Move(temporal, _rutaTunelUrl, overwrite: true);

                Console.WriteLine($"[LucIAValidacion] tunel_lucia_url.json → exito={exito}, url={url}");
            }
            catch (Exception ex)
            {
                // ES: Un fallo de escritura no debe tumbar la app; solo se registra.
                // EN: A write failure must not crash the app; it is only logged.
                Console.WriteLine($"[LucIAValidacion] Error escribiendo tunel_lucia_url.json: {ex.Message}");
            }
        }

        /// <summary>
        /// ES: Igual que EscribirTunelUrl pero para el túnel de la DAO
        ///     (sala de reuniones/asambleas del metaverso). Godot lo lee cada
        ///     0.5 s desde _poll_dao() en LuciaRecepcion.gd.
        /// EN: Same as EscribirTunelUrl but for the DAO tunnel (the metaverse's
        ///     meeting/assembly room). Godot reads it every 0.5 s from _poll_dao()
        ///     in LuciaRecepcion.gd.
        /// </summary>
        private void EscribirTunelDaoUrl(bool exito, string url, string mensaje)
        {
            try
            {
                var resultado = new TunelLuciaUrl
                {
                    Exito     = exito,
                    Url       = url,
                    Mensaje   = mensaje,
                    Timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
                };

                // ES/EN: Escritura atómica / Atomic write (temp + move).
                string temporal = _rutaTunelDaoUrl + ".tmp";
                string json = JsonSerializer.Serialize(resultado, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(temporal, json);
                File.Move(temporal, _rutaTunelDaoUrl, overwrite: true);

                Console.WriteLine($"[LucIAValidacion] tunel_dao_url.json → exito={exito}, url={url}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[LucIAValidacion] Error escribiendo tunel_dao_url.json: {ex.Message}");
            }
        }

        // ─── Compatibilidad legada / Legacy compatibility ───
        // validacion_conexion.json → validacion_resultado.json

        /// <summary>
        /// ES: Crea un FileSystemWatcher que reacciona cuando Godot (versión antigua)
        ///     crea o modifica validacion_conexion.json.
        /// EN: Creates a FileSystemWatcher that reacts when (old) Godot creates or
        ///     modifies validacion_conexion.json.
        /// </summary>
        private void _IniciarWatcherLegado()
        {
            try
            {
                _watcherLegado = new FileSystemWatcher(_godotUserDir)
                {
                    Filter = "validacion_conexion.json",
                    NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.CreationTime
                };
                _watcherLegado.Created += _OnValidacionLegadaSolicitada;
                _watcherLegado.Changed += _OnValidacionLegadaSolicitada;
                _watcherLegado.EnableRaisingEvents = true;   // ES: empezar a escuchar / EN: start listening
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[LucIAValidacion] Watcher legado no disponible: {ex.Message}");
            }
        }

        /// <summary>
        /// ES: Se ejecuta al detectar una solicitud legada. Responde con el estado
        ///     actual del túnel principal tras una breve espera de 400 ms.
        /// EN: Runs when a legacy request is detected. Replies with the main tunnel's
        ///     current state after a short 400 ms delay.
        /// </summary>
        private void _OnValidacionLegadaSolicitada(object sender, FileSystemEventArgs e)
        {
            Task.Delay(400).ContinueWith(_ =>
            {
                try
                {
                    bool activo = _tunnelManager?.Activo ?? false;
                    string url  = _tunnelManager?.UrlPublica ?? "";
                    _EscribirResultadoLegado(activo, activo
                        ? $"Conexión verificada. Túnel: {url}"
                        : "Túnel aún no disponible. Espera un momento.");
                }
                catch { /* ES: ignorar errores / EN: ignore errors */ }
            });
        }

        /// <summary>
        /// ES: Escribe validacion_resultado.json (formato antiguo, sin escritura atómica).
        /// EN: Writes validacion_resultado.json (old format, non-atomic write).
        /// </summary>
        private void _EscribirResultadoLegado(bool exito, string mensaje)
        {
            try
            {
                var resultado = new ValidacionResultado
                {
                    Exito     = exito,
                    Mensaje   = mensaje,
                    Timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
                };
                string json = JsonSerializer.Serialize(resultado, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(_rutaResultado, json);
            }
            catch { }
        }

        /// <summary>
        /// ES: Detiene ambos túneles (isla + DAO) y libera recursos.
        /// EN: Stops both tunnels (island + DAO) and releases resources.
        /// </summary>
        public void Detener()
        {
            P2PTunnelManager? tm;
            P2PTunnelManager? tmDao;
            FileSystemWatcher? fw;
            CancellationTokenSource? cts;

            lock (_sync)
            {
                // NOTA/NOTE (ES): Dispose() pone _disposeado = true ANTES de llamar a
                //   Detener(), así que este return se ejecuta y los túneles NO se detienen
                //   al hacer Dispose(). Posible bug; ver explicación aparte.
                // NOTE (EN): Dispose() sets _disposeado = true BEFORE calling Detener(),
                //   so this return fires and the tunnels are NOT stopped on Dispose().
                //   Possible bug.
                if (_disposeado) return;

                Console.WriteLine("[LucIAValidacion] Deteniendo túneles HOST (isla + DAO)…");

                // ES: Copiar referencias a locales y anular los campos, así el resto
                //     se hace fuera del lock (evita bloqueos largos).
                // EN: Copy references to locals and null the fields, so the rest runs
                //     outside the lock (avoids long blocking).
                tm    = _tunnelManager;    _tunnelManager    = null;
                tmDao = _tunnelManagerDao; _tunnelManagerDao = null;
                fw    = _watcherLegado;    _watcherLegado    = null;
                cts   = _cts;              _cts              = null;
            }

            // ES: Cancelar, detener y liberar cada recurso; cada paso ignora errores
            //     para que uno que falle no impida los demás.
            // EN: Cancel, stop and dispose each resource; each step swallows errors so
            //     one failure doesn't prevent the others.
            try { cts?.Cancel(); } catch { }
            try { tm?.Detener(); }    catch { }
            try { tm?.Dispose(); }    catch { }
            try { tmDao?.Detener(); } catch { }
            try { tmDao?.Dispose(); } catch { }
            try { cts?.Dispose(); }   catch { }

            // ES: Apagar el watcher legado y desuscribir sus eventos.
            // EN: Shut down the legacy watcher and unsubscribe its events.
            if (fw != null)
            {
                try
                {
                    fw.EnableRaisingEvents = false;
                    fw.Created -= _OnValidacionLegadaSolicitada;
                    fw.Changed -= _OnValidacionLegadaSolicitada;
                    fw.Dispose();
                }
                catch { }
            }

            // ES: Avisar a Godot de que ambos túneles están inactivos.
            // EN: Tell Godot that both tunnels are inactive.
            EscribirTunelUrl(false, "", "Visor desconectado");
            EscribirTunelDaoUrl(false, "", "DAO desconectada");
        }

        /// <summary>
        /// ES: Implementación de IDisposable: marca el objeto como liberado y llama a Detener().
        /// EN: IDisposable implementation: marks the object as disposed and calls Detener().
        /// </summary>
        public void Dispose()
        {
            lock (_sync)
            {
                if (_disposeado) return;
                _disposeado = true;
            }
            Detener();
        }

        // ─── DTOs (objetos de datos / data objects) ──────────────────────────

        /// <summary>
        /// ES: Estructura del JSON de los túneles (isla y DAO) que lee Godot.
        /// EN: Structure of the tunnels' JSON (island and DAO) that Godot reads.
        /// </summary>
        private class TunelLuciaUrl
        {
            public bool   Exito     { get; set; }          // ES: ¿túnel activo? / EN: tunnel active?
            public string Url       { get; set; } = "";    // ES: URL pública / EN: public URL
            public string Mensaje   { get; set; } = "";    // ES: texto para la UI / EN: UI text
            public long   Timestamp { get; set; }          // ES: segundos UNIX (UTC) / EN: UNIX seconds (UTC)
        }

        /// <summary>
        /// ES: Estructura del JSON de resultado del flujo legado.
        /// EN: Structure of the legacy flow's result JSON.
        /// </summary>
        private class ValidacionResultado
        {
            public bool   Exito     { get; set; }
            public string Mensaje   { get; set; } = "";
            public long   Timestamp { get; set; }
        }
    }
}
