using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&xp",
		ePrivLevel.Player,
		"경험치 획득을 켜거나 끕니다.",
		"/xp <on/off>")]
	public class XPCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (args.Length < 2)
			{
				DisplaySyntax(client);
				return;
			}

			if (IsSpammingCommand(client.Player, "xp"))
				return;

			if (args[1].ToLower().Equals("on"))
			{
				client.Player.GainXP = true;
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.XP.On"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			}
			else if (args[1].ToLower().Equals("off"))
			{
				client.Player.GainXP = false;
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.XP.Off"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			}
		}
	}
}
