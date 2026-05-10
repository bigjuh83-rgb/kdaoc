using System;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&facegloc",
		ePrivLevel.Player,
		"Turns and faces your character into the direction of the x, y coordinates provided (using DOL region global coordinates).",
		"/facegloc [x] [y]")]
	public class GLocFaceCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (IsSpammingCommand(client.Player, "facegloc"))
				return;

			if (args.Length < 3)
			{
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.FaceLoc.EnterXY"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				return;
			}

			int x, y;
			try
			{
				x = Convert.ToInt32(args[1]);
				y = Convert.ToInt32(args[2]);
			}
			catch (Exception)
			{
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.FaceLoc.EnterXY"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				return;
			}

			ushort direction = client.Player.GetHeading(x, y);
			client.Player.Heading = direction;
			client.Out.SendPlayerJump(true);
		}
	}
}
