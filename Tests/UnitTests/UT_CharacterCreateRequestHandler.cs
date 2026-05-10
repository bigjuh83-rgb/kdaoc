using System;
using System.Reflection;
using System.Text;
using DOL.GS.PacketHandler;
using DOL.GS.PacketHandler.Client.v168;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_CharacterCreateRequestHandler
    {
        [Test]
        public void CreationCharacterData_With1126LocalizedNames_ShouldKeepClassAndRealmAligned()
        {
            GSPacketIn packet = CreateVersion1126CharacterCreatePacket();
            GameClient client = new(null) { Version = GameClient.eClientVersion.Version1126 };

            object data = CreateCreationCharacterData(packet, client);

            Assert.That(GetProperty<int>(data, "Class"), Is.EqualTo(33));
            Assert.That(GetProperty<int>(data, "Realm"), Is.EqualTo(2));
            Assert.That(GetProperty<int>(data, "Race"), Is.EqualTo(7));
            Assert.That(GetProperty<int>(data, "Gender"), Is.EqualTo(1));
            Assert.That(GetProperty<int>(data, "CreationModel"), Is.EqualTo(0x1234));
        }

        private static object CreateCreationCharacterData(GSPacketIn packet, GameClient client)
        {
            Type nestedType = typeof(CharacterCreateRequestHandler).GetNestedType("CreationCharacterData", BindingFlags.NonPublic);
            return Activator.CreateInstance(nestedType, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic, null, new object[] { packet, client }, null);
        }

        private static T GetProperty<T>(object instance, string propertyName)
        {
            PropertyInfo property = instance.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            object value = property.GetValue(instance);
            return (T)Convert.ChangeType(value, typeof(T));
        }

        private static GSPacketIn CreateVersion1126CharacterCreatePacket()
        {
            GSPacketIn packet = new();

            packet.WriteByte(11); // CharacterSlot.
            WriteIntPascalString(packet, "한글이름");
            WriteZeros(packet, 4);

            packet.WriteByte(0); // CustomMode.
            packet.WriteByte(1); // EyeSize.
            packet.WriteByte(2); // LipSize.
            packet.WriteByte(3); // EyeColor.
            packet.WriteByte(4); // HairColor.
            packet.WriteByte(5); // FaceType.
            packet.WriteByte(6); // HairStyle.
            WriteZeros(packet, 3);
            packet.WriteByte(7); // MoodType.
            WriteZeros(packet, 9);

            packet.WriteByte(1); // Operation.
            packet.WriteByte(3); // CustomizeType.
            WriteZeros(packet, 2);

            WriteIntPascalString(packet, "코츠월드");
            WriteIntPascalString(packet, "블레이드마스터");
            WriteIntPascalString(packet, "피르볼그");

            packet.WriteByte(33); // Class.
            packet.WriteByte(2); // Realm.
            packet.WriteByte(0x87); // Race 7, female.
            WriteShortLowEndian(packet, 0x1234);

            packet.WriteByte(60); // Strength.
            packet.WriteByte(70); // Dexterity.
            packet.WriteByte(80); // Constitution.
            packet.WriteByte(90); // Quickness.
            packet.WriteByte(50); // Intelligence.
            packet.WriteByte(40); // Piety.
            packet.WriteByte(30); // Empathy.
            packet.WriteByte(20); // Charisma.

            WriteZeros(packet, 43);
            packet.WriteByte(81); // NewConstitution.
            packet.Position = 0;
            return packet;
        }

        private static void WriteIntPascalString(GSPacketIn packet, string value)
        {
            byte[] bytes = Encoding.UTF8.GetBytes(value);
            WriteIntLowEndian(packet, bytes.Length);
            packet.Write(bytes, 0, bytes.Length);
        }

        private static void WriteIntLowEndian(GSPacketIn packet, int value)
        {
            packet.WriteByte((byte)(value & 0xFF));
            packet.WriteByte((byte)((value >> 8) & 0xFF));
            packet.WriteByte((byte)((value >> 16) & 0xFF));
            packet.WriteByte((byte)((value >> 24) & 0xFF));
        }

        private static void WriteShortLowEndian(GSPacketIn packet, int value)
        {
            packet.WriteByte((byte)(value & 0xFF));
            packet.WriteByte((byte)((value >> 8) & 0xFF));
        }

        private static void WriteZeros(GSPacketIn packet, int count)
        {
            for (int i = 0; i < count; i++)
                packet.WriteByte(0);
        }
    }
}
