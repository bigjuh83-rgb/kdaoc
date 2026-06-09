using System.Numerics;

namespace DOL.GS.Commands
{
    [CmdAttribute("&stuck",
        ePrivLevel.Player,
        "캐릭터를 마지막으로 기록된 안전 위치로 이동합니다.",
        "/stuck")]
    public class StuckCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (IsSpammingCommand(client.Player, "stuck"))
                return;

            GamePlayer player = client.Player;
            PlayerMovementComponent movementComponent = player.movementComponent;

            // Early exit if the currently set safe position cannot be used.
            if (!player.movementComponent.TryGetSafePosition(out Vector3 _))
            {
                DisplayMessage(client, T(client, "PlayerCommands.Stuck.NoSafePosition"));
                return;
            }

            movementComponent.UseSafePosition = true; // Will be reset if the quit timer is interrupted.

            if (!player.Quit(false))
                return;
        }
    }
}
