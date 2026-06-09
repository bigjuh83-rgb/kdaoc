using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands {
	[CmdAttribute(
		"&xpstats",
		ePrivLevel.Player,
		"경험치 통계 표시를 켜거나 끕니다.",
		"/xpstats <off|on|verbose>")]
	public class XPStatsCommandHandler : AbstractCommandHandler, ICommandHandler {
		public void OnCommand(GameClient client, string[] args)
		{
			if (args.Length < 2)
			{
				DisplaySyntax(client);
				return;
			}

			if (IsSpammingCommand(client.Player, "xpstats"))
				return;

			if (args[1].ToLower().Equals("on"))
			{
				client.Player.XPLogState = eXPLogState.On;
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.XPStats.On"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			}
			else if (args[1].ToLower().Equals("off"))
			{
				client.Player.XPLogState = eXPLogState.Off;
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.XPStats.Off"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			}
			else if (args[1].ToLower().Equals("verbose"))
			{
				client.Player.XPLogState = eXPLogState.Verbose;
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.XPStats.Verbose"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			}
		}
	}
}
