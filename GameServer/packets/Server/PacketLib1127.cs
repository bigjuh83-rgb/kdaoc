using DOL.GS.Commands;

using System;

namespace DOL.GS.PacketHandler
{
    [PacketLib(1127, GameClient.eClientVersion.Version1127)]
    public class PacketLib1127 : PacketLib1126
    {
        public PacketLib1127(GameClient client) : base(client) { }

        /// 1127 login granted packet unchanged, work around for server type
        public override void SendLoginGranted(byte color)
        {
            // work around for character screen bugs when server type sent as 00 but player doesnt have a realm
            // 0x07 allows for characters in all realms
            using (var pak = PooledObjectFactory.GetForTick<GSTCPPacketOut>().Init(GetPacketCode(eServerPackets.LoginGranted)))
            {
                pak.WritePascalString(m_gameClient.Account.Name);
                pak.WritePascalString(GameServer.Instance.Configuration.ServerNameShort); //server name
                pak.WriteByte(0x05); //Server ID, seems irrelevant
                var type = color == 0 ? 7 : color;
                pak.WriteByte((byte)type); // 00 normal type?, 01 mordred type, 03 gaheris type, 07 ywain type
                pak.WriteByte(0x00); // Trial switch 0x00 - subbed, 0x01 - trial acc
                SendTCP(pak);
            }
        }

        public override void SendMessage(string msg, eChatType type, eChatLoc loc)
        {
            msg = LocalizeKnownKoreanMessage(msg);

            SnoopManager.CheckAndBroadcast(m_gameClient.Player, msg, type, loc);

            if (m_gameClient.DisabledChatTypes.Contains(type))
                return;

            SendRawMessage(msg, type, loc);
        }

        public override void SendRawMessage(string msg, eChatType type, eChatLoc loc)
        {
            if (m_gameClient.ClientState is GameClient.eClientState.CharScreen)
                return;

            msg = LocalizeKnownKoreanMessage(msg);

            var pak = PooledObjectFactory.GetForTick<GSTCPPacketOut>().Init(GetPacketCode(eServerPackets.Message));
            pak.WriteByte((byte) type);

            // The @@ prefix seems to be technically needed only for the send reply feature.
            // Otherwise the client is able to print to the correct window based on eChatType.
            // We're keeping it here in case something else still needs it (more research needed).
            if (type is eChatType.CT_Send)
                pak.WriteNonNullTerminatedString("@@");
            else if (loc is eChatLoc.CL_PopupWindow)
                pak.WriteNonNullTerminatedString("##");

            pak.WriteString(msg);
            SendTCP(pak);
        }

        private string LocalizeKnownKoreanMessage(string msg)
        {
            if (m_gameClient?.Account?.Language != "KR" || string.IsNullOrEmpty(msg))
                return msg;

            const string speedUpSelf = "Your speed greatly increases!";
            const string speedUpOtherSuffix = "'s speed greatly increases!";
            const string speedNormalSelf = "Your speed returns to normal.";
            const string speedNormalOtherSuffix = "'s speed returns to normal.";

            if (msg == speedUpSelf)
                return "이동 속도가 크게 증가합니다!";

            if (msg.EndsWith(speedUpOtherSuffix, StringComparison.Ordinal))
            {
                string name = msg.Substring(0, msg.Length - speedUpOtherSuffix.Length);
                return string.IsNullOrWhiteSpace(name)
                    ? msg
                    : $"{name}의 이동 속도가 크게 증가합니다!";
            }

            if (msg == speedNormalSelf)
                return "이동 속도가 정상으로 돌아옵니다.";

            if (msg.EndsWith(speedNormalOtherSuffix, StringComparison.Ordinal))
            {
                string name = msg.Substring(0, msg.Length - speedNormalOtherSuffix.Length);
                return string.IsNullOrWhiteSpace(name)
                    ? msg
                    : $"{name}의 이동 속도가 정상으로 돌아옵니다.";
            }

            return msg;
        }
    }
}
