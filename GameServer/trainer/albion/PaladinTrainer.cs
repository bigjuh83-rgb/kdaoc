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
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Trainer
{
	/// <summary>
	/// Paladin Trainer
	/// </summary>
	[NPCGuildScript("Paladin Trainer", eRealm.Albion)]		// this attribute instructs DOL to use this script for all "Paladin Trainer" NPC's in Albion (multiple guilds are possible for one script)
	public class PaladinTrainer : GameTrainer
	{
		public override eCharacterClass TrainedClass
		{
			get { return eCharacterClass.Paladin; }
		}

		public const string WEAPON_ID1 = "slash_sword_item";
		public const string WEAPON_ID2 = "crush_sword_item";
		public const string WEAPON_ID3 = "thrust_sword_item";
		public const string WEAPON_ID4 = "twohand_sword_item";

		public PaladinTrainer() : base()
		{
		}

		/// <summary>
		/// Interact with trainer
		/// </summary>
		/// <param name="player"></param>
		/// <returns></returns>
		public override bool Interact(GamePlayer player)
		{
			if (!base.Interact(player)) return false;

			// check if class matches.
			if (player.CharacterClass.ID == (int)TrainedClass)
			{
				OfferTraining(player);
			}
			else
			{
				// perhaps player can be promoted
				if (CanPromotePlayer(player))
				{
					player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.PaladinPrompt", this.Name), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
					if (!player.IsLevelRespecUsed)
					{
						OfferRespecialize(player);
					}
				}
				else
				{
					CheckChampionTraining(player);
				}
			}
			return true;
		}

		/// <summary>
		/// Talk to trainer
		/// </summary>
		/// <param name="source"></param>
		/// <param name="text"></param>
		/// <returns></returns>
		public override bool WhisperReceive(GameLiving source, string text)
		{
			if (!base.WhisperReceive(source, text)) return false;
			GamePlayer player = source as GamePlayer;


			if (CanPromotePlayer(player))
			{
				switch (text)
				{
						case "join the Church of Albion":
						case "알비온 교회에 입문":
							player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.PaladinChooseWeapon", this.Name), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
							break;
						case "slashing":
						case "베기":
							PromotePlayer(player, (int)eCharacterClass.Paladin, LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.PaladinWelcome.Sword"), null);
							player.ReceiveItem(this,WEAPON_ID1);
							break;
						case "crushing":
						case "타격":
							PromotePlayer(player, (int)eCharacterClass.Paladin, LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.PaladinWelcome.Mace"), null);
							player.ReceiveItem(this,WEAPON_ID2);
							break;
						case "thrusting":
						case "찌르기":
							PromotePlayer(player, (int)eCharacterClass.Paladin, LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.PaladinWelcome.Rapier"), null);
							player.ReceiveItem(this,WEAPON_ID3);
							break;
						case "two handed":
						case "양손":
							PromotePlayer(player, (int)eCharacterClass.Paladin, LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.PaladinWelcome.GreatSword"), null);
							player.ReceiveItem(this,WEAPON_ID4);
							break;
				}
			}
			return true;
		}
	}
}
