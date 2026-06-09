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

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&random",
		ePrivLevel.Player,
		"1부터 지정한 숫자 사이의 무작위 숫자를 출력합니다.",
		"/random [#] 1부터 지정한 숫자 사이의 무작위 숫자를 얻습니다.")]
	public class RandomCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		private const int RESULT_RANGE = 512; // emote range

		public void OnCommand(GameClient client, string[] args)
		{
			if (IsSpammingCommand(client.Player, "random", 500))
			{
				DisplayMessage(client, T(client, "PlayerCommands.Common.SlowDown"));
				return;
			}

			// no args - display usage
			if (args.Length < 2)
			{
				SystemMessage(client, T(client, "PlayerCommands.Random.Help"));
				return;
			}

			int thrownMax;

			// trying to convert number
			try
			{
				thrownMax = System.Convert.ToInt32(args[1]);
			}
			catch (OverflowException)
			{
				thrownMax = int.MaxValue - 1; // max+1 is used in GameObject.Random(int,int)
			}
			catch (Exception)
			{
				SystemMessage(client, T(client, "PlayerCommands.Random.Help"));
				return;
			}

			if (thrownMax < 2)
			{
				SystemMessage(client, T(client, "PlayerCommands.Random.LowNumber"));
				return;
			}

			// throw result
			int thrown = Util.Random(1, thrownMax);

			BattleGroup mybattlegroup = client.Player.TempProperties.GetProperty<BattleGroup>(BattleGroup.BATTLEGROUP_PROPERTY);
			if (mybattlegroup != null && mybattlegroup.IsRecordingRolls() && thrownMax <= mybattlegroup.GetRecordingThreshold())
			{
				mybattlegroup.AddRoll(client.Player, thrown);
			}

			// building result messages
			// sending msg to player
			EmoteMessage(client, T(client, "PlayerCommands.Random.ResultSelf", thrownMax, thrown));

			// sending result & playername to all players in range
			foreach (GamePlayer player in client.Player.GetPlayersInRadius(RESULT_RANGE))
			{
				if (client.Player != player) // client gets unique message
					EmoteMessage(player, T(player, "PlayerCommands.Random.ResultOther", client.Player.Name, thrownMax, thrown)); // sending msg to other players
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
