using System;
using DOL.GS.PacketHandler;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&setwho",
		ePrivLevel.Player,
		"/who 출력에 표시할 클래스 또는 제작 직업을 설정합니다.",
		"/setwho 클래스 | 제작")]
	public class SetWhoCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (IsSpammingCommand(client.Player, "setwho"))
				return;

			if (args.Length < 2)
			{
				DisplayMessage(client, T(client, "PlayerCommands.SetWho.Specify"));
				return;
			}

			var played = client.Player.PlayedTimeSinceLevel / 60 / 60; // Sets time played since last level
			var totalPlayed = client.Player.PlayedTime / 60 / 60; // Time played total for character

			string displayMode = NormalizeDisplayMode(args[1]);

			if (client.Player.Level == 50 && played < 15 && displayMode == "class" && !client.Player.ClassNameFlag && client.Player.Advisor || client.Player.Level != 50 && totalPlayed < 15 && client.Player.Advisor && displayMode == "class" && !client.Player.ClassNameFlag)
			{
				// Message: "You cannot turn off your craft title while your Advisor flag is active, as you do not meet the other level and/or time played requirements."
				ChatUtil.SendSystemMessage(client, "PLCommands.SetWho.Err.CraftAdvisor", null);
				return;
			}

			if (displayMode == "class")
				client.Player.ClassNameFlag = true;
			else if (displayMode == "trade")
			{
				if (client.Player.CraftingPrimarySkill == eCraftingSkill.NoCrafting)
				{
					DisplayMessage(client, T(client, "PlayerCommands.SetWho.NeedProfession"));
					return;
				}

				client.Player.ClassNameFlag= false;
			}
			else
			{
				DisplayMessage(client, T(client, "PlayerCommands.SetWho.Specify"));
				return;
			}

			if (client.Player.ClassNameFlag)
				DisplayMessage(client, T(client, "PlayerCommands.SetWho.HideCraftTitle"));
			else
				DisplayMessage(client, T(client, "PlayerCommands.SetWho.ShowCraftTitle"));
		}

		private static string NormalizeDisplayMode(string mode)
		{
			return mode?.Trim().ToLowerInvariant() switch
			{
				"클래스" => "class",
				"직업" => "class",
				"제작" => "trade",
				"제작직업" => "trade",
				"제작기술" => "trade",
				_ => mode?.Trim().ToLowerInvariant()
			};
		}
	}
}
