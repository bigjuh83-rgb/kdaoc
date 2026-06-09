using DOL.GS.Housing;

namespace DOL.GS.Commands
{
	[CmdAttribute(
	  "&boot",
	  ePrivLevel.Player,
	   "플레이어를 내 집에서 내보냅니다.",
		 "사용법: /boot [플레이어이름]")]
	public class BootCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (IsSpammingCommand(client.Player, "boot"))
				return;

            House house = client.Player.CurrentHouse;
			if (house == null)
			{
                DisplayMessage(client, T(client, "Scripts.Players.Boot.InHouseError"));
				return;
			}

			// no permission to banish, return
			if (!house.CanBanish(client.Player))
			{
				DisplayMessage(client, T(client, "PlayerCommands.Common.NoPermission"));
				return;
			}

			// check each player, try and find player with the given name (lowercase cmp)
			foreach (GamePlayer player in house.GetAllPlayersInHouse())
			{
				if (player != client.Player && player.Name.ToLower() != args[1].ToLower())
				{
					ChatUtil.SendSystemMessage(client, "Scripts.Players.Boot.YouRemoved", client.Player.Name);
					player.LeaveHouse();

					return;
				}
			}

			ChatUtil.SendHelpMessage(client, "Scripts.Players.Boot.NoOneOnline", null);
		}
	}
}
