using System;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&respec",
        ePrivLevel.Player,
        "Respecs the char",
        "/respec")]
    public class RespecCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        const string RA_RESPEC = "realm_respec";
        const string ALL_RESPEC = "all_respec";
        const string LINE_RESPEC = "line_respec";
        const string DOL_RESPEC = "dol_respec";
        const string BUY_RESPEC = "buy_respec";
        const string CHAMP_RESPEC = "champion_respec";

        public void OnCommand(GameClient client, string[] args)
        {
            if (args.Length < 2)
            {
                if (ServerProperties.Properties.FREE_RESPEC || client.Player.Level < 50)
                {
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.TargetTrainer"));
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.HelpAll"));
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.HelpLine"));
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.HelpRealm"));
                    //DisplayMessage(client, "/respec CHAMPION to respec champion abilities");
                    return;
                }

                // Check for respecs.
                if (client.Player.RespecAmountAllSkill < 1
                    && client.Player.RespecAmountSingleSkill < 1
                    && client.Player.RespecAmountDOL <1
                    && client.Player.RespecAmountRealmSkill < 1)
                {
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.NoneAvailable"));
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.BuyHint"));
                    return;
                }

                if (client.Player.RespecAmountAllSkill > 0)
                {
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.FullAvailable", client.Player.RespecAmountAllSkill));
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.UseAll"));
                }
                if (client.Player.RespecAmountSingleSkill > 0)
                {
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.LineAvailable", client.Player.RespecAmountSingleSkill));
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.UseLine"));
                }
                if (client.Player.RespecAmountRealmSkill > 0)
                {
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.RealmAvailable", client.Player.RespecAmountRealmSkill));
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.UseRealm"));
                }
                if (client.Player.RespecAmountDOL > 0)
                {
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.DolAvailable", client.Player.RespecAmountDOL));
                    DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.UseAllLower"));
                }
                DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.BuyHint"));
                return;
            }

            GameTrainer trainer = client.Player.TargetObject as GameTrainer;
            // Player must be speaking with trainer to respec.  (Thus have trainer targeted.) Prevents losing points out in the wild.
            if (args[1].ToLower() != "buy" && (trainer == null || !trainer.CanTrain(client.Player)))
            {
                DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.MustSpeakTrainer"));
                return;
            }

            switch (args[1].ToLower())
            {
                //case "buy":
                //	{
                //		if (ServerProperties.Properties.FREE_RESPEC)
                //			return;

                //		// Buy respec
                //		if (client.Player.CanBuyRespec == false || client.Player.RespecCost < 0)
                //		{
                //			DisplayMessage(client, "You can't buy a respec on this level again.");
                //			return;
                //		}

                //		long mgold = client.Player.RespecCost;
                //		if ((client.Player.Gold + 1000 * client.Player.Platinum) < mgold)
                //		{
                //			DisplayMessage(client, "You don't have enough money! You need " + mgold + " gold!");
                //			return;
                //		}
                //		client.Out.SendCustomDialog("It costs " + mgold + " gold. Want you really buy?", new CustomDialogResponse(RespecDialogResponse));
                //		client.Player.TempProperties.setProperty(BUY_RESPEC, true);
                //		break;
                //	}
                case "all":
                    {
                        if (/*client.Player.Level >= 50 || */TimeSpan.FromSeconds(client.Player.PlayedTimeSinceLevel).Hours > 24)
                        {
                            // Check for full respecs.
                            if ( client.Player.RespecAmountAllSkill < 1
                                && !ServerProperties.Properties.FREE_RESPEC)
                            {
                                DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.NoFull"));
                                return;
                            }
                        }

                        client.Out.SendCustomDialog(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.Caution"), new CustomDialogResponse(RespecDialogResponse));
                        client.Player.TempProperties.SetProperty(ALL_RESPEC, true);

                        break;
                    }
                //case "dol":
                //	{
                //		// Check for DOL respecs.
                //		if (client.Player.RespecAmountDOL < 1
                //			&& !ServerProperties.Properties.FREE_RESPEC)
                //		{
                //			DisplayMessage(client, "You don't seem to have any DOL respecs available.");
                //			return;
                //		}

                //		client.Out.SendCustomDialog("CAUTION: All respec changes are final with no second chance. Proceed carefully!", new CustomDialogResponse(RespecDialogResponse));
                //		client.Player.TempProperties.setProperty(DOL_RESPEC, true);
                //		break;
                //	}
                case "realm":
                    {
                        if (/*client.Player.Level >= 50 || */TimeSpan.FromSeconds(client.Player.PlayedTimeSinceLevel).Hours > 24)
                        {
                            if (client.Player.RespecAmountRealmSkill < 1
                                && !ServerProperties.Properties.FREE_RESPEC)
                            {
                                DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.NoRealm"));
                                return;
                            }
                        }
                        client.Out.SendCustomDialog(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.Caution"), new CustomDialogResponse(RespecDialogResponse));
                        client.Player.TempProperties.SetProperty(RA_RESPEC, true);
                        break;
                    }
                //case "champion":
                //	{
                //		if (ServerProperties.Properties.FREE_RESPEC)
                //		{
                //			client.Out.SendCustomDialog("CAUTION: All respec changes are final with no second chance. Proceed carefully!", new CustomDialogResponse(RespecDialogResponse));
                //			client.Player.TempProperties.setProperty(CHAMP_RESPEC, true);
                //			break;
                //		}
                //		return;
                //	}
                default:
                    {
                        if (/*client.Player.Level >= 50 || */TimeSpan.FromSeconds(client.Player.PlayedTimeSinceLevel).Hours > 24)
                        {
                            // Check for single-line respecs.
                            if (client.Player.RespecAmountSingleSkill < 1
                            && !ServerProperties.Properties.FREE_RESPEC)
                            {
                                DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.NoLine"));
                                return;
                            }
                        }

                        string lineName = string.Join(" ", args, 1, args.Length - 1);
                        Specialization specLine = client.Player.GetSpecializationByName(lineName);

                        if (specLine == null)
                        {
                            DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.LineNotFound", lineName));
                            return;
                        }
                        if (specLine.Level < 2)
                        {
                            DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.LineLevelTooLow", specLine.Name));
                            return;
                        }

                        client.Out.SendCustomDialog(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Respec.Caution"), new CustomDialogResponse(RespecDialogResponse));
                        client.Player.TempProperties.SetProperty(LINE_RESPEC, specLine);
                        break;
                    }
            }
        }


        protected void RespecDialogResponse(GamePlayer player, byte response)
        {
            if (response != 0x01) return; //declined

            int specPoints = player.SkillSpecialtyPoints;
            int realmSpecPoints = player.RealmSpecialtyPoints;

            if (player.TempProperties.GetProperty<bool>(ALL_RESPEC))
            {
                player.RespecAll();
                player.TempProperties.RemoveProperty(ALL_RESPEC);
            }
            if (player.TempProperties.GetProperty<bool>(DOL_RESPEC))
            {
                player.RespecDOL();
                player.TempProperties.RemoveProperty(DOL_RESPEC);
            }
            if (player.TempProperties.GetProperty<bool>(RA_RESPEC))
            {
                player.RespecRealm();
                player.TempProperties.RemoveProperty(RA_RESPEC);
            }
            if (player.TempProperties.GetProperty<bool>(CHAMP_RESPEC))
            {
                player.RespecChampionSkills();
                player.TempProperties.RemoveProperty(CHAMP_RESPEC);
            }
            Specialization specLine = player.TempProperties.GetProperty<Specialization>(LINE_RESPEC);
            if (specLine != null)
            {
                player.RespecSingle(specLine);
                player.TempProperties.RemoveProperty(LINE_RESPEC);
            }
            if (player.TempProperties.GetProperty<bool>(BUY_RESPEC))
            {
                player.TempProperties.RemoveProperty(BUY_RESPEC);
                if (player.RespecCost >= 0 && player.RemoveMoney(player.RespecCost * 10000))
                {
                    InventoryLogging.LogInventoryAction(player, "(respec)", eInventoryActionType.Merchant, player.RespecCost * 10000);
                    player.RespecAmountSingleSkill++;
                    player.RespecBought++;
                    DisplayMessage(player, T(player, "Scripts.Players.Respec.BoughtSingleLine"));
                }
                player.Out.SendUpdateMoney();
            }
            // Assign full points returned
            if (player.SkillSpecialtyPoints > specPoints)
            {
                player.styleComponent.RemoveAllStyles(); // Kill styles
                DisplayMessage(player, T(player, "Scripts.Players.Respec.RegainSpecPoints", player.SkillSpecialtyPoints - specPoints));
            }
            if (player.RealmSpecialtyPoints > realmSpecPoints)
            {
                 DisplayMessage(player, T(player, "Scripts.Players.Respec.RegainRealmSpecPoints", player.RealmSpecialtyPoints - realmSpecPoints));
            }

            player.RefreshSpecDependantSkills(false);
            player.Out.SendUpdatePlayerSkills(true);
            player.Out.SendUpdatePoints();
            player.Out.SendUpdatePlayer();
            player.SendTrainerWindow();
            player.SaveIntoDatabase();

            ClearRelevantBuffs(player);
        }

        private static void ClearRelevantBuffs(GamePlayer player)
        {
            // Every buff casted on self.
            foreach (ECSGameEffect effect in player.effectListComponent.GetEffects())
            {
                if (effect.SpellHandler?.Caster == player)
                    effect.End();
            }

            // Every pulsing effect (not returned by GetEffects).
            foreach (ECSGameEffect effect in player.effectListComponent.GetPulseEffects())
            {
                if (effect.SpellHandler?.Caster == player)
                    effect.End();
            }

            // Every concentration buff casted on self or on other entities.
            foreach (ECSGameEffect effect in player.effectListComponent.GetConcentrationEffects())
                effect.End();

            // Kill the pet.
            // We could keep charmed pets alive, but since we had to cancel pulsing spells, they would end up attacking the player.
            player.ControlledBrain?.Body.Die(null);
        }
    }
}
