using DOL.GS.PacketHandler;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_GameNPC
    {
        [TestCase("KR", eChatLoc.CL_PopupWindow, true)]
        [TestCase("kr", eChatLoc.CL_PopupWindow, true)]
        [TestCase("EN", eChatLoc.CL_PopupWindow, false)]
        [TestCase("KR", eChatLoc.CL_ChatWindow, false)]
        [TestCase("KR", eChatLoc.CL_SystemWindow, false)]
        public void ShouldUseCustomTextWindowForSayTo_ShouldOnlyRouteKoreanPopups(string language, eChatLoc loc, bool expected)
        {
            Assert.That(GameNPC.ShouldUseCustomTextWindowForSayTo(language, loc), Is.EqualTo(expected));
        }

        [TestCase("KR", eChatLoc.CL_PopupWindow, "안녕하세요.", true)]
        [TestCase("KR", eChatLoc.CL_PopupWindow, "[Castle Sauvage] 소바쥬 성", false)]
        [TestCase("KR", eChatLoc.CL_PopupWindow, "[히어로]로 훈련받겠습니까?", false)]
        [TestCase("EN", eChatLoc.CL_PopupWindow, "[Castle Sauvage]", false)]
        public void ShouldUseCustomTextWindowForSayTo_ShouldPreserveNpcHotspots(string language, eChatLoc loc, string message, bool expected)
        {
            Assert.That(GameNPC.ShouldUseCustomTextWindowForSayTo(language, loc, message), Is.EqualTo(expected));
        }
    }
}
