using WoldVirtual.Servidor.Modulos.Blockchain;
using WoldVirtual.Servidor.Modulos.Dao;
using WoldVirtual.Servidor.Modulos.Tuneles;
using WoldVirtual.Servidor.Modulos.Ipc;

var builder = WebApplication.CreateBuilder(args);
var port = int.TryParse(Environment.GetEnvironmentVariable("WVP_PORT"), out var configuredPort)
    ? configuredPort : 8765;
builder.WebHost.UseUrls($"http://0.0.0.0:{port}");

builder.Services.AddSingleton<BlockchainModule>();
builder.Services.AddSingleton<DaoModule>();
builder.Services.AddSingleton<TunnelModule>();
builder.Services.AddSingleton<FileBridgeModule>();

var app = builder.Build();
app.UseWebSockets();

app.MapGet("/", () => Results.Ok(new
{
    producto = "WoldVirtualP2P3D",
    version = "2.9.3-preview",
    estado = "activo",
    modulos = new[] { "blockchain-local", "dao-presencia", "tunel-efimero" }
}));
app.MapGet("/api/health", (BlockchainModule blockchain, DaoModule dao, TunnelModule tunnel) =>
    Results.Ok(new
    {
        ok = true,
        version = "2.9.3-preview",
        blockchain = blockchain.Estado,
        dao = new { miembros = dao.TotalMiembrosEnLinea },
        tunel = tunnel.Estado
    }));

app.MapBlockchainEndpoints();
app.MapDaoEndpoints();
app.MapTunnelEndpoints();

var stop = app.Lifetime.ApplicationStopping;
var blockchainModule = app.Services.GetRequiredService<BlockchainModule>();
var daoModule = app.Services.GetRequiredService<DaoModule>();
var tunnelModule = app.Services.GetRequiredService<TunnelModule>();
var ipcModule = app.Services.GetRequiredService<FileBridgeModule>();

// Orden intencional de inicio: cadena local, presencia DAO y, por último, túnel.
await blockchainModule.IniciarAsync(stop);
await daoModule.IniciarAsync(stop);
await ipcModule.StartAsync(stop);

var ipcOnly = Environment.GetEnvironmentVariable("WVP_IPC_ONLY") == "1";
if (!ipcOnly) await tunnelModule.IniciarAsync(port, stop);
else Console.WriteLine("[servidor] Modo IPC local: HTTP y túneles desactivados.");

try
{
    if (ipcOnly)
        await Task.Delay(Timeout.InfiniteTimeSpan);
    else
        await app.RunAsync();
}
finally
{
    await tunnelModule.DetenerAsync();
    await ipcModule.StopAsync();
    daoModule.Detener();
}
