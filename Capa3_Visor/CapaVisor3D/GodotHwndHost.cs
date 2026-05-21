using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;

namespace VisorSingularity
{
    public class GodotHwndHost : HwndHost
    {
        private readonly IntPtr _childHwnd;
        private IntPtr _hostHwnd = IntPtr.Zero;

        public GodotHwndHost(IntPtr childHwnd)
        {
            _childHwnd = childHwnd;
        }

        protected override HandleRef BuildWindowCore(HandleRef hwndParent)
        {
            // Create a local child window container on the WPF UI thread using the standard "static" window class.
            // This avoids cross-thread and cross-process Win32 handle exceptions from WPF.
            _hostHwnd = CreateWindowEx(
                0,
                "static",
                "",
                WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN,
                0, 0,
                (int)Math.Max(1, this.ActualWidth), 
                (int)Math.Max(1, this.ActualHeight),
                hwndParent.Handle,
                IntPtr.Zero,
                IntPtr.Zero,
                IntPtr.Zero
            );

            if (_hostHwnd == IntPtr.Zero)
            {
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            }

            // Set parent of the Godot process window to our local container
            SetParent(_childHwnd, _hostHwnd);

            // Modify styles of the Godot window to make it a borderless child window
            int style = GetWindowLong(_childHwnd, GWL_STYLE);
            style = style & ~WS_CAPTION & ~WS_BORDER & ~WS_POPUP & ~WS_THICKFRAME;
            style = style | WS_CHILD;
            SetWindowLong(_childHwnd, GWL_STYLE, style);

            // Modify extended styles to remove borders
            int exStyle = GetWindowLong(_childHwnd, GWL_EXSTYLE);
            exStyle = exStyle & ~WS_EX_DLGMODALFRAME & ~WS_EX_CLIENTEDGE & ~WS_EX_STATICEDGE & ~WS_EX_WINDOWEDGE;
            SetWindowLong(_childHwnd, GWL_EXSTYLE, exStyle);

            // Update window styles and flush the frame cache to remove title bar and borders completely
            SetWindowPos(_childHwnd, IntPtr.Zero, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED);

            // Force showing the Godot child window inside the container
            ShowWindow(_childHwnd, SW_SHOW);

            // Force initial resize using system DPI
            ResizeToActualPixels();

            return new HandleRef(this, _hostHwnd);
        }

        protected override void DestroyWindowCore(HandleRef hwnd)
        {
            if (_hostHwnd != IntPtr.Zero)
            {
                DestroyWindow(_hostHwnd);
                _hostHwnd = IntPtr.Zero;
            }
        }

        public void ResizeToActualPixels()
        {
            if (_hostHwnd == IntPtr.Zero || _childHwnd == IntPtr.Zero) return;

            // Get the DPI scale factor
            var source = PresentationSource.FromVisual(this);
            double dpiX = 1.0;
            double dpiY = 1.0;
            if (source?.CompositionTarget != null)
            {
                var matrix = source.CompositionTarget.TransformToDevice;
                dpiX = matrix.M11;
                dpiY = matrix.M22;
            }

            // Convert DIP (Device Independent Pixels) to Physical Pixels
            int width = (int)Math.Max(1, this.ActualWidth * dpiX);
            int height = (int)Math.Max(1, this.ActualHeight * dpiY);

            // Resize the host window
            MoveWindow(_hostHwnd, 0, 0, width, height, true);

            // Resize the Godot child window to fit perfectly inside
            MoveWindow(_childHwnd, 0, 0, width, height, true);
        }

        protected override void OnRenderSizeChanged(SizeChangedInfo sizeInfo)
        {
            base.OnRenderSizeChanged(sizeInfo);
            ResizeToActualPixels();
        }

        // Win32 API Imports
        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode, EntryPoint = "CreateWindowExW")]
        private static extern IntPtr CreateWindowEx(
           int dwExStyle,
           string lpClassName,
           string lpWindowName,
           int dwStyle,
           int x, int y,
           int nWidth, int nHeight,
           IntPtr hWndParent,
           IntPtr hMenu,
           IntPtr hInstance,
           IntPtr lpParam);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool DestroyWindow(IntPtr hwnd);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr SetParent(IntPtr hWndChild, IntPtr hWndNewParent);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern int GetWindowLong(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

        private const int GWL_STYLE = -16;
        private const int GWL_EXSTYLE = -20;

        private const int WS_VISIBLE = 0x10000000;
        private const int WS_CHILD = 0x40000000;
        private const int WS_POPUP = unchecked((int)0x80000000);
        private const int WS_BORDER = 0x00800000;
        private const int WS_DLGFRAME = 0x00400000;
        private const int WS_CAPTION = WS_BORDER | WS_DLGFRAME;
        private const int WS_THICKFRAME = 0x00040000;
        private const int WS_CLIPCHILDREN = 0x02000000;

        private const int WS_EX_DLGMODALFRAME = 0x00000001;
        private const int WS_EX_WINDOWEDGE = 0x00000100;
        private const int WS_EX_CLIENTEDGE = 0x00000200;
        private const int WS_EX_STATICEDGE = 0x00020000;

        private const int SW_SHOW = 5;

        private const uint SWP_NOSIZE = 0x0001;
        private const uint SWP_NOMOVE = 0x0002;
        private const uint SWP_NOZORDER = 0x0004;
        private const uint SWP_NOACTIVATE = 0x0010;
        private const uint SWP_FRAMECHANGED = 0x0020;
    }
}
