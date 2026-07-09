namespace DOL.GS.PacketHandler.Client.v168
{
	[PacketHandlerAttribute(PacketHandlerType.UDP, eClientPackets.UDPInitRequest, "Handles UDP init", eClientStatus.None)]
	public class UDPInitRequestHandler : PacketHandler
	{
		protected override void HandlePacketInternal(GameClient client, GSPacketIn packet)
		{
			TryReadLocalEndpoint(packet, client.Version, out string localIP, out ushort localPort);
			client.LocalIP = localIP;
			// client.UdpEndPoint = new IPEndPoint(IPAddress.Parse(localIP), localPort);
			client.Out.SendUDPInitReply();
		}

		public static bool TryReadLocalEndpoint(GSPacketIn packet, GameClient.eClientVersion version, out string localIP, out ushort localPort)
		{
			localPort = 0;

			int ipLength = version >= GameClient.eClientVersion.Version1124 ? 20 : 22;
			localIP = packet.ReadString(ipLength);

			if (packet.Length - packet.Position < 2)
				return false;

			localPort = packet.ReadShort();
			return true;
		}
	}
}
