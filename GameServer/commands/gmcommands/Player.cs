using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;
using DOL.Events;
using DOL.GS.Effects;
using DOL.GS.Friends;
using DOL.GS.Housing;
using DOL.GS.PacketHandler;
using DOL.GS.Quests;

namespace DOL.GS.Commands
{
	[Cmd(
		"&player",
		ePrivLevel.GM,
		"Various Admin/GM commands to edit characters.",
		"/player name <newName>",
		"/player lastname <change|reset> <newLastName>",
		"/player level <newLevel>",
        "/player levelup",
        "/player reset - Reset and re-level a player to their current level.",
		"/player realm <newRealm>",
		"/player inventory [wear|bag|vault|house|cons]",
		"/player <rps|bps|xp|xpa|clxp|mlxp> <amount>",
		"/player stat <typeofStat> <value>",
		"/player money <copp|silv|gold|plat|mith> <amount>",
		"/player respec <all|line|realm|dol|champion> <amount=1>",
		"/player model <reset|[change]> <modelid>",
		"/player friend <list|playerName>",
		"/player <rez|kill> <albs|mids|hibs|self|all>", // if realm not specified, it will rez target.
		"/player jump <group|guild|cg|bg> <name>", // to jump a group to you, just type in a player's name and his or her entire group will come with.
		"/player kick <all>",
		"/player save <all>",
		"/player purge",
		"/player update",
		"/player info",
		"/player location - write a location string to the chat window",
		"/player showgroup",
		"/player showeffects",
		"/player startchampion - Starts the target on the path of the Champion.",
		"/player clearchampion - Remove all Champion XP and levels from this player.",
		"/player respecchampion - Respec this players Champion skills.",
		"/player saddlebags <0 - 15> - Set what horse saddlebags are active on this player",
		"/player startml - Start this players Master Level training.",
		"/player setml <level> - Set this players current Master Level.",
		"/player setmlstep <level> <step> [false] - Sets a step for an ML level to finished. 0 to set as unfinished.",
        "/player allchars <PlayerName>",
        "/player class <list|classID|className> - view a list of classes, or change the targets class.",
        "/player areas - list all the areas the player is currently inside of "
		)]
	public class PlayerCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

        public void OnCommand(GameClient client, string[] args)
        {
            if (args.Length == 1)
            {
                DisplaySyntax(client);
                return;
            }

            switch (args[1])
            {
                #region name

                case "name":
                    {
                        var player = client.Player.TargetObject as GamePlayer;
                        if (args.Length != 3)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null)
                            player = client.Player;

                        var character = DOLDB<DbCoreCharacter>.SelectObject(DB.Column("Name").IsEqualTo(args[2]));

                        if (character != null)
                        {
                            client.Out.SendMessage(T(client, "GMCommands.Player.DuplicateName"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        string oldName = player.Name;

                        player.Name = args[2];
                        player.Out.SendMessage(
                            T(player, "GMCommands.Player.TargetNameChanged", client.Player.Name, client.Account.PrivLevel, player.Name),
                            eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                        client.Out.SendMessage(T(client, "GMCommands.Player.NameChanged", player.Name),
                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                        client.Out.SendMessage(T(client, "GMCommands.Player.RelogToCompleteNameChange"), eChatType.CT_Important,
                                               eChatLoc.CL_SystemWindow);

                        // Log change
                        AuditMgr.AddAuditEntry(client, AuditType.Character, AuditSubtype.CharacterRename, oldName, args[2]);

                        player.SaveIntoDatabase();
                        break;
                    }

                #endregion

                #region lastname

                case "lastname":
                    {
                        var player = client.Player.TargetObject as GamePlayer;
                        if (args.Length > 4)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null)
                            player = client.Player;

                        switch (args[2])
                        {
                            case "change":
                                {
                                    player.LastName = args[3];
                                    player.Out.SendMessage(
                                        T(player, "GMCommands.Player.TargetLastnameChanged", client.Player.Name, client.Account.PrivLevel, player.LastName),
                                        eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    client.Out.SendMessage(T(client, "GMCommands.Player.LastnameChanged", player.Name, player.LastName),
                                                           eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    player.SaveIntoDatabase();
                                    break;
                                }

                            case "reset":
                                {
                                    player.LastName = null;
                                    client.Out.SendMessage(T(client, "GMCommands.Player.LastnameCleared", player.Name), eChatType.CT_Important,
                                                           eChatLoc.CL_SystemWindow);
                                    player.Out.SendMessage(
                                        T(player, "GMCommands.Player.TargetLastnameCleared", client.Player.Name, client.Account.PrivLevel),
                                        eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    player.SaveIntoDatabase();
                                    break;
                                }
                        }
                        break;
                    }

                #endregion

                #region level / reset
                case "levelup":
                    var pToLevel = client.Player.TargetObject as GamePlayer;
                    if (pToLevel == null)
                        pToLevel = client.Player;

                    if (pToLevel.Level != byte.MaxValue)
                    {
                        if (pToLevel.Level < 40 || pToLevel.IsLevelSecondStage)
                        {
                            pToLevel.Level++;

                            client.Out.SendMessage(T(client, "GMCommands.Player.GaveFreeLevel", pToLevel.Name),
                                                       eChatType.CT_Important, eChatLoc.CL_SystemWindow);

                            if (pToLevel != client.Player)
                                pToLevel.Out.SendMessage(
                                    T(pToLevel, "GMCommands.Player.TargetGivenFreeLevel", client.Player.Name, client.Account.PrivLevel),
                                    eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                        }
                        else
                        {
                            pToLevel.GainExperience(eXPSource.Other, pToLevel.ExperienceForCurrentLevelSecondStage - pToLevel.Experience);

                            client.Out.SendMessage(T(client, "GMCommands.Player.GaveFreeHalfLevel", pToLevel.Name),
                                                       eChatType.CT_Important, eChatLoc.CL_SystemWindow);

                            if (pToLevel != client.Player)
                                pToLevel.Out.SendMessage(
                                    T(pToLevel, "GMCommands.Player.TargetGivenFreeHalfLevel", client.Player.Name, client.Account.PrivLevel),
                                    eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                        }

                    }

                    break;
                case "reset":
                case "level":
                    {
                        try
                        {
                            var player = client.Player.TargetObject as GamePlayer;
                            if (player == null)
                                player = client.Player;

                            byte newLevel = player.Level;

                            if (args[1] == "level")
                            {
                                newLevel = Convert.ToByte(args[2]);
                            }

                            if (newLevel <= 0 || newLevel > 255)
                            {
                                client.Out.SendMessage(T(client, "GMCommands.Player.LevelRange", player.Name), eChatType.CT_Important,
                                                       eChatLoc.CL_SystemWindow);
                                return;
                            }

                            if (newLevel < player.Level || args[1] == "reset")
                            {
                                player.Reset();
                            }

                            int curLevel = player.Level;

                            if (newLevel > curLevel)
                            {
                                bool curSecondStage = player.IsLevelSecondStage;
                                if (newLevel > curLevel && curSecondStage)
                                {
                                    player.GainExperience(eXPSource.Other, player.GetExperienceValueForLevel(++curLevel));
                                }
                                if (newLevel != curLevel || !curSecondStage)
                                    player.Level = newLevel;

                                // If new level is more than 40, then we have
                                // to add the skill points from half-levels
                                if (newLevel > 40)
                                {
                                    if (curLevel < 40)
                                        curLevel = 40;
                                    for (int i = curLevel; i < newLevel; i++)
                                    {
                                        // we skip the first add if was in level 2nd stage
                                        if (curSecondStage)
                                            curSecondStage = false;
                                    }
                                }
                            }

                            if (args[1] == "reset")
                            {
                                client.Out.SendMessage(T(client, "GMCommands.Player.ResetPlayer", player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                player.Out.SendMessage(
                                    T(player, "GMCommands.Player.TargetResetSkills", client.Player.Name, client.Account.PrivLevel),
                                    eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            }
                            else
                            {
                                client.Out.SendMessage(T(client, "GMCommands.Player.LevelChanged", player.Name, newLevel),
                                                       eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                player.Out.SendMessage(
                                    T(player, "GMCommands.Player.TargetLevelChanged", client.Player.Name, client.Account.PrivLevel, newLevel),
                                    eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            }


                            player.Out.SendUpdatePlayer();
                            player.Out.SendUpdatePoints();
                            player.Out.SendCharStatsUpdate();
                            player.UpdatePlayerStatus();
                            player.SaveIntoDatabase();
                        }

                        catch (Exception)
                        {
                            DisplaySyntax(client);
                            return;
                        }
                    }
                    break;

                #endregion

				#region Start Champion

				case "startchampion":
					try
					{
						var player = client.Player.TargetObject as GamePlayer;
						if (player == null)
							player = client.Player;

						if (player.Champion == false)
						{
							player.Champion = true;
							player.SaveIntoDatabase();
							client.Out.SendMessage(T(client, "GMCommands.Player.ChampionStarted", player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
							player.Out.SendMessage(T(player, "GMCommands.Player.TargetChampionStarted", client.Player.Name, client.Account.PrivLevel), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
						}
						else
						{
							client.Out.SendMessage(T(client, "GMCommands.Player.ChampionAlreadyStarted", player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
						}

					}
					catch
					{
						DisplaySyntax(client);
						return;
					}
					break;

				#endregion Start Champion

				#region Clear / Respec Champion

				case "clearchampion":

                    try
                    {
                        var player = client.Player.TargetObject as GamePlayer;
                        if (player == null)
                            player = client.Player;

                        player.RemoveChampionLevels();
                        client.Out.SendMessage(T(client, "GMCommands.Player.ChampionLevelsCleared", player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                        player.Out.SendMessage(T(player, "GMCommands.Player.TargetChampionLevelsCleared", client.Player.Name, client.Account.PrivLevel), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                    }

                    catch (Exception)
                    {
                        DisplaySyntax(client);
                        return;
                    }
                    break;

				case "respecchampion":

					try
					{
						var player = client.Player.TargetObject as GamePlayer;
						if (player == null)
							player = client.Player;

						player.RespecChampionSkills();
						client.Out.SendMessage(T(client, "GMCommands.Player.ChampionLevelsRespecced", player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
						player.Out.SendMessage(T(player, "GMCommands.Player.TargetChampionLevelsRespecced", client.Player.Name, client.Account.PrivLevel), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
					}

					catch (Exception)
					{
						DisplaySyntax(client);
						return;
					}
					break;

                #endregion Clear / Respec Champion

				#region Master Levels

				case "startml":

					try
					{
						var player = client.Player.TargetObject as GamePlayer;
						if (player == null)
							player = client.Player;

						if (player.MLGranted == false)
						{
							player.MLGranted = true;
							player.SaveIntoDatabase();
							client.Out.SendMessage(T(client, "GMCommands.Player.MasterLevelTrainingStarted", player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
							player.Out.SendMessage(T(player, "GMCommands.Player.TargetMasterLevelTrainingStarted", client.Player.Name, client.Account.PrivLevel), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
						}
						else
						{
							client.Out.SendMessage(T(client, "GMCommands.Player.MasterLevelTrainingAlreadyStarted", player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
						}
					}
					catch (Exception)
					{
						DisplaySyntax(client);
						return;
					}
					break;

				case "setml":

					try
					{
						var player = client.Player.TargetObject as GamePlayer;
						if (player == null)
							player = client.Player;

						byte level = Convert.ToByte(args[2]);

						if (level > GamePlayer.ML_MAX_LEVEL) level = GamePlayer.ML_MAX_LEVEL;

						player.MLLevel = level;
						player.MLExperience = 0;
						player.SaveIntoDatabase();
						player.Out.SendUpdatePlayer();
						player.Out.SendMasterLevelWindow((byte)player.MLLevel);
						client.Out.SendMessage(T(client, "GMCommands.Player.MasterLevelSet", player.Name, level), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
						player.Out.SendMessage(T(player, "GMCommands.Player.TargetMasterLevelSet", client.Player.Name, client.Account.PrivLevel, level), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
					}
					catch (Exception)
					{
						DisplaySyntax(client);
						return;
					}
					break;

				case "setmlline":

					try
					{
						var player = client.Player.TargetObject as GamePlayer;
						if (player == null)
							player = client.Player;

						byte line = Convert.ToByte(args[2]);

						if (line > 1) line = 1;

						player.MLLine = line;
						player.SaveIntoDatabase();
						player.RefreshSpecDependantSkills(true);
						player.Out.SendUpdatePlayerSkills(true);
						player.Out.SendUpdatePlayer();
						player.Out.SendMasterLevelWindow((byte)player.MLLevel);
						client.Out.SendMessage(T(client, "GMCommands.Player.MasterLineSet", player.Name, line), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
						player.Out.SendMessage(T(player, "GMCommands.Player.TargetMasterLineSet", client.Player.Name, client.Account.PrivLevel, line), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
					}
					catch (Exception)
					{
						DisplaySyntax(client);
						return;
					}
					break;

				case "setmlstep":

					try
					{
						var player = client.Player.TargetObject as GamePlayer;
						if (player == null)
							player = client.Player;

						if (player.MLLevel == GamePlayer.ML_MAX_LEVEL)
						{
							client.Out.SendMessage(T(client, "GMCommands.Player.MasterLevelsAlreadyFinished", player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
							return;
						}

						byte level = Convert.ToByte(args[2]);
						if (level > GamePlayer.ML_MAX_LEVEL)
						{
							client.Out.SendMessage(T(client, "GMCommands.Player.ValidMasterLevels", GamePlayer.ML_MAX_LEVEL), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
							return;
						}

						// Possible steps per level varies, max appears to be 11
						byte step = Convert.ToByte(args[3]);

						bool setFinished = true;
						if (args.Length > 4)
						{
							setFinished = Convert.ToBoolean(args[4]);
						}

						if (setFinished && player.HasFinishedMLStep(player.MLLevel + 1, step))
						{
							client.Out.SendMessage(T(client, "GMCommands.Player.MasterStepAlreadyFinished", player.Name, step, player.MLLevel + 1), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
						}
						else if (setFinished == false && player.HasFinishedMLStep(player.MLLevel + 1, step) == false)
						{
							client.Out.SendMessage(T(client, "GMCommands.Player.MasterStepNotFinished", player.Name, step, player.MLLevel + 1), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
						}
						else
						{
							player.SetFinishedMLStep(player.MLLevel + 1, step, setFinished);
							if (setFinished)
							{
								client.Out.SendMessage(T(client, "GMCommands.Player.MasterStepSetFinished", player.Name, step, player.MLLevel + 1), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
								player.Out.SendMessage(T(player, "GMCommands.Player.TargetMasterStepSetFinished", client.Player.Name, client.Account.PrivLevel, step, player.MLLevel + 1), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
							}
							else
							{
								client.Out.SendMessage(T(client, "GMCommands.Player.MasterStepSetUnfinished", player.Name, step, player.MLLevel + 1), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
								player.Out.SendMessage(T(player, "GMCommands.Player.TargetMasterStepSetUnfinished", client.Player.Name, client.Account.PrivLevel, step, player.MLLevel + 1), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
							}
							player.SaveIntoDatabase();
							player.Out.SendMasterLevelWindow(level);
							player.Out.SendUpdatePlayer();
						}
					}
					catch (Exception)
					{
						DisplaySyntax(client);
						return;
					}
					break;

				#endregion Master Levels

                #region realm

                case "realm":
                    {
                        try
                        {
                            byte newRealm = Convert.ToByte(args[2]);
                            var player = client.Player.TargetObject as GamePlayer;

                            if (args.Length != 3)
                            {
                                DisplaySyntax(client);
                                return;
                            }

                            if (player == null)
                                player = client.Player;

                            if (newRealm < 0 || newRealm > 3)
                            {
                                client.Out.SendMessage(T(client, "GMCommands.Player.RealmRange", player.Name), eChatType.CT_Important,
                                                       eChatLoc.CL_SystemWindow);
                                return;
                            }

                            player.Realm = (eRealm)newRealm;

                            string realmName = GlobalConstants.RealmToName((eRealm)newRealm);
                            client.Out.SendMessage(T(client, "GMCommands.Player.RealmChanged", player.Name, realmName),
                                                   eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            player.Out.SendMessage(T(player, "GMCommands.Player.TargetRealmChanged", client.Player.Name, realmName),
                                                   eChatType.CT_Important, eChatLoc.CL_SystemWindow);

                            player.Out.SendUpdatePlayer();
                            player.SaveIntoDatabase();
                        }

                        catch (Exception)
                        {
                            DisplaySyntax(client);
                            return;
                        }
                    }
                    break;

                #endregion

                #region model

                case "model":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        try
                        {
                            if (args.Length > 4)
                            {
                                DisplaySyntax(client);
                                return;
                            }

                            if (player == null)
                                player = client.Player;


                            switch (args[2])
                            {
                                case "reset":
                                    {
                                        player.Model = (ushort)player.Client.Account.Characters[player.Client.ActiveCharIndex].CreationModel;
                                        client.Out.SendMessage(T(client, "GMCommands.Player.ModelReset", player.Name),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        player.Out.SendMessage(
                                            T(player, "GMCommands.Player.TargetModelReset", client.Player.Name, client.Account.PrivLevel),
                                            eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        player.Out.SendUpdatePlayer();
                                        player.SaveIntoDatabase();
                                    }
                                    break;

                                default:
                                    {
                                        ushort modelID = 0;
                                        int modelIndex = 0;

                                        if (args[2] == "change")
                                            modelIndex = 3;
                                        else
                                            modelIndex = 2;

                                        if (ushort.TryParse(args[modelIndex], out modelID) == false)
                                        {
                                            DisplaySyntax(client, args[1]);
                                            return;
                                        }

                                        player.Model = modelID;
                                        client.Out.SendMessage(T(client, "GMCommands.Player.ModelChanged", player.Name, modelID),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        player.Out.SendMessage(
                                            T(player, "GMCommands.Player.TargetModelChanged", client.Player.Name, client.Account.PrivLevel, modelID),
                                            eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        player.Out.SendUpdatePlayer();
                                        player.SaveIntoDatabase();
                                    }
                                    break;
                            }
                        }
                        catch (Exception)
                        {
                            DisplaySyntax(client);
                            return;
                        }
                    }
                    break;

                #endregion

                #region money

                case "money":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        try
                        {
                            if (args.Length != 4)
                            {
                                DisplaySyntax(client);
                                return;
                            }

                            if (player == null)
                                player = client.Player;

                            switch (args[2])
                            {
                                case "copp":
                                    {
                                        long amount = long.Parse(args[3]);
                                        player.AddMoney(amount);
                                        InventoryLogging.LogInventoryAction(client.Player, player, eInventoryActionType.Other, amount);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.MoneyGiven", player.Name, T(client, "GMCommands.Player.Currency.Copper")), eChatType.CT_Important,
                                                               eChatLoc.CL_SystemWindow);
                                        player.Out.SendMessage(
                                            T(player, "GMCommands.Player.TargetMoneyGiven", client.Player.Name, client.Account.PrivLevel, T(player, "GMCommands.Player.Currency.Copper")),
                                            eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        return;
                                    }


                                case "silv":
                                    {
                                        long amount = long.Parse(args[3]) * 100;
                                        player.AddMoney(amount);
                                        InventoryLogging.LogInventoryAction(client.Player, player, eInventoryActionType.Other, amount);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.MoneyGiven", player.Name, T(client, "GMCommands.Player.Currency.Silver")), eChatType.CT_Important,
                                                               eChatLoc.CL_SystemWindow);
                                        player.Out.SendMessage(
                                            T(player, "GMCommands.Player.TargetMoneyGiven", client.Player.Name, client.Account.PrivLevel, T(player, "GMCommands.Player.Currency.Silver")),
                                            eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        return;
                                    }

                                case "gold":
                                    {
                                        long amount = long.Parse(args[3]) * 100 * 100;
                                        player.AddMoney(amount);
                                        InventoryLogging.LogInventoryAction(client.Player, player, eInventoryActionType.Other, amount);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.MoneyGiven", player.Name, T(client, "GMCommands.Player.Currency.Gold")), eChatType.CT_Important,
                                                               eChatLoc.CL_SystemWindow);
                                        player.Out.SendMessage(
                                            T(player, "GMCommands.Player.TargetMoneyGiven", client.Player.Name, client.Account.PrivLevel, T(player, "GMCommands.Player.Currency.Gold")),
                                            eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        return;
                                    }

                                case "plat":
                                    {
                                        long amount = long.Parse(args[3]) * 100 * 100 * 1000;
                                        player.AddMoney(amount);
                                        InventoryLogging.LogInventoryAction(client.Player, player, eInventoryActionType.Other, amount);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.MoneyGiven", player.Name, T(client, "GMCommands.Player.Currency.Platinum")), eChatType.CT_Important,
                                                               eChatLoc.CL_SystemWindow);
                                        player.Out.SendMessage(
                                            T(player, "GMCommands.Player.TargetMoneyGiven", client.Player.Name, client.Account.PrivLevel, T(player, "GMCommands.Player.Currency.Platinum")),
                                            eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        return;
                                    }

                                case "mith":
                                    {
                                        long amount = long.Parse(args[3]) * 100 * 100 * 1000 * 1000;
                                        player.AddMoney(amount);
                                        InventoryLogging.LogInventoryAction(client.Player, player, eInventoryActionType.Other, amount);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.MoneyGiven", player.Name, T(client, "GMCommands.Player.Currency.Mithril")), eChatType.CT_Important,
                                                               eChatLoc.CL_SystemWindow);
                                        player.Out.SendMessage(
                                            T(player, "GMCommands.Player.TargetMoneyGiven", client.Player.Name, client.Account.PrivLevel, T(player, "GMCommands.Player.Currency.Mithril")),
                                            eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        return;
                                    }
                            }
                            player.Out.SendUpdatePlayer();
                            player.SaveIntoDatabase();
                        }

                        catch (Exception)
                        {
                            DisplaySyntax(client);
                            return;
                        }
                    }
                    break;

                #endregion

                #region points

                case "rps":
                    {
                        var player = client.Player.TargetObject as GamePlayer;
                        try
                        {
                            if (args.Length != 3)
                            {
                                DisplaySyntax(client);
                                return;
                            }

                            if (player == null)
                                player = client.Player;

                            long amount = long.Parse(args[2]);
                            player.GainRealmPoints(amount, false, true, true, false);
                            client.Out.SendMessage(T(client, "GMCommands.Player.PointsGiven", player.Name, amount, T(client, "GMCommands.Player.Point.RealmPoints")),
                                                   eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            player.Out.SendMessage(
                                T(player, "GMCommands.Player.TargetPointsGiven", client.Player.Name, client.Account.PrivLevel, amount, T(player, "GMCommands.Player.Point.RealmPoints")),
                                eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            player.SaveIntoDatabase();
                            player.Out.SendUpdatePlayer();
                        }
                        catch (Exception)
                        {
                            DisplaySyntax(client);
                            return;
                        }
                    }
                    break;


                case "xp":
                case "xpa":
                    {
                        var player = client.Player.TargetObject as GamePlayer;
                        try
                        {
                            if (args.Length != 3)
                            {
                                DisplaySyntax(client);
                                return;
                            }

                            if (player == null)
                                player = client.Player;

                            eXPSource xpSource = eXPSource.Other;
                            if (args[1].ToLower() == "xpa")
                            {
                                xpSource = eXPSource.NPC;
                            }

                            long amount = long.Parse(args[2]);
                            player.GainExperience(xpSource, amount, false);
                            client.Out.SendMessage(T(client, "GMCommands.Player.PointsGiven", player.Name, amount, T(client, "GMCommands.Player.Point.Experience")),
                                                   eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            player.Out.SendMessage(
                                T(player, "GMCommands.Player.TargetPointsGiven", client.Player.Name, client.Account.PrivLevel, amount, T(player, "GMCommands.Player.Point.Experience")),
                                eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            player.SaveIntoDatabase();
                            player.Out.SendUpdatePlayer();
                        }
                        catch (Exception)
                        {
                            DisplaySyntax(client);
                            return;
                        }
                    }
                    break;

                case "clxp":
                    {
                        var player = client.Player.TargetObject as GamePlayer;
                        try
                        {
                            if (args.Length != 3)
                            {
                                DisplaySyntax(client);
                                return;
                            }

                            if (player == null)
                                player = client.Player;

                            long amount = long.Parse(args[2]);
                            player.GainChampionExperience(amount, eXPSource.GM);
                            client.Out.SendMessage(T(client, "GMCommands.Player.PointsGiven", player.Name, amount, T(client, "GMCommands.Player.Point.ChampionExperience")), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            player.Out.SendMessage(T(player, "GMCommands.Player.TargetPointsGiven", client.Player.Name, client.Account.PrivLevel, amount, T(player, "GMCommands.Player.Point.ChampionExperience")), eChatType.CT_Important, eChatLoc.CL_SystemWindow);

							// now see if player gained any CL and level them up
							bool gainedLevel = false;
							while (player.ChampionLevel < player.ChampionMaxLevel && player.ChampionExperience >= player.ChampionExperienceForNextLevel)
							{
								player.ChampionLevelUp();
								gainedLevel = true;
							}

							if (gainedLevel)
							{
								player.Out.SendMessage(T(player, "GMCommands.Player.ChampionLevelReached", player.ChampionLevel), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
							}


                            player.SaveIntoDatabase();
                            player.Out.SendUpdatePlayer();
                        }
                        catch (Exception)
                        {
                            DisplaySyntax(client);
                            return;
                        }
                    }
                    break;

				case "mlxp":
					{
						var player = client.Player.TargetObject as GamePlayer;
						try
						{
							if (args.Length != 3)
							{
								DisplaySyntax(client);
								return;
							}

							if (player == null)
								player = client.Player;

							// WIP, For the moment it simply sets MLExperience - Tolakram

							long amount = long.Parse(args[2]);

							player.MLExperience += amount;
							client.Out.SendMessage(T(client, "GMCommands.Player.PointsGiven", player.Name, amount, T(client, "GMCommands.Player.Point.MLExperience")), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
							player.Out.SendMessage(T(player, "GMCommands.Player.TargetPointsGiven", client.Player.Name, client.Account.PrivLevel, amount, T(player, "GMCommands.Player.Point.MLExperience")), eChatType.CT_Important, eChatLoc.CL_SystemWindow);

							if (player.MLExperience > player.GetMLExperienceForLevel(player.MLLevel + 1))
							{
								player.MLExperience = player.GetMLExperienceForLevel(player.MLLevel + 1);
							}

							if (player.MLExperience < 0)
							{
								player.MLExperience = 0;
							}

							player.SaveIntoDatabase();
							player.Out.SendUpdatePlayer();
							player.Out.SendMasterLevelWindow((byte)player.MLLevel);
						}
						catch (Exception)
						{
							DisplaySyntax(client);
							return;
						}
					}
					break;

                case "bps":
                    {
                        var player = client.Player.TargetObject as GamePlayer;
                        try
                        {
                            if (args.Length != 3)
                            {
                                DisplaySyntax(client);
                                return;
                            }

                            if (player == null)
                                player = client.Player;

                            long amount = long.Parse(args[2]);
                            player.GainBountyPoints(amount, false);
                            client.Out.SendMessage(T(client, "GMCommands.Player.PointsGiven", player.Name, amount, T(client, "GMCommands.Player.Point.BountyPoints")),
                                                   eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            player.Out.SendMessage(
                                T(player, "GMCommands.Player.TargetPointsGiven", client.Player.Name, client.Account.PrivLevel, amount, T(player, "GMCommands.Player.Point.BountyPoints")),
                                eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            player.SaveIntoDatabase();
                            player.Out.SendUpdatePlayer();
                        }
                        catch (Exception)
                        {
                            DisplaySyntax(client);
                            return;
                        }
                    }
                    break;

                #endregion

                #region stat

                case "stat":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        try
                        {
                            short value = Convert.ToInt16(args[3]);

                            if (args.Length != 4)
                            {
                                DisplaySyntax(client);
                                return;
                            }

                            if (player == null)
                                player = client.Player;

                            switch (args[2])
                            {
                                /*1*/
                                case "dex":
                                    {
                                        player.ChangeBaseStat(eStat.DEX, value);
                                        player.Out.SendMessage(T(player, "GMCommands.Player.TargetStatGiven", client.Player.Name, client.Account.PrivLevel, value, T(player, "GMCommands.Player.Stat.Dexterity")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.StatGiven", player.Name, value, T(client, "GMCommands.Player.Stat.Dexterity")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    }
                                    break;

                                /*2*/
                                case "str":
                                    {
                                        player.ChangeBaseStat(eStat.STR, value);
                                        player.Out.SendMessage(T(player, "GMCommands.Player.TargetStatGiven", client.Player.Name, client.Account.PrivLevel, value, T(player, "GMCommands.Player.Stat.Strength")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.StatGiven", player.Name, value, T(client, "GMCommands.Player.Stat.Strength")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    }
                                    break;

                                /*3*/
                                case "con":
                                    {
                                        player.ChangeBaseStat(eStat.CON, value);
                                        player.Out.SendMessage(T(player, "GMCommands.Player.TargetStatGiven", client.Player.Name, client.Account.PrivLevel, value, T(player, "GMCommands.Player.Stat.Constitution")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.StatGiven", player.Name, value, T(client, "GMCommands.Player.Stat.Constitution")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    }
                                    break;

                                /*4*/
                                case "emp":
                                    {
                                        player.ChangeBaseStat(eStat.EMP, value);
                                        player.Out.SendMessage(T(player, "GMCommands.Player.TargetStatGiven", client.Player.Name, client.Account.PrivLevel, value, T(player, "GMCommands.Player.Stat.Empathy")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.StatGiven", player.Name, value, T(client, "GMCommands.Player.Stat.Empathy")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    }
                                    break;

                                /*5*/
                                case "int":
                                    {
                                        player.ChangeBaseStat(eStat.INT, value);
                                        player.Out.SendMessage(T(player, "GMCommands.Player.TargetStatGiven", client.Player.Name, client.Account.PrivLevel, value, T(player, "GMCommands.Player.Stat.Intelligence")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.StatGiven", player.Name, value, T(client, "GMCommands.Player.Stat.Intelligence")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    }
                                    break;

                                /*6*/
                                case "pie":
                                    {
                                        player.ChangeBaseStat(eStat.PIE, value);
                                        player.Out.SendMessage(T(player, "GMCommands.Player.TargetStatGiven", client.Player.Name, client.Account.PrivLevel, value, T(player, "GMCommands.Player.Stat.Piety")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.StatGiven", player.Name, value, T(client, "GMCommands.Player.Stat.Piety")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    }
                                    break;

                                /*7*/
                                case "qui":
                                    {
                                        player.ChangeBaseStat(eStat.QUI, value);
                                        player.Out.SendMessage(T(player, "GMCommands.Player.TargetStatGiven", client.Player.Name, client.Account.PrivLevel, value, T(player, "GMCommands.Player.Stat.Quickness")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.StatGiven", player.Name, value, T(client, "GMCommands.Player.Stat.Quickness")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    }
                                    break;

                                /*8*/
                                case "cha":
                                    {
                                        player.ChangeBaseStat(eStat.CHR, value);
                                        player.Out.SendMessage(T(player, "GMCommands.Player.TargetStatGiven", client.Player.Name, client.Account.PrivLevel, value, T(player, "GMCommands.Player.Stat.Charisma")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.StatGiven", player.Name, value, T(client, "GMCommands.Player.Stat.Charisma")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    }
                                    break;

                                /*all*/
                                case "all":
                                    {
                                        player.ChangeBaseStat(eStat.CHR, value); //1
                                        player.ChangeBaseStat(eStat.QUI, value); //2
                                        player.ChangeBaseStat(eStat.INT, value); //3
                                        player.ChangeBaseStat(eStat.PIE, value); //4
                                        player.ChangeBaseStat(eStat.EMP, value); //5
                                        player.ChangeBaseStat(eStat.CON, value); //6
                                        player.ChangeBaseStat(eStat.STR, value); //7
                                        player.ChangeBaseStat(eStat.DEX, value); //8
                                        player.Out.SendMessage(T(player, "GMCommands.Player.TargetStatGiven", client.Player.Name, client.Account.PrivLevel, value, T(player, "GMCommands.Player.Stat.All")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.StatGiven", player.Name, value, T(client, "GMCommands.Player.Stat.All")),
                                                               eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    }
                                    break;

                                default:
                                    {
                                        client.Out.SendMessage(T(client, "GMCommands.Player.StatTypeUsage"),
                                                               eChatType.CT_System, eChatLoc.CL_SystemWindow);
                                    }
                                    break;
                            }

                            player.Out.SendCharStatsUpdate();
                            player.Out.SendUpdatePlayer();
                            player.SaveIntoDatabase();
                        }
                        catch (Exception)
                        {
                            DisplaySyntax(client);
                            return;
                        }
                    }
                    break;

                #endregion

                #region friend

                case "friend":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        if (args.Length != 3)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null)
                        {
                            client.Out.SendMessage(T(client, "GMCommands.Player.NeedValidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        if (args[2] == "list")
                        {
                            string[] list = player.SerializedFriendsList;
                            client.Out.SendCustomTextWindow(T(client, "GMCommands.Player.FriendListTitle", player.Name), list);
                            return;
                        }

                        string name = string.Join(" ", args, 2, args.Length - 2);
                        GamePlayer targetPlayer = ClientService.Instance.GetPlayerByPartialName(name, out ClientService.PlayerGuessResult result);;

                        if (targetPlayer != null && !GameServer.ServerRules.IsSameRealm(targetPlayer, player.Client.Player, true))
                            targetPlayer = null;

                        if (targetPlayer == null)
                        {
                            name = args[2];

                            if (player.GetFriends().Contains(name) && player.RemoveFriend(name))
                            {
                                player.Out.SendMessage(T(player, "GMCommands.Player.TargetFriendRemoved", client.Player.Name, client.Account.PrivLevel, name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                client.Out.SendMessage(T(client, "GMCommands.Player.FriendRemoved", name, player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                return;
                            }
                            else
                            {
                                client.Out.SendMessage(T(client, "GMCommands.Player.NoOnlinePlayerNamed", name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                return;
                            }
                        }

                        switch (result)
                        {
                            case ClientService.PlayerGuessResult.FOUND_MULTIPLE:
                            {
                                client.Out.SendMessage(T(client, "GMCommands.Player.CharacterNameNotUnique"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                                return;
                            }
                            case ClientService.PlayerGuessResult.FOUND_EXACT:
                            case ClientService.PlayerGuessResult.FOUND_PARTIAL:
                            {
                                if (targetPlayer == player)
                                {
                                    client.Out.SendMessage(T(client, "GMCommands.Player.CannotAddSelfFriend"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    return;
                                }

                                name = targetPlayer.Name;

                                if (player.GetFriends().Contains(name) && player.RemoveFriend(name))
                                {
                                    player.Out.SendMessage(T(player, "GMCommands.Player.TargetFriendRemoved", client.Player.Name, client.Account.PrivLevel, name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    client.Out.SendMessage(T(client, "GMCommands.Player.FriendRemoved", name, player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                }
                                else if (player.AddFriend(name))
                                {
                                    player.Out.SendMessage(T(player, "GMCommands.Player.TargetFriendAdded", client.Player.Name, client.Account.PrivLevel, name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    client.Out.SendMessage(T(client, "GMCommands.Player.FriendAdded", name, player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                }

                                break;
                            }
                        }

                        player.Out.SendUpdatePlayer();
                        player.SaveIntoDatabase();
                    }
                    break;

                #endregion

                #region respec

                case "respec":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        if (args.Length < 2 || args.Length > 4)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null)
                            player = client.Player;

                        int amount = 1;
                        if (args.Length == 4)
                        {
                            try
                            {
                                amount = Convert.ToInt32(args[3]);
                            }
                            catch
                            {
                                amount = 1;
                            }
                        }

                        switch (args[2])
                        {
                            case "line":
                                {
                                    player.RespecAmountSingleSkill += amount;
                                    player.Client.Out.SendMessage(
                                        T(player, "GMCommands.Player.TargetRespecAwarded", client.Player.Name, client.Account.PrivLevel, amount, T(player, "GMCommands.Player.Respec.Single")), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    client.Out.SendMessage(T(client, "GMCommands.Player.RespecAwarded", amount, T(client, "GMCommands.Player.Respec.Single"), player.Name),
                                                           eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    break;
                                }
                            case "all":
                                {
                                    player.RespecAmountAllSkill += amount;
                                    player.Client.Out.SendMessage(
                                        T(player, "GMCommands.Player.TargetRespecAwarded", client.Player.Name, client.Account.PrivLevel, amount, T(player, "GMCommands.Player.Respec.Full")), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    client.Out.SendMessage(T(client, "GMCommands.Player.RespecAwarded", amount, T(client, "GMCommands.Player.Respec.Full"), player.Name),
                                                           eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    break;
                                }
                            case "realm":
                                {
                                    player.RespecAmountRealmSkill += amount;
                                    player.Client.Out.SendMessage(
                                        T(player, "GMCommands.Player.TargetRespecAwarded", client.Player.Name, client.Account.PrivLevel, amount, T(player, "GMCommands.Player.Respec.Realm")), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    client.Out.SendMessage(T(client, "GMCommands.Player.RespecAwarded", amount, T(client, "GMCommands.Player.Respec.Realm"), player.Name),
                                                           eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    break;
                                }
                            case "dol":
                                {
                                    player.RespecAmountDOL += amount;
                                    player.Client.Out.SendMessage(
                                        T(player, "GMCommands.Player.TargetRespecAwarded", client.Player.Name, client.Account.PrivLevel, amount, T(player, "GMCommands.Player.Respec.DOL")), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    client.Out.SendMessage(T(client, "GMCommands.Player.RespecAwarded", amount, T(client, "GMCommands.Player.Respec.DOL"), player.Name),
                                                           eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    break;
                                }
                            case "champion":
                                {
                                    player.RespecAmountChampionSkill += amount;
                                    player.Client.Out.SendMessage(
                                        T(player, "GMCommands.Player.TargetRespecAwarded", client.Player.Name, client.Account.PrivLevel, amount, T(player, "GMCommands.Player.Respec.Champion")), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    client.Out.SendMessage(T(client, "GMCommands.Player.RespecAwarded", amount, T(client, "GMCommands.Player.Respec.Champion"), player.Name),
                                                           eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    break;
                                }
                            /*case "ml":
                            {
                                //
                                player.Client.Out.SendMessage(client.Player.Name + "(PrivLevel: " + client.Account.PrivLevel + ") has awarded you an ML respec!", eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                client.Out.SendMessage("ML respec given successfully to " + player.Name + "!", eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                break;
                            }*/
                        }

                        player.Client.Player.SaveIntoDatabase();
                    }
                    break;

                #endregion

                #region realm

                case "purge":
                    {
                        var player = client.Player.TargetObject as GamePlayer;
                        bool m_hasEffect;

                        if (args.Length != 2)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null)
                        {
                            client.Out.SendMessage(T(client, "GMCommands.Player.NeedValidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        m_hasEffect = false;

                        lock (player.EffectList.Lock)
                        {
                            foreach (GameSpellEffect effect in player.EffectList)
                            {
                                if (!effect.SpellHandler.HasPositiveEffect)
                                {
                                    m_hasEffect = true;
                                    break;
                                }
                            }
                        }

                        if (!m_hasEffect)
                        {
                            SendResistEffect(player);
                            return;
                        }

                        lock (player.EffectList.Lock)
                        {
                            foreach (GameSpellEffect effect in player.EffectList)
                            {
                                if (!effect.SpellHandler.HasPositiveEffect)
                                {
                                    effect.Cancel(false);
                                }
                            }
                        }
                    }
                    break;

                #endregion

                #region save

                case "save":
                    {
                        GamePlayer player = client.Player.TargetObject as GamePlayer;

                        if (args.Length is > 3 or < 2)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null && args.Length == 2)
                        {
                            client.Out.SendMessage(T(client, "GMCommands.Player.NeedValidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        if (args.Length == 2 && player != null)
                        {
                            player.Out.SendMessage(T(player, "GMCommands.Player.TargetCharacterSaved", client.Player.Name, client.Account.PrivLevel),eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            client.Out.SendMessage(T(client, "GMCommands.Player.CharacterSaved", player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            player.SaveIntoDatabase();
                        }

                        if (args.Length == 3)
                        {
                            switch (args[2])
                            {
                                case "all":
                                {
                                    foreach (GamePlayer otherPlayer in ClientService.Instance.GetPlayers())
                                        otherPlayer.SaveIntoDatabase();

                                    client.Out.SendMessage(T(client, "GMCommands.Player.AllCharactersSaved"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    break;
                                }
                                default:
                                {
                                    DisplaySyntax(client);
                                    return;
                                }
                            }
                        }
                    }
                    break;

                #endregion

                #region kick

                case "kick":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        if (args.Length > 3 || args.Length < 2)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null && args.Length == 2)
                        {
                            client.Out.SendMessage(T(client, "GMCommands.Player.NeedValidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        if (args.Length == 2 && player != null)
                        {
                            if (player.Client.Account.PrivLevel > 1)
                            {
                                client.Out.SendMessage(T(client, "GMCommands.Player.KickGMUseKickCommand"),
                                                       eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                return;
                            }
                            player.Client.Out.SendPlayerQuit(true);
                            player.Client.Disconnect();
                            return;
                        }

                        if (args.Length == 3)
                        {
                            switch (args[2])
                            {
                                case "all":
                                    {
                                        foreach (GamePlayer otherPlayer in ClientService.Instance.GetNonGmPlayers())
                                        {
                                            otherPlayer.Out.SendMessage(T(otherPlayer, "GMCommands.Player.TargetKickAll", client.Player.Name, client.Account.PrivLevel), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                            otherPlayer.Out.SendPlayerQuit(true);
                                            otherPlayer.Client.Disconnect();
                                            continue;
                                        }
                                    }
                                    break;

                                default:
                                    {
                                        DisplaySyntax(client);
                                        return;
                                    }
                            }
                        }
                    }
                    break;

                #endregion

                #region rez kill

                case "rez":
                    {
                        GamePlayer player = client.Player.TargetObject as GamePlayer;

                        if (args.Length is > 3 or < 2)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null && args.Length == 2)
                        {
                            client.Out.SendMessage(T(client, "GMCommands.Player.NeedValidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        if (args.Length == 2 && player != null)
                        {
                            if (!player.IsAlive)
                            {
                                player.Health = player.MaxHealth;
                                player.Mana = player.MaxMana;
                                player.Endurance = player.MaxEndurance;
                                player.MoveTo(client.Player.CurrentRegionID, client.Player.X, client.Player.Y, client.Player.Z, client.Player.Heading);
                                client.Out.SendMessage(T(client, "GMCommands.Player.Resurrected", player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                player.StopReleaseTimer();
                                player.Out.SendPlayerRevive(player);
                                player.Out.SendStatusUpdate();
                                player.Out.SendMessage(T(player, "GMCommands.Player.TargetResurrectedBy", client.Player.GetName(0, false)), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                                player.Notify(GamePlayerEvent.Revive, player);
                            }
                            else
                            {
                                client.Out.SendMessage(T(client, "GMCommands.Player.PlayerNotDead"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                return;
                            }
                        }

                        if (args.Length >= 3)
                        {
                            switch (args[2])
                            {
                                case "albs":
                                    {
                                        foreach (GamePlayer albPlayer in ClientService.Instance.GetPlayersOfRealm(eRealm.Albion))
                                        {
                                            if (!albPlayer.IsAlive)
                                            {
                                                albPlayer.Health = albPlayer.MaxHealth;
                                                albPlayer.Mana = albPlayer.MaxMana;
                                                albPlayer.Endurance = albPlayer.MaxEndurance;
                                                albPlayer.MoveTo(client.Player.CurrentRegionID, client.Player.X, client.Player.Y, client.Player.Z, client.Player.Heading);
                                                albPlayer.StopReleaseTimer();
                                                albPlayer.Out.SendPlayerRevive(albPlayer);
                                                albPlayer.Out.SendStatusUpdate();
                                                albPlayer.Out.SendMessage(T(albPlayer, "GMCommands.Player.TargetResurrectedBy", client.Player.GetName(0, false)), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                                                albPlayer.Notify(GamePlayerEvent.Revive, albPlayer);
                                            }
                                        }
                                    }
                                    break;

                                case "hibs":
                                    {
                                        foreach (GamePlayer hibPlayer in ClientService.Instance.GetPlayersOfRealm(eRealm.Hibernia))
                                        {
                                            if (!hibPlayer.IsAlive)
                                            {
                                                hibPlayer.Health = hibPlayer.MaxHealth;
                                                hibPlayer.Mana = hibPlayer.MaxMana;
                                                hibPlayer.Endurance = hibPlayer.MaxEndurance;
                                                hibPlayer.MoveTo(client.Player.CurrentRegionID, client.Player.X, client.Player.Y, client.Player.Z, client.Player.Heading);
                                                hibPlayer.StopReleaseTimer();
                                                hibPlayer.Out.SendPlayerRevive(hibPlayer);
                                                hibPlayer.Out.SendStatusUpdate();
                                                hibPlayer.Out.SendMessage(T(hibPlayer, "GMCommands.Player.TargetResurrectedBy", client.Player.GetName(0, false)), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                                                hibPlayer.Notify(GamePlayerEvent.Revive, hibPlayer);
                                            }
                                        }
                                    }
                                    break;
                                case "mids":
                                    {
                                        foreach (GamePlayer midPlayer in ClientService.Instance.GetPlayersOfRealm(eRealm.Midgard))
                                        {
                                            if (!midPlayer.IsAlive)
                                            {
                                                midPlayer.Health = midPlayer.MaxHealth;
                                                midPlayer.Mana = midPlayer.MaxMana;
                                                midPlayer.Endurance = midPlayer.MaxEndurance;
                                                midPlayer.MoveTo(client.Player.CurrentRegionID, client.Player.X, client.Player.Y, client.Player.Z, client.Player.Heading);
                                                midPlayer.StopReleaseTimer();
                                                midPlayer.Out.SendPlayerRevive(midPlayer);
                                                midPlayer.Out.SendStatusUpdate();
                                                midPlayer.Out.SendMessage(T(midPlayer, "GMCommands.Player.TargetResurrectedBy", client.Player.GetName(0, false)), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                                                midPlayer.Notify(GamePlayerEvent.Revive, midPlayer);
                                            }
                                        }
                                    }
                                    break;

                                case "self":
                                    {
                                        GamePlayer self = client.Player;

                                        if (!self.IsAlive)
                                        {
                                            self.Health = self.MaxHealth;
                                            self.Mana = self.MaxMana;
                                            self.Endurance = self.MaxEndurance;
                                            self.MoveTo(client.Player.CurrentRegionID, client.Player.X, client.Player.Y, client.Player.Z, client.Player.Heading);
                                            self.Out.SendMessage(T(self, "GMCommands.Player.ReviveSelf"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                            self.StopReleaseTimer();
                                            self.Out.SendPlayerRevive(self);
                                            self.Out.SendStatusUpdate();
                                            self.Notify(GamePlayerEvent.Revive, self);
                                        }
                                        else
                                        {
                                            client.Out.SendMessage(T(client, "GMCommands.Player.YouAreNotDead"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                            return;
                                        }
                                    }
                                    break;

                                case "all":
                                    {
                                        foreach (GamePlayer otherPlayer in ClientService.Instance.GetPlayers<object>(Predicate, default))
                                        {
                                            otherPlayer.Health = otherPlayer.MaxHealth;
                                            otherPlayer.Mana = otherPlayer.MaxMana;
                                            otherPlayer.Endurance = otherPlayer.MaxEndurance;
                                            otherPlayer.MoveTo(client.Player.CurrentRegionID, client.Player.X, client.Player.Y, client.Player.Z, client.Player.Heading);
                                            otherPlayer.StopReleaseTimer();
                                            otherPlayer.Out.SendPlayerRevive(otherPlayer);
                                            otherPlayer.Out.SendStatusUpdate();
                                            otherPlayer.Out.SendMessage(T(otherPlayer, "GMCommands.Player.TargetResurrectedBy", client.Player.GetName(0, false)), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                                            otherPlayer.Notify(GamePlayerEvent.Revive, otherPlayer);
                                        }

                                        static bool Predicate(GamePlayer x, object unused)
                                        {
                                            return !x.IsAlive;
                                        }
                                    }
                                    break;
                                default:
                                    {
                                        client.Out.SendMessage(T(client, "GMCommands.Player.RezSyntax"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                                    }
                                    break;
                            }
                        }
                    }
                    break;

                case "kill":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        if (args.Length < 2 || args.Length > 3)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null && args.Length == 2)
                        {
                            client.Out.SendMessage(T(client, "GMCommands.Player.NeedValidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        if (args.Length == 2 && player != null)
                        {
                            if (player.Client.Account.PrivLevel > 1)
                            {
                                client.Out.SendMessage(T(client, "GMCommands.Player.CannotUseOnGamemasters"), eChatType.CT_Important,
                                                       eChatLoc.CL_SystemWindow);
                                return;
                            }

                            if (player.IsAlive)
                            {
                                KillPlayer(client.Player, player);
                                client.Out.SendMessage(T(client, "GMCommands.Player.KilledPlayer", player.Name), eChatType.CT_Important,
                                                       eChatLoc.CL_SystemWindow);
                                player.Out.SendMessage(T(player, "GMCommands.Player.TargetKilledBy", client.Player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                            }
                            else
                            {
                                client.Out.SendMessage(T(client, "GMCommands.Player.PlayerNotAlive"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                return;
                            }
                        }
                        if (args.Length < 3)
                            return;
                        switch (args[2])
                        {
                            case "albs":
                                {
                                    foreach (GamePlayer albPlayer in ClientService.Instance.GetPlayersOfRealm(eRealm.Albion))
                                    {
                                        if (albPlayer.IsAlive && albPlayer.Client.Account.PrivLevel == 1)
                                            KillPlayer(client.Player, albPlayer);
                                    }
                                }
                                break;

                            case "mids":
                                {
                                    foreach (GamePlayer midPlayer in ClientService.Instance.GetPlayersOfRealm(eRealm.Midgard))
                                    {
                                        if (midPlayer.IsAlive && midPlayer.Client.Account.PrivLevel == 1)
                                            KillPlayer(client.Player, midPlayer);
                                    }
                                }
                                break;

                            case "hibs":
                                {
                                    foreach (GamePlayer hibPlayer in ClientService.Instance.GetPlayersOfRealm(eRealm.Hibernia))
                                    {
                                        if (hibPlayer.IsAlive && hibPlayer.Client.Account.PrivLevel == 1)
                                            KillPlayer(client.Player, hibPlayer);
                                    }
                                }
                                break;

                            case "self":
                                {
                                    GamePlayer self = client.Player;

                                    if (!self.IsAlive)
                                    {
                                        client.Out.SendMessage(T(client, "GMCommands.Player.AlreadyDeadUseRezSelf"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                        return;
                                    }
                                    else
                                    {
                                        KillPlayer(client.Player, client.Player);
                                        client.Out.SendMessage(T(client, "GMCommands.Player.KilledSelf"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                    }
                                }
                                break;

                            case "all":
                                {
                                    foreach (GamePlayer otherPlayer in ClientService.Instance.GetNonGmPlayers())
                                    {
                                        if (otherPlayer.IsAlive)
                                            KillPlayer(client.Player, otherPlayer);
                                    }
                                }
                                break;

                            default:
                                {
                                    client.Out.SendMessage(T(client, "GMCommands.Player.InvalidArgument", args[2]), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                }
                                break;
                        }
                        /*End Switch Statement*/
                    }
                    break;

                #endregion

                #region jump

                case "jump":
                    {
                        if (args.Length < 4)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        switch (args[2])
                        {
                            case "guild":
                                {
                                    if (args[3] == null)
                                    {
                                        DisplaySyntax(client);
                                        return;
                                    }

                                    short count = 0;
                                    string guildName = string.Join(" ", args, 3, args.Length - 3);
                                    List<GamePlayer> players = ClientService.Instance.GetPlayers(Predicate, guildName);

                                    foreach (GamePlayer guildMember in players)
                                    {
                                        count++;
                                        guildMember.MoveTo(client.Player.CurrentRegionID, client.Player.X, client.Player.Y, client.Player.Z, client.Player.Heading);
                                    }

                                    client.Out.SendMessage(T(client, "GMCommands.Player.PlayersJumped", count), eChatType.CT_Important, eChatLoc.CL_SystemWindow);

                                    static bool Predicate(GamePlayer player, string guildName)
                                    {
                                        return !string.IsNullOrEmpty(player.GuildName) && player.GuildName.Equals(guildName);
                                    }
                                }
                                break;

                            case "group":
                                {
                                    if (args[3] == null)
                                    {
                                        DisplaySyntax(client);
                                        return;
                                    }

                                    short count = 0;
                                    string name = args[3];
                                    GamePlayer player = ClientService.Instance.GetPlayerByExactName(name);

                                    if (player != null)
                                    {
                                        foreach (GameLiving groupMember in player.Group.GetMembersInTheGroup())
                                        {
                                            groupMember.MoveTo(client.Player.CurrentRegionID, client.Player.X, client.Player.Y, client.Player.Z, client.Player.Heading);
                                            count++;
                                        }
                                    }

                                    client.Out.SendMessage(T(client, "GMCommands.Player.PlayersJumped", count), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                }
                                break;

                            case "cg":
                                {
                                    if (args[3] == null)
                                    {
                                        DisplaySyntax(client);
                                        return;
                                    }

                                    short count = 0;
                                    string name = args[3];
                                    GamePlayer player = ClientService.Instance.GetPlayerByExactName(name);

                                    if (player != null)
                                    {
                                        ChatGroup cg = player.TempProperties.GetProperty<ChatGroup>(ChatGroup.CHATGROUP_PROPERTY);

                                        if (cg != null)
                                        {
                                            foreach (GamePlayer bgMember in cg.Members.Keys)
                                            {
                                                bgMember.MoveTo(client.Player.CurrentRegionID, client.Player.X, client.Player.Y, client.Player.Z, client.Player.Heading);
                                                count++;
                                            }
                                        }
                                    }

                                    client.Out.SendMessage(T(client, "GMCommands.Player.PlayersJumped", count), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                }
                                break;

                            case "bg":
                                {
                                    if (args[3] == null)
                                    {
                                        DisplaySyntax(client);
                                        return;
                                    }

                                    short count = 0;
                                    string name = args[3];
                                    GamePlayer player = ClientService.Instance.GetPlayerByExactName(name);

                                    if (player != null)
                                    {
                                        BattleGroup bg = player.TempProperties.GetProperty<BattleGroup>(BattleGroup.BATTLEGROUP_PROPERTY);

                                        if (bg != null)
                                        {
                                            foreach (GamePlayer bgMember in bg.Members.Keys)
                                            {
                                                bgMember.MoveTo(client.Player.CurrentRegionID, client.Player.X, client.Player.Y, client.Player.Z, client.Player.Heading);
                                                count++;
                                            }
                                        }
                                    }

                                    client.Out.SendMessage(T(client, "GMCommands.Player.PlayersJumped", count), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                }
                                break;

                            default:
                                {
                                    client.Out.SendMessage(T(client, "GMCommands.Player.InvalidArgument", args[2]), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                                }
                                break;
                        }
                    }
                    break;

                #endregion

                #region update

                case "update":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        if (args.Length != 2)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null)
                            player = client.Player;

                        player.Out.SendUpdatePlayer();
                        player.Out.SendCharStatsUpdate();
                        player.Out.SendUpdatePoints();
                        player.Out.SendUpdateMaxSpeed();
                        player.Out.SendStatusUpdate();
                        player.Out.SendCharResistsUpdate();
                        client.Out.SendMessage(T(client, "GMCommands.Player.PlayerUpdated", player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                    }
                    break;

                #endregion

				#region Saddlebags

				case "saddlebags":
					{
						var player = client.Player.TargetObject as GamePlayer;

						if (args.Length != 3)
						{
							DisplaySyntax(client);
							return;
						}

						if (player == null)
							player = client.Player;

						byte activeBags = 0;

						if (byte.TryParse(args[2], out activeBags))
						{
							if (activeBags <= 0x0F)
							{
								player.ActiveSaddleBags = activeBags;
								player.SaveIntoDatabase();
								client.Player.Out.SendMessage(T(client, "GMCommands.Player.SaddlebagsSet", player.Name, player.ActiveSaddleBags), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
								player.Out.SendMessage(T(player, "GMCommands.Player.TargetSaddlebagsSet", player.ActiveSaddleBags, client.Player.Name), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
								player.Out.SendSetControlledHorse(player);
							}
							else
							{
								DisplayMessage(client, T(client, "GMCommands.Player.ValidSaddlebagValues"));
							}
						}
						else
						{
							DisplaySyntax(client);
						}

					}
					break;

				#endregion Saddlebags

				#region info

				case "info":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        if (args.Length != 2)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null)
                            player = client.Player;

                        Show_Info(player, client);
                    }
                    break;

                #endregion

                #region location

                case "location":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        client.Out.SendMessage("\"" + player.Name + "\", " +
                                               player.CurrentRegionID + ", " +
                                               player.X + ", " +
                                               player.Y + ", " +
                                               player.Z + ", " +
                                               player.Heading,
                                               eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    }
                    break;

                #endregion

                #region show group - effects

                case "showgroup":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        if (args.Length != 2)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null)
                        {
                            client.Out.SendMessage(T(client, "GMCommands.Player.NeedValidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        if (player.Group == null)
                        {
                            client.Out.SendMessage(T(client, "GMCommands.Player.NoGroup"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        var text = new List<string>();

                        foreach (GamePlayer p in player.Group.GetPlayersInTheGroup())
                        {
                            text.Add(p.Name + " " + p.Level + " " + p.CharacterClass.Name);
                        }

                        client.Out.SendCustomTextWindow(T(client, "GMCommands.Player.GroupMembersTitle"), text);
                        break;
                    }
                case "showeffects":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        if (args.Length != 2)
                        {
                            DisplaySyntax(client);
                            return;
                        }

                        if (player == null)
                        {
                            client.Out.SendMessage(T(client, "GMCommands.Player.NeedValidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        var effects = new List<string>();
                        ArrayList positiveEffects = new ArrayList();
                        ArrayList negativeEffects = new ArrayList();

                        if (positiveEffects.Count > 0)
                            positiveEffects.Clear();
                        if (negativeEffects.Count > 0)
                            negativeEffects.Clear();

                        if (player.effectListComponent != null)
                        {

                            foreach (ECSGameSpellEffect e in player.effectListComponent.GetSpellEffects())
                            {
                                if (e.HasPositiveEffect)
                                    positiveEffects.Add(e);
                                if (!e.HasPositiveEffect)
                                    negativeEffects.Add(e);
                            }

                            effects.Add(" ");
                            effects.Add(T(client, "GMCommands.Player.PositiveSpellEffects"));
                            if (positiveEffects.Count > 0)
                            {
                                // List active spell effects
                                foreach (ECSGameSpellEffect e in positiveEffects)
                                {
                                    var caster = T(client, "GMCommands.Player.EffectCasterNone");
                                    if (e.SpellHandler.Caster.Name != null)
                                    {
                                        caster = e.SpellHandler.Caster.Name;
                                        if (e.SpellHandler.Caster.Name == player.Name)
                                            caster = T(client, "GMCommands.Player.EffectCasterSelf");
                                    }

                                    effects.Add(T(client, "GMCommands.Player.SpellEffectLine", e.SpellHandler.Spell.Name, e.EffectType, e.SpellHandler.Spell.Level, caster, e.GetRemainingTimeForClient() / 1000));
                                }
                            }

                            effects.Add(" ");
                            effects.Add(T(client, "GMCommands.Player.NegativeSpellEffects"));
                            if (negativeEffects.Count > 0)
                            {
                                // List active spell effects
                                foreach (ECSGameSpellEffect e in negativeEffects)
                                {
                                    var caster = T(client, "GMCommands.Player.EffectCasterNone");
                                    if (e.SpellHandler.Caster.Name != null)
                                    {
                                        caster = e.SpellHandler.Caster.Name;
                                        if (e.SpellHandler.Caster.Name == player.Name)
                                            caster = T(client, "GMCommands.Player.EffectCasterSelf");
                                    }

                                    effects.Add(T(client, "GMCommands.Player.SpellEffectLine", e.SpellHandler.Spell.Name, e.EffectType, e.SpellHandler.Spell.Level, caster, e.GetRemainingTimeForClient() / 1000));
                                }
                            }
                        }
                        client.Out.SendCustomTextWindow(T(client, "GMCommands.Player.PlayerEffectsTitle"), effects);
                        break;
                    }

                #endregion

                #region inventory

                case "inventory":
                    {
                        var player = client.Player.TargetObject as GamePlayer;

                        if (player == null)
                        {
                            client.Out.SendMessage(T(client, "GMCommands.Player.NeedValidTarget"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        if (args.Length == 2)
                        {
                            Show_Inventory(player, client, "");
                            return;
                        }
                        else if (args.Length == 3)
                        {
                            Show_Inventory(player, client, args[2].ToLower());
                            return;
                        }

                        DisplaySyntax(client);
                        break;
                    }

                #endregion

                #region allcharacters

                case "allchars":
                    {
                       GamePlayer targetPlayer;

                        if (args.Length > 2)
                            targetPlayer = ClientService.Instance.GetPlayerByExactName(args[2]);
                        else
                            targetPlayer = client.Player.TargetObject as GamePlayer;

                        if (targetPlayer == null)
                        {
                            DisplaySyntax(client, args[1]);
                            return;
                        }
                        else
                        {
                            string characterNames = string.Empty;

                            foreach (DbCoreCharacter acctChar in targetPlayer.Client.Account.Characters)
                            {
                                if (acctChar != null)
                                    characterNames += $"{acctChar.Name} {acctChar.LastName}\n";
                            }

                            client.Out.SendMessage(characterNames, eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                        }
                    }
                    break;

                #endregion allcharacters

                #region class
                case "class":
                    {
                        var targetPlayer = client.Player.TargetObject as GamePlayer;
                        GameClient targetClient = targetPlayer == null ? null : targetPlayer.Client;

                        if (args.Length < 3)
                        {
                            DisplayMessage(client, T(client, "GMCommands.Player.ClassSyntax"));
                            return;
                        }

                        switch (args[2])
                        {
                            case "list":
                                {
                                    IList<string> classList = new List<string>();

                                    foreach (eCharacterClass cl in Enum.GetValues(typeof(eCharacterClass)))
                                    {
                                        classList.Add(Enum.GetName(typeof(eCharacterClass), cl) + " - " + (int)cl);
                                    }

                                    client.Player.Out.SendCustomTextWindow(T(client, "GMCommands.Player.ClassListTitle"), classList);
                                }
                                break;
                            default:
                                {
                                    if (targetPlayer == null)
                                    {
                                        DisplayMessage(client, T(client, "GMCommands.Player.ClassNeedsTarget"));
                                        return;
                                    }

                                    if (int.TryParse(args[2], out int valueInt))
                                    {
                                        SetClass(targetPlayer, valueInt);
                                    }
                                    else if (Enum.TryParse(args[2], true, out eCharacterClass valueEnum))
                                    {
                                        SetClass(targetPlayer, (byte)valueEnum);
                                    }
                                    else
                                    {
                                        DisplayMessage(client, T(client, "GMCommands.Player.ClassUseIdOrName"));
                                        return;
                                    }
                                }
                                break;
                        }
                    }
                    break;
                #endregion

                #region areas
                case "areas":
                    {
                        var targetPlayer = client.Player.TargetObject as GamePlayer;
                        if (targetPlayer == null) targetPlayer = client.Player;

                        List<string> areaList = new List<string>();

                        foreach (AbstractArea area in targetPlayer.CurrentAreas)
                        {
                            string areaInfo = area.GetType().Name + ", ID:" + area.ID;
                            if (area is QuestSearchArea)
                            {
                                QuestSearchArea questArea = area as QuestSearchArea;

                                if (questArea.DataQuest != null)
                                {
                                    areaInfo += T(client, "GMCommands.Player.AreaDataQuestId", questArea.DataQuest.ID);

                                    if (questArea.Step > 0)
                                    {
                                        areaInfo += T(client, "GMCommands.Player.AreaQuestStep", questArea.Step);
                                    }
                                    else
                                    {
                                        areaInfo += T(client, "GMCommands.Player.AreaEligible", questArea.DataQuest.CheckQuestQualification(targetPlayer));
                                    }
                                }
                            }
                            areaList.Add(areaInfo);
                        }

                        if (areaList.Count == 0) areaList.Add(T(client, "GMCommands.Player.None"));

                        client.Player.Out.SendCustomTextWindow(T(client, "GMCommands.Player.CurrentAreasTitle", targetPlayer.Name), areaList);
                    }
                    break;
                #endregion
            }
        }

		private void SendResistEffect(GamePlayer target)
		{
			if (target != null)
			{
				foreach (GamePlayer nearPlayer in target.GetPlayersInRadius(WorldMgr.VISIBILITY_DISTANCE))
				{
					nearPlayer.Out.SendSpellEffectAnimation(target, target, 7011, 0, false, 0);
				}
			}
		}

		private static void KillPlayer(GameLiving killer, GamePlayer player)
		{
			int damage = player.Health;
			if (damage > 0)
				player.TakeDamage(killer, eDamageType.Natural, damage, 0);
		}

		private void Show_Inventory(GamePlayer player, GameClient client, string limitType)
		{
			var text = new List<string>();
			text.Add(T(client, "GMCommands.Player.InventoryNameLastname", player.Name, player.LastName));
			text.Add(T(client, "GMCommands.Player.InventoryRealmLevelClass", GlobalConstants.RealmToName(player.Realm), player.Level, player.CharacterClass.Name));
			text.Add(" ");
			text.Add(Money.GetShortString(player.GetCurrentMoney()));
			text.Add(" ");

			bool limitShown = false;


			if (limitType == string.Empty || limitType == "wear")
			{
				limitShown = true;
				text.Add(T(client, "GMCommands.Player.InventoryWearing"));

				foreach (DbInventoryItem item in player.Inventory.EquippedItems)
				{
					text.Add("     [" + GlobalConstants.SlotToName(item.Item_Type) + "] " + item.Name + " (" + item.Id_nb + ")");
				}
				text.Add(" ");
			}

			if (limitType == string.Empty || limitType == "bag")
			{
				limitShown = true;
				text.Add(T(client, "GMCommands.Player.InventoryBackpack"));
				foreach (DbInventoryItem item in player.Inventory.AllItems)
				{
					if (item.SlotPosition >= (int)eInventorySlot.FirstBackpack &&
						item.SlotPosition <= (int)eInventorySlot.LastBackpack)
					{
						text.Add(item.Count.ToString("000") + " " + item.Name + " (" + item.Id_nb + ")");
					}
				}
			}

			if (limitType == "vault")
			{
				limitShown = true;
				text.Add(T(client, "GMCommands.Player.InventoryVault"));
				foreach (DbInventoryItem item in player.Inventory.AllItems)
				{
					if (item.SlotPosition >= (int)eInventorySlot.FirstVault && item.SlotPosition <= (int)eInventorySlot.LastVault)
					{
						text.Add(item.Count.ToString("000") + " " + item.Name + " (" + item.Id_nb + ")");
					}
				}
			}

			if (limitType == "house")
			{
				limitShown = true;
				text.Add(T(client, "GMCommands.Player.InventoryHousing"));
				foreach (DbInventoryItem item in player.Inventory.AllItems)
				{
					if (item.SlotPosition >= (int)eInventorySlot.HouseVault_First &&
						item.SlotPosition <= (int)eInventorySlot.HouseVault_Last)
					{
						text.Add(item.Count.ToString("000") + " " + item.Name + " (" + item.Id_nb + ")");
					}
				}
			}

			if (limitType == "cons")
			{
				limitShown = true;
				text.Add(T(client, "GMCommands.Player.InventoryConsignment"));
				foreach (DbInventoryItem item in player.Inventory.AllItems)
				{
					if (item.SlotPosition >= (int)eInventorySlot.Consignment_First &&
						item.SlotPosition <= (int)eInventorySlot.Consignment_Last)
					{
						text.Add(item.Count.ToString("000") + " " + item.Name + " (" + item.Id_nb + ")");
					}
				}
			}

			if (!limitShown)
			{
				text.Add(T(client, "GMCommands.Player.InventoryUnknownLimit"));
			}


			client.Out.SendCustomTextWindow(T(client, "GMCommands.Player.InventoryWindowTitle"), text);
		}

		private void Show_Info(GamePlayer player, GameClient client)
		{
			var text = new List<string>();
			text.Add(" ");
			text.Add(T(client, "GMCommands.Player.InfoHeader", player.Client.SessionID, player.GetType().FullName));
			text.Add(T(client, "GMCommands.Player.InfoNameLastname", player.Name, player.LastName));
			text.Add(T(client, "GMCommands.Player.InfoRealmLevelGenderClass", GlobalConstants.RealmToName(player.Realm), player.Level, player.Gender, player.CharacterClass.Name, player.CharacterClass.ID));
			text.Add(T(client, "GMCommands.Player.InfoGuild", player.GuildName, player.GuildRank != null ? T(client, "GMCommands.Player.InfoGuildRank", player.GuildRank.RankLevel) : ""));
			text.Add(T(client, "GMCommands.Player.InfoPoints", player.Experience, player.RealmPoints, player.BountyPoints));

			if (player.Champion)
			{
				text.Add(T(client, "GMCommands.Player.InfoChampion", player.ChampionLevel, player.ChampionExperience));

				string activeBags = T(client, "GMCommands.Player.None");
				if (player.ActiveSaddleBags != 0)
				{
					if (player.ActiveSaddleBags == (byte)eHorseSaddleBag.All)
					{
						activeBags = T(client, "GMCommands.Player.All");
					}
					else
					{
						activeBags = string.Empty;

						if ((player.ActiveSaddleBags & (byte)eHorseSaddleBag.LeftFront) > 0)
						{
							if (activeBags != string.Empty)
								activeBags += ", ";

							activeBags += T(client, "GMCommands.Player.SaddlebagLeftFront");
						}
						if ((player.ActiveSaddleBags & (byte)eHorseSaddleBag.RightFront) > 0)
						{
							if (activeBags != string.Empty)
								activeBags += ", ";

							activeBags += T(client, "GMCommands.Player.SaddlebagRightFront");
						}
						if ((player.ActiveSaddleBags & (byte)eHorseSaddleBag.LeftRear) > 0)
						{
							if (activeBags != string.Empty)
								activeBags += ", ";

							activeBags += T(client, "GMCommands.Player.SaddlebagLeftRear");
						}
						if ((player.ActiveSaddleBags & (byte)eHorseSaddleBag.RightRear) > 0)
						{
							if (activeBags != string.Empty)
								activeBags += ", ";

							activeBags += T(client, "GMCommands.Player.SaddlebagRightRear");
						}
					}
				}

				text.Add(T(client, "GMCommands.Player.InfoActiveSaddlebags", activeBags, player.ActiveSaddleBags));
			}
			else
			{
				text.Add(T(client, "GMCommands.Player.InfoChampionNotStarted"));
			}
			if (player.MLGranted)
			{
				text.Add(T(client, "GMCommands.Player.InfoMasterLevels", player.MLLevel, player.MLExperience, player.MLLine));
			}
			else
			{
				text.Add(T(client, "GMCommands.Player.InfoMasterLevelsNotStarted"));
			}
			text.Add(T(client, "GMCommands.Player.InfoCraftingSkill", player.CraftingPrimarySkill));
			text.Add(T(client, "GMCommands.Player.InfoMoney", Money.GetString(player.GetCurrentMoney())));
			text.Add(T(client, "GMCommands.Player.InfoModelId", player.Model));
			text.Add(T(client, "GMCommands.Player.InfoRegionOid", player.ObjectID));
			text.Add(T(client, "GMCommands.Player.InfoAfkMessage", player.TempProperties.GetProperty<string>(GamePlayer.AFK_MESSAGE)));
			text.Add(" ");
			text.Add(T(client, "GMCommands.Player.InfoHouseHeader"));
			text.Add(T(client, "GMCommands.Player.InfoPersonalHouse", HouseMgr.GetHouseNumberByPlayer(player)));
			if (player.CurrentHouse != null && player.CurrentHouse.HouseNumber > 0)
				text.Add(T(client, "GMCommands.Player.InfoCurrentHouse", player.CurrentHouse.HouseNumber));
			text.Add(T(client, "GMCommands.Player.InfoInHouse", player.InHouse));
			text.Add(" ");
			text.Add(T(client, "GMCommands.Player.InfoAccountHeader"));
			text.Add(T(client, "GMCommands.Player.InfoAccountNameIp", player.Client.Account.Name, player.Client.Account.LastLoginIP));
			text.Add(T(client, "GMCommands.Player.InfoPrivLevel", player.Client.Account.PrivLevel));
			text.Add(T(client, "GMCommands.Player.InfoClientVersion", player.Client.Account.LastClientVersion));
			text.Add(" ");
			text.Add(T(client, "GMCommands.Player.InfoStatsHeader"));

			String sCurrent = string.Empty;
			String sTitle = string.Empty;
			int cnt = 0;

			for (eProperty stat = eProperty.Stat_First; stat <= eProperty.Stat_Last; stat++, cnt++)
			{
				sTitle += GlobalConstants.PropertyToName(stat) + "/";
				sCurrent += player.GetModified(stat) + "/";
				if (cnt == 3)
				{
					text.Add(T(client, "GMCommands.Player.InfoCurrentStats", sTitle, sCurrent));
					sTitle = string.Empty;
					sCurrent = string.Empty;
				}
			}
			text.Add(T(client, "GMCommands.Player.InfoCurrentStats", sTitle, sCurrent));

			sCurrent = string.Empty;
			sTitle = string.Empty;
			cnt = 0;
			for (eProperty res = eProperty.Resist_First; res <= eProperty.Resist_Last; res++, cnt++)
			{
				sTitle += GlobalConstants.PropertyToName(res) + "/";
				sCurrent += player.GetModified(res) + "/";
				if (cnt == 2)
				{
					text.Add(T(client, "GMCommands.Player.InfoCurrentValues", sTitle, sCurrent));
					sCurrent = string.Empty;
					sTitle = string.Empty;
				}
				if (cnt == 5)
				{
					text.Add(T(client, "GMCommands.Player.InfoCurrentValues", sTitle, sCurrent));
					sCurrent = string.Empty;
					sTitle = string.Empty;
				}
			}
			text.Add(T(client, "GMCommands.Player.InfoCurrentValues", sTitle, sCurrent));

			text.Add(T(client, "GMCommands.Player.InfoMaximumHealth", player.MaxHealth));
			text.Add(T(client, "GMCommands.Player.InfoCurrentAfAbs", player.GetModified(eProperty.ArmorFactor), player.GetModified(eProperty.ArmorAbsorption)));
			text.Add(" ");
			text.Add(T(client, "GMCommands.Player.InfoSpeccingHeader"));
			text.Add(T(client, "GMCommands.Player.InfoRespecsAvailable", player.RespecAmountDOL, player.RespecAmountSingleSkill, player.RespecAmountAllSkill));
			text.Add(T(client, "GMCommands.Player.InfoRemainingSpecPoints", player.SkillSpecialtyPoints));
			sTitle = T(client, "GMCommands.Player.InfoPlayerSpecialisations");
			sCurrent = string.Empty;
			foreach (Specialization spec in player.GetSpecList())
			{
				sCurrent += spec.Name + " = " + spec.Level + " ; ";
			}
			text.Add(sTitle + sCurrent);

			client.Out.SendCustomTextWindow(T(client, "GMCommands.Player.InfoWindowTitle"), text);
        }
        public void SetClass(GamePlayer target, int classID)
        {
            //remove all their tricks and abilities!
            target.RemoveAllSpecs();
            target.RemoveAllSpellLines();
            target.styleComponent.RemoveAllStyles();

            //reset before, and after changing the class.
            target.Reset();
            target.SetCharacterClass(classID);
            target.Reset();

            //this is just for additional updates
            //that add all the new class changes.
            target.OnLevelUp(0);

            target.Out.SendUpdatePlayer();
            target.Out.SendUpdatePlayerSkills(true);
            target.Out.SendUpdatePoints();
        }
	}
}
