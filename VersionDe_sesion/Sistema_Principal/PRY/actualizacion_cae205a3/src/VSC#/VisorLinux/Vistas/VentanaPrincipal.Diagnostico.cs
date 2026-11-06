using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using Avalonia.Controls;
using Avalonia.Controls.Primitives;
using Avalonia.Media;
using Visor3D.Linux;
using Visor3D.Seguridad;
using Visor3D.Seguridad.SesionUnica;
using Visor3D.Services;

namespace Visor3D.Linux.Vistas
{
    public sealed partial class VentanaPrincipal
    {
        private readonly TextBlock _txtDiagnostico = new()
        {
            FontFamily = new FontFamily("Consolas, DejaVu Sans Mono, monospace"),
            FontSize = 12,
            Foreground = Interfaz.Texto,
            TextWrapping = TextWrapping.Wrap,
        };

        private Control ConstruirDiagnostico() => Interfaz.Vertical(
            12,
            Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Diagnóstico del visor Linux", 17, Interfaz.Texto, true),
                Interfaz.Parrafo(
                    "Rutas efectivas, estado de cuenta, portal, túnel y motor. «Copiar diagnóstico» incluye las " +
                    "últimas líneas del registro.", Interfaz.Suave, 12),
                new ScrollViewer
                {
                    Height = 380,
                    Content = _txtDiagnostico,
                    HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
                },
                Interfaz.Horizontal(
                    10,
                    Interfaz.Boton("Actualizar", RefrescarDiagnostico, principal: true),
                    Interfaz.Boton("Copiar diagnóstico", () => Copiar(TextoDiagnostico())),
                    Interfaz.Boton("Abrir carpeta de registro", AbrirCarpetaRegistro),
                    Interfaz.Boton("Abrir datos del motor", AbrirDatosMotor)))));

        private void RefrescarDiagnostico()
        {
            _txtDiagnostico.Text = TextoDiagnostico();
        }

        private string TextoDiagnostico()
        {
            var sb = new StringBuilder();
            sb.AppendLine($"visor: {RutasLinux.Version} (Linux)");
            sb.AppendLine($"sistema: {RuntimeInformation.OSDescription} · {RuntimeInformation.ProcessArchitecture}");
            sb.AppendLine($"binario: {RutasLinux.BaseDir}");
            sb.AppendLine(RutasLinux.Resumen());
            sb.AppendLine();

            var estado = CuentaLinux.Estado(out string motivo);
            sb.AppendLine($"cuenta: {estado} ({motivo})");
            sb.AppendLine($"sesión: {(_dentro ? _nick + " · " + Corto(_uuid) : "sin iniciar")}");
            sb.AppendLine($"sello de equipo: {(RegistroPcUnico.YaExisteCuentaEnEstePc() ? "registrado" : "sin sello")}");
            sb.AppendLine($"perfil: {PerfilUsuario.BaseDir}");
            sb.AppendLine();

            string portal = _portal.IsRunning
                ? $"escuchando en http://localhost:{_portal.ActivePort}/"
                : "parado" + (_portal.StartError == null ? "" : " (" + _portal.StartError + ")");
            sb.AppendLine($"portal WebNodo: {portal}");
            sb.AppendLine($"túnel público: {(_portal.PublicTunnelUrl ?? "sin túnel")}");
            sb.AppendLine(_portal.ChatEnabled
                ? $"chat: relay en {_portal.ChatLocalPort}"
                : "chat: relay parado");

            string red = _red == null
                ? "nodo P2P detenido"
                : $"nodo P2P activo · túnel {(_red.UrlPublicaPropia ?? "pendiente")} · {_red.Nodo.Pares.Count} par(es)";
            sb.AppendLine(red);

            sb.AppendLine(_motor.EnEjecucion
                ? $"motor: en ejecución (PID {_motor.IdProceso})"
                : "motor: detenido");
            sb.AppendLine();

            sb.AppendLine($"registro: {VisorLog.ArchivoActual}");
            sb.AppendLine();
            sb.AppendLine("— últimas líneas del registro —");
            sb.Append(VisorLog.Cola(30));
            return sb.ToString();
        }

        private void AbrirCarpetaRegistro() => AbrirCarpeta(VisorLog.Carpeta, "el registro");

        private void AbrirDatosMotor() => AbrirCarpeta(RutasLinux.GodotUserDir, "los datos del motor");

        private void AbrirCarpeta(string ruta, string etiqueta)
        {
            try
            {
                Directory.CreateDirectory(ruta);
                if (OperatingSystem.IsLinux())
                    Process.Start("xdg-open", ruta);
                else
                    Process.Start(new ProcessStartInfo(ruta) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                Estado($"No se pudo abrir la carpeta de {etiqueta}: {ex.Message}", error: true);
            }
        }
    }
}
