using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.RedP2P
{
    /// <summary>
    /// Servidor HTTP / WebNodo embebido que actúa como nodo P2P del visor y portal web para invitados.
    /// Utiliza TcpListener para máxima compatibilidad con túneles SSH efímeros (localhost.run, serveo, cloudflared)
    /// sin requerir permisos de administrador de Windows ni depender de HTTP.sys.
    /// 
    /// Endpoints:
    ///   GET  /             → WebNodo: página web futurista con imagen del metaverso y descarga del visor
    ///   GET  /webnodo      → Alias de la web de bienvenida
    ///   GET  /metaverso.jpg → Imagen futurista del portal del metaverso
    ///   GET  /descargar    → Descarga directa del visor ejecutable más actual (.exe)
    ///   GET  /api/info     → JSON con información del nodo, IPFS CID y túnel
    ///   GET  /ping         → Keepalive / comprobación P2P
    ///   POST /peer         → Registro de un par remoto
    /// </summary>
    public class P2PNodo : IDisposable
    {
        private TcpListener? _tcpListener;
        private CancellationTokenSource? _cts;
        private bool _disposed;
        private readonly string _nombreUsuario;
        private readonly string _sessionCid;
        private readonly DateTime _inicioSesionUtc;

        public int Puerto { get; }
        public string? UrlPublica { get; set; }
        public string SessionCid => _sessionCid;

        /// <summary>Lista de URLs de pares descubiertos remotamente.</summary>
        public System.Collections.Generic.List<string> Pares { get; } = new();

        /// <summary>Disparado cuando se registra un nuevo par.</summary>
        public event Action<string>? NuevoPar;

        public P2PNodo(int puerto, string nombreUsuario)
        {
            Puerto = puerto;
            _nombreUsuario = nombreUsuario;
            _inicioSesionUtc = DateTime.UtcNow;

            // Generar un hash único de sesión estilo IPFS CID v0 (Qm...)
            byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes($"{nombreUsuario}_{_inicioSesionUtc.Ticks}_{Guid.NewGuid()}"));
            string hex = Convert.ToHexString(hash).ToLowerInvariant();
            _sessionCid = "Qm" + hex[..44];
        }

        public Task IniciarAsync()
        {
            _cts = new CancellationTokenSource();

            try
            {
                // Intentar escuchar en Loopback (127.0.0.1) que no requiere privilegios especiales
                _tcpListener = new TcpListener(IPAddress.Loopback, Puerto);
                _tcpListener.Start();
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[P2PNodo] Error al iniciar TcpListener en puerto {Puerto}: {ex.Message}");
                return Task.CompletedTask;
            }

            Task.Run(() => BucleAceptarConexionesAsync(_cts.Token), _cts.Token);
            return Task.CompletedTask;
        }

        private async Task BucleAceptarConexionesAsync(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested && _tcpListener != null)
            {
                try
                {
                    TcpClient client = await _tcpListener.AcceptTcpClientAsync(ct).ConfigureAwait(false);
                    _ = Task.Run(() => ProcesarClienteAsync(client, ct), ct);
                }
                catch (OperationCanceledException) { break; }
                catch (ObjectDisposedException) { break; }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"[P2PNodo] Error en accept: {ex.Message}");
                }
            }
        }

        private async Task ProcesarClienteAsync(TcpClient client, CancellationToken ct)
        {
            using (client)
            {
                try
                {
                    using NetworkStream stream = client.GetStream();
                    stream.ReadTimeout = 8000;
                    stream.WriteTimeout = 30000;

                    // Leer cabecera de la petición HTTP
                    using var reader = new StreamReader(stream, Encoding.UTF8, leaveOpen: true);
                    string? lineaPeticion = await reader.ReadLineAsync(ct).ConfigureAwait(false);
                    if (string.IsNullOrWhiteSpace(lineaPeticion)) return;

                    string[] partes = lineaPeticion.Split(' ', 3);
                    if (partes.Length < 2) return;

                    string metodo = partes[0].ToUpperInvariant();
                    string rawRuta = partes[1];
                    string ruta = rawRuta.Split('?')[0].ToLowerInvariant();

                    // Leer encabezados
                    var encabezados = new System.Collections.Generic.Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                    string? lineaEncabezado;
                    int contentLength = 0;
                    while (!string.IsNullOrEmpty(lineaEncabezado = await reader.ReadLineAsync(ct).ConfigureAwait(false)))
                    {
                        int sep = lineaEncabezado.IndexOf(':');
                        if (sep > 0)
                        {
                            string clave = lineaEncabezado[..sep].Trim();
                            string valor = lineaEncabezado[(sep + 1)..].Trim();
                            encabezados[clave] = valor;
                            if (clave.Equals("Content-Length", StringComparison.OrdinalIgnoreCase))
                                int.TryParse(valor, out contentLength);
                        }
                    }

                    // Enrutamiento de peticiones
                    if (metodo == "GET" && (ruta == "/" || ruta == "/webnodo" || ruta == "/index.html"))
                    {
                        await ResponderHtmlWebNodoAsync(stream).ConfigureAwait(false);
                    }
                    else if (metodo == "GET" && (ruta == "/metaverso.jpg" || ruta == "/assets/metaverso.jpg"))
                    {
                        await ResponderImagenMetaversoAsync(stream).ConfigureAwait(false);
                    }
                    else if (metodo == "GET" && (ruta == "/descargar" || ruta == "/download" || ruta == "/descargar/visor" || ruta.EndsWith(".exe")))
                    {
                        await ResponderDescargaVisorAsync(stream).ConfigureAwait(false);
                    }
                    else if (metodo == "GET" && ruta == "/ping")
                    {
                        await EnviarJsonAsync(stream, 200, "{\"status\":\"pong\"}").ConfigureAwait(false);
                    }
                    else if (metodo == "GET" && (ruta == "/info" || ruta == "/api/info"))
                    {
                        string infoJson = ObtenerInfoJson();
                        await EnviarJsonAsync(stream, 200, infoJson).ConfigureAwait(false);
                    }
                    else if (metodo == "POST" && ruta == "/peer")
                    {
                        string cuerpo = "";
                        if (contentLength > 0 && contentLength < 65536)
                        {
                            char[] buffer = new char[contentLength];
                            int leidos = await reader.ReadBlockAsync(buffer, 0, contentLength).ConfigureAwait(false);
                            cuerpo = new string(buffer, 0, leidos);
                        }

                        RegistrarParRemoto(cuerpo);
                        await EnviarJsonAsync(stream, 200, "{\"status\":\"ok\"}").ConfigureAwait(false);
                    }
                    else
                    {
                        // 404 o redirigir a raíz
                        await ResponderHtmlWebNodoAsync(stream).ConfigureAwait(false);
                    }
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"[P2PNodo] Error en cliente: {ex.Message}");
                }
            }
        }

        private void RegistrarParRemoto(string cuerpo)
        {
            if (string.IsNullOrWhiteSpace(cuerpo)) return;
            try
            {
                using var doc = JsonDocument.Parse(cuerpo);
                if (doc.RootElement.TryGetProperty("url", out var urlProp))
                {
                    string? urlPar = urlProp.GetString();
                    if (!string.IsNullOrWhiteSpace(urlPar) && !Pares.Contains(urlPar))
                    {
                        Pares.Add(urlPar);
                        NuevoPar?.Invoke(urlPar);
                    }
                }
            }
            catch { }
        }

        private string ObtenerInfoJson()
        {
            string? exePath = ObtenerRutaVisorExe();
            long tamanoBytes = exePath != null && File.Exists(exePath) ? new FileInfo(exePath).Length : 0;
            string tamanoMb = (tamanoBytes / (1024.0 * 1024.0)).ToString("F1");

            var info = new
            {
                nodo = _nombreUsuario,
                version = "0.2.0",
                puerto = Puerto,
                pares = Pares.Count,
                session_cid = _sessionCid,
                tunnel_url = UrlPublica ?? "",
                exe_disponible = exePath != null && File.Exists(exePath),
                exe_nombre = exePath != null ? Path.GetFileName(exePath) : "DMWoldVirtualp2pCNX.exe",
                exe_tamano_mb = tamanoMb
            };
            return JsonSerializer.Serialize(info);
        }

        private static async Task EnviarJsonAsync(NetworkStream stream, int codigo, string json)
        {
            byte[] cuerpo = Encoding.UTF8.GetBytes(json);
            string cabecera =
                $"HTTP/1.1 {codigo} OK\r\n" +
                $"Content-Type: application/json; charset=utf-8\r\n" +
                $"Content-Length: {cuerpo.Length}\r\n" +
                $"Access-Control-Allow-Origin: *\r\n" +
                $"Connection: close\r\n\r\n";

            byte[] cabeceraBytes = Encoding.ASCII.GetBytes(cabecera);
            await stream.WriteAsync(cabeceraBytes).ConfigureAwait(false);
            await stream.WriteAsync(cuerpo).ConfigureAwait(false);
            await stream.FlushAsync().ConfigureAwait(false);
        }

        private async Task ResponderHtmlWebNodoAsync(NetworkStream stream)
        {
            string html = GenerarHtmlWebNodo();
            byte[] cuerpo = Encoding.UTF8.GetBytes(html);
            string cabecera =
                "HTTP/1.1 200 OK\r\n" +
                "Content-Type: text/html; charset=utf-8\r\n" +
                $"Content-Length: {cuerpo.Length}\r\n" +
                "Access-Control-Allow-Origin: *\r\n" +
                "Connection: close\r\n\r\n";

            byte[] cabeceraBytes = Encoding.ASCII.GetBytes(cabecera);
            await stream.WriteAsync(cabeceraBytes).ConfigureAwait(false);
            await stream.WriteAsync(cuerpo).ConfigureAwait(false);
            await stream.FlushAsync().ConfigureAwait(false);
        }

        private static async Task ResponderImagenMetaversoAsync(NetworkStream stream)
        {
            byte[]? imgBytes = CargarBytesImagenMetaverso();
            if (imgBytes == null || imgBytes.Length == 0)
            {
                // Fallback a un SVG futurista en caso de que el archivo físico no exista
                string svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 675' width='1200' height='675'><defs><linearGradient id='g' x1='0%' y1='0%' x2='100%' y2='100%'><stop offset='0%' stop-color='#0a0e1a'/><stop offset='50%' stop-color='#1a0933'/><stop offset='100%' stop-color='#051329'/></linearGradient></defs><rect width='100%' height='100%' fill='url(#g)'/><circle cx='600' cy='337' r='200' fill='none' stroke='#00d9ff' stroke-width='6'/><text x='600' y='350' fill='#00d9ff' font-family='sans-serif' font-size='32' text-anchor='middle'>WOLD VIRTUAL P2P 3D</text></svg>";
                byte[] svgBytes = Encoding.UTF8.GetBytes(svg);
                string cabeceraSvg =
                    "HTTP/1.1 200 OK\r\n" +
                    "Content-Type: image/svg+xml\r\n" +
                    $"Content-Length: {svgBytes.Length}\r\n" +
                    "Connection: close\r\n\r\n";
                await stream.WriteAsync(Encoding.ASCII.GetBytes(cabeceraSvg)).ConfigureAwait(false);
                await stream.WriteAsync(svgBytes).ConfigureAwait(false);
                await stream.FlushAsync().ConfigureAwait(false);
                return;
            }

            string cabecera =
                "HTTP/1.1 200 OK\r\n" +
                "Content-Type: image/jpeg\r\n" +
                $"Content-Length: {imgBytes.Length}\r\n" +
                "Cache-Control: public, max-age=86400\r\n" +
                "Connection: close\r\n\r\n";

            await stream.WriteAsync(Encoding.ASCII.GetBytes(cabecera)).ConfigureAwait(false);
            await stream.WriteAsync(imgBytes).ConfigureAwait(false);
            await stream.FlushAsync().ConfigureAwait(false);
        }

        private static byte[]? CargarBytesImagenMetaverso()
        {
            string baseDir = AppContext.BaseDirectory;
            string[] posiblesRutas =
            {
                Path.Combine(baseDir, "assets", "metaverso.jpg"),
                Path.Combine(baseDir, "metaverso.jpg"),
                Path.Combine(Directory.GetCurrentDirectory(), "assets", "metaverso.jpg"),
                Path.Combine(Directory.GetCurrentDirectory(), "webnodo", "public", "metaverso.jpg")
            };

            foreach (string ruta in posiblesRutas)
            {
                if (File.Exists(ruta))
                {
                    try { return File.ReadAllBytes(ruta); } catch { }
                }
            }
            return null;
        }

        private async Task ResponderDescargaVisorAsync(NetworkStream stream)
        {
            string? rutaExe = ObtenerRutaVisorExe();

            if (rutaExe == null || !File.Exists(rutaExe))
            {
                string msgError = "{\"error\":\"El ejecutable del visor aún no está disponible en este nodo anfitrión.\"}";
                await EnviarJsonAsync(stream, 404, msgError).ConfigureAwait(false);
                return;
            }

            try
            {
                var fi = new FileInfo(rutaExe);
                long longitud = fi.Length;
                string nombreArchivo = fi.Name;

                string cabecera =
                    "HTTP/1.1 200 OK\r\n" +
                    "Content-Type: application/octet-stream\r\n" +
                    $"Content-Disposition: attachment; filename=\"{nombreArchivo}\"\r\n" +
                    $"Content-Length: {longitud}\r\n" +
                    "Access-Control-Allow-Origin: *\r\n" +
                    "Connection: close\r\n\r\n";

                await stream.WriteAsync(Encoding.ASCII.GetBytes(cabecera)).ConfigureAwait(false);

                // Transmitir el binario en bloques de 64 KB
                using (FileStream fs = new FileStream(rutaExe, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                {
                    byte[] buffer = new byte[65536];
                    int leidos;
                    while ((leidos = await fs.ReadAsync(buffer).ConfigureAwait(false)) > 0)
                    {
                        await stream.WriteAsync(buffer.AsMemory(0, leidos)).ConfigureAwait(false);
                    }
                }
                await stream.FlushAsync().ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[P2PNodo] Error al transmitir descarga: {ex.Message}");
            }
        }

        public static string? ObtenerRutaVisorExe()
        {
            string baseDir = AppContext.BaseDirectory;

            // 1. Proceso actual si es un .exe compilado
            try
            {
                string? mainExe = System.Diagnostics.Process.GetCurrentProcess().MainModule?.FileName;
                if (!string.IsNullOrEmpty(mainExe) && File.Exists(mainExe) && mainExe.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
                {
                    // Si no es el runner de dotnet o de debug
                    string nombre = Path.GetFileName(mainExe).ToLowerInvariant();
                    if (!nombre.Contains("devenv") && !nombre.Contains("testhost") && new FileInfo(mainExe).Length > 10_000_000)
                    {
                        return mainExe;
                    }
                }
            }
            catch { }

            // 2. Rutas conocidas en el árbol de trabajo
            string[] posibles =
            {
                Path.Combine(baseDir, "DMWoldVirtualp2pCNX.exe"),
                Path.Combine(baseDir, "Visor3D.exe"),
                Path.Combine(baseDir, "descargas", "DMWoldVirtualp2pCNX.exe"),
                Path.Combine(baseDir, "nuevaversion_sinusers", "DMWoldVirtualp2pCNX.exe"),
                Path.Combine(Directory.GetCurrentDirectory(), "nuevaversion_sinusers", "DMWoldVirtualp2pCNX.exe"),
                Path.Combine(Directory.GetCurrentDirectory(), "webnodo", "descargas", "DMWoldVirtualp2pCNX.exe")
            };

            foreach (string p in posibles)
            {
                if (File.Exists(p) && new FileInfo(p).Length > 1_000_000)
                    return p;
            }

            // 3. Buscar cualquier .exe grande en baseDir
            try
            {
                if (Directory.Exists(baseDir))
                {
                    foreach (string f in Directory.GetFiles(baseDir, "*.exe", SearchOption.TopDirectoryOnly))
                    {
                        if (new FileInfo(f).Length > 20_000_000)
                            return f;
                    }
                }
            }
            catch { }

            return null;
        }

        private string GenerarHtmlWebNodo()
        {
            string urlActual = UrlPublica ?? $"http://localhost:{Puerto}";
            string? exePath = ObtenerRutaVisorExe();
            string nombreExe = exePath != null ? Path.GetFileName(exePath) : "DMWoldVirtualp2pCNX.exe";
            string tamanoMb = exePath != null && File.Exists(exePath) ? (new FileInfo(exePath).Length / (1024.0 * 1024.0)).ToString("F1") + " MB" : "~162 MB";

            return $$"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Wold Virtual P2P 3D — WebNodo Efímero</title>
  <meta name="description" content="Portal de acceso y descarga descentralizada al Metaverso Wold Virtual 3D. Conexión P2P directa a través de túnel efímero."/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;900&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet"/>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #070913;
      --surface: #0d1224;
      --surface-card: rgba(13, 21, 42, 0.75);
      --border: rgba(0, 217, 255, 0.22);
      --border-purple: rgba(168, 85, 247, 0.3);
      --accent: #00d9ff;
      --accent-glow: rgba(0, 217, 255, 0.35);
      --purple: #a855f7;
      --purple-glow: rgba(168, 85, 247, 0.35);
      --green: #10b981;
      --text: #f1f5f9;
      --muted: #94a3b8;
    }

    body {
      font-family: 'Outfit', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      overflow-x: hidden;
      position: relative;
    }

    /* Fondo animado Cyber Grid */
    .cyber-grid {
      position: fixed; inset: 0; z-index: 0; pointer-events: none;
      background-image:
        linear-gradient(rgba(0, 217, 255, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 217, 255, 0.04) 1px, transparent 1px);
      background-size: 50px 50px;
      animation: gridDrift 28s linear infinite;
    }
    @keyframes gridDrift {
      0% { transform: translateY(0); }
      100% { transform: translateY(50px); }
    }

    .ambient-glow-1 {
      position: fixed; top: -160px; left: 15%;
      width: 600px; height: 600px; border-radius: 50%;
      background: radial-gradient(circle, rgba(0, 217, 255, 0.12) 0%, transparent 65%);
      pointer-events: none; z-index: 0;
    }
    .ambient-glow-2 {
      position: fixed; bottom: -100px; right: 10%;
      width: 650px; height: 650px; border-radius: 50%;
      background: radial-gradient(circle, rgba(168, 85, 247, 0.13) 0%, transparent 65%);
      pointer-events: none; z-index: 0;
    }

    .container {
      position: relative; z-index: 1;
      max-width: 860px; width: 100%;
      padding: 40px 24px 80px;
      display: flex; flex-direction: column; align-items: center; gap: 28px;
    }

    /* Insignias de Sesión */
    .badge-bar {
      display: flex; flex-wrap: wrap; justify-content: center; gap: 10px;
      margin-bottom: 8px;
    }
    .pill {
      display: inline-flex; align-items: center; gap: 8px;
      padding: 6px 14px; border-radius: 999px;
      font-size: 11.5px; font-weight: 600; letter-spacing: 0.5px;
      backdrop-filter: blur(8px);
    }
    .pill-cyan {
      background: rgba(0, 217, 255, 0.08);
      border: 1px solid rgba(0, 217, 255, 0.35);
      color: var(--accent);
    }
    .pill-purple {
      background: rgba(168, 85, 247, 0.08);
      border: 1px solid rgba(168, 85, 247, 0.35);
      color: #c084fc;
    }
    .pill-green {
      background: rgba(16, 185, 129, 0.08);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #34d399;
    }
    .dot-pulse {
      width: 8px; height: 8px; border-radius: 50%;
      background: #34d399; box-shadow: 0 0 10px #34d399;
      animation: pulseAnim 2s infinite ease-in-out;
    }
    @keyframes pulseAnim {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }

    /* Encabezado */
    header { text-align: center; }
    h1 {
      font-size: clamp(30px, 5.5vw, 54px);
      font-weight: 900;
      line-height: 1.12;
      background: linear-gradient(135deg, #ffffff 10%, var(--accent) 55%, var(--purple) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 12px;
      letter-spacing: -0.5px;
    }
    .hero-subtitle {
      color: var(--muted);
      font-size: 16px;
      max-width: 620px;
      margin: 0 auto;
      line-height: 1.5;
    }

    /* Marco de la Imagen Futurista del Metaverso */
    .portal-frame {
      width: 100%;
      border-radius: 20px;
      overflow: hidden;
      position: relative;
      background: #0d1224;
      border: 1px solid rgba(0, 217, 255, 0.3);
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6), 0 0 30px rgba(0, 217, 255, 0.15);
      transition: border-color 0.4s, box-shadow 0.4s;
    }
    .portal-frame:hover {
      border-color: rgba(168, 85, 247, 0.5);
      box-shadow: 0 16px 50px rgba(0, 0, 0, 0.7), 0 0 40px rgba(168, 85, 247, 0.25);
    }
    .portal-img {
      width: 100%;
      height: auto;
      display: block;
      max-height: 440px;
      object-fit: cover;
      transition: transform 0.8s ease;
    }
    .portal-frame:hover .portal-img {
      transform: scale(1.02);
    }
    .portal-overlay-badge {
      position: absolute; bottom: 16px; left: 16px;
      background: rgba(7, 11, 22, 0.85);
      border: 1px solid var(--border);
      backdrop-filter: blur(12px);
      padding: 8px 18px; border-radius: 12px;
      font-size: 12px; font-weight: 700;
      color: var(--accent); letter-spacing: 0.8px;
      display: flex; align-items: center; gap: 8px;
    }

    /* Tarjeta Principal de Descarga */
    .download-card {
      width: 100%;
      background: var(--surface-card);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 34px;
      backdrop-filter: blur(16px);
      box-shadow: 0 10px 40px rgba(0,0,0,0.45);
      display: flex; flex-direction: column; gap: 24px;
    }

    .dl-header {
      display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;
    }
    .dl-title-box h2 {
      font-size: 22px; font-weight: 700; color: #fff; margin-bottom: 4px;
    }
    .dl-title-box p {
      font-size: 13.5px; color: var(--muted);
    }

    .btn-download-hero {
      width: 100%;
      padding: 18px 30px;
      background: linear-gradient(135deg, #00d9ff 0%, #0284c7 50%, #9333ea 100%);
      color: #ffffff;
      font-family: 'Outfit', sans-serif;
      font-size: 18px;
      font-weight: 800;
      text-decoration: none;
      border: none;
      border-radius: 14px;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center; gap: 12px;
      box-shadow: 0 6px 30px rgba(0, 217, 255, 0.4);
      transition: transform 0.15s, box-shadow 0.25s, opacity 0.2s;
    }
    .btn-download-hero:hover {
      transform: translateY(-2px);
      box-shadow: 0 10px 40px rgba(0, 217, 255, 0.6);
      opacity: 0.95;
    }
    .btn-download-hero:active {
      transform: translateY(0);
    }

    /* Grid de Información de Sesión */
    .session-grid {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px;
      width: 100%;
    }
    .info-box {
      background: rgba(13, 21, 42, 0.5);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 14px 18px;
    }
    .info-box .label {
      font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: var(--muted); font-weight: 600; margin-bottom: 4px;
    }
    .info-box .val {
      font-family: 'JetBrains Mono', monospace; font-size: 13.5px; font-weight: 600; color: #fff; word-break: break-all;
    }

    /* Pasos para Invitados */
    .steps-section {
      width: 100%;
      background: rgba(13, 21, 42, 0.5);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 18px;
      padding: 28px;
    }
    .steps-title {
      font-size: 15px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; color: var(--accent); margin-bottom: 20px;
    }
    .step-item {
      display: flex; gap: 16px; align-items: flex-start;
      padding: 14px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }
    .step-item:last-child { border-bottom: none; }
    .step-badge {
      width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
      background: linear-gradient(135deg, rgba(0,217,255,0.2), rgba(168,85,247,0.2));
      border: 1px solid var(--accent);
      color: var(--accent); font-weight: 800; font-size: 13px;
      display: flex; align-items: center; justify-content: center;
    }
    .step-content strong { display: block; font-size: 14.5px; font-weight: 700; color: #fff; margin-bottom: 3px; }
    .step-content p { font-size: 13px; color: var(--muted); line-height: 1.45; }

    /* Botón Copiar */
    .copy-btn {
      background: rgba(0, 217, 255, 0.1);
      border: 1px solid var(--accent);
      color: var(--accent);
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex; align-items: center; gap: 6px;
      transition: background 0.2s;
    }
    .copy-btn:hover {
      background: rgba(0, 217, 255, 0.2);
    }

    footer {
      font-size: 12.5px; color: var(--muted); text-align: center; line-height: 1.6;
    }
    footer span { color: var(--accent); }
  </style>
</head>
<body>
  <div class="cyber-grid"></div>
  <div class="ambient-glow-1"></div>
  <div class="ambient-glow-2"></div>

  <div class="container">
    <!-- Barra de Insignias -->
    <div class="badge-bar">
      <div class="pill pill-cyan">&#127760; METAVERSO P2P DESCENTRALIZADO</div>
      <div class="pill pill-purple">&#9889; T&Uacute;NEL EF&Iacute;MERO CLOUDFLARE / SSH</div>
      <div class="pill pill-green">
        <span class="dot-pulse"></span>
        <span>NODO ACTIVO EN L&Iacute;NEA</span>
      </div>
    </div>

    <!-- Título y Subtítulo -->
    <header>
      <h1>Wold Virtual P2P 3D</h1>
      <p class="hero-subtitle">Portal WebNodo oficial de sesión efímera. Conéctate a la isla virtual del anfitrión sin depender de servidores centrales.</p>
    </header>

    <!-- Visual Futurista del Metaverso -->
    <div class="portal-frame">
      <img src="/metaverso.jpg" alt="Portal Holográfico Metaverso 3D" class="portal-img" onerror="this.src='/metaverso.jpg'"/>
      <div class="portal-overlay-badge">&#10024; PORTAL CU&Aacute;NTICO P2P &mdash; SESI&Oacute;N &Uacute;NICA</div>
    </div>

    <!-- Tarjeta de Descarga Principal -->
    <div class="download-card">
      <div class="dl-header">
        <div class="dl-title-box">
          <h2>Descargar Visor 3D</h2>
          <p>Ejecutable portable Windows 64-bit &bull; Sin instalación requerida</p>
        </div>
        <div>
          <button class="copy-btn" id="btn-copy-link" onclick="copiarEnlace()">
            &#128203; Copiar Enlace de Invitado
          </button>
        </div>
      </div>

      <a href="/descargar" class="btn-download-hero" id="btn-descarga">
        <span>&#11015;</span>
        <span>Descargar {{nombreExe}} ({{tamanoMb}})</span>
      </a>

      <!-- Grid de Metadatos de Sesión -->
      <div class="session-grid">
        <div class="info-box">
          <div class="label">&#128100; Nodo Anfitrión</div>
          <div class="val">{{_nombreUsuario}}</div>
        </div>
        <div class="info-box">
          <div class="label">&#128230; Hash IPFS de Sesión</div>
          <div class="val" title="{{_sessionCid}}">{{_sessionCid[..16]}}...{{_sessionCid[^8..]}}</div>
        </div>
        <div class="info-box">
          <div class="label">&#128279; Enlace P2P de Conexión</div>
          <div class="val" id="link-p2p">{{urlActual}}</div>
        </div>
      </div>
    </div>

    <!-- Pasos para Invitados -->
    <div class="steps-section">
      <div class="steps-title">&#128640; Guía de Entrada al Mundo 3D</div>
      
      <div class="step-item">
        <div class="step-badge">1</div>
        <div class="step-content">
          <strong>Descarga el Visor</strong>
          <p>Pulsa el botón de descarga superior para obtener <code>{{nombreExe}}</code> directamente desde este nodo.</p>
        </div>
      </div>

      <div class="step-item">
        <div class="step-badge">2</div>
        <div class="step-content">
          <strong>Ejecuta sin Instalación</strong>
          <p>Abre el visor en tu equipo. Al ser portable, almacena tus credenciales en tu propia carpeta local controlada.</p>
        </div>
      </div>

      <div class="step-item">
        <div class="step-badge">3</div>
        <div class="step-content">
          <strong>Identidad y Wallet DeFi</strong>
          <p>Registra tu hardware y guarda las 12 palabras semilla generadas localmente para tu monedero.</p>
        </div>
      </div>

      <div class="step-item">
        <div class="step-badge">4</div>
        <div class="step-content">
          <strong>Conexión Directa al Anfitrión</strong>
          <p>Pega este enlace WebNodo (<code>{{urlActual}}</code>) en la barra de conexión de amigos del visor para materializar tu avatar en la misma isla 3D.</p>
        </div>
      </div>
    </div>

    <footer>
      Wold Virtual P2P 3D &mdash; Red Descentralizada Peer-to-Peer &mdash; <span>Sin Intermediarios</span>
    </footer>
  </div>

  <script>
    function copiarEnlace() {
      const url = document.getElementById('link-p2p').innerText.trim();
      navigator.clipboard.writeText(url).then(() => {
        const btn = document.getElementById('btn-copy-link');
        const orig = btn.innerHTML;
        btn.innerHTML = '&#9989; &iexcl;Copiado!';
        setTimeout(() => { btn.innerHTML = orig; }, 2500);
      }).catch(() => {
        alert('Enlace: ' + url);
      });
    }

    // Actualizar dinámicamente si se conecta
    fetch('/api/info').then(r => r.json()).then(d => {
      if (d.tunnel_url && d.tunnel_url.startsWith('http')) {
        document.getElementById('link-p2p').innerText = d.tunnel_url;
      }
    }).catch(() => {});
  </script>
</body>
</html>
""";
        }

        public async Task AnunciarseAlParAsync(string urlPar, string miUrlPublica)
        {
            try
            {
                using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(8) };
                var payload = new StringContent(
                    JsonSerializer.Serialize(new { url = miUrlPublica }),
                    Encoding.UTF8, "application/json");
                await http.PostAsync($"{urlPar.TrimEnd('/')}/peer", payload).ConfigureAwait(false);
            }
            catch { }
        }

        public static async Task<bool> PingParAsync(string urlPar)
        {
            try
            {
                using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(5) };
                var resp = await http.GetAsync($"{urlPar.TrimEnd('/')}/ping").ConfigureAwait(false);
                return resp.IsSuccessStatusCode;
            }
            catch { return false; }
        }

        public void Detener()
        {
            _cts?.Cancel();
            try { _tcpListener?.Stop(); } catch { }
            _tcpListener = null;
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            Detener();
            _cts?.Dispose();
        }
    }
}
