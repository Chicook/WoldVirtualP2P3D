// SeccionesMenu.cs
// Partial class auxiliar para el menú desplegable "☰ Secciones ▾" de la barra superior.
// Enruta los clics de los botones del Popup al handler original del code-behind.
//
// IMPORTANTE: Este archivo debe estar en el mismo namespace que MainWindow.xaml.cs
//             y compilarse junto con él (mismo proyecto).

using System.Windows;
using System.Windows.Controls;

namespace Visor3D
{
    public partial class MainWindow
    {
        // ─────────────────────────────────────────────────────────────────────
        //  Apertura / cierre del Popup
        // ─────────────────────────────────────────────────────────────────────

        private void BtnSecciones_Click(object sender, RoutedEventArgs e)
        {
            PopupSecciones.IsOpen = !PopupSecciones.IsOpen;
        }

        // ─────────────────────────────────────────────────────────────────────
        //  Enrutadores: cierran el popup y delegan al handler original
        // ─────────────────────────────────────────────────────────────────────

        private void BtnSecciones_VolverLucia_Click(object sender, RoutedEventArgs e)
        {
            PopupSecciones.IsOpen = false;
            // Reutiliza el mismo handler que tiene BtnVolverLucia en el code-behind principal.
            // Si el handler original es un evento Click enlazado por XAML, invocarlo así:
            BtnVolverLucia.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
        }

        private void BtnSecciones_OficinaAvatar_Click(object sender, RoutedEventArgs e)
        {
            PopupSecciones.IsOpen = false;
            BtnOficinaAvatar.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
        }

        private void BtnSecciones_InvitarLucia_Click(object sender, RoutedEventArgs e)
        {
            PopupSecciones.IsOpen = false;
            BtnInvitarLucia.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
        }

        private void BtnSecciones_Construir_Click(object sender, RoutedEventArgs e)
        {
            PopupSecciones.IsOpen = false;
            BtnConstruir.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
        }

        private async void BtnSecciones_ReiniciarConexion_Click(object sender, RoutedEventArgs e)
        {
            PopupSecciones.IsOpen = false;
            await ReiniciarConexionAsync();
        }

        private void BtnSecciones_Chat_Click(object sender, RoutedEventArgs e)
        {
            PopupSecciones.IsOpen = false;
            AlternarPanelChat();
        }

        private void BtnSecciones_Log_Click(object sender, RoutedEventArgs e)
        {
            PopupSecciones.IsOpen = false;
            OnDiagnosticoClicked(sender, e);
        }
    }
}
