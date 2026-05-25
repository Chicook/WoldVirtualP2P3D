using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using Renci.SshNet;

namespace VisorSingularity
{
    public class IPFSTunnelConnector : IDisposable
    {
        private readonly string _sshHost;
        private readonly int _sshPort;
        private readonly string _sshUser;
        private readonly string _sshPassword;
        private readonly string _sshKeyFile;
        private readonly int _remoteIpfsApiPort;

        private SshClient? _sshClient;
        private ForwardedPortLocal? _portForwarder;
        private HttpClient _httpClient;
        private bool _disposed;

        public bool IsConnected { get; private set; }
        public int LocalForwardPort { get; private set; }
        public string IpfsApiUrl { get; private set; } = string.Empty;
        public string? LastPinnedCid { get; private set; }
        public string? RemoteVersion { get; private set; }

        public event Action<string>? OnStatusChanged;
        public event Action<bool>? OnConnectionChanged;

        public IPFSTunnelConnector(string sshHost, int sshPort, string sshUser, string sshPassword, string sshKeyFile,
            int remoteIpfsApiPort = 5001, int localForwardPort = 0)
        {
            _sshHost = sshHost;
            _sshPort = sshPort;
            _sshUser = sshUser;
            _sshPassword = sshPassword ?? "";
            _sshKeyFile = sshKeyFile ?? "";
            _remoteIpfsApiPort = remoteIpfsApiPort;
            LocalForwardPort = localForwardPort > 0 ? localForwardPort : FindAvailablePort(5001);
            IpfsApiUrl = $"http://127.0.0.1:{LocalForwardPort}";
            _httpClient = new HttpClient { Timeout = TimeSpan.FromSeconds(60) };
        }

        public async Task ConnectAsync()
        {
            await Task.Run(() => ConnectInternal());
        }

        private void ConnectInternal()
        {
            DisconnectInternal();
            LogStatus("Conectando vía SSH al servidor IPFS remoto...");

            try
            {
                var methods = new List<AuthenticationMethod>();

                if (!string.IsNullOrEmpty(_sshPassword))
                    methods.Add(new PasswordAuthenticationMethod(_sshUser, _sshPassword));

                if (!string.IsNullOrEmpty(_sshKeyFile))
                    methods.Add(new PrivateKeyAuthenticationMethod(_sshUser,
                        new PrivateKeyFile(_sshKeyFile)));

                var connectionInfo = new ConnectionInfo(_sshHost, _sshPort, _sshUser, methods.ToArray());
                _sshClient = new SshClient(connectionInfo);
                _sshClient.Connect();

                LogStatus($"SSH conectado a {_sshUser}@{_sshHost}:{_sshPort}");

                _portForwarder = new ForwardedPortLocal(
                    "127.0.0.1", (uint)LocalForwardPort,
                    "127.0.0.1", (uint)_remoteIpfsApiPort);

                _sshClient.AddForwardedPort(_portForwarder);
                _portForwarder.Start();

                IsConnected = true;
                OnConnectionChanged?.Invoke(true);
                LogStatus($"Túnel activo: 127.0.0.1:{LocalForwardPort} -> {_sshHost}:{_remoteIpfsApiPort} (API IPFS)");

                _ = TestIpfsApiAsync();
            }
            catch (Exception ex)
            {
                IsConnected = false;
                OnConnectionChanged?.Invoke(false);
                LogStatus($"Error SSH: {ex.Message}");
                CleanupSsh();
            }
        }

        public void Disconnect()
        {
            DisconnectInternal();
            LogStatus("Túnel SSH desconectado.");
        }

        private void DisconnectInternal()
        {
            CleanupSsh();
            IsConnected = false;
            OnConnectionChanged?.Invoke(false);
        }

        public async Task<string?> AddUrlToIpfsAsync(string url, bool pin = true)
        {
            if (!await EnsureConnectedAsync()) return null;

            try
            {
                LogStatus($"Añadiendo contenido a IPFS desde URL: {url}");

                var requestUrl = $"{IpfsApiUrl}/api/v0/add?url={Uri.EscapeDataString(url)}&pin={pin.ToString().ToLower()}";
                using var response = await _httpClient.PostAsync(requestUrl, null);
                response.EnsureSuccessStatusCode();

                var json = await response.Content.ReadAsStringAsync();
                return ParseIpfsAddResponse(json);
            }
            catch (Exception ex)
            {
                LogStatus($"Error al añadir URL a IPFS: {ex.Message}");
                return null;
            }
        }

        public async Task<string?> AddFileToIpfsAsync(string filePath, bool pin = true)
        {
            if (!await EnsureConnectedAsync()) return null;

            try
            {
                LogStatus($"Subiendo archivo a IPFS: {Path.GetFileName(filePath)}");

                using var formData = new MultipartFormDataContent();
                using var fileStream = File.OpenRead(filePath);
                using var streamContent = new StreamContent(fileStream);
                formData.Add(streamContent, "file", Path.GetFileName(filePath));

                var requestUrl = $"{IpfsApiUrl}/api/v0/add?pin={pin.ToString().ToLower()}";
                using var response = await _httpClient.PostAsync(requestUrl, formData);
                response.EnsureSuccessStatusCode();

                var json = await response.Content.ReadAsStringAsync();
                return ParseIpfsAddResponse(json);
            }
            catch (Exception ex)
            {
                LogStatus($"Error al subir archivo a IPFS: {ex.Message}");
                return null;
            }
        }

        public async Task<bool> PinContentAsync(string cid)
        {
            if (!IsConnected) return false;

            try
            {
                var requestUrl = $"{IpfsApiUrl}/api/v0/pin/add?arg={cid}";
                using var response = await _httpClient.PostAsync(requestUrl, null);
                response.EnsureSuccessStatusCode();

                LogStatus($"Contenido pineado: {cid}");
                return true;
            }
            catch (Exception ex)
            {
                LogStatus($"Error al pinear {cid}: {ex.Message}");
                return false;
            }
        }

        public async Task<bool> UnpinContentAsync(string cid)
        {
            if (!IsConnected) return false;

            try
            {
                var requestUrl = $"{IpfsApiUrl}/api/v0/pin/rm?arg={cid}";
                using var response = await _httpClient.PostAsync(requestUrl, null);
                response.EnsureSuccessStatusCode();

                LogStatus($"Contenido despineado: {cid}");
                return true;
            }
            catch (Exception ex)
            {
                LogStatus($"Error al despinear {cid}: {ex.Message}");
                return false;
            }
        }

        public async Task<string?> GetContentStatusAsync(string cid)
        {
            if (!IsConnected) return null;

            try
            {
                var requestUrl = $"{IpfsApiUrl}/api/v0/pin/ls?arg={cid}";
                using var response = await _httpClient.PostAsync(requestUrl, null);
                if (!response.IsSuccessStatusCode) return "no_pin";

                var json = await response.Content.ReadAsStringAsync();
                using var doc = JsonDocument.Parse(json);
                if (doc.RootElement.TryGetProperty("Keys", out var keys) &&
                    keys.TryGetProperty(cid, out var info) &&
                    info.TryGetProperty("Type", out var type))
                {
                    return type.GetString() ?? "unknown";
                }
                return "unknown";
            }
            catch
            {
                return null;
            }
        }

        private async Task<bool> EnsureConnectedAsync()
        {
            if (IsConnected) return true;
            LogStatus("Reconectando túnel SSH...");
            await ConnectAsync();
            return IsConnected;
        }

        public async Task<bool> TestIpfsApiAsync()
        {
            try
            {
                using var response = await _httpClient.PostAsync($"{IpfsApiUrl}/api/v0/version", null);
                if (!response.IsSuccessStatusCode) return false;

                var json = await response.Content.ReadAsStringAsync();
                using var doc = JsonDocument.Parse(json);
                RemoteVersion = doc.RootElement.GetProperty("Version").GetString();

                LogStatus($"IPFS daemon v{RemoteVersion} detectado en servidor remoto.");
                return true;
            }
            catch
            {
                LogStatus("No se pudo conectar con la API IPFS en el servidor remoto.");
                return false;
            }
        }

        private string? ParseIpfsAddResponse(string json)
        {
            using var doc = JsonDocument.Parse(json);
            var hash = doc.RootElement.GetProperty("Hash").GetString();
            var name = doc.RootElement.GetProperty("Name").GetString();

            LastPinnedCid = hash;
            LogStatus($"IPFS añadido: {name} -> CID: {hash}");

            return hash;
        }

        private void CleanupSsh()
        {
            try
            {
                if (_portForwarder != null)
                {
                    if (_portForwarder.IsStarted)
                        _portForwarder.Stop();
                    _sshClient?.RemoveForwardedPort(_portForwarder);
                    _portForwarder.Dispose();
                    _portForwarder = null;
                }

                if (_sshClient != null)
                {
                    if (_sshClient.IsConnected)
                        _sshClient.Disconnect();
                    _sshClient.Dispose();
                    _sshClient = null;
                }
            }
            catch { }
        }

        private int FindAvailablePort(int startingPort)
        {
            int port = startingPort;
            while (port < startingPort + 100)
            {
                try
                {
                    using var client = new System.Net.Sockets.TcpClient();
                    var result = client.BeginConnect("127.0.0.1", port, null, null);
                    var success = result.AsyncWaitHandle.WaitOne(100);
                    if (!success) return port;
                    client.EndConnect(result);
                }
                catch { return port; }
                port++;
            }
            return startingPort;
        }

        private void LogStatus(string msg)
        {
            OnStatusChanged?.Invoke(msg);
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            DisconnectInternal();
            _httpClient?.Dispose();
        }
    }
}
