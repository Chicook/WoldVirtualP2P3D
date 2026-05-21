using System;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Diagnostics;

namespace VisorSingularity
{
    public class P2PWebNode
    {
        public string NodeId { get; private set; }
        public string SimulatedUrl { get; private set; }
        public int Port { get; private set; } = 8082;
        public string LocalUrl { get; private set; }
        public string ZipPath { get; private set; }
        public bool IsZipping { get; private set; } = false;
        public bool ZipReady { get; private set; } = false;

        private HttpListener _listener;
        private CancellationTokenSource? _cts;
        private string _repoPath;

        public event Action<string>? OnStatusChanged;

        public P2PWebNode(string username, string repoPath)
        {
            _repoPath = repoPath;

            // Generar NodeId único (ND + 5 números aleatorios basados en hash del usuario o random)
            int randomSeed = Math.Abs((username + DateTime.Now.Ticks).GetHashCode()) % 90000 + 10000;
            NodeId = $"ND{randomSeed}";
            SimulatedUrl = $"www.{NodeId}.ipfs";

            // Encontrar puerto disponible a partir del 8082
            Port = FindAvailablePort(8082);
            LocalUrl = $"http://127.0.0.1:{Port}/";

            // Guardar ZIP en el directorio temporal
            string tempDir = Path.Combine(Path.GetTempPath(), "WoldVirtualP2P");
            if (!Directory.Exists(tempDir))
            {
                Directory.CreateDirectory(tempDir);
            }
            ZipPath = Path.Combine(tempDir, $"wold_virtual_visor_{NodeId}.zip");

            _listener = new HttpListener();
            _listener.Prefixes.Add(LocalUrl);
            _listener.Prefixes.Add($"http://localhost:{Port}/");
        }

        public void Start()
        {
            _cts = new CancellationTokenSource();
            _listener.Start();

            // Iniciar bucle de escucha HTTP
            Task.Run(() => ListenLoop(_cts.Token));

            // Iniciar compresión del visor en segundo plano
            Task.Run(() => GenerateRepositoryZip());

            LogStatus($"Nodo P2P en línea: {SimulatedUrl} -> {LocalUrl}");
        }

        public void Stop()
        {
            if (_cts != null)
            {
                _cts.Cancel();
                _cts.Dispose();
                _cts = null;
            }

            if (_listener != null && _listener.IsListening)
            {
                try
                {
                    _listener.Stop();
                    _listener.Close();
                }
                catch { }
            }

            // Eliminar archivo ZIP temporal
            if (File.Exists(ZipPath))
            {
                try
                {
                    File.Delete(ZipPath);
                }
                catch { }
            }

            LogStatus("Nodo P2P apagado.");
        }

        private int FindAvailablePort(int startingPort)
        {
            int port = startingPort;
            while (port < startingPort + 100)
            {
                try
                {
                    using (var client = new System.Net.Sockets.TcpClient())
                    {
                        // Si conecta, el puerto está ocupado
                        var result = client.BeginConnect("127.0.0.1", port, null, null);
                        var success = result.AsyncWaitHandle.WaitOne(100);
                        if (!success)
                        {
                            return port; // No se conectó rápidamente, asumimos libre
                        }
                        client.EndConnect(result);
                    }
                }
                catch
                {
                    return port; // Si da error de conexión, el puerto está libre
                }
                port++;
            }
            return startingPort; // Fallback
        }

        private async Task ListenLoop(CancellationToken token)
        {
            while (!token.IsCancellationRequested && _listener.IsListening)
            {
                try
                {
                    var context = await _listener.GetContextAsync();
                    var request = context.Request;
                    var response = context.Response;

                    string path = request.Url?.AbsolutePath.ToLower() ?? "/";

                    if (path == "/visor.zip")
                    {
                        if (!ZipReady || !File.Exists(ZipPath))
                        {
                            response.StatusCode = (int)HttpStatusCode.NotFound;
                            byte[] errorBytes = Encoding.UTF8.GetBytes("El archivo ZIP se está generando. Por favor actualice en unos instantes.");
                            response.ContentType = "text/plain; charset=UTF-8";
                            response.ContentLength64 = errorBytes.Length;
                            await response.OutputStream.WriteAsync(errorBytes, 0, errorBytes.Length);
                        }
                        else
                        {
                            response.StatusCode = (int)HttpStatusCode.OK;
                            response.ContentType = "application/zip";
                            response.AddHeader("Content-Disposition", $"attachment; filename=\"WoldVirtual_Visor_{NodeId}.zip\"");

                            using (var fileStream = File.OpenRead(ZipPath))
                            {
                                response.ContentLength64 = fileStream.Length;
                                await fileStream.CopyToAsync(response.OutputStream);
                            }
                        }
                    }
                    else
                    {
                        // Servir landing page Cyberpunk
                        string html = GetInvitePageHtml();
                        byte[] buffer = Encoding.UTF8.GetBytes(html);
                        response.StatusCode = (int)HttpStatusCode.OK;
                        response.ContentType = "text/html; charset=UTF-8";
                        response.ContentLength64 = buffer.Length;
                        await response.OutputStream.WriteAsync(buffer, 0, buffer.Length);
                    }

                    response.OutputStream.Close();
                }
                catch (ObjectDisposedException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"Error en HTTP P2P WebNode: {ex.Message}");
                }
            }
        }

        private void GenerateRepositoryZip()
        {
            if (IsZipping) return;
            IsZipping = true;
            ZipReady = false;
            LogStatus("Generando archivo ZIP del visor (excluyendo carpetas pesadas)...");

            try
            {
                if (File.Exists(ZipPath))
                {
                    File.Delete(ZipPath);
                }

                using (var zipStream = new FileStream(ZipPath, FileMode.Create))
                using (var archive = new ZipArchive(zipStream, ZipArchiveMode.Create))
                {
                    AddDirectoryToZip(archive, _repoPath, _repoPath);
                }

                ZipReady = true;
                LogStatus("¡Archivo ZIP generado exitosamente y listo para compartir!");
            }
            catch (Exception ex)
            {
                LogStatus($"Error al comprimir el repositorio: {ex.Message}");
                Debug.WriteLine($"Error zipping repo: {ex.Message}");
            }
            finally
            {
                IsZipping = false;
            }
        }

        private void AddDirectoryToZip(ZipArchive archive, string sourceDir, string rootDir)
        {
            foreach (string file in Directory.GetFiles(sourceDir))
            {
                string ext = Path.GetExtension(file).ToLower();
                if (ext == ".zip" || ext == ".tmp" || ext == ".log") continue;

                // Evitar copiar binarios o temporales sueltos pesados
                string fileName = Path.GetFileName(file).ToLower();
                if (fileName == "vram_status.json") continue;

                string relativePath = Path.GetRelativePath(rootDir, file);
                try
                {
                    archive.CreateEntryFromFile(file, relativePath);
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"No se pudo añadir archivo al zip ({relativePath}): {ex.Message}");
                }
            }

            foreach (string dir in Directory.GetDirectories(sourceDir))
            {
                string dirName = Path.GetFileName(dir).ToLower();

                // Ignorar directorios pesados y de compilación
                if (dirName == ".git" || 
                    dirName == ".gemini" || 
                    dirName == "obj" || 
                    dirName == "peers" || 
                    dirName == "logs" || 
                    dirName == "temp" || 
                    dirName == "tmp" ||
                    dirName == "wcvcoinmtb") // evitar bucles
                {
                    continue;
                }

                AddDirectoryToZip(archive, dir, rootDir);
            }
        }

        private string GetInvitePageHtml()
        {
            string zipStatusMsg = ZipReady 
                ? "El paquete del Visor 3D está listo para descargar." 
                : "El paquete del Visor 3D se está generando en el host, por favor espera unos instantes...";

            string buttonDisabledClass = ZipReady ? "" : "disabled";
            string downloadUrl = ZipReady ? "/visor.zip" : "#";

            return $@"<!DOCTYPE html>
<html lang=""es"">
<head>
    <meta charset=""UTF-8"">
    <meta name=""viewport"" content=""width=device-width, initial-scale=1.0"">
    <title>Invitación a Wold Virtual P2P 3D</title>
    <link href=""https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap"" rel=""stylesheet"">
    <style>
        :root {{
            --bg-color: #060913;
            --card-bg: rgba(17, 22, 37, 0.7);
            --primary: #66FCF1;
            --primary-glow: rgba(102, 252, 241, 0.4);
            --secondary: #45A29E;
            --accent: #00ff8c;
            --accent-glow: rgba(0, 255, 140, 0.3);
            --text: #C5C6C7;
            --text-bright: #FFFFFF;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            background: var(--bg-color);
            color: var(--text);
            font-family: 'Outfit', sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow-x: hidden;
            position: relative;
        }}

        /* Neon Background Grid */
        body::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: 
                linear-gradient(rgba(102, 252, 241, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(102, 252, 241, 0.03) 1px, transparent 1px);
            background-size: 30px 30px;
            z-index: 1;
        }}

        /* Ambient Glow Spheres */
        .glow-sphere {{
            position: absolute;
            width: 400px;
            height: 400px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(102, 252, 241, 0.08) 0%, transparent 70%);
            z-index: 2;
            pointer-events: none;
        }}

        .glow-1 {{ top: -100px; right: -100px; }}
        .glow-2 {{ bottom: -100px; left: -100px; }}

        .container {{
            width: 90%;
            max-width: 580px;
            background: var(--card-bg);
            border: 1px solid var(--secondary);
            border-radius: 16px;
            padding: 40px;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37), 0 0 15px var(--primary-glow);
            z-index: 10;
            text-align: center;
            border-top: 2px solid var(--primary);
            position: relative;
        }}

        .logo-container {{
            margin-bottom: 25px;
        }}

        .logo-icon {{
            font-size: 50px;
            margin-bottom: 10px;
            filter: drop-shadow(0 0 8px var(--primary));
        }}

        h1 {{
            font-size: 28px;
            font-weight: 800;
            color: var(--text-bright);
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 5px;
            text-shadow: 0 0 10px var(--primary-glow);
        }}

        .subtitle {{
            color: var(--primary);
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-bottom: 25px;
        }}

        .card-info {{
            background: rgba(6, 9, 19, 0.8);
            border: 1px dashed rgba(102, 252, 241, 0.3);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 25px;
        }}

        .peer-id-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--secondary);
            margin-bottom: 5px;
        }}

        .peer-id-val {{
            font-size: 16px;
            font-weight: 600;
            color: var(--accent);
            text-shadow: 0 0 8px var(--accent-glow);
            word-break: break-all;
        }}

        p.desc {{
            font-size: 14px;
            line-height: 1.6;
            margin-bottom: 30px;
            color: var(--text);
        }}

        .btn-download {{
            display: inline-block;
            background: transparent;
            color: var(--primary);
            border: 2px solid var(--primary);
            padding: 14px 30px;
            font-size: 15px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 2px;
            border-radius: 8px;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.3s ease;
            box-shadow: 0 0 10px rgba(102, 252, 241, 0.1);
            width: 100%;
        }}

        .btn-download:hover:not(.disabled) {{
            background: var(--primary);
            color: var(--bg-color);
            box-shadow: 0 0 20px var(--primary-glow);
            transform: translateY(-2px);
        }}

        .btn-download.disabled {{
            border-color: #334;
            color: #556;
            cursor: not-allowed;
            pointer-events: none;
        }}

        .status-msg {{
            margin-top: 15px;
            font-size: 12px;
            color: var(--accent);
        }}

        .footer {{
            margin-top: 35px;
            font-size: 11px;
            color: rgba(197, 198, 199, 0.4);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
    </style>
</head>
<body>
    <div class=""glow-sphere glow-1""></div>
    <div class=""glow-sphere glow-2""></div>

    <div class=""container"">
        <div class=""logo-container"">
            <div class=""logo-icon"">🌐</div>
            <h1>Wold Virtual 3D</h1>
            <div class=""subtitle"">P2P Network Node</div>
        </div>

        <div class=""card-info"">
            <div class=""peer-id-label"">Dirección IPFS del Host</div>
            <div class=""peer-id-val"">{SimulatedUrl}</div>
        </div>

        <p class=""desc"">
            Te han invitado a unirte como nodo al metaverso descentralizado 3D de Wold Virtual. 
            Descarga el visor comprimido a continuación, descomprímelo en tu PC y ejecútalo para crear tu avatar y registrar tu isla en la red.
        </p>

        <a href=""{downloadUrl}"" class=""btn-download {buttonDisabledClass}"">
            Descargar Visor (.ZIP)
        </a>

        <div class=""status-msg"">
            {zipStatusMsg}
        </div>

        <div class=""footer"">
            Powered by IPFS & C# WoldVirtual P2P Engine
        </div>
    </div>
</body>
</html>";
        }

        private void LogStatus(string msg)
        {
            OnStatusChanged?.Invoke(msg);
        }
    }
}
