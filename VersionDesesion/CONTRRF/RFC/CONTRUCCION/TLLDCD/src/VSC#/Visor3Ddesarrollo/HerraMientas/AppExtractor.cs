using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows;
using Visor3D.Services;

namespace Visor3D
{
    /// <summary>
    /// Extrae los recursos embebidos (motor Godot, mundo .pck y LucIA) a
    /// %LOCALAPPDATA%\WoldVirtualP2P3D\runtime\<versión>\.
    /// Verifica su integridad antes de reutilizarlos.
    /// </summary>
    public static class AppExtractor
    {
        // El marcador de re-extracción es la versión del propio ensamblado, no una
        // constante a mano: un OTA reemplaza el .exe —y con él el PCK embebido—, y si
        // el marcador no se moviera el visor seguiría arrancando el mundo extraído por
        // una versión anterior.
        private static readonly string AppVersion = ObtenerVersionEnsamblado();

        /// <summary>Versión usada como marcador de re-extracción (informativa).</summary>
        public static string Version => AppVersion;

        /// <summary>En la prueba de arranque no debe aparecer ningún diálogo modal.</summary>
        public static bool SilentErrors { get; set; }

        private static string ObtenerVersionEnsamblado()
        {
            var info = typeof(AppExtractor).Assembly
                .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion;
            if (string.IsNullOrWhiteSpace(info)) return "0.0.0";

            int plus = info.IndexOf('+');          // descarta el sufijo "+<sha>"
            return (plus >= 0 ? info.Substring(0, plus) : info).Trim();
        }

        /// <summary>
        /// Carpeta de runtime. Se puede redirigir con la variable de entorno
        /// <c>WOLD_RUNTIME_DIR</c> (pruebas y modo portable); si no, LocalAppData.
        /// </summary>
        public static readonly string RuntimeDir = ResolverRuntimeDir();

        private static string ResolverRuntimeDir()
        {
            string? custom = Environment.GetEnvironmentVariable("WOLD_RUNTIME_DIR");
            if (!string.IsNullOrWhiteSpace(custom))
                return custom;

            return Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "WoldVirtualP2P3D", "runtime", AppVersion);
        }

        private static readonly string VersionFile = Path.Combine(RuntimeDir, ".extracted");

        public static string GodotExePath =>
            Path.Combine(RuntimeDir, "Servidor3D", $"Godot_v{WoldInfoVersion.Motor}-stable_win64.exe");

        /// <summary>Mundo empaquetado que se pasa a Godot con <c>--main-pack</c>.</summary>
        public static string PckPath => Path.Combine(RuntimeDir, "wvp3d.pck");

        /// <summary>Solo las builds delta antiguas embeben este parche; la 2.8.7 va completa.</summary>
        public static string DaoPatchPath => Path.Combine(RuntimeDir, "dao_patch.pck");

        /// <summary>La build actual lleva el mundo completo y no necesita la base 2.8.6.</summary>
        public static bool EmbebeMundoCompleto =>
            typeof(AppExtractor).Assembly.GetManifestResourceInfo("Visor3D.wvp3d.pck") != null;

        /// <summary>La build actual lleva un PCK delta que exige montar la base 2.8.6.</summary>
        public static bool EmbebeDeltaDao =>
            typeof(AppExtractor).Assembly.GetManifestResourceInfo("Visor3D.dao_patch.pck") != null;

        /// <summary>Proyecto suelto (solo modo desarrollo; ya no se extrae del .exe).</summary>
        public static string ProjectPath => Path.Combine(RuntimeDir, "WoldVirtualP2P3D");

        /// <summary>Plantilla del editor de construcción extraída del .exe.</summary>
        public static string ConstructorTemplateDir => Path.Combine(RuntimeDir, "ConstructorGodot");

        private const string LuciaResourceName = "Visor3D.lucia_runtime.zip";

        public static string LuciaDir => Path.Combine(RuntimeDir, "LucIA");
        public static string LuciaPythonPath => Path.Combine(LuciaDir, "python", "python.exe");
        public static string LuciaScriptPath => Path.Combine(LuciaDir, "celebro_3D", "puente_3D", "servidor_lucia.py");
        public static bool EmbebeLucia =>
            typeof(AppExtractor).Assembly.GetManifestResourceInfo(LuciaResourceName) != null;

        /// <summary>Extrae los recursos si no se ha hecho ya. Devuelve false si falla.</summary>
        public static bool EnsureExtracted()
        {
            try
            {
                var assembly = Assembly.GetExecutingAssembly();
                bool expectsPatch = assembly.GetManifestResourceInfo("Visor3D.dao_patch.pck") != null;
                bool expectsPck = assembly.GetManifestResourceInfo("Visor3D.wvp3d.pck") != null;
                bool expectsLucia = EmbebeLucia;
                string luciaHash = "";
                if (expectsLucia)
                {
                    using var luciaStream = assembly.GetManifestResourceStream(LuciaResourceName)
                        ?? throw new InvalidDataException("No se pudo leer el runtime embebido de LucIA.");
                    luciaHash = CalcularSha256(luciaStream);
                }
                if (File.Exists(VersionFile) &&
                    File.Exists(GodotExePath) &&
                    Directory.Exists(ConstructorTemplateDir))
                {
                    var lines = File.ReadAllLines(VersionFile);
                    if (lines.Length > 0 && lines[0].Trim() == AppVersion &&
                        Array.Exists(lines, line => line == "build_id=" + assembly.ManifestModule.ModuleVersionId))
                    {
                        string expectedPckHash = "";
                        string expectedGodotHash = "";
                        string expectedPatchHash = "";
                        string expectedLuciaHash = "";
                        for (int i = 1; i < lines.Length; i++)
                        {
                            if (lines[i].StartsWith("pck_sha256=", StringComparison.OrdinalIgnoreCase))
                                expectedPckHash = lines[i].Substring("pck_sha256=".Length).Trim();
                            else if (lines[i].StartsWith("godot_sha256=", StringComparison.OrdinalIgnoreCase))
                                expectedGodotHash = lines[i].Substring("godot_sha256=".Length).Trim();
                            else if (lines[i].StartsWith("dao_patch_sha256=", StringComparison.OrdinalIgnoreCase))
                                expectedPatchHash = lines[i].Substring("dao_patch_sha256=".Length).Trim();
                            else if (lines[i].StartsWith("lucia_sha256=", StringComparison.OrdinalIgnoreCase))
                                expectedLuciaHash = lines[i].Substring("lucia_sha256=".Length).Trim();
                        }

                        // Reutilizar solo si los hashes coinciden (H4: fiabilidad de extracción).
                        // El mundo completo es obligatorio en la build 2.8.7: un marcador de
                        // una build delta anterior no puede darse por válido.
                        bool pckOk = !expectsPck ||
                            (!string.IsNullOrEmpty(expectedPckHash) && CalcularSha256(PckPath) == expectedPckHash);
                        bool godotOk = string.IsNullOrEmpty(expectedGodotHash) || CalcularSha256(GodotExePath) == expectedGodotHash;
                        bool patchOk = !expectsPatch ||
                            (!string.IsNullOrEmpty(expectedPatchHash) && CalcularSha256(DaoPatchPath) == expectedPatchHash);
                        bool luciaOk = !expectsLucia ||
                            (expectedLuciaHash == luciaHash && VerificarLucia(assembly));
                        if (pckOk && godotOk && patchOk && luciaOk)
                        {
                            return true;
                        }
                    }
                }

                if (Directory.Exists(RuntimeDir))
                {
                    try
                    {
                        Directory.Delete(RuntimeDir, recursive: true);
                    }
                    catch (Exception ex)
                    {
                        // Un Godot anterior aún ejecutándose mantiene bloqueado el
                        // runtime. Seguir extrayendo dejaría media versión mezclada.
                        throw new IOException(
                            $"No se pudo limpiar el runtime anterior: {RuntimeDir}\n" +
                            "Cierra cualquier visor o proceso Godot que siga abierto.", ex);
                    }
                }
                Directory.CreateDirectory(RuntimeDir);

                // 1. Motor Godot → Servidor3D
                string servidorDir = Path.Combine(RuntimeDir, "Servidor3D");
                Directory.CreateDirectory(servidorDir);
                if (!ExtractResource(assembly, "Visor3D.godot_exe.zip", servidorDir))
                    return false;

                string godotEnServidor = GodotExePath;
                if (!File.Exists(godotEnServidor))
                {
                    var found = Directory.GetFiles(servidorDir, $"Godot_v{WoldInfoVersion.Motor}-stable_win64.exe", SearchOption.AllDirectories);
                    if (found.Length > 0 && found[0] != godotEnServidor)
                        File.Copy(found[0], godotEnServidor, overwrite: true);
                }

                // 2. Mundo empaquetado → wvp3d.pck. La 2.8.7 lo embebe completo;
                //    en builds delta viaja dentro del paquete volátil o no existe.
                bool pckExtraido = ExtractFile(assembly, "Visor3D.wvp3d.pck", PckPath);
                if (expectsPck && !pckExtraido)
                    throw new InvalidDataException("El mundo completo está embebido, pero no se pudo extraer.");

                // El parche incremental contiene solo los recursos cambiados desde 2.8.6.
                bool patchExtraido = ExtractFile(assembly, "Visor3D.dao_patch.pck", DaoPatchPath);
                if (expectsPatch && !patchExtraido)
                    throw new InvalidDataException("El parche DAO está embebido, pero no se pudo extraer.");

                // 3. Plantilla del editor de construcción (opcional).
                ExtractResource(assembly, "Visor3D.constructor_godot.zip", ConstructorTemplateDir);

                if (expectsLucia &&
                    (!ExtractResource(assembly, LuciaResourceName, LuciaDir) || !VerificarLucia(assembly)))
                    throw new InvalidDataException("El runtime de LucIA está incompleto o no coincide con el ZIP embebido.");

                string pckHash = CalcularSha256(PckPath) ?? "";
                string godotHash = CalcularSha256(godotEnServidor) ?? "";
                string patchHash = CalcularSha256(DaoPatchPath) ?? "";
                File.WriteAllLines(VersionFile, new[]
                {
                    AppVersion,
                    "build_id=" + assembly.ManifestModule.ModuleVersionId,
                    $"pck_sha256={pckHash}",
                    $"godot_sha256={godotHash}",
                    $"dao_patch_sha256={patchHash}",
                    $"lucia_sha256={luciaHash}"
                });
                return true;
            }
            catch (Exception ex)
            {
                VisorLog.Info($"[extracción] {ex.GetType().Name}: {ex.Message}");
                if (!SilentErrors)
                {
                    MessageBox.Show(
                        $"Error al preparar el motor 3D:\n{ex.Message}\n\nDirectorio: {RuntimeDir}",
                        "Error de extracción", MessageBoxButton.OK, MessageBoxImage.Error);
                }
                return false;
            }
        }

        private static bool VerificarLucia(Assembly assembly)
        {
            using var stream = assembly.GetManifestResourceStream(LuciaResourceName);
            if (stream == null) return false;

            using var archive = new ZipArchive(stream, ZipArchiveMode.Read);
            var esenciales = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                Path.GetFullPath(LuciaPythonPath),
                Path.GetFullPath(Path.Combine(LuciaDir, "python", "python315.dll")),
                Path.GetFullPath(LuciaScriptPath),
                Path.GetFullPath(Path.Combine(LuciaDir, "celebro_3D", "nucleo", "orquestador_lucia.py"))
            };

            foreach (var entry in archive.Entries)
            {
                if (string.IsNullOrEmpty(entry.Name)) continue;
                string targetPath = ResolverRutaEntrada(LuciaDir, entry.FullName);
                var file = new FileInfo(targetPath);
                if (!file.Exists || file.Length != entry.Length ||
                    (esenciales.Contains(targetPath) && entry.Length == 0))
                    return false;

                using var entryStream = entry.Open();
                if (CalcularSha256(entryStream) != CalcularSha256(targetPath)) return false;
                esenciales.Remove(targetPath);
            }

            return esenciales.Count == 0;
        }

        private static string CalcularSha256(Stream stream)
        {
            using var sha = System.Security.Cryptography.SHA256.Create();
            return Convert.ToHexString(sha.ComputeHash(stream)).ToLowerInvariant();
        }

        private static string? CalcularSha256(string path)
        {
            try
            {
                if (!File.Exists(path)) return null;
                using var fs = File.OpenRead(path);
                return CalcularSha256(fs);
            }
            catch
            {
                return null;
            }
        }

        private static string ResolverRutaEntrada(string destDir, string entryName)
        {
            string relativePath = entryName.Replace('\\', '/');
            if (Path.IsPathRooted(relativePath) || relativePath.Contains(':'))
                throw new InvalidDataException($"Ruta absoluta o inválida en ZIP: {entryName}");

            string destDirFull = Path.GetFullPath(destDir);
            string destDirWithSep = Path.EndsInDirectorySeparator(destDirFull)
                ? destDirFull
                : destDirFull + Path.DirectorySeparatorChar;
            string targetPath = Path.GetFullPath(Path.Combine(destDirFull, relativePath));
            if (!targetPath.StartsWith(destDirWithSep, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException($"Ruta fuera del directorio de extracción: {entryName}");
            return targetPath;
        }

        private static bool ExtractResource(Assembly asm, string resourceName, string destDir)
        {
            using Stream? stream = asm.GetManifestResourceStream(resourceName);
            if (stream == null)
            {
                // Si no está embebido (modo debug o sin recursos embebidos), omitir sin error fatal
                return false;
            }

            using var archive = new ZipArchive(stream, ZipArchiveMode.Read);

            foreach (var entry in archive.Entries)
            {
                if (string.IsNullOrEmpty(entry.Name)) continue; // Carpeta
                string targetPath = ResolverRutaEntrada(destDir, entry.FullName);

                string? parentDir = Path.GetDirectoryName(targetPath);
                if (!string.IsNullOrEmpty(parentDir) && !Directory.Exists(parentDir))
                {
                    Directory.CreateDirectory(parentDir);
                }

                entry.ExtractToFile(targetPath, overwrite: true);
            }

            return true;
        }

        /// <summary>Copia un recurso embebido tal cual (el PCK no es un ZIP).</summary>
        private static bool ExtractFile(Assembly asm, string resourceName, string destPath)
        {
            using Stream? stream = asm.GetManifestResourceStream(resourceName);
            if (stream == null) return false;

            string? dir = Path.GetDirectoryName(destPath);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

            using var fs = File.Create(destPath);
            stream.CopyTo(fs);
            return true;
        }
    }
}
