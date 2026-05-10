using System.Collections.Generic;
using DOL.GS.PacketHandler;

namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&kotest",
        ePrivLevel.GM,
        "Send Korean text to yourself for encoding tests.",
        "/kotest")]
    public class KoreanTestCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            const string message = "한글 테스트 가나다라마바사";

            client.Out.SendMessage("[System] " + message, eChatType.CT_System, eChatLoc.CL_SystemWindow);
            client.Out.SendMessage("[Chat] " + message, eChatType.CT_Broadcast, eChatLoc.CL_ChatWindow);
            client.Out.SendMessage("[Popup] " + message, eChatType.CT_System, eChatLoc.CL_PopupWindow);
            client.Out.SendCustomTextWindow("Korean Test", new List<string> { message });
        }
    }
}
