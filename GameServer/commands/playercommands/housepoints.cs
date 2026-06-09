using DOL.GS;
using DOL.GS.Housing;
using DOL.GS.PacketHandler;

namespace DOL.GS.Commands
{
	[CmdAttribute(
	  "&housepoints",
	  ePrivLevel.Player,
	   "하우스 포인트 표시를 켜거나 끕니다.",
		 "사용법: /housepoints toggle")]
	public class HousePointsCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
            House house = client.Player.CurrentHouse;
			if (!client.Player.InHouse || house == null)
			{
                DisplayMessage(client, T(client, "PlayerCommands.HousePoints.NeedHouse"));
				return;
			}

            if (!house.HasOwnerPermissions(client.Player))
            {
                DisplayMessage(client, T(client, "PlayerCommands.Common.NoPermission"));
                return;
            }

			client.Player.Out.SendToggleHousePoints(house);
		}
	}
}
