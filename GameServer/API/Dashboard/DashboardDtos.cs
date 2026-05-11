using System;
using System.Collections.Generic;

namespace DOL.GS.API.Dashboard
{
    public sealed record DashboardRealmStats(int RealmId, string RealmName, int Players);

    public sealed record DashboardClassSample(int ClassId, string ClassName);

    public sealed record DashboardClassStats(int ClassId, string ClassName, int Players);

    public sealed record DashboardPerformanceStats(float CpuPercent, long MemoryKb);

    public sealed record DashboardLiveResponse(
        int TotalPlayers,
        IReadOnlyList<DashboardRealmStats> Realms,
        IReadOnlyList<DashboardClassStats> Classes,
        DashboardPerformanceStats Performance,
        string Uptime,
        DateTime StartedAt,
        DateTime UpdatedAt);

    public sealed record DashboardHistoryPoint(
        DateTime Bucket,
        int TotalPlayers,
        int AlbionPlayers,
        int MidgardPlayers,
        int HiberniaPlayers,
        float CpuPercent,
        long MemoryKb);

    public sealed record DashboardHistoryResponse(
        string Range,
        IReadOnlyList<DashboardHistoryPoint> Points,
        DateTime UpdatedAt);

    public sealed record DashboardRealmActivityPoint(
        DateTime Bucket,
        long AlbionGold,
        long MidgardGold,
        long HiberniaGold,
        long AlbionRealmPoints,
        long MidgardRealmPoints,
        long HiberniaRealmPoints);

    public sealed record DashboardRealmActivityResponse(
        string Range,
        IReadOnlyList<DashboardRealmActivityPoint> Points,
        DateTime UpdatedAt);
}
