# Dashboard Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an Eden-style public KDAOC stats dashboard inside the existing Atlas API host, with live population, history charts, server-issued gold/RP realm trends, and a Naver Cafe-friendly live badge image.

**Architecture:** Keep dashboard DTOs, aggregation, HTTP routes, static assets, and reward tracking separated. Existing game code records only trusted server-issued gold/RP into an aggregate table, while the public API exposes only privacy-safe totals.

**Tech Stack:** .NET 10, ASP.NET Core minimal APIs, existing `GameServer.Database`, `serverstats`, local HTML/CSS/vanilla JS canvas charts, SkiaSharp PNG rendering for Linux-safe badge output, NUnit tests.

---

## File Structure

Create:

- `GameServer/API/Dashboard/DashboardDtos.cs`
  - Public response contracts and small input sample records used by tests.
- `GameServer/API/Dashboard/DashboardAggregation.cs`
  - Pure functions for realm/class aggregation, history normalization, activity bucket keys, and activity chart series.
- `GameServer/API/Dashboard/DashboardStatsProvider.cs`
  - Reads current live state, `serverstats`, and dashboard activity rows from the running server/database.
- `GameServer/API/Dashboard/DashboardPerformanceSampler.cs`
  - Wraps current process CPU and managed memory sampling.
- `GameServer/API/Dashboard/DashboardRoutes.cs`
  - Adds `/dashboard`, `/api/dashboard/live`, `/api/dashboard/history`, `/api/dashboard/realm-activity`, and `/status/badge.png`.
- `GameServer/API/Dashboard/DashboardBadgeRenderer.cs`
  - Renders a PNG badge for Naver Cafe.
- `GameServer/API/dashboard/index.html`
  - Public dashboard shell.
- `GameServer/API/dashboard/dashboard.css`
  - Dashboard styling.
- `GameServer/API/dashboard/dashboard.js`
  - Fetches JSON endpoints and draws local canvas charts.
- `CoreDatabase/Tables/DbDashboardRealmActivity.cs`
  - Aggregate table for hourly realm gold/RP inflow.
- `GameServer/gameutils/DashboardRealmActivityTracker.cs`
  - Runtime tracker used by server reward paths.
- `Tests/UnitTests/UT_DashboardAggregation.cs`
  - Pure aggregation, history, privacy, and bucket tests.
- `Tests/UnitTests/UT_DashboardRealmActivityTracker.cs`
  - Tracker policy and fake sink tests.
- `Tests/UnitTests/UT_DashboardBadgeRenderer.cs`
  - PNG renderer smoke test.

Modify:

- `GameServer/API/ApiHost.cs`
  - Call `api.MapDashboardRoutes(contentRoot);`.
- `GameServer/GameServer.csproj`
  - Add SkiaSharp package references and copy dashboard static assets to `wwwroot/dashboard`.
- `GameServer/gameobjects/GamePlayer.cs`
  - Add `AddServerIssuedMoney(...)` overloads and optional RP dashboard tracking suppression.
  - Count direct ground-money pickup as server-issued gold after guild dues.
- `GameServer/gameutils/Group.cs`
  - Count group ground-money split as server-issued gold after guild dues.
- `GameServer/gameobjects/GameMerchant.cs`
  - Count NPC merchant sell payout as server-issued gold.
- `GameServer/keeps/Gameobjects/Guards/GameGuardMerchant.cs`
  - Count guard merchant sell payout as server-issued gold.
- `GameServer/quests/Tasks/AbstractTask.cs`
  - Count task reward money as server-issued gold.
- `GameServer/quests/Missions/AbstractMission.cs`
  - Count mission reward money as server-issued gold.
- `GameServer/quests/QuestsMgr/DataQuest.cs`
  - Count data quest money rewards as server-issued gold.
- `GameServer/quests/QuestsMgr/RewardQuest.cs`
  - Count reward quest money as server-issued gold.
- `GameServer/serverrules/AbstractServerRules.cs`
  - Count server-rule reward money as server-issued gold.
- `GameServer/behaviour/Actions/GiveGoldAction.cs`
  - Count behavior-script gold awards as server-issued gold.
- `GameServer/scripts/quests/**/*.cs`
  - Count direct quest-script money awards as server-issued gold.
- `GameServer/commands/gmcommands/Player.cs`
  - Suppress dashboard RP tracking for manual GM RP grants; leave manual GM money grants untracked.
- `docs/local-mariadb-dotnet-runbook.md`
  - Add dashboard and stats-save production settings.

Do not modify for gold tracking:

- `GameServer/gameutils/PlayerTradeWindow.cs`
- `GameServer/gameutils/ConsignmentState.cs`
- `GameServer/gameutils/Guild.cs`
- `GameServer/commands/gmcommands/Player.cs` money cases

Those paths are transfers or manual grants, not new server-issued economy inflow.

---

### Task 1: Dashboard DTOs And Pure Aggregation

**Files:**

- Create: `GameServer/API/Dashboard/DashboardDtos.cs`
- Create: `GameServer/API/Dashboard/DashboardAggregation.cs`
- Test: `Tests/UnitTests/UT_DashboardAggregation.cs`

- [ ] **Step 1: Write failing aggregation tests**

Add `Tests/UnitTests/UT_DashboardAggregation.cs`:

```csharp
using System;
using System.Collections.Generic;
using DOL.Database;
using DOL.GS.API.Dashboard;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DashboardAggregation
    {
        [Test]
        public void BuildClassStats_GroupsValidClassesAndSkipsInvalidSamples()
        {
            var samples = new[]
            {
                new DashboardClassSample(1, "Armsman"),
                new DashboardClassSample(1, "Armsman"),
                new DashboardClassSample(2, "Cabalist"),
                new DashboardClassSample(0, ""),
                new DashboardClassSample(-1, "Broken")
            };

            IReadOnlyList<DashboardClassStats> result = DashboardAggregation.BuildClassStats(samples);

            Assert.That(result, Has.Count.EqualTo(2));
            Assert.That(result[0].ClassId, Is.EqualTo(1));
            Assert.That(result[0].ClassName, Is.EqualTo("Armsman"));
            Assert.That(result[0].Players, Is.EqualTo(2));
            Assert.That(result[1].ClassId, Is.EqualTo(2));
            Assert.That(result[1].Players, Is.EqualTo(1));
        }

        [Test]
        public void NormalizeHistory_ReturnsChronologicalRowsInsideRange()
        {
            DateTime now = new(2026, 5, 11, 12, 0, 0, DateTimeKind.Utc);
            var rows = new[]
            {
                new DbServerStat { StatDate = now.AddHours(-1), Clients = 4, CPU = 12.5f, Memory = 1024, AlbionPlayers = 1, MidgardPlayers = 2, HiberniaPlayers = 1 },
                new DbServerStat { StatDate = now.AddHours(-25), Clients = 99, CPU = 99, Memory = 99 },
                new DbServerStat { StatDate = now.AddHours(-2), Clients = 3, CPU = 8.5f, Memory = 900, AlbionPlayers = 1, MidgardPlayers = 1, HiberniaPlayers = 1 }
            };

            IReadOnlyList<DashboardHistoryPoint> result = DashboardAggregation.NormalizeHistory(rows, now, TimeSpan.FromHours(24));

            Assert.That(result, Has.Count.EqualTo(2));
            Assert.That(result[0].TotalPlayers, Is.EqualTo(3));
            Assert.That(result[1].TotalPlayers, Is.EqualTo(4));
            Assert.That(result[0].Bucket <= result[1].Bucket, Is.True);
        }

        [Test]
        public void BuildRealmActivitySeries_FillsMissingHourlyBucketsWithZeroes()
        {
            DateTime now = new(2026, 5, 11, 12, 35, 0, DateTimeKind.Utc);
            DateTime bucket = new(2026, 5, 11, 11, 0, 0, DateTimeKind.Utc);
            var rows = new[]
            {
                new DbDashboardRealmActivity
                {
                    BucketRealmKey = DashboardAggregation.BuildActivityKey(bucket, eRealm.Albion),
                    BucketStart = bucket,
                    Realm = (int)eRealm.Albion,
                    ServerIssuedGold = 500,
                    ServerIssuedRealmPoints = 42
                }
            };

            IReadOnlyList<DashboardRealmActivityPoint> result = DashboardAggregation.BuildRealmActivitySeries(rows, now, TimeSpan.FromHours(3));

            Assert.That(result, Has.Count.EqualTo(4));
            Assert.That(result[^2].AlbionGold, Is.EqualTo(500));
            Assert.That(result[^2].AlbionRealmPoints, Is.EqualTo(42));
            Assert.That(result[^2].MidgardGold, Is.EqualTo(0));
            Assert.That(result[^1].Bucket, Is.EqualTo(DashboardAggregation.GetHourBucket(now)));
        }
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
dotnet test Tests/Tests.csproj --no-restore --filter "UT_DashboardAggregation"
```

Expected: build fails because `DashboardAggregation`, `DashboardClassSample`, `DashboardClassStats`, `DashboardHistoryPoint`, `DbDashboardRealmActivity`, and `DashboardRealmActivityPoint` do not exist.

- [ ] **Step 3: Add DTOs**

Create `GameServer/API/Dashboard/DashboardDtos.cs`:

```csharp
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
```

- [ ] **Step 4: Add activity database row**

Create `CoreDatabase/Tables/DbDashboardRealmActivity.cs`:

```csharp
using System;
using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "dashboard_realm_activity")]
    public class DbDashboardRealmActivity : DataObject
    {
        private string m_bucketRealmKey = string.Empty;
        private DateTime m_bucketStart;
        private int m_realm;
        private long m_serverIssuedGold;
        private long m_serverIssuedRealmPoints;

        [PrimaryKey]
        public string BucketRealmKey
        {
            get => m_bucketRealmKey;
            set { m_bucketRealmKey = value; Dirty = true; }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime BucketStart
        {
            get => m_bucketStart;
            set { m_bucketStart = value; Dirty = true; }
        }

        [DataElement(AllowDbNull = false)]
        public int Realm
        {
            get => m_realm;
            set { m_realm = value; Dirty = true; }
        }

        [DataElement(AllowDbNull = false)]
        public long ServerIssuedGold
        {
            get => m_serverIssuedGold;
            set { m_serverIssuedGold = value; Dirty = true; }
        }

        [DataElement(AllowDbNull = false)]
        public long ServerIssuedRealmPoints
        {
            get => m_serverIssuedRealmPoints;
            set { m_serverIssuedRealmPoints = value; Dirty = true; }
        }
    }
}
```

- [ ] **Step 5: Add pure aggregation**

Create `GameServer/API/Dashboard/DashboardAggregation.cs`:

```csharp
using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;

namespace DOL.GS.API.Dashboard
{
    public static class DashboardAggregation
    {
        public static IReadOnlyList<DashboardRealmStats> BuildRealmStats(int albion, int midgard, int hibernia)
        {
            return new[]
            {
                new DashboardRealmStats((int)eRealm.Albion, "Albion", Math.Max(0, albion)),
                new DashboardRealmStats((int)eRealm.Midgard, "Midgard", Math.Max(0, midgard)),
                new DashboardRealmStats((int)eRealm.Hibernia, "Hibernia", Math.Max(0, hibernia))
            };
        }

        public static IReadOnlyList<DashboardClassStats> BuildClassStats(IEnumerable<DashboardClassSample> samples)
        {
            return samples
                .Where(sample => sample.ClassId > 0 && !string.IsNullOrWhiteSpace(sample.ClassName))
                .GroupBy(sample => new { sample.ClassId, sample.ClassName })
                .Select(group => new DashboardClassStats(group.Key.ClassId, group.Key.ClassName, group.Count()))
                .OrderByDescending(stat => stat.Players)
                .ThenBy(stat => stat.ClassName, StringComparer.Ordinal)
                .ToArray();
        }

        public static IReadOnlyList<DashboardHistoryPoint> NormalizeHistory(IEnumerable<DbServerStat> rows, DateTime now, TimeSpan range)
        {
            DateTime start = now.ToUniversalTime().Add(-range);

            return rows
                .Where(row => row.StatDate.ToUniversalTime() >= start && row.StatDate.ToUniversalTime() <= now.ToUniversalTime())
                .OrderBy(row => row.StatDate)
                .Select(row => new DashboardHistoryPoint(
                    row.StatDate,
                    row.Clients,
                    row.AlbionPlayers,
                    row.MidgardPlayers,
                    row.HiberniaPlayers,
                    row.CPU,
                    row.Memory))
                .ToArray();
        }

        public static DateTime GetHourBucket(DateTime time)
        {
            DateTime utc = time.Kind == DateTimeKind.Utc ? time : time.ToUniversalTime();
            return new DateTime(utc.Year, utc.Month, utc.Day, utc.Hour, 0, 0, DateTimeKind.Utc);
        }

        public static string BuildActivityKey(DateTime bucketStart, eRealm realm)
        {
            return $"{GetHourBucket(bucketStart):yyyyMMddHH}|{(int)realm}";
        }

        public static IReadOnlyList<DashboardRealmActivityPoint> BuildRealmActivitySeries(IEnumerable<DbDashboardRealmActivity> rows, DateTime now, TimeSpan range)
        {
            DateTime end = GetHourBucket(now);
            DateTime start = GetHourBucket(end.Add(-range));

            Dictionary<DateTime, DashboardRealmActivityAccumulator> buckets = new();
            for (DateTime bucket = start; bucket <= end; bucket = bucket.AddHours(1))
                buckets[bucket] = new DashboardRealmActivityAccumulator(bucket);

            foreach (DbDashboardRealmActivity row in rows)
            {
                DateTime bucket = GetHourBucket(row.BucketStart);
                if (!buckets.TryGetValue(bucket, out DashboardRealmActivityAccumulator accumulator))
                    continue;

                accumulator.Add((eRealm)row.Realm, row.ServerIssuedGold, row.ServerIssuedRealmPoints);
            }

            return buckets.Values
                .OrderBy(accumulator => accumulator.Bucket)
                .Select(accumulator => accumulator.ToPoint())
                .ToArray();
        }

        private sealed class DashboardRealmActivityAccumulator
        {
            public DateTime Bucket { get; }
            private long m_albionGold;
            private long m_midgardGold;
            private long m_hiberniaGold;
            private long m_albionRealmPoints;
            private long m_midgardRealmPoints;
            private long m_hiberniaRealmPoints;

            public DashboardRealmActivityAccumulator(DateTime bucket)
            {
                Bucket = bucket;
            }

            public void Add(eRealm realm, long gold, long realmPoints)
            {
                switch (realm)
                {
                    case eRealm.Albion:
                        m_albionGold += Math.Max(0, gold);
                        m_albionRealmPoints += Math.Max(0, realmPoints);
                        break;
                    case eRealm.Midgard:
                        m_midgardGold += Math.Max(0, gold);
                        m_midgardRealmPoints += Math.Max(0, realmPoints);
                        break;
                    case eRealm.Hibernia:
                        m_hiberniaGold += Math.Max(0, gold);
                        m_hiberniaRealmPoints += Math.Max(0, realmPoints);
                        break;
                }
            }

            public DashboardRealmActivityPoint ToPoint()
            {
                return new DashboardRealmActivityPoint(
                    Bucket,
                    m_albionGold,
                    m_midgardGold,
                    m_hiberniaGold,
                    m_albionRealmPoints,
                    m_midgardRealmPoints,
                    m_hiberniaRealmPoints);
            }
        }
    }
}
```

- [ ] **Step 6: Run aggregation tests**

Run:

```bash
dotnet test Tests/Tests.csproj --no-restore --filter "UT_DashboardAggregation"
```

Expected: `Passed!`.

- [ ] **Step 7: Commit**

```bash
git add CoreDatabase/Tables/DbDashboardRealmActivity.cs GameServer/API/Dashboard/DashboardDtos.cs GameServer/API/Dashboard/DashboardAggregation.cs Tests/UnitTests/UT_DashboardAggregation.cs
git commit -m "feat: add dashboard aggregation contracts"
```

---

### Task 2: Live Dashboard Provider And Routes

**Files:**

- Create: `GameServer/API/Dashboard/DashboardPerformanceSampler.cs`
- Create: `GameServer/API/Dashboard/DashboardStatsProvider.cs`
- Create: `GameServer/API/Dashboard/DashboardRoutes.cs`
- Modify: `GameServer/API/ApiHost.cs`
- Test: `Tests/UnitTests/UT_DashboardAggregation.cs`

- [ ] **Step 1: Add privacy test for live DTO shape**

Append to `UT_DashboardAggregation.cs`:

```csharp
[Test]
public void LiveResponse_PublicContractDoesNotContainPrivateFieldNames()
{
    string[] propertyNames = typeof(DashboardLiveResponse)
        .GetProperties()
        .Select(property => property.Name)
        .ToArray();

    Assert.That(propertyNames, Does.Not.Contain("AccountName"));
    Assert.That(propertyNames, Does.Not.Contain("CharacterName"));
    Assert.That(propertyNames, Does.Not.Contain("IPAddress"));
    Assert.That(propertyNames, Does.Not.Contain("Zone"));
    Assert.That(propertyNames, Does.Not.Contain("GuildName"));
}
```

Also add `using System.Linq;` to the test file.

- [ ] **Step 2: Run test**

Run:

```bash
dotnet test Tests/Tests.csproj --no-restore --filter "LiveResponse_PublicContractDoesNotContainPrivateFieldNames"
```

Expected: passes after Task 1 DTOs exist.

- [ ] **Step 3: Add performance sampler**

Create `GameServer/API/Dashboard/DashboardPerformanceSampler.cs`:

```csharp
using System;
using DOL.GS.PerformanceStatistics;

namespace DOL.GS.API.Dashboard
{
    internal sealed class DashboardPerformanceSampler
    {
        private readonly IPerformanceStatistic m_cpu = new CurrentProcessCpuUsagePercentStatistic();

        public DashboardPerformanceStats GetSnapshot()
        {
            double cpu = m_cpu.GetNextValue();
            return new DashboardPerformanceStats(
                (float)(cpu >= 0 ? cpu : 0),
                GC.GetTotalMemory(false) / 1024);
        }
    }
}
```

- [ ] **Step 4: Add stats provider**

Create `GameServer/API/Dashboard/DashboardStatsProvider.cs`:

```csharp
using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;
using DOL.GS.ServerProperties;

namespace DOL.GS.API.Dashboard
{
    internal sealed class DashboardStatsProvider
    {
        private static readonly TimeSpan LiveCacheDuration = TimeSpan.FromSeconds(15);
        private static readonly TimeSpan HistoryCacheDuration = TimeSpan.FromSeconds(60);
        private readonly DashboardPerformanceSampler m_performanceSampler = new();
        private readonly object m_lock = new();
        private DashboardLiveResponse m_cachedLive;
        private DateTime m_cachedLiveUntil;
        private DashboardHistoryResponse m_cachedHistory;
        private DateTime m_cachedHistoryUntil;
        private DashboardRealmActivityResponse m_cachedActivity;
        private DateTime m_cachedActivityUntil;

        public DashboardLiveResponse GetLive()
        {
            DateTime now = DateTime.UtcNow;
            lock (m_lock)
            {
                if (m_cachedLive != null && now < m_cachedLiveUntil)
                    return m_cachedLive;

                List<GamePlayer> players = GetOnlinePlayers();
                IReadOnlyList<DashboardRealmStats> realms = DashboardAggregation.BuildRealmStats(
                    players.Count(player => player.Realm == eRealm.Albion),
                    players.Count(player => player.Realm == eRealm.Midgard),
                    players.Count(player => player.Realm == eRealm.Hibernia));

                var classSamples = players.Select(player =>
                {
                    string className = ScriptMgr.FindCharacterClass(player.Class)?.Name ?? $"Class {player.Class}";
                    return new DashboardClassSample(player.Class, className);
                });

                DateTime startedAt = GameServer.Instance?.StartupTime.ToUniversalTime() ?? now;
                DashboardLiveResponse response = new(
                    ClientService.Instance.ClientCount,
                    realms,
                    DashboardAggregation.BuildClassStats(classSamples),
                    m_performanceSampler.GetSnapshot(),
                    new Utils().GetUptime(startedAt),
                    startedAt,
                    now);

                m_cachedLive = response;
                m_cachedLiveUntil = now.Add(LiveCacheDuration);
                return response;
            }
        }

        public DashboardHistoryResponse GetHistory(string range)
        {
            DateTime now = DateTime.UtcNow;
            TimeSpan duration = ParseRange(range, TimeSpan.FromHours(24));
            lock (m_lock)
            {
                if (m_cachedHistory != null && now < m_cachedHistoryUntil)
                    return m_cachedHistory;

                DateTime start = now.Add(-duration);
                IList<DbServerStat> rows = GameServer.Database.SelectObjects<DbServerStat>(
                    DB.Column("StatDate").IsGreaterThan(start));

                DashboardHistoryResponse response = new(
                    ToRangeName(duration),
                    DashboardAggregation.NormalizeHistory(rows, now, duration),
                    now);

                m_cachedHistory = response;
                m_cachedHistoryUntil = now.Add(HistoryCacheDuration);
                return response;
            }
        }

        public DashboardRealmActivityResponse GetRealmActivity(string range)
        {
            DateTime now = DateTime.UtcNow;
            TimeSpan duration = ParseRange(range, TimeSpan.FromDays(7));
            lock (m_lock)
            {
                if (m_cachedActivity != null && now < m_cachedActivityUntil)
                    return m_cachedActivity;

                DateTime start = DashboardAggregation.GetHourBucket(now.Add(-duration));
                IList<DbDashboardRealmActivity> rows = GameServer.Database.SelectObjects<DbDashboardRealmActivity>(
                    DB.Column("BucketStart").IsGreaterThan(start));

                DashboardRealmActivityResponse response = new(
                    ToRangeName(duration),
                    DashboardAggregation.BuildRealmActivitySeries(rows, now, duration),
                    now);

                m_cachedActivity = response;
                m_cachedActivityUntil = now.Add(HistoryCacheDuration);
                return response;
            }
        }

        private static List<GamePlayer> GetOnlinePlayers()
        {
            return ClientService.Instance.GetPlayersOfRealm(eRealm.Albion)
                .Concat(ClientService.Instance.GetPlayersOfRealm(eRealm.Midgard))
                .Concat(ClientService.Instance.GetPlayersOfRealm(eRealm.Hibernia))
                .Where(player => player != null)
                .ToList();
        }

        private static TimeSpan ParseRange(string range, TimeSpan fallback)
        {
            return range?.ToLowerInvariant() switch
            {
                "24h" => TimeSpan.FromHours(24),
                "7d" => TimeSpan.FromDays(7),
                _ => fallback
            };
        }

        private static string ToRangeName(TimeSpan duration)
        {
            return duration.TotalDays >= 7 ? "7d" : "24h";
        }
    }
}
```

- [ ] **Step 5: Add routes**

Create `GameServer/API/Dashboard/DashboardRoutes.cs`:

```csharp
using System.IO;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.FileProviders;

namespace DOL.GS.API.Dashboard
{
    internal static class DashboardRoutes
    {
        public static void MapDashboardRoutes(this WebApplication api, string contentRoot)
        {
            string dashboardRoot = Path.Combine(contentRoot, "wwwroot", "dashboard");
            DashboardStatsProvider provider = new();

            api.UseStaticFiles(new StaticFileOptions
            {
                FileProvider = new PhysicalFileProvider(dashboardRoot),
                RequestPath = new PathString("/dashboard")
            });

            api.MapGet("/dashboard", async context =>
            {
                context.Response.ContentType = "text/html; charset=utf-8";
                await context.Response.SendFileAsync(Path.Combine(dashboardRoot, "index.html"));
            });

            api.MapGet("/api/dashboard/live", () => Results.Ok(provider.GetLive()));
            api.MapGet("/api/dashboard/history", (string range) => Results.Ok(provider.GetHistory(range)));
            api.MapGet("/api/dashboard/realm-activity", (string range) => Results.Ok(provider.GetRealmActivity(range)));
        }
    }
}
```

- [ ] **Step 6: Wire routes into API host**

Modify `GameServer/API/ApiHost.cs`:

```csharp
using DOL.GS.API.Dashboard;
```

Add after the `/stats/uptime` route block:

```csharp
api.MapDashboardRoutes(contentRoot);
```

- [ ] **Step 7: Build**

Run:

```bash
dotnet build GameServer/GameServer.csproj --no-restore
```

Expected: build passes. If `Utils.GetUptime` does not accept UTC `DateTime`, adjust only the provider call to match the existing method signature.

- [ ] **Step 8: Commit**

```bash
git add GameServer/API/ApiHost.cs GameServer/API/Dashboard/DashboardPerformanceSampler.cs GameServer/API/Dashboard/DashboardStatsProvider.cs GameServer/API/Dashboard/DashboardRoutes.cs Tests/UnitTests/UT_DashboardAggregation.cs
git commit -m "feat: expose live dashboard stats"
```

---

### Task 3: Static Dashboard Page

**Files:**

- Create: `GameServer/API/dashboard/index.html`
- Create: `GameServer/API/dashboard/dashboard.css`
- Create: `GameServer/API/dashboard/dashboard.js`
- Modify: `GameServer/GameServer.csproj`

- [ ] **Step 1: Add static asset copy rules**

Modify `GameServer/GameServer.csproj` item group:

```xml
<DashboardAssets Include=".\API\dashboard\**\*" />
```

Modify `CopyFiles` target:

```xml
<Copy SourceFiles="@(DashboardAssets)" DestinationFiles="@(DashboardAssets->'$(MSBuildProjectDirectory)\..\$(Configuration)\wwwroot\dashboard\%(RecursiveDir)%(Filename)%(Extension)')" />
```

- [ ] **Step 2: Add dashboard HTML**

Create `GameServer/API/dashboard/index.html`:

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KDAOC Server Stats</title>
  <link rel="stylesheet" href="/dashboard/dashboard.css">
</head>
<body>
  <main class="shell">
    <header class="masthead">
      <div>
        <p class="eyebrow">KDAOC Live</p>
        <h1>Server Statistics</h1>
      </div>
      <div class="refresh">Updated <span id="updatedAt">-</span></div>
    </header>

    <section class="summary" aria-label="Server summary">
      <article><span>Online</span><strong id="onlinePlayers">0</strong></article>
      <article><span>Albion</span><strong id="albionPlayers">0</strong></article>
      <article><span>Midgard</span><strong id="midgardPlayers">0</strong></article>
      <article><span>Hibernia</span><strong id="hiberniaPlayers">0</strong></article>
      <article><span>Uptime</span><strong id="uptime">-</strong></article>
    </section>

    <section class="grid">
      <article class="panel wide"><h2>24h Population</h2><canvas id="populationChart"></canvas></article>
      <article class="panel"><h2>Realm Split</h2><canvas id="realmChart"></canvas></article>
      <article class="panel"><h2>Class Distribution</h2><canvas id="classChart"></canvas></article>
      <article class="panel wide"><h2>CPU / RAM Trend</h2><canvas id="performanceChart"></canvas></article>
      <article class="panel wide"><h2>This Week Server-Issued Gold</h2><canvas id="goldChart"></canvas></article>
      <article class="panel wide"><h2>This Week Server-Issued Realm Points</h2><canvas id="rpChart"></canvas></article>
    </section>
  </main>
  <script src="/dashboard/dashboard.js"></script>
</body>
</html>
```

- [ ] **Step 3: Add CSS**

Create `GameServer/API/dashboard/dashboard.css` with restrained operational styling:

```css
:root {
  color-scheme: dark;
  --bg: #101418;
  --surface: #161c22;
  --line: #29323b;
  --text: #edf1f5;
  --muted: #9ba8b5;
  --albion: #d64545;
  --midgard: #5a8dee;
  --hibernia: #4fb06d;
  --accent: #d8ae52;
}

* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.shell { width: min(1240px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0 48px; }
.masthead { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.eyebrow { margin: 0 0 4px; color: var(--accent); font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0; }
h1, h2 { margin: 0; letter-spacing: 0; }
h1 { font-size: clamp(28px, 4vw, 44px); }
h2 { font-size: 17px; }
.refresh { color: var(--muted); font-size: 14px; }
.summary { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-bottom: 10px; }
.summary article, .panel { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; }
.summary article { padding: 14px; min-height: 82px; }
.summary span { display: block; color: var(--muted); font-size: 13px; }
.summary strong { display: block; margin-top: 7px; font-size: 28px; line-height: 1.1; }
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.panel { padding: 14px; min-height: 320px; }
.panel.wide { grid-column: span 2; }
canvas { width: 100%; height: 260px; display: block; margin-top: 10px; }

@media (max-width: 820px) {
  .masthead { align-items: start; flex-direction: column; }
  .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .summary article:first-child { grid-column: span 2; }
  .grid { grid-template-columns: 1fr; }
  .panel.wide { grid-column: span 1; }
}
```

- [ ] **Step 4: Add local chart JavaScript**

Create `GameServer/API/dashboard/dashboard.js`:

```javascript
const realmColors = ["#d64545", "#5a8dee", "#4fb06d"];

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json();
}

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function resizeCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = Math.max(1, Math.floor(width * ratio));
  canvas.height = Math.max(1, Math.floor(height * ratio));
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { ctx, width, height };
}

function clearChart(canvas, title) {
  const { ctx, width, height } = resizeCanvas(canvas);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#9ba8b5";
  ctx.font = "14px system-ui";
  ctx.fillText(title, 12, 26);
  return { ctx, width, height };
}

function drawLineChart(canvasId, series) {
  const canvas = document.getElementById(canvasId);
  const { ctx, width, height } = clearChart(canvas, "Not enough data yet");
  const padding = 28;
  const max = Math.max(1, ...series.flatMap(item => item.values));
  const points = series[0]?.values.length || 0;
  if (points < 2) return;

  ctx.strokeStyle = "#29323b";
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i++) {
    const y = padding + ((height - padding * 2) * i / 3);
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(width - padding, y);
    ctx.stroke();
  }

  series.forEach((item, index) => {
    ctx.strokeStyle = item.color || realmColors[index % realmColors.length];
    ctx.lineWidth = 2;
    ctx.beginPath();
    item.values.forEach((value, pointIndex) => {
      const x = padding + ((width - padding * 2) * pointIndex / (points - 1));
      const y = height - padding - ((height - padding * 2) * value / max);
      if (pointIndex === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
}

function drawBarChart(canvasId, labels, values, colors) {
  const canvas = document.getElementById(canvasId);
  const { ctx, width, height } = clearChart(canvas, "No data");
  const max = Math.max(1, ...values);
  const barWidth = Math.max(12, (width - 40) / Math.max(1, values.length));
  ctx.font = "12px system-ui";
  values.forEach((value, index) => {
    const x = 20 + index * barWidth;
    const h = (height - 70) * value / max;
    ctx.fillStyle = colors[index % colors.length];
    ctx.fillRect(x, height - 34 - h, Math.max(8, barWidth - 8), h);
    ctx.fillStyle = "#edf1f5";
    ctx.fillText(String(value), x, height - 40 - h);
    ctx.fillStyle = "#9ba8b5";
    ctx.fillText(labels[index].slice(0, 10), x, height - 12);
  });
}

function applyLive(live) {
  setText("onlinePlayers", live.totalPlayers);
  setText("updatedAt", new Date(live.updatedAt).toLocaleTimeString());
  setText("uptime", live.uptime);
  const realms = live.realms || [];
  setText("albionPlayers", realms.find(r => r.realmName === "Albion")?.players ?? 0);
  setText("midgardPlayers", realms.find(r => r.realmName === "Midgard")?.players ?? 0);
  setText("hiberniaPlayers", realms.find(r => r.realmName === "Hibernia")?.players ?? 0);
  drawBarChart("realmChart", realms.map(r => r.realmName), realms.map(r => r.players), realmColors);
  drawBarChart("classChart", (live.classes || []).map(c => c.className), (live.classes || []).map(c => c.players), ["#d8ae52", "#7dc5d8", "#c97cc7"]);
}

function applyHistory(history) {
  const points = history.points || [];
  drawLineChart("populationChart", [
    { values: points.map(p => p.totalPlayers), color: "#d8ae52" },
    { values: points.map(p => p.albionPlayers), color: realmColors[0] },
    { values: points.map(p => p.midgardPlayers), color: realmColors[1] },
    { values: points.map(p => p.hiberniaPlayers), color: realmColors[2] }
  ]);
  drawLineChart("performanceChart", [
    { values: points.map(p => p.cpuPercent), color: "#d8ae52" },
    { values: points.map(p => Math.round((p.memoryKb || 0) / 1024)), color: "#7dc5d8" }
  ]);
}

function applyActivity(activity) {
  const points = activity.points || [];
  drawLineChart("goldChart", [
    { values: points.map(p => p.albionGold), color: realmColors[0] },
    { values: points.map(p => p.midgardGold), color: realmColors[1] },
    { values: points.map(p => p.hiberniaGold), color: realmColors[2] }
  ]);
  drawLineChart("rpChart", [
    { values: points.map(p => p.albionRealmPoints), color: realmColors[0] },
    { values: points.map(p => p.midgardRealmPoints), color: realmColors[1] },
    { values: points.map(p => p.hiberniaRealmPoints), color: realmColors[2] }
  ]);
}

async function refresh() {
  const [live, history, activity] = await Promise.all([
    getJson("/api/dashboard/live"),
    getJson("/api/dashboard/history?range=24h"),
    getJson("/api/dashboard/realm-activity?range=7d")
  ]);
  applyLive(live);
  applyHistory(history);
  applyActivity(activity);
}

window.addEventListener("resize", refresh);
refresh();
setInterval(refresh, 30000);
```

- [ ] **Step 5: Build and check copied assets**

Run:

```bash
dotnet build GameServer/GameServer.csproj --no-restore
test -f Debug/wwwroot/dashboard/index.html
test -f Debug/wwwroot/dashboard/dashboard.js
test -f Debug/wwwroot/dashboard/dashboard.css
```

Expected: build passes and all three files exist in `Debug/wwwroot/dashboard`.

- [ ] **Step 6: Commit**

```bash
git add GameServer/GameServer.csproj GameServer/API/dashboard
git commit -m "feat: add public dashboard page"
```

---

### Task 4: Realm Activity Tracker

**Files:**

- Create: `GameServer/gameutils/DashboardRealmActivityTracker.cs`
- Test: `Tests/UnitTests/UT_DashboardRealmActivityTracker.cs`

- [ ] **Step 1: Write failing tracker tests**

Create `Tests/UnitTests/UT_DashboardRealmActivityTracker.cs`:

```csharp
using System;
using System.Collections.Generic;
using DOL.GS;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DashboardRealmActivityTracker
    {
        [Test]
        public void RecordServerIssuedGold_IgnoresInvalidRealmAndNonPositiveAmount()
        {
            FakeDashboardRealmActivitySink sink = new();
            DashboardRealmActivityTracker.Sink = sink;

            DashboardRealmActivityTracker.RecordServerIssuedGold(eRealm.None, 100, DateTime.UtcNow);
            DashboardRealmActivityTracker.RecordServerIssuedGold(eRealm.Albion, 0, DateTime.UtcNow);
            DashboardRealmActivityTracker.RecordServerIssuedGold(eRealm.Albion, -5, DateTime.UtcNow);

            Assert.That(sink.Entries, Is.Empty);
        }

        [Test]
        public void RecordServerIssuedRealmPoints_ForwardsValidAmountToSink()
        {
            FakeDashboardRealmActivitySink sink = new();
            DashboardRealmActivityTracker.Sink = sink;
            DateTime at = new(2026, 5, 11, 12, 42, 0, DateTimeKind.Utc);

            DashboardRealmActivityTracker.RecordServerIssuedRealmPoints(eRealm.Midgard, 75, at);

            Assert.That(sink.Entries, Has.Count.EqualTo(1));
            Assert.That(sink.Entries[0].Realm, Is.EqualTo(eRealm.Midgard));
            Assert.That(sink.Entries[0].RealmPoints, Is.EqualTo(75));
            Assert.That(sink.Entries[0].Gold, Is.EqualTo(0));
        }

        [TearDown]
        public void TearDown()
        {
            DashboardRealmActivityTracker.ResetSink();
        }

        private sealed class FakeDashboardRealmActivitySink : IDashboardRealmActivitySink
        {
            public List<Entry> Entries { get; } = new();

            public void Add(eRealm realm, long gold, long realmPoints, DateTime at)
            {
                Entries.Add(new Entry(realm, gold, realmPoints, at));
            }
        }

        private sealed record Entry(eRealm Realm, long Gold, long RealmPoints, DateTime At);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
dotnet test Tests/Tests.csproj --no-restore --filter "UT_DashboardRealmActivityTracker"
```

Expected: build fails because tracker types do not exist.

- [ ] **Step 3: Add tracker**

Create `GameServer/gameutils/DashboardRealmActivityTracker.cs`:

```csharp
using System;
using DOL.Database;
using DOL.GS.API.Dashboard;

namespace DOL.GS
{
    public interface IDashboardRealmActivitySink
    {
        void Add(eRealm realm, long gold, long realmPoints, DateTime at);
    }

    public static class DashboardRealmActivityTracker
    {
        private static readonly IDashboardRealmActivitySink DefaultSink = new DatabaseDashboardRealmActivitySink();
        private static IDashboardRealmActivitySink m_sink = DefaultSink;

        public static IDashboardRealmActivitySink Sink
        {
            get => m_sink;
            set => m_sink = value ?? DefaultSink;
        }

        public static void ResetSink()
        {
            m_sink = DefaultSink;
        }

        public static void RecordServerIssuedGold(eRealm realm, long copper, DateTime at)
        {
            if (!ShouldRecord(realm, copper))
                return;

            m_sink.Add(realm, copper, 0, at);
        }

        public static void RecordServerIssuedRealmPoints(eRealm realm, long realmPoints, DateTime at)
        {
            if (!ShouldRecord(realm, realmPoints))
                return;

            m_sink.Add(realm, 0, realmPoints, at);
        }

        private static bool ShouldRecord(eRealm realm, long amount)
        {
            return amount > 0 && (realm == eRealm.Albion || realm == eRealm.Midgard || realm == eRealm.Hibernia);
        }

        private sealed class DatabaseDashboardRealmActivitySink : IDashboardRealmActivitySink
        {
            private readonly object m_lock = new();

            public void Add(eRealm realm, long gold, long realmPoints, DateTime at)
            {
                DateTime bucket = DashboardAggregation.GetHourBucket(at);
                string key = DashboardAggregation.BuildActivityKey(bucket, realm);

                lock (m_lock)
                {
                    DbDashboardRealmActivity row = GameServer.Database.FindObjectByKey<DbDashboardRealmActivity>(key);
                    if (row == null)
                    {
                        row = new DbDashboardRealmActivity
                        {
                            BucketRealmKey = key,
                            BucketStart = bucket,
                            Realm = (int)realm,
                            ServerIssuedGold = 0,
                            ServerIssuedRealmPoints = 0
                        };
                        GameServer.Database.AddObject(row);
                    }

                    row.ServerIssuedGold += Math.Max(0, gold);
                    row.ServerIssuedRealmPoints += Math.Max(0, realmPoints);
                    GameServer.Database.SaveObject(row);
                }
            }
        }
    }
}
```

- [ ] **Step 4: Run tracker tests**

Run:

```bash
dotnet test Tests/Tests.csproj --no-restore --filter "UT_DashboardRealmActivityTracker"
```

Expected: `Passed!`.

- [ ] **Step 5: Commit**

```bash
git add GameServer/gameutils/DashboardRealmActivityTracker.cs Tests/UnitTests/UT_DashboardRealmActivityTracker.cs
git commit -m "feat: add realm activity tracker"
```

---

### Task 5: Wire Server-Issued RP Tracking

**Files:**

- Modify: `GameServer/gameobjects/GamePlayer.cs`
- Modify: `GameServer/commands/gmcommands/Player.cs`

- [ ] **Step 1: Add RP tracking overload**

Modify the existing `GainRealmPoints` overload set in `GameServer/gameobjects/GamePlayer.cs`:

```csharp
public override void GainRealmPoints(long amount)
{
    GainRealmPoints(amount, true, true);
}

public void GainRealmPoints(long amount, bool modify)
{
    GainRealmPoints(amount, modify, true);
}

public void GainRealmPoints(long amount, bool modify, bool sendMessage)
{
    GainRealmPoints(amount, modify, sendMessage, true);
}

public virtual void GainRealmPoints(long amount, bool modify, bool sendMessage, bool notify)
{
    GainRealmPoints(amount, modify, sendMessage, notify, true);
}

public virtual void GainRealmPoints(long amount, bool modify, bool sendMessage, bool notify, bool trackDashboardReward)
{
    // existing body moves here
}
```

Inside the final overload, after:

```csharp
m_statistics.AddToTotalRealmPointsEarned((uint) amount);
```

add:

```csharp
if (trackDashboardReward && amount > 0 && Client?.Account?.PrivLevel == 1)
    DashboardRealmActivityTracker.RecordServerIssuedRealmPoints(Realm, amount, DateTime.UtcNow);
```

This counts PvP, bonus, event, quest, and system RP for normal player accounts while allowing GM/admin manual grants to opt out.

- [ ] **Step 2: Suppress GM manual RP grant**

In `GameServer/commands/gmcommands/Player.cs`, replace:

```csharp
player.GainRealmPoints(amount, false);
```

with:

```csharp
player.GainRealmPoints(amount, false, true, true, false);
```

- [ ] **Step 3: Build**

Run:

```bash
dotnet build GameServer/GameServer.csproj --no-restore
```

Expected: build passes.

- [ ] **Step 4: Commit**

```bash
git add GameServer/gameobjects/GamePlayer.cs GameServer/commands/gmcommands/Player.cs
git commit -m "feat: track server-issued realm points"
```

---

### Task 6: Wire Server-Issued Gold Tracking

**Files:**

- Modify: `GameServer/gameobjects/GamePlayer.cs`
- Modify: `GameServer/gameutils/Group.cs`
- Modify: `GameServer/gameobjects/GameMerchant.cs`
- Modify: `GameServer/keeps/Gameobjects/Guards/GameGuardMerchant.cs`
- Modify: `GameServer/quests/Tasks/AbstractTask.cs`
- Modify: `GameServer/quests/Missions/AbstractMission.cs`
- Modify: `GameServer/quests/QuestsMgr/DataQuest.cs`
- Modify: `GameServer/quests/QuestsMgr/RewardQuest.cs`
- Modify: `GameServer/serverrules/AbstractServerRules.cs`
- Modify: `GameServer/behaviour/Actions/GiveGoldAction.cs`
- Modify: `GameServer/scripts/quests/**/*.cs`

- [ ] **Step 1: Add explicit server-issued money API**

In `GameServer/gameobjects/GamePlayer.cs`, add these overloads immediately after existing `AddMoney(...)` overloads:

```csharp
public virtual void AddServerIssuedMoney(long money)
{
    AddServerIssuedMoney(money, null, eChatType.CT_System, eChatLoc.CL_SystemWindow);
}

public virtual void AddServerIssuedMoney(long money, string messageFormat)
{
    AddServerIssuedMoney(money, messageFormat, eChatType.CT_System, eChatLoc.CL_SystemWindow);
}

public virtual void AddServerIssuedMoney(long money, string messageFormat, eChatType ct, eChatLoc cl)
{
    AddMoney(money, messageFormat, ct, cl);

    if (money > 0 && Client?.Account?.PrivLevel == 1)
        DashboardRealmActivityTracker.RecordServerIssuedGold(Realm, money, DateTime.UtcNow);
}
```

- [ ] **Step 2: Change loot and merchant payout paths**

Replace trusted server-created payout calls:

```csharp
AddMoney(moneyToPlayer, LanguageMgr.GetTranslation(Client.Account.Language, "GamePlayer.PickupObject.YouPickUp", Money.GetString(moneyToPlayer)));
```

with:

```csharp
AddServerIssuedMoney(moneyToPlayer, LanguageMgr.GetTranslation(Client.Account.Language, "GamePlayer.PickupObject.YouPickUp", Money.GetString(moneyToPlayer)));
```

In `GameServer/gameutils/Group.cs`, replace:

```csharp
eligibleMember.AddMoney(moneyToPlayer, LanguageMgr.GetTranslation(eligibleMember.Client.Account.Language, eligibleMembers.Count > 1 ? "GamePlayer.PickupObject.YourLootShare" : "GamePlayer.PickupObject.YouPickUp", Money.GetString(splitMoney)));
```

with:

```csharp
eligibleMember.AddServerIssuedMoney(moneyToPlayer, LanguageMgr.GetTranslation(eligibleMember.Client.Account.Language, eligibleMembers.Count > 1 ? "GamePlayer.PickupObject.YourLootShare" : "GamePlayer.PickupObject.YouPickUp", Money.GetString(splitMoney)));
```

In both merchant files, replace:

```csharp
player.AddMoney(itemValue, message, eChatType.CT_Merchant, eChatLoc.CL_SystemWindow);
```

with:

```csharp
player.AddServerIssuedMoney(itemValue, message, eChatType.CT_Merchant, eChatLoc.CL_SystemWindow);
```

- [ ] **Step 3: Change core quest/task/mission payout paths**

Use targeted replacements in these files only:

```bash
perl -0pi -e 's/\.AddMoney\(/.AddServerIssuedMoney(/g' \
  GameServer/quests/Tasks/AbstractTask.cs \
  GameServer/quests/Missions/AbstractMission.cs \
  GameServer/quests/QuestsMgr/DataQuest.cs \
  GameServer/quests/QuestsMgr/RewardQuest.cs \
  GameServer/serverrules/AbstractServerRules.cs \
  GameServer/behaviour/Actions/GiveGoldAction.cs
```

Then inspect:

```bash
git diff -- GameServer/quests/Tasks/AbstractTask.cs GameServer/quests/Missions/AbstractMission.cs GameServer/quests/QuestsMgr/DataQuest.cs GameServer/quests/QuestsMgr/RewardQuest.cs GameServer/serverrules/AbstractServerRules.cs GameServer/behaviour/Actions/GiveGoldAction.cs
```

Expected: only player reward money calls changed from `AddMoney` to `AddServerIssuedMoney`.

- [ ] **Step 4: Change direct quest-script payout paths**

Use targeted replacements in quest scripts:

```bash
find GameServer/scripts/quests -name '*.cs' -print0 | xargs -0 perl -0pi -e 's/\.AddMoney\(/.AddServerIssuedMoney(/g'
```

Then inspect the replacement set:

```bash
git diff --stat -- GameServer/scripts/quests
rg -n "\.AddServerIssuedMoney\(" GameServer/scripts/quests | wc -l
```

Expected: direct quest reward money calls changed. Commented sample reward lines may also be renamed in comments; that is harmless but can be cleaned if a diff hunk becomes noisy.

- [ ] **Step 5: Audit untracked AddMoney calls**

Run:

```bash
rg -n "\.AddMoney\(" GameServer | rg -v "PlayerTradeWindow|ConsignmentState|gameutils/Guild.cs|commands/gmcommands/Player.cs"
```

Expected: remaining output is either non-gold methods, comments, or intentionally excluded transfer/manual-grant paths. Any remaining live reward path should be changed to `AddServerIssuedMoney(...)` before continuing.

- [ ] **Step 6: Build**

Run:

```bash
dotnet build GameServer/GameServer.csproj --no-restore
```

Expected: build passes.

- [ ] **Step 7: Commit**

```bash
git add GameServer/gameobjects/GamePlayer.cs GameServer/gameutils/Group.cs GameServer/gameobjects/GameMerchant.cs GameServer/keeps/Gameobjects/Guards/GameGuardMerchant.cs GameServer/quests GameServer/serverrules/AbstractServerRules.cs GameServer/behaviour/Actions/GiveGoldAction.cs GameServer/scripts/quests
git commit -m "feat: track server-issued gold rewards"
```

---

### Task 7: Naver Cafe Badge PNG

**Files:**

- Create: `GameServer/API/Dashboard/DashboardBadgeRenderer.cs`
- Modify: `GameServer/API/Dashboard/DashboardRoutes.cs`
- Modify: `GameServer/GameServer.csproj`
- Test: `Tests/UnitTests/UT_DashboardBadgeRenderer.cs`

- [ ] **Step 1: Add package references**

Modify `GameServer/GameServer.csproj`:

```xml
<PackageReference Include="SkiaSharp" Version="3.119.2" />
<PackageReference Include="SkiaSharp.NativeAssets.Linux.NoDependencies" Version="3.119.2" />
```

- [ ] **Step 2: Write failing badge test**

Create `Tests/UnitTests/UT_DashboardBadgeRenderer.cs`:

```csharp
using System;
using DOL.GS.API.Dashboard;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DashboardBadgeRenderer
    {
        [Test]
        public void Render_ReturnsPngBytes()
        {
            DashboardLiveResponse live = new(
                12,
                DashboardAggregation.BuildRealmStats(4, 5, 3),
                Array.Empty<DashboardClassStats>(),
                new DashboardPerformanceStats(0, 0),
                "1d 02h",
                DateTime.UtcNow.AddDays(-1),
                DateTime.UtcNow);

            byte[] png = DashboardBadgeRenderer.Render(live);

            Assert.That(png.Length, Is.GreaterThan(100));
            Assert.That(png[0], Is.EqualTo(0x89));
            Assert.That(png[1], Is.EqualTo(0x50));
            Assert.That(png[2], Is.EqualTo(0x4e));
            Assert.That(png[3], Is.EqualTo(0x47));
        }
    }
}
```

- [ ] **Step 3: Add renderer**

Create `GameServer/API/Dashboard/DashboardBadgeRenderer.cs`:

```csharp
using System;
using System.Linq;
using SkiaSharp;

namespace DOL.GS.API.Dashboard
{
    public static class DashboardBadgeRenderer
    {
        public static byte[] Render(DashboardLiveResponse live)
        {
            const int width = 900;
            const int height = 240;

            using SKBitmap bitmap = new(width, height);
            using SKCanvas canvas = new(bitmap);
            canvas.Clear(new SKColor(16, 20, 24));

            using SKPaint titlePaint = new() { Color = SKColors.White, TextSize = 42, IsAntialias = true, Typeface = SKTypeface.FromFamilyName("Arial", SKFontStyle.Bold) };
            using SKPaint labelPaint = new() { Color = new SKColor(155, 168, 181), TextSize = 24, IsAntialias = true };
            using SKPaint valuePaint = new() { Color = new SKColor(216, 174, 82), TextSize = 58, IsAntialias = true, Typeface = SKTypeface.FromFamilyName("Arial", SKFontStyle.Bold) };
            using SKPaint realmPaint = new() { Color = SKColors.White, TextSize = 27, IsAntialias = true };

            canvas.DrawText("KDAOC Server Status", 36, 62, titlePaint);
            canvas.DrawText("Online", 40, 118, labelPaint);
            canvas.DrawText(live.TotalPlayers.ToString(), 40, 186, valuePaint);

            DrawRealm(canvas, realmPaint, live, "Albion", 280, 144, new SKColor(214, 69, 69));
            DrawRealm(canvas, realmPaint, live, "Midgard", 470, 144, new SKColor(90, 141, 238));
            DrawRealm(canvas, realmPaint, live, "Hibernia", 670, 144, new SKColor(79, 176, 109));

            using SKPaint updatedPaint = new() { Color = new SKColor(155, 168, 181), TextSize = 20, IsAntialias = true };
            canvas.DrawText($"Updated {live.UpdatedAt.ToLocalTime():HH:mm:ss}", 650, 215, updatedPaint);

            using SKImage image = SKImage.FromBitmap(bitmap);
            using SKData data = image.Encode(SKEncodedImageFormat.Png, 92);
            return data.ToArray();
        }

        private static void DrawRealm(SKCanvas canvas, SKPaint textPaint, DashboardLiveResponse live, string realmName, float x, float y, SKColor color)
        {
            int players = live.Realms.FirstOrDefault(realm => realm.RealmName == realmName)?.Players ?? 0;
            using SKPaint dotPaint = new() { Color = color, IsAntialias = true };
            canvas.DrawCircle(x, y - 9, 9, dotPaint);
            canvas.DrawText($"{realmName} {players}", x + 18, y, textPaint);
        }
    }
}
```

- [ ] **Step 4: Add badge endpoint**

Modify `DashboardRoutes.cs`:

```csharp
api.MapGet("/status/badge.png", () =>
{
    byte[] png = DashboardBadgeRenderer.Render(provider.GetLive());
    return Results.File(png, "image/png");
});
```

Add short cache headers if direct `HttpContext` is preferred:

```csharp
api.MapGet("/status/badge.png", (HttpContext context) =>
{
    context.Response.Headers.CacheControl = "public, max-age=60";
    byte[] png = DashboardBadgeRenderer.Render(provider.GetLive());
    return Results.File(png, "image/png");
});
```

- [ ] **Step 5: Run tests and build**

Run:

```bash
dotnet test Tests/Tests.csproj --no-restore --filter "UT_DashboardBadgeRenderer"
dotnet build GameServer/GameServer.csproj --no-restore
```

Expected: test and build pass.

- [ ] **Step 6: Commit**

```bash
git add GameServer/GameServer.csproj GameServer/API/Dashboard/DashboardBadgeRenderer.cs GameServer/API/Dashboard/DashboardRoutes.cs Tests/UnitTests/UT_DashboardBadgeRenderer.cs
git commit -m "feat: add dashboard status badge"
```

---

### Task 8: Manual Smoke Test And Documentation

**Files:**

- Modify: `docs/local-mariadb-dotnet-runbook.md`

- [ ] **Step 1: Update runbook**

Append this section to `docs/local-mariadb-dotnet-runbook.md`:

```markdown
## Public Dashboard

Enable the Atlas API and periodic stat saving before using the public dashboard:

- `atlas_api=True`
- `statsave_interval=1`

Dashboard URLs:

- `http://<server-host>:<api-port>/dashboard`
- `http://<server-host>:<api-port>/api/dashboard/live`
- `http://<server-host>:<api-port>/api/dashboard/history?range=24h`
- `http://<server-host>:<api-port>/api/dashboard/realm-activity?range=7d`
- `http://<server-host>:<api-port>/status/badge.png`

For Naver Cafe, use `/status/badge.png` as a plain image and link the image to `/dashboard` if the cafe editor allows image links. The badge does not require JavaScript or iframe support.

Gold and RP charts intentionally show server-issued inflow only. Player trades, consignment payouts, guild transfers, vault movement, and manual GM money/RP grants are excluded.
```

- [ ] **Step 2: Run full verification**

Run:

```bash
dotnet test Tests/Tests.csproj --no-restore
dotnet build CoreServer/CoreServer.csproj --no-restore
```

Expected: tests and server build pass.

- [ ] **Step 3: Optional local API smoke test**

If a local MariaDB-backed server is already running with `atlas_api=True`, run:

```bash
curl -I http://localhost:9874/dashboard
curl -s http://localhost:9874/api/dashboard/live
curl -s http://localhost:9874/api/dashboard/history?range=24h
curl -s http://localhost:9874/api/dashboard/realm-activity?range=7d
curl -I http://localhost:9874/status/badge.png
```

Expected:

- `/dashboard` returns `200 OK` and `text/html`.
- JSON endpoints return JSON without account names, character names, IP addresses, or player lists.
- `/status/badge.png` returns `200 OK` and `image/png`.

- [ ] **Step 4: Commit**

```bash
git add docs/local-mariadb-dotnet-runbook.md
git commit -m "docs: document public dashboard setup"
```

---

## Final Quality Gate

- [ ] `dotnet test Tests/Tests.csproj --no-restore`
- [ ] `dotnet build CoreServer/CoreServer.csproj --no-restore`
- [ ] `rg -n "AccountName|CharacterName|IPAddress|Zone|GuildName" GameServer/API/Dashboard` returns no private public DTO fields.
- [ ] `rg -n "\.AddMoney\(" GameServer | rg -v "PlayerTradeWindow|ConsignmentState|gameutils/Guild.cs|commands/gmcommands/Player.cs"` is reviewed and has no missed server-issued reward path.
- [ ] The dashboard renders at `/dashboard`.
- [ ] The badge renders at `/status/badge.png`.

## Self-Review

Spec coverage:

- Public dashboard page: Task 3.
- Live JSON endpoint: Task 2.
- History JSON endpoint from `serverstats`: Task 2.
- Weekly realm gold/RP endpoint: Tasks 1, 2, 4, 5, 6.
- Naver Cafe PNG badge: Task 7.
- CPU/RAM only in chart: Task 3 HTML/JS, no CPU/RAM summary card.
- Server-issued gold only: Task 6, with explicit exclusions.
- Server-issued RP only: Task 5, with GM suppression.
- Privacy-safe aggregation: Tasks 1 and 2 DTO tests plus final quality gate.
- Runbook/deployment notes: Task 8.

Placeholder scan:

- This plan defines every new file, route, command, and test needed for the first implementation.
- The only conditional step is the optional local API smoke test, which depends on whether the local server is already running.

Type consistency:

- `DbDashboardRealmActivity`, `DashboardAggregation`, `DashboardStatsProvider`, `DashboardRealmActivityTracker`, and `DashboardBadgeRenderer` names are consistent across tasks.
- DTO property names used by `dashboard.js` match ASP.NET Core default camelCase JSON output.
