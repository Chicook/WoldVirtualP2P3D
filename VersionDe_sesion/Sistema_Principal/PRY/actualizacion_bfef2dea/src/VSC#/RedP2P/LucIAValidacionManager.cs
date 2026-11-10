using System;
using System.IO;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Visor3D.RedP2P;

namespace Visor3D.RedP2P
{
    /// <summary>
    /// Gestor de validación de conexión con LucIA.
    /// Monitorea el directorio user:// de Godot para detectar solicitudes de validación
    /// de conexión emitidas por LucIARecepcion.gd y responde iniciando túneles SSH efímeros.
    /// </summary>
    public class LucIAValidacionManager : IDisposable
    {
        private readonly string _godotUserDir;
        private readonly string _rutaValidacion;
        private readonly string _rutaResultado;
        private FileSystemWatcher? _watcher;
        private P2PTunnelManager? _tunnelManager;
        private CancellationTokenSource? _cts;
        private bool _disposeado;
        private readonly object _sync = new();

        /// <summary>Se dispara cuando se completa una validación de conexión.</summary>
        public event Action<bool, string>? ValidacionCompletada;

        /// <summary>Ruta del directorio user:// de Godot en Windows.</summary>
        public static string GodotUserDir => Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "Godot", "app_userdata", "WoldVirtualP2P3D");

        public LucIAValidacionManager()
        {
            _godotUserDir = GodotUserDir;
            _rutaValidacion = Path.Combine(_godotUserDir, "validacion_conexion.json");
            _rutaResultado = Path.Combine(_godotUserDir, "validacion_resultado.json");

            // Asegurar que el directorio existe
            Directory.CreateDirectory(_godotUserDir);
        }

        /// <summary>
        /// Inicia el monitoreo del directorio user:// para detectar solicitudes de validación.
        /// </summary>
        public void Iniciar()
        {
            lock (_sync)
            {
                if (_disposeado || _watcher != null) return;

                Console.WriteLine($"[LucIAValidacion] Iniciando monitoreo en {_godotUserDir}");

                _cts = new CancellationTokenSource();
                _watcher = new FileSystemWatcher(_godotUserDir)
                {
                    Filter = "validacion_conexion.json",
                    NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.CreationTime
                };

                _watcher.Created += OnValidacionSolicitada;
                _watcher.Changed += OnValidacionSolicitada;
                _watcher.EnableRaisingEvents = true;

                // Verificar si ya existe un archivo pendiente al iniciar
                if (File.Exists(_rutaValidacion))
                {
                    Task.Run(() => ProcesarValidacionAsync(_cts!.Token));
                }
            }
        }

        /// <summary>
        /// Detiene el monitoreo y libera recursos.
        /// </summary>
        public void Detener()
        {
            lock (_sync)
            {
                if (_disposeado) return;

                Console.WriteLine("[LucIAValidacion] Deteniendo monitoreo");

                if (_watcher != null)
                {
                    _watcher.Created -= OnValidacionSolicitada;
                    _watcher.Changed -= OnValidacionSolicitada;
                    _watcher.EnableRaisingEvents = false;
                    _watcher.Dispose();
                    _watcher = null;
                }

                _cts?.Cancel();
                _tunnelManager?.Dispose();
                _tunnelManager = null;
                _cts?.Dispose();
                _cts = null;
            }
        }

        private void OnValidacionSolicitada(object sender, FileSystemEventArgs e)
        {
            Console.WriteLine($"[LucIAValidacion] Solicitud detectada: {e.FullPath}");

            // Debounce: esperar un poco para asegurar que el archivo esté completamente escrito
            Task.Delay(500).ContinueWith(_ =>
            {
                if (_cts != null && !_cts.IsCancellationRequested)
                {
                    Task.Run(() => ProcesarValidacionAsync(_cts!.Token));
                }
            });
        }

        /// <summary>
        /// Procesa una solicitud de validación de conexión.
        /// Lee validacion_conexion.json, inicia el túnel SSH y escribe validacion_resultado.json.
        /// </summary>
        private async Task ProcesarValidacionAsync(CancellationToken token)
        {
            try
            {
                // Leer la solicitud de validación
                if (!File.Exists(_rutaValidacion))
                {
                    Console.WriteLine("[LucIAValidacion] Archivo de validación no encontrado");
                    return;
                }

                string contenido = await File.ReadAllTextAsync(_rutaValidacion, token);
                var datosValidacion = JsonSerializer.Deserialize<ValidacionDatos>(contenido);

                if (datosValidacion == null)
                {
                    Console.WriteLine("[LucIAValidacion] Error al deserializar datos de validación");
                    EscribirResultado(false, "Error al deserializar datos de validación");
                    return;
                }

                Console.WriteLine($"[LucIAValidacion] Procesando validación para cuenta: {datosValidacion.CuentaHash.Substring(0, 16)}...");

                // Validar que el token no haya expirado
                long expira = long.Parse(datosValidacion.Expira);
                long ahora = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
                if (ahora > expira)
                {
                    Console.WriteLine("[LucIAValidacion] Token expirado");
                    EscribirResultado(false, "Token de validación expirado");
                    return;
                }

                // Iniciar túnel SSH efímero
                Console.WriteLine("[LucIAValidacion] Iniciando túnel SSH efímero...");
                _tunnelManager = new P2PTunnelManager(puertoLocal: 8545);
                await _tunnelManager.IniciarAsync();

                // Esperar a que el túnel esté activo
                var timeout = Task.Delay(30000, token); // 30 segundos timeout
                var tunnelTask = Task.Run(async () =>
                {
                    while (!_tunnelManager!.Activo && !token.IsCancellationRequested)
                    {
                        await Task.Delay(500, token);
                    }
                }, token);

                var ganador = await Task.WhenAny(tunnelTask, timeout);

                if (ganador == timeout)
                {
                    Console.WriteLine("[LucIAValidacion] Timeout esperando túnel SSH");
                    EscribirResultado(false, "Timeout al iniciar túnel SSH");
                    _tunnelManager?.Dispose();
                    return;
                }

                if (!_tunnelManager.Activo)
                {
                    Console.WriteLine("[LucIAValidacion] No se pudo establecer el túnel SSH");
                    EscribirResultado(false, "No se pudo establecer el túnel SSH");
                    _tunnelManager?.Dispose();
                    return;
                }

                string urlPublica = _tunnelManager.UrlPublica ?? "";
                Console.WriteLine($"[LucIAValidacion] Túnel activo: {urlPublica}");

                // Validación exitosa
                EscribirResultado(true, $"Conexión validada correctamente. Túnel: {urlPublica}");

                // Esperar un poco antes de cerrar el túnel (para dar tiempo a Godot de leer el resultado)
                await Task.Delay(5000, token);

                _tunnelManager?.Dispose();
                _tunnelManager = null;

                // Eliminar el archivo de solicitud
                try
                {
                    File.Delete(_rutaValidacion);
                }
                catch { }
            }
            catch (OperationCanceledException)
            {
                Console.WriteLine("[LucIAValidacion] Operación cancelada");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[LucIAValidacion] Error procesando validación: {ex.Message}");
                EscribirResultado(false, $"Error: {ex.Message}");
            }
        }

        /// <summary>
        /// Escribe el resultado de la validación en validacion_resultado.json.
        /// </summary>
        private void EscribirResultado(bool exito, string mensaje)
        {
            try
            {
                var resultado = new ValidacionResultado
                {
                    Exito = exito,
                    Mensaje = mensaje,
                    Timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
                };

                string json = JsonSerializer.Serialize(resultado, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(_rutaResultado, json);

                Console.WriteLine($"[LucIAValidacion] Resultado escrito: exito={exito}, mensaje={mensaje}");
                ValidacionCompletada?.Invoke(exito, mensaje);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[LucIAValidacion] Error escribiendo resultado: {ex.Message}");
            }
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

        /// <summary>Datos de validación leídos de validacion_conexion.json</summary>
        private class ValidacionDatos
        {
            public string CuentaHash { get; set; } = "";
            public string Token { get; set; } = "";
            public string Timestamp { get; set; } = "";
            public string Expira { get; set; } = "";
        }

        /// <summary>Resultado de validación escrito en validacion_resultado.json</summary>
        private class ValidacionResultado
        {
            public bool Exito { get; set; }
            public string Mensaje { get; set; } = "";
            public long Timestamp { get; set; }
        }
    }
}
