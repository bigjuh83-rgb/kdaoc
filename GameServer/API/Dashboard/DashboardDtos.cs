using System;
using System.Collections.Generic;

namespace DOL.GS.API.Dashboard
{
    public sealed record DashboardRealmStats(int RealmId, string RealmName, int Players);

    public sealed record DashboardClassSample(int RealmId, string RealmName, int ClassId, string ClassName);

    public sealed record DashboardClassStats(int RealmId, string RealmName, int ClassId, string ClassName, int Players);

    public sealed record DashboardClassHistoryStats(
        int RealmId,
        string RealmName,
        int ClassId,
        string ClassName,
        double AveragePlayers,
        int PeakPlayers);

    public sealed record DashboardPerformanceStats(
        float CpuPercent,
        long MemoryKb,
        double NetworkReceivedKbps = 0,
        double NetworkSentKbps = 0);

    public sealed record DashboardServiceCheck(
        string Name,
        string Status,
        string Detail,
        DateTime CheckedAt);

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
        long MemoryKb,
        double NetworkReceivedKbps = 0,
        double NetworkSentKbps = 0);

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

    public sealed record DashboardClassHistoryResponse(
        string Range,
        IReadOnlyList<DashboardClassHistoryStats> Classes,
        DateTime UpdatedAt);

    public sealed record DashboardHeraldRealmSummary(
        int RealmId,
        string RealmName,
        int OnlinePlayers,
        int CharacterCount,
        int Level50Characters,
        int Guilds,
        long RealmPoints);

    public sealed record DashboardHeraldCharacterRank(
        int Rank,
        string Name,
        int RealmId,
        string RealmName,
        int Level,
        int ClassId,
        string ClassName,
        long RealmPoints,
        long BountyPoints,
        int RealmLevel,
        string GuildName,
        DateTime LastPlayed,
        int TotalPlayerKills,
        int TotalDeathBlows,
        int TotalSoloKills,
        int PvpDeaths);

    public sealed record DashboardHeraldGuildRank(
        int Rank,
        string GuildName,
        int RealmId,
        string RealmName,
        long RealmPoints,
        long BountyPoints,
        long GuildLevel);

    public sealed record DashboardHeraldCharacterDetail(
        string Name,
        int RealmId,
        string RealmName,
        int Level,
        int ClassId,
        string ClassName,
        long RealmPoints,
        long BountyPoints,
        int RealmLevel,
        string RealmRank,
        string GuildName,
        DateTime LastPlayed,
        int TotalPlayerKills,
        int TotalDeathBlows,
        int TotalSoloKills,
        int PvpDeaths);

    public sealed record DashboardHeraldGuildMemberSummary(
        string Name,
        int RealmId,
        string RealmName,
        int Level,
        int ClassId,
        string ClassName,
        long RealmPoints,
        int RealmLevel,
        string RealmRank,
        DateTime LastPlayed);

    public sealed record DashboardHeraldGuildDetail(
        string GuildName,
        int RealmId,
        string RealmName,
        long RealmPoints,
        long BountyPoints,
        long GuildLevel,
        int MemberCount,
        int Level50Members,
        IReadOnlyList<DashboardHeraldGuildMemberSummary> TopMembers);

    public sealed record DashboardHeraldActivityItem(
        DateTime Bucket,
        string Label,
        int RealmId,
        string RealmName,
        long Value,
        string Metric);

    public sealed record DashboardHeraldRvrActivityItem(
        DateTime KilledAt,
        string KillerName,
        int KillerRealmId,
        string KillerRealmName,
        int KillerClassId,
        string KillerClassName,
        string KillerGuildName,
        string VictimName,
        int VictimRealmId,
        string VictimRealmName,
        int VictimClassId,
        string VictimClassName,
        string VictimGuildName,
        string RegionName,
        int RealmPoints,
        bool SoloKill);

    public sealed record DashboardHeraldKeepSample(int RealmId, bool IsTower, bool IsUnderSiege);

    public sealed record DashboardHeraldWarRealmSummary(
        int RealmId,
        string RealmName,
        int Keeps,
        int Towers,
        int Relics,
        int KeepsUnderSiege);

    public sealed record DashboardHeraldRelicStatus(
        string Name,
        string Type,
        int OriginalRealmId,
        string OriginalRealmName,
        int CurrentRealmId,
        string CurrentRealmName,
        bool IsCaptured);

    public sealed record DashboardHeraldWarState(
        int DarknessFallsOwnerRealmId,
        string DarknessFallsOwnerRealmName,
        IReadOnlyList<DashboardHeraldWarRealmSummary> RealmSummaries,
        IReadOnlyList<DashboardHeraldRelicStatus> Relics);

    public sealed record DashboardHeraldResponse(
        IReadOnlyList<DashboardRealmStats> Realms,
        IReadOnlyList<DashboardHeraldRealmSummary> RealmSummaries,
        DashboardHeraldWarState War,
        IReadOnlyList<DashboardHeraldCharacterRank> TopCharacters,
        IReadOnlyList<DashboardHeraldGuildRank> TopGuilds,
        IReadOnlyList<DashboardHeraldRvrActivityItem> RecentRvr,
        IReadOnlyList<DashboardHeraldActivityItem> RecentActivity,
        DateTime UpdatedAt);

    public sealed record DashboardOperatorStatusResponse(
        string OverallStatus,
        string Message,
        DashboardLiveResponse Live,
        int HistoryPoints24h,
        DateTime? LatestHistoryBucket,
        IReadOnlyList<DashboardServiceCheck> Checks,
        DateTime UpdatedAt);

    public sealed record DashboardStatusSummaryResponse(
        string Status,
        int TotalPlayers,
        int PeakPlayers24h,
        IReadOnlyList<DashboardRealmStats> Realms,
        DashboardPerformanceStats Performance,
        string Uptime,
        DateTime UpdatedAt,
        string BadgeUrl,
        string DashboardUrl);
}
