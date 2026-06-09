// using System;
//
// namespace DOL.GS.Commands
// {
// 	[CmdAttribute(
// 		"&shuffle",
// 		ePrivLevel.Player,
// 		"지정한 수의 덱을 섞습니다. 최소 1개이며 /deal 전에 사용해야 합니다.",
// 		"/shuffle <#>")]
// 	public class ShuffleCommandHandler : AbstractCommandHandler, ICommandHandler
// 	{
// 		public void OnCommand(GameClient client, string[] args)
// 		{
// 			if (args.Length < 2)
// 				return;
//
// 			int numDecks;
// 			try
// 			{
// 				numDecks = System.Convert.ToInt32(args[1]);
// 			}
// 			catch (Exception)
// 			{
// 				return;
// 			}
//
// 			if (numDecks > 0)
// 				CardMgr.Shuffle(client, (uint)numDecks);
// 		}
// 	}
// }