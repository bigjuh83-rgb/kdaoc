using System;
using System.Collections.Generic;
using DOL.GS.LiveCompanion;
using DOL.GS.PacketHandler;

namespace DOL.GS.Commands
{
    [CmdAttribute("&dummy",
        ePrivLevel.GM,
        "GM companion test command",
        "/dummy fill <playerName>",
        "/dummy role <playerName> healer|tank|dps|support",
        "/dummy status <playerName>",
        "/dummy leave <playerName>")]
    public class DummyCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (client?.Player == null)
                return;

            if (args.Length < 2)
            {
                DisplaySyntax(client);
                return;
            }

            switch (args[1].ToLowerInvariant())
            {
                case "fill":
                    QueueRole(client, args, CompanionRequestRoles.Fill, requiredArgs: 3);
                    return;
                case "role":
                    QueueExplicitRole(client, args);
                    return;
                case "status":
                    ShowStatus(client, args);
                    return;
                case "leave":
                    QueueLeave(client, args);
                    return;
                default:
                    DisplaySyntax(client);
                    return;
            }
        }

        private void QueueExplicitRole(GameClient client, string[] args)
        {
            if (args.Length < 4)
            {
                DisplaySyntax(client);
                return;
            }

            string role = CompanionRequestRoles.Normalize(args[3]);
            if (!CompanionRequestRoles.IsValid(role) || role == CompanionRequestRoles.Fill)
            {
                DisplayMessage(client, "역할은 healer, tank, dps, support 중 하나여야 합니다.");
                return;
            }

            QueueRole(client, args, role, requiredArgs: 4);
        }

        private void QueueRole(GameClient client, string[] args, string role, int requiredArgs)
        {
            if (args.Length < requiredArgs)
            {
                DisplaySyntax(client);
                return;
            }

            GamePlayer player = FindPlayer(args[2]);
            if (player == null)
            {
                DisplayMessage(client, $"플레이어를 찾을 수 없습니다: {args[2]}");
                return;
            }

            CompanionRequestResult result = CompanionRequestService.CreateRequest(
                player,
                role,
                "gm_command",
                "pve",
                client.Player.Name);

            DisplayMessage(client, result.Message);
            if (result.Request != null)
                DisplayMessage(client, $"요청 {result.Request.Id}: {result.Request.RequesterName}, 역할 {result.Request.RequestedRole}, 빈자리 {result.Request.VacantSlots}");
        }

        private void QueueLeave(GameClient client, string[] args)
        {
            if (args.Length < 3)
            {
                DisplaySyntax(client);
                return;
            }

            GamePlayer player = FindPlayer(args[2]);
            if (player == null)
            {
                DisplayMessage(client, $"플레이어를 찾을 수 없습니다: {args[2]}");
                return;
            }

            CompanionRequestResult result = CompanionRequestService.RequestLeave(
                player,
                "gm_command",
                client.Player.Name);

            DisplayMessage(client, result.Message);
            if (result.Request != null)
                DisplayMessage(client, $"요청 {result.Request.Id}: {result.Request.RequesterName}, 상태 {result.Request.Status}");
        }

        private void ShowStatus(GameClient client, string[] args)
        {
            if (args.Length < 3)
            {
                DisplaySyntax(client);
                return;
            }

            CompanionRequest request = CompanionRequestService.LatestForPlayer(args[2]);
            if (request == null)
            {
                DisplayMessage(client, $"동료 요청 이력이 없습니다: {args[2]}");
                return;
            }

            client.Out.SendCustomTextWindow(
                "동료 요청 상태",
                new List<string>
                {
                    $"요청: {request.Id}",
                    $"플레이어: {request.RequesterName}",
                    $"상태: {request.Status}",
                    $"역할: {request.RequestedRole}",
                    $"소집 방식: {request.Source}",
                    $"동료명: {request.AssignedCompanionName}",
                    $"파티 인원/빈자리: {request.GroupSize}/{request.VacantSlots}",
                    $"메시지: {request.Message}",
                });
        }

        private static GamePlayer FindPlayer(string name)
        {
            if (string.IsNullOrWhiteSpace(name))
                return null;

            return ClientService.Instance.GetPlayerByExactName(name);
        }
    }
}
