using ServidorVirtualCS.ViewModels;
using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;

namespace ServidorVirtualCS.Controls;

public partial class EmbeddedNodeControl : UserControl
{
    private readonly EmbeddedNodeViewModel _viewModel = new();
    private readonly DispatcherTimer _heartbeatTimer = new() { Interval = TimeSpan.FromSeconds(12) };

    public EmbeddedNodeControl()
    {
        InitializeComponent();
        DataContext = _viewModel;
        Loaded += EmbeddedNodeControl_Loaded;
        Unloaded += EmbeddedNodeControl_Unloaded;
        _heartbeatTimer.Tick += HeartbeatTimer_Tick;
    }

    private async void EmbeddedNodeControl_Loaded(object sender, RoutedEventArgs e)
    {
        await _viewModel.RefreshAsync();
        await _viewModel.PublishAsync();
        _heartbeatTimer.Start();
    }

    private void EmbeddedNodeControl_Unloaded(object sender, RoutedEventArgs e)
    {
        _heartbeatTimer.Stop();
    }

    private async void HeartbeatTimer_Tick(object? sender, EventArgs e)
    {
        await _viewModel.RefreshAsync();
    }
}
