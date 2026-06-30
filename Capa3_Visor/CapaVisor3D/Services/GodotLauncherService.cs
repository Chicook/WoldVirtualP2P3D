using System.Diagnostics;
using System.IO;

namespace VisorSingularity.Services
{
    public static class GodotLauncherService
    {
        public static void DeleteGodotCurrentUserJson()
        {
            try
            {
                var baseDir = AppDomain.CurrentDomain.BaseDirectory;
                var dir = new DirectoryInfo(baseDir);
                while (dir != null)
                {
                    var candidate = Path.Combine(dir.FullName, "WoldVirtual", "woldvirtual", "scene", "MTC", "users3D", "current_user.json");
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

            var godotHwnd = await Task.Run(() => ScanForGodotWindow(process.Id, 15000, wpfHwnd, isClosingPredicate)).ConfigureAwait(false);

            return (process, godotHwnd);
        }

        private static IntPtr ScanForGodotWindow(int targetProcessId, int timeoutMs, IntPtr wpfHwnd, Func<bool> isClosingPredicate)
        {
            var start = DateTime.Now;

            while ((DateTime.Now - start).TotalMilliseconds < timeoutMs && !isClosingPredicate())
            {
                var candidates = Win32WindowScanner.GetProcessTopLevelWindowCandidates((uint)targetProcessId, wpfHwnd);

                if (candidates.Count > 0)
                {
                    // Priorizar: primero className esperado (Engine, Godot, SDL_app, GLFW), luego mayor área
                    Win32WindowScanner.WindowCandidate? best = null;
                    var bestIsPreferredClass = false;

                    foreach (var candidate in candidates)
                    {
                        var isPreferredClass = Win32WindowScanner.IsPreferredGodotClassName(candidate.ClassName);
                        Debug.WriteLine($"[GodotLauncher] Ventana candidata encontrada: HWND={candidate.Hwnd}, ClassName=\"{candidate.ClassName}\", Title=\"{candidate.Title}\", Area={candidate.Area}px");

                        if (best is null)
                        {
                            best = candidate;
                            bestIsPreferredClass = isPreferredClass;
                        }
                        else if (isPreferredClass && !bestIsPreferredClass)
                        {
                            best = candidate;
                            bestIsPreferredClass = true;
                        }
                        else if (isPreferredClass == bestIsPreferredClass && candidate.Area > best.Value.Area)
                        {
                            best = candidate;
                        }
                    }

                    if (best is not null)
                    {
                        Debug.WriteLine($"[GodotLauncher] Ventana elegida para embebido: HWND={best.Value.Hwnd}, ClassName=\"{best.Value.ClassName}\", Title=\"{best.Value.Title}\", Area={best.Value.Area}px");
                        return best.Value.Hwnd;
                    }
                }

                Thread.Sleep(250);
            }

            Debug.WriteLine($"[GodotLauncher] No se encontró ventana de Godot en el timeout de {timeoutMs}ms");
            return IntPtr.Zero;
        }
    }
}
