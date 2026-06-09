namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&bind",
        ePrivLevel.Player,
        "영혼을 바인드 위치에 묶습니다. 사망 후 /release하면 그 위치에서 시작합니다.",
        "/bind")]
    public class BindCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (IsSpammingCommand(client.Player, "bind"))
                return;

            client.Player.Bind();
        }
    }
}
