using ServidorVirtualCS.ViewModels;
using System.Windows;
using System.Windows.Controls;

namespace ServidorVirtualCS.Controls;

public partial class EmbeddedNodeControl : UserControl
{
    private readonly EmbeddedNodeViewModel _viewModel = new();

    public EmbeddedNodeControl()
    {
        InitializeComponent();
        DataContext = _viewModel;
        Loaded += EmbeddedNodeControl_Loaded;
        Unloaded += EmbeddedNodeControl_Unloaded;
    }

    private async void EmbeddedNodeControl_Loaded(object sender, RoutedEventArgs e)
    {
        await _viewModel.RefreshAsync();
        await _viewModel.PublishAsync();
    }

    private void EmbeddedNodeControl_Unloaded(object sender, RoutedEventArgs e)
    {
        _viewModel.Dispose();
    }
}
