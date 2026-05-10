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

namespace DOL.GS.Trainer
{
	/// <summary>
	/// Elementalist Trainer
	/// </summary>
	[NPCGuildScript("Elementalist Trainer", eRealm.Albion)]		// this attribute instructs DOL to use this script for all "Elementalist Trainer" NPC's in Albion (multiple guilds are possible for one script)
	public class ElementalistTrainer : GameTrainer
	{
		public override eCharacterClass TrainedClass
		{
			get { return eCharacterClass.Elementalist; }
		}

		public const string PRACTICE_WEAPON_ID = "trimmed_branch";


		public ElementalistTrainer() : base(eChampionTrainerType.Elementalist)
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

			// check if class matches
			if (player.CharacterClass.ID == (int)TrainedClass)
			{
				// player can be promoted
				if (player.Level>=5)
				{
					player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.ElementalistPaths", this.Name), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
				}
				else
				{
					OfferTraining(player);
				}

				// ask for basic equipment if player doesnt own it
				if (player.Inventory.GetFirstItemByID(PRACTICE_WEAPON_ID, eInventorySlot.MinEquipable, eInventorySlot.LastBackpack) == null)
				{
					player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "StarterTrainer.PracticeWeapon", this.Name),eChatType.CT_Say,eChatLoc.CL_PopupWindow);
				}
			}
			else
			{
				CheckChampionTraining(player);
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

			switch (text) {
					case "Theurgist":
					case "시어지스트":
						if(player.Race == (int) eRace.Briton || player.Race == (int) eRace.Avalonian || player.Race == (int) eRace.HalfOgre){
							player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.Elementalist.Info.Theurgist", this.Name), eChatType.CT_Say,eChatLoc.CL_PopupWindow);
						}
					else{
						player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "StarterTrainer.ClassUnavailable", this.Name, "Theurgist"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
					}
					return true;
					case "Wizard":
					case "위저드":
						if(player.Race == (int) eRace.Briton || player.Race == (int) eRace.Avalonian || player.Race == (int) eRace.HalfOgre){
							player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.Elementalist.Info.Wizard", this.Name), eChatType.CT_Say,eChatLoc.CL_PopupWindow);
						}
					else{
						player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "StarterTrainer.ClassUnavailable", this.Name, "Wizard"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
					}
					return true;
				case "practice weapon":
				case "연습용 무기":
					if (player.Inventory.GetFirstItemByID(PRACTICE_WEAPON_ID, eInventorySlot.Min_Inv, eInventorySlot.Max_Inv) == null)
					{
						player.ReceiveItem(this,PRACTICE_WEAPON_ID);
					}
					return true;
			}
			return true;
		}
	}
}
