using System;
using DOL.GS.Housing;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&house",
		ePrivLevel.Player,
		"Show various housing information"
		)]
	public class HouseCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

		public void OnCommand(GameClient client, string[] args)
		{
			try
			{
				if (client.Account.PrivLevel > (int)ePrivLevel.Player)
				{
					if (args.Length > 1)
					{
						HouseAdmin(client.Player, args);
						return;
					}

					if (client.Account.PrivLevel >= (int)ePrivLevel.GM)
					{
						DisplayMessage(client, T(client, "PlayerCommands.House.HelpGmInfo"));
					}

					if (client.Account.PrivLevel == (int)ePrivLevel.Admin)
					{
						DisplayMessage(client, T(client, "PlayerCommands.House.HelpAdminModel"));
						DisplayMessage(client, T(client, "PlayerCommands.House.HelpAdminRestart"));
						DisplayMessage(client, T(client, "PlayerCommands.House.HelpAdminAddHookpoints"));
						DisplayMessage(client, T(client, "PlayerCommands.House.HelpAdminRemove"));
					}
				}

				House house = HouseMgr.GetHouseByPlayer(client.Player);

				if (house != null)
					house.SendHouseInfo(client.Player);
				else
					DisplayMessage(client, T(client, "PlayerCommands.House.NoHouseOwned"));
			}
			catch
			{
				DisplaySyntax(client);
			}
		}

		public void HouseAdmin(GamePlayer player, string [] args)
		{
			if (player.Client.Account.PrivLevel == (int)ePrivLevel.Admin)
			{
				if (args[1].ToLower() == "restart")
				{
					HouseMgr.Start(player.Client);
					return;
				}

				if (args[1].ToLower() == "addhookpoints")
				{
					if (player.TempProperties.GetProperty<bool>(HousingConstants.AllowAddHouseHookpoint))
					{
						player.TempProperties.RemoveProperty(HousingConstants.AllowAddHouseHookpoint);
						DisplayMessage(player.Client, T(player, "PlayerCommands.House.AddHookpointsOff"));
					}
					else
					{
						player.TempProperties.SetProperty(HousingConstants.AllowAddHouseHookpoint, true);
						DisplayMessage(player.Client, T(player, "PlayerCommands.House.AddHookpointsOn"));
					}

					return;
				}
			}

			var houses = HouseMgr.GetHousesCloseToSpot(player.CurrentRegionID, player.X, player.Y, 700);
			if (houses.Count != 1)
			{
				DisplayMessage(player.Client, T(player, "PlayerCommands.House.StandCloser"));
				return;
			}

			if (args[1].ToLower() == "info")
			{
				houses[0].SendHouseInfo(player);
				return;
			}

			// The following commands are for Admins only

			if (player.Client.Account.PrivLevel != (int)ePrivLevel.Admin)
				return;

			if (args[1].ToLower() == "model")
			{
				int newModel = Convert.ToInt32(args[2]);

				if (newModel < 1 || newModel > 12)
				{
					DisplayMessage(player.Client, T(player, "PlayerCommands.House.ValidModels"));
					return;
				}

				if (houses.Count == 1 && newModel != (houses[0] as House).Model)
				{
					HouseMgr.RemoveHouseItems(houses[0] as House);
					(houses[0] as House).Model = newModel;
					(houses[0] as House).SaveIntoDatabase();
					(houses[0] as House).SendUpdate();

					DisplayMessage(player.Client, T(player, "PlayerCommands.House.ModelChanged", newModel));
					GameServer.Instance.LogGMAction(player.Name + " changed house #" + (houses[0] as House).HouseNumber + " model to " + newModel);
				}

				return;
			}

			if (args[1].ToLower() == "remove")
			{
				string confirm = string.Empty;

				if (args.Length > 2)
					confirm = args[2];

				if (confirm != "YES")
				{
					DisplayMessage(player.Client, T(player, "PlayerCommands.House.ConfirmRemove"));
					return;
				}

				if (houses.Count == 1)
				{
					HouseMgr.RemoveHouse(houses[0] as House);
					DisplayMessage(player.Client, T(player, "PlayerCommands.House.Removed"));
					GameServer.Instance.LogGMAction(player.Name + " removed house #" + (houses[0] as House).HouseNumber);
				}

				return;
			}
		}
	}
}
