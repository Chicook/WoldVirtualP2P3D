using ServidorVirtualCS.Models;
using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace ServidorVirtualCS.Services;

public sealed class LocalIpfsPublisher
{
    private static readonly HttpClient HttpClient = new()
    {
        Timeout = TimeSpan.FromSeconds(15)
    };

    public async Task<bool> IsAvailableAsync(string apiBaseUrl, CancellationToken cancellationToken)
    {
        try
        {
            using HttpRequestMessage request = new(HttpMethod.Post, $"{apiBaseUrl.TrimEnd('/')}/api/v0/version");
            using HttpResponseMessage response = await HttpClient.SendAsync(request, cancellationToken);
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    public async Task<string?> PublishManifestAsync(
        NodeResourceSnapshot snapshot,
        ResourceContributionPlan plan,
        CancellationToken cancellationToken)
    {
        string manifestJson = JsonSerializer.Serialize(new
        {
            node = snapshot.MachineName,
            capturedAt = snapshot.CapturedAt,
            cpu = new
            {
                snapshot.CpuName,
                snapshot.LogicalCores,
                snapshot.CpuLoadPercent,
                reservedMb = plan.CpuBudgetMb
            },
            ram = new
            {
                snapshot.TotalRamMb,
                snapshot.AvailableRamMb,
                reservedMb = plan.RamBudgetMb
            },
            gpu = new
            {
                snapshot.GpuName,
                snapshot.DedicatedVramMb,
                reservedMb = plan.VramBudgetMb
            },
            storage = new
            {
                snapshot.TotalDiskMb,
                snapshot.AvailableDiskMb,
                reservedMb = plan.StorageBudgetMb
            },
            bandwidth = new
            {
                snapshot.NetworkBandwidthMbPerSecond,
                reservedMb = plan.BandwidthBudgetMb
            },
            aggregateBudgetMb = plan.TotalBudgetMb,
            meetsMinimum = plan.MeetsMinimum
        });

        using MultipartFormDataContent content = new();
        using ByteArrayContent fileContent = new(Encoding.UTF8.GetBytes(manifestJson));
        content.Add(fileContent, "file", "resource-manifest.json");

        using HttpRequestMessage request = new(
            HttpMethod.Post,
            $"{snapshot.IpfsApiUrl.TrimEnd('/')}/api/v0/add?pin=true&wrap-with-directory=false")
        {
            Content = content
        };

        try
        {
            using HttpResponseMessage response = await HttpClient.SendAsync(request, cancellationToken);
            response.EnsureSuccessStatusCode();
            string json = await response.Content.ReadAsStringAsync(cancellationToken);
            using JsonDocument document = JsonDocument.Parse(json);
            return document.RootElement.TryGetProperty("Hash", out JsonElement hash) ? hash.GetString() : null;
        }
        catch
        {
            return null;
        }
    }
}
