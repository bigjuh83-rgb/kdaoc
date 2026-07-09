using System.Text;
using DOL.GS.PacketHandler;
using DOL.GS.PacketHandler.Client.v168;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_UDPInitRequestHandler
    {
        [Test]
        public void TryReadLocalEndpoint_WithVersion1127ShortPayload_ShouldNotThrow()
        {
            GSPacketIn packet = CreatePacket("192.168.0.4", 20, includePort: false);

            bool hasPort = UDPInitRequestHandler.TryReadLocalEndpoint(packet, GameClient.eClientVersion.Version1127, out string localIP, out ushort localPort);

            Assert.That(hasPort, Is.False);
            Assert.That(localIP, Is.EqualTo("192.168.0.4"));
            Assert.That(localPort, Is.Zero);
        }

        [Test]
        public void TryReadLocalEndpoint_WithVersion1127FullPayload_ShouldReadPort()
        {
            GSPacketIn packet = CreatePacket("192.168.0.4", 20, includePort: true);

            bool hasPort = UDPInitRequestHandler.TryReadLocalEndpoint(packet, GameClient.eClientVersion.Version1127, out string localIP, out ushort localPort);

            Assert.That(hasPort, Is.True);
            Assert.That(localIP, Is.EqualTo("192.168.0.4"));
            Assert.That(localPort, Is.EqualTo(10400));
        }

        [Test]
        public void TryReadLocalEndpoint_WithPre1124Payload_ShouldUseLegacyIpLength()
        {
            GSPacketIn packet = CreatePacket("10.0.0.5", 22, includePort: true);

            bool hasPort = UDPInitRequestHandler.TryReadLocalEndpoint(packet, GameClient.eClientVersion.Version1110, out string localIP, out ushort localPort);

            Assert.That(hasPort, Is.True);
            Assert.That(localIP, Is.EqualTo("10.0.0.5"));
            Assert.That(localPort, Is.EqualTo(10400));
        }

        private static GSPacketIn CreatePacket(string ipAddress, int ipFieldLength, bool includePort)
        {
            GSPacketIn packet = new();
            byte[] ipBytes = Encoding.ASCII.GetBytes(ipAddress);
            packet.Write(ipBytes, 0, ipBytes.Length);

            for (int i = ipBytes.Length; i < ipFieldLength; i++)
                packet.WriteByte(0);

            if (includePort)
            {
                packet.WriteByte(0x28);
                packet.WriteByte(0xA0);
            }

            packet.Position = 0;
            return packet;
        }
    }
}
