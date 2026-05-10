/*
 * DAWN OF LIGHT - The first free open source DAoC server emulator
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 *
 */
using System;
using System.Linq;

using DOL.Database;
using DOL.Language;

namespace DOL.GS
{
	/// <summary>
	/// Teleporter for entering and leaving the throne room.
	/// </summary>
	/// <author>Aredhel</author>
	public class ThroneRoomTeleporter : GameNPC
	{
		private static new readonly Logging.Logger log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

		/// <summary>
		/// Interact with the NPC.
		/// </summary>
		/// <param name="player"></param>
		/// <returns></returns>
		public override bool Interact(GamePlayer player)
		{
			if (!base.Interact(player) || player == null)
				return false;

			if (GlobalConstants.IsExpansionEnabled((int)eClientExpansion.DarknessRising))
			{
				if (player.CurrentRegion.Expansion == (int)eClientExpansion.DarknessRising)
				{
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "ThroneRoomTeleporter.Interact.ExitPrompt"));
				}
				else
				{
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "ThroneRoomTeleporter.Interact.KingPrompt"));
				}
				return true;
			}
			else
			{
				String reply = LanguageMgr.GetTranslation(player.Client.Account.Language, "ThroneRoomTeleporter.Interact.KingBusy");

				if (player.Inventory.CountItemTemplate("Personal_Bind_Recall_Stone", eInventorySlot.Min_Inv, eInventorySlot.Max_Inv) == 0)
					reply += " " + LanguageMgr.GetTranslation(player.Client.Account.Language, "ThroneRoomTeleporter.Interact.StoneFallback");

				SayTo(player, reply);
				return false;
			}
		}

		/// <summary>
		/// Talk to the NPC.
		/// </summary>
		/// <param name="source"></param>
		/// <param name="str"></param>
		/// <returns></returns>
		public override bool WhisperReceive(GameLiving source, string text)
		{
			if (!base.WhisperReceive(source, text) || !(source is GamePlayer))
				return false;

			GamePlayer player = source as GamePlayer;

			string normalizedText = text.ToLowerInvariant();

			if ((normalizedText == "king" || normalizedText == "exit" || text == "국왕" || text == "나가기") && GlobalConstants.IsExpansionEnabled((int)eClientExpansion.DarknessRising))
			{
				uint throneRegionID = 0;
				string teleportThroneID = "error";
				string teleportExitID = "error";

				switch (Realm)
				{
					case eRealm.Albion:
						throneRegionID = 394;
						teleportThroneID = "AlbThroneRoom";
						teleportExitID = "AlbThroneExit";
						break;
					case eRealm.Midgard:
						throneRegionID = 360;
						teleportThroneID = "MidThroneRoom";
						teleportExitID = "MidThroneExit";
						break;
					case eRealm.Hibernia:
						throneRegionID = 395;
						teleportThroneID = "HibThroneRoom";
						teleportExitID = "HibThroneExit";
						break;
				}

				if (throneRegionID == 0)
				{
					log.ErrorFormat("Can't find King for player {0} speaking to {1} of realm {2}!", player.Name, Name, Realm);
					player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "ThroneRoomTeleporter.Error.ThroneRoomNotFound"), DOL.GS.PacketHandler.eChatType.CT_Staff, DOL.GS.PacketHandler.eChatLoc.CL_SystemWindow);
					return false;
				}

				DbTeleport teleport = null;

				if (player.CurrentRegionID == throneRegionID)
				{
					teleport = DOLDB<DbTeleport>.SelectObject(DB.Column("TeleportID").IsEqualTo(teleportExitID));
					if (teleport == null)
					{
						log.ErrorFormat("Can't find throne room exit TeleportID {0}!", teleportExitID);
						player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "ThroneRoomTeleporter.Error.ExitNotFoundMoveBind"), DOL.GS.PacketHandler.eChatType.CT_Staff, DOL.GS.PacketHandler.eChatLoc.CL_SystemWindow);
						player.MoveToBind();
					}
				}
				else
				{
					teleport = DOLDB<DbTeleport>.SelectObject(DB.Column("TeleportID").IsEqualTo(teleportThroneID));
					if (teleport == null)
					{
						log.ErrorFormat("Can't find throne room TeleportID {0}!", teleportThroneID);
						player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "ThroneRoomTeleporter.Error.TeleportLocationNotFound"), DOL.GS.PacketHandler.eChatType.CT_Staff, DOL.GS.PacketHandler.eChatLoc.CL_SystemWindow);
					}
				}

				if (teleport != null)
				{
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "ThroneRoomTeleporter.Teleport.Accepted"));
					player.MoveTo((ushort)teleport.RegionID, teleport.X, teleport.Y, teleport.Z, (ushort)teleport.Heading);
				}

				return true;
			}


				if (normalizedText == "do" || normalizedText == "드리기")
			{
				if (player.Inventory.CountItemTemplate("Personal_Bind_Recall_Stone", eInventorySlot.Min_Inv, eInventorySlot.Max_Inv) == 0)
				{
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "ThroneRoomTeleporter.Whisper.GiveStone"));
					player.ReceiveItem(this, "Personal_Bind_Recall_Stone");
				}
				return false;
			}

			return true;
		}
	}
}
