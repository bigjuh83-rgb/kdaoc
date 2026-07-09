using DOL.Language;

namespace DOL.GS.PacketHandler.Client.v168
{
	[PacketHandlerAttribute(PacketHandlerType.TCP, eClientPackets.PickUpRequest, "Handles Pick up object request", eClientStatus.PlayerInGame)]
	public class PlayerPickUpRequestHandler : PacketHandler
	{
		protected override void HandlePacketInternal(GameClient client, GSPacketIn packet)
		{
			if (client.Player == null)
				return;

			TryReadPickUpRequestFields(packet, out _, out _, out _, out _);

			GameObject target = client.Player.TargetObject;
			if (target == null)
			{
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "PlayerPickUpRequestHandler.HandlePacket.Target"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				return;
			}
			if (target.ObjectState != GameObject.eObjectState.Active)
			{
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "PlayerPickUpRequestHandler.HandlePacket.InvalidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				return;
			}

			client.Player.PickupObject(target, false);
		}

		public static bool TryReadPickUpRequestFields(GSPacketIn packet, out uint x, out uint y, out ushort sessionId, out ushort objectId)
		{
			x = 0;
			y = 0;
			sessionId = 0;
			objectId = 0;

			if (packet.Length - packet.Position < 12)
				return false;

			x = packet.ReadInt();
			y = packet.ReadInt();
			sessionId = packet.ReadShort();
			objectId = packet.ReadShort();
			return true;
		}
	}
}
