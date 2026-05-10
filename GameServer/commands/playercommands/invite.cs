using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&invite",
        ePrivLevel.Player,
        "Invite a specified or targeted player to join your group", "/invite <player>")]
    public class InviteCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (client.Player.Group != null && client.Player.Group.Leader != client.Player)
            {
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.NotLeader"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            if (IsSpammingCommand(client.Player, "invite"))
                return;

            string targetName = string.Join(" ", args, 1, args.Length - 1);
            GamePlayer target;

            if (args.Length < 2)
            {
                // Inviting by target
                if (client.Player.TargetObject == null || client.Player.TargetObject == client.Player)
                {
                    client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.InvalidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return;
                }

                if (client.Player.TargetObject is not GamePlayer targetPlayer)
                {
                    client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.InvalidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return;
                }

                target = targetPlayer;

                if (!GameServer.ServerRules.IsAllowedToGroup(client.Player, target, false))
                    return;
            }
            else
            {
                // Inviting by name
                target = ClientService.Instance.GetPlayerByPartialName(targetName, out ClientService.PlayerGuessResult result);

                switch (result)
                {
                    case ClientService.PlayerGuessResult.NOT_FOUND:
                    {
                        client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.NoPlayerOnline"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                        return;
                    }
                    case ClientService.PlayerGuessResult.FOUND_MULTIPLE:
                    {
                        client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.MultiplePlayersMatch"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                        return;
                    }
                    case ClientService.PlayerGuessResult.FOUND_EXACT:
                    case ClientService.PlayerGuessResult.FOUND_PARTIAL:
                    {
                        if (!GameServer.ServerRules.IsAllowedToGroup(client.Player, target, true))
                        {
                            client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.NoPlayerOnline"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        if (target == client.Player)
                        {
                            client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.CantInviteSelf"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        break;
                    }
                }
            }

            if (target.Group != null)
            {
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.TargetAlreadyGrouped"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            if (client.Account.PrivLevel > target.Client.Account.PrivLevel)
            {
                // you have no choice!
                if (client.Player.Group == null)
                {
                    Group group = new(client.Player);
                    GroupMgr.AddGroup(group);
                    group.AddMember(client.Player);
                    group.AddMember(target);
                }
                else
                    client.Player.Group.AddMember(target);

                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.GMAddedTarget", target.Name), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                target.Out.SendMessage(LanguageMgr.GetTranslation(target.Client.Account.Language, "Scripts.Players.Group.GMAddedYou", client.Player.Name), eChatType.CT_System, eChatLoc.CL_SystemWindow);
            }
            else
            {
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.InvitedTarget", target.Name), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                target.Out.SendGroupInviteCommand(client.Player, LanguageMgr.GetTranslation(target.Client.Account.Language, "Scripts.Players.Group.InviteDialog", client.Player.Name));
                target.Out.SendMessage(LanguageMgr.GetTranslation(target.Client.Account.Language, "Scripts.Players.Group.InvitedBy", client.Player.Name), eChatType.CT_System, eChatLoc.CL_SystemWindow);
            }
        }
    }
}
