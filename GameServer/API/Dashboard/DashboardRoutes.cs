using System.IO;
using System.Linq;
using System;
using System.Collections.Generic;
using System.Globalization;
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
            string indexPath = Path.Combine(dashboardRoot, "index.html");
            string statusPath = Path.Combine(dashboardRoot, "status.html");
            DashboardStatsProvider provider = new();

            if (Directory.Exists(dashboardRoot))
            {
                api.UseStaticFiles(new StaticFileOptions
                {
                    FileProvider = new PhysicalFileProvider(dashboardRoot),
                    RequestPath = new PathString("/dashboard")
                });
            }

            api.MapGet("/dashboard", () =>
            {
                if (File.Exists(indexPath))
                    return Results.File(indexPath, "text/html");

                return Results.Text(
                    "Dashboard assets are not built yet.",
                    "text/plain",
                    statusCode: StatusCodes.Status503ServiceUnavailable);
            });

            api.MapGet("/api/dashboard/live", () => Results.Ok(provider.GetLive()));
            api.MapGet("/api/dashboard/history", (HttpContext context) =>
                Results.Ok(provider.GetHistory(context.Request.Query["range"].FirstOrDefault())));
            api.MapGet("/api/dashboard/realm-activity", (HttpContext context) =>
                Results.Ok(provider.GetRealmActivity(context.Request.Query["range"].FirstOrDefault())));
            api.MapGet("/api/dashboard/class-history", (HttpContext context) =>
                Results.Ok(provider.GetClassHistory(context.Request.Query["range"].FirstOrDefault())));
            api.MapGet("/api/dashboard/herald", () => Results.Ok(provider.GetHerald()));
            api.MapGet("/api/dashboard/operator", () => Results.Ok(provider.GetOperatorStatus()));
            api.MapGet("/api/dashboard/dynamic-quests/difficulty", () =>
                Results.Ok(BuildDynamicQuestDifficultySnapshot(contentRoot)));
            api.MapGet("/api/dashboard/herald/character/{name}", (string name) =>
            {
                DashboardHeraldCharacterDetail detail = provider.GetHeraldCharacter(name);
                return detail == null ? Results.NotFound() : Results.Ok(detail);
            });
            api.MapGet("/api/dashboard/herald/guild/{name}", (string name) =>
            {
                DashboardHeraldGuildDetail detail = provider.GetHeraldGuild(name);
                return detail == null ? Results.NotFound() : Results.Ok(detail);
            });
            api.MapGet("/status/badge.png", (HttpContext context) =>
            {
                context.Response.Headers.CacheControl = "public, max-age=30";
                try
                {
                    return Results.File(DashboardBadgeRenderer.Render(provider.GetLive()), "image/png");
                }
                catch
                {
                    return Results.File(DashboardBadgeRenderer.Render(null, false), "image/png");
                }
            });
            api.MapGet("/api/status/summary", () => Results.Ok(provider.GetStatusSummary()));
            api.MapGet("/status", () =>
            {
                if (File.Exists(statusPath))
                    return Results.File(statusPath, "text/html");

                return Results.Redirect("/dashboard");
            });
        }

        internal static object BuildDynamicQuestDifficultySnapshotForTest(string contentRoot)
        {
            return BuildDynamicQuestDifficultySnapshot(contentRoot);
        }

        private static object BuildDynamicQuestDifficultySnapshot(string contentRoot)
        {
            List<string> roots = FindTestOutputRoots(contentRoot).ToList();
            List<FileInfo> metricFiles = roots
                .SelectMany(SafeEnumerateDynamicQuestMetricFiles)
                .OrderByDescending(file => file.LastWriteTimeUtc)
                .Take(40)
                .ToList();

            List<DynamicQuestDifficultyRun> runs = metricFiles
                .Select(ReadDynamicQuestDifficultyRun)
                .Where(run => run.Rows > 0)
                .OrderByDescending(run => run.UpdatedAt)
                .Take(20)
                .ToList();

            int rows = runs.Sum(run => run.Rows);
            int okRows = runs.Sum(run => run.OkRows);
            int completedRows = runs.Sum(run => run.CompletedRows);
            double elapsedSum = runs.Sum(run => run.ElapsedSecondsSum);
            int elapsedRows = runs.Sum(run => run.ElapsedRows);
            double combatSum = runs.Sum(run => run.CombatSecondsSum);
            int combatRows = runs.Sum(run => run.CombatRows);

            return new
            {
                updatedAt = DateTime.UtcNow,
                sourceRootCount = roots.Count,
                sourceFileCount = metricFiles.Count,
                rows,
                okRows,
                okRate = Rate(okRows, rows),
                completedRows,
                completionRate = Rate(completedRows, rows),
                deaths = runs.Sum(run => run.Deaths),
                targetRemoved = runs.Sum(run => run.TargetRemoved),
                targetTimeouts = runs.Sum(run => run.TargetTimeouts),
                movementFailures = runs.Sum(run => run.MovementFailures),
                avgElapsedSeconds = Average(elapsedSum, elapsedRows),
                avgCombatSeconds = Average(combatSum, combatRows),
                latestRuns = runs.Take(8).Select(run => new
                {
                    name = run.Name,
                    path = run.Path,
                    updatedAt = run.UpdatedAt,
                    rows = run.Rows,
                    okRows = run.OkRows,
                    okRate = Rate(run.OkRows, run.Rows),
                    completedRows = run.CompletedRows,
                    completionRate = Rate(run.CompletedRows, run.Rows),
                    deaths = run.Deaths,
                    targetRemoved = run.TargetRemoved,
                    targetTimeouts = run.TargetTimeouts,
                    movementFailures = run.MovementFailures,
                    avgElapsedSeconds = Average(run.ElapsedSecondsSum, run.ElapsedRows),
                    avgCombatSeconds = Average(run.CombatSecondsSum, run.CombatRows),
                    error = run.Error
                }).ToList()
            };
        }

        private static IEnumerable<string> FindTestOutputRoots(string contentRoot)
        {
            HashSet<string> roots = new(StringComparer.OrdinalIgnoreCase);
            DirectoryInfo current = new(string.IsNullOrWhiteSpace(contentRoot) ? Directory.GetCurrentDirectory() : contentRoot);

            for (int i = 0; current != null && i < 6; i++, current = current.Parent)
            {
                string testOutput = Path.Combine(current.FullName, "test-output");
                if (Directory.Exists(testOutput))
                    roots.Add(Path.GetFullPath(testOutput));

                string toolsTestOutput = Path.Combine(current.FullName, "tools", "test-output");
                if (Directory.Exists(toolsTestOutput))
                    roots.Add(Path.GetFullPath(toolsTestOutput));
            }

            return roots;
        }

        private static IEnumerable<FileInfo> SafeEnumerateFiles(string root, string pattern)
        {
            if (string.IsNullOrWhiteSpace(root) || !Directory.Exists(root))
                return Array.Empty<FileInfo>();

            try
            {
                return Directory.EnumerateFiles(root, pattern, SearchOption.AllDirectories)
                    .Select(path => new FileInfo(path))
                    .Where(file => file.Exists)
                    .ToList();
            }
            catch
            {
                return Array.Empty<FileInfo>();
            }
        }

        private static IEnumerable<FileInfo> SafeEnumerateDynamicQuestMetricFiles(string root)
        {
            if (string.IsNullOrWhiteSpace(root) || !Directory.Exists(root))
                return Array.Empty<FileInfo>();

            try
            {
                return Directory.EnumerateDirectories(root, "dynamic-quest*", SearchOption.TopDirectoryOnly)
                    .SelectMany(directory => SafeEnumerateFiles(directory, "metrics.csv"))
                    .ToList();
            }
            catch
            {
                return Array.Empty<FileInfo>();
            }
        }

        private static DynamicQuestDifficultyRun ReadDynamicQuestDifficultyRun(FileInfo file)
        {
            DynamicQuestDifficultyRun run = new()
            {
                Name = BuildRunName(file),
                Path = BuildRunPath(file),
                UpdatedAt = file.LastWriteTimeUtc
            };

            try
            {
                using StreamReader reader = file.OpenText();
                string headerLine = reader.ReadLine();
                if (string.IsNullOrWhiteSpace(headerLine))
                    return run;

                Dictionary<string, int> headers = SplitCsvLine(headerLine)
                    .Select((name, index) => new { name, index })
                    .Where(item => !string.IsNullOrWhiteSpace(item.name))
                    .GroupBy(item => item.name.Trim(), StringComparer.OrdinalIgnoreCase)
                    .ToDictionary(group => group.Key, group => group.First().index, StringComparer.OrdinalIgnoreCase);

                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    if (string.IsNullOrWhiteSpace(line))
                        continue;

                    List<string> values = SplitCsvLine(line);
                    run.Rows++;
                    if (ReadBool(values, headers, "ok"))
                        run.OkRows++;
                    if (LooksCompleted(values, headers))
                        run.CompletedRows++;

                    run.Deaths += ReadInt(values, headers, "player_deaths");
                    run.TargetRemoved += ReadInt(values, headers, "target_removed");
                    run.TargetTimeouts += ReadInt(values, headers, "target_timeouts");
                    run.MovementFailures += ReadInt(values, headers, "movement_failures");

                    double elapsed = ReadDouble(values, headers, "elapsed_seconds");
                    if (elapsed > 0)
                    {
                        run.ElapsedSecondsSum += elapsed;
                        run.ElapsedRows++;
                    }

                    double combat = ReadDouble(values, headers, "avg_combat_seconds");
                    if (combat > 0)
                    {
                        run.CombatSecondsSum += combat;
                        run.CombatRows++;
                    }

                    string error = ReadString(values, headers, "error");
                    if (!string.IsNullOrWhiteSpace(error) && string.IsNullOrWhiteSpace(run.Error))
                        run.Error = error.Trim();
                }
            }
            catch (Exception ex)
            {
                run.Error = ex.Message;
            }

            return run;
        }

        private static string BuildRunName(FileInfo file)
        {
            DirectoryInfo parent = file.Directory;
            if (parent == null)
                return file.Name;

            string leaf = parent.Name;
            string root = parent.Parent?.Name ?? string.Empty;
            return root.StartsWith("dynamic-quest", StringComparison.OrdinalIgnoreCase)
                ? $"{root}/{leaf}"
                : leaf;
        }

        private static string BuildRunPath(FileInfo file)
        {
            string fullPath = file.FullName.Replace('\\', '/');
            int index = fullPath.IndexOf("/test-output/", StringComparison.OrdinalIgnoreCase);
            return index >= 0 ? fullPath.Substring(index + 1) : file.FullName;
        }

        private static bool LooksCompleted(List<string> values, Dictionary<string, int> headers)
        {
            return ReadBool(values, headers, "ok") &&
                   (ReadInt(values, headers, "action_dynamic_quest_complete_verified") > 0 ||
                    ReadInt(values, headers, "action_dynamic_quest_final_inactive") > 0 ||
                    ReadInt(values, headers, "action_required_target_complete") > 0 ||
                    ReadInt(values, headers, "action_required_target_complete_exit") > 0 ||
                    ReadInt(values, headers, "action_required_target_complete_pending_safe_exit") > 0);
        }

        private static List<string> SplitCsvLine(string line)
        {
            List<string> values = new();
            if (line == null)
                return values;

            bool quoted = false;
            System.Text.StringBuilder builder = new();

            for (int i = 0; i < line.Length; i++)
            {
                char ch = line[i];
                if (ch == '"')
                {
                    if (quoted && i + 1 < line.Length && line[i + 1] == '"')
                    {
                        builder.Append('"');
                        i++;
                    }
                    else
                    {
                        quoted = !quoted;
                    }
                    continue;
                }

                if (ch == ',' && !quoted)
                {
                    values.Add(builder.ToString());
                    builder.Clear();
                    continue;
                }

                builder.Append(ch);
            }

            values.Add(builder.ToString());
            return values;
        }

        private static string ReadString(List<string> values, Dictionary<string, int> headers, string key)
        {
            return headers.TryGetValue(key, out int index) && index >= 0 && index < values.Count
                ? values[index]
                : string.Empty;
        }

        private static bool ReadBool(List<string> values, Dictionary<string, int> headers, string key)
        {
            string value = ReadString(values, headers, key).Trim();
            return string.Equals(value, "1", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "true", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "yes", StringComparison.OrdinalIgnoreCase);
        }

        private static int ReadInt(List<string> values, Dictionary<string, int> headers, string key)
        {
            return int.TryParse(ReadString(values, headers, key), NumberStyles.Integer, CultureInfo.InvariantCulture, out int value)
                ? Math.Max(0, value)
                : 0;
        }

        private static double ReadDouble(List<string> values, Dictionary<string, int> headers, string key)
        {
            return double.TryParse(ReadString(values, headers, key), NumberStyles.Float, CultureInfo.InvariantCulture, out double value)
                ? Math.Max(0, value)
                : 0;
        }

        private static double Average(double sum, int count)
        {
            return count <= 0 ? 0 : sum / count;
        }

        private static double Rate(int value, int total)
        {
            return total <= 0 ? 0 : (double)value / total;
        }

        private sealed class DynamicQuestDifficultyRun
        {
            public string Name { get; set; } = string.Empty;
            public string Path { get; set; } = string.Empty;
            public DateTime UpdatedAt { get; set; }
            public int Rows { get; set; }
            public int OkRows { get; set; }
            public int CompletedRows { get; set; }
            public int Deaths { get; set; }
            public int TargetRemoved { get; set; }
            public int TargetTimeouts { get; set; }
            public int MovementFailures { get; set; }
            public double ElapsedSecondsSum { get; set; }
            public int ElapsedRows { get; set; }
            public double CombatSecondsSum { get; set; }
            public int CombatRows { get; set; }
            public string Error { get; set; } = string.Empty;
        }
    }
}
