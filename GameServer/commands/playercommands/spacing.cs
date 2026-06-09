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
using DOL.GS.PacketHandler;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&spacing",
		ePrivLevel.Player,
		"소환수 간격을 변경합니다.", "/spacing {normal, big, huge}")]
	public class SpacingHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (IsSpammingCommand(client.Player, "spacing"))
				return;

			GamePlayer player = client.Player;

			//No one else needs to use this spell
			if (player.CharacterClass.ID != (int)eCharacterClass.Bonedancer)
			{
				DisplayMessage(player, T(player, "PlayerCommands.Spacing.OnlyBonedancers"));
				return;
			}

			//Help display
			if (args.Length == 1)
			{
				DisplayMessage(player, T(player, "PlayerCommands.Spacing.Commands"));
				DisplayMessage(player, T(player, "PlayerCommands.Spacing.NormalHelp"));
				DisplayMessage(player, T(player, "PlayerCommands.Spacing.BigHelp"));
				DisplayMessage(player, T(player, "PlayerCommands.Spacing.HugeHelp"));
				return;
			}

			//Check to see if the BD has a commander and minions
			if (player.ControlledBrain == null)
			{
				DisplayMessage(player, T(player, "PlayerCommands.Spacing.NoCommander"));
				return;
			}
			bool haveminion = false;
			foreach (AI.Brain.IControlledBrain icb in player.ControlledBrain.Body.ControlledNpcList)
			{
				if (icb != null)
					haveminion = true;
			}
			if (!haveminion)
			{
				DisplayMessage(player, T(player, "PlayerCommands.Spacing.NoMinions"));
				return;
			}

			switch (args[1].ToLower())
			{
				//Triangle Formation
				case "normal":
					player.ControlledBrain.Body.FormationSpacing = 1;
					break;
				//Line formation
				case "big":
					player.ControlledBrain.Body.FormationSpacing = 2;
					break;
				//Protect formation
				case "huge":
					player.ControlledBrain.Body.FormationSpacing = 3;
					break;
				default:
					DisplayMessage(player, T(player, "PlayerCommands.Spacing.Unrecognized", args[1]));
					break;
			}
		}
	}
}
