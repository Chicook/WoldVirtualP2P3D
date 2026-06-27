using System;

namespace VisorSingularity.Services
{
    public class NodeIdentity
    {
        public string NodeId { get; set; } = string.Empty;
        public string Username { get; set; } = string.Empty;
        public string PublicKeyBase64 { get; set; } = string.Empty;
        public string PrivateKeyBase64 { get; set; } = string.Empty;
    }
}
