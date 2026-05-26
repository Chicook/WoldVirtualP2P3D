using ServidorVirtualCS.Models;
using System;
using System.Collections.Generic;

namespace ServidorVirtualCS.Services;

public sealed class ResourceContributionPlanner
{
    public ResourceContributionPlan CreatePlan(NodeResourceSnapshot snapshot, double boostMultiplier = 1.0d)
    {
        boostMultiplier = Math.Clamp(boostMultiplier, 1.0d, 1.8d);

        int cpuBudget = Math.Min((int)Math.Round(snapshot.LogicalCores * Math.Max(0.25, (100d - snapshot.CpuLoadPercent) / 100d) * 48d), 192);
        int ramBudget = Math.Min((int)(snapshot.AvailableRamMb * 0.12), 384);
        int vramBudget = Math.Min((int)(snapshot.DedicatedVramMb * 0.10), 160);
        int storageBudget = Math.Min((int)(snapshot.AvailableDiskMb * 0.0035), 384);
        int bandwidthBudget = Math.Min((int)Math.Round(snapshot.NetworkBandwidthMbPerSecond * 4), 128);

        cpuBudget = Math.Max(cpuBudget, 64);
        ramBudget = Math.Max(ramBudget, 192);
        vramBudget = Math.Max(vramBudget, snapshot.DedicatedVramMb > 0 ? 64 : 0);
        storageBudget = Math.Max(storageBudget, 256);
        bandwidthBudget = Math.Max(bandwidthBudget, snapshot.NetworkBandwidthMbPerSecond > 0 ? 64 : 32);

        List<ResourceBucket> buckets =
        [
            new("cpu", cpuBudget, Math.Min(Math.Max(cpuBudget * 2, 192), 256)),
            new("ram", ramBudget, Math.Min(Math.Max(ramBudget * 2, 384), 512)),
            new("vram", vramBudget, Math.Min(Math.Max(vramBudget * 2, 128), 256)),
            new("storage", storageBudget, Math.Min(Math.Max(storageBudget * 2, 384), 768)),
            new("bandwidth", bandwidthBudget, Math.Min(Math.Max(bandwidthBudget * 2, 96), 192))
        ];

        foreach (ResourceBucket bucket in buckets)
        {
            bucket.Value = Math.Min(bucket.MaxValue, (int)Math.Round(bucket.Value * boostMultiplier));
        }

        int total = 0;
        foreach (ResourceBucket bucket in buckets)
        {
            total += bucket.Value;
        }

        int missing = Math.Max(0, ResourceContributionPlan.MinimumTotalMb - total);
        while (missing > 0)
        {
            bool changed = false;
            foreach (ResourceBucket bucket in buckets)
            {
                if (bucket.Value >= bucket.MaxValue)
                {
                    continue;
                }

                int step = Math.Min(32, Math.Min(bucket.MaxValue - bucket.Value, missing));
                bucket.Value += step;
                missing -= step;
                changed = true;

                if (missing <= 0)
                {
                    break;
                }
            }

            if (!changed)
            {
                break;
            }
        }

        return new ResourceContributionPlan
        {
            CpuBudgetMb = buckets[0].Value,
            RamBudgetMb = buckets[1].Value,
            VramBudgetMb = buckets[2].Value,
            StorageBudgetMb = buckets[3].Value,
            BandwidthBudgetMb = buckets[4].Value
        };
    }

    private sealed class ResourceBucket(string name, int value, int maxValue)
    {
        public string Name { get; } = name;

        public int Value { get; set; } = value;

        public int MaxValue { get; } = maxValue;
    }
}
