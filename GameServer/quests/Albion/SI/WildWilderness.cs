using DOL.Database;
using DOL.Events;
using DOL.GS.PacketHandler;
using System;
using System.Reflection;
using DOL.GS.Trainer;

namespace DOL.GS.Quests.Hibernia
{
    public class WildWilderness : BaseQuest
    {
        private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);
        protected const int MIN_LEVEL = 1;
        protected const int MAX_LEVEL = 5;
        protected const string QUEST_TITLE = "Wild Wilderness";
        protected const string QUEST_GIVER_NAME = "Miach";
        protected const string QUEST_FINISH_NAME = "Resalg";
        private static GameNPC _miach = null;
        private static GameNPC _resalg = null;
        private static DbItemTemplate _lungerTail = null;

        public override string Name
        {
            get { return L(m_questPlayer, "Quest.Hibernia.WildWilderness.Name"); }
        }

        public override string Description
        {
            get
            {
                switch (Step)
                {
                    case 1:
                        return L(m_questPlayer, "Quest.Hibernia.WildWilderness.Description1");
                    case 2:
                        return L(m_questPlayer, "Quest.Hibernia.WildWilderness.Description2");
                    case 3:
                        return L(m_questPlayer, "Quest.Hibernia.WildWilderness.Description3");
                }
                return base.Description;
            }
        }
        public WildWilderness() : base() { }
        public WildWilderness(GamePlayer questingPlayer) : base(questingPlayer) { }
        public WildWilderness(GamePlayer questingPlayer, int step) : base(questingPlayer, step) { }
        public WildWilderness(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest) { }

        [ScriptLoadedEvent]
        public static void ScriptLoaded(DOLEvent e, object sender, EventArgs args)
        {
            if (!ServerProperties.Properties.LOAD_QUESTS)
                return;

            #region initialize NPC
            GameNPC[] npcs = WorldMgr.GetNPCsByName(QUEST_GIVER_NAME, eRealm.Hibernia);

            if (npcs.Length > 0)
                foreach (GameNPC npc in npcs)
                    if (npc.CurrentRegionID == 181 && npc.X == 424066 && npc.Y == 446316)
                    {
                        _miach = (ForesterTrainer)npc;
                        break;
                    }

            if (_miach == null)
            {
                if (log.IsWarnEnabled)
                    log.Warn("Could not find Miach, creating it ...");
                _miach = new ForesterTrainer();
                _miach.Model = 734;
                _miach.Name = "Miach";
                _miach.LoadEquipmentTemplateFromDatabase("586bb1ab-7832-48ba-b46c-3bcede4d6d8a");
                _miach.GuildName = "Forester Trainer";
                _miach.Realm = eRealm.Hibernia;
                _miach.CurrentRegionID = 181;
                _miach.Size = 50;
                _miach.Level = 59;
                _miach.X = 424066;
                _miach.Y = 446316;
                _miach.Z = 5952;
                _miach.Heading = 1228;
                _miach.AddToWorld();
                if (SAVE_INTO_DATABASE)
                    _miach.SaveIntoDatabase();

            }

            npcs = WorldMgr.GetNPCsByName("Resalg", eRealm.Hibernia);

            if (npcs.Length > 0)
                foreach (var npc in npcs)
                    if (npc.CurrentRegionID == 181 && npc.X == 424834 && npc.Y == 445558)
                    {
                        _resalg = npc;
                        break;
                    }

            if (_resalg == null)
            {
                if (log.IsWarnEnabled)
                    log.Warn("Could not find Resalg, creating it ...");
                _resalg = new GameNPC();
                _resalg.Model = 363;
                _resalg.Name = "Resalg";
                _resalg.GuildName = string.Empty;
                _resalg.Realm = eRealm.Hibernia;
                _resalg.CurrentRegionID = 181;
                _resalg.LoadEquipmentTemplateFromDatabase("Resalg");
                _resalg.Size = 51;
                _resalg.Level = 52;
                _resalg.X = 424834;
                _resalg.Y = 445558;
                _resalg.Z = 5977;
                _resalg.Heading = 125;
                _resalg.AddToWorld();
                if (SAVE_INTO_DATABASE)
                    _resalg.SaveIntoDatabase();
            }
            #endregion

            #region initialize Quest Item
            _lungerTail = GameServer.Database.FindObjectByKey<DbItemTemplate>("lunger_tail");
            if (_lungerTail == null)
            {
                _lungerTail = new DbItemTemplate();
                _lungerTail.Name = "Lunger Tail";
                if (log.IsWarnEnabled)
                {
                    log.Warn("Could not find " + _lungerTail.Name + ", creating it ...");
                }
                _lungerTail.Weight = 10;
                _lungerTail.Model = 515;
                _lungerTail.Id_nb = "lunger_tail";
                _lungerTail.IsPickable = true;
                _lungerTail.IsDropable = true;
                _lungerTail.IsTradable = false;
                _lungerTail.Quality = 100;
                _lungerTail.Condition = 1000;
                _lungerTail.MaxCondition = 1000;
                _lungerTail.Durability = 1000;
                _lungerTail.MaxDurability = 1000;
            }
            #endregion

            GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
            GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

            GameEventMgr.AddHandler(_miach, GameObjectEvent.Interact, new DOLEventHandler(TalkToMiach));
            GameEventMgr.AddHandler(_miach, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToMiach));

            GameEventMgr.AddHandler(_resalg, GameObjectEvent.Interact, new DOLEventHandler(TalkToResalg));
            GameEventMgr.AddHandler(_resalg, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToResalg));

            _miach.AddQuestToGive(typeof(WildWilderness));
            if (log.IsInfoEnabled)
            {
                log.Info($"Quest {QUEST_TITLE} initialized");
            }
        }

        [ScriptUnloadedEvent]
        public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
        {
            if (_miach == null) return;

            GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
            GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

            GameEventMgr.RemoveHandler(_miach, GameObjectEvent.Interact, new DOLEventHandler(TalkToMiach));
            GameEventMgr.RemoveHandler(_miach, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToMiach));

            GameEventMgr.RemoveHandler(_resalg, GameObjectEvent.Interact, new DOLEventHandler(TalkToResalg));
            GameEventMgr.RemoveHandler(_resalg, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToResalg));
            _miach.RemoveQuestToGive(typeof(WildWilderness));
        }

        protected static void SubscribeQuest(DOLEvent e, object sender, EventArgs args)
        {
            QuestEventArgs qargs = args as QuestEventArgs;
            if (qargs == null)
            {
                return;
            }
            if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(WildWilderness)))
            {
                return;
            }
            if (e == GamePlayerEvent.AcceptQuest)
            {
                CheckPlayerAcceptQuest(qargs.Player, 0x01);
            }
            else if (e == GamePlayerEvent.DeclineQuest)
            {
                CheckPlayerAcceptQuest(qargs.Player, 0x00);
            }
        }

        private static void TalkToMiach(DOLEvent e, object sender, EventArgs args)
        {
            GamePlayer player = ((SourceEventArgs)args).Source as GamePlayer;
            if (player == null)
                return;

            if (_miach.CanGiveQuest(typeof(WildWilderness), player) <= 0)
                return;

            WildWilderness quest = player.IsDoingQuest(typeof(WildWilderness)) as WildWilderness;
            _miach.TurnTo(player);
            if (e == GameObjectEvent.Interact)
            {
                if (quest != null)
                {
                    switch (quest.Step)
                    {
                        case 1:
                            _miach.SayTo(player, L(player, "Quest.Hibernia.WildWilderness.MiachTailRequest"));
                            break;
                        case 2:
                            _miach.SayTo(player, L(player, "Quest.Hibernia.WildWilderness.MiachFindLungers", player.CharacterClass.Name));
                            break;
                        case 3:
                            _miach.SayTo(player, L(player, "Quest.Hibernia.WildWilderness.MiachBringTail"));
                            break;
                    }
                }
                else
                {
                    _miach.SayTo(player, L(player, "Quest.Hibernia.WildWilderness.MiachIntro"));
                }
            }
            else if (e == GameLivingEvent.WhisperReceive)
            {
                WhisperReceiveEventArgs wArgs = (WhisperReceiveEventArgs)args;
                if (quest == null)
                {
                    switch (wArgs.Text)
                    {
	                        case "hunt":
	                        case "사냥":
                            _miach.SayTo(player, L(player, "Quest.Hibernia.WildWilderness.MiachHunt"));
                            player.Out.SendQuestSubscribeCommand(_miach, QuestMgr.GetIDForQuestType(typeof(WildWilderness)), L(player, "Quest.Hibernia.WildWilderness.Subscribe"));
                            break;
                    }
                }
                else
                {
                    switch (wArgs.Text)
                    {
                        case "abort":
                            player.Out.SendCustomDialog(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.AbortConfirm"), new CustomDialogResponse(CheckPlayerAbortQuest));
                            break;
	                        case "tail":
	                        case "꼬리":
                            if (quest.Step == 1)
                            {
                                _miach.SayTo(player, L(player, "Quest.Hibernia.WildWilderness.FindTail"));
                                quest.Step = 2;
                            }
                            break;
                    }
                }
            }
        }

          private static void TalkToResalg(DOLEvent e, object sender, EventArgs args)
        {
            GamePlayer player = ((SourceEventArgs)args).Source as GamePlayer;
            if (player == null)
                return;

            WildWilderness quest = player.IsDoingQuest(typeof(WildWilderness)) as WildWilderness;
            _resalg.TurnTo(player);
            if (e == GameObjectEvent.Interact)
            {
                if (quest != null)
                {
                    switch (quest.Step)
                    {
                        case 1:
                            _resalg.SayTo(player, L(player, "Quest.Hibernia.WildWilderness.ResalgGreeting"));
                            break;
                        case 2:
                            _resalg.SayTo(player, L(player, "Quest.Hibernia.WildWilderness.ResalgTailQuestion"));
                            break;
                        case 3:
                            _resalg.SayTo(player, L(player, "Quest.Hibernia.WildWilderness.ResalgClassGreeting", player.CharacterClass.Name));

                            _resalg.SayTo(player, L(player, "Quest.Hibernia.WildWilderness.ResalgFormulaIntro"));
                            break;
                    }
                }
                else
                {
                }
            }
            else if (e == GameLivingEvent.WhisperReceive)
            {
                WhisperReceiveEventArgs wArgs = (WhisperReceiveEventArgs)args;
                if (quest == null)
                {
                }
                else
                {
                    switch (wArgs.Text)
                    {
                        case "abort":
                            player.Out.SendCustomDialog(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.AbortConfirm"), new CustomDialogResponse(CheckPlayerAbortQuest));
                            break;
	                        case "formula":
	                        case "제조법":
                            _resalg.SayTo(player, L(player, "Quest.Hibernia.WildWilderness.ResalgFormula"));
                            RemoveItem(player, _lungerTail);
                            quest.FinishQuest();
                            break;
                    }
                }
            }
            else if (e == GameObjectEvent.ReceiveItem)
            {
                var rArgs = (ReceiveItemEventArgs) args;
                if (quest == null) return;
                if (rArgs.Item.Id_nb != _lungerTail.Id_nb) return;
                _resalg.SayTo(player, L(player, "Quest.Hibernia.WildWilderness.ResalgFormulaIntro"));
                RemoveItem(player, _lungerTail);
            }

        }

        public override void Notify(DOLEvent e, object sender, EventArgs args)
        {
            GamePlayer player = sender as GamePlayer;
            if (player?.IsDoingQuest(typeof(WildWilderness)) == null)
                return;

            if (sender != m_questPlayer)
                return;

            if (Step == 2 && e == GameLivingEvent.EnemyKilled)
            {
                EnemyKilledEventArgs gArgs = (EnemyKilledEventArgs)args;

                if (gArgs.Target.Name.ToLower() == "lunger")
                {
                    GiveItem(player, _lungerTail);
                    Step = 3;
                }
            }
        }

        private static void CheckPlayerAbortQuest(GamePlayer player, byte response)
        {
            WildWilderness quest = player.IsDoingQuest(typeof(WildWilderness)) as WildWilderness;
            if (quest == null)
            {
                return;
            }
            if (response == 0x00)
            {
                SendSystemMessage(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.ContinueQuestWork"));
            }
            else
            {
                SendSystemMessage(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.AbortingQuestRestart", QUEST_TITLE));
                quest.AbortQuest();
            }
        }

        private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
        {
            if (_miach.CanGiveQuest(typeof(WildWilderness), player) <= 0)
                return;

            if (player.IsDoingQuest(typeof(WildWilderness)) != null)
                return;

            if (response == 0x00)
            {
                SendReply(player, L(player, "Quest.Hibernia.WildWilderness.Decline"));
            }
            else
            {
                if (!_miach.GiveQuest(typeof(WildWilderness), player, 1))
                    return;

                SendReply(player, L(player, "Quest.Hibernia.WildWilderness.MiachTailRequest"));
            }
        }

        public override bool CheckQuestQualification(GamePlayer player)
        {
            if (player.IsDoingQuest(typeof(WildWilderness)) != null)
            {
                return true;
            }
            if (player.Level < MIN_LEVEL || player.Level > MAX_LEVEL)
            {
                return false;
            }
            if (player.CharacterClass.ID != (byte) eCharacterClass.Animist &&
                player.CharacterClass.ID != (byte) eCharacterClass.Forester)
                return false;

            return true;
        }

        public override void FinishQuest()
        {
            m_questPlayer.ForceGainExperience( 20);
            m_questPlayer.AddServerIssuedMoney(Money.GetMoney(0, 0, 0, 6, 0), L(m_questPlayer, "Quest.Hibernia.WildWilderness.MoneyReward"));

            base.FinishQuest();
        }

        private static string L(GamePlayer player, string key, params object[] args)
        {
            string language = player?.Client?.Account?.Language ?? "EN";
            return DOL.Language.LanguageMgr.GetTranslation(language, key, args);
        }
    }
}
