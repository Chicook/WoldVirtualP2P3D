using System;
using System.IO;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.RedP2P
{
    /// <summary>
    /// Gestor de conexión P2P con LucIA — v2.9.3.
    ///
    /// ARQUITECTURA CORREGIDA: Lucía es el HOST del túnel efímero.
    ///
    /// Al llamar a Iniciar() se arranca automáticamente el túnel SSH efímero
    /// (P2PTunnelManager). Cuando el túnel obtiene su URL pública, se escribe
    /// user://tunel_lucia_url.json para que LuciaRecepcion.gd lo lea.
    ///
    /// El flujo es:
    ///   C# arranca → IniciarAsync() → SSH tunnel → URL pública → archivo JSON
    ///   Godot polling → lee JSON → botón "CONECTAR" muestra URL → "CONECTADO"
    /// </summary>
    public class LucIAValidacionManager : IDisposable
    {
        private readonly string _godotUserDir;
        private readonly string _rutaTunelUrl;

        // Compatibilidad legada (ya no se usa para el flujo principal)
        private readonly string _rutaValidacion;
        private readonly string _rutaResultado;

        private FileSystemWatcher? _watcherLegado;
        private P2PTunnelManager? _tunnelManager;
        private P2PTunnelManager? _tunnelManagerDao;  // túnel Cloudflare de la DAO
        private readonly string   _rutaTunelDaoUrl;
        private CancellationTokenSource? _cts;
        private bool _disposeado;
        private readonly object _sync = new();

        /// <summary>Se dispara cuando el túnel obtiene (o pierde) URL pública.</summary>
        public event Action<bool, string>? ValidacionCompletada;

        /// <summary>Ruta del directorio user:// de Godot en Windows.</summary>
        public static string GodotUserDir => Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "Godot", "app_userdata", "WoldVirtualP2P3D");

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
        /// Inicia el túnel SSH efímero inmediatamente (Lucía = HOST).
        /// La URL pública se publica en user://tunel_lucia_url.json.
        /// Idempotente: si ya hay un túnel activo no hace nada.
        /// </summary>
        public void Iniciar()
        {
            lock (_sync)
            {
                if (_disposeado || _tunnelManager != null) return;

                Console.WriteLine($"[LucIAValidacion] Iniciando túnel HOST (Lucía) en {_godotUserDir}");

                _cts = new CancellationTokenSource();

                // Lucía abre el túnel en el puerto del WebNodo (3030 o dinámico).
                // Usamos 8545 que es el puerto del servidor blockchain (como en versiones anteriores)
                // y coincide con el puerto configurado en P2PTunnelManager por defecto.
                _tunnelManager = new P2PTunnelManager(puertoLocal: 8545);

                // Cuando el túnel tenga URL → publicar para Godot
                _tunnelManager.UrlObtenida += url =>
                {
                    Console.WriteLine($"[LucIAValidacion] Túnel HOST activo: {url}");
                    EscribirTunelUrl(true, url, $"Túnel WebNodo activo: {url}");
                    ValidacionCompletada?.Invoke(true, $"Túnel WebNodo activo: {url}");
                };

                // Cuando el túnel muera → marcar como inactivo en Godot
                _tunnelManager.TunnelMuerto += host =>
                {
                    Console.WriteLine($"[LucIAValidacion] Túnel HOST caído ({host}), reconectando…");
                    EscribirTunelUrl(false, "", $"Reconectando túnel (host: {host})…");
                    ValidacionCompletada?.Invoke(false, $"Túnel desconectado (host: {host})");
                };

                // Iniciar el bucle del túnel en background
                _ = Task.Run(() => _tunnelManager.IniciarAsync());

                // ── Túnel Cloudflare de la DAO (puerto 8766) ──────────────────
                // Mismo cloudflared, puerto diferente → URL pública propia de la DAO.
                // Godot la lee desde user://tunel_dao_url.json.
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

                // Mantener watcher legado por compatibilidad con versiones anteriores
                _IniciarWatcherLegado();
            }
        }

        /// <summary>
        /// Escribe user://tunel_lucia_url.json con el estado actual del túnel.
        /// Godot lo lee cada 0.5 s desde _poll_conexion().
        /// </summary>
        private void EscribirTunelUrl(bool exito, string url, string mensaje)
        {
            try
            {
                var resultado = new TunelLuciaUrl
                {
                    Exito   = exito,
                    Url     = url,
                    Mensaje = mensaje,
                    Timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
                };

                // Escritura atómica: temporal + rename para evitar que Godot lea a medias.
                string temporal = _rutaTunelUrl + ".tmp";
                string json = JsonSerializer.Serialize(resultado, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(temporal, json);
                File.Move(temporal, _rutaTunelUrl, overwrite: true);

                Console.WriteLine($"[LucIAValidacion] tunel_lucia_url.json → exito={exito}, url={url}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[LucIAValidacion] Error escribiendo tunel_lucia_url.json: {ex.Message}");
            }
        }

        /// <summary>
        /// Escribe user://tunel_dao_url.json con el estado del túnel Cloudflare de la DAO.
        /// LucIA es el HOST: abre este túnel desde su máquina para que los usuarios
        /// se conecten a la DAO como sala de reuniones/asambleas del metaverso.
        /// Godot lo lee cada 0.5 s desde _poll_dao() en LuciaRecepcion.gd.
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

        // ─── Compatibilidad legada (validacion_conexion.json → validacion_resultado.json) ───

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
                _watcherLegado.EnableRaisingEvents = true;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[LucIAValidacion] Watcher legado no disponible: {ex.Message}");
            }
        }

        private void _OnValidacionLegadaSolicitada(object sender, FileSystemEventArgs e)
        {
            // Responder con el estado actual del túnel principal
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
                catch { }
            });
        }

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

        /// <summary>Detiene ambos túneles (isla + DAO) y libera recursos. LucIA es el HOST de los dos.</summary>
        public void Detener()
        {
            P2PTunnelManager? tm;
            P2PTunnelManager? tmDao;
            FileSystemWatcher? fw;
            CancellationTokenSource? cts;

            lock (_sync)
            {
                if (_disposeado) return;

                Console.WriteLine("[LucIAValidacion] Deteniendo túneles HOST (isla + DAO)…");

                tm    = _tunnelManager;    _tunnelManager    = null;
                tmDao = _tunnelManagerDao; _tunnelManagerDao = null;
                fw    = _watcherLegado;    _watcherLegado    = null;
                cts   = _cts;              _cts              = null;
            }

            try { cts?.Cancel(); } catch { }
            try { tm?.Detener(); }    catch { }
            try { tm?.Dispose(); }    catch { }
            try { tmDao?.Detener(); } catch { }
            try { tmDao?.Dispose(); } catch { }
            try { cts?.Dispose(); }   catch { }

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

            // Marcar ambos túneles como inactivos para Godot
            EscribirTunelUrl(false, "", "Visor desconectado");
            EscribirTunelDaoUrl(false, "", "DAO desconectada");
        }

        public void Dispose()
        {
            lock (_sync)
            {
                if (_disposeado) return;
                _disposeado = true;
            }
            Detener();
        }

        // ─── DTOs ────────────────────────────────────────────────────────────

        private class TunelLuciaUrl
        {
            public bool   Exito     { get; set; }
            public string Url       { get; set; } = "";
            public string Mensaje   { get; set; } = "";
            public long   Timestamp { get; set; }
        }

        private class ValidacionResultado
        {
            public bool   Exito     { get; set; }
            public string Mensaje   { get; set; } = "";
            public long   Timestamp { get; set; }
        }
    }
}
