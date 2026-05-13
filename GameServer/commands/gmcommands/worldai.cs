using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;
using DOL.GS.ServerProperties;
using DOL.GS.WorldAI;

namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&worldai",
        ePrivLevel.GM,
        "World AI MVP controls.",
        "/worldai jobs",
        "/worldai jobs detail [all] [limit]",
        "/worldai seed bossborn",
        "/worldai see bossborn",
        "/worldai clearpreview",
        "/worldai processfake [count]",
        "/worldai processllm [count]",
        "/worldai llmcheck",
        "/worldai llmconfig",
        "/worldai health",
        "/worldai reclaim [minutes]",
        "/worldai cleanup bossborn",
        "/worldai approvals [limit]",
        "/worldai approve <eventId>",
        "/worldai retry <jobId>",
        "/worldai reject <jobId> [reason]")]
    public class WorldAiCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        private const int BossBornPreviewModel = 34;
        private const int BossBornPreviewPlayerOffset = 450;
        private static readonly object BossBornPreviewLock = new();
        private static GameNPC BossBornPreview;

        public void OnCommand(GameClient client, string[] args)
        {
            if (client.Player == null)
                return;

            if (args.Length < 2)
            {
                DisplayUsage(client);
                return;
            }

            switch (args[1].ToLowerInvariant())
            {
                case "jobs":
                    DisplayJobs(client, args);
                    return;
                case "seed":
                    Seed(client, args);
                    return;
                case "see":
                    See(client, args);
                    return;
                case "clearpreview":
                    ClearPreview(client);
                    return;
                case "processfake":
                    ProcessFake(client, args);
                    return;
                case "processllm":
                    ProcessLlm(client, args);
                    return;
                case "llmcheck":
                    CheckLlm(client);
                    return;
                case "llmconfig":
                    DisplayLlmConfig(client);
                    return;
                case "health":
                    DisplayHealth(client);
                    return;
                case "reclaim":
                    Reclaim(client, args);
                    return;
                case "cleanup":
                    Cleanup(client, args);
                    return;
                case "approvals":
                    DisplayApprovals(client, args);
                    return;
                case "approve":
                    Approve(client, args);
                    return;
                case "retry":
                    Retry(client, args);
                    return;
                case "reject":
                    Reject(client, args);
                    return;
                default:
                    DisplayUsage(client);
                    return;
            }
        }

        private void DisplayJobs(GameClient client, string[] args)
        {
            if (args.Length >= 3 && args[2].Equals("detail", StringComparison.OrdinalIgnoreCase))
            {
                DisplayJobDetails(client, args);
                return;
            }

            IDictionary<string, int> counts = LlmJobQueueService.Instance.CountByStatus();
            List<string> lines = new()
            {
                $"Pending: {GetCount(counts, WorldAiJobStatuses.Pending)}",
                $"Claimed: {GetCount(counts, WorldAiJobStatuses.Claimed)}",
                $"Completed: {GetCount(counts, WorldAiJobStatuses.Completed)}",
                $"Failed: {GetCount(counts, WorldAiJobStatuses.Failed)}",
                $"Rejected: {GetCount(counts, WorldAiJobStatuses.Rejected)}"
            };

            client.Out.SendCustomTextWindow("World AI Jobs", lines);
        }

        private void DisplayJobDetails(GameClient client, string[] args)
        {
            int limit = 20;
            bool includeClosed = false;

            for (int i = 3; i < args.Length; i++)
            {
                if (args[i].Equals("all", StringComparison.OrdinalIgnoreCase))
                    includeClosed = true;
                else
                    int.TryParse(args[i], out limit);
            }

            IEnumerable<LlmJobDetail> details = LlmJobQueueService.Instance.GetJobDetails(100);

            if (!includeClosed)
            {
                details = details.Where(detail =>
                    detail.Status != WorldAiJobStatuses.Completed &&
                    detail.Status != WorldAiJobStatuses.Rejected);
            }

            IList<LlmJobDetail> visibleDetails = details.Take(limit).ToList();
            List<string> lines = new();

            if (visibleDetails.Count == 0)
            {
                lines.Add(includeClosed
                    ? "LLM 작업이 없습니다."
                    : "표시할 활성 LLM 작업이 없습니다. 완료/거부 작업까지 보려면 /worldai jobs detail all");
            }
            else
            {
                foreach (LlmJobDetail detail in visibleDetails)
                {
                    string shortId = ShortId(detail.JobId);
                    string eventId = ShortId(detail.EventId);
                    string actor = string.IsNullOrWhiteSpace(detail.ActorName) ? "(unknown)" : detail.ActorName;
                    string region = string.IsNullOrWhiteSpace(detail.Region) ? "(unknown)" : detail.Region;
                    lines.Add($"{shortId} [{detail.Status}] {detail.JobType} attempts={detail.AttemptCount}");
                    lines.Add($"  event={eventId} {detail.EventType} / {actor} / {region}");

                    if (!string.IsNullOrWhiteSpace(detail.LastError))
                        lines.Add($"  error={detail.LastError}");
                }
            }

            client.Out.SendCustomTextWindow("World AI Job Details", lines);
        }

        private void Seed(GameClient client, string[] args)
        {
            if (args.Length < 3 || !args[2].Equals("bossborn", StringComparison.OrdinalIgnoreCase))
            {
                DisplayMessage(client, "사용법: /worldai seed bossborn");
                return;
            }

            WorldEventSeedResult result = WorldEventService.Instance.SeedBossBornSample();
            DisplayMessage(client, $"샘플 사건 생성: {result.Event.ActorName}, LLM 작업 {result.Jobs.Count}개 Pending.");
        }

        private void See(GameClient client, string[] args)
        {
            if (args.Length < 3 || !args[2].Equals("bossborn", StringComparison.OrdinalIgnoreCase))
            {
                DisplayMessage(client, "사용법: /worldai see bossborn");
                return;
            }

            if (!WorldEventService.Instance.TryGetLatestEventLocation(WorldAiEventTypes.BossBorn, out WorldEventLocation location))
            {
                WorldEventService.Instance.SeedBossBornSample();
                WorldEventService.Instance.TryGetLatestEventLocation(WorldAiEventTypes.BossBorn, out location);
            }

            if (location == null)
            {
                DisplayMessage(client, "bossborn 위치를 찾지 못했습니다.");
                return;
            }

            if (!EnsureBossBornPreview(location, out string previewError))
            {
                DisplayMessage(client, previewError);
                return;
            }

            int playerX = Math.Max(0, location.X - BossBornPreviewPlayerOffset);

            if (!client.Player.MoveTo(location.RegionId, playerX, location.Y, location.Z, location.Heading))
            {
                DisplayMessage(client, "bossborn 위치로 이동하지 못했습니다. 좌표 또는 지역을 확인하세요.");
                return;
            }

            DisplayMessage(client, $"bossborn 프리뷰 위치로 이동했습니다. 대상={GetBossBornPreviewName(location)} region={location.RegionId} x={location.X} y={location.Y} z={location.Z}");
        }

        private void ClearPreview(GameClient client)
        {
            bool cleared = ClearBossBornPreview();
            DisplayMessage(client, cleared ? "bossborn 프리뷰 NPC를 제거했습니다." : "제거할 bossborn 프리뷰 NPC가 없습니다.");
        }

        private void ProcessFake(GameClient client, string[] args)
        {
            int count = 10;

            if (args.Length >= 3)
                int.TryParse(args[2], out count);

            LlmJobProcessingSummary summary = LlmJobQueueService.Instance.ProcessFake(count);
            DisplayMessage(
                client,
                $"Fake 처리 완료: 처리 {summary.Processed}, 완료 {summary.Completed}, 거부 {summary.Rejected}, 실패 {summary.Failed}");
        }

        private void ProcessLlm(GameClient client, string[] args)
        {
            int count = 1;

            if (args.Length >= 3)
                int.TryParse(args[2], out count);

            try
            {
                OpenAiCompatibleLlmResultGenerator generator = new(
                    Properties.WORLDAI_LLM_API_URL,
                    Properties.WORLDAI_LLM_MODEL,
                    Properties.WORLDAI_LLM_TIMEOUT_SECONDS);
                LlmJobProcessingSummary summary = LlmJobQueueService.Instance.ProcessWithGenerator(count, generator);
                DisplayMessage(
                    client,
                    $"LLM 처리 완료: 처리 {summary.Processed}, 완료 {summary.Completed}, 거부 {summary.Rejected}, 실패 {summary.Failed}");
            }
            catch (Exception e)
            {
                DisplayMessage(client, $"LLM 처리 실패: {e.Message}");
            }
        }

        private void DisplayLlmConfig(GameClient client)
        {
            List<string> lines = new()
            {
                $"API URL: {Properties.WORLDAI_LLM_API_URL}",
                $"Model: {Properties.WORLDAI_LLM_MODEL}",
                $"Timeout: {Properties.WORLDAI_LLM_TIMEOUT_SECONDS}s",
                "연결 확인: /worldai llmcheck",
                "처리 명령: /worldai processllm [count]",
                "설정 변경 후 서버 프로퍼티를 refresh 하거나 서버를 재시작하세요."
            };

            client.Out.SendCustomTextWindow("World AI LLM Config", lines);
        }

        private void CheckLlm(GameClient client)
        {
            OpenAiCompatibleLlmResultGenerator generator = new(
                Properties.WORLDAI_LLM_API_URL,
                Properties.WORLDAI_LLM_MODEL,
                Properties.WORLDAI_LLM_TIMEOUT_SECONDS);
            LlmConnectionCheckResult result = generator.CheckConnection(Properties.WORLDAI_LLM_API_URL);

            List<string> lines = new()
            {
                result.IsAvailable ? "상태: 연결 가능" : "상태: 연결 실패",
                $"API URL: {result.ApiUrl}",
                $"Configured Model: {result.Model}"
            };

            if (result.IsAvailable)
            {
                lines.Add("Available Models:");

                foreach (string model in result.AvailableModels.Take(20))
                    lines.Add($"- {model}");

                if (!result.AvailableModels.Contains(result.Model, StringComparer.OrdinalIgnoreCase))
                    lines.Add("주의: 설정된 모델명이 목록에 없습니다.");
            }
            else
            {
                lines.Add($"Error: {result.Error}");
            }

            client.Out.SendCustomTextWindow("World AI LLM Check", lines);
        }

        private void DisplayHealth(GameClient client)
        {
            LlmQueueHealth health = LlmJobQueueService.Instance.GetQueueHealth();
            List<string> lines = new()
            {
                $"Active Jobs: {health.ActiveJobs}",
                $"Pending: {GetCount(health.Counts, WorldAiJobStatuses.Pending)}",
                $"Claimed: {GetCount(health.Counts, WorldAiJobStatuses.Claimed)}",
                $"Failed: {GetCount(health.Counts, WorldAiJobStatuses.Failed)}",
                $"Completed: {GetCount(health.Counts, WorldAiJobStatuses.Completed)}",
                $"Rejected: {GetCount(health.Counts, WorldAiJobStatuses.Rejected)}",
                $"Oldest Pending: {health.OldestPendingAgeSeconds}s",
                $"Oldest Claimed: {health.OldestClaimedAgeSeconds}s",
                "Stuck 작업 회수: /worldai reclaim [minutes]"
            };

            client.Out.SendCustomTextWindow("World AI Health", lines);
        }

        private void Reclaim(GameClient client, string[] args)
        {
            int minutes = 15;

            if (args.Length >= 3)
                int.TryParse(args[2], out minutes);

            int reclaimed = LlmJobQueueService.Instance.ReclaimStaleClaimedJobs(minutes);
            DisplayMessage(client, $"Claimed 상태로 멈춘 작업 회수 완료: {reclaimed}개 Pending 복귀.");
        }

        private void Cleanup(GameClient client, string[] args)
        {
            if (args.Length < 3 || !args[2].Equals("bossborn", StringComparison.OrdinalIgnoreCase))
            {
                DisplayMessage(client, "사용법: /worldai cleanup bossborn");
                return;
            }

            int rejected = WorldEventService.Instance.RejectDuplicateBossBornSampleJobs();
            DisplayMessage(client, $"bossborn 중복 작업 정리 완료: {rejected}개 작업을 Rejected 처리했습니다.");
        }

        private void DisplayApprovals(GameClient client, string[] args)
        {
            int limit = 20;

            if (args.Length >= 3)
                int.TryParse(args[2], out limit);

            IList<DbWorldEventLog> approvals = WorldEventService.Instance.GetPendingApprovalEvents(limit);
            List<string> lines = new();

            if (approvals.Count == 0)
            {
                lines.Add("승인 대기 중인 월드AI 공개문이 없습니다.");
            }
            else
            {
                foreach (DbWorldEventLog approval in approvals)
                {
                    string shortId = approval.EventId.Length > 8 ? approval.EventId.Substring(0, 8) : approval.EventId;
                    string title = string.IsNullOrWhiteSpace(approval.PublicTitle) ? approval.ActorName : approval.PublicTitle;
                    lines.Add($"{shortId} [{approval.Importance}] {title}");
                    lines.Add(approval.PublicText);
                    lines.Add(string.Empty);
                }
            }

            client.Out.SendCustomTextWindow("World AI Approvals", lines);
        }

        private void Approve(GameClient client, string[] args)
        {
            if (args.Length < 3)
            {
                DisplayMessage(client, "사용법: /worldai approve <eventId>");
                return;
            }

            bool approved = WorldEventService.Instance.ApprovePublicEvent(args[2]);
            DisplayMessage(client, approved ? "월드AI 공개문을 승인했습니다." : "승인할 월드AI 공개문을 찾지 못했습니다.");
        }

        private void Retry(GameClient client, string[] args)
        {
            if (args.Length < 3)
            {
                DisplayMessage(client, "사용법: /worldai retry <jobId>");
                return;
            }

            LlmJobSubmissionResult result = LlmJobQueueService.Instance.RetryJob(args[2]);
            DisplayMessage(client, result.Accepted ? $"작업을 Pending으로 되돌렸습니다: {ShortId(result.JobId)}" : result.Message);
        }

        private void Reject(GameClient client, string[] args)
        {
            if (args.Length < 3)
            {
                DisplayMessage(client, "사용법: /worldai reject <jobId> [reason]");
                return;
            }

            string reason = args.Length >= 4 ? string.Join(" ", args, 3, args.Length - 3) : "Rejected by GM.";
            LlmJobSubmissionResult result = LlmJobQueueService.Instance.RejectJob(args[2], reason);
            DisplayMessage(client, result.Accepted ? $"작업을 Rejected로 변경했습니다: {ShortId(result.JobId)}" : result.Message);
        }

        private void DisplayUsage(GameClient client)
        {
            List<string> lines = new()
            {
                "/worldai jobs",
                "/worldai jobs detail [all] [limit]",
                "/worldai seed bossborn",
                "/worldai see bossborn",
                "/worldai clearpreview",
                "/worldai processfake [count]",
                "/worldai processllm [count]",
                "/worldai llmcheck",
                "/worldai llmconfig",
                "/worldai health",
                "/worldai reclaim [minutes]",
                "/worldai cleanup bossborn",
                "/worldai approvals [limit]",
                "/worldai approve <eventId>",
                "/worldai retry <jobId>",
                "/worldai reject <jobId> [reason]"
            };

            client.Out.SendCustomTextWindow("World AI", lines);
        }

        private static int GetCount(IDictionary<string, int> counts, string status)
        {
            return counts.TryGetValue(status, out int value) ? value : 0;
        }

        private static bool EnsureBossBornPreview(WorldEventLocation location, out string error)
        {
            error = string.Empty;

            if (location == null)
            {
                error = "bossborn 위치 정보가 비어 있습니다.";
                return false;
            }

            lock (BossBornPreviewLock)
            {
                if (BossBornPreview != null && BossBornPreview.ObjectState == GameObject.eObjectState.Active)
                    BossBornPreview.Delete();

                GameNPC preview = new()
                {
                    Name = GetBossBornPreviewName(location),
                    GuildName = "WorldAI bossborn preview",
                    Model = BossBornPreviewModel,
                    Level = 50,
                    Realm = eRealm.None,
                    Size = 75,
                    Flags = GameNPC.eFlags.PEACE
                };

                if (!preview.Create(location.RegionId, location.X, location.Y, location.Z, location.Heading))
                {
                    error = "bossborn 프리뷰 NPC를 생성하지 못했습니다. 좌표 또는 지역을 확인하세요.";
                    return false;
                }

                BossBornPreview = preview;
                return true;
            }
        }

        private static bool ClearBossBornPreview()
        {
            lock (BossBornPreviewLock)
            {
                if (BossBornPreview == null || BossBornPreview.ObjectState != GameObject.eObjectState.Active)
                {
                    BossBornPreview = null;
                    return false;
                }

                BossBornPreview.Delete();
                BossBornPreview = null;
                return true;
            }
        }

        private static string GetBossBornPreviewName(WorldEventLocation location)
        {
            return string.IsNullOrWhiteSpace(location?.ActorName) ? "붉은 송곳니 그락" : location.ActorName;
        }

        private static string ShortId(string id)
        {
            if (string.IsNullOrWhiteSpace(id))
                return "(none)";

            return id.Length > 8 ? id.Substring(0, 8) : id;
        }
    }
}
