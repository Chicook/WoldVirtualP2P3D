using ServidorVirtualCS.Infrastructure;
using ServidorVirtualCS.Models;
using ServidorVirtualCS.Services;
using System;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Input;

namespace ServidorVirtualCS.ViewModels;

public sealed class EmbeddedNodeViewModel : INotifyPropertyChanged, IDisposable
{
    private readonly HardwareProfileService _hardwareProfileService = new();
    private readonly ResourceContributionPlanner _planner = new();
    private readonly LocalIpfsPublisher _ipfsPublisher = new();
    private readonly SemaphoreSlim _refreshLock = new(1, 1);
    private readonly RelayCommand _publishCommand;

    private NodeResourceSnapshot? _lastSnapshot;
    private ResourceContributionPlan? _lastPlan;
    private bool _isPublishing;

    public EmbeddedNodeViewModel()
    {
        _publishCommand = new RelayCommand(() => _ = PublishAsync(), () => !_isPublishing && _lastSnapshot is not null && _lastPlan is not null);
        StatusText = "Nodo listo para perfilar recursos.";
        IpfsStatusText = "IPFS pendiente";
        TotalBudgetText = "0 / 1024 MB";
        PublishCommand = _publishCommand;
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ICommand PublishCommand { get; }

    public string NodeName { get; private set; } = "Nodo local";

    public string StatusText { get; private set; }

    public string IpfsStatusText { get; private set; }

    public string PublishedCid { get; private set; } = "-";

    public string GatewayUrl { get; private set; } = "-";

    public string CpuText { get; private set; } = "-";

    public string RamText { get; private set; } = "-";

    public string VramText { get; private set; } = "-";

    public string StorageText { get; private set; } = "-";

    public string BandwidthText { get; private set; } = "-";

    public string TotalBudgetText { get; private set; }

    public int CpuBudget { get; private set; }

    public int RamBudget { get; private set; }

    public int VramBudget { get; private set; }

    public int StorageBudget { get; private set; }

    public int BandwidthBudget { get; private set; }

    public int TotalBudget { get; private set; }

    public bool MeetsMinimum { get; private set; }

    public async Task RefreshAsync()
    {
        await _refreshLock.WaitAsync();
        try
        {
            NodeResourceSnapshot snapshot = await Task.Run(_hardwareProfileService.Capture);
            ResourceContributionPlan plan = _planner.CreatePlan(snapshot);

            _lastSnapshot = snapshot;
            _lastPlan = plan;

            NodeName = snapshot.MachineName;
            CpuText = $"{snapshot.CpuName} | {snapshot.LogicalCores} hilos | carga {snapshot.CpuLoadPercent:0}%";
            RamText = $"{snapshot.AvailableRamMb} MB libres de {snapshot.TotalRamMb} MB";
            VramText = $"{snapshot.GpuName} | {snapshot.DedicatedVramMb} MB VRAM";
            StorageText = $"{snapshot.AvailableDiskMb} MB libres de {snapshot.TotalDiskMb} MB";
            BandwidthText = $"{snapshot.NetworkBandwidthMbPerSecond:0.##} MB/s estimados";

            CpuBudget = plan.CpuBudgetMb;
            RamBudget = plan.RamBudgetMb;
            VramBudget = plan.VramBudgetMb;
            StorageBudget = plan.StorageBudgetMb;
            BandwidthBudget = plan.BandwidthBudgetMb;
            TotalBudget = plan.TotalBudgetMb;
            MeetsMinimum = plan.MeetsMinimum;
            TotalBudgetText = $"{plan.TotalBudgetMb} / {ResourceContributionPlan.MinimumTotalMb} MB";
            StatusText = plan.MeetsMinimum
                ? "Nodo equilibrado. El reparto mantiene margen local para una experiencia fluida."
                : "Nodo conservador. Se comparte menos de 1 GB para evitar cortes en el equipo local.";

            OnPropertyChanged(string.Empty);
            _publishCommand.RaiseCanExecuteChanged();
        }
        finally
        {
            _refreshLock.Release();
        }
    }

    public async Task PublishAsync()
    {
        if (_lastSnapshot is null || _lastPlan is null)
        {
            return;
        }

        _isPublishing = true;
        IpfsStatusText = "Publicando manifiesto del nodo en IPFS...";
        OnPropertyChanged(nameof(IpfsStatusText));
        _publishCommand.RaiseCanExecuteChanged();

        try
        {
            bool ipfsAvailable = await _ipfsPublisher.IsAvailableAsync(_lastSnapshot.IpfsApiUrl, CancellationToken.None);
            if (!ipfsAvailable)
            {
                IpfsStatusText = "IPFS local no disponible en http://127.0.0.1:5001";
                PublishedCid = "-";
                GatewayUrl = "-";
                return;
            }

            string? cid = await _ipfsPublisher.PublishManifestAsync(_lastSnapshot, _lastPlan, CancellationToken.None);
            if (string.IsNullOrWhiteSpace(cid))
            {
                IpfsStatusText = "No se pudo publicar el manifiesto del nodo.";
                PublishedCid = "-";
                GatewayUrl = "-";
                return;
            }

            PublishedCid = cid;
            GatewayUrl = $"http://127.0.0.1:8080/ipfs/{cid}";
            IpfsStatusText = "Nodo anunciado en IPFS. El manifiesto ya puede ser descubierto por la red.";
        }
        finally
        {
            _isPublishing = false;
            OnPropertyChanged(string.Empty);
            _publishCommand.RaiseCanExecuteChanged();
        }
    }

    public void Dispose()
    {
        _refreshLock.Dispose();
    }

    private void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}
