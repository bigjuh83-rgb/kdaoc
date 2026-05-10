using System;
using System.Reflection;
using System.Threading;
using DOL.AI.Brain;
using DOL.Database;
using DOL.Events;
using DOL.GS.PacketHandler;

namespace DOL.GS.Quests.Albion;

public class LostStoneofArawn : BaseQuest
{
    private const string questTitle = "Lost Stone of Arawn";
    private const int minimumLevel = 48;
    private const int maximumLevel = 50;

    /// <summary>
    ///     Defines a logger for this class.
    /// </summary>
    private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

    private static GameNPC Honaytrt; // Start NPC Honayt'rt
    private static GameNPC Nchever; // N'chever
    private static GameNPC Ohonat; // O'honat
    private static GameNPC Nyaegha; // Nyaegha

    private static readonly GameLocation demonLocation = new("Nyaegha", 51, 348381, 479838, 3320);

    private static AbstractArea demonArea;

    private static DbItemTemplate ancient_copper_necklace;
    private static DbItemTemplate scroll_wearyall_loststone;
    private static DbItemTemplate lost_stone_of_arawn;

    // Constructors
    public LostStoneofArawn()
    {
    }

    public LostStoneofArawn(GamePlayer questingPlayer) : base(questingPlayer)
    {
    }

    public LostStoneofArawn(GamePlayer questingPlayer, int step) : base(questingPlayer, step)
    {
    }

    public LostStoneofArawn(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest)
    {
    }

    private static string L(GamePlayer player, string key, params object[] args)
    {
        return DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, key, args);
    }

    public override int Level =>
        // Quest Level
        minimumLevel;

    //Set quest name
    public override string Name => questTitle;

    // Define Steps
    public override string Description
    {
        get
        {
            switch (Step)
            {
                case 1:
                    return L(m_questPlayer, "Quest.Albion.LostStoneOfArawn.Description1");
                case 2:
                    return L(m_questPlayer, "Quest.Albion.LostStoneOfArawn.Description2");
                case 3:
                    return L(m_questPlayer, "Quest.Albion.LostStoneOfArawn.Description3");
                case 4:
                    return L(m_questPlayer, "Quest.Albion.LostStoneOfArawn.Description4");
                case 5:
                    return L(m_questPlayer, "Quest.Albion.LostStoneOfArawn.Description5");
                case 6:
                    return L(m_questPlayer, "Quest.Albion.LostStoneOfArawn.Description6");
            }

            return base.Description;
        }
    }

    [ScriptLoadedEvent]
    public static void ScriptLoaded(DOLEvent e, object sender, EventArgs args)
    {
        if (!ServerProperties.Properties.LOAD_QUESTS)
            return;


        #region defineNPCs

        var npcs = WorldMgr.GetNPCsByName("Honayt\'rt", eRealm.Albion);

        if (npcs.Length > 0)
            foreach (var npc in npcs)
                if (npc.CurrentRegionID == 51 && npc.X == 435217 && npc.Y == 495273)
                {
                    Honaytrt = npc;
                    break;
                }

        if (Honaytrt == null)
        {
            if (log.IsWarnEnabled)
                log.Warn("Could not find Honaytrt, creating it ...");
            Honaytrt = new GameNPC();
            Honaytrt.Model = 759;
            Honaytrt.Name = "Honayt\'rt";
            Honaytrt.GuildName = string.Empty;
            Honaytrt.Realm = eRealm.Albion;
            Honaytrt.CurrentRegionID = 51;
            Honaytrt.LoadEquipmentTemplateFromDatabase("097fe8c1-7d7e-4b82-a7ca-04a6e192afc1");
            Honaytrt.Size = 51;
            Honaytrt.Level = 50;
            Honaytrt.X = 435217;
            Honaytrt.Y = 495273;
            Honaytrt.Z = 3134;
            Honaytrt.Heading = 3270;
            Honaytrt.AddToWorld();
            if (SAVE_INTO_DATABASE) Honaytrt.SaveIntoDatabase();
        }

        npcs = WorldMgr.GetNPCsByName("N\'chever", eRealm.Albion);

        if (npcs.Length > 0)
            foreach (var npc in npcs)
                if (npc.CurrentRegionID == 51 && npc.X == 30763 && npc.Y == 29908)
                {
                    Nchever = npc;
                    break;
                }

        if (Nchever == null)
        {
            if (log.IsWarnEnabled)
                log.Warn("Could not find Nchever , creating it ...");
            Nchever = new GameNPC();
            Nchever.Model = 752;
            Nchever.Name = "N\'chever";
            Nchever.GuildName = string.Empty;
            Nchever.Realm = eRealm.Albion;
            Nchever.CurrentRegionID = 51;
            Nchever.LoadEquipmentTemplateFromDatabase("a2639e94-f032-4041-ad67-15dfeaf004d2");
            Nchever.Size = 51;
            Nchever.Level = 52;
            Nchever.X = 435972;
            Nchever.Y = 492370;
            Nchever.Z = 3087;
            Nchever.Heading = 594;
            Nchever.AddToWorld();
            if (SAVE_INTO_DATABASE) Nchever.SaveIntoDatabase();
        }
        // end npc

        npcs = WorldMgr.GetNPCsByName("O\'honat", eRealm.Albion);

        if (npcs.Length > 0)
            foreach (var npc in npcs)
                if (npc.CurrentRegionID == 51 && npc.X == 404696 && npc.Y == 503469)
                {
                    Ohonat = npc;
                    break;
                }

        if (Ohonat == null)
        {
            if (log.IsWarnEnabled)
                log.Warn("Could not find Ohonat , creating it ...");
            Ohonat = new GameNPC();
            Ohonat.LoadEquipmentTemplateFromDatabase("a58ef747-80e0-4cda-9052-15711ea0f4f7");
            Ohonat.Model = 761;
            Ohonat.Name = "O\'honat";
            Ohonat.GuildName = string.Empty;
            Ohonat.Realm = eRealm.Albion;
            Ohonat.CurrentRegionID = 51;
            Ohonat.Size = 52;
            Ohonat.Level = 50;
            Ohonat.X = 404696;
            Ohonat.Y = 503469;
            Ohonat.Z = 5192;
            Ohonat.Heading = 1037;
            Ohonat.VisibleActiveWeaponSlots = 51;
            Ohonat.Flags ^= GameNPC.eFlags.PEACE;
            Ohonat.MaxSpeedBase = 200;
            Ohonat.AddToWorld();
            if (SAVE_INTO_DATABASE) Ohonat.SaveIntoDatabase();
        }
        // end npc

        #endregion

        #region defineItems

        ancient_copper_necklace = GameServer.Database.FindObjectByKey<DbItemTemplate>("ancient_copper_necklace");


        scroll_wearyall_loststone = GameServer.Database.FindObjectByKey<DbItemTemplate>("scroll_wearyall_loststone");
        if (scroll_wearyall_loststone == null)
        {
            if (log.IsWarnEnabled)
                log.Warn("Could not find Victory Speech for Albion, creating it ...");
            scroll_wearyall_loststone = new DbItemTemplate();
            scroll_wearyall_loststone.Id_nb = "scroll_wearyall_loststone";
            scroll_wearyall_loststone.Name = "Victory Speech for Albion";
            scroll_wearyall_loststone.Level = 5;
            scroll_wearyall_loststone.Item_Type = 0;
            scroll_wearyall_loststone.Model = 498;
            scroll_wearyall_loststone.IsDropable = true;
            scroll_wearyall_loststone.IsTradable = false;
            scroll_wearyall_loststone.IsIndestructible = true;
            scroll_wearyall_loststone.IsPickable = true;
            scroll_wearyall_loststone.DPS_AF = 0;
            scroll_wearyall_loststone.SPD_ABS = 0;
            scroll_wearyall_loststone.Object_Type = 0;
            scroll_wearyall_loststone.Hand = 0;
            scroll_wearyall_loststone.Type_Damage = 0;
            scroll_wearyall_loststone.Quality = 100;
            scroll_wearyall_loststone.Weight = 1;
            scroll_wearyall_loststone.Description =
                "Bring this Speech to Honayt\'rt in Wearyall Village. She will be interested in reading this scroll.";
            if (SAVE_INTO_DATABASE) GameServer.Database.AddObject(scroll_wearyall_loststone);
        }

        lost_stone_of_arawn = GameServer.Database.FindObjectByKey<DbItemTemplate>("lost_stone_of_arawn");
        if (lost_stone_of_arawn == null)
        {
            if (log.IsWarnEnabled)
                log.Warn("Could not find Lost Stone of Arawn, creating it ...");
            lost_stone_of_arawn = new DbItemTemplate();
            lost_stone_of_arawn.Id_nb = "lost_stone_of_arawn";
            lost_stone_of_arawn.Name = "Lost Stone of Arawn";
            lost_stone_of_arawn.Level = 55;
            lost_stone_of_arawn.Item_Type = 0;
            lost_stone_of_arawn.Model = 110;
            lost_stone_of_arawn.IsDropable = true;
            lost_stone_of_arawn.IsTradable = false;
            lost_stone_of_arawn.IsIndestructible = true;
            lost_stone_of_arawn.IsPickable = true;
            lost_stone_of_arawn.DPS_AF = 0;
            lost_stone_of_arawn.SPD_ABS = 0;
            lost_stone_of_arawn.Object_Type = 0;
            lost_stone_of_arawn.Hand = 0;
            lost_stone_of_arawn.Type_Damage = 0;
            lost_stone_of_arawn.Quality = 100;
            lost_stone_of_arawn.Weight = 1;
            lost_stone_of_arawn.Description = "A stone of infinite power.";
            if (SAVE_INTO_DATABASE) GameServer.Database.AddObject(lost_stone_of_arawn);
        }
        //Item Descriptions End

        #endregion

        const int radius = 1500;
        var region = WorldMgr.GetRegion(demonLocation.RegionID);
        if (region == null)
        {
            log.Error("Could not find region " + demonLocation.RegionID + " when trying to create " + questTitle + " demon area.");
            return;
        }

        demonArea = new Area.Circle("demonic patch", demonLocation.X, demonLocation.Y, demonLocation.Z,
            radius);
        demonArea.CanBroadcast = false;
        demonArea.DisplayMessage = false;
        region.AddArea(demonArea);
        demonArea.RegisterPlayerEnter(PlayerEnterDemonArea);

        GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, SubscribeQuest);
        GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, SubscribeQuest);

        GameEventMgr.AddHandler(Honaytrt, GameObjectEvent.Interact, TalkToHonaytrt);
        GameEventMgr.AddHandler(Honaytrt, GameLivingEvent.WhisperReceive, TalkToHonaytrt);

        GameEventMgr.AddHandler(Nchever, GameObjectEvent.Interact, TalkToNchever);
        GameEventMgr.AddHandler(Nchever, GameLivingEvent.WhisperReceive, TalkToNchever);

        GameEventMgr.AddHandler(Ohonat, GameObjectEvent.Interact, TalkToOhonat);
        GameEventMgr.AddHandler(Ohonat, GameLivingEvent.WhisperReceive, TalkToOhonat);

        Honaytrt.AddQuestToGive(typeof(LostStoneofArawn));

        if (log.IsInfoEnabled)
            log.Info("Quest \"" + questTitle + "\" initialized");
    }

    [ScriptUnloadedEvent]
    public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
    {
        //if not loaded, don't worry
        if (Honaytrt == null)
            return;
        // remove handlers
        GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, SubscribeQuest);
        GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, SubscribeQuest);

        demonArea.UnRegisterPlayerEnter(PlayerEnterDemonArea);
        WorldMgr.GetRegion(demonLocation.RegionID)?.RemoveArea(demonArea);

        GameEventMgr.RemoveHandler(Honaytrt, GameObjectEvent.Interact, TalkToHonaytrt);
        GameEventMgr.RemoveHandler(Honaytrt, GameLivingEvent.WhisperReceive, TalkToHonaytrt);

        GameEventMgr.RemoveHandler(Nchever, GameObjectEvent.Interact, TalkToNchever);
        GameEventMgr.RemoveHandler(Nchever, GameLivingEvent.WhisperReceive, TalkToNchever);

        GameEventMgr.RemoveHandler(Ohonat, GameObjectEvent.Interact, TalkToOhonat);
        GameEventMgr.RemoveHandler(Ohonat, GameLivingEvent.WhisperReceive, TalkToOhonat);

        /* Now we remove to Honaytrt the possibility to give this quest to players */
        Honaytrt.RemoveQuestToGive(typeof(LostStoneofArawn));
    }

    protected virtual void CreateNyaegha(GamePlayer player)
    {
        Nyaegha = new SINeckBoss();
        Nyaegha.LoadEquipmentTemplateFromDatabase("Nyaegha");
        Nyaegha.Model = 605;
        Nyaegha.Name = "Nyaegha";
        Nyaegha.GuildName = string.Empty;
        Nyaegha.Realm = eRealm.None;
        Nyaegha.Race = 2001;
        Nyaegha.BodyType = (ushort) NpcTemplateMgr.eBodyType.Demon;
        Nyaegha.CurrentRegionID = 51;
        Nyaegha.Size = 150;
        Nyaegha.Level = 65;
        Nyaegha.X = 348381;
        Nyaegha.Y = 479838;
        Nyaegha.Z = 3320;
        Nyaegha.VisibleActiveWeaponSlots = 34;
        Nyaegha.MaxSpeedBase = 250;
        Nyaegha.AddToWorld();

        var brain = new SINeckBossBrain();
        brain.AggroLevel = 200;
        brain.AggroRange = 500;
        Nyaegha.SetOwnBrain(brain);

        Nyaegha.AddToWorld();

        Nyaegha.StartAttack(player);

        GameEventMgr.AddHandler(Nyaegha, GameLivingEvent.Dying, NyaeghaDying);
    }
    private void NyaeghaDying(DOLEvent e, object sender, EventArgs arguments)
    {
        var args = (DyingEventArgs) arguments;

        var player = args.Killer as GamePlayer;

        if (player == null)
            return;

        if (player.Group != null)
        {
            foreach (var gpl in player.Group.GetPlayersInTheGroup())
            {
                AdvanceAfterKill(gpl);
            }
        }
        else
        {
            AdvanceAfterKill(player);
        }

        GameEventMgr.RemoveHandler(Nyaegha, GameLivingEvent.Dying, NyaeghaDying);
        Nyaegha.Delete();
    }
    private static void AdvanceAfterKill(GamePlayer player)
    {
        var quest = player.IsDoingQuest(typeof(LostStoneofArawn)) as LostStoneofArawn;
        if (quest is not {Step: 4}) return;
        if (!player.Inventory.IsSlotsFree(1, eInventorySlot.FirstBackpack, eInventorySlot.LastBackpack))
            player.Out.SendMessage(
                L(player, "Quest.Albion.LostStoneOfArawn.NoRoomForStone", lost_stone_of_arawn.Name),
                eChatType.CT_Important, eChatLoc.CL_SystemWindow);
        GiveItem(player, lost_stone_of_arawn);
        quest.Step = 5;
    }

    private static void PlayerEnterDemonArea(DOLEvent e, object sender, EventArgs args)
    {
        var aargs = args as AreaEventArgs;
        var player = aargs?.GameObject as GamePlayer;

        if (player == null)
            return;

        var quest = player.IsDoingQuest(typeof(LostStoneofArawn)) as LostStoneofArawn;

        if (quest is not {Step: 4}) return;

        var existingCopy = WorldMgr.GetNPCsByName("Nyaegha", eRealm.None);

        if (existingCopy.Length > 0) return;

        //only try to spawn him once per trigger even if multiple people enter at the same time
        if (_spawnLock.TryEnter())
        {
            try
            {
                // player near demon
                SendSystemMessage(player,
                    L(player, "Quest.Albion.LostStoneOfArawn.EnterDemonArea"));
                player.Out.SendMessage(L(player, "Quest.Albion.LostStoneOfArawn.NyaeghaAmbush"), eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
                quest.CreateNyaegha(player);
            }
            finally
            {
                _spawnLock.Exit();
            }
        }
        else
        {
            return;
        }
    }

    private static readonly Lock _spawnLock = new();

    private static void TalkToHonaytrt(DOLEvent e, object sender, EventArgs args)
    {
        //We get the player from the event arguments and check if he qualifies
        var player = ((SourceEventArgs) args).Source as GamePlayer;
        if (player == null)
            return;

        if (Honaytrt.CanGiveQuest(typeof(LostStoneofArawn), player) <= 0)
            return;

        //We also check if the player is already doing the quest
        var quest = player.IsDoingQuest(typeof(LostStoneofArawn)) as LostStoneofArawn;

        if (e == GameObjectEvent.Interact)
        {
            if (quest != null)
                switch (quest.Step)
                {
                    case 1:
                        Honaytrt.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.HonaytrtStep1"));
                        break;
                    case 2:
                        Honaytrt.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.HonaytrtStep2", player.Name));
                        break;
                    case 3:
                        Honaytrt.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.HonaytrtStep3"));
                        break;
                    case 4:
                        Honaytrt.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.HonaytrtStep4"));
                        break;
                    case 5:
                        Honaytrt.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.HonaytrtStep5"));
                        break;
                    case 6:
                        Honaytrt.SayTo(player, L(player, "Quest.Albion.LostStoneOfArawn.HonaytrtStep6", player.CharacterClass.Name));
                        break;
                }
            else
                Honaytrt.SayTo(player, L(player, "Quest.Albion.LostStoneOfArawn.HonaytrtGreeting", player.Name));
        }
        // The player whispered to the NPC
        else if (e == GameLivingEvent.WhisperReceive)
        {
            var wArgs = (WhisperReceiveEventArgs) args;
            if (quest == null)
                switch (wArgs.Text)
                {
                    case "help me":
						case "도와주기":
                        player.Out.SendQuestSubscribeCommand(Honaytrt,
                            QuestMgr.GetIDForQuestType(typeof(LostStoneofArawn)),
                            L(player, "Quest.Albion.LostStoneOfArawn.SubscribePrompt"));
                        break;
                }
            else
                switch (wArgs.Text)
                {
	                    case "Stone of Arawn":
	                    case "아로운의 돌":
                        if (quest.Step == 1)
                        {
                            quest.Step = 2;
                            Honaytrt.SayTo(player,
                                L(player, "Quest.Albion.LostStoneOfArawn.HonaytrtStoneOfArawn"));
                        }

                        break;
                    case "reward":
                    case "보상":
                        if (quest.Step == 6) quest.FinishQuest();
                        break;
                    case "abort":
                        player.Out.SendCustomDialog(
                            DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.AbortConfirm"),
                            CheckPlayerAbortQuest);
                        break;
                }
        }
        else if (e == GameObjectEvent.ReceiveItem)
        {
            var rArgs = (ReceiveItemEventArgs) args;
            if (quest != null)
            {
                /*if (rArgs.Item.Id_nb == .Id_nb)
                {
                    Honaytrt.SayTo(player, "Thank you "+ player.Name +".\n");
                    //quest.Step = 3;
                }*/
            }
        }
    }

    private static void TalkToNchever(DOLEvent e, object sender, EventArgs args)
    {
        //We get the player from the event arguments and check if he qualifies
        var player = ((SourceEventArgs) args).Source as GamePlayer;
        if (player == null)
            return;

        //We also check if the player is already doing the quest
        var quest = player.IsDoingQuest(typeof(LostStoneofArawn)) as LostStoneofArawn;

        if (e == GameObjectEvent.Interact)
        {
            if (quest != null)
                switch (quest.Step)
                {
                    case 1:
                        Nchever.SayTo(player, L(player, "Quest.Albion.LostStoneOfArawn.NcheverStep1", player.Name));
                        break;
                    case 2:
                        Nchever.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.NcheverStep2"));
                        break;
                    case 3:
                        Nchever.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.NcheverStep3", player.CharacterClass.Name));
                        break;
                    case 4:
                        Nchever.SayTo(player, L(player, "Quest.Albion.LostStoneOfArawn.NcheverStep4"));
                        break;
                    case 5:
                        Nchever.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.NcheverStep5"));
                        break;
                    case 6:
                        Nchever.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.NcheverStep6"));
                        break;
                }
            else
                Nchever.SayTo(player, L(player, "Quest.Albion.LostStoneOfArawn.NcheverGreeting"));
        }
        // The player whispered to the NPC
        else if (e == GameLivingEvent.WhisperReceive)
        {
            var wArgs = (WhisperReceiveEventArgs) args;
            if (quest == null)
                switch (wArgs.Text)
                {
                }
            else
                switch (wArgs.Text)
                {
                    case "stone":
						case "돌":
                        if (quest.Step == 2)
                            Nchever.SayTo(player,
                                L(player, "Quest.Albion.LostStoneOfArawn.NcheverStone"));
                        break;
	                    case "Lost Stone of Arawn":
	                    case "잃어버린 아로운의 돌":
                        if (quest.Step == 2)
                        {
                            quest.Step = 3;
                            Nchever.SayTo(player, L(player, "Quest.Albion.LostStoneOfArawn.NcheverLostStone"));
                        }

                        break;
                }
        }
    }

    private static void TalkToOhonat(DOLEvent e, object sender, EventArgs args)
    {
        //We get the player from the event arguments and check if he qualifies
        var player = ((SourceEventArgs) args).Source as GamePlayer;
        if (player == null)
            return;

        //We also check if the player is already doing the quest
        var quest = player.IsDoingQuest(typeof(LostStoneofArawn)) as LostStoneofArawn;

        if (e == GameObjectEvent.Interact)
        {
            if (quest != null)
                switch (quest.Step)
                {
                    case 1:
                        Ohonat.SayTo(player, L(player, "Quest.Albion.LostStoneOfArawn.OhonatStep1", Ohonat.Name));
                        break;
                    case 2:
                        Ohonat.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.OhonatStep2"));
                        break;
                    case 3:
                        Ohonat.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.OhonatStep3"));
                        break;
                    case 4:
                        Ohonat.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.OhonatStep4"));
                        break;
                    case 5:
                        Ohonat.SayTo(player,
                            L(player, "Quest.Albion.LostStoneOfArawn.OhonatStep5", player.Name));
                        break;
                    case 6:
                        Ohonat.SayTo(player, L(player, "Quest.Albion.LostStoneOfArawn.OhonatStep6"));
                        break;
                }
            else
                Ohonat.SayTo(player,
                    L(player, "Quest.Albion.LostStoneOfArawn.OhonatGreeting"));
        }
        // The player whispered to the NPC
        else if (e == GameLivingEvent.WhisperReceive)
        {
            var wArgs = (WhisperReceiveEventArgs) args;
            if (quest == null)
                switch (wArgs.Text)
                {
                }
            else
                switch (wArgs.Text)
                {
                    case "Gwyddneau":
                        if (quest.Step == 3)
                        {
                            quest.Step = 4;
                            Ohonat.SayTo(player,
                                L(player, "Quest.Albion.LostStoneOfArawn.OhonatStep4"));
                        }

                        break;
                    case "impossible":
						case "불가능":
                        if (quest.Step == 5)
                        {
                            Ohonat.SayTo(player,
                                L(player, "Quest.Albion.LostStoneOfArawn.OhonatImpossible", player.Name));
                            Ohonat.Emote(eEmote.Cheer);
                        }

                        break;
                    case "Farewell":
							case "작별":
                        if (quest.Step == 5 && player.Inventory.IsSlotsFree(1, eInventorySlot.FirstBackpack,
                                eInventorySlot.LastBackpack))
                        {
                            GiveItem(player, scroll_wearyall_loststone);
                            RemoveItem(player, lost_stone_of_arawn);
                            player.Out.SendSpellEffectAnimation(Ohonat, player, 4310, 0, false, 1);
                            new ECSGameTimer(player, timer => TeleportToWearyall(timer, player), 3000);
                            quest.Step = 6;
                            Ohonat.SayTo(player, L(player, "Quest.Albion.LostStoneOfArawn.OhonatStep6"));
                        }

                        break;
                }
        }
        else if (e == GameObjectEvent.ReceiveItem)
        {
            var rArgs = (ReceiveItemEventArgs) args;
            if (quest != null)
                if (rArgs.Item.Id_nb == lost_stone_of_arawn.Id_nb)
                {
                    Ohonat.SayTo(player,
                        L(player, "Quest.Albion.LostStoneOfArawn.OhonatImpossible", player.Name));
                    Ohonat.Emote(eEmote.Cheer);
                }
        }
    }

    private static int TeleportToWearyall(ECSGameTimer timer, GamePlayer player)
    {
        //teleport to wearyall village
        player.MoveTo(51, 435868, 493994, 3088, 3587);
        return 0;
    }

    public override bool CheckQuestQualification(GamePlayer player)
    {
        // if the player is already doing the quest his level is no longer of relevance
        if (player.IsDoingQuest(typeof(LostStoneofArawn)) != null)
            return true;

        if (player.Level < minimumLevel || player.Level > maximumLevel)
            return false;

        return true;
    }

    private static void CheckPlayerAbortQuest(GamePlayer player, byte response)
    {
        var quest = player.IsDoingQuest(typeof(LostStoneofArawn)) as LostStoneofArawn;

        if (quest == null)
            return;

        if (response == 0x00)
        {
            SendSystemMessage(player, L(player, "Quest.Albion.LostStoneOfArawn.AbortDeclined"));
        }
        else
        {
            SendSystemMessage(player, L(player, "Quest.Albion.LostStoneOfArawn.AbortingQuest", questTitle));
            quest.AbortQuest();
        }
    }

    private static void SubscribeQuest(DOLEvent e, object sender, EventArgs args)
    {
        var qargs = args as QuestEventArgs;
        if (qargs == null)
            return;

        if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(LostStoneofArawn)))
            return;

        if (e == GamePlayerEvent.AcceptQuest)
            CheckPlayerAcceptQuest(qargs.Player, 0x01);
        else if (e == GamePlayerEvent.DeclineQuest)
            CheckPlayerAcceptQuest(qargs.Player, 0x00);
    }

    private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
    {
        if (Honaytrt.CanGiveQuest(typeof(LostStoneofArawn), player) <= 0)
            return;

        if (player.IsDoingQuest(typeof(LostStoneofArawn)) != null)
            return;

        if (response == 0x00)
        {
            player.Out.SendMessage(L(player, "Quest.Albion.LostStoneOfArawn.DeclineQuest"), eChatType.CT_Say,
                eChatLoc.CL_PopupWindow);
        }
        else
        {
            //Check if we can add the quest!
            if (!Honaytrt.GiveQuest(typeof(LostStoneofArawn), player, 1))
                return;

            Honaytrt.SayTo(player, L(player, "Quest.Albion.LostStoneOfArawn.AcceptQuest"));
            Honaytrt.SayTo(player,
                L(player, "Quest.Albion.LostStoneOfArawn.HonaytrtStep1"));
        }
    }
    public override void AbortQuest()
    {
        base.AbortQuest(); //Defined in Quest, changes the state, stores in DB etc ...
        RemoveItem(m_questPlayer, lost_stone_of_arawn);
        RemoveItem(m_questPlayer, scroll_wearyall_loststone);
    }

    public override void FinishQuest()
    {
        if (m_questPlayer.Inventory.IsSlotsFree(1, eInventorySlot.FirstBackpack, eInventorySlot.LastBackpack))
        {
            if (m_questPlayer.Level >= 49)
                m_questPlayer.GainExperience(eXPSource.Quest,
                    (m_questPlayer.ExperienceForNextLevel - m_questPlayer.ExperienceForCurrentLevel) / 3, false);
            else
                m_questPlayer.GainExperience(eXPSource.Quest,
                    (m_questPlayer.ExperienceForNextLevel - m_questPlayer.ExperienceForCurrentLevel) / 2, false);
            RemoveItem(m_questPlayer, scroll_wearyall_loststone);
            GiveItem(m_questPlayer, ancient_copper_necklace);
            m_questPlayer.AddMoney(Money.GetMoney(0, 0, 121, 41, Util.Random(50)), L(m_questPlayer, "Quest.Albion.LostStoneOfArawn.MoneyReward"));

            base.FinishQuest(); //Defined in Quest, changes the state, stores in DB etc ...
        }
        else
        {
            m_questPlayer.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.NotEnoughInventorySpace"),
                eChatType.CT_Important, eChatLoc.CL_SystemWindow);
        }
    }
}
