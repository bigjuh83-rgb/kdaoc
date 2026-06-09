using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&range",
        ePrivLevel.Player,
        "대상까지의 거리를 표시합니다.",
        "/range")]
    public class RangeCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (IsSpammingCommand(client.Player, "range"))
                return;

            GameObject targetObject = client.Player.TargetObject;

            if (targetObject == null)
                DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Range.NeedTarget"));

            if ((ePrivLevel) client.Account.PrivLevel <= ePrivLevel.Player && targetObject is GameLiving)
            {
                DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Range.InvalidObject"));
                return;
            }

            int range = client.Player.GetDistanceTo(targetObject);
            string targetNotInView = client.Player.TargetInView ? string.Empty : LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Range.NotVisible");
            DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Range.Result", range, targetNotInView));
        }
    }
}
