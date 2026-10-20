namespace Visor3D.Update
{
    public class ReleaseInfo
    {
        public string TagName { get; set; } = "";
        public string Version { get; set; } = "";
        public string? AssetUrl { get; set; }
        public string? AssetName { get; set; }
        public long AssetSize { get; set; }
        public bool Prerelease { get; set; }
    }
}
