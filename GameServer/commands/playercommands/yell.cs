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
using DOL.Language;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&yell",
		new string[] { "&y" },
		ePrivLevel.Player,
		"Yell something to other players around you",
		"/yell <message>")]
	public class YellCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			const string YELL_TICK = "YELL_Tick";
			long YELLTick = client.Player.TempProperties.GetProperty<long>(YELL_TICK);
			if (YELLTick > 0 && YELLTick - client.Player.CurrentRegion.Time <= 0)
			{
				client.Player.TempProperties.RemoveProperty(YELL_TICK);
			}

			long changeTime = client.Player.CurrentRegion.Time - YELLTick;
			if (changeTime < 750 && YELLTick > 0)
			{
				DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Speech.SlowDown"));
				return;
			}
            if (client.Player.IsMuted)
            {
                client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Yell.Muted"), eChatType.CT_Staff, eChatLoc.CL_SystemWindow);
                return;
            }

			if (args.Length < 2)
			{
				foreach (GamePlayer player in client.Player.GetPlayersInRadius(WorldMgr.YELL_DISTANCE))
				{
					if (player != client.Player)
					{
						ushort headingtemp = player.GetHeading(client.Player);
						ushort headingtotarget = (ushort)(headingtemp - player.Heading);
						string directionKey = string.Empty;
						if (headingtotarget < 0)
							headingtotarget += 4096;
						if (headingtotarget >= 3840 || headingtotarget <= 256)
							directionKey = "Scripts.Common.Direction.South";
						else if (headingtotarget > 256 && headingtotarget < 768)
							directionKey = "Scripts.Common.Direction.SouthWest";
						else if (headingtotarget >= 768 && headingtotarget <= 1280)
							directionKey = "Scripts.Common.Direction.West";
						else if (headingtotarget > 1280 && headingtotarget < 1792)
							directionKey = "Scripts.Common.Direction.NorthWest";
						else if (headingtotarget >= 1792 && headingtotarget <= 2304)
							directionKey = "Scripts.Common.Direction.North";
						else if (headingtotarget > 2304 && headingtotarget < 2816)
							directionKey = "Scripts.Common.Direction.NorthEast";
						else if (headingtotarget >= 2816 && headingtotarget <= 3328)
							directionKey = "Scripts.Common.Direction.East";
						else if (headingtotarget > 3328 && headingtotarget < 3840)
							directionKey = "Scripts.Common.Direction.SouthEast";
						player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "Scripts.Players.Yell.HelpFrom", client.Player.Name, LanguageMgr.GetTranslation(player.Client.Account.Language, directionKey)), eChatType.CT_Help, eChatLoc.CL_SystemWindow);
					}
					else
						client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Yell.HelpSelf"), eChatType.CT_Help, eChatLoc.CL_SystemWindow);
				}
				client.Player.TempProperties.SetProperty(YELL_TICK, client.Player.CurrentRegion.Time);
				return;
			}

			string message = string.Join(" ", args, 1, args.Length - 1);
			client.Player.Yell(message);
			client.Player.TempProperties.SetProperty(YELL_TICK, client.Player.CurrentRegion.Time);
			return;
		}
	}
}
