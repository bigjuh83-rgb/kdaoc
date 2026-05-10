using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands {
	[CmdAttribute(
		"&combatstats",
		ePrivLevel.Player,
		"Toggle detailed combat log",
		"/combatstats <on/off>")]
	public class CombatStatsCommandHandler : AbstractCommandHandler, ICommandHandler {
		public void OnCommand(GameClient client, string[] args)
		{
			if (args.Length < 2)
			{
				DisplaySyntax(client);
				return;
			}

			if (IsSpammingCommand(client.Player, "combatstats"))
				return;

			if (args[1].ToLower().Equals("on"))
			{
				client.Player.UseDetailedCombatLog = true;
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.CombatStats.On"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			}
			else if (args[1].ToLower().Equals("off"))
			{
				client.Player.UseDetailedCombatLog = false;
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.CombatStats.Off"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			}
		}
	}
}
