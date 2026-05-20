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

        public GodotHwndHost(IntPtr childHwnd)
        {
            _childHwnd = childHwnd;
        }

        protected override HandleRef BuildWindowCore(HandleRef hwndParent)
        {
            // Set parent window to the WPF host window
            SetParent(_childHwnd, hwndParent.Handle);

            // Modify styles to make it a child window without borders or popups
            int style = GetWindowLong(_childHwnd, GWL_STYLE);
            style = style & ~WS_CAPTION & ~WS_BORDER & ~WS_POPUP;
            style = style | WS_CHILD;
            SetWindowLong(_childHwnd, GWL_STYLE, style);

            // Force initial resize using system DPI
            ResizeToActualPixels();

            return new HandleRef(this, _childHwnd);
        }

        protected override void DestroyWindowCore(HandleRef hwnd)
        {
            // Destruction is managed by the Godot process life-cycle
        }

        public void ResizeToActualPixels()
        {
            if (_childHwnd == IntPtr.Zero) return;

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

            MoveWindow(_childHwnd, 0, 0, width, height, true);
        }

        protected override void OnRenderSizeChanged(SizeChangedInfo sizeInfo)
        {
            base.OnRenderSizeChanged(sizeInfo);
            ResizeToActualPixels();
        }

        // Win32 API Imports
        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr SetParent(IntPtr hWndChild, IntPtr hWndNewParent);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern int GetWindowLong(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);

        private const int GWL_STYLE = -16;
        private const int WS_CHILD = 0x40000000;
        private const int WS_POPUP = unchecked((int)0x80000000);
        private const int WS_BORDER = 0x00800000;
        private const int WS_DLGFRAME = 0x00400000;
        private const int WS_CAPTION = WS_BORDER | WS_DLGFRAME;
    }
}
