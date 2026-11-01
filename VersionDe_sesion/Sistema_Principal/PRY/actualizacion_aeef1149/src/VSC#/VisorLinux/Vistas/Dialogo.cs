using System.Threading.Tasks;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Layout;

namespace Visor3D.Linux.Vistas
{
    /// <summary>Aviso y confirmación modales (Avalonia no trae MessageBox).</summary>
    internal sealed class Dialogo : Window
    {
        private Dialogo(string titulo, string mensaje, bool pregunta, string aceptar, string cancelar)
        {
            Title = titulo;
            Width = 480;
            SizeToContent = SizeToContent.Height;
            CanResize = false;
            WindowStartupLocation = WindowStartupLocation.CenterOwner;
            Background = Interfaz.Fondo;
            ShowInTaskbar = false;

            var botones = new System.Collections.Generic.List<Control>();
            if (pregunta)
            {
                botones.Add(Interfaz.Boton(cancelar, () => Close(false)));
                botones.Add(Interfaz.Boton(aceptar, () => Close(true), principal: true));
            }
            else
            {
                botones.Add(Interfaz.Boton(aceptar, () => Close(true), principal: true));
            }

            Content = Interfaz.Vertical(
                18,
                Interfaz.T(titulo, 18, Interfaz.Acento, true),
                Interfaz.T(mensaje, 14),
                Interfaz.Horizontal(10, botones.ToArray()));
        }

        public static Task AvisarAsync(Window dueno, string titulo, string mensaje)
            => new Dialogo(titulo, mensaje, pregunta: false, aceptar: "Entendido", cancelar: "").ShowDialog<bool>(dueno);

        public static Task<bool> PreguntarAsync(Window dueno, string titulo, string mensaje,
                                                string aceptar = "Sí", string cancelar = "Cancelar")
            => new Dialogo(titulo, mensaje, pregunta: true, aceptar, cancelar).ShowDialog<bool>(dueno);
    }
}
