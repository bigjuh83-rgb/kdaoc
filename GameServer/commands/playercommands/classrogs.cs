namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&classrog",
        ePrivLevel.Player,
        "50레벨에는 현재 클래스와 맞지 않는 ROG 획득 확률을," +
        " 50레벨 미만에는 전문화와 맞는 아이템 획득 확률을 조정합니다.",
        "/classrog <%확률>")]
    public class ClassRogsCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            int ROGCap = 0;
            int cachedInput = 0;

            if (args.Length < 2)
            {
                DisplaySyntax(client);
                DisplayMessage(client, T(client, "PlayerCommands.ClassRog.CurrentCap", ROGCap));
                return;
            }

            if (!int.TryParse(args[1], out cachedInput))
            {
                DisplaySyntax(client);
                DisplayMessage(client, T(client, "PlayerCommands.ClassRog.CurrentCap", ROGCap));
                return;
            }

            if ( cachedInput > ROGCap)
            {
                DisplayMessage(client, T(client, "PlayerCommands.ClassRog.InputTooHigh", ROGCap));
                cachedInput = ROGCap;
            }
            else if (cachedInput < 0)
            {
                DisplayMessage(client, T(client, "PlayerCommands.ClassRog.InputTooLow", ROGCap));
                return;
            }

            client.Player.OutOfClassROGPercent = cachedInput;

            if(client.Player.Level == 50)
                DisplayMessage(client, T(client, "PlayerCommands.ClassRog.Updated", client.Player.OutOfClassROGPercent));
            else
            {
                //DisplayMessage(client, "You are now " + client.Player.OutOfClassROGPercent + "% more likely to get ROGs relevant to your spec.");
            }
        }
    }
}
