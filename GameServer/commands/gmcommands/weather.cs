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

namespace DOL.GS.Commands
{
	[Cmd(
		"&weather",
		ePrivLevel.GM,
		"GMCommands.Weather.Description",
		"GMCommands.Weather.Usage.Info",
		"GMCommands.Weather.Usage.StartWithArgs",
		"GMCommands.Weather.Usage.Start",
		"GMCommands.Weather.Usage.Restart",
		"GMCommands.Weather.Usage.Stop")]
	public class WeatherCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		/// <summary>
		/// Execute Weather Command
		/// </summary>
		public void OnCommand(GameClient client, string[] args)
		{
			if (args.Length >= 2)
			{
				var action = args[1].ToLower();

				switch (action)
				{
					case "info":
						break;
					case "restart":
						if (GameServer.Instance.WorldManager.WeatherManager.RestartWeather(client.Player.CurrentRegionID))
							DisplayMessage(client, T(client, "GMCommands.Weather.Restart.Success"));
						else
							DisplayMessage(client, T(client, "GMCommands.Weather.Restart.Failed"));
						break;
					case "stop":
						if (GameServer.Instance.WorldManager.WeatherManager.StopWeather(client.Player.CurrentRegionID))
							DisplayMessage(client, T(client, "GMCommands.Weather.Stop.Success"));
						else
							DisplayMessage(client, T(client, "GMCommands.Weather.Stop.Failed"));
						break;
					case "start":
						if (args.Length > 2)
						{
							try
							{
								uint position = Convert.ToUInt32(args[2]);
								uint width = Convert.ToUInt32(args[3]);
								ushort speed = Convert.ToUInt16(args[4]);
								ushort diffusion = Convert.ToUInt16(args[5]);
								ushort intensity = Convert.ToUInt16(args[6]);
								if (!GameServer.Instance.WorldManager.WeatherManager.StartWeather(client.Player.CurrentRegionID, position, width, speed, diffusion, intensity))
								{
									DisplayMessage(client, T(client, "GMCommands.Weather.Start.Failed"));
									break;
								}
							}
							catch
							{
								DisplayMessage(client, T(client, "GMCommands.Weather.Start.WrongArguments"));
								DisplaySyntax(client);
								return;
							}
						}
						else
						{
							if (!GameServer.Instance.WorldManager.WeatherManager.StartWeather(client.Player.CurrentRegionID))
							{
								DisplayMessage(client, T(client, "GMCommands.Weather.Start.Failed"));
								break;
							}
						}

						DisplayMessage(client, T(client, "GMCommands.Weather.Start.Success"));
						break;
				}
				PrintInfo(client);
				return;
			}

			DisplaySyntax(client);
		}

		/// <summary>
		/// Display Weather Info to Client
		/// </summary>
		/// <param name="client"></param>
		public void PrintInfo(GameClient client)
		{
			var weather = GameServer.Instance.WorldManager.WeatherManager[client.Player.CurrentRegionID];

			if (weather == null)
			{
				DisplayMessage(client, T(client, "GMCommands.Weather.Info.NotRegistered"));
			}
			else
			{
				if (weather.StartTime == 0)
					DisplayMessage(client, T(client, "GMCommands.Weather.Info.Stopped"));
				else
					DisplayMessage(client, T(client, "GMCommands.Weather.Info.CurrentPosition", weather.CurrentPosition(Scheduler.SimpleScheduler.Ticks), weather));
			}
		}
	}
}
