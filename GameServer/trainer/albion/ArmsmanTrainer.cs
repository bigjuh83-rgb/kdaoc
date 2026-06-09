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
	/// Armsman Trainer
	/// </summary>
	[NPCGuildScript("Armsman Trainer", eRealm.Albion)]		// this attribute instructs DOL to use this script for all "Fighter Trainer" NPC's in Albion (multiple guilds are possible for one script)
	public class ArmsmanTrainer : GameTrainer
	{
		public override eCharacterClass TrainedClass
		{
			get { return eCharacterClass.Armsman; }
		}
		/// <summary>
		/// The slash sword item template ID
		/// </summary>
		public const string WEAPON_ID1 = "slash_sword_item";
		/// <summary>
		/// The crush sword item template ID
		/// </summary>
		public const string WEAPON_ID2 = "crush_sword_item";
		/// <summary>
		/// The thrust sword item template ID
		/// </summary>
		public const string WEAPON_ID3 = "thrust_sword_item";
		/// <summary>
		/// The pike polearm item template ID
		/// </summary>
		public const string WEAPON_ID4 = "pike_polearm_item";

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
					player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.ArmsmanPrompt", this.Name), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
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
					case "join the Defenders of Albion":
					case "알비온 수호대 입단":

							player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.ArmsmanChooseWeapon", this.Name), eChatType.CT_Say,eChatLoc.CL_PopupWindow);

							break;
						case "slashing":
						case "베기":
						case "슬래쉬":

							PromotePlayer(player, (int)eCharacterClass.Armsman, LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.ArmsmanWelcome.Sword"), null);
							player.ReceiveItem(this,WEAPON_ID1);

							break;
						case "crushing":
						case "타격":
						case "크러쉬":

							PromotePlayer(player, (int)eCharacterClass.Armsman, LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.ArmsmanWelcome.Mace"), null);
							player.ReceiveItem(this,WEAPON_ID2);

							break;
						case "thrusting":
						case "찌르기":
						case "쓰러스트":

							PromotePlayer(player, (int)eCharacterClass.Armsman, LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.ArmsmanWelcome.Rapier"), null);
							player.ReceiveItem(this,WEAPON_ID3);

							break;
						case "polearms":
						case "폴암":

							PromotePlayer(player, (int)eCharacterClass.Armsman, LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.ArmsmanWelcome.Pike"), null);
							player.ReceiveItem(this,WEAPON_ID4);

						break;
				}
			}
			return true;
		}
	}
}
