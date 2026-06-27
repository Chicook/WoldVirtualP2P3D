using System;
using VisorSingularity.Services;

namespace VisorSingularity
{
    internal static class P2PNodeIdFactory
    {
        public static string Create(string username)
        {
            if (NodeIdentityManager.Current == null)
            {
                NodeIdentityManager.Initialize(username);
            }
            return NodeIdentityManager.Current?.NodeId ?? $"ND{Math.Abs(username.GetHashCode()) % 90000 + 10000}";
        }
    }
}
