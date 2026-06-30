using System.Runtime.InteropServices;

namespace VisorSingularity.Services
{
    internal static class Win32WindowScanner
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;
        }

        internal readonly record struct WindowCandidate(nint Hwnd, string ClassName, string Title, long Area);

        internal static bool IsPreferredGodotClassName(string className) =>
            className is "Engine" or "Godot"
            || className.StartsWith("SDL", StringComparison.Ordinal)
            || className.StartsWith("GLFW", StringComparison.Ordinal);

        internal static List<WindowCandidate> GetProcessTopLevelWindowCandidates(uint targetProcessId, nint excludedHwnd)
        {
            var candidates = new List<WindowCandidate>();

            bool Callback(nint hwnd, nint _)
            {
                if (hwnd == excludedHwnd)
                {
                    return true;
                }

                if (!User32.IsWindowVisible(hwnd))
                {
                    return true;
                }

                var threadId = User32.GetWindowThreadProcessId(hwnd, out var processId);
                if (threadId == 0 || processId != targetProcessId)
                {
                    return true;
                }

                if (!TryGetClassName(hwnd, out var className))
                {
                    return true;
                }

                var title = GetWindowTitle(hwnd);

                if (!User32.GetWindowRect(hwnd, out var rect))
                {
                    return true;
                }

                var width = rect.Right - rect.Left;
                var height = rect.Bottom - rect.Top;
                var area = width * height;

                candidates.Add(new WindowCandidate(hwnd, className, title, area));
                return true;
            }

            User32.EnumWindows(Callback, 0);
            return candidates;
        }

        private static bool TryGetClassName(nint hwnd, out string className)
        {
            var buffer = new char[256];
            var length = User32.GetClassName(hwnd, buffer, buffer.Length);
            if (length <= 0)
            {
                className = string.Empty;
                return false;
            }

            className = new string(buffer, 0, length);
            return true;
        }

        private static string GetWindowTitle(nint hwnd)
        {
            var buffer = new char[256];
            var length = User32.GetWindowText(hwnd, buffer, buffer.Length);
            return length <= 0 ? string.Empty : new string(buffer, 0, length);
        }

        private static class User32
        {
            internal delegate bool EnumWindowsProc(nint hwnd, nint lParam);

            [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
            [DllImport("user32.dll", SetLastError = true)]
            [return: MarshalAs(UnmanagedType.Bool)]
            internal static extern bool EnumWindows(EnumWindowsProc enumProc, nint lParam);

            [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
            [DllImport("user32.dll", SetLastError = true)]
            [return: MarshalAs(UnmanagedType.Bool)]
            internal static extern bool IsWindowVisible(nint hWnd);

            [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
            [DllImport("user32.dll", SetLastError = true)]
            internal static extern uint GetWindowThreadProcessId(nint hWnd, out uint processId);

            [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
            [DllImport("user32.dll", EntryPoint = "GetClassNameW", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
            internal static extern int GetClassName(nint hWnd, [Out] char[] lpClassName, int nMaxCount);

            [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
            [DllImport("user32.dll", EntryPoint = "GetWindowTextW", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
            internal static extern int GetWindowText(nint hWnd, [Out] char[] lpString, int nMaxCount);

            [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
            [DllImport("user32.dll", SetLastError = true)]
            [return: MarshalAs(UnmanagedType.Bool)]
            internal static extern bool GetWindowRect(nint hWnd, out RECT lpRect);
        }
    }
}
