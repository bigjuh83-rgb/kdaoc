using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute("&checkconcolor", ePrivLevel.Player, "대상의 난이도 색상을 서버 기준으로 확인합니다.", "/checkconcolor")]
    public class CheckConColorCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (IsSpammingCommand(client.Player, "checkconcolor"))
                return;

            GamePlayer player = client.Player;
            GameObject target = player.TargetObject;

            if (target == null)
            {
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.CheckConColor.RequiresTarget"), eChatType.CT_SpellResisted, eChatLoc.CL_SystemWindow);
                return;
            }

            client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.CheckConColor.Result", ConLevels.GetConColor(ConLevels.GetConLevel(player.EffectiveLevel, target.EffectiveLevel))), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
        }
    }
}
