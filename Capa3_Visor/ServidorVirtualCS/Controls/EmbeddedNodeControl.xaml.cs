using ServidorVirtualCS.ViewModels;
using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Threading;

namespace ServidorVirtualCS.Controls;

public partial class EmbeddedNodeControl : UserControl
{
    private readonly EmbeddedNodeViewModel _viewModel = new();
    private readonly DispatcherTimer _heartbeatTimer = new() { Interval = TimeSpan.FromSeconds(12) };
    private readonly DispatcherTimer _publishDebounceTimer = new() { Interval = TimeSpan.FromMilliseconds(650) };
    private bool _isLoaded;

    public EmbeddedNodeControl()
    {
        InitializeComponent();
        DataContext = _viewModel;
        Loaded += EmbeddedNodeControl_Loaded;
        Unloaded += EmbeddedNodeControl_Unloaded;
        _heartbeatTimer.Tick += HeartbeatTimer_Tick;
        _publishDebounceTimer.Tick += PublishDebounceTimer_Tick;
    }

    private async void EmbeddedNodeControl_Loaded(object sender, RoutedEventArgs e)
    {
        _isLoaded = true;
        await _viewModel.RefreshAsync();
        await _viewModel.PublishAsync();
        _heartbeatTimer.Start();
    }

    private void EmbeddedNodeControl_Unloaded(object sender, RoutedEventArgs e)
    {
        _isLoaded = false;
        _heartbeatTimer.Stop();
        _publishDebounceTimer.Stop();
    }

    private async void HeartbeatTimer_Tick(object? sender, EventArgs e)
    {
        await _viewModel.RefreshAsync();
    }

    private void BoostSlider_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
    {
        if (!_isLoaded)
        {
            return;
        }

        _publishDebounceTimer.Stop();
        _publishDebounceTimer.Start();
    }

    private void BoostSlider_PreviewMouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (sender is not Slider slider)
        {
            return;
        }

        Point position = e.GetPosition(slider);
        double ratio = Math.Clamp(position.X / Math.Max(1, slider.ActualWidth), 0.0, 1.0);
        double range = slider.Maximum - slider.Minimum;
        slider.Value = slider.Minimum + (range * ratio);
        e.Handled = false;
    }

    private async void PublishDebounceTimer_Tick(object? sender, EventArgs e)
    {
        _publishDebounceTimer.Stop();
        await _viewModel.PublishAsync();
    }
}
