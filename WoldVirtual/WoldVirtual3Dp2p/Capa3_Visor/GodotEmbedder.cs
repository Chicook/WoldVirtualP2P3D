using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms; // For Control.Handle

namespace VisorSingularity
{
    public class GodotEmbedder
    {
        // Win32 API declarations for window manipulation
        [DllImport("user32.dll")]
        private static extern IntPtr SetParent(IntPtr hWndChild, IntPtr hWndNewParent);

        [DllImport("user32.dll")]
        private static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

        [DllImport("user32.dll")]
        private static extern int GetWindowLong(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll")]
        private static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);

        [DllImport("user32.dll")]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        // Window styles
        private const int GWL_STYLE = -16;
        private const int WS_CHILD = 0x40000000; // Child window
        private const int WS_POPUP = 0x80000000; // Pop-up window
        private const int WS_BORDER = 0x00800000; // Window with border
        private const int WS_DLGFRAME = 0x00400000; // Window with double border
        private const int WS_CAPTION = WS_BORDER | WS_DLGFRAME; // Window with a title bar

        // ShowWindow commands
        private const int SW_SHOW = 5;
        private const int SW_HIDE = 0;

        private Process? _godotProcess;
        private IntPtr _godotWindowHandle = IntPtr.Zero;
        private Control? _parentControl; // The Windows Forms control that will host Godot

        public bool IsGodotRunning => _godotProcess != null && !_godotProcess.HasExited;
        public IntPtr GodotWindowHandle => _godotWindowHandle;

        public GodotEmbedder()
        {
            // Constructor
        }

        public async Task LaunchAndEmbed(string godotExecutablePath, string godotProjectPath, Control parentControl, string args = "")
        {
            if (IsGodotRunning)
            {
                StopGodot();
            }

            _parentControl = parentControl;

            // Construct Godot arguments
            // --path: Specifies the project path
            // --resolution: Sets the window resolution (optional, can be handled by embedding)
            // --disable-vsync: Often good for embedded applications
            // --no-window: Godot 4.x doesn't have a --no-window flag, we rely on embedding
            // --fixed-fps 60: Optional, to control frame rate
            // --editor: If you want to embed the editor (unlikely for a viewer)
            // --display-driver: Optional, e.g., "opengl3" or "vulkan"
            // --gpu-index: Optional, if multiple GPUs
            // --position X Y: Optional, to set initial window position

            // For embedding, Godot needs to run in a window, then we set its parent.
            // We might need to pass a specific display driver if issues arise.
            string fullArgs = $"--path \"{godotProjectPath}\" --resolution {parentControl.Width}x{parentControl.Height} {args}";

            LogDebug($"Launching Godot with: {godotExecutablePath} {fullArgs}");

            _godotProcess = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = godotExecutablePath,
                    Arguments = fullArgs,
                    UseShellExecute = false,
                    RedirectStandardOutput = false, // Godot might print a lot, redirect if needed for debugging
                    RedirectStandardError = false,
                    CreateNoWindow = false // Godot needs a window to be embedded
                },
                EnableRaisingEvents = true
            };

            _godotProcess.Exited += (sender, e) =>
            {
                LogDebug("Godot process exited.");
                _godotWindowHandle = IntPtr.Zero;
                _godotProcess?.Dispose();
                _godotProcess = null;
            };

            _godotProcess.Start();
            LogDebug($"Godot process started with ID: {_godotProcess.Id}");

            // Wait for Godot window to appear
            _godotWindowHandle = await FindGodotWindow(_godotProcess, 5000); // 5 seconds timeout
            if (_godotWindowHandle == IntPtr.Zero)
            {
                LogDebug("Failed to find Godot window handle.");
                StopGodot();
                throw new InvalidOperationException("Could not find Godot window.");
            }

            LogDebug($"Found Godot window handle: {_godotWindowHandle}");

            // Set Godot window as a child of the parent control
            SetParent(_godotWindowHandle, parentControl.Handle);

            // Remove window styles (border, title bar)
            int style = GetWindowLong(_godotWindowHandle, GWL_STYLE);
            style = style & ~WS_CAPTION & ~WS_BORDER & ~WS_POPUP; // Remove caption, border, popup style
            style = style | WS_CHILD; // Add child style
            SetWindowLong(_godotWindowHandle, GWL_STYLE, style);

            // Resize and show Godot window
            ResizeGodotWindow(parentControl.Width, parentControl.Height);
            ShowWindow(_godotWindowHandle, SW_SHOW);

            LogDebug("Godot embedded successfully.");
        }

        public void ResizeGodotWindow(int width, int height)
        {
            if (_godotWindowHandle != IntPtr.Zero)
            {
                MoveWindow(_godotWindowHandle, 0, 0, width, height, true);
            }
        }

        public void StopGodot()
        {
            if (IsGodotRunning)
            {
                LogDebug("Stopping Godot process.");
                _godotProcess?.Kill();
                _godotProcess?.WaitForExit();
                _godotProcess?.Dispose();
                _godotProcess = null;
                _godotWindowHandle = IntPtr.Zero;
            }
        }

        private async Task<IntPtr> FindGodotWindow(Process process, int timeoutMs)
        {
            IntPtr hWnd = IntPtr.Zero;
            DateTime startTime = DateTime.Now;

            while ((DateTime.Now - startTime).TotalMilliseconds < timeoutMs && hWnd == IntPtr.Zero)
            {
                // Enumerate all top-level windows
                EnumWindows((currentHwnd, lParam) =>
                {
                    uint processId;
                    GetWindowThreadProcessId(currentHwnd, out processId);

                    if (processId == process.Id)
                    {
                        // Check if it's a main window (Godot usually creates one main window)
                        // You might need more robust checks here if Godot creates multiple windows
                        StringBuilder sb = new StringBuilder(256);
                        GetWindowText(currentHwnd, sb, sb.Capacity);
                        string windowTitle = sb.ToString();

                        // Godot's default window title is often the project name or empty initially.
                        // We can refine this check if needed.
                        if (!string.IsNullOrEmpty(windowTitle) || GetWindowLong(currentHwnd, GWL_STYLE) != 0)
                        {
                            hWnd = currentHwnd;
                            return false; // Stop enumeration
                        }
                    }
                    return true; // Continue enumeration
                }, IntPtr.Zero);

                if (hWnd == IntPtr.Zero)
                {
                    await Task.Delay(100); // Wait a bit before trying again
                }
            }
            return hWnd;
        }

        private void LogDebug(string message)
        {
            // Use the MainWindow's LogDebug or a dedicated logger
            // For now, a simple console log or file log
            try
            {
                string logPath = System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "godot_embedder_debug.log");
                System.IO.File.AppendAllText(logPath, $"[{DateTime.Now:HH:mm:ss.fff}] GodotEmbedder: {message}\r\n");
            }
            catch { }
        }
    }
}