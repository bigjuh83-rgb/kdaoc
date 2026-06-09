using System;
using System.Reflection;
using DOL.AI.Brain;
using DOL.Database;
using DOL.Events;
using DOL.GS.PacketHandler;

namespace DOL.GS.Quests.Albion
{
    public class ImmediateResolutionVB : BaseQuest
    {
        private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);
        protected const string questTitle = "Immediate Resolution";
        protected const string stewardWillieNpcName = "Steward Willie";
        protected const string masterTorNpc = "Master Torr";
        protected const string waxSealedNoteInDb = "wax_sealed_note";
        protected const string waxSealedNoteName = "Wax Sealed Note";

        protected const int MIN_LEVEL = 1;
        protected const int MAX_LEVEL = 5;

        protected const int _cluster1BaseX = 519203;
        protected const int _cluster1BaseY = 451090;
        protected const int _cluster1BaseZ = 2370;

        protected const int _cluster2BaseX = 523755;
        protected const int _cluster2BaseY = 451229;
        protected const int _cluster2BaseZ = 2379;

        protected const int _xDelta = 75;
        protected const int _yDelta = 20;

        private static DbItemTemplate waxSealedNote = null;

        private static GameNPC _masterTor = null;
        private static GameNPC _stewardWillie = null;

        private static GameGuard _gaurdsman1 = null;
        private static GameGuard _gaurdsman2 = null;
        private static GameGuard _gaurdsman3 = null;
        private static GameGuard _gaurdsman4 = null;

        public ImmediateResolutionVB() : base() { }
        public ImmediateResolutionVB(GamePlayer questingPlayer) : this(questingPlayer, 1) { }
        public ImmediateResolutionVB(GamePlayer questingPlayer, int step) : base(questingPlayer, step) { }
        public ImmediateResolutionVB(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest) { }

        private static string L(GamePlayer player, string key, params object[] args)
        {
            return DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, key, args);
        }

        public override void Notify(DOLEvent e, object sender, EventArgs args)
        {
            GamePlayer player = sender as GamePlayer;

            if(player == null)
            {
                return;
            }
            if(player.IsDoingQuest(typeof(ImmediateResolutionVB)) == null)
            {
                return;
            }

            if(Step == 2 && e == GamePlayerEvent.GiveItem)
            {
                GiveItemEventArgs gArgs = (GiveItemEventArgs)args;
                if(gArgs.Target == _gaurdsman1 || gArgs.Target == _gaurdsman2 || gArgs.Target == _gaurdsman3 || gArgs.Target == _gaurdsman4)
                {
                    if(gArgs.Item.Id_nb == waxSealedNoteInDb)
                    {
                        GameNPC selectedGuard = gArgs.Target as GameNPC;
                        INpcTemplate template = NpcTemplateMgr.GetTemplate(12211);
                        RemoveItem(selectedGuard, player, waxSealedNote);
                        selectedGuard.SayTo(player, L(player, "Quest.Albion.ImmediateResolution.GuardAssist"));
                        selectedGuard.SayTo(player, L(player, "Quest.Albion.ImmediateResolution.GuardPrepare"));
                        FinishQuest();
                        if (gArgs.Target == _gaurdsman1 || gArgs.Target == _gaurdsman2)
                        {
                            for (int i = 0; i < 10; i++)
                            {
                                GameNPC mob = new GameNPC(template)
                                {
                                    X = _cluster1BaseX - (i * _xDelta),
                                    Y = _cluster1BaseY + (i * _yDelta),
                                    Z = _cluster1BaseZ,
                                    CurrentRegionID = 1,
                                    SaveInDB = false
                                };
                                mob.AddBrain(new StandardMobBrain());
                                mob.TargetObject = gArgs.Target;
                                mob.AddToWorld();
                                if (i <= 5)
                                {
                                    mob.WalkTo(_gaurdsman2, 180);
                                    (mob.Brain as StandardMobBrain).AddToAggroList(_gaurdsman2, 1000);
                                }
                                else
                                {
                                    mob.WalkTo(_gaurdsman1, 180);
                                    (mob.Brain as StandardMobBrain).AddToAggroList(_gaurdsman1, 1000);
                                }
                            }
                        }

                        if (gArgs.Target == _gaurdsman3 || gArgs.Target == _gaurdsman4)
                        {
                            for (int i = 0; i < 10; i++)
                            {
                                GameNPC mob = new GameNPC(template)
                                {
                                    X = _cluster2BaseX - (i * _xDelta),
                                    Y = _cluster2BaseY + (i * _yDelta),
                                    Z = _cluster2BaseZ,
                                    CurrentRegionID = 1,
                                    SaveInDB = false
                                };
                                mob.AddBrain(new StandardMobBrain());
                                mob.TargetObject = gArgs.Target;
                                mob.AddToWorld();
                                if (i <= 5)
                                {
                                    mob.WalkTo(_gaurdsman4, 180);
                                    (mob.Brain as StandardMobBrain).AddToAggroList(_gaurdsman4, 1000);
                                }
                                else
                                {
                                    mob.WalkTo(_gaurdsman3, 180);
                                    (mob.Brain as StandardMobBrain).AddToAggroList(_gaurdsman3, 1000);
                                }
                            }
                        }
                    }
                }
            }
            base.Notify(e, sender, args);
        }

        [ScriptLoadedEvent]
        public static void ScriptLoaded(DOLEvent e, object sender, EventArgs args)
        {
            if (!ServerProperties.Properties.LOAD_QUESTS)
                return;
            if (log.IsInfoEnabled)
                log.Info("Quest \"" + questTitle + "\" initializing ...");

            GameNPC[] gameNpcQuery = WorldMgr.GetNPCsByName(masterTorNpc, eRealm.Albion);
            if (gameNpcQuery.Length == 0)
            {
                _logReasonQuestCantBeImplemented(masterTorNpc);
                return;
            }
            else
            {
                _masterTor = gameNpcQuery[0];
            }
            gameNpcQuery = WorldMgr.GetNPCsByName(stewardWillieNpcName, eRealm.Albion);
            if (gameNpcQuery.Length == 0)
            {
                _logReasonQuestCantBeImplemented(stewardWillieNpcName);
                return;
            }
            else
            {
                _stewardWillie = gameNpcQuery[0];
            }
            _loadGuards();

            waxSealedNote = GameServer.Database.FindObjectByKey<DbItemTemplate>(waxSealedNoteInDb);
            if (waxSealedNote == null)
            {
                if (log.IsWarnEnabled)
                    log.Warn($"Could not find {waxSealedNoteName}, creating it ...");
                waxSealedNote = new DbItemTemplate();
                waxSealedNote.Object_Type = 0;
                waxSealedNote.Id_nb = waxSealedNoteInDb;
                waxSealedNote.Name = waxSealedNoteName;
                waxSealedNote.Level = 1;
                waxSealedNote.Model = 499;
                waxSealedNote.IsDropable = false;
                waxSealedNote.IsPickable = false;
                waxSealedNote.IsTradable = false;
                GameServer.Database.AddObject(waxSealedNote);
            }

            GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
            GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));
            GameEventMgr.AddHandler(_stewardWillie, GameLivingEvent.Interact, new DOLEventHandler(TalkToStewardWillie));
            GameEventMgr.AddHandler(_stewardWillie, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToStewardWillie));
            GameEventMgr.AddHandler(_masterTor, GameLivingEvent.Interact, new DOLEventHandler(TalkToMasterTor));
            GameEventMgr.AddHandler(_masterTor, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToMasterTor));

            _masterTor.AddQuestToGive(typeof(ImmediateResolutionVB));

            if (log.IsInfoEnabled)
                log.Info("Quest \"" + questTitle + "\" initialized");
        }

        [ScriptUnloadedEvent]
        public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
        {
            GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
            GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

            GameEventMgr.RemoveHandler(_stewardWillie, GameObjectEvent.Interact, new DOLEventHandler(TalkToStewardWillie));
            GameEventMgr.RemoveHandler(_stewardWillie, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToStewardWillie));

            GameEventMgr.RemoveHandler(_masterTor, GameLivingEvent.Interact, new DOLEventHandler(TalkToMasterTor));
            GameEventMgr.RemoveHandler(_masterTor, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToMasterTor));

            _masterTor.RemoveQuestToGive(typeof(ImmediateResolutionVB));
        }

        protected static void TalkToStewardWillie(DOLEvent e, object sender, EventArgs args)
        {
            GamePlayer player = ((SourceEventArgs)args).Source as GamePlayer;
            if (player == null)
                return;

            ImmediateResolutionVB quest = player.IsDoingQuest(typeof(ImmediateResolutionVB)) as ImmediateResolutionVB;

            _stewardWillie.TurnTo(player);
            if (e == GameObjectEvent.Interact)
            {
                if (quest != null)
                {
                    _stewardWillie.SayTo(player, L(player, "Quest.Albion.ImmediateResolution.StewardChosen"));
                    return;
                }
            }
            else if (e == GameLivingEvent.WhisperReceive)
            {
                WhisperReceiveEventArgs wArgs = (WhisperReceiveEventArgs)args;

                if (quest != null)
                {
                    switch (wArgs.Text)
                    {
                        case "a message":
						case "전갈":
                            _stewardWillie.SayTo(player, L(player, "Quest.Albion.ImmediateResolution.StewardMessage"));
                            break;
                        case "attacked":
							case "공격":
                            _stewardWillie.SayTo(player, L(player, "Quest.Albion.ImmediateResolution.StewardAttacked"));
                            if (quest.Step == 1)
                            {
                                quest.Step = 2;
                                GiveItem(_stewardWillie, player, waxSealedNote);
                            }
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
                    }
                }

            }
        }

        protected static void TalkToMasterTor(DOLEvent e, object sender, EventArgs args)
        {
            GamePlayer player = ((SourceEventArgs)args).Source as GamePlayer;
            if (player == null)
                return;

            if (_masterTor.CanGiveQuest(typeof(ImmediateResolutionVB), player) <= 0)
                return;

            ImmediateResolutionVB quest = player.IsDoingQuest(typeof(ImmediateResolutionVB)) as ImmediateResolutionVB;

            _masterTor.TurnTo(player);
            if (e == GameObjectEvent.Interact)
            {
                if (quest == null)
                {
                    _masterTor.SayTo(player, L(player, "Quest.Albion.ImmediateResolution.MasterWelcome"));
                    return;
                }
            }
            else if (e == GameLivingEvent.WhisperReceive)
            {
                WhisperReceiveEventArgs wArgs = (WhisperReceiveEventArgs)args;

                if (quest == null)
                {
                    switch (wArgs.Text)
                    {
                        case "adventurers":
							case "모험가들":
                            player.Out.SendQuestSubscribeCommand(_masterTor, QuestMgr.GetIDForQuestType(typeof(ImmediateResolutionVB)), L(player, "Quest.Albion.ImmediateResolution.SubscribePrompt"));
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
                    }
                }

            }
        }

        private static void CheckPlayerAbortQuest(GamePlayer player, byte response)
        {
            ImmediateResolutionVB quest = player.IsDoingQuest(typeof(ImmediateResolutionVB)) as ImmediateResolutionVB;

            if (quest == null)
                return;

            if (response == 0x00)
            {
                SendSystemMessage(player, L(player, "Quest.Albion.ImmediateResolution.AbortDeclined"));
            }
            else
            {
                SendSystemMessage(player, L(player, "Quest.Albion.ImmediateResolution.AbortingQuest", questTitle));
                quest.AbortQuest();
            }
        }

        protected static void SubscribeQuest(DOLEvent e, object sender, EventArgs args)
        {
            QuestEventArgs qargs = args as QuestEventArgs;
            if (qargs == null)
                return;

            if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(ImmediateResolutionVB)))
                return;

            if (e == GamePlayerEvent.AcceptQuest)
                CheckPlayerAcceptQuest(qargs.Player, 0x01);
            else if (e == GamePlayerEvent.DeclineQuest)
                CheckPlayerAcceptQuest(qargs.Player, 0x00);
        }

        private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
        {
            if (_masterTor.CanGiveQuest(typeof(ImmediateResolutionVB), player) <= 0)
                return;

            if (player.IsDoingQuest(typeof(ImmediateResolutionVB)) != null)
                return;

            if (response == 0x00)
            {
                SendReply(player, L(player, "Quest.Albion.ImmediateResolution.DeclineQuest"));
            }
            else
            {
                if (!_masterTor.GiveQuest(typeof(ImmediateResolutionVB), player, 1))
                    return;

                _masterTor.SayTo(player, L(player, "Quest.Albion.ImmediateResolution.AcceptQuest"));
            }
        }

        public override string Name
        {
            get { return DOL.Language.LanguageMgr.GetTranslatedQuestTitle(m_questPlayer?.Client?.Account?.Language, questTitle); }
        }

        public override string Description
        {
            get
            {
                switch (Step)
                {
                    case 1:
                        return L(m_questPlayer, "Quest.Albion.ImmediateResolution.Description1");
                    case 2:
                        return L(m_questPlayer, "Quest.Albion.ImmediateResolution.Description2");
                }
                return base.Description;
            }
        }

        public override bool CheckQuestQualification(GamePlayer player)
        {
            if (player.IsDoingQuest(typeof(ImmediateResolutionVB)) != null)
                return true;

            if (player.Level < MIN_LEVEL || player.Level > MAX_LEVEL)
                return false;

            return true;
        }

        public override void FinishQuest()
        {
            base.FinishQuest();
            m_questPlayer.ForceGainExperience( 50);
            long money = Money.GetMoney(0, 0, 0, 0, 30 + Util.Random(50));
            m_questPlayer.AddServerIssuedMoney(money, L(m_questPlayer, "Quest.Albion.ImmediateResolution.MoneyReward"));
            InventoryLogging.LogInventoryAction("(QUEST;" + Name + ")", m_questPlayer, eInventoryActionType.Quest, money);

        }

        public static void _logReasonQuestCantBeImplemented(string entity)
        {
            if (log.IsWarnEnabled)
            {
                log.Warn($"Could not find {entity}, cannot load quest: {questTitle}");
            }
        }

        private static void _loadGuards()
        {
            NpcTemplateMgr.Reload();
            INpcTemplate template = NpcTemplateMgr.GetTemplate(12964);
            _gaurdsman1 = new GameGuard(template)
            {
                X = 519273,
                Y = 452388,
                Z = 2329,
                Heading = 1883,
                CurrentRegionID = 1,
                SaveInDB = false,
                Realm = eRealm.Albion
            };
            _gaurdsman1.Flags ^= GameNPC.eFlags.GHOST;
            _gaurdsman1.AddToWorld();
            _gaurdsman2 = new GameGuard(template)
            {
                X = 519829,
                Y = 452156,
                Z = 2368,
                Heading = 1860,
                CurrentRegionID = 1,
                SaveInDB = false,
                Realm = eRealm.Albion
            };
            _gaurdsman2.Flags ^= GameNPC.eFlags.GHOST;
            _gaurdsman2.AddToWorld();
            _gaurdsman3 = new GameGuard(template)
            {
                X = 523091,
                Y = 452281,
                Z = 2330,
                Heading = 1995,
                CurrentRegionID = 1,
                SaveInDB = false,
                Realm = eRealm.Albion
            };
            _gaurdsman3.Flags ^= GameNPC.eFlags.GHOST;
            _gaurdsman3.AddToWorld();
            _gaurdsman4 = new GameGuard(template)
            {
                X = 522534,
                Y = 452024,
                Z = 2354,
                Heading = 2371,
                CurrentRegionID = 1,
                SaveInDB = false,
                Realm = eRealm.Albion
            };
            _gaurdsman4.Flags ^= GameNPC.eFlags.GHOST;
            _gaurdsman4.AddToWorld();
        }
    }
}
