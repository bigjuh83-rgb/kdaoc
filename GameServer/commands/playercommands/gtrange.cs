using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&gtrange",
        ePrivLevel.Player,
        "Gives a range to a ground target",
        "/gtrange")]
    public class GroundTargetRangeCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (IsSpammingCommand(client.Player, "gtrange"))
                return;

            if (!client.Player.GroundTarget.IsValid)
            {
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.GroundTargetRange.NeedTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            int range = client.Player.GetDistanceTo(client.Player.GroundTarget);
            client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.GroundTargetRange.Result", range), eChatType.CT_System, eChatLoc.CL_SystemWindow);
        }
    }
}
