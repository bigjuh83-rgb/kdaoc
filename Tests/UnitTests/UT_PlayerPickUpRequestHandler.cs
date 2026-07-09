using DOL.GS.PacketHandler;
using DOL.GS.PacketHandler.Client.v168;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_PlayerPickUpRequestHandler
    {
        [Test]
        public void TryReadPickUpRequestFields_WithShortPayload_ShouldNotThrow()
        {
            GSPacketIn packet = new();
            packet.WriteByte(0x12);
            packet.WriteByte(0x34);
            packet.Position = 0;

            bool result = PlayerPickUpRequestHandler.TryReadPickUpRequestFields(packet, out uint x, out uint y, out ushort sessionId, out ushort objectId);

            Assert.That(result, Is.False);
            Assert.That(x, Is.Zero);
            Assert.That(y, Is.Zero);
            Assert.That(sessionId, Is.Zero);
            Assert.That(objectId, Is.Zero);
        }

        [Test]
        public void TryReadPickUpRequestFields_WithFullPayload_ShouldReadFields()
        {
            GSPacketIn packet = new();
            WriteInt(packet, 0x01020304);
            WriteInt(packet, 0x05060708);
            WriteShort(packet, 0x090A);
            WriteShort(packet, 0x0B0C);
            packet.Position = 0;

            bool result = PlayerPickUpRequestHandler.TryReadPickUpRequestFields(packet, out uint x, out uint y, out ushort sessionId, out ushort objectId);

            Assert.That(result, Is.True);
            Assert.That(x, Is.EqualTo(0x01020304));
            Assert.That(y, Is.EqualTo(0x05060708));
            Assert.That(sessionId, Is.EqualTo(0x090A));
            Assert.That(objectId, Is.EqualTo(0x0B0C));
        }

        private static void WriteInt(GSPacketIn packet, uint value)
        {
            packet.WriteByte((byte)((value >> 24) & 0xFF));
            packet.WriteByte((byte)((value >> 16) & 0xFF));
            packet.WriteByte((byte)((value >> 8) & 0xFF));
            packet.WriteByte((byte)(value & 0xFF));
        }

        private static void WriteShort(GSPacketIn packet, ushort value)
        {
            packet.WriteByte((byte)((value >> 8) & 0xFF));
            packet.WriteByte((byte)(value & 0xFF));
        }
    }
}
