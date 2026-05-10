using DOL.GS.Housing;

namespace DOL.GS.PacketHandler.Client.v168
{
    [PacketHandlerAttribute(PacketHandlerType.TCP, eClientPackets.HouseEnterLeave, "Housing Enter Leave Request.", eClientStatus.PlayerInGame)]
    public class HouseEnterLeaveHandler : PacketHandler
    {
        protected override void HandlePacketInternal(GameClient client, GSPacketIn packet)
        {
            int pid = packet.ReadShort();
            int houseNumber = packet.ReadShort();
            int enter = packet.ReadByte();
            House house = HouseMgr.GetHouse(houseNumber);

            if (house == null)
                return;

            GamePlayer player = client.Player;

            switch (enter)
            {
                case 0:
                {
                    player.LeaveHouse();
                    break;
                }
                case 1:
                {
                    if (!player.IsWithinRadius(house, 1000) || (player.CurrentRegionID != house.RegionID))
                    {
                        ChatUtil.SendSystemMessage(player, "HouseEnterLeave.TooFarAway", house.HouseNumber);
                        return;
                    }

                    if (house.CanEnterHome(player))
                    {
                        player.CurrentHouse = house;
                        house.Enter(player);
                    }
                    else
                        ChatUtil.SendSystemMessage(player, "HouseEnterLeave.CantEnter", house.HouseNumber);

                    break;
                }
            }
        }
    }
}
