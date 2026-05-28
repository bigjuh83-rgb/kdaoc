using System;
using System.Linq;
using System.Net;
using DOL.Events;
using DOL.GS.LiveCompanion;
using DOL.GS.ServerProperties;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace DOL.GS.API.DummyCompanion
{
    internal static class DummyCompanionRoutes
    {
        public static void MapDummyCompanionRoutes(this WebApplication api)
        {
            api.MapGet("/api/dummy/companions/requests", (HttpContext context) =>
            {
                IResult denied = RequireMutationAllowed(context);
                if (denied != null)
                    return denied;

                string status = Query(context, "status");
                int limit = ParseInt(Query(context, "limit"), 100);
                return Results.Ok(CompanionRequestService.Snapshot(status, limit));
            });

            api.MapGet("/api/dummy/companions/requests/{id}", (HttpContext context, string id) =>
            {
                IResult denied = RequireMutationAllowed(context);
                if (denied != null)
                    return denied;

                CompanionRequest request = CompanionRequestService.Get(id);
                return request == null ? Results.NotFound(new { error = "RequestNotFound", id }) : Results.Ok(request);
            });

            api.MapGet("/api/dummy/companions/players/{playerName}/latest", (HttpContext context, string playerName) =>
            {
                IResult denied = RequireMutationAllowed(context);
                if (denied != null)
                    return denied;

                CompanionRequest request = CompanionRequestService.LatestForPlayer(playerName);
                return request == null
                    ? Results.NotFound(new { error = "RequestNotFound", playerName })
                    : Results.Ok(request);
            });

            api.MapGet("/api/dummy/companions/summary", (HttpContext context) =>
            {
                IResult denied = RequireMutationAllowed(context);
                if (denied != null)
                    return denied;

                int limit = ParseInt(Query(context, "limit"), 20);
                return Results.Ok(CompanionRequestService.Summary(limit));
            });

            api.MapPost("/api/dummy/companions/requests", (HttpContext context) =>
            {
                IResult denied = RequireMutationAllowed(context);
                if (denied != null)
                    return denied;

                string playerName = Query(context, "player");
                GamePlayer player = FindPlayer(playerName);
                if (player == null)
                    return Results.NotFound(new { error = "PlayerNotFound", player = playerName });

                CompanionRequestResult result = CompanionRequestService.CreateRequest(
                    player,
                    Query(context, "role", CompanionRequestRoles.Fill),
                    Query(context, "source", "api"),
                    Query(context, "contentType", "pve"),
                    Query(context, "createdBy", "api"),
                    ParseUShort(Query(context, "region"), 0),
                    ParseInt(Query(context, "x"), 0),
                    ParseInt(Query(context, "y"), 0),
                    ParseInt(Query(context, "z"), 0),
                    Query(context, "requestedCapabilities", Query(context, "capabilities", Query(context, "capability"))),
                    Query(context, "objectiveTarget", Query(context, "targetName", Query(context, "objectiveName"))));

                return result.Success ? Results.Ok(result) : Results.BadRequest(result);
            });

            api.MapPost("/api/dummy/companions/requests/claim", (HttpContext context) =>
            {
                IResult denied = RequireMutationAllowed(context);
                if (denied != null)
                    return denied;

                CompanionRequest request = CompanionRequestService.ClaimNextQueued();
                return request == null ? Results.NotFound(new { error = "NoQueuedRequest" }) : Results.Ok(request);
            });

            api.MapPost("/api/dummy/companions/requests/{id}/status", (HttpContext context, string id) =>
            {
                IResult denied = RequireMutationAllowed(context);
                if (denied != null)
                    return denied;

                CompanionRequest request = CompanionRequestService.UpdateStatus(
                    id,
                    Query(context, "status"),
                    Query(context, "message"),
                    Query(context, "companion"));

                return request == null ? Results.NotFound(new { error = "RequestNotFoundOrInvalidStatus", id }) : Results.Ok(request);
            });

            api.MapPost("/api/dummy/companions/requests/{id}/cancel", (HttpContext context, string id) =>
            {
                IResult denied = RequireMutationAllowed(context);
                if (denied != null)
                    return denied;

                CompanionRequest request = CompanionRequestService.CancelRequest(
                    id,
                    Query(context, "reason", "request_canceled"),
                    Query(context, "message", "동료 요청이 취소되었습니다."));

                return request == null ? Results.NotFound(new { error = "RequestNotFoundOrNotCancelable", id }) : Results.Ok(request);
            });

            api.MapPost("/api/dummy/companions/requests/{id}/attach", (HttpContext context, string id) =>
            {
                IResult denied = RequireMutationAllowed(context);
                if (denied != null)
                    return denied;

                CompanionRequest request = CompanionRequestService.Get(id);
                if (request == null)
                    return Results.NotFound(new { error = "RequestNotFound", id });

                IResult notAttachable = RequireAttachableRequest(request);
                if (notAttachable != null)
                    return notAttachable;

                GamePlayer requester = FindPlayer(request.RequesterName, request.RequesterAccount);
                if (requester == null)
                    return Results.NotFound(new { error = "RequesterNotFound", request.RequesterName });

                string companionName = Query(context, "companion");
                string companionAccount = Query(context, "account");
                if (!AttachCompanionMatchesRequest(request, companionName, companionAccount))
                    return Results.BadRequest(new
                    {
                        error = "UnexpectedCompanion",
                        expected = request.AssignedCompanionName,
                        companion = companionName,
                        account = companionAccount
                    });

                GamePlayer companion = FindPlayer(companionName, companionAccount);
                if (companion == null)
                    return Results.NotFound(new { error = "CompanionNotFound", companion = companionName, account = companionAccount });

                string failure = AttachCompanion(requester, companion);
                if (!string.IsNullOrWhiteSpace(failure))
                {
                    CompanionRequest failed = CompanionRequestService.UpdateStatus(id, CompanionRequestStatus.Failed, failure, companion.Name);
                    return Results.BadRequest(new { error = "AttachFailed", message = failure, request = failed });
                }

                CompanionRequest updated = CompanionRequestService.UpdateStatus(
                    id,
                    CompanionRequestStatus.Active,
                    $"{companion.Name} 동료가 파티에 합류했습니다.",
                    companion.Name);

                return Results.Ok(updated);
            });

            api.MapPost("/api/dummy/companions/requests/{id}/detach", (HttpContext context, string id) =>
            {
                IResult denied = RequireMutationAllowed(context);
                if (denied != null)
                    return denied;

                CompanionRequest request = CompanionRequestService.Get(id);
                if (request == null)
                    return Results.NotFound(new { error = "RequestNotFound", id });

                GamePlayer companion = FindPlayer(Query(context, "companion", request.AssignedCompanionName), Query(context, "account"));
                if (companion == null)
                    return Results.NotFound(new { error = "CompanionNotFound", companion = request.AssignedCompanionName });

                if (companion.Group != null)
                    companion.Group.RemoveMember(companion);

                CompanionRequest updated = CompanionRequestService.UpdateStatus(
                    id,
                    CompanionRequestStatus.Completed,
                    $"companion {companion.Name} detached from group",
                    companion.Name);

                return Results.Ok(updated);
            });

            api.MapPost("/api/dummy/companions/requests/leave", (HttpContext context) =>
            {
                IResult denied = RequireMutationAllowed(context);
                if (denied != null)
                    return denied;

                string playerName = Query(context, "player");
                GamePlayer player = FindPlayer(playerName);
                if (player == null)
                    return Results.NotFound(new { error = "PlayerNotFound", player = playerName });

                CompanionRequestResult result = CompanionRequestService.RequestLeave(
                    player,
                    Query(context, "source", "api"),
                    Query(context, "createdBy", "api"));

                return result.Success ? Results.Ok(result) : Results.BadRequest(result);
            });
        }

        private static IResult RequireMutationAllowed(HttpContext context)
        {
            string configuredPassword = Properties.API_PASSWORD;
            if (!string.IsNullOrWhiteSpace(configuredPassword))
            {
                if (new PasswordVerification().VerifyAPIPassword(Query(context, "password")))
                    return null;

                return Results.Problem("No bread for you!", null, 401);
            }

            IPAddress remoteAddress = context.Connection.RemoteIpAddress;
            if (remoteAddress == null || IPAddress.IsLoopback(remoteAddress))
                return null;

            return Results.Problem("No bread for you!", null, 401);
        }

        private static string Query(HttpContext context, string key, string defaultValue = "")
        {
            string value = context.Request.Query[key].FirstOrDefault();
            return string.IsNullOrWhiteSpace(value) ? defaultValue : value.Trim();
        }

        private static int ParseInt(string value, int defaultValue)
        {
            return int.TryParse(value, out int parsed) ? parsed : defaultValue;
        }

        private static ushort ParseUShort(string value, ushort defaultValue)
        {
            return ushort.TryParse(value, out ushort parsed) ? parsed : defaultValue;
        }

        private static IResult RequireAttachableRequest(CompanionRequest request)
        {
            if (request.Status.Equals(CompanionRequestStatus.Grouping, StringComparison.OrdinalIgnoreCase))
                return null;

            return Results.BadRequest(new
            {
                error = "RequestNotAttachable",
                id = request.Id,
                status = request.Status
            });
        }

        private static bool AttachCompanionMatchesRequest(CompanionRequest request, string companionName, string account)
        {
            string expected = request?.AssignedCompanionName?.Trim() ?? string.Empty;
            if (string.IsNullOrWhiteSpace(expected))
                return false;

            return (!string.IsNullOrWhiteSpace(companionName) &&
                    expected.Equals(companionName.Trim(), StringComparison.OrdinalIgnoreCase)) ||
                   (!string.IsNullOrWhiteSpace(account) &&
                    expected.Equals(account.Trim(), StringComparison.OrdinalIgnoreCase));
        }

        private static GamePlayer FindPlayer(string name, string account = "")
        {
            if (string.IsNullOrWhiteSpace(name) && string.IsNullOrWhiteSpace(account))
                return null;

            GamePlayer player = string.IsNullOrWhiteSpace(name) ? null : ClientService.Instance.GetPlayerByExactName(name);
            if (IsUsablePlayer(player))
                return player;

            return ClientService.Instance.GetClients()
                .Select(client => client.Player)
                .FirstOrDefault(candidate => IsUsablePlayer(candidate) &&
                                             ((!string.IsNullOrWhiteSpace(name) &&
                                               candidate.Name.Equals(name, StringComparison.OrdinalIgnoreCase)) ||
                                              (!string.IsNullOrWhiteSpace(account) &&
                                               string.Equals(candidate.Client?.Account?.Name, account, StringComparison.OrdinalIgnoreCase))));
        }

        private static bool IsUsablePlayer(GamePlayer player)
        {
            return player != null &&
                   player.ObjectState is GameObject.eObjectState.Active &&
                   player.Client?.ClientState is GameClient.eClientState.Playing;
        }

        private static string AttachCompanion(GamePlayer requester, GamePlayer companion)
        {
            if (requester == null)
                return "요청자를 찾을 수 없습니다.";
            if (companion == null)
                return "동료를 찾을 수 없습니다.";
            if (ReferenceEquals(requester, companion))
                return "요청자 자신은 동료로 붙일 수 없습니다.";
            if (!GameServer.ServerRules.IsAllowedToGroup(requester, companion, true))
                return "같은 렐름의 동료만 파티에 합류할 수 있습니다.";
            if (companion.Group != null)
            {
                if (ReferenceEquals(companion.Group, requester.Group) && requester.Group.IsInTheGroup(companion))
                    return string.Empty;

                return "동료가 이미 다른 파티에 속해 있습니다.";
            }

            if (requester.Group != null)
            {
                if (requester.Group.MemberCount >= Properties.GROUP_MAX_MEMBER)
                    return "파티가 가득 차 동료를 합류시킬 수 없습니다.";

                if (!requester.Group.AddMember(companion))
                    return "동료를 파티에 합류시키지 못했습니다.";

                GameEventMgr.Notify(GamePlayerEvent.AcceptGroup, companion);
                return string.Empty;
            }

            Group group = new(requester);
            GroupMgr.AddGroup(group);
            if (!group.AddMember(requester) || !group.AddMember(companion))
                return "동료 파티를 생성하지 못했습니다.";

            GameEventMgr.Notify(GamePlayerEvent.AcceptGroup, companion);
            return string.Empty;
        }
    }
}
