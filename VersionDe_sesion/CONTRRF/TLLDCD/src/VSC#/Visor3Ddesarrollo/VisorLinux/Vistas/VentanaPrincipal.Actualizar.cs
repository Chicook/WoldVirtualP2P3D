using System;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;
using Avalonia.Controls;
using Visor3D.Linux;
using Visor3D.Update;

namespace Visor3D.Linux.Vistas
{
    public sealed partial class VentanaPrincipal
    {
        private readonly ActualizadorLinux _actualizador = new();
        private readonly TextBlock _txtActEstado = Interfaz.T("Sin comprobar.", 15, Interfaz.Suave, true);
        private readonly TextBlock _txtActInfo = Interfaz.Parrafo("—", Interfaz.Suave, 12);
        private readonly TextBlock _txtActProgreso = Interfaz.Parrafo("", Interfaz.Acento, 12);
        private readonly StackPanel _panelPaquetes = Interfaz.Vertical(3);

        private Button _btnActBuscar = null!;
        private Button _btnActDescargar = null!;
        private ReleaseInfo? _actRelease;
        private bool _actOcupado;

        private Control ConstruirActualizar()
        {
            _btnActBuscar = Interfaz.Boton("Buscar actualizaciones", () => _ = BuscarActualizacionAsync(), principal: true);
            _btnActDescargar = Interfaz.Boton("Descargar paquete", () => _ = DescargarActualizacionAsync());
            _btnActDescargar.IsEnabled = false;

            var estado = Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Actualizaciones del visor Linux", 17, Interfaz.Texto, true),
                Interfaz.Parrafo($"Versión instalada: {RutasLinux.Version}", Interfaz.Texto, 13),
                Interfaz.Parrafo(
                    "Se consultan las mismas releases de GitHub que usa el visor de Windows, pero aquí se busca " +
                    "el paquete .tar.gz de Linux. El paquete incluye motor, mundo y este visor.", Interfaz.Suave, 12),
                _txtActEstado,
                _txtActInfo,
                _txtActProgreso,
                Interfaz.Horizontal(10, _btnActBuscar, _btnActDescargar)));

            var aplicar = Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Cómo se aplica", 16, Interfaz.Texto, true),
                Interfaz.Parrafo(ActualizadorLinux.ComoAplicar),
                Interfaz.Parrafo($"Carpeta de descargas: {ActualizadorLinux.Carpeta}", Interfaz.Suave, 12),
                Interfaz.Horizontal(10,
                    Interfaz.Boton("Abrir carpeta", AbrirCarpetaActualizaciones),
                    Interfaz.Boton("Volver a listar", RefrescarPaquetes))));

            var paquetes = Interfaz.Tarjeta(Interfaz.Vertical(
                10,
                Interfaz.T("Paquetes descargados", 16, Interfaz.Texto, true),
                _panelPaquetes));

            RefrescarPaquetes();
            return Interfaz.Vertical(12, estado, aplicar, paquetes);
        }

        private async Task BuscarActualizacionAsync()
        {
            if (_actOcupado) return;
            _actOcupado = true;
            _btnActBuscar.IsEnabled = false;
            _btnActDescargar.IsEnabled = false;
            _actRelease = null;
            _txtActEstado.Text = "Consultando GitHub…";
            _txtActEstado.Foreground = Interfaz.Aviso;
            _txtActInfo.Text = "—";
            _txtActProgreso.Text = "";

            try
            {
                var release = await _actualizador.BuscarAsync(RutasLinux.Version);
                if (release == null)
                {
                    _txtActEstado.Text = _actualizador.UltimoError ?? "Ya tienes la última versión publicada para Linux.";
                    _txtActEstado.Foreground = _actualizador.UltimoError == null ? Interfaz.Bien : Interfaz.Mal;
                    return;
                }

                _actRelease = release;
                _txtActEstado.Text = $"Actualización disponible: {release.TagName}";
                _txtActEstado.Foreground = Interfaz.Aviso;

                double mb = release.AssetSize / 1048576.0;
                _txtActInfo.Text =
                    $"Paquete: {release.AssetName}{Environment.NewLine}" +
                    $"Tamaño: {(release.AssetSize > 0 ? mb.ToString("0.0") + " MB" : "desconocido")}{Environment.NewLine}" +
                    $"SHA-256: {DigestCorto(release.Digest)}{Environment.NewLine}" +
                    $"{(release.Prerelease ? "Canal: preliminar (prerelease)" : "Canal: estable")}";

                _btnActDescargar.IsEnabled = true;
                Estado($"Hay una versión nueva para Linux: {release.Version}.");
            }
            catch (Exception ex)
            {
                _txtActEstado.Text = $"No se pudo comprobar: {ex.Message}";
                _txtActEstado.Foreground = Interfaz.Mal;
            }
            finally
            {
                _btnActBuscar.IsEnabled = true;
                _actOcupado = false;
            }
        }

        private async Task DescargarActualizacionAsync()
        {
            var release = _actRelease;
            if (release == null || _actOcupado) return;

            _actOcupado = true;
            _btnActBuscar.IsEnabled = false;
            _btnActDescargar.IsEnabled = false;
            _txtActEstado.Text = "Descargando paquete…";
            _txtActEstado.Foreground = Interfaz.Aviso;

            var progreso = new Progress<DownloadProgress>(p =>
            {
                _txtActProgreso.Text = p.TotalBytes > 0
                    ? $"{p.Percentage:0.0} % — {p.BytesReceived / 1048576.0:0.0} de {p.TotalBytes / 1048576.0:0.0} MB"
                    : $"{p.BytesReceived / 1048576.0:0.0} MB";
            });

            try
            {
                string? ruta = await _actualizador.DescargarAsync(release, progreso);
                if (ruta == null)
                {
                    _txtActEstado.Text = _actualizador.UltimoError ?? "No se pudo descargar el paquete.";
                    _txtActEstado.Foreground = Interfaz.Mal;
                    Estado("La descarga de la actualización falló.", error: true);
                    return;
                }

                _txtActEstado.Text = "Paquete descargado y verificado.";
                _txtActEstado.Foreground = Interfaz.Bien;
                _txtActProgreso.Text = ruta;
                RefrescarPaquetes();
                Estado($"Actualización descargada en {ruta}. Ciérrame y extrae el paquete para aplicarla.");
            }
            catch (Exception ex)
            {
                _txtActEstado.Text = $"Error al descargar: {ex.Message}";
                _txtActEstado.Foreground = Interfaz.Mal;
            }
            finally
            {
                _btnActBuscar.IsEnabled = true;
                _btnActDescargar.IsEnabled = _actRelease != null;
                _actOcupado = false;
            }
        }

        private void RefrescarPaquetes()
        {
            _panelPaquetes.Children.Clear();

            try
            {
                if (!Directory.Exists(ActualizadorLinux.Carpeta))
                {
                    _panelPaquetes.Children.Add(Interfaz.Parrafo("Todavía no hay paquetes descargados.", Interfaz.Suave, 12));
                    return;
                }

                var archivos = Directory.GetFiles(ActualizadorLinux.Carpeta, "*.tar.gz");
                if (archivos.Length == 0)
                {
                    _panelPaquetes.Children.Add(Interfaz.Parrafo("Todavía no hay paquetes descargados.", Interfaz.Suave, 12));
                    return;
                }

                Array.Sort(archivos, StringComparer.OrdinalIgnoreCase);
                foreach (string archivo in archivos)
                {
                    var info = new FileInfo(archivo);
                    _panelPaquetes.Children.Add(Interfaz.Parrafo(
                        $"{info.Name} — {info.Length / 1048576.0:0.0} MB ({info.LastWriteTime:yyyy-MM-dd HH:mm})",
                        Interfaz.Texto, 12));
                }
            }
            catch (Exception ex)
            {
                _panelPaquetes.Children.Add(Interfaz.Parrafo($"No se pudo leer la carpeta: {ex.Message}", Interfaz.Mal, 12));
            }
        }

        private void AbrirCarpetaActualizaciones()
        {
            try
            {
                Directory.CreateDirectory(ActualizadorLinux.Carpeta);
                if (OperatingSystem.IsLinux())
                    Process.Start("xdg-open", ActualizadorLinux.Carpeta);
                else
                    Process.Start(new ProcessStartInfo(ActualizadorLinux.Carpeta) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                Estado($"No se pudo abrir la carpeta: {ex.Message}", error: true);
            }
        }

        private static string DigestCorto(string? digest)
        {
            if (string.IsNullOrWhiteSpace(digest)) return "no publicado";
            string limpio = digest.StartsWith("sha256:", StringComparison.OrdinalIgnoreCase)
                ? digest["sha256:".Length..]
                : digest;
            return limpio.Length <= 16 ? limpio : limpio[..16] + "…";
        }
    }
}
