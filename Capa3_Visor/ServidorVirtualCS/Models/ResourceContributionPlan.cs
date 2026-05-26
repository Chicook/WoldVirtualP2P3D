namespace ServidorVirtualCS.Models;

public sealed class ResourceContributionPlan
{
    public const int MinimumTotalMb = 1024;

    public int CpuBudgetMb { get; init; }

    public int RamBudgetMb { get; init; }

    public int VramBudgetMb { get; init; }

    public int StorageBudgetMb { get; init; }

    public int BandwidthBudgetMb { get; init; }

    public int TotalBudgetMb => CpuBudgetMb + RamBudgetMb + VramBudgetMb + StorageBudgetMb + BandwidthBudgetMb;

    public bool MeetsMinimum => TotalBudgetMb >= MinimumTotalMb;

    public string Mode => MeetsMinimum ? "Equilibrado" : "Conservador";
}
