using DOL.GS.PacketHandler;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_PacketEncoding
    {
        [Test]
        public void DecryptPacket168_WithCarryFromLowLengthByte_DecryptsFullPacket()
        {
            PacketEncoding168 encoding = new()
            {
                EncryptionState = eEncryptionState.RSAEncrypted,
                SBox = CreateIdentitySBox()
            };
            byte[] packet = CreatePacketWithCarryingLength();
            byte original = packet[400];

            encoding.DecryptPacket(packet, 0, false);

            Assert.That(packet[400], Is.Not.EqualTo(original));
        }

        [Test]
        public void DecryptPacket1110_WithCarryFromLowLengthByte_DecryptsFullPacket()
        {
            PacketEncoding1110 encoding = new()
            {
                EncryptionState = eEncryptionState.RSAEncrypted,
                SBox = CreateIdentitySBox()
            };
            byte[] packet = CreatePacketWithCarryingLength();
            byte original = packet[400];

            encoding.DecryptPacket(packet, 0, false);

            Assert.That(packet[400], Is.Not.EqualTo(original));
        }

        private static byte[] CreatePacketWithCarryingLength()
        {
            byte[] packet = new byte[520];
            packet[0] = 0x01;
            packet[1] = 0xF6;

            for (int i = 2; i < packet.Length; i++)
                packet[i] = (byte)i;

            return packet;
        }

        private static byte[] CreateIdentitySBox()
        {
            byte[] sbox = new byte[256];

            for (int i = 0; i < sbox.Length; i++)
                sbox[i] = (byte)i;

            return sbox;
        }
    }
}
