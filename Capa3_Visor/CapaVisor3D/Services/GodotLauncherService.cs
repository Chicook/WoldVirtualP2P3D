using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;

using VisorSingularity.Interop;

namespace VisorSingularity.Services
{
    /// <summary>
    /// Servicio para lanzar y gestionar el proceso de Godot
    /// </summary>
    public static class GodotLauncherService
    {
        private static Process? _godotProcess;


        private class WindowCandidate
        {
            public IntPtr Hwnd { get; }
            public string ClassName { get; }
            public string Title { get; }
            public long Area { get; }

            public WindowCandidate(IntPtr hwnd, string className, string title, long area)
            {
                Hwnd = hwnd;
                ClassName = className;
                Title = title;
                Area = area;
            }
        }

        public static void DeleteGodotCurrentUserJson()
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                DirectoryInfo? dir = new DirectoryInfo(baseDir);
                while (dir != null)
                {
                    string candidate = Path.Combine(dir.FullName, "WoldVirtual", "woldvirtual", "scene", "MTC", "users3D", "current_user.json");
                    if (File.Exists(candidate))
                    {
                        File.Delete(candidate);
                        Debug.WriteLine($"[ResetRegistration] Deleted Godot current_user.json at: {candidate}");
                        return;
                    }
                    candidate = Path.Combine(dir.FullName, "woldvirtual", "scene", "MTC", "users3D", "current_user.json");
                    if (File.Exists(candidate))
                    {
                        File.Delete(candidate);
                        Debug.WriteLine($"[ResetRegistration] Deleted Godot current_user.json at: {candidate}");
                        return;
                    }
                    dir = dir.Parent;
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[ResetRegistration] Error deleting Godot user JSON: {ex.Message}");
            }
        }

        public static async Task<(Process process, IntPtr godotHwnd)> LaunchGodotAsync(
            string projectDir, 
            string exePath, 
            string arguments, 
            Action<string> onOutputDataReceived,
            IntPtr wpfHwnd,
            Func<bool> isClosingPredicate)
        {
            Debug.WriteLine($"[GodotLauncher] Iniciando Godot...");
            Debug.WriteLine($"[GodotLauncher]  - Exe: {exePath}");
            Debug.WriteLine($"[GodotLauncher]  - Args: {arguments}");
            Debug.WriteLine($"[GodotLauncher]  - CWD: {projectDir}");

            var startInfo = new ProcessStartInfo
            {
                FileName = exePath,
                Arguments = arguments,
                WorkingDirectory = projectDir,
                UseShellExecute = false,
                CreateNoWindow = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            var process = new Process
            {
                StartInfo = startInfo,
                EnableRaisingEvents = true
            };

            process.OutputDataReceived += (s, ev) =>
            {
                if (!string.IsNullOrEmpty(ev.Data))
                {
                    Debug.WriteLine($"[GodotLauncher] stdout: {ev.Data}");
                    onOutputDataReceived(ev.Data);
                }
            };

            process.ErrorDataReceived += (s, ev) =>
            {
                if (!string.IsNullOrEmpty(ev.Data))
                {
                    Debug.WriteLine($"[GodotLauncher] stderr: {ev.Data}");
                }
            };

            process.Start();
            Debug.WriteLine($"[GodotLauncher] PID: {process.Id}");
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();

            IntPtr godotHwnd = await Task.Run(() => ScanForGodotWindow(process.Id, 15000, wpfHwnd, isClosingPredicate));

            return (process, godotHwnd);
        }

        private static IntPtr ScanForGodotWindow(int targetProcessId, int timeoutMs, IntPtr wpfHwnd, Func<bool> isClosingPredicate)
        {
            DateTime start = DateTime.Now;

            while ((DateTime.Now - start).TotalMilliseconds < timeoutMs && !isClosingPredicate())
            {
                var candidates = new List<WindowCandidate>();

                NativeMethods.EnumWindows((hwnd, lParam) =>
                {
                    if (hwnd == wpfHwnd) return true; // Ignorar la ventana principal de WPF

                    if (!NativeMethods.IsWindowVisible(hwnd)) return true;

                    NativeMethods.GetWindowThreadProcessId(hwnd, out uint processId);
                    if (processId != targetProcessId) return true; // No es el proceso de Godot, ignorar

                    StringBuilder classNameSb = new StringBuilder(256);
                    NativeMethods.GetClassName(hwnd, classNameSb, classNameSb.Capacity);
                    string cls = classNameSb.ToString();

                    StringBuilder titleSb = new StringBuilder(256);
                    NativeMethods.GetWindowText(hwnd, titleSb, titleSb.Capacity);
                    string title = titleSb.ToString();

                    NativeMethods.GetWindowRect(hwnd, out NativeMethods.RECT rect);
                    long width = rect.Right - rect.Left;
                    long height = rect.Bottom - rect.Top;
                    long area = width * height;

                    Debug.WriteLine($"[GodotLauncher] Ventana candidata encontrada: HWND={hwnd}, ClassName=\"{cls}\", Title=\"{title}\", Area={area}px ({width}x{height})");

                    candidates.Add(new WindowCandidate(hwnd, cls, title, area));

                    return true;
                }, IntPtr.Zero);

                if (candidates.Count > 0)
                {
                    // Priorizar: primero className esperado (Engine, Godot, SDL_app, GLFW), luego mayor área
                    WindowCandidate best = null;
                    foreach (var candidate in candidates)
                    {
                        bool isPreferredClass = candidate.ClassName is "Engine" or "Godot" || candidate.ClassName.StartsWith("SDL") || candidate.ClassName.StartsWith("GLFW");
                        if (best == null)
                        {
                            best = candidate;
                        }
                        else if (isPreferredClass && !candidates.Contains(best))
                        {
                            best = candidate;
                        }
                        else if (isPreferredClass == (best.ClassName is "Engine" or "Godot" || best.ClassName.StartsWith("SDL") || best.ClassName.StartsWith("GLFW")))
                        {
                            if (candidate.Area > best.Area)
                            {
                                best = candidate;
                            }
                        }
                        else if (isPreferredClass)
                        {
                            best = candidate;
                        }
                    }

                    if (best != null)
                    {
                        Debug.WriteLine($"[GodotLauncher] Ventana elegida para embebido: HWND={best.Hwnd}, ClassName=\"{best.ClassName}\", Title=\"{best.Title}\", Area={best.Area}px");
                        return best.Hwnd;
                    }
                }

                System.Threading.Thread.Sleep(250);
            }

            Debug.WriteLine($"[GodotLauncher] No se encontró ventana de Godot en el timeout de {timeoutMs}ms");
            return IntPtr.Zero;
        }
    }
}
