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
using DOL.Database;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS
{
	/// <summary>
	/// Midgard teleporter.
	/// </summary>
	/// <author>Aredhel</author>
	public class MidgardTeleporter : GameTeleporter
	{
		/// <summary>
		/// Player right-clicked the teleporter.
		/// </summary>
		/// <param name="player"></param>
		/// <returns></returns>
		public override bool Interact(GamePlayer player)
		{
			if (!base.Interact(player) || GameRelic.IsPlayerCarryingRelic(player)) return false;

			TurnTo(player, 10000);

			SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "MidgardTeleporter.Interact.Menu", player.Name));

			return true;
		}

		/// <summary>
		/// Player has picked a subselection.
		/// </summary>
		/// <param name="player"></param>
		/// <param name="subSelection"></param>
		protected override void OnSubSelectionPicked(GamePlayer player, DbTeleport subSelection)
		{
			switch (subSelection.TeleportID.ToLower())
			{
				case "shrouded isles":
					{
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "MidgardTeleporter.SubSelection.ShroudedIslesPrompt"));
						return;
					}
				case "housing":
					{
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "RealmTeleporter.SubSelection.HousingPrompt"));
						return;
					}

				case "towns":
				{
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "MidgardTeleporter.SubSelection.TownsPrompt"));
					return;
				}
			}
			base.OnSubSelectionPicked(player, subSelection);
		}

		/// <summary>
		/// Player has picked a destination.
		/// </summary>
		/// <param name="player"></param>
		/// <param name="destination"></param>
		protected override void OnDestinationPicked(GamePlayer player, DbTeleport destination)
		{

			Region region = WorldMgr.GetRegion((ushort) destination.RegionID);

			if (region == null || region.IsDisabled)
			{
				player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "RealmTeleporter.Destination.NotAvailable"), eChatType.CT_System,
					eChatLoc.CL_SystemWindow);
				return;
			}

			Say(LanguageMgr.GetTranslation(player.Client.Account.Language, "RealmTeleporter.Destination.Teleporting", destination.TeleportID));
			OnTeleportSpell(player, destination);
		}
	}
}
