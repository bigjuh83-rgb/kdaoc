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

namespace DOL.GS
{
	/// <summary>
	/// Represents an in-game FaceCustomiser NPC
	/// </summary>
	public class FaceCustomiser : GameNPC
	{
		/// <summary>
		/// Spell id of the magical effect
		/// </summary>
		public const int EFFECT_ID = 5924;

		/// <summary>
		/// The cast time delay in milliseconds
		/// </summary>
		public const int CAST_TIME = 2000;

		/// <summary>
		/// Constructor
		/// </summary>
		public FaceCustomiser () : base()
		{
		}

		/// <summary>
		/// Called when a player right clicks on the npc
		/// </summary>
		/// <param name="player">Player that interacting</param>
		/// <returns>True if succeeded</returns>
		public override bool Interact(GamePlayer player)
		{
			if (!base.Interact(player))
				return false;

			TurnTo(player, 5000);

			if(player.CustomisationStep == 2)
			{
				SayTo(player, eChatLoc.CL_PopupWindow, LanguageMgr.GetTranslation(player.Client.Account.Language, "FaceCustomiser.Interact.Offer", player.CharacterClass.Name));
			}
			else if(player.CustomisationStep == 3)
			{
				SayTo(player, eChatLoc.CL_PopupWindow, LanguageMgr.GetTranslation(player.Client.Account.Language, "FaceCustomiser.Interact.AlreadyGranted"));
			}

			return true;
		}

		/// <summary>
		/// This function is called when the Living receives a whispered text
		/// </summary>
		/// <param name="source">GameLiving that was whispering</param>
		/// <param name="text">string that was whispered</param>
		/// <returns>true if the string correctly processed</returns>
		public override bool WhisperReceive(GameLiving source, string text)
		{
			if (!base.WhisperReceive(source, text))
				return false;

			GamePlayer player = source as GamePlayer;
			if (player == null)
				return false;

			string normalizedText = text.ToLowerInvariant();

			if (player.CustomisationStep == 2 && (normalizedText == "change your appearance" || text == "외형 변경"))
			{
				foreach(GamePlayer players in this.GetPlayersInRadius(WorldMgr.VISIBILITY_DISTANCE))
				{
					players.Out.SendSpellCastAnimation(this,EFFECT_ID,CAST_TIME);
				}
				new ECSGameTimer(player, new ECSGameTimer.ECSTimerCallback(EndCastCallback), CAST_TIME);

				SayTo(player, eChatLoc.CL_PopupWindow, LanguageMgr.GetTranslation(player.Client.Account.Language, "FaceCustomiser.Whisper.DoneLogoutRequired"));
				player.CustomisationStep = 3;
			}
			return true;
		}

		/// <summary>
		/// This function is called to show the spell animation to players
		/// </summary>
		/// <param name="callingTimer"></param>
		/// <returns>new delay in milliseconds</returns>
		protected virtual int EndCastCallback(ECSGameTimer callingTimer)
		{
			foreach(GamePlayer players in this.GetPlayersInRadius( WorldMgr.VISIBILITY_DISTANCE))
			{
				players.Out.SendSpellEffectAnimation(this,this,EFFECT_ID,0,false,0x01);
			}
			return 0;
		}
	}
}
