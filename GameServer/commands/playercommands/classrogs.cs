namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&classrog",
        ePrivLevel.Player,
        "change the chance% of getting ROGs outside of your current class at level 50," +
        " or the likelihood of getting items relevant to your spec while under 50",
        "/classrog <%chance>")]
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
