using System;
using System.IO;

namespace VisorSingularity.Services
{
    internal sealed record GodotProjectPaths(string ProjectDir, string ExePath);

    internal static class GodotProjectLocator
    {
        private const string ProjectDirectoryName = "WoldVirtual";
        private const string ProjectFileName = "project.godot";
        private static readonly string GodotExecutableRelativePath =
            Path.Combine("servidorinterno", "Godot_v4.6.2-stable_mono_win64.exe");

        public static GodotProjectPaths Resolve()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            DirectoryInfo? dir = new DirectoryInfo(baseDir);

            while (dir != null)
            {
                string checkProject = Path.Combine(dir.FullName, ProjectDirectoryName);
                if (IsValidProject(checkProject, out string checkExe))
                {
                    return new GodotProjectPaths(checkProject, checkExe);
                }

                if (dir.Name == ProjectDirectoryName && IsValidProject(dir.FullName, out string currentExe))
                {
                    return new GodotProjectPaths(dir.FullName, currentExe);
                }

                dir = dir.Parent;
            }

            string defaultProject = Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "..", ProjectDirectoryName));
            string defaultExe = Path.Combine(defaultProject, GodotExecutableRelativePath);
            return new GodotProjectPaths(defaultProject, defaultExe);
        }

        private static bool IsValidProject(string projectDir, out string exePath)
        {
            exePath = Path.Combine(projectDir, GodotExecutableRelativePath);
            return Directory.Exists(projectDir)
                && File.Exists(Path.Combine(projectDir, ProjectFileName))
                && File.Exists(exePath);
        }
    }
}
