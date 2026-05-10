using DOL.GS.PacketHandler;
using DOL.Network;
using NUnit.Framework;
using System.IO;
using System.Text;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_PacketIn
    {
        [Test]
        public void ReadIntPascalStringLowEndian_WithUtf8Bytes_ShouldDecodeUtf8()
        {
            GSPacketIn packet = CreateIntPascalPacket(System.Text.Encoding.UTF8.GetBytes("가나다"));

            string result = packet.ReadIntPascalStringLowEndian();

            Assert.That(result, Is.EqualTo("가나다"));
        }

        [Test]
        public void ReadIntPascalStringLowEndian_WithCp949Bytes_ShouldFallbackToDefaultEncoding()
        {
            GSPacketIn packet = CreateIntPascalPacket(BaseServer.DefaultEncoding.GetBytes("가나다"));

            string result = packet.ReadIntPascalStringLowEndian();

            Assert.That(result, Is.EqualTo("가나다"));
        }

        [Test]
        public void ReadIntPascalStringLowEndian_WithCp949BytesThatAreValidUtf8_ShouldPreferDefaultEncoding()
        {
            GSPacketIn packet = CreateIntPascalPacket(BaseServer.DefaultEncoding.GetBytes("호호호"));

            string result = packet.ReadIntPascalStringLowEndian();

            Assert.That(result, Is.EqualTo("호호호"));
        }

        [Test]
        public void ReadString_WithLongNullTerminatedString_ShouldStopAtTerminator()
        {
            string expected = new('A', 1200);
            byte[] stringBytes = Encoding.ASCII.GetBytes(expected);
            byte[] trailingBytes = Encoding.ASCII.GetBytes(new string('B', 100));
            GSPacketIn packet = new();
            packet.Write(stringBytes, 0, stringBytes.Length);
            packet.WriteByte(0);
            packet.Write(trailingBytes, 0, trailingBytes.Length);
            packet.Position = 0;

            string result = packet.ReadString(stringBytes.Length + 1 + trailingBytes.Length);

            Assert.That(result, Is.EqualTo(expected));
        }

        [Test]
        public void ReadString_WithLongTruncatedString_ShouldDecodeOnlyBytesRead()
        {
            string expected = new('A', 1200);
            byte[] stringBytes = Encoding.ASCII.GetBytes(expected);
            GSPacketIn packet = new();
            packet.Write(stringBytes, 0, stringBytes.Length);
            packet.Position = 0;

            string result = packet.ReadString(stringBytes.Length + 100);

            Assert.That(result, Is.EqualTo(expected));
        }

        [Test]
        public void ReadIntPascalStringLowEndian_WithTruncatedPayload_ShouldDecodeOnlyBytesRead()
        {
            GSPacketIn packet = new();
            byte[] stringBytes = Encoding.UTF8.GetBytes("가나");
            WriteIntLowEndian(packet, stringBytes.Length + 10);
            packet.Write(stringBytes, 0, stringBytes.Length);
            packet.Position = 0;

            string result = packet.ReadIntPascalStringLowEndian();

            Assert.That(result, Is.EqualTo("가나"));
        }

        [Test]
        public void ReadIntPascalStringLowEndian_WithHugeMalformedLength_ShouldNotReturnEmptyOrUseStaleBytes()
        {
            GSPacketIn packet = new();
            byte[] stringBytes = Encoding.UTF8.GetBytes("abc");
            WriteIntLowEndian(packet, unchecked((int)0x80000000));
            packet.Write(stringBytes, 0, stringBytes.Length);
            packet.Position = 0;

            string result = packet.ReadIntPascalStringLowEndian();

            Assert.That(result, Is.EqualTo("abc"));
        }

        [Test]
        public void ReadShort_WithTruncatedHeader_ShouldThrowEndOfStream()
        {
            GSPacketIn packet = new();
            packet.WriteByte(0x12);
            packet.Position = 0;

            Assert.Throws<EndOfStreamException>(() => packet.ReadShort());
        }

        [Test]
        public void ReadInt_WithTruncatedHeader_ShouldThrowEndOfStream()
        {
            GSPacketIn packet = new();
            packet.WriteByte(0x12);
            packet.WriteByte(0x34);
            packet.WriteByte(0x56);
            packet.Position = 0;

            Assert.Throws<EndOfStreamException>(() => packet.ReadInt());
        }

        private static GSPacketIn CreateIntPascalPacket(byte[] stringBytes)
        {
            GSPacketIn packet = new();
            int length = stringBytes.Length;

            WriteIntLowEndian(packet, length);
            packet.Write(stringBytes, 0, stringBytes.Length);
            packet.Position = 0;
            return packet;
        }

        private static void WriteIntLowEndian(GSPacketIn packet, int length)
        {
            packet.WriteByte((byte)(length & 0xFF));
            packet.WriteByte((byte)((length >> 8) & 0xFF));
            packet.WriteByte((byte)((length >> 16) & 0xFF));
            packet.WriteByte((byte)((length >> 24) & 0xFF));
        }
    }
}
