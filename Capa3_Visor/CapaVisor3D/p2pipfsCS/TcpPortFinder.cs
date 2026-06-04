using System.Net.Sockets;

namespace VisorSingularity
{
    internal static class TcpPortFinder
    {
        public static int FindAvailablePort(int start)
        {
            for (int port = start; port < start + 100; port++)
            {
                try
                {
                    using var client = new TcpClient();
                    var result = client.BeginConnect("127.0.0.1", port, null, null);
                    if (!result.AsyncWaitHandle.WaitOne(100))
                    {
                        return port;
                    }

                    client.EndConnect(result);
                }
                catch
                {
                    return port;
                }
            }

            return start;
        }
    }
}
