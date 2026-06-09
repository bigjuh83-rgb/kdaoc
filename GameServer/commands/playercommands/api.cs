
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
	[Cmd(
		"&api",
		ePrivLevel.Player,
		"API 표시 옵션을 켜거나 끕니다.",
		"/api specs - 플레이어 전문화 표시를 켜거나 끕니다.")]
	public class APICommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (args.Length < 2)
			{
				DisplaySyntax(client);
				return;
			}

			if (IsSpammingCommand(client.Player, "api"))
				return;

			if (args[1].ToLower() == "specs")
			{
				client.Player.HideSpecializationAPI = !client.Player.HideSpecializationAPI;
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.API.SpecializationDetails", LanguageMgr.GetTranslation(client.Account.Language, client.Player.HideSpecializationAPI ? "Scripts.Common.Hidden" : "Scripts.Common.Shown")), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				GameServer.Database.SaveObject(client.Player.DBCharacter); // using this instead of SaveIntoDatabase() because we don't want to display it to the player to avoid save abuse
			}
		}
	}
}
