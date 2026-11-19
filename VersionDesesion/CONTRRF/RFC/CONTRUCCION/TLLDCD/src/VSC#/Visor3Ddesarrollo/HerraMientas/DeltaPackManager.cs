using System;
using System.IO;
using System.IO.Compression;
using System.Linq;

namespace Visor3D
{
    /// <summary>
    /// Resuelve la base inmutable 2.8.6 para el PCK delta 2.8.7.
    /// La base original nunca se reescribe: se reutiliza el runtime instalado o se
    /// extrae una copia de mundo/wvp3d.pck desde el ZIP de la carpeta 2.8.6.
    /// </summary>
    public static class DeltaPackManager
    {
        private const string VersionBase = "2.8.6";

        public static string BasePckPath
        {
            get
            {
                string? cache = Environment.GetEnvironmentVariable("WOLD_BASE_PCK_CACHE");
                if (!string.IsNullOrWhiteSpace(cache)) return Path.Combine(cache, "wvp3d.pck");
                return Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "WoldVirtualP2P3D", "base_packs", VersionBase, "wvp3d.pck");
            }
        }

        public static bool EnsureBasePackAvailable()
        {
            try
            {
                if (EsPckValido(BasePckPath)) return true;

                string runtimeAnterior = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "WoldVirtualP2P3D", "runtime", VersionBase, "wvp3d.pck");
                if (EsPckValido(runtimeAnterior))
                {
                    CopiarPck(runtimeAnterior, BasePckPath);
                    return true;
                }

                string? archivoBase = BuscarPaqueteBase();
                if (archivoBase == null) return false;

                using var stream = File.OpenRead(archivoBase);
                using var zip = new ZipArchive(stream, ZipArchiveMode.Read);
                var entrada = zip.Entries.FirstOrDefault(e =>
                    string.Equals(e.FullName.Replace('\\', '/'), "mundo/wvp3d.pck",
                        StringComparison.OrdinalIgnoreCase));
                if (entrada == null || entrada.Length < 100L * 1024 * 1024) return false;

                Directory.CreateDirectory(Path.GetDirectoryName(BasePckPath)!);
                using var entradaStream = entrada.Open();
                using var salida = File.Create(BasePckPath);
                entradaStream.CopyTo(salida);
                return salida.Length >= 100L * 1024 * 1024;
            }
            catch (Exception ex)
            {
                Services.VisorLog.Warn($"[Delta DAO] No se pudo preparar la base 2.8.6: {ex.Message}");
                return false;
            }
        }

        private static bool EsPckValido(string ruta) =>
            File.Exists(ruta) && new FileInfo(ruta).Length >= 100L * 1024 * 1024;

        private static void CopiarPck(string origen, string destino)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(destino)!);
            File.Copy(origen, destino, overwrite: true);
        }

        private static string? BuscarPaqueteBase()
        {
            string? actual = AppContext.BaseDirectory;
            for (int i = 0; i < 10 && actual != null; i++)
            {
                string vecino = Path.Combine(actual,
                    $"LCDMWoldVirtualP2P3Dv{VersionBase}", "actualizacion_v2.8.4.zip");
                if (File.Exists(vecino)) return vecino;
                actual = Directory.GetParent(actual)?.FullName;
            }

            string? src = GodotConfig.SrcActivo();
            if (src != null)
            {
                string respaldo = Path.Combine(src, "VSC#", "Visor3Ddesarrollo",
                    "CopiaDeSeguridad", "actualizacion_v2.8.4.zip");
                if (File.Exists(respaldo)) return respaldo;
            }
            return null;
        }
    }
}
