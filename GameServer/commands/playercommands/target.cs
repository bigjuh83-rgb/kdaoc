using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute("&target", ePrivLevel.Player, "target a player by name", "/target <playerName>")]
    public class TargetCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (IsSpammingCommand(client.Player, "target"))
                return;

            if (args.Length == 2)
            {
                GamePlayer targetPlayer = ClientService.Instance.GetPlayerByPartialName(args[1], out ClientService.PlayerGuessResult result);

                if (result is ClientService.PlayerGuessResult.FOUND_PARTIAL or ClientService.PlayerGuessResult.FOUND_EXACT)
                {
                    if (!client.Player.IsWithinRadius(targetPlayer, WorldMgr.YELL_DISTANCE) || targetPlayer.IsStealthed || GameServer.ServerRules.IsAllowedToAttack(client.Player, targetPlayer, true))
                    {
                        client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Target.NotSeen", args[1]), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                        return;
                    }

                    client.Out.SendChangeTarget(targetPlayer);
                    client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Target.YouTarget", targetPlayer.GetName(0, true)), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return;
                }
                else if (client.Account.PrivLevel > 1)
                {
                    foreach (GameNPC npc in client.Player.GetNPCsInRadius(800))
                    {
                        if (npc.Name == args[1])
                        {
                            client.Out.SendChangeTarget(npc);
                            client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Target.GMYouTarget", npc.GetName(0, true)), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }
                    }
                }

                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Target.NotSeen", args[1]), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            if (client.Account.PrivLevel > 1)
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Target.UsageGM"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
            else
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Target.Usage"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
        }
    }
}
