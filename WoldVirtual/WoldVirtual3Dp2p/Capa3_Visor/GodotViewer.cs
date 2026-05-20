using System;
using System.Windows.Forms;
using System.Windows.Forms.Integration;
using System.Windows.Interop;

namespace VisorSingularity
{
    public class GodotViewer : HwndHost
    {
        private readonly GodotEmbedder _godotEmbedder;
        private readonly string _godotExecutablePath;
        private readonly string _godotProjectPath;
        private readonly string _godotArgs;

        private Panel _hostPanel; // Windows Forms Panel to host Godot

        public GodotViewer(GodotEmbedder godotEmbedder, string godotExecutablePath, string godotProjectPath, string godotArgs)
        {
            _godotEmbedder = godotEmbedder;
            _godotExecutablePath = godotExecutablePath;
            _godotProjectPath = godotProjectPath;
            _godotArgs = godotArgs;
        }

        protected override System.Runtime.InteropServices.HandleRef BuildWindowCore(System.Runtime.InteropServices.HandleRef hwndParent)
        {
            _hostPanel = new Panel
            {
                // Set initial size, will be resized by WPF layout
                Width = (int)ActualWidth,
                Height = (int)ActualHeight,
                BackColor = System.Drawing.Color.Black // Background for the panel
            };

            // Launch and embed Godot
            _ = _godotEmbedder.LaunchAndEmbed(_godotExecutablePath, _godotProjectPath, _hostPanel, _godotArgs);

            return new System.Runtime.InteropServices.HandleRef(this, _hostPanel.Handle);
        }

        protected override void DestroyWindowCore(System.Runtime.InteropServices.HandleRef hwnd)
        {
            _godotEmbedder.StopGodot();
            _hostPanel.Dispose();
        }

        protected override void OnRenderSizeChanged(System.Windows.SizeChangedInfo sizeInfo)
        {
            base.OnRenderSizeChanged(sizeInfo);
            if (_hostPanel != null && _godotEmbedder.IsGodotRunning)
            {
                _hostPanel.Width = (int)sizeInfo.NewSize.Width;
                _hostPanel.Height = (int)sizeInfo.NewSize.Height;
                _godotEmbedder.ResizeGodotWindow(_hostPanel.Width, _hostPanel.Height);
            }
        }
    }
}
