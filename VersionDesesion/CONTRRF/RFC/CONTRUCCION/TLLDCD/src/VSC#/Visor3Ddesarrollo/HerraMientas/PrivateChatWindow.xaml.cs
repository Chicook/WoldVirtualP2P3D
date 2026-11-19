using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;

namespace Visor3D
{
    public sealed record MensajePrivado(bool Propio, string Autor, string Texto);

    public partial class PrivateChatWindow : Window
    {
        private readonly Action<string> _enviar;
        private readonly Action<PrivateChatWindow>? _alCerrar;

        public string FriendUid { get; }
        public string FriendName { get; }

        /// <summary>Se dispara cuando la ventana pasa a primer plano para marcar como leída.</summary>
        public event Action<PrivateChatWindow>? Leido;

        public PrivateChatWindow(
            string uid,
            string nombre,
            Action<string> enviar,
            Action<PrivateChatWindow>? alCerrar)
        {
            InitializeComponent();

            FriendUid = uid;
            FriendName = nombre;
            _enviar = enviar;
            _alCerrar = alCerrar;

            TxtTitulo.Text = $"🔒 {nombre}";
            BtnEnviar.Click += (s, e) => Enviar();
            TxtMensaje.KeyDown += OnMensajeKeyDown;
            Activated += (s, e) => Leido?.Invoke(this);
            Closing += (s, e) => _alCerrar?.Invoke(this);

            Loaded += (s, e) =>
            {
                TxtMensaje.Focus();
                TxtMensaje.CaretIndex = TxtMensaje.Text.Length;
            };
        }

        public void SetEnLinea(bool enLinea)
        {
            TxtEstado.Text = enLinea ? "🟢 En línea" : "⚪ Sin conexión";
            TxtEstado.Foreground = new SolidColorBrush(
                enLinea ? Color.FromRgb(45, 212, 191) : Color.FromRgb(100, 116, 139));
        }

        public void CargarHistorial(IEnumerable<MensajePrivado> mensajes)
        {
            foreach (var mensaje in mensajes)
                AgregarMensaje(mensaje.Autor, mensaje.Texto, mensaje.Propio);
        }

        public void AgregarMensaje(string autor, string texto, bool propio)
        {
            var bloque = new TextBlock
            {
                TextWrapping = TextWrapping.Wrap,
                FontSize = 11.5,
                Margin = new Thickness(2, 1, 2, 1)
            };
            bloque.Inlines.Add(new Run
            {
                Text = autor + ": ",
                Foreground = new SolidColorBrush(propio
                    ? Color.FromRgb(45, 212, 191)
                    : Color.FromRgb(0, 217, 255)),
                FontWeight = FontWeights.Bold
            });
            bloque.Inlines.Add(new Run
            {
                Text = texto,
                Foreground = new SolidColorBrush(Color.FromRgb(226, 232, 240))
            });
            AnadirLinea(bloque);
        }

        public void AgregarSistema(string texto)
        {
            AnadirLinea(new TextBlock
            {
                Text = "· " + texto,
                TextWrapping = TextWrapping.Wrap,
                FontSize = 10.5,
                FontStyle = FontStyles.Italic,
                Foreground = new SolidColorBrush(Color.FromRgb(100, 116, 139)),
                Margin = new Thickness(2, 1, 2, 1)
            });
        }

        public void CerrarPorSesion()
        {
            try { Close(); } catch { }
        }

        private void AnadirLinea(TextBlock bloque)
        {
            ListaMensajes.Items.Add(bloque);
            while (ListaMensajes.Items.Count > 400)
                ListaMensajes.Items.RemoveAt(0);
            ListaMensajes.ScrollIntoView(bloque);
        }

        private void Enviar()
        {
            string texto = TxtMensaje.Text.Trim();
            if (texto.Length == 0) return;

            TxtMensaje.Clear();
            AgregarMensaje("Tú", texto, true);
            TxtMensaje.Focus();
            _enviar(texto);
        }

        private void OnMensajeKeyDown(object sender, KeyEventArgs e)
        {
            if (e.Key == Key.Enter)
            {
                Enviar();
                e.Handled = true;
            }
            else if (e.Key == Key.Escape)
            {
                Close();
                e.Handled = true;
            }
        }
    }
}
