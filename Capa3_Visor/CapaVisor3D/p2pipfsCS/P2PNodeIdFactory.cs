using System;

namespace VisorSingularity
{
    internal static class P2PNodeIdFactory
    {
        public static string Create(string username)
        {
            int seed = Math.Abs((username + DateTime.Now.Ticks).GetHashCode()) % 90000 + 10000;
            return $"ND{seed}";
        }
    }
}
