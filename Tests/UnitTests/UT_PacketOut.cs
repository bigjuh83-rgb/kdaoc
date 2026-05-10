using DOL.GS.PacketHandler;
using DOL.Network;
using NUnit.Framework;
using System.Collections.Generic;
using System.Linq;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_PacketOut
    {
        [Test]
        public void WriteDialogMessage_WithKoreanText_ShouldKeepAllDefaultEncodedBytesAndNullTerminate()
        {
            const string message = "한글 확인";
            byte[] expectedTextBytes = BaseServer.DefaultEncoding.GetBytes(message);
            GSTCPPacketOut packet = new();

            TestPacketLib168.WriteDialogMessageForTest(packet, message);

            byte[] actual = packet.ToArray();
            Assert.That(actual.Length, Is.EqualTo(expectedTextBytes.Length + 1));
            Assert.That(actual[..expectedTextBytes.Length], Is.EqualTo(expectedTextBytes));
            Assert.That(actual[^1], Is.EqualTo(0));
        }

        [Test]
        public void WriteCustomTextWindowData_WithLongKoreanText_ShouldSplitByDefaultEncodedByteLength()
        {
            string message = new('가', 180);
            byte[] expectedTextBytes = BaseServer.DefaultEncoding.GetBytes(message);
            GSTCPPacketOut packet = new();

            TestPacketLib168.WriteCustomTextWindowDataForTest(packet, new List<string> { message });

            byte[] actual = packet.ToArray();
            List<byte> reconstructed = [];
            int position = 0;
            int line = 1;

            while (position < actual.Length)
            {
                Assert.That(actual[position++], Is.EqualTo(line++));
                int lineLength = actual[position++];
                Assert.That(lineLength, Is.LessThanOrEqualTo(byte.MaxValue));
                reconstructed.AddRange(actual.Skip(position).Take(lineLength));
                position += lineLength;
            }

            Assert.That(line, Is.GreaterThan(2));
            Assert.That(reconstructed.ToArray(), Is.EqualTo(expectedTextBytes));
        }

        [Test]
        public void WriteCustomTextWindowData_WhenNearPacketLimit_ShouldReserveTrailingZero()
        {
            GSTCPPacketOut packet = new();
            packet.Fill(0xEE, 2040);

            TestPacketLib168.WriteCustomTextWindowDataForTest(packet, new List<string> { new('가', 20) });

            Assert.That(packet.Position, Is.LessThanOrEqualTo(2047));
            packet.WriteByte(0);
            Assert.That(packet.Position, Is.LessThanOrEqualTo(2048));
        }

        [Test]
        public void WriteCustomTextWindowString_WithKoreanText_ShouldWriteDefaultEncodedPascalString()
        {
            const string message = "렐름 상태";
            byte[] expectedTextBytes = BaseServer.DefaultEncoding.GetBytes(message);
            GSTCPPacketOut packet = new();

            TestPacketLib168.WriteCustomTextWindowStringForTest(packet, message);

            byte[] actual = packet.ToArray();
            Assert.That(actual[0], Is.EqualTo(expectedTextBytes.Length));
            Assert.That(actual.Skip(1).ToArray(), Is.EqualTo(expectedTextBytes));
        }

        [Test]
        public void TakeEncodedChunk_WithLongKoreanText_ShouldCapByDefaultEncodedByteLength()
        {
            string message = new('가', 200);
            string chunk = TestPacketLib168.TakeEncodedChunkStringForTest(message, byte.MaxValue);

            Assert.That(BaseServer.DefaultEncoding.GetByteCount(chunk), Is.LessThanOrEqualTo(byte.MaxValue));
            Assert.That(chunk.Length, Is.LessThan(message.Length));

            GSTCPPacketOut packet = new();
            Assert.DoesNotThrow(() => TestPacketLib168.WriteCustomTextWindowStringForTest(packet, chunk));
        }

        private sealed class TestPacketLib168 : PacketLib168
        {
            private TestPacketLib168()
                : base(null)
            {
            }

            public static void WriteDialogMessageForTest(GSTCPPacketOut packet, string message)
            {
                WriteDialogMessage(packet, message);
            }

            public static void WriteCustomTextWindowDataForTest(GSTCPPacketOut packet, IList<string> text)
            {
                WriteCustomTextWindowData(packet, text);
            }

            public static void WriteCustomTextWindowStringForTest(GSTCPPacketOut packet, string message)
            {
                WriteCustomTextWindowString(packet, message);
            }

            public static string TakeEncodedChunkStringForTest(string message, int maxByteCount)
            {
                return TakeEncodedChunk(message, maxByteCount).ToString();
            }

        }
    }
}
