using System;
using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace VisorSingularity.p2pipfsCS
{
    public partial class P2PNodeControl : UserControl
    {
        public P2PNodeControl()
        {
            InitializeComponent();
            UpdateNodeStatus("Desconectado", 0);
        }

        public void UpdateNodeStatus(string status, int peerCount)
        {
            NodeStatus.Text = status;
            PeerCount.Text = peerCount.ToString();
            
            // Actualizar color según el estado
            switch (status.ToLower())
            {
                case "conectado":
                case "activo":
                    NodeStatus.Foreground = Brushes.LimeGreen;
                    break;
                case "conectando":
                case "inicializando":
                    NodeStatus.Foreground = Brushes.Yellow;
                    break;
                case "desconectado":
                case "inactivo":
                case "error":
                    NodeStatus.Foreground = Brushes.Red;
                    break;
                default:
                    NodeStatus.Foreground = Brushes.Gray;
                    break;
            }
        }

        public void UpdateNodeInfo(string nodeId, string simulatedUrl, bool isTunnelActive)
        {
            NodeIdText.Text = nodeId;
            NodeUrl.Text = simulatedUrl;
            
            if (isTunnelActive)
            {
                UpdateNodeStatus("Activo", 1);
            }
            else
            {
                UpdateNodeStatus("Inactivo", 0);
            }
        }

        public void UpdateNodeIdAndLink(string nodeId, string link)
        {
            NodeIdText.Text = nodeId;
            NodeUrl.Text = link;
        }

        public void UpdateGeneralStatus(string status, Brush color)
        {
            NodeStatus.Text = status;
            NodeStatus.Foreground = color;
        }

        public void UpdatePeerCount(int count)
        {
            PeerCount.Text = count.ToString();
        }

        public void UpdateNodeUrl(string url)
        {
            NodeUrl.Text = url;
        }

        public void UpdateNodeId(string nodeId)
        {
            NodeIdText.Text = nodeId;
        }
    }
}