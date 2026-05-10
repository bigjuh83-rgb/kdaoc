using System;
using System.Reflection;
using DOL.Database;
using DOL.Events;
using DOL.GS.PacketHandler;

namespace DOL.GS.Quests.Albion
{
    public class WolfPeltCloak : BaseQuest
    {
        private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

        protected const string questTitle = "Wolf Pelt Cloak";
        protected const string stewardWillieNpcName = "Steward Willie";
        protected const string streamstressLynnetNpcName = "Seamstress Lynnet";
        protected const string brothDonNpcName = "Brother Don";
        protected const string wolfPeltCloak = "wolf_pelt_cloak";
        protected const string wolfFur = "wolf_fur";
        protected const string wolfHeadToken = "wolf_head_token";

        protected const int MIN_LEVEL = 1;
        protected const int MAX_LEVEL = 11;

        private static GameNPC _stewardWillie = null;
        private static GameNPC _lynett = null;
        private static GameNPC _don = null;

        private static DbItemTemplate _wolfPeltCloak = null;
        private static DbItemTemplate _wolfFur = null;
        private static DbItemTemplate _wolfHeadToken = null;

        public WolfPeltCloak() : base() { }
        public WolfPeltCloak(GamePlayer questingPlayer) : this(questingPlayer, 1) { }
        public WolfPeltCloak(GamePlayer questingPlayer, int step) : base(questingPlayer, step) { }
        public WolfPeltCloak(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest) { }

        private static string L(GamePlayer player, string key, params object[] args)
        {
            return DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, key, args);
        }

        [ScriptLoadedEvent]
        public static void ScriptLoaded(DOLEvent e, object sender, EventArgs args)
        {
            if (!ServerProperties.Properties.LOAD_QUESTS)
                return;
            if (log.IsInfoEnabled)
                log.Info("Quest \"" + questTitle + "\" initializing ...");

            GameNPC[] gameNpcQuery = WorldMgr.GetNPCsByName(stewardWillieNpcName, eRealm.Albion);
            if (gameNpcQuery.Length == 0)
            {
                _logReasonQuestCantBeImplemented(stewardWillieNpcName);
                return;
            }
            else
            {
                _stewardWillie = gameNpcQuery[0];
            }
            gameNpcQuery = WorldMgr.GetNPCsByName(streamstressLynnetNpcName, eRealm.Albion);
            if (gameNpcQuery.Length == 0)
            {
                _logReasonQuestCantBeImplemented(streamstressLynnetNpcName);
                return;
            }
            else
            {
                _lynett = gameNpcQuery[0];
            }
            gameNpcQuery = WorldMgr.GetNPCsByName(brothDonNpcName, eRealm.Albion);
            if (gameNpcQuery.Length == 0)
            {
                _logReasonQuestCantBeImplemented(brothDonNpcName);
                return;
            }
            else
            {
                _don = gameNpcQuery[0];
            }

            _wolfPeltCloak = GameServer.Database.FindObjectByKey<DbItemTemplate>(wolfPeltCloak);
            if (_wolfPeltCloak == null)
            {
                _logReasonQuestCantBeImplemented(wolfPeltCloak);
                return;
            }
            _wolfFur = GameServer.Database.FindObjectByKey<DbItemTemplate>(wolfFur);
            if (_wolfFur == null)
            {
                _logReasonQuestCantBeImplemented(wolfFur);
                return;
            }

            _wolfHeadToken = GameServer.Database.FindObjectByKey<DbItemTemplate>(wolfHeadToken);
            if (_wolfHeadToken == null)
            {
                _logReasonQuestCantBeImplemented(wolfHeadToken);
                return;
            }
            GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
            GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));
            GameEventMgr.AddHandler(_stewardWillie, GameLivingEvent.Interact, new DOLEventHandler(TalkToStewardWillie));
            GameEventMgr.AddHandler(_stewardWillie, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToStewardWillie));
            GameEventMgr.AddHandler(_don, GameLivingEvent.Interact, new DOLEventHandler(TalkToBrotherDon));
            GameEventMgr.AddHandler(_don, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToBrotherDon));
            GameEventMgr.AddHandler(_lynett, GameLivingEvent.Interact, new DOLEventHandler(TalkToSeamstressLynnet));

            _stewardWillie.AddQuestToGive(typeof(WolfPeltCloak));

            if (log.IsInfoEnabled)
                log.Info("Quest \"" + questTitle + "\" initialized");
        }

        [ScriptUnloadedEvent]
        public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
        {
            if (_stewardWillie == null)
                return;

            GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
            GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));
            GameEventMgr.RemoveHandler(_stewardWillie, GameObjectEvent.Interact, new DOLEventHandler(TalkToStewardWillie));
            GameEventMgr.RemoveHandler(_stewardWillie, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToStewardWillie));
            GameEventMgr.RemoveHandler(_don, GameLivingEvent.Interact, new DOLEventHandler(TalkToBrotherDon));
            GameEventMgr.RemoveHandler(_don, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToBrotherDon));
            GameEventMgr.RemoveHandler(_lynett, GameObjectEvent.Interact, new DOLEventHandler(TalkToSeamstressLynnet));
            _stewardWillie.RemoveQuestToGive(typeof(WolfPeltCloak));
        }

        protected static void TalkToStewardWillie(DOLEvent e, object sender, EventArgs args)
        {
            GamePlayer player = ((SourceEventArgs)args).Source as GamePlayer;
            if (player == null)
                return;

            if (_stewardWillie.CanGiveQuest(typeof(WolfPeltCloak), player) <= 0)
                return;

            WolfPeltCloak quest = player.IsDoingQuest(typeof(WolfPeltCloak)) as WolfPeltCloak;

            _stewardWillie.TurnTo(player);
            if (e == GameObjectEvent.Interact)
            {
                if (quest != null)
                {
                    if (player.Inventory.GetFirstItemByID(_wolfFur.Id_nb, eInventorySlot.FirstBackpack, eInventorySlot.LastBackpack) != null)
                        _stewardWillie.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.StewardHasFur"));
                    else if (player.Inventory.GetFirstItemByID(_wolfHeadToken.Id_nb, eInventorySlot.FirstBackpack, eInventorySlot.LastBackpack) != null)
                        _stewardWillie.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.StewardHasToken"));
                    else
                        _stewardWillie.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.StewardInProgress"));
                    return;
                }
                else
                {
                    _stewardWillie.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.StewardGreeting"));
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
                        case "problem":
						case "문제":
                            _stewardWillie.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.Problem"));
                            break;
                        case "pack of wolves":
							case "늑대 무리":
                            _stewardWillie.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.PackOfWolves"));
                            break;
                        case "like to help":
							case "도울 의향이 있는지":
                            _stewardWillie.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.LikeToHelp"));
                            break;
                        case "serve him well":
							case "그분을 잘 섬긴":
                            player.Out.SendQuestSubscribeCommand(_stewardWillie, QuestMgr.GetIDForQuestType(typeof(WolfPeltCloak)), L(player, "Quest.Albion.WolfPeltCloak.SubscribePrompt"));
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

        protected static void SubscribeQuest(DOLEvent e, object sender, EventArgs args)
        {
            QuestEventArgs qargs = args as QuestEventArgs;
            if (qargs == null)
                return;

            if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(WolfPeltCloak)))
                return;

            if (e == GamePlayerEvent.AcceptQuest)
                CheckPlayerAcceptQuest(qargs.Player, 0x01);
            else if (e == GamePlayerEvent.DeclineQuest)
                CheckPlayerAcceptQuest(qargs.Player, 0x00);
        }

        protected static void TalkToSeamstressLynnet(DOLEvent e, object sender, EventArgs args)
        {
            GamePlayer player = ((SourceEventArgs)args).Source as GamePlayer;
            if (player == null)
                return;

            if (_stewardWillie.CanGiveQuest(typeof(WolfPeltCloak), player) <= 0)
                return;

            WolfPeltCloak quest = player.IsDoingQuest(typeof(WolfPeltCloak)) as WolfPeltCloak;

            _lynett.TurnTo(player);
            if (e == GameObjectEvent.Interact)
            {
                if (quest != null)
                {
                    _lynett.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.LynnetToken"));
                }
            }
        }

        protected static void TalkToBrotherDon(DOLEvent e, object sender, EventArgs args)
        {
            GamePlayer player = ((SourceEventArgs)args).Source as GamePlayer;
            if (player == null)
                return;

            if (e == GameObjectEvent.Interact)
            {
                if (player.Inventory.GetFirstItemByID(_wolfPeltCloak.Id_nb, eInventorySlot.FirstBackpack, eInventorySlot.LastBackpack) != null)
                    _don.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.BrotherDonGreeting"));
                return;
            }
            else if (e == GameLivingEvent.WhisperReceive)
            {
                WhisperReceiveEventArgs wArgs = (WhisperReceiveEventArgs)args;
                switch (wArgs.Text)
                {
                    case "orphanage":
							case "고아원":
                        _don.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.Orphanage"));
                        break;
                    case "donation":
							case "기부":
                        _don.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.Donation"));
                        break;
                }
            }
        }

        public override bool CheckQuestQualification(GamePlayer player)
        {
            if (player.IsDoingQuest(typeof(WolfPeltCloak)) != null)
                return true;

            if (player.Level < MIN_LEVEL || player.Level > MAX_LEVEL)
                return false;

            return true;
        }
        private static void CheckPlayerAbortQuest(GamePlayer player, byte response)
        {
            WolfPeltCloak quest = player.IsDoingQuest(typeof(WolfPeltCloak)) as WolfPeltCloak;

            if (quest == null)
                return;

            if (response == 0x00)
            {
                SendSystemMessage(player, L(player, "Quest.Albion.WolfPeltCloak.AbortDeclined"));
            }
            else
            {
                SendSystemMessage(player, L(player, "Quest.Albion.WolfPeltCloak.AbortingQuest", questTitle));
                quest.AbortQuest();
            }
        }

        private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
        {
            if (_stewardWillie.CanGiveQuest(typeof(WolfPeltCloak), player) <= 0)
                return;

            if (player.IsDoingQuest(typeof(WolfPeltCloak)) != null)
                return;

            if (response == 0x00)
            {
                SendReply(player, L(player, "Quest.Albion.WolfPeltCloak.DeclineQuest"));
            }
            else
            {
                if (!_stewardWillie.GiveQuest(typeof(WolfPeltCloak), player, 1))
                    return;

                _stewardWillie.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.StewardInProgress"));
            }
        }

        public override string Name
        {
            get { return questTitle; }
        }

        public override string Description
        {
            get
            {
                switch (Step)
                {
                    case 1:
                        return L(m_questPlayer, "Quest.Albion.WolfPeltCloak.Description1");
                    case 2:
                        return L(m_questPlayer, "Quest.Albion.WolfPeltCloak.Description2");
                    case 3:
                        return L(m_questPlayer, "Quest.Albion.WolfPeltCloak.Description3");
                }
                return base.Description;
            }
        }

        public override void Notify(DOLEvent e, object sender, EventArgs args)
        {
            GamePlayer player = sender as GamePlayer;

            if (player == null)
                return;

            // brother don
            if (e == GamePlayerEvent.GiveItem)
            {
                GiveItemEventArgs gArgs = (GiveItemEventArgs)args;
                if (gArgs.Target.Name == _don.Name && gArgs.Item.Id_nb == _wolfPeltCloak.Id_nb)
                {
                    _don.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.BrotherDonThanks"));
                    RemoveItem(_don, m_questPlayer, _wolfPeltCloak);
                    _don.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.BrotherDonComplete"));

                    player.ForceGainExperience(200);

                    return;
                }
            }

            if (player.IsDoingQuest(typeof(WolfPeltCloak)) == null)
                return;

            if (Step == 1 && e == GameLivingEvent.EnemyKilled)
            {
                EnemyKilledEventArgs gArgs = (EnemyKilledEventArgs)args;
                if (gArgs.Target.Name.IndexOf("wolf") >= 0)
                {
                    SendSystemMessage(L(player, "Quest.Albion.WolfPeltCloak.WolfKilled", gArgs.Target.Name));
                    _wolfFur.Name = gArgs.Target.GetName(1, true) + " fur";
                    GiveItem(player, _wolfFur);
                    Step = 2;
                    return;
                }
            }
            else if (Step == 2 && e == GamePlayerEvent.GiveItem)
            {
                GiveItemEventArgs gArgs = (GiveItemEventArgs)args;
                if (gArgs.Target.Name == _stewardWillie.Name && gArgs.Item.Id_nb == _wolfFur.Id_nb)
                {
                    _stewardWillie.TurnTo(m_questPlayer);
                    _stewardWillie.SayTo(m_questPlayer, L(m_questPlayer, "Quest.Albion.WolfPeltCloak.StewardTakeToken"));

                    RemoveItem(_stewardWillie, player, _wolfFur);
                    GiveItem(_stewardWillie, player, _wolfHeadToken);
                    Step = 3;
                    return;
                }
            }
            else if (Step == 3 && e == GamePlayerEvent.GiveItem)
            {
                GiveItemEventArgs gArgs = (GiveItemEventArgs)args;
                if (gArgs.Target.Name == _lynett.Name && gArgs.Item.Id_nb == _wolfHeadToken.Id_nb)
                {
                    RemoveItem(_lynett, player, _wolfHeadToken);
                    _lynett.SayTo(player, L(player, "Quest.Albion.WolfPeltCloak.LynnetReward"));
                    FinishQuest();
                    return;
                }
            }
        }

        public override void AbortQuest()
        {
            base.AbortQuest();
            RemoveItem(m_questPlayer, _wolfFur, false);
            RemoveItem(m_questPlayer, _wolfHeadToken, false);
        }

        public override void FinishQuest()
        {
            base.FinishQuest();
            GiveItem(_lynett, m_questPlayer, _wolfPeltCloak);

            m_questPlayer.GainExperience(eXPSource.Quest, 50, true);
            long money = Money.GetMoney(0, 0, 0, 0, 50);
            m_questPlayer.AddMoney(money, L(m_questPlayer, "Quest.Albion.WolfPeltCloak.MoneyReward"));
            InventoryLogging.LogInventoryAction("(QUEST;" + Name + ")", m_questPlayer, eInventoryActionType.Quest, money);

        }

        public static void _logReasonQuestCantBeImplemented(string entity)
        {
            if (log.IsWarnEnabled)
            {
                log.Warn($"Could not find {entity}, cannot load quest: Wolf Pelt Quest");
            }
        }

    }
}
