using DOL.GS.GameEvents;
using DOL.GS.PacketHandler;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&dragonball",
		ePrivLevel.Player,
		"드래곤볼 수집 상태를 확인합니다.",
		"/dragonball",
		"/yell 나오너라 신룡이여")]
	public class DragonBallCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (client?.Player == null)
				return;

			if (args.Length > 1 && args[1].Equals("summon", System.StringComparison.OrdinalIgnoreCase))
			{
				client.Player.Out.SendMessage("신룡 소환은 /yell 나오너라 신룡이여 로만 가능합니다.", eChatType.CT_Important, eChatLoc.CL_SystemWindow);
				return;
			}

			client.Player.Out.SendMessage(DragonBallDropEvent.GetCollectionStatusMessage(client.Player), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
		}
	}
}
