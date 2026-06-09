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
/***[ roll.cs ]****
* reqired DOL:	1.5.0
* author|date:	SEpHirOTH |	2004/02/25
* modificatio:  SmallHorse (just a little cleanup)
* modificatio:  noret (made it look like on live servers)
* description: enables the usage of "/roll" command
*		"/roll <n>" rolling with <n> dice
*		results will be sent to all players in emote range
******************/

using System;
using DOL.GS.PacketHandler;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&roll",
		ePrivLevel.Player,
		"주사위 굴림을 시뮬레이션합니다.",
		"/roll [#] 지정한 개수의 주사위를 굴립니다.")]
	public class RollCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		private const int RESULT_RANGE = 512; // emote range
		private const int MAX_DICE = 100;
		private const int ONE_DIE_MAX_VALUE = 6; // :)

		public void OnCommand(GameClient client, string[] args)
		{
			if (IsSpammingCommand(client.Player, "roll", 500))
			{
				DisplayMessage(client, T(client, "PlayerCommands.Common.SlowDown"));
				return;
			}

			// no args - display usage
			if (args.Length < 2)
			{
				SystemMessage(client, T(client, "PlayerCommands.Roll.Help"));
				return;
			}


			int dice; // number of dice to roll

			// trying to convert number
			try
			{
				dice = System.Convert.ToInt32(args[1]);
			}
			catch (OverflowException)
			{
				SystemMessage(client, T(client, "PlayerCommands.Roll.WrongNumber", MAX_DICE));
				return;
			}
			catch (Exception)
			{
				SystemMessage(client, T(client, "PlayerCommands.Roll.Help"));
				return;
			}

			if (dice < 1 || dice > MAX_DICE)
			{
				SystemMessage(client, T(client, "PlayerCommands.Roll.WrongNumber", MAX_DICE));
				return;
			}

			// throw result
			int thrown = Util.Random(dice, dice * ONE_DIE_MAX_VALUE);

			// building roll result msg
			// sending msg to player
			EmoteMessage(client, T(client, "PlayerCommands.Roll.ResultSelf", dice, thrown));

			// sending result & playername to all players in range
			foreach (GamePlayer player in client.Player.GetPlayersInRadius(RESULT_RANGE))
			{
				if (client.Player != player) // client gets unique message
					EmoteMessage(player, T(player, "PlayerCommands.Roll.ResultOther", client.Player.Name, dice, thrown)); // sending msg to other players
			}
		}

		// these are to make code look better
		private void SystemMessage(GameClient client, string str)
		{
			client.Out.SendMessage(str, eChatType.CT_System, eChatLoc.CL_SystemWindow);
		}

		private void EmoteMessage(GamePlayer player, string str)
		{
			EmoteMessage(player.Client, str);
		}

		private void EmoteMessage(GameClient client, string str)
		{
			client.Out.SendMessage(str, eChatType.CT_Emote, eChatLoc.CL_SystemWindow);
		}
	}
}
