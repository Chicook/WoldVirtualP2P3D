using Avalonia;
using Avalonia.Controls;
using Avalonia.Layout;
using Avalonia.Media;

namespace Visor3D.Linux.Vistas
{
    /// <summary>Paleta y constructores de controles: la ventana se arma en C#.</summary>
    internal static class Interfaz
    {
        public static IBrush C(string hex) => new SolidColorBrush(Color.Parse(hex));

        public static readonly IBrush Fondo = C("#07111B");
        public static readonly IBrush Panel = C("#0F1E2B");
        public static readonly IBrush Borde = C("#1E3A4F");
        public static readonly IBrush Acento = C("#00D9FF");
        public static readonly IBrush Texto = C("#E6F1F8");
        public static readonly IBrush Suave = C("#93A9BA");
        public static readonly IBrush Bien = C("#3DDC97");
        public static readonly IBrush Mal = C("#FF6B6B");
        public static readonly IBrush Aviso = C("#FFC46B");

        public static TextBlock T(string texto, double tam = 14, IBrush? color = null, bool negrita = false) => new()
        {
            Text = texto,
            FontSize = tam,
            Foreground = color ?? Texto,
            FontWeight = negrita ? FontWeight.SemiBold : FontWeight.Normal,
            TextWrapping = TextWrapping.Wrap,
        };

        public static TextBlock Parrafo(string texto, IBrush? color = null, double tam = 13)
            => T(texto, tam, color ?? Suave);

        public static StackPanel Vertical(double separacion, params Control[] hijos)
        {
            var panel = new StackPanel { Orientation = Orientation.Vertical, Spacing = separacion };
            foreach (Control hijo in hijos) panel.Children.Add(hijo);
            return panel;
        }

        public static StackPanel Horizontal(double separacion, params Control[] hijos)
        {
            var panel = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                Spacing = separacion,
                VerticalAlignment = VerticalAlignment.Center,
            };
            foreach (Control hijo in hijos) panel.Children.Add(hijo);
            return panel;
        }

        public static Border Tarjeta(Control hijo) => new()
        {
            Background = Panel,
            BorderBrush = Borde,
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(10),
            Padding = new Thickness(16),
            Child = hijo,
        };

        public static TextBox Campo(string marcador, string? valor = null, double ancho = 300, bool contrasena = false) => new()
        {
            Watermark = marcador,
            Text = valor ?? "",
            Width = ancho,
            FontSize = 14,
            PasswordChar = contrasena ? '•' : '\0',
        };

        public static Button Boton(string texto, Action alPulsar, bool principal = false)
        {
            var boton = new Button
            {
                Content = texto,
                Padding = new Thickness(14, 8),
                CornerRadius = new CornerRadius(8),
                FontWeight = FontWeight.SemiBold,
            };
            if (principal)
            {
                boton.Background = Acento;
                boton.Foreground = C("#04131C");
            }
            boton.Click += (_, _) => alPulsar();
            return boton;
        }

        public static Border Etiqueta(string texto, IBrush color) => new()
        {
            Background = color,
            CornerRadius = new CornerRadius(20),
            Padding = new Thickness(10, 3),
            VerticalAlignment = VerticalAlignment.Center,
            Child = T(texto, 12, C("#04131C"), true),
        };
    }
}
