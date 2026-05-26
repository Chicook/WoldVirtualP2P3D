using System.Windows;
using ServidorVirtualCS.ViewModels;

namespace ServidorVirtualCS;

public partial class MainWindow : Window
{
    private readonly EmbeddedNodeViewModel _viewModel = new();

    public MainWindow()
    {
        InitializeComponent();
        DataContext = _viewModel;
        Loaded += MainWindow_Loaded;
        Closed += MainWindow_Closed;
    }

    private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
    {
        await _viewModel.RefreshAsync();
        await _viewModel.PublishAsync();
    }

    private void MainWindow_Closed(object? sender, EventArgs e)
    {
        _viewModel.Dispose();
    }

    private async void RefreshButton_Click(object sender, RoutedEventArgs e)
    {
        await _viewModel.RefreshAsync();
    }
}
