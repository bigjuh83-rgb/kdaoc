using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
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

    public sealed class CompanionRequest
    {
        public string Id { get; set; } = string.Empty;
        public DateTime CreatedUtc { get; set; }
        public DateTime UpdatedUtc { get; set; }
        public string Status { get; set; } = CompanionRequestStatus.Queued;
        public string Source { get; set; } = string.Empty;
        public string RequestedRole { get; set; } = CompanionRequestRoles.Fill;
        public string RequestedCapabilities { get; set; } = string.Empty;
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
            string objectiveTarget = "")
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
                    objectiveTarget);

                if (availableSlots <= 0)
                {
                    request.Status = CompanionRequestStatus.Failed;
                    request.Message = "파티가 가득 차 동료를 부를 수 없습니다.";
                    AddRequestLocked(request);
                    return new CompanionRequestResult { Success = false, Message = request.Message, Request = request };
                }

                request.Message = "동료 요청이 접수되었습니다.";
                AddRequestLocked(request);
                return new CompanionRequestResult { Success = true, Message = request.Message, Request = request };
            }
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
                    "동료 해산으로 대기 중인 요청을 취소했습니다.");

                CompanionRequest request = BuildRequest(
                    requester,
                    "leave",
                    source,
                    "control",
                    createdBy,
                    CurrentGroupSize(requester),
                    VacantSlots(requester));
                request.Status = CompanionRequestStatus.Leaving;
                request.Message = "동료 해산 요청이 접수되었습니다.";
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
                    "동료 요청이 취소되었습니다.");

                CompanionRequest latest = LatestForPlayerLocked(requester.Name);
                string message = canceled > 0
                    ? $"대기 중인 동료 요청 {canceled}건을 취소했습니다."
                    : "취소할 대기 중인 동료 요청이 없습니다.";
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
                request.Message = string.IsNullOrWhiteSpace(message) ? "동료 요청이 취소되었습니다." : message.Trim();
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

                request.Message = $"동료 보상 제한 기록: {rewardType} {clampedAmount}";
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
                    ? "동료 서비스가 해산 요청을 처리 중입니다."
                    : "동료 서비스가 요청을 처리 중입니다.";
                return Clone(request);
            }
        }

        public static CompanionRequest UpdateStatus(string id, string status, string message, string assignedCompanionName)
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

                request.Status = normalizedStatus;
                request.UpdatedUtc = DateTime.UtcNow;
                if (!string.IsNullOrWhiteSpace(message))
                    request.Message = message.Trim();
                if (!string.IsNullOrWhiteSpace(assignedCompanionName))
                    request.AssignedCompanionName = assignedCompanionName.Trim();

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
            string objectiveTarget = "")
        {
            DateTime now = DateTime.UtcNow;
            bool hasObjectiveLocation = objectiveX != 0 || objectiveY != 0 || objectiveZ != 0;
            ushort requestRegion = objectiveRegion > 0 ? objectiveRegion : requester.CurrentRegionID;
            return new CompanionRequest
            {
                Id = Guid.NewGuid().ToString("N"),
                CreatedUtc = now,
                UpdatedUtc = now,
                Status = CompanionRequestStatus.Queued,
                Source = string.IsNullOrWhiteSpace(source) ? "unknown" : source.Trim(),
                RequestedRole = requestedRole,
                RequestedCapabilities = string.IsNullOrWhiteSpace(requestedCapabilities) ? string.Empty : requestedCapabilities.Trim().ToLowerInvariant(),
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
                    continue;

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
