using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute(
    "&statsanon",
    ePrivLevel.Player,
    "내 통계를 숨깁니다.",
    "/statsanon")]
    public class StatsAnonHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (IsSpammingCommand(client.Player, "statsanon"))
                return;

            if (client == null)
                return;

            client.Player.IgnoreStatistics = !client.Player.IgnoreStatistics;
            string msg;

            if (client.Player.IgnoreStatistics)
                msg = LanguageMgr.GetTranslation(client.Account.Language, "PlayerStatistics.StatsAnon.Hidden");
            else
                msg = LanguageMgr.GetTranslation(client.Account.Language, "PlayerStatistics.StatsAnon.Visible");

            client.Player.Out.SendMessage(msg, eChatType.CT_System, eChatLoc.CL_ChatWindow);
        }
    }
}
