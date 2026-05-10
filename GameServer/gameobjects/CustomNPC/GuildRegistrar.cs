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

using DOL.Language;

namespace DOL.GS
{
	/// <summary>
	/// Guild Registrar
	/// </summary>
	[NPCGuildScript("Guild Registrar")]
	public class GuildRegistrar : GameNPC
	{
		protected const string FORM_A_GUILD = "form a guild";

		public override bool Interact(GamePlayer player)
		{
			if (!base.Interact(player))
				return false;

			SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "GuildRegistrar.Interact.FormGuildPrompt", player.CharacterClass.Name, FORM_A_GUILD));

			return true;
		}

		public override bool WhisperReceive(GameLiving source, string text)
		{
			if (!base.WhisperReceive(source, text))
				return false;
			if (source is GamePlayer == false)
				return true;
			GamePlayer player = (GamePlayer) source;

			switch (text)
			{
				case FORM_A_GUILD:
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "GuildRegistrar.Whisper.FormGuildInstructions", ServerProperties.Properties.GUILD_NUM));
					break;
			}

			return true;
		}
	}
}
