using System;
using System.Windows.Forms;
using System.Windows.Forms.Integration;

namespace VisorSingularity
{
    public class GodotViewer : UserControl
    {
        private readonly GodotEmbedder _godotEmbedder;
        private readonly string _godotExecutablePath;
        private readonly string _godotProjectPath;
        private readonly string _godotArgs;

        public GodotViewer(GodotEmbedder godotEmbedder, string godotExecutablePath, string godotProjectPath, string godotArgs)
        {
            _godotEmbedder = godotEmbedder;
            _godotExecutablePath = godotExecutablePath;
            _godotProjectPath = godotProjectPath;
            _godotArgs = godotArgs;
            
            // Set up the control
            BackColor = System.Drawing.Color.Black;
            Dock = DockStyle.Fill;
        }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            
            // Launch and embed Godot when the control is created
            if (!DesignMode)
            {
                _ = _godotEmbedder.LaunchAndEmbed(_godotExecutablePath, _godotProjectPath, this, _godotArgs);
            }
        }

        protected override void OnResize(EventArgs e)
        {
            base.OnResize(e);
            
            // Resize Godot window when control is resized
            if (_godotEmbedder.IsGodotRunning)
            {
                _godotEmbedder.ResizeGodotWindow(Width, Height);
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                _godotEmbedder.StopGodot();
            }
            base.Dispose(disposing);
        }
    }
}
