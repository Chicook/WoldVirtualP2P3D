using System;
using VisorSingularity.Identity;

namespace VisorSingularity
{
    internal static class P2PNodeIdFactory
    {
        public static string Create(string username)
        {
            using var identity = NodeIdentity.LoadOrCreate();
            return identity.NodeId;
        }
    }
}
