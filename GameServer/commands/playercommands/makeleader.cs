using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute("&makeleader",
         new string[] { "&m" },
         ePrivLevel.Player,
         "Set a new group leader (can be used by current leader).",
         "/m <playerName>")]

    public class MakeLeaderCommandHandler : ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (client.Player.Group == null || client.Player.Group.MemberCount < 2)
            {
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.NotInGroup"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            if(client.Player.Group.Leader != client.Player)
            {
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.NotLeader"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            GamePlayer target;

            if (args.Length < 2) // Setting by target
            {
                if (client.Player.TargetObject == null || client.Player.TargetObject == client.Player)
                {
                    client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.InvalidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return;
                }

                if(client.Player.TargetObject is not GamePlayer)
                {
                    client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.InvalidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return;
                }

                target = (GamePlayer) client.Player.TargetObject;

                if(client.Player.Group != target.Group)
                {
                    client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.InvalidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return;
                }
            }
            else //Setting by name
            {
                string targetName = args[1];
                target = ClientService.Instance.GetPlayerByPartialName(targetName, out _);

                if(target==null || client.Player.Group != target.Group)
                { // Invalid target
                    client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.NoPlayerInGroup"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return;
                }

                if(target==client.Player)
                {
                    client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Group.AlreadyLeader"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return;
                }

            }

            client.Player.Group.MakeLeader(target);
        }
    }
}
