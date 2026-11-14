using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Reflection;

namespace Visor3D.CargaVolatil
{
    /// <summary>
    /// Carga volátil del paquete de actualización embebido en el ejecutable.
    ///
    /// El .zip (mundo Godot + modelos de Lucía + configuración de cuenta/sesión)
    /// viaja como recurso embebido y se lee directamente desde los bytes del
    /// ensamblado, sin pasar por ficheros sueltos:
    ///
    ///   • Configuración (<c>config/cuenta.json</c>, <c>config/sesion.yaml</c>,
    ///     <c>config/version.json</c>, <c>manifest.json</c>) → SOLO en RAM.
    ///     Nunca se escribe en disco: son credenciales/estado de sesión.
    ///   • Mundo y modelos → se materializan en un directorio temporal único.
    ///     Es el mínimo imprescindible: Godot 4 no monta un PCK desde un stream
    ///     (exige ruta de fichero con <c>--main-pack</c>) y onnxruntime también
    ///     necesita rutas en disco. Ese directorio se borra en <see cref="Liberar"/>.
    ///
    /// <see cref="Liberar"/> se invoca al cerrar la aplicación (App.Exit) y como
    /// red de seguridad en ProcessExit, liberando los buffers en RAM y purgando
    /// el directorio temporal.
    /// </summary>
    public static class VolatilePackage
    {
        // Nombre lógico estable del recurso (el .csproj fija el LogicalName aunque
        // el fichero en disco se llame actualizacion_v2.8.1.zip).
        private const string ResourceName = "Visor3D.actualizacion_volatil.zip";

        private static readonly object Gate = new object();

        // Configuración solo en RAM.
        private static string? _cuentaJson;
        private static string? _sesionYaml;
        private static string? _versionJson;
        private static string? _manifestJson;

        // Materialización mínima en disco (mundo + modelos).
        private static string? _tempDir;
        private static string? _pckPath;

        /// <summary>True si el paquete volátil quedó montado y listo para usarse.</summary>
        public static bool Disponible { get; private set; }

        /// <summary>Ruta temporal del PCK (o null si no se montó). Válida hasta <see cref="Liberar"/>.</summary>
        public static string? PckVolatilPath => _pckPath;

        /// <summary>Directorio temporal raíz del paquete (mundo/ + lucia/).</summary>
        public static string? TempDir => _tempDir;

        /// <summary>cuenta.json en RAM (texto crudo) — nunca en disco.</summary>
        public static string? CuentaJson => _cuentaJson;

        /// <summary>sesion.yaml en RAM (texto crudo) — nunca en disco.</summary>
        public static string? SesionYaml => _sesionYaml;

        /// <summary>version.json en RAM.</summary>
        public static string? VersionJson => _versionJson;

        /// <summary>manifest.json en RAM (SHA-256 + tamaños).</summary>
        public static string? ManifestJson => _manifestJson;

        /// <summary>
        /// Monta el paquete volátil. Idempotente: si ya está montado no hace nada.
        /// Devuelve true si el recurso está embebido y quedó listo; false si no
        /// existe (build sin el .zip) y el visor debe caer al flujo clásico.
        /// </summary>
        public static bool EnsureReady()
        {
            lock (Gate)
            {
                if (Disponible) return true;

                var asm = Assembly.GetExecutingAssembly();
                using Stream? recurso = asm.GetManifestResourceStream(ResourceName);
                if (recurso == null) return false;

                // Copiar el zip entero a memoria: a partir de aquí el disco no
                // participa en la lectura del paquete.
                using var memoria = new MemoryStream();
                recurso.CopyTo(memoria);
                memoria.Position = 0;

                string dir = Path.Combine(Path.GetTempPath(), "wvp_vol_" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(dir);
                string raizFull = Path.GetFullPath(dir);

                string? pck = null;

                using (var zip = new ZipArchive(memoria, ZipArchiveMode.Read))
                {
                    foreach (var entry in zip.Entries)
                    {
                        if (string.IsNullOrEmpty(entry.Name)) continue; // carpeta

                        string limpio = entry.FullName.Replace('/', Path.DirectorySeparatorChar).TrimStart(Path.DirectorySeparatorChar);
                        string destino = Path.GetFullPath(Path.Combine(raizFull, limpio));
                        if (!destino.StartsWith(raizFull + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                            continue; // zip-slip

                        switch (Normalizar(limpio))
                        {
                            case "config/cuenta.json":
                                _cuentaJson = LeerTexto(entry);
                                break;
                            case "config/sesion.yaml":
                                _sesionYaml = LeerTexto(entry);
                                break;
                            case "config/version.json":
                                _versionJson = LeerTexto(entry);
                                break;
                            case "manifest.json":
                                _manifestJson = LeerTexto(entry);
                                break;
                            default:
                                // Mundo y modelos: materialización mínima en disco.
                                string? padre = Path.GetDirectoryName(destino);
                                if (!string.IsNullOrEmpty(padre)) Directory.CreateDirectory(padre);
                                using (var fs = File.Create(destino))
                                    entry.Open().CopyTo(fs);
                                if (string.Equals(Normalizar(limpio), "mundo/wvp3d.pck", StringComparison.OrdinalIgnoreCase))
                                    pck = destino;
                                break;
                        }
                    }
                }

                _tempDir = raizFull;
                _pckPath = pck;
                Disponible = true;

                // Punto de enganche para procesos hijos (Godot, Python/Lucía):
                // encuentran el materializado sin depender de rutas del repo.
                Environment.SetEnvironmentVariable("WOLD_VOLATIL_DIR", raizFull);
                Environment.SetEnvironmentVariable("WOLD_VOLATIL_PCK", pck ?? "");
                return true;
            }
        }

        /// <summary>
        /// Libera todo: buffers en RAM a null y borrado del directorio temporal.
        /// Mejor esfuerzo (los ficheros que Godot aún tenga abiertos se reintentan).
        /// </summary>
        public static void Liberar()
        {
            lock (Gate)
            {
                _cuentaJson = null;
                _sesionYaml = null;
                _versionJson = null;
                _manifestJson = null;
                _pckPath = null;

                if (_tempDir != null && Directory.Exists(_tempDir))
                {
                    for (int intento = 0; intento < 5; intento++)
                    {
                        try
                        {
                            Directory.Delete(_tempDir, recursive: true);
                            break;
                        }
                        catch
                        {
                            System.Threading.Thread.Sleep(120);
                        }
                    }
                }
                _tempDir = null;
                Disponible = false;
            }
        }

        private static string? LeerTexto(ZipArchiveEntry entry)
        {
            using var lector = new StreamReader(entry.Open());
            return lector.ReadToEnd();
        }

        private static string Normalizar(string ruta) =>
            ruta.Replace('\\', '/').TrimStart('/');
    }
}
