using DOL.GS.PacketHandler;
using System.Collections;
using System.Collections.Generic;
using DOL.Language;
using DOL.GS.Keeps;
using DOL.GS.ServerRules;

namespace DOL.GS.Commands
{
	[CmdAttribute(
	   "&ck",
	   ePrivLevel.Player,
		 "Displays who owns the CK while in a battleground.", "/ck")]
	public class CkCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (IsSpammingCommand(client.Player, "ck"))
				return;

			string bgName = client.Player.CurrentZone.Description;

			if (GameServer.KeepManager.GetBattleground(client.Player.CurrentRegionID) != null)
			{
				ICollection<AbstractGameKeep> keepList =
					GameServer.KeepManager.GetKeepsOfRegion(client.Player.CurrentRegionID);
				foreach (AbstractGameKeep keep in keepList)
				{
					ChatUtil.SendSystemMessage(client, KeepStringBuilder(keep, client.Account.Language));
				}
			}
			else
			{
				client.Out.SendMessage(LanguageMgr.GetTranslation(client, "Scripts.Players.CK.NotInBattleground"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			}
		}
		private string KeepStringBuilder(AbstractGameKeep keep, string language = null)
		{
			string buffer = string.Empty;
			buffer += LanguageMgr.GetTranslatedKeepName(language, keep.Name) + ": " + GlobalConstants.RealmToName(keep.Realm, language);
			if (keep.Guild != null)
			{
				buffer += " (" + keep.Guild.Name + ")";
			}
			buffer += "\n";
			return buffer;
		}

	}
}
