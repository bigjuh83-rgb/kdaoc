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
    }
}
