using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;

namespace VisorSingularity.Services
{
    public class GodotLauncherService
    {
        [DllImport("user32.dll")]
        private static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);
        private delegate bool EnumWindowsProc(IntPtr hwnd, IntPtr lParam);

        [DllImport("user32.dll")]
        private static extern bool IsWindowVisible(IntPtr hwnd);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);

        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode, EntryPoint = "GetClassNameW")]
        private static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);

        [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

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
                    onOutputDataReceived(ev.Data);
                }
            };

            process.Start();
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();

            IntPtr godotHwnd = await Task.Run(() => ScanForGodotWindow(process.Id, 15000, wpfHwnd, isClosingPredicate));

            return (process, godotHwnd);
        }

        private static IntPtr ScanForGodotWindow(int targetProcessId, int timeoutMs, IntPtr wpfHwnd, Func<bool> isClosingPredicate)
        {
            IntPtr result = IntPtr.Zero;
            DateTime start = DateTime.Now;

            while (result == IntPtr.Zero && (DateTime.Now - start).TotalMilliseconds < timeoutMs && !isClosingPredicate())
            {
                EnumWindows((hwnd, lParam) =>
                {
                    if (hwnd == wpfHwnd) return true; // Ignorar la ventana principal de WPF

                    if (!IsWindowVisible(hwnd)) return true;

                    GetWindowThreadProcessId(hwnd, out uint processId);
                    if (processId != targetProcessId) return true; // No es el proceso de Godot, ignorar

                    StringBuilder className = new StringBuilder(256);
                    GetClassName(hwnd, className, className.Capacity);
                    string cls = className.ToString();

                    StringBuilder sb = new StringBuilder(256);
                    GetWindowText(hwnd, sb, sb.Capacity);
                    string title = sb.ToString();

                    // Descartar ventanas de consola o selectores de depuración, buscando la ventana principal de renderizado (Engine)
                    if (cls == "Engine" || (!title.Contains("Console") && !title.Contains("Select")))
                    {
                        result = hwnd;
                        return false; 
                    }

                    return true;
                }, IntPtr.Zero);

                if (result != IntPtr.Zero) break;
                System.Threading.Thread.Sleep(250);
            }

            return result;
        }
    }
}
