using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using DOL.Database;
using DOL.GS.ServerProperties;

namespace DOL.GS.LiveCompanion
{
    public static class CompanionRequestStatus
    {
        public const string Queued = "queued";
        public const string Spawning = "spawning";
        public const string Grouping = "grouping";
        public const string Active = "active";
        public const string Leaving = "leaving";
        public const string Failed = "failed";
        public const string Completed = "completed";
        public const string Canceled = "canceled";

        private static readonly HashSet<string> ValidStatuses = new(StringComparer.OrdinalIgnoreCase)
        {
            Queued,
            Spawning,
            Grouping,
            Active,
            Leaving,
            Failed,
            Completed,
            Canceled
        };

        public static bool IsValid(string status) => ValidStatuses.Contains(Normalize(status));

        public static string Normalize(string status)
        {
            string normalized = (status ?? string.Empty).Trim().ToLowerInvariant();
            return string.IsNullOrEmpty(normalized) ? Queued : normalized;
        }
    }

    public static class CompanionRequestRoles
    {
        public const string Fill = "fill";
        public const string Healer = "healer";
        public const string Tank = "tank";
        public const string Dps = "dps";
        public const string Support = "support";

        private static readonly HashSet<string> ValidRoles = new(StringComparer.OrdinalIgnoreCase)
        {
            Fill,
            Healer,
            Tank,
            Dps,
            Support
        };

        public static bool IsValid(string role) => ValidRoles.Contains(Normalize(role));

        public static string Normalize(string role)
        {
            string normalized = (role ?? string.Empty).Trim().ToLowerInvariant();
            return string.IsNullOrEmpty(normalized) ? Fill : normalized;
        }
    }

    public static class CompanionContractTiers
    {
        public const string Common = "common";
        public const string Skilled = "skilled";
        public const string Elite = "elite";
        public const string Legendary = "legendary";

        private static readonly HashSet<string> ValidTiers = new(StringComparer.OrdinalIgnoreCase)
        {
            Common,
            Skilled,
            Elite,
            Legendary
        };

        public static string Normalize(string tier)
        {
            string normalized = (tier ?? string.Empty).Trim().ToLowerInvariant();
            return ValidTiers.Contains(normalized) ? normalized : Common;
        }

        public static int ContractDurationSeconds(string tier)
        {
            return Normalize(tier) switch
            {
                Skilled => 45 * 60,
                Elite => 60 * 60,
                Legendary => 90 * 60,
                _ => 30 * 60
            };
        }

        public static int OfflineGraceSeconds(string tier)
        {
            return Normalize(tier) switch
            {
                Skilled => 5 * 60,
                Elite => 7 * 60,
                Legendary => 10 * 60,
                _ => 3 * 60
            };
        }
    }

    public sealed class CompanionRequest
    {
        public string Id { get; set; } = string.Empty;
        public DateTime CreatedUtc { get; set; }
        public DateTime UpdatedUtc { get; set; }
        public string Status { get; set; } = CompanionRequestStatus.Queued;
        public string Source { get; set; } = string.Empty;
        public string RequestedRole { get; set; } = CompanionRequestRoles.Fill;
        public string RequestedCapabilities { get; set; } = string.Empty;
        public string ContractTier { get; set; } = CompanionContractTiers.Common;
        public int ContractDurationSeconds { get; set; }
        public int OfflineGraceSeconds { get; set; }
        public DateTime ContractStartedUtc { get; set; }
        public string MercenaryId { get; set; } = string.Empty;
        public string MercenaryName { get; set; } = string.Empty;
        public string MercenaryClassName { get; set; } = string.Empty;
        public string MercenaryPersonality { get; set; } = string.Empty;
        public string MercenaryTraits { get; set; } = string.Empty;
        public string MercenaryItemProfile { get; set; } = string.Empty;
        public string MercenaryBackground { get; set; } = string.Empty;
        public string MercenaryTacticPreset { get; set; } = "balanced";
        public int MercenaryTrust { get; set; } = 50;
        public int MercenaryFatigue { get; set; }
        public string MercenaryAdventureMemory { get; set; } = string.Empty;
        public string MercenaryRumorHint { get; set; } = string.Empty;
        public int MercenaryTotalContracts { get; set; }
        public int MercenaryTotalContractMinutes { get; set; }
        public int MercenaryKillsTogether { get; set; }
        public int MercenaryDeathsTogether { get; set; }
        public int MercenaryRevivesReceived { get; set; }
        public int MercenaryRescues { get; set; }
        public int MercenaryQuestsCompleted { get; set; }
        public string MercenaryEarnedTitles { get; set; } = string.Empty;
        public string MercenaryPersonalQuestState { get; set; } = string.Empty;
        public string MercenaryRelationshipEventState { get; set; } = string.Empty;
        public DateTime MercenaryLastHiredAt { get; set; }
        public string ContentType { get; set; } = "pve";
        public string ObjectiveTarget { get; set; } = string.Empty;
        public string RequesterName { get; set; } = string.Empty;
        public string RequesterAccount { get; set; } = string.Empty;
        public int Realm { get; set; }
        public ushort Region { get; set; }
        public int X { get; set; }
        public int Y { get; set; }
        public int Z { get; set; }
        public string GroupId { get; set; } = string.Empty;
        public int GroupSize { get; set; }
        public int VacantSlots { get; set; }
        public string CreatedBy { get; set; } = string.Empty;
        public string AssignedCompanionName { get; set; } = string.Empty;
        public string Message { get; set; } = string.Empty;
        public string CloseReason { get; set; } = string.Empty;
        public long SuppressedRealmPoints { get; set; }
        public long SuppressedBountyPoints { get; set; }
        public long SuppressedMoney { get; set; }
        public long SuppressedKillCredits { get; set; }
    }

    public sealed class CompanionRequestResult
    {
        public bool Success { get; set; }
        public string Message { get; set; } = string.Empty;
        public CompanionRequest Request { get; set; }
    }

    public sealed class CompanionRequestSummary
    {
        public int Total { get; set; }
        public int OpenCount { get; set; }
        public int ActiveCount { get; set; }
        public IDictionary<string, int> StatusCounts { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IList<CompanionRequest> ActiveRequests { get; set; } = new List<CompanionRequest>();
        public IList<CompanionRequest> OpenRequests { get; set; } = new List<CompanionRequest>();
        public IList<CompanionRequest> RecentRequests { get; set; } = new List<CompanionRequest>();
    }

    public sealed class CompanionRequestDisplaySummary
    {
        public string StatusLabel { get; set; } = string.Empty;
        public string RoleLabel { get; set; } = string.Empty;
        public string TierLabel { get; set; } = string.Empty;
        public string CompanionName { get; set; } = string.Empty;
        public string MercenaryLine { get; set; } = string.Empty;
        public string ContractLine { get; set; } = string.Empty;
        public string PartyLine { get; set; } = string.Empty;
        public string ProgressLine { get; set; } = string.Empty;
        public string ResultLine { get; set; } = string.Empty;
        public string RecoveryLine { get; set; } = string.Empty;
        public string MessageLine { get; set; } = string.Empty;
        public IList<string> Lines { get; set; } = new List<string>();
    }

    public static class CompanionRequestService
    {
        private const int MaxStoredRequests = 500;
        private static readonly TimeSpan StaleOpenRequestTimeout = TimeSpan.FromMinutes(10);
        private static readonly TimeSpan ActiveCompanionLeaseTimeout = TimeSpan.FromMinutes(5);
        private static readonly object Sync = new();
        private static readonly List<CompanionRequest> Requests = new();
        private static readonly HashSet<string> SlotHoldingStatuses = new(StringComparer.OrdinalIgnoreCase)
        {
            CompanionRequestStatus.Queued,
            CompanionRequestStatus.Spawning,
            CompanionRequestStatus.Grouping,
            CompanionRequestStatus.Active
        };
        private static readonly HashSet<string> ExpirableOpenStatuses = new(StringComparer.OrdinalIgnoreCase)
        {
            CompanionRequestStatus.Queued,
            CompanionRequestStatus.Spawning,
            CompanionRequestStatus.Grouping
        };
        private static readonly HashSet<string> TerminalStatuses = new(StringComparer.OrdinalIgnoreCase)
        {
            CompanionRequestStatus.Failed,
            CompanionRequestStatus.Completed,
            CompanionRequestStatus.Canceled
        };
        private static readonly HashSet<string> CancelableStatuses = new(StringComparer.OrdinalIgnoreCase)
        {
            CompanionRequestStatus.Queued,
            CompanionRequestStatus.Spawning,
            CompanionRequestStatus.Grouping
        };

        public static CompanionRequestResult CreateRequest(
            GamePlayer requester,
            string requestedRole,
            string source,
            string contentType,
            string createdBy,
            ushort objectiveRegion = 0,
            int objectiveX = 0,
            int objectiveY = 0,
            int objectiveZ = 0,
            string requestedCapabilities = "",
            string objectiveTarget = "",
            string contractTier = "",
            DbPlayerMercenary ownedMercenary = null)
        {
            if (requester == null)
            {
                return new CompanionRequestResult
                {
                    Success = false,
                    Message = "요청할 플레이어를 찾을 수 없습니다."
                };
            }

            string normalizedRole = CompanionRequestRoles.Normalize(requestedRole);
            if (!CompanionRequestRoles.IsValid(normalizedRole))
            {
                return new CompanionRequestResult
                {
                    Success = false,
                    Message = "역할은 fill, healer, tank, dps, support 중 하나여야 합니다."
                };
            }

            int groupSize = CurrentGroupSize(requester);
            int vacantSlots = VacantSlots(requester);
            lock (Sync)
            {
                ExpireStaleOpenRequestsLocked(DateTime.UtcNow);
                int reservedSlots = OpenRequestCountForRequesterLocked(requester);
                int availableSlots = Math.Max(0, vacantSlots - reservedSlots);
                CompanionRequest request = BuildRequest(
                    requester,
                    normalizedRole,
                    source,
                    contentType,
                    createdBy,
                    groupSize,
                    availableSlots,
                    objectiveRegion,
                    objectiveX,
                    objectiveY,
                    objectiveZ,
                    requestedCapabilities,
                    objectiveTarget,
                    contractTier,
                    ownedMercenary);

                if (availableSlots <= 0)
                {
                    request.Status = CompanionRequestStatus.Failed;
                    request.Message = "파티가 가득 차 용병을 부를 수 없습니다.";
                    AddRequestLocked(request);
                    return new CompanionRequestResult { Success = false, Message = request.Message, Request = request };
                }

                request.Message = "용병 요청이 접수되었습니다.";
                AddRequestLocked(request);
                return new CompanionRequestResult { Success = true, Message = request.Message, Request = request };
            }
        }

        public static CompanionRequestResult CreateOwnedMercenaryRequest(
            GamePlayer requester,
            string mercenaryIdOrName,
            string source,
            string contentType,
            string createdBy,
            ushort objectiveRegion = 0,
            int objectiveX = 0,
            int objectiveY = 0,
            int objectiveZ = 0,
            string objectiveTarget = "")
        {
            DbPlayerMercenary mercenary = PlayerMercenaryService.GetOwned(requester, mercenaryIdOrName);
            if (mercenary == null)
            {
                return new CompanionRequestResult
                {
                    Success = false,
                    Message = "보유한 용병을 찾을 수 없습니다."
                };
            }

            CompanionRequestResult result = CreateRequest(
                requester,
                mercenary.Role,
                source,
                contentType,
                createdBy,
                objectiveRegion,
                objectiveX,
                objectiveY,
                objectiveZ,
                mercenary.Capabilities,
                objectiveTarget,
                mercenary.ContractTier,
                mercenary);
            if (result.Success)
            {
                PlayerMercenaryService.RecordContractStarted(mercenary);
                ApplyMercenaryProgressionSnapshot(result.Request, mercenary);
            }

            return result;
        }

        public static CompanionRequestResult RequestLeave(GamePlayer requester, string source, string createdBy)
        {
            if (requester == null)
            {
                return new CompanionRequestResult
                {
                    Success = false,
                    Message = "요청할 플레이어를 찾을 수 없습니다."
                };
            }

            lock (Sync)
            {
                CancelPendingRequestsLocked(
                    requester.Client?.Account?.Name ?? string.Empty,
                    requester.Name,
                    "leave_requested",
                    "용병 해산으로 대기 중인 요청을 취소했습니다.");

                CompanionRequest request = BuildRequest(
                    requester,
                    "leave",
                    source,
                    "control",
                    createdBy,
                    CurrentGroupSize(requester),
                    VacantSlots(requester));
                request.Status = CompanionRequestStatus.Leaving;
                request.Message = "용병 해산 요청이 접수되었습니다.";
                AddRequestLocked(request);

                return new CompanionRequestResult { Success = true, Message = request.Message, Request = Clone(request) };
            }
        }

        public static CompanionRequestResult CancelPendingRequests(GamePlayer requester, string source, string createdBy)
        {
            if (requester == null)
            {
                return new CompanionRequestResult
                {
                    Success = false,
                    Message = "요청할 플레이어를 찾을 수 없습니다."
                };
            }

            lock (Sync)
            {
                int canceled = CancelPendingRequestsLocked(
                    requester.Client?.Account?.Name ?? string.Empty,
                    requester.Name,
                    "request_canceled",
                    "용병 요청이 취소되었습니다.");

                CompanionRequest latest = LatestForPlayerLocked(requester.Name);
                string message = canceled > 0
                    ? $"대기 중인 용병 요청 {canceled}건을 취소했습니다."
                    : "취소할 대기 중인 용병 요청이 없습니다.";
                return new CompanionRequestResult
                {
                    Success = canceled > 0,
                    Message = message,
                    Request = latest == null ? null : Clone(latest)
                };
            }
        }

        public static CompanionRequest CancelRequest(string id, string reason, string message)
        {
            if (string.IsNullOrWhiteSpace(id))
                return null;

            lock (Sync)
            {
                CompanionRequest request = Requests.FirstOrDefault(row => row.Id.Equals(id, StringComparison.OrdinalIgnoreCase));
                if (request == null || !CancelableStatuses.Contains(request.Status))
                    return null;

                request.Status = CompanionRequestStatus.Canceled;
                request.CloseReason = string.IsNullOrWhiteSpace(reason) ? "request_canceled" : reason.Trim();
                request.Message = string.IsNullOrWhiteSpace(message) ? "용병 요청이 취소되었습니다." : message.Trim();
                request.UpdatedUtc = DateTime.UtcNow;
                return Clone(request);
            }
        }

        public static IList<CompanionRequest> Snapshot(string status = "", int limit = 100)
        {
            string normalizedStatus = CompanionRequestStatus.Normalize(status);

            lock (Sync)
            {
                ExpireStaleOpenRequestsLocked(DateTime.UtcNow);
                IEnumerable<CompanionRequest> rows = Requests
                    .OrderByDescending(request => request.CreatedUtc);

                if (!string.IsNullOrWhiteSpace(status))
                    rows = rows.Where(request => request.Status.Equals(normalizedStatus, StringComparison.OrdinalIgnoreCase));

                return rows.Take(Math.Clamp(limit, 1, MaxStoredRequests)).Select(Clone).ToList();
            }
        }

        public static CompanionRequestSummary Summary(int limit = 20)
        {
            int boundedLimit = Math.Clamp(limit, 1, MaxStoredRequests);
            lock (Sync)
            {
                ExpireStaleOpenRequestsLocked(DateTime.UtcNow);
                List<CompanionRequest> ordered = Requests
                    .OrderByDescending(request => request.UpdatedUtc == default ? request.CreatedUtc : request.UpdatedUtc)
                    .ToList();
                List<CompanionRequest> active = ordered
                    .Where(request => request.Status.Equals(CompanionRequestStatus.Active, StringComparison.OrdinalIgnoreCase))
                    .Take(boundedLimit)
                    .Select(Clone)
                    .ToList();
                List<CompanionRequest> open = ordered
                    .Where(request => SlotHoldingStatuses.Contains(request.Status) ||
                                      request.Status.Equals(CompanionRequestStatus.Leaving, StringComparison.OrdinalIgnoreCase))
                    .Take(boundedLimit)
                    .Select(Clone)
                    .ToList();

                return new CompanionRequestSummary
                {
                    Total = Requests.Count,
                    OpenCount = ordered.Count(request => SlotHoldingStatuses.Contains(request.Status) ||
                                                         request.Status.Equals(CompanionRequestStatus.Leaving, StringComparison.OrdinalIgnoreCase)),
                    ActiveCount = ordered.Count(request => request.Status.Equals(CompanionRequestStatus.Active, StringComparison.OrdinalIgnoreCase)),
                    StatusCounts = ordered
                        .GroupBy(request => CompanionRequestStatus.Normalize(request.Status), StringComparer.OrdinalIgnoreCase)
                        .ToDictionary(group => group.Key, group => group.Count(), StringComparer.OrdinalIgnoreCase),
                    ActiveRequests = active,
                    OpenRequests = open,
                    RecentRequests = ordered.Take(boundedLimit).Select(Clone).ToList()
                };
            }
        }

        public static CompanionRequest Get(string id)
        {
            if (string.IsNullOrWhiteSpace(id))
                return null;

            lock (Sync)
            {
                ExpireStaleOpenRequestsLocked(DateTime.UtcNow);
                CompanionRequest request = Requests.FirstOrDefault(row => row.Id.Equals(id, StringComparison.OrdinalIgnoreCase));
                return request == null ? null : Clone(request);
            }
        }

        public static CompanionRequestDisplaySummary BuildDisplaySummary(CompanionRequest request, DateTime? nowUtc = null)
        {
            if (request == null)
                return new CompanionRequestDisplaySummary
                {
                    StatusLabel = "요청 없음",
                    Lines = new List<string> { "아직 접수된 용병 요청이 없습니다." }
                };

            DateTime now = nowUtc ?? DateTime.UtcNow;
            string companionName = FirstNonEmpty(request.AssignedCompanionName, request.MercenaryName, "배정 대기");
            CompanionRequestDisplaySummary summary = new()
            {
                StatusLabel = StatusLabel(request.Status),
                RoleLabel = RoleLabel(request.RequestedRole),
                TierLabel = TierLabel(request.ContractTier),
                CompanionName = companionName,
                MercenaryLine = BuildMercenaryLine(request),
                ContractLine = BuildContractLine(request, now),
                PartyLine = $"파티: 요청 시 {request.GroupSize}명, 빈자리 {request.VacantSlots}칸",
                ProgressLine = BuildProgressLine(request),
                ResultLine = BuildResultLine(request),
                RecoveryLine = BuildRecoveryLine(request),
                MessageLine = string.IsNullOrWhiteSpace(request.Message) ? "" : $"최근 메시지: {request.Message.Trim()}"
            };

            List<string> lines = new()
            {
                $"상태: {summary.StatusLabel}",
                $"역할: {summary.RoleLabel} / 등급: {summary.TierLabel}",
                $"용병: {summary.CompanionName}"
            };

            AddIfPresent(lines, summary.MercenaryLine);
            AddIfPresent(lines, BuildMercenaryProgressLine(request));
            AddIfPresent(lines, summary.ContractLine);
            AddIfPresent(lines, summary.PartyLine);
            AddIfPresent(lines, summary.ProgressLine);
            AddIfPresent(lines, summary.ResultLine);
            AddIfPresent(lines, summary.RecoveryLine);
            AddIfPresent(lines, summary.MessageLine);
            summary.Lines = lines;
            return summary;
        }

        public static CompanionRequest LatestForPlayer(string playerName)
        {
            if (string.IsNullOrWhiteSpace(playerName))
                return null;

            lock (Sync)
            {
                ExpireStaleOpenRequestsLocked(DateTime.UtcNow);
                CompanionRequest request = LatestForPlayerLocked(playerName);
                return request == null ? null : Clone(request);
            }
        }

        public static string ActiveCompanionRoleFor(string companionName)
        {
            if (string.IsNullOrWhiteSpace(companionName))
                return string.Empty;

            lock (Sync)
            {
                ExpireStaleOpenRequestsLocked(DateTime.UtcNow);
                CompanionRequest request = Requests
                    .Where(row => row.Status.Equals(CompanionRequestStatus.Active, StringComparison.OrdinalIgnoreCase))
                    .Where(row => row.AssignedCompanionName.Equals(companionName, StringComparison.OrdinalIgnoreCase))
                    .OrderByDescending(row => row.UpdatedUtc)
                    .FirstOrDefault();

                return request == null ? string.Empty : request.RequestedRole;
            }
        }

        public static bool IsActiveCompanion(string companionName)
        {
            return !string.IsNullOrWhiteSpace(ActiveCompanionRoleFor(companionName));
        }

        public static bool RecordSuppressedReward(string companionName, string rewardType, long amount)
        {
            if (string.IsNullOrWhiteSpace(companionName))
                return false;

            lock (Sync)
            {
                ExpireStaleOpenRequestsLocked(DateTime.UtcNow);
                CompanionRequest request = Requests
                    .Where(row => row.Status.Equals(CompanionRequestStatus.Active, StringComparison.OrdinalIgnoreCase))
                    .Where(row => row.AssignedCompanionName.Equals(companionName, StringComparison.OrdinalIgnoreCase))
                    .OrderByDescending(row => row.UpdatedUtc)
                    .FirstOrDefault();
                if (request == null)
                    return false;

                long clampedAmount = Math.Max(0, amount);
                switch ((rewardType ?? string.Empty).Trim().ToLowerInvariant())
                {
                    case "realm_points":
                        request.SuppressedRealmPoints += clampedAmount;
                        break;
                    case "bounty_points":
                        request.SuppressedBountyPoints += clampedAmount;
                        break;
                    case "money":
                        request.SuppressedMoney += clampedAmount;
                        break;
                    case "rvr_kill_credit":
                        request.SuppressedKillCredits += clampedAmount;
                        break;
                }

                request.Message = $"용병 보상 제한 기록: {rewardType} {clampedAmount}";
                request.UpdatedUtc = DateTime.UtcNow;
                return true;
            }
        }

        public static CompanionRequest ClaimNextQueued()
        {
            lock (Sync)
            {
                ExpireStaleOpenRequestsLocked(DateTime.UtcNow);
                CompanionRequest request = Requests
                    .Where(row => row.Status.Equals(CompanionRequestStatus.Queued, StringComparison.OrdinalIgnoreCase) ||
                                  row.Status.Equals(CompanionRequestStatus.Leaving, StringComparison.OrdinalIgnoreCase))
                    .OrderBy(row => row.CreatedUtc)
                    .FirstOrDefault();

                if (request == null)
                    return null;

                if (request.Status.Equals(CompanionRequestStatus.Queued, StringComparison.OrdinalIgnoreCase))
                    request.Status = CompanionRequestStatus.Spawning;
                request.UpdatedUtc = DateTime.UtcNow;
                request.Message = request.Status.Equals(CompanionRequestStatus.Leaving, StringComparison.OrdinalIgnoreCase)
                    ? "용병 서비스가 해산 요청을 처리 중입니다."
                    : "용병 서비스가 요청을 처리 중입니다.";
                return Clone(request);
            }
        }

        public static CompanionRequest UpdateStatus(
            string id,
            string status,
            string message,
            string assignedCompanionName,
            string closeReason = "")
        {
            if (string.IsNullOrWhiteSpace(status))
                return null;

            string normalizedStatus = CompanionRequestStatus.Normalize(status);
            if (!CompanionRequestStatus.IsValid(normalizedStatus))
                return null;

            lock (Sync)
            {
                CompanionRequest request = Requests.FirstOrDefault(row => row.Id.Equals(id ?? string.Empty, StringComparison.OrdinalIgnoreCase));
                if (request == null)
                    return null;
                if (!CanTransitionStatus(request.Status, normalizedStatus))
                    return null;

                string previousStatus = request.Status;
                request.Status = normalizedStatus;
                request.UpdatedUtc = DateTime.UtcNow;
                if (!string.IsNullOrWhiteSpace(message))
                    request.Message = message.Trim();
                if (!string.IsNullOrWhiteSpace(assignedCompanionName))
                    request.AssignedCompanionName = assignedCompanionName.Trim();
                if (!string.IsNullOrWhiteSpace(closeReason))
                    request.CloseReason = closeReason.Trim();
                if (normalizedStatus.Equals(CompanionRequestStatus.Active, StringComparison.OrdinalIgnoreCase) &&
                    request.ContractStartedUtc == default)
                    request.ContractStartedUtc = DateTime.UtcNow;
                if (TerminalStatuses.Contains(normalizedStatus) && !TerminalStatuses.Contains(previousStatus))
                    ApplyMercenaryContractOutcome(request, normalizedStatus, previousStatus);

                return Clone(request);
            }
        }

        public static int VacantSlots(GamePlayer player)
        {
            int maxMembers = Math.Max(1, Properties.GROUP_MAX_MEMBER);
            return Math.Max(0, maxMembers - CurrentGroupSize(player));
        }

        public static int CurrentGroupSize(GamePlayer player)
        {
            if (player == null)
                return 0;

            return player.Group == null ? 1 : Math.Max(1, (int) player.Group.MemberCount);
        }

        private static CompanionRequest BuildRequest(
            GamePlayer requester,
            string requestedRole,
            string source,
            string contentType,
            string createdBy,
            int groupSize,
            int vacantSlots,
            ushort objectiveRegion = 0,
            int objectiveX = 0,
            int objectiveY = 0,
            int objectiveZ = 0,
            string requestedCapabilities = "",
            string objectiveTarget = "",
            string contractTier = "",
            DbPlayerMercenary ownedMercenary = null)
        {
            DateTime now = DateTime.UtcNow;
            bool hasObjectiveLocation = objectiveX != 0 || objectiveY != 0 || objectiveZ != 0;
            ushort requestRegion = objectiveRegion > 0 ? objectiveRegion : requester.CurrentRegionID;
            string normalizedTier = CompanionContractTiers.Normalize(contractTier);
            return new CompanionRequest
            {
                Id = Guid.NewGuid().ToString("N"),
                CreatedUtc = now,
                UpdatedUtc = now,
                Status = CompanionRequestStatus.Queued,
                Source = string.IsNullOrWhiteSpace(source) ? "unknown" : source.Trim(),
                RequestedRole = requestedRole,
                RequestedCapabilities = string.IsNullOrWhiteSpace(requestedCapabilities) ? string.Empty : requestedCapabilities.Trim().ToLowerInvariant(),
                ContractTier = normalizedTier,
                ContractDurationSeconds = CompanionContractTiers.ContractDurationSeconds(normalizedTier),
                OfflineGraceSeconds = CompanionContractTiers.OfflineGraceSeconds(normalizedTier),
                MercenaryId = ownedMercenary?.MercenaryId ?? string.Empty,
                MercenaryName = ownedMercenary?.DisplayName ?? string.Empty,
                MercenaryClassName = ownedMercenary?.ClassName ?? string.Empty,
                MercenaryPersonality = ownedMercenary?.Personality ?? string.Empty,
                MercenaryTraits = ownedMercenary?.Traits ?? string.Empty,
                MercenaryItemProfile = ownedMercenary?.ItemProfile ?? string.Empty,
                MercenaryBackground = ownedMercenary?.Background ?? string.Empty,
                MercenaryTacticPreset = ownedMercenary?.TacticPreset ?? "balanced",
                MercenaryTrust = ownedMercenary?.Trust ?? 50,
                MercenaryFatigue = ownedMercenary?.Fatigue ?? 0,
                MercenaryAdventureMemory = ownedMercenary?.AdventureMemory ?? string.Empty,
                MercenaryRumorHint = ownedMercenary?.RumorHint ?? string.Empty,
                MercenaryTotalContracts = ownedMercenary?.TotalContracts ?? 0,
                MercenaryTotalContractMinutes = ownedMercenary?.TotalContractMinutes ?? 0,
                MercenaryKillsTogether = ownedMercenary?.KillsTogether ?? 0,
                MercenaryDeathsTogether = ownedMercenary?.DeathsTogether ?? 0,
                MercenaryRevivesReceived = ownedMercenary?.RevivesReceived ?? 0,
                MercenaryRescues = ownedMercenary?.Rescues ?? 0,
                MercenaryQuestsCompleted = ownedMercenary?.QuestsCompleted ?? 0,
                MercenaryEarnedTitles = ownedMercenary?.EarnedTitles ?? string.Empty,
                MercenaryPersonalQuestState = ownedMercenary?.PersonalQuestState ?? string.Empty,
                MercenaryRelationshipEventState = ownedMercenary?.RelationshipEventState ?? string.Empty,
                MercenaryLastHiredAt = ownedMercenary?.LastHiredAt ?? default,
                ContentType = string.IsNullOrWhiteSpace(contentType) ? "pve" : contentType.Trim().ToLowerInvariant(),
                ObjectiveTarget = string.IsNullOrWhiteSpace(objectiveTarget) ? string.Empty : objectiveTarget.Trim(),
                RequesterName = requester.Name,
                RequesterAccount = requester.Client?.Account?.Name ?? string.Empty,
                Realm = (int) requester.Realm,
                Region = hasObjectiveLocation ? requestRegion : requester.CurrentRegionID,
                X = hasObjectiveLocation ? objectiveX : requester.X,
                Y = hasObjectiveLocation ? objectiveY : requester.Y,
                Z = hasObjectiveLocation ? objectiveZ : requester.Z,
                GroupId = requester.Group == null ? string.Empty : requester.Group.GetHashCode().ToString(CultureInfo.InvariantCulture),
                GroupSize = groupSize,
                VacantSlots = vacantSlots,
                CreatedBy = createdBy ?? string.Empty
            };
        }

        private static void AddRequest(CompanionRequest request)
        {
            lock (Sync)
            {
                AddRequestLocked(request);
            }
        }

        private static void ApplyMercenaryProgressionSnapshot(CompanionRequest request, DbPlayerMercenary mercenary)
        {
            if (request == null || mercenary == null)
                return;

            request.MercenaryTrust = mercenary.Trust;
            request.MercenaryFatigue = mercenary.Fatigue;
            request.MercenaryTotalContracts = mercenary.TotalContracts;
            request.MercenaryTotalContractMinutes = mercenary.TotalContractMinutes;
            request.MercenaryKillsTogether = mercenary.KillsTogether;
            request.MercenaryDeathsTogether = mercenary.DeathsTogether;
            request.MercenaryRevivesReceived = mercenary.RevivesReceived;
            request.MercenaryRescues = mercenary.Rescues;
            request.MercenaryQuestsCompleted = mercenary.QuestsCompleted;
            request.MercenaryEarnedTitles = mercenary.EarnedTitles;
            request.MercenaryPersonalQuestState = mercenary.PersonalQuestState;
            request.MercenaryRelationshipEventState = mercenary.RelationshipEventState;
            request.MercenaryLastHiredAt = mercenary.LastHiredAt;
            request.UpdatedUtc = DateTime.UtcNow;
        }

        private static void ApplyMercenaryContractOutcome(
            CompanionRequest request,
            string normalizedStatus,
            string previousStatus)
        {
            if (request == null || string.IsNullOrWhiteSpace(request.MercenaryId))
                return;

            DbPlayerMercenary mercenary = GameServer.Database.FindObjectByKey<DbPlayerMercenary>(request.MercenaryId);
            if (mercenary == null)
                return;

            bool wasActive =
                previousStatus.Equals(CompanionRequestStatus.Active, StringComparison.OrdinalIgnoreCase) ||
                request.ContractStartedUtc != default;
            if (normalizedStatus.Equals(CompanionRequestStatus.Completed, StringComparison.OrdinalIgnoreCase))
            {
                TimeSpan activeDuration = request.ContractStartedUtc == default
                    ? TimeSpan.Zero
                    : DateTime.UtcNow - request.ContractStartedUtc;
                PlayerMercenaryService.RecordContractCompleted(
                    mercenary,
                    activeDuration,
                    request.CloseReason,
                    request.SuppressedKillCredits);
            }
            else if (normalizedStatus.Equals(CompanionRequestStatus.Failed, StringComparison.OrdinalIgnoreCase))
            {
                PlayerMercenaryService.RecordContractFailed(mercenary, wasActive && IsPlayerAccountableMercenaryFailure(request));
            }

            ApplyMercenaryProgressionSnapshot(request, mercenary);
        }

        private static bool IsPlayerAccountableMercenaryFailure(CompanionRequest request)
        {
            string reason = (request?.CloseReason ?? string.Empty).Trim().ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(reason))
                reason = (request?.Message ?? string.Empty).Trim().ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(reason))
                return false;

            return reason.Contains("mercenary_death", StringComparison.OrdinalIgnoreCase) ||
                   reason.Contains("companion_death", StringComparison.OrdinalIgnoreCase) ||
                   reason.Contains("abandoned_mercenary", StringComparison.OrdinalIgnoreCase) ||
                   reason.Contains("abandoned_companion", StringComparison.OrdinalIgnoreCase) ||
                   reason.Contains("reckless_order", StringComparison.OrdinalIgnoreCase);
        }

        private static string BuildMercenaryLine(CompanionRequest request)
        {
            if (string.IsNullOrWhiteSpace(request.MercenaryId) &&
                string.IsNullOrWhiteSpace(request.MercenaryClassName) &&
                string.IsNullOrWhiteSpace(request.MercenaryPersonality))
                return string.Empty;

            string name = FirstNonEmpty(request.MercenaryName, request.AssignedCompanionName, "이름 미정");
            string className = FirstNonEmpty(request.MercenaryClassName, "직업 미정");
            string title = FirstTitle(request.MercenaryEarnedTitles);
            string titlePart = string.IsNullOrWhiteSpace(title) ? "" : $", 칭호 {title}";
            return $"보유 용병: {name} {className}, 성격 {PersonalityLabel(request.MercenaryPersonality)}, 전술 {TacticLabel(request.MercenaryTacticPreset)}, 친밀도 {request.MercenaryTrust}({PlayerMercenaryService.TrustStageLabel(request.MercenaryTrust)}), 피로 {request.MercenaryFatigue}{titlePart}";
        }

        private static string BuildMercenaryProgressLine(CompanionRequest request)
        {
            if (string.IsNullOrWhiteSpace(request.MercenaryId))
                return string.Empty;

            string quest = PersonalQuestLabel(request.MercenaryPersonalQuestState);
            return
                $"용병 기록: 계약 {request.MercenaryTotalContracts}회/{request.MercenaryTotalContractMinutes}분, " +
                $"처치 기여 {request.MercenaryKillsTogether}회, 구출 {request.MercenaryRescues}회, 개인 의뢰 {quest}";
        }

        private static string BuildContractLine(CompanionRequest request, DateTime now)
        {
            if (request.ContractDurationSeconds <= 0)
                return string.Empty;

            if (request.ContractStartedUtc == default)
                return $"계약: 최대 {FormatDuration(TimeSpan.FromSeconds(request.ContractDurationSeconds))}, 아직 시작 전";

            TimeSpan elapsed = now - request.ContractStartedUtc;
            if (elapsed < TimeSpan.Zero)
                elapsed = TimeSpan.Zero;

            TimeSpan duration = TimeSpan.FromSeconds(request.ContractDurationSeconds);
            TimeSpan remaining = duration - elapsed;
            if (remaining < TimeSpan.Zero)
                remaining = TimeSpan.Zero;

            if (request.Status.Equals(CompanionRequestStatus.Active, StringComparison.OrdinalIgnoreCase))
                return $"계약: 남은 시간 약 {FormatDuration(remaining)} / 진행 {FormatDuration(elapsed)}";

            return $"계약: 진행 {FormatDuration(elapsed)} / 최대 {FormatDuration(duration)}";
        }

        private static string BuildProgressLine(CompanionRequest request)
        {
            string status = CompanionRequestStatus.Normalize(request.Status);
            if (status == CompanionRequestStatus.Queued)
                return "진행: 고용 요청 대기 중입니다.";
            if (status == CompanionRequestStatus.Spawning)
                return "진행: 용병을 부르는 중입니다.";
            if (status == CompanionRequestStatus.Grouping)
                return "진행: 파티 합류를 확인하는 중입니다.";
            if (status == CompanionRequestStatus.Leaving)
                return "진행: 용병 해산을 처리하는 중입니다.";
            if (status == CompanionRequestStatus.Active)
                return "진행: 계약이 활성 상태입니다.";
            return string.Empty;
        }

        private static string BuildResultLine(CompanionRequest request)
        {
            string status = CompanionRequestStatus.Normalize(request.Status);
            if (!TerminalStatuses.Contains(status))
                return string.Empty;

            string reason = FirstNonEmpty(request.CloseReason, request.Message, status);
            string result = status switch
            {
                CompanionRequestStatus.Completed => $"결과: {CloseReasonLabel(reason)}",
                CompanionRequestStatus.Failed => $"결과: 실패 - {CloseReasonLabel(reason)}",
                CompanionRequestStatus.Canceled => $"결과: 취소 - {CloseReasonLabel(reason)}",
                _ => $"결과: {CloseReasonLabel(reason)}"
            };

            string contribution = BuildContributionLine(request);
            return string.IsNullOrWhiteSpace(contribution) ? result : $"{result} / {contribution}";
        }

        private static string BuildContributionLine(CompanionRequest request)
        {
            List<string> parts = new();
            if (request.SuppressedKillCredits > 0)
                parts.Add($"처치 기여 {request.SuppressedKillCredits}");
            if (request.SuppressedRealmPoints > 0)
                parts.Add($"RVR 보상 제한 {request.SuppressedRealmPoints}");
            if (request.SuppressedBountyPoints > 0)
                parts.Add($"BP 제한 {request.SuppressedBountyPoints}");
            if (request.SuppressedMoney > 0)
                parts.Add($"돈 보상 제한 {request.SuppressedMoney}");

            return parts.Count == 0 ? string.Empty : $"기록: {string.Join(", ", parts)}";
        }

        private static string BuildRecoveryLine(CompanionRequest request)
        {
            string status = CompanionRequestStatus.Normalize(request.Status);
            if (status == CompanionRequestStatus.Active)
                return $"복구: 재접속 후 용병이 안 보이면 잠시 기다려 주세요. 상태 갱신이 끊기면 자동 정리됩니다. 접속 유예 {FormatDuration(TimeSpan.FromSeconds(Math.Max(0, request.OfflineGraceSeconds)))}";
            if (status is CompanionRequestStatus.Queued or CompanionRequestStatus.Spawning or CompanionRequestStatus.Grouping)
                return "복구: 오래 멈춰 있으면 요청 취소 후 다시 고용하면 됩니다.";
            if (status == CompanionRequestStatus.Failed && IsSystemFailure(request))
                return "복구: 서버/서비스 문제로 보이면 친밀도 불이익 없이 다시 고용해도 됩니다.";
            return string.Empty;
        }

        private static bool IsSystemFailure(CompanionRequest request)
        {
            string reason = FirstNonEmpty(request.CloseReason, request.Message).Trim().ToLowerInvariant();
            return reason.StartsWith("system_", StringComparison.OrdinalIgnoreCase) ||
                   reason.Contains("service", StringComparison.OrdinalIgnoreCase) ||
                   reason.Contains("offline_grace_expired", StringComparison.OrdinalIgnoreCase) ||
                   reason.Contains("lease expired", StringComparison.OrdinalIgnoreCase);
        }

        private static string StatusLabel(string status)
        {
            return CompanionRequestStatus.Normalize(status) switch
            {
                CompanionRequestStatus.Queued => "대기 중",
                CompanionRequestStatus.Spawning => "소집 중",
                CompanionRequestStatus.Grouping => "파티 합류 중",
                CompanionRequestStatus.Active => "계약 진행 중",
                CompanionRequestStatus.Leaving => "해산 처리 중",
                CompanionRequestStatus.Completed => "계약 종료",
                CompanionRequestStatus.Failed => "실패",
                CompanionRequestStatus.Canceled => "취소됨",
                _ => "알 수 없음"
            };
        }

        private static string RoleLabel(string role)
        {
            return CompanionRequestRoles.Normalize(role) switch
            {
                CompanionRequestRoles.Healer => "치유",
                CompanionRequestRoles.Tank => "방어",
                CompanionRequestRoles.Dps => "공격",
                CompanionRequestRoles.Support => "지원",
                _ => "빈자리 보충"
            };
        }

        private static string TierLabel(string tier)
        {
            return CompanionContractTiers.Normalize(tier) switch
            {
                CompanionContractTiers.Skilled => "숙련",
                CompanionContractTiers.Elite => "정예",
                CompanionContractTiers.Legendary => "전설",
                _ => "일반"
            };
        }

        private static string PersonalityLabel(string personality)
        {
            return (personality ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "reckless_berserker" => "돌격형",
                "wary_survivor" => "생존형",
                "eager_rookie" => "신참형",
                "proud_veteran" => "고참형",
                "shifty_traitor" => "배신자형",
                "cunning_opportunist" => "얍삽한형",
                _ => "침착형"
            };
        }

        private static string TacticLabel(string tactic)
        {
            return (tactic ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "safe" => "안전 우선",
                "aggressive" => "공격 우선",
                "heal_priority" => "힐 우선",
                "mez_priority" => "메즈 우선",
                "leader_protect" => "리더 보호",
                _ => "균형"
            };
        }

        private static string FirstTitle(string titles)
        {
            return (titles ?? string.Empty)
                .Split(new[] { '|', ';', ',' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(title => title.Trim())
                .FirstOrDefault(title => !string.IsNullOrWhiteSpace(title)) ?? string.Empty;
        }

        private static string PersonalQuestLabel(string state)
        {
            return (state ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "available:first_bond" => "신뢰의 첫 증표 진행 가능",
                "completed:first_bond" => "신뢰의 첫 증표 완료",
                "available:field_oath" => "전장의 맹세 진행 가능",
                "completed:field_oath" => "전장의 맹세 완료",
                _ => "없음"
            };
        }

        private static string CloseReasonLabel(string reason)
        {
            string normalized = (reason ?? string.Empty).Trim().ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(normalized))
                return "세부 사유 없음";

            return normalized switch
            {
                "leader_dismissed" => "파티장이 해산함",
                "party_lost" => "파티에서 이탈함",
                "offline_grace_expired" => "접속 유예 시간이 지나 계약 정리됨",
                "party_full" => "파티 자리가 부족함",
                "request_canceled" => "요청 취소",
                "system_spawn_blocked" => "소집 조건 미충족",
                "system_spawn_failed" => "용병 소집 실패",
                "system_grouping_timeout" => "파티 합류 시간 초과",
                "system_attach_failed" => "파티 합류 실패",
                "system_behavior_client_exit" => "용병 행동 서비스 종료",
                "resurrection_save" => "부활 지원으로 파티를 살림",
                "boss_defeated" => "강적 처치 완료",
                "objective_completed" => "목표 완료",
                _ => reason.Trim()
            };
        }

        private static string FormatDuration(TimeSpan duration)
        {
            if (duration <= TimeSpan.Zero)
                return "0분";
            if (duration.TotalHours >= 1)
                return $"{(int)duration.TotalHours}시간 {duration.Minutes}분";
            if (duration.TotalMinutes >= 1)
                return $"{Math.Max(1, (int)Math.Ceiling(duration.TotalMinutes))}분";
            return $"{Math.Max(1, (int)Math.Ceiling(duration.TotalSeconds))}초";
        }

        private static string FirstNonEmpty(params string[] values)
        {
            foreach (string value in values)
            {
                if (!string.IsNullOrWhiteSpace(value))
                    return value.Trim();
            }

            return string.Empty;
        }

        private static void AddIfPresent(IList<string> lines, string line)
        {
            if (!string.IsNullOrWhiteSpace(line))
                lines.Add(line.Trim());
        }

        private static void AddRequestLocked(CompanionRequest request)
        {
            Requests.Add(request);
            if (Requests.Count > MaxStoredRequests)
                Requests.RemoveRange(0, Requests.Count - MaxStoredRequests);
        }

        private static int OpenRequestCountForRequesterLocked(GamePlayer requester)
        {
            string requesterName = requester?.Name ?? string.Empty;
            string requesterAccount = requester?.Client?.Account?.Name ?? string.Empty;
            return Requests.Count(request =>
                SlotHoldingStatuses.Contains(request.Status) &&
                ((!string.IsNullOrWhiteSpace(requesterAccount) &&
                  request.RequesterAccount.Equals(requesterAccount, StringComparison.OrdinalIgnoreCase)) ||
                 (!string.IsNullOrWhiteSpace(requesterName) &&
                  request.RequesterName.Equals(requesterName, StringComparison.OrdinalIgnoreCase))));
        }

        private static int CancelPendingRequestsLocked(string requesterAccount, string requesterName, string reason, string message)
        {
            int canceled = 0;
            DateTime now = DateTime.UtcNow;
            foreach (CompanionRequest request in Requests)
            {
                if (!CancelableStatuses.Contains(request.Status))
                    continue;
                bool accountMatches = !string.IsNullOrWhiteSpace(requesterAccount) &&
                                      request.RequesterAccount.Equals(requesterAccount, StringComparison.OrdinalIgnoreCase);
                bool nameMatches = !string.IsNullOrWhiteSpace(requesterName) &&
                                   request.RequesterName.Equals(requesterName, StringComparison.OrdinalIgnoreCase);
                if (!accountMatches && !nameMatches)
                    continue;

                request.Status = CompanionRequestStatus.Canceled;
                request.CloseReason = reason;
                request.Message = message;
                request.UpdatedUtc = now;
                canceled++;
            }
            return canceled;
        }

        private static CompanionRequest LatestForPlayerLocked(string playerName)
        {
            return Requests
                .Where(row => row.RequesterName.Equals(playerName, StringComparison.OrdinalIgnoreCase))
                .OrderByDescending(row => row.UpdatedUtc == default ? row.CreatedUtc : row.UpdatedUtc)
                .FirstOrDefault();
        }

        private static bool CanTransitionStatus(string currentStatus, string nextStatus)
        {
            string current = CompanionRequestStatus.Normalize(currentStatus);
            string next = CompanionRequestStatus.Normalize(nextStatus);
            if (current.Equals(next, StringComparison.OrdinalIgnoreCase))
                return true;

            return !TerminalStatuses.Contains(current);
        }

        private static void ExpireStaleOpenRequestsLocked(DateTime now)
        {
            foreach (CompanionRequest request in Requests)
            {
                bool isActive = request.Status.Equals(CompanionRequestStatus.Active, StringComparison.OrdinalIgnoreCase);
                if (!ExpirableOpenStatuses.Contains(request.Status) && !isActive)
                    continue;

                DateTime referenceTime = request.UpdatedUtc == default ? request.CreatedUtc : request.UpdatedUtc;
                TimeSpan timeout = isActive ? ActiveCompanionLeaseTimeout : StaleOpenRequestTimeout;
                if (referenceTime != default && now - referenceTime <= timeout)
                {
                    if (isActive &&
                        request.ContractStartedUtc != default &&
                        request.ContractDurationSeconds > 0 &&
                        now - request.ContractStartedUtc > TimeSpan.FromSeconds(request.ContractDurationSeconds))
                    {
                        request.Status = CompanionRequestStatus.Completed;
                        request.UpdatedUtc = now;
                        request.Message = "companion contract time expired";
                    }
                    continue;
                }

                request.Status = CompanionRequestStatus.Failed;
                request.UpdatedUtc = now;
                request.Message = isActive
                    ? "companion active lease expired"
                    : "companion request expired before activation";
            }
        }

        private static CompanionRequest Clone(CompanionRequest request)
        {
            return new CompanionRequest
            {
                Id = request.Id,
                CreatedUtc = request.CreatedUtc,
                UpdatedUtc = request.UpdatedUtc,
                Status = request.Status,
                Source = request.Source,
                RequestedRole = request.RequestedRole,
                RequestedCapabilities = request.RequestedCapabilities,
                ContractTier = request.ContractTier,
                ContractDurationSeconds = request.ContractDurationSeconds,
                OfflineGraceSeconds = request.OfflineGraceSeconds,
                ContractStartedUtc = request.ContractStartedUtc,
                MercenaryId = request.MercenaryId,
                MercenaryName = request.MercenaryName,
                MercenaryClassName = request.MercenaryClassName,
                MercenaryPersonality = request.MercenaryPersonality,
                MercenaryTraits = request.MercenaryTraits,
                MercenaryItemProfile = request.MercenaryItemProfile,
                MercenaryBackground = request.MercenaryBackground,
                MercenaryTacticPreset = request.MercenaryTacticPreset,
                MercenaryTrust = request.MercenaryTrust,
                MercenaryFatigue = request.MercenaryFatigue,
                MercenaryAdventureMemory = request.MercenaryAdventureMemory,
                MercenaryRumorHint = request.MercenaryRumorHint,
                MercenaryTotalContracts = request.MercenaryTotalContracts,
                MercenaryTotalContractMinutes = request.MercenaryTotalContractMinutes,
                MercenaryKillsTogether = request.MercenaryKillsTogether,
                MercenaryDeathsTogether = request.MercenaryDeathsTogether,
                MercenaryRevivesReceived = request.MercenaryRevivesReceived,
                MercenaryRescues = request.MercenaryRescues,
                MercenaryQuestsCompleted = request.MercenaryQuestsCompleted,
                MercenaryEarnedTitles = request.MercenaryEarnedTitles,
                MercenaryPersonalQuestState = request.MercenaryPersonalQuestState,
                MercenaryRelationshipEventState = request.MercenaryRelationshipEventState,
                MercenaryLastHiredAt = request.MercenaryLastHiredAt,
                ContentType = request.ContentType,
                ObjectiveTarget = request.ObjectiveTarget,
                RequesterName = request.RequesterName,
                RequesterAccount = request.RequesterAccount,
                Realm = request.Realm,
                Region = request.Region,
                X = request.X,
                Y = request.Y,
                Z = request.Z,
                GroupId = request.GroupId,
                GroupSize = request.GroupSize,
                VacantSlots = request.VacantSlots,
                CreatedBy = request.CreatedBy,
                AssignedCompanionName = request.AssignedCompanionName,
                Message = request.Message,
                CloseReason = request.CloseReason,
                SuppressedRealmPoints = request.SuppressedRealmPoints,
                SuppressedBountyPoints = request.SuppressedBountyPoints,
                SuppressedMoney = request.SuppressedMoney,
                SuppressedKillCredits = request.SuppressedKillCredits
            };
        }
    }
}
