using System;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&discard",
		ePrivLevel.Player,
		"손패의 지정한 카드를 버리거나 모든 카드를 버립니다.",
		"/discard <#|all>")]
	public class DiscardCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (args.Length < 2) return;
            if (args[1].Equals("all"))
                CardMgr.DiscardAll(client);
            else
            {
                try
                {
                    uint cardId = System.Convert.ToUInt32(args[1]);
                    CardMgr.Discard(client, cardId);
                }
                catch (Exception)
                {
					return;
                }
            }
		}
	}
}