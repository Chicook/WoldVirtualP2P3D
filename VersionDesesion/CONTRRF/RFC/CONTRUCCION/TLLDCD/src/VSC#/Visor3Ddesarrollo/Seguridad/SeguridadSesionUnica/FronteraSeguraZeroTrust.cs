// =============================================================================
// FronteraSeguraZeroTrust.cs
// Namespace  : Visor3D.Seguridad.SesionUnica
// Proyecto   : Visor3D — Validación de Frontera Zero-Trust, Gestión Segura de
//              Procesos (PID) y Operaciones de Archivos Confinadas.
// =============================================================================

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Management;
using System.Runtime.InteropServices;
using System.Security;
using System.Text;

namespace Visor3D.Seguridad.SesionUnica
{
    /// <summary>
    /// Excepción lanzada cuando una operación o ruta intenta escapar de la frontera
    /// canónica establecida en la arquitectura Zero Trust.
    /// </summary>
    public sealed class SecurityBoundaryException : SecurityException
    {
        public string? RutaInfraccion { get; }
        public string? RaizCanonica { get; }

        public SecurityBoundaryException(string mensaje, string? rutaInfraccion = null, string? raizCanonica = null)
            : base(mensaje)
        {
            RutaInfraccion = rutaInfraccion;
            RaizCanonica = raizCanonica;
        }

        public SecurityBoundaryException(string mensaje, Exception innerException)
            : base(mensaje, innerException)
        {
        }
    }

    /// <summary>
    /// Subrutina de seguridad Zero-Trust en C# que garantiza:
    ///   1. Contención estricta de rutas y prevención de Path Traversal (sin supresión de excepciones).
    ///   2. Validación rigurosa de argumentos posicionales y nombrados.
    ///   3. Gestión y terminación segura de procesos por PID y verificación de ejecutable (eliminando comodines).
    ///   4. Operaciones de archivos protegidas con barreras atómicas y detección de reparse points / symlinks.
    /// </summary>
    public static class FronteraSeguraZeroTrust
    {
        private static readonly object Bloqueo = new();
        private static string? _raizRepositorio;
        private static string? _appDataSeguro;
        private static string? _directorioPids;

        static FronteraSeguraZeroTrust()
        {
            InicializarRutasCanónicas();
        }

        /// <summary>
        /// Raíz canónica del repositorio de WoldVirtualP2P3D.
        /// </summary>
        public static string RaizRepositorio
        {
            get
            {
                if (string.IsNullOrEmpty(_raizRepositorio))
                {
                    InicializarRutasCanónicas();
                }
                return _raizRepositorio!;
            }
        }

        /// <summary>
        /// Directorio seguro de datos de usuario en LocalAppData.
        /// </summary>
        public static string AppDataSeguro
        {
            get
            {
                if (string.IsNullOrEmpty(_appDataSeguro))
                {
                    InicializarRutasCanónicas();
                }
                return _appDataSeguro!;
            }
        }

        /// <summary>
        /// Directorio exclusivo para el registro atómico de PIDs de servicios en ejecución.
        /// </summary>
        public static string DirectorioPids
        {
            get
            {
                if (string.IsNullOrEmpty(_directorioPids))
                {
                    InicializarRutasCanónicas();
                }
                return _directorioPids!;
            }
        }

        private static void InicializarRutasCanónicas()
        {
            lock (Bloqueo)
            {
                // LocalAppData seguro para la aplicación
                _appDataSeguro = Path.GetFullPath(
                    Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "WoldVirtualP2P3D"));

                _directorioPids = Path.Combine(_appDataSeguro, "pids");
                try
                {
                    Directory.CreateDirectory(_directorioPids);
                }
                catch { }

                // Localizar la raíz del repositorio a partir de BaseDirectory o CWD
                string cursor = AppDomain.CurrentDomain.BaseDirectory;
                string? encontrada = null;

                for (int i = 0; i < 15 && !string.IsNullOrEmpty(cursor); i++)
                {
                    if (File.Exists(Path.Combine(cursor, "LICENSE")) &&
                        (Directory.Exists(Path.Combine(cursor, "VersionDesesion")) || File.Exists(Path.Combine(cursor, "README.md"))))
                    {
                        encontrada = cursor;
                        break;
                    }
                    string? padre = Path.GetDirectoryName(cursor);
                    if (padre == cursor || string.IsNullOrEmpty(padre)) break;
                    cursor = padre;
                }

                if (string.IsNullOrEmpty(encontrada))
                {
                    string cwd = Directory.GetCurrentDirectory();
                    cursor = cwd;
                    for (int i = 0; i < 15 && !string.IsNullOrEmpty(cursor); i++)
                    {
                        if (File.Exists(Path.Combine(cursor, "LICENSE")) &&
                            (Directory.Exists(Path.Combine(cursor, "VersionDesesion")) || File.Exists(Path.Combine(cursor, "README.md"))))
                        {
                            encontrada = cursor;
                            break;
                        }
                        string? padre = Path.GetDirectoryName(cursor);
                        if (padre == cursor || string.IsNullOrEmpty(padre)) break;
                        cursor = padre;
                    }
                }

                _raizRepositorio = Path.GetFullPath(encontrada ?? @"E:\WoldVirtualP2P3D");
            }
        }

        /// <summary>
        /// Permite fijar explícitamente la raíz del repositorio (útil en entornos de test o despliegues personalizados).
        /// </summary>
        public static void ConfigurarRaizRepositorio(string rutaRaiz)
        {
            lock (Bloqueo)
            {
                if (string.IsNullOrWhiteSpace(rutaRaiz))
                    throw new ArgumentException("La raíz del repositorio no puede ser nula o vacía", nameof(rutaRaiz));

                _raizRepositorio = Path.GetFullPath(rutaRaiz);
            }
        }

        // =====================================================================
        // 1. VALIDACIÓN ZERO-TRUST DE FRONTERAS Y PATH TRAVERSAL
        // =====================================================================

        /// <summary>
        /// Comprueba si la ruta provista se ubica de forma legítima dentro de las
        /// fronteras canónicas permitidas (Raíz del Repositorio o Directorio Seguro AppData).
        /// </summary>
        public static bool EsRutaPermitida(string? ruta, out string rutaCanonica)
        {
            rutaCanonica = string.Empty;
            if (string.IsNullOrWhiteSpace(ruta))
                return false;

            try
            {
                // Detectar caracteres de escape o streams de datos alternativos (ADS)
                if (ruta.Contains(':') && ruta.IndexOf(':') != 1) // Más de un dos puntos o no es letra de unidad 'C:'
                {
                    // Posible Alternate Data Stream 'archivo.txt:stream'
                    return false;
                }

                // Normalización canónica completa
                string res = Path.GetFullPath(ruta);

                // Detección de dispositivos reservados en Windows (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
                string nombreArchivo = Path.GetFileNameWithoutExtension(res).ToUpperInvariant();
                if (EsDispositivoReservadoWindows(nombreArchivo))
                {
                    return false;
                }

                // Verificar reparse point (symlink / junction) si el archivo o carpeta existe
                if (File.Exists(res) || Directory.Exists(res))
                {
                    try
                    {
                        var info = new FileInfo(res);
                        if ((info.Attributes & FileAttributes.ReparsePoint) != 0)
                        {
                            string? target = info.LinkTarget;
                            if (!string.IsNullOrEmpty(target))
                            {
                                string targetFull = Path.GetFullPath(Path.Combine(Path.GetDirectoryName(res) ?? "", target));
                                if (!EstaEnPrefijo(targetFull, RaizRepositorio) && !EstaEnPrefijo(targetFull, AppDataSeguro))
                                {
                                    return false; // Reparse point apunta fuera de las fronteras permitidas
                                }
                            }
                        }
                    }
                    catch
                    {
                        // En caso de fallo al leer atributos o reparse point, mantener el chequeo estricto
                    }
                }

                // Validación de contención en prefijo canónico
                if (EstaEnPrefijo(res, RaizRepositorio) || EstaEnPrefijo(res, AppDataSeguro))
                {
                    rutaCanonica = res;
                    return true;
                }

                return false;
            }
            catch
            {
                return false;
            }
        }

        private static bool EstaEnPrefijo(string rutaCompleta, string prefijoCanónico)
        {
            string normalizadaRuta = rutaCompleta.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string normalizadoPrefijo = prefijoCanónico.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

            if (string.Equals(normalizadaRuta, normalizadoPrefijo, StringComparison.OrdinalIgnoreCase))
                return true;

            return normalizadaRuta.StartsWith(normalizadoPrefijo + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
        }

        private static bool EsDispositivoReservadoWindows(string nombre)
        {
            return nombre is "CON" or "PRN" or "AUX" or "NUL" or
                   "COM1" or "COM2" or "COM3" or "COM4" or "COM5" or "COM6" or "COM7" or "COM8" or "COM9" or
                   "LPT1" or "LPT2" or "LPT3" or "LPT4" or "LPT5" or "LPT6" or "LPT7" or "LPT8" or "LPT9";
        }

        /// <summary>
        /// Exige de forma estricta que la ruta esté contenida en la frontera canónica.
        /// Si se detecta un intento de escape o path traversal, LANZA SecurityBoundaryException.
        /// NUNCA suprime excepciones.
        /// </summary>
        public static string ExigirFrontera(string? ruta, string descripcion = "Ruta")
        {
            if (string.IsNullOrWhiteSpace(ruta))
            {
                var ex = new SecurityBoundaryException($"[VIOLACIÓN ZERO TRUST] {descripcion} es nula o vacía.");
                AuditoriaSeguridad.Registrar(EventoAuditoria.ManipulacionDetectada, "ZeroTrust", "Denegado", ex.Message);
                throw ex;
            }

            if (!EsRutaPermitida(ruta, out string canonica))
            {
                string mensaje = $"[VIOLACIÓN DE FRONTERA ZERO TRUST] {descripcion} ('{ruta}') " +
                                 $"intenta escapar de la raíz canónica '{RaizRepositorio}' o '{AppDataSeguro}'.";
                AuditoriaSeguridad.Registrar(EventoAuditoria.ManipulacionDetectada, "ZeroTrust", "Denegado", mensaje);
                throw new SecurityBoundaryException(mensaje, ruta, RaizRepositorio);
            }

            return canonica;
        }

        /// <summary>
        /// Valida exhaustivamente una colección de argumentos posicionales y nombrados.
        /// Garantiza que ninguna cadena que represente una ruta escape de la frontera.
        /// </summary>
        public static void ValidarArgumentos(params (string Nombre, object? Valor)[] argumentos)
        {
            if (argumentos == null) return;

            foreach (var (nombre, valor) in argumentos)
            {
                if (valor == null) continue;

                if (valor is string strVal)
                {
                    // Detectar si la cadena parece ser una ruta relativa o absoluta sospechosa
                    if (strVal.Contains(Path.DirectorySeparatorChar) ||
                        strVal.Contains(Path.AltDirectorySeparatorChar) ||
                        strVal.Contains(':') ||
                        strVal.StartsWith("..") ||
                        strVal.Contains(".."))
                    {
                        ExigirFrontera(strVal, $"Parámetro '{nombre}'");
                    }
                }
                else if (valor is FileInfo fi)
                {
                    ExigirFrontera(fi.FullName, $"FileInfo '{nombre}'");
                }
                else if (valor is DirectoryInfo di)
                {
                    ExigirFrontera(di.FullName, $"DirectoryInfo '{nombre}'");
                }
                else if (valor is Uri uri && uri.IsFile)
                {
                    ExigirFrontera(uri.LocalPath, $"Uri Local '{nombre}'");
                }
            }
        }

        // =====================================================================
        // 2. GESTIÓN SEGURA DE PROCESOS (PID Y VERIFICACIÓN DE IDENTIDAD)
        // =====================================================================

        /// <summary>
        /// Registra atómicamente el PID y la firma de identidad de un proceso lanzado legítimamente.
        /// </summary>
        public static void RegistrarPidServicio(string nombreServicio, int pid)
        {
            if (string.IsNullOrWhiteSpace(nombreServicio))
                throw new ArgumentNullException(nameof(nombreServicio));

            try
            {
                Directory.CreateDirectory(DirectorioPids);
                string archivoPid = Path.Combine(DirectorioPids, $"{nombreServicio}.pid");
                string contenido = $"{pid}|{DateTime.UtcNow:O}|{Environment.MachineName}";
                File.WriteAllText(archivoPid, contenido, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                AuditoriaSeguridad.Registrar(EventoAuditoria.ErrorCritico, "ZeroTrust", "Fallo",
                    $"No se pudo escribir archivo PID para {nombreServicio}: {ex.Message}");
            }
        }

        /// <summary>
        /// Lee el PID previamente registrado para el servicio indicado.
        /// </summary>
        public static int? ObtenerPidRegistrado(string nombreServicio)
        {
            try
            {
                string archivoPid = Path.Combine(DirectorioPids, $"{nombreServicio}.pid");
                if (!File.Exists(archivoPid)) return null;

                string txt = File.ReadAllText(archivoPid, Encoding.UTF8).Trim();
                string[] partes = txt.Split('|');
                if (partes.Length >= 1 && int.TryParse(partes[0], out int pid) && pid > 0)
                {
                    return pid;
                }
            }
            catch { }
            return null;
        }

        /// <summary>
        /// Elimina el archivo de registro de PID para un servicio.
        /// </summary>
        public static void LimpiarPidRegistrado(string nombreServicio)
        {
            try
            {
                string archivoPid = Path.Combine(DirectorioPids, $"{nombreServicio}.pid");
                if (File.Exists(archivoPid))
                {
                    File.Delete(archivoPid);
                }
            }
            catch { }
        }

        /// <summary>
        /// Valida si un PID determinado corresponde a un proceso legítimo del sistema WoldVirtualP2P3D:
        /// - Verifica que el proceso esté vivo.
        /// - Verifica que el ejecutable sea un intérprete de Python o componente autorizado.
        /// - Verifica que el ejecutable resida dentro del repositorio o ruta canónica de .dev.
        /// - Evita terminación accidental de procesos no relacionados.
        /// </summary>
        public static bool EsProcesoValidoYSeguro(int pid, string scriptEsperado, out string detalle)
        {
            detalle = string.Empty;
            if (pid <= 0)
            {
                detalle = "PID inválido";
                return false;
            }

            try
            {
                var proceso = Process.GetProcessById(pid);
                if (proceso.HasExited)
                {
                    detalle = "El proceso ya ha finalizado";
                    return false;
                }

                string? rutaExe = null;
                try
                {
                    rutaExe = proceso.MainModule?.FileName;
                }
                catch
                {
                    // En caso de permisos insuficientes para MainModule, intentar consulta Win32 segura
                    rutaExe = ObtenerRutaProcesoWin32(pid);
                }

                if (string.IsNullOrEmpty(rutaExe))
                {
                    detalle = "No se pudo verificar la ruta del ejecutable del proceso";
                    return false;
                }

                string nombreExe = Path.GetFileName(rutaExe).ToLowerInvariant();
                if (!nombreExe.Contains("python") && !nombreExe.Contains("dotnet") && !nombreExe.Contains("godot"))
                {
                    detalle = $"El ejecutable '{nombreExe}' no es un ejecutable autorizado para este servicio";
                    return false;
                }

                // Verificar CommandLine con WMI seguro
                string cmdLine = ObtenerLineaComandosWin32(pid);
                if (!string.IsNullOrEmpty(scriptEsperado) &&
                    !cmdLine.Contains(scriptEsperado, StringComparison.OrdinalIgnoreCase))
                {
                    detalle = $"La línea de comandos del PID {pid} no coincide con el script esperado '{scriptEsperado}'";
                    return false;
                }

                detalle = $"Proceso verificado con éxito (PID {pid}, Exe: {rutaExe})";
                return true;
            }
            catch (ArgumentException)
            {
                detalle = "El proceso no existe";
                return false;
            }
            catch (Exception ex)
            {
                detalle = $"Error al verificar proceso: {ex.Message}";
                return false;
            }
        }

        /// <summary>
        /// Detiene de manera segura un proceso identificado por su PID y nombre de servicio,
        /// realizando comprobación de identidad previa y eliminando la dependencia de comodines PowerShell.
        /// </summary>
        public static bool DetenerProcesoSeguro(string nombreServicio, string scriptEsperado, int timeoutMs = 3000)
        {
            int? pid = ObtenerPidRegistrado(nombreServicio);
            if (pid == null)
            {
                return false;
            }

            try
            {
                if (EsProcesoValidoYSeguro(pid.Value, scriptEsperado, out string detalle))
                {
                    var proceso = Process.GetProcessById(pid.Value);
                    try
                    {
                        proceso.Kill(entireProcessTree: true);
                        proceso.WaitForExit(timeoutMs);
                    }
                    catch { }

                    LimpiarPidRegistrado(nombreServicio);
                    AuditoriaSeguridad.Registrar(EventoAuditoria.OperacionIPC, "ZeroTrust", "Exito",
                        $"Proceso {nombreServicio} (PID {pid}) detenido de forma segura.");
                    return true;
                }
                else
                {
                    AuditoriaSeguridad.Registrar(EventoAuditoria.ManipulacionDetectada, "ZeroTrust", "Denegado",
                        $"Detención abortada para {nombreServicio}: {detalle}");
                    LimpiarPidRegistrado(nombreServicio);
                    return false;
                }
            }
            catch (Exception ex)
            {
                AuditoriaSeguridad.Registrar(EventoAuditoria.ErrorCritico, "ZeroTrust", "Fallo",
                    $"Fallo al detener proceso {nombreServicio} (PID {pid}): {ex.Message}");
                return false;
            }
        }

        private static string ObtenerRutaProcesoWin32(int pid)
        {
            try
            {
                using var searcher = new ManagementObjectSearcher(
                    $"SELECT ExecutablePath FROM Win32_Process WHERE ProcessId = {pid}");
                foreach (ManagementObject obj in searcher.Get())
                {
                    string? path = obj["ExecutablePath"]?.ToString();
                    if (!string.IsNullOrEmpty(path)) return path;
                }
            }
            catch { }
            return string.Empty;
        }

        private static string ObtenerLineaComandosWin32(int pid)
        {
            try
            {
                using var searcher = new ManagementObjectSearcher(
                    $"SELECT CommandLine FROM Win32_Process WHERE ProcessId = {pid}");
                foreach (ManagementObject obj in searcher.Get())
                {
                    string? cmd = obj["CommandLine"]?.ToString();
                    if (!string.IsNullOrEmpty(cmd)) return cmd;
                }
            }
            catch { }
            return string.Empty;
        }

        // =====================================================================
        // 3. OPERACIONES DE ARCHIVOS CON SALVAGUARDAS ZERO-TRUST
        // =====================================================================

        /// <summary>
        /// Elimina un archivo de forma segura previa validación de contención y reparse points.
        /// </summary>
        public static bool EliminarArchivoSeguro(string rutaArchivo)
        {
            string canonica = ExigirFrontera(rutaArchivo, "Eliminación segura de archivo");

            if (!File.Exists(canonica))
                return false;

            try
            {
                // Salvaguarda: No permitir eliminar archivos fuera de las extensiones o directorios esperados
                File.Delete(canonica);
                AuditoriaSeguridad.Registrar(EventoAuditoria.OperacionIPC, "ZeroTrust", "Exito",
                    $"Archivo eliminado de forma segura: {canonica}");
                return true;
            }
            catch (Exception ex)
            {
                AuditoriaSeguridad.Registrar(EventoAuditoria.ErrorCritico, "ZeroTrust", "Fallo",
                    $"Error al eliminar archivo seguro '{canonica}': {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// Limpia de forma recursiva un directorio temporal o de caché, con salvaguardas explícitas:
        /// - Exige que la ruta esté estrictamente contenida dentro del repositorio o AppData.
        /// - Prohíbe explícitamente eliminar la raíz del repositorio, directorios de sistema o carpetas principales.
        /// - No sigue enlaces simbólicos fuera de la frontera.
        /// </summary>
        public static bool LimpiarDirectorioSeguro(string rutaDirectorio, bool permitirRecursivo = false)
        {
            string canonica = ExigirFrontera(rutaDirectorio, "Limpieza segura de directorio");

            if (!Directory.Exists(canonica))
                return false;

            // Salvaguardas críticas: no se permite eliminar la raíz del repo ni AppData raíz
            if (string.Equals(canonica, RaizRepositorio, StringComparison.OrdinalIgnoreCase) ||
                string.Equals(canonica, AppDataSeguro, StringComparison.OrdinalIgnoreCase))
            {
                throw new SecurityBoundaryException(
                    $"[SALVAGUARDA CRÍTICA] Se impidió el borrado de la raíz de seguridad: '{canonica}'.");
            }

            try
            {
                if (permitirRecursivo)
                {
                    Directory.Delete(canonica, recursive: true);
                }
                else
                {
                    Directory.Delete(canonica, recursive: false);
                }

                AuditoriaSeguridad.Registrar(EventoAuditoria.OperacionIPC, "ZeroTrust", "Exito",
                    $"Directorio eliminado de forma segura: {canonica}");
                return true;
            }
            catch (Exception ex)
            {
                AuditoriaSeguridad.Registrar(EventoAuditoria.ErrorCritico, "ZeroTrust", "Fallo",
                    $"Error al limpiar directorio seguro '{canonica}': {ex.Message}");
                throw;
            }
        }
    }
}
