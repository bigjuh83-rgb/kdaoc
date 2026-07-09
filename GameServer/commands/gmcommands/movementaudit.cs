using DOL.GS.PacketHandler;

namespace DOL.GS.Commands
{
    [CmdAttribute("&movementaudit",
        ePrivLevel.Player,
        "Toggle server-side movement packet audit for the current player",
        "/movementaudit status [playerName]",
        "/movementaudit on [playerName] [full]",
        "/movementaudit off [playerName]")]
    public class MovementAuditCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (client?.Player == null)
                return;

            if (args.Length < 2)
            {
                DisplaySyntax(client);
                return;
            }

            string action = args[1].ToLowerInvariant();
            GamePlayer target = ResolveTarget(client, args.Length >= 3 ? args[2] : string.Empty);
            if (target == null)
                return;

            switch (action)
            {
                case "on":
                    bool full = args.Length >= 4 && args[3].ToLowerInvariant() == "full";
                    MovementAudit.Enable(target, full);
                    DisplayMessage(client, $"movement audit enabled for {target.Name} ({(full ? "full" : "normal")})");
                    return;
                case "off":
                    MovementAudit.Disable(target);
                    DisplayMessage(client, $"movement audit disabled for {target.Name}");
                    return;
                case "status":
                    DisplayMessage(client, $"movement audit for {target.Name}: {(MovementAudit.IsEnabled(target) ? "on" : "off")}");
                    return;
                default:
                    DisplaySyntax(client);
                    return;
            }
        }

        private GamePlayer ResolveTarget(GameClient client, string name)
        {
            if (string.IsNullOrWhiteSpace(name))
                return client.Player;

            if (client.Account.PrivLevel < (uint)ePrivLevel.GM && !name.Equals(client.Player.Name, System.StringComparison.OrdinalIgnoreCase))
            {
                DisplayMessage(client, "movement audit can only target your own character.");
                return null;
            }

            GamePlayer target = ClientService.Instance.GetPlayerByExactName(name);
            if (target == null)
                DisplayMessage(client, $"player not found: {name}");
            return target;
        }
    }
}
