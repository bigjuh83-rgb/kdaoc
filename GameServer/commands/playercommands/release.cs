using System;

namespace DOL.GS.Commands
{
    [Cmd(
        "&release", ["&rel"],
        ePrivLevel.Player,
        "사망 중일 때 '/release'를 사용하면 바인드 지점으로 돌아갑니다.",
        "/release")]
    public class ReleaseCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (args.Length <= 1)
            {
                client.Player.Release(eReleaseType.Normal, false);
                return;
            }

            string toArgument = args[1];

            if (toArgument.Equals("city", StringComparison.OrdinalIgnoreCase))
            {
                client.Player.Release(eReleaseType.City, false);
                return;
            }

            if (toArgument.Equals("house", StringComparison.OrdinalIgnoreCase))
            {
                client.Player.Release(eReleaseType.House, false);
                return;
            }

            if (toArgument.Equals("bind", StringComparison.OrdinalIgnoreCase))
            {
                client.Player.Release(eReleaseType.Bind, false);
                return;
            }
        }
    }
}
