/*
*Author         : Kelt
*Editor			: Kelt
*Source         : Custom
*Date           : 03 July 2022
*Quest Name     : [Memorial] Power of Nature
*Quest Classes  : all
*Quest Version  : v1.0
*
*Changes:
*
*/

using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using DOL.AI.Brain;
using DOL.Database;
using DOL.Events;
using DOL.GS;
using DOL.GS.PacketHandler;
using DOL.GS.PlayerTitles;

namespace DOL.GS.Quests.Hibernia
{
    public class PowerOfNature : BaseQuest
    {
        /// <summary>
        /// Defines a logger for this class.
        /// </summary>
        private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

        protected const string questTitle = "[Memorial] Power of Nature";
        protected const int minimumLevel = 1;
        protected const int maximumLevel = 50;

        private static GameNPC Theresa = null; // Start + Finish NPC
        private static GameNPC Karl = null; // Speak with Karl
        private static GameNPC MobEffect = null; // Speak with Karl

        private static DbItemTemplate theresas_doll = null;
        private static DbItemTemplate magical_theresas_doll = null;
        // Constructors
        public PowerOfNature() : base()
        {
        }

        public PowerOfNature(GamePlayer questingPlayer) : base(questingPlayer)
        {
        }

        public PowerOfNature(GamePlayer questingPlayer, int step) : base(questingPlayer, step)
        {
        }

        public PowerOfNature(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest)
        {
        }


        [ScriptLoadedEvent]
        public static void ScriptLoaded(DOLEvent e, object sender, EventArgs args)
        {
            if (!ServerProperties.Properties.LOAD_QUESTS)
                return;


            #region defineNPCs

            GameNPC[] npcs = WorldMgr.GetNPCsByName("Theresa", eRealm.Hibernia);

            if (npcs.Length > 0)
                foreach (GameNPC npc in npcs)
                    if (npc.CurrentRegionID == 201 && npc.X == 31401 && npc.Y == 30076)
                    {
                        Theresa = npc;
                        break;
                    }

            if (Theresa == null)
            {
                if (log.IsWarnEnabled)
                    log.Warn("Could not find Theresa, creating it ...");
                Theresa = new GameNPC();
                Theresa.Model = 310;
                Theresa.Name = "Theresa";
                Theresa.GuildName = string.Empty;
                Theresa.Realm = eRealm.Hibernia;
                Theresa.CurrentRegionID = 201;
                Theresa.LoadEquipmentTemplateFromDatabase("Theresa");
                Theresa.Size = 48;
                Theresa.Level = 50;
                Theresa.X = 31401;
                Theresa.Y = 30076;
                Theresa.Z = 8011;
                Theresa.Heading = 1505;
                Theresa.AddToWorld();
                if (SAVE_INTO_DATABASE)
                    Theresa.SaveIntoDatabase();
            }

            npcs = WorldMgr.GetNPCsByName("Karl", eRealm.Hibernia);

            if (npcs.Length > 0)
                foreach (GameNPC npc in npcs)
                    if (npc.CurrentRegionID == 200 && npc.X == 328521 && npc.Y == 518534)
                    {
                        Karl = npc;
                        break;
                    }

            if (Karl == null)
            {
                if (log.IsWarnEnabled)
                    log.Warn("Could not find Karl, creating it ...");
                Karl = new GameNPC();
                Karl.Model = 956;
                Karl.Name = "Karl";
                Karl.GuildName = string.Empty;
                Karl.Realm = eRealm.Hibernia;
                Karl.CurrentRegionID = 200;
                Karl.LoadEquipmentTemplateFromDatabase("Karl");
                Karl.Size = 50;
                Karl.Level = 50;
                Karl.X = 328521;
                Karl.Y = 518534;
                Karl.Z = 4285;
                Karl.Heading = 2612;
                Karl.AddToWorld();
                if (SAVE_INTO_DATABASE)
                    Karl.SaveIntoDatabase();
            }

            // end npc

            #endregion

            #region defineItems

            theresas_doll = GameServer.Database.FindObjectByKey<DbItemTemplate>("theresas_doll");
            if (theresas_doll == null)
            {
                if (log.IsWarnEnabled)
                    log.Warn("Could not find Theresa's doll, creating it ...");
                theresas_doll = new DbItemTemplate();
                theresas_doll.Id_nb = "theresas_doll";
                theresas_doll.Name = "Theresa's doll";
                theresas_doll.Level = 5;
                theresas_doll.Item_Type = 0;
                theresas_doll.Model = 1879;
                theresas_doll.IsDropable = false;
                theresas_doll.IsTradable = false;
                theresas_doll.IsIndestructible = false;
                theresas_doll.IsPickable = false;
                theresas_doll.DPS_AF = 0;
                theresas_doll.SPD_ABS = 0;
                theresas_doll.Object_Type = 0;
                theresas_doll.Hand = 0;
                theresas_doll.Type_Damage = 0;
                theresas_doll.Quality = 100;
                theresas_doll.Weight = 1;
                theresas_doll.Description = "This doll was a present of Karl the Hero of Hibernia.";
                if (SAVE_INTO_DATABASE)
                    GameServer.Database.AddObject(theresas_doll);
            }

            magical_theresas_doll = GameServer.Database.FindObjectByKey<DbItemTemplate>("magical_theresas_doll");
            if (magical_theresas_doll == null)
            {
                if (log.IsWarnEnabled)
                    log.Warn("Could not find Magical Theresa's doll, creating it ...");
                magical_theresas_doll = new DbItemTemplate();
                magical_theresas_doll.Id_nb = "magical_theresas_doll";
                magical_theresas_doll.Name = "Theresa's magical doll";
                magical_theresas_doll.Level = 50;
                magical_theresas_doll.Item_Type = 0;
                magical_theresas_doll.Model = 1879;
                magical_theresas_doll.IsDropable = false;
                magical_theresas_doll.IsTradable = false;
                magical_theresas_doll.IsIndestructible = false;
                magical_theresas_doll.IsPickable = false;
                magical_theresas_doll.DPS_AF = 0;
                magical_theresas_doll.SPD_ABS = 0;
                magical_theresas_doll.Object_Type = 0;
                magical_theresas_doll.Hand = 0;
                magical_theresas_doll.Type_Damage = 0;
                magical_theresas_doll.Quality = 100;
                magical_theresas_doll.Weight = 1;
                magical_theresas_doll.Description = "This magical doll from Karl is a sign of love and is a present for Theresa.";
                if (SAVE_INTO_DATABASE)
                    GameServer.Database.AddObject(theresas_doll);
            }
            #endregion

            GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
            GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

            GameEventMgr.AddHandler(Theresa, GameObjectEvent.Interact, new DOLEventHandler(TalkToTheresa));
            GameEventMgr.AddHandler(Theresa, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToTheresa));

            GameEventMgr.AddHandler(Karl, GameObjectEvent.Interact, new DOLEventHandler(TalkToKarl));
            GameEventMgr.AddHandler(Karl, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToKarl));

            Theresa.AddQuestToGive(typeof(PowerOfNature));

            if (log.IsInfoEnabled)
                log.Info("Quest \"" + questTitle + "\" initialized");
        }

        [ScriptUnloadedEvent]
        public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
        {
            //if not loaded, don't worry
            if (Theresa == null)
                return;

            // remove handlers
            GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
            GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

            GameEventMgr.RemoveHandler(Theresa, GameObjectEvent.Interact, new DOLEventHandler(TalkToTheresa));
            GameEventMgr.RemoveHandler(Theresa, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToTheresa));

            GameEventMgr.RemoveHandler(Karl, GameObjectEvent.Interact, new DOLEventHandler(TalkToKarl));
            GameEventMgr.RemoveHandler(Karl, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToKarl));

            Theresa.RemoveQuestToGive(typeof(PowerOfNature));
        }

        protected static void TalkToTheresa(DOLEvent e, object sender, EventArgs args)
        {
            //We get the player from the event arguments and check if he qualifies
            GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
            if (player == null)
                return;

            if (Theresa.CanGiveQuest(typeof(PowerOfNature), player) <= 0)
                return;

            //We also check if the player is already doing the quest
            PowerOfNature quest = player.IsDoingQuest(typeof(PowerOfNature)) as PowerOfNature;

            if (e == GameObjectEvent.Interact)
            {
                if (quest != null)
                {
                    switch (quest.Step)
                    {
                        case 1:
                            Theresa.SayTo(player,
                                L(player, "Quest.Atlas.PowerOfNature.TheresaStep1", player.Name));
                            break;
                        case 2:
                            Theresa.SayTo(player,
                                L(player, "Quest.Atlas.PowerOfNature.TheresaStep2", player.Name));
                            break;
                        case 3:
                            Theresa.SayTo(player, L(player, "Quest.Atlas.PowerOfNature.TheresaStep3", player.Name));
                            break;
                        case 4:
                            Theresa.SayTo(player,
                                L(player, "Quest.Atlas.PowerOfNature.TheresaStep4"));
                            break;
                    }
                }
                else
                {
                    Theresa.SayTo(player,
                        L(player, "Quest.Atlas.PowerOfNature.TheresaIntro", player.CharacterClass.Name));
                }
            }
            // The player whispered to the NPC
            else if (e == GameLivingEvent.WhisperReceive)
            {
                WhisperReceiveEventArgs wArgs = (WhisperReceiveEventArgs) args;
                if (quest == null)
                {
                    switch (wArgs.Text)
                    {
	                        case "help me":
	                        case "도와":
                            player.Out.SendQuestSubscribeCommand(Theresa,
                                QuestMgr.GetIDForQuestType(typeof(PowerOfNature)),
                                L(player, "Quest.Atlas.PowerOfNature.Subscribe"));
                            break;
                    }
                }
                else
                {
                    switch (wArgs.Text)
                    {
	                        case "information":
	                        case "정보":
                            Theresa.SayTo(player,
                                L(player, "Quest.Atlas.PowerOfNature.Information"));
                            break;
	                        case "needed him":
	                        case "필요했습니다":
                            Theresa.SayTo(player,
                                L(player, "Quest.Atlas.PowerOfNature.NeededHim"));
                            break;
	                        case "toy":
	                        case "장난감":
                            Theresa.SayTo(player,
                                L(player, "Quest.Atlas.PowerOfNature.Toy"));
                            if (quest.Step == 1 && player.Inventory.IsSlotsFree(1, eInventorySlot.FirstBackpack,
                                    eInventorySlot.LastBackpack))
                            {
                                GiveItem(player, theresas_doll);
                                quest.Step = 2;
                            }
                            else
                            {
                                Theresa.SayTo(player,
                                    L(player, "Quest.Atlas.PowerOfNature.InventoryFull"));
                            }

                            break;
	                        case "say":
	                        case "말":
                            if (quest.Step == 3)
                            {
                                Theresa.SayTo(player,
                                    L(player, "Quest.Atlas.PowerOfNature.Say"));
                            }
                            break;
	                        case "Power of Nature":
	                        case "자연의 힘":
                            if (quest.Step == 4)
                            {
                                Theresa.SayTo(player,
                                    L(player, "Quest.Atlas.PowerOfNature.PowerMeaning"));
                            }
                            break;
		                        case "natural powers":
		                        case "자연의 힘의 근원":
                            if (quest.Step == 4)
                            {
                                RemoveItem(player, magical_theresas_doll);
                                Theresa.SayTo(player,
                                    L(player, "Quest.Atlas.PowerOfNature.NaturalPowers"));
                                Theresa.Emote(eEmote.Cheer);
                                new ECSGameTimer(Theresa, new ECSGameTimer.ECSTimerCallback(StartTheresaEffect), 2000);
                                Theresa.SayTo(player,
                                    L(player, "Quest.Atlas.PowerOfNature.FeelPower"));
                                quest.FinishQuest();
                            }
                            break;
                        case "abort":
                            player.Out.SendCustomDialog(
                                DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.AbortConfirm"),
                                new CustomDialogResponse(CheckPlayerAbortQuest));
                            break;
                    }
                }
            }
        }

        protected static void TalkToKarl(DOLEvent e, object sender, EventArgs args)
        {
            //We get the player from the event arguments and check if he qualifies
            GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
            if (player == null)
                return;

            //We also check if the player is already doing the quest
            PowerOfNature quest = player.IsDoingQuest(typeof(PowerOfNature)) as PowerOfNature;

            if (e == GameObjectEvent.Interact)
            {
                if (quest != null)
                {
                    switch (quest.Step)
                    {
                        case 1:
                            Karl.SayTo(player, L(player, "Quest.Atlas.PowerOfNature.KarlGreeting"));
                            break;
                        case 2:
                            Karl.SayTo(player,
                                L(player, "Quest.Atlas.PowerOfNature.KarlStep2", player.CharacterClass.Name));
                            break;
                        case 3:
                            Karl.SayTo(player,
                                L(player, "Quest.Atlas.PowerOfNature.KarlStep3", player.Name));
                            break;
                        case 4:
                            Karl.SayTo(player,
                                L(player, "Quest.Atlas.PowerOfNature.KarlStep4", player.Name));
                            break;
                    }
                }
                else
                {
                }
            }
            // The player whispered to the NPC
            else if (e == GameLivingEvent.WhisperReceive)
            {
                WhisperReceiveEventArgs wArgs = (WhisperReceiveEventArgs) args;
                if (quest == null)
                {
                    switch (wArgs.Text)
                    {
                    }
                }
                else
                {
                    switch (wArgs.Text)
                    {
	                        case "this place":
	                        case "이곳":
                            Karl.SayTo(player,
                                L(player, "Quest.Atlas.PowerOfNature.ThisPlace"));
                            break;
	                        case "my daughter":
	                        case "제 딸":
                            Karl.SayTo(player,
                                L(player, "Quest.Atlas.PowerOfNature.MyDaughter"));
                            break;
	                        case "doll":
	                        case "인형":
                            Karl.SayTo(player,
                                L(player, "Quest.Atlas.PowerOfNature.Doll"));
                            break;
	                        case "strength and aura":
	                        case "힘과 기운":
                            if (quest.Step == 2)
                            {
                                RemoveItem(player, theresas_doll);
                                Karl.SayTo(player,
                                    L(player, "Quest.Atlas.PowerOfNature.StrengthAura", player.Name));
                                quest.Step = 3;
                            }

                            break;
	                        case "begin":
	                        case "시작":
                            if (quest.Step == 3)
                            {
                                new ECSGameTimer(Karl, new ECSGameTimer.ECSTimerCallback(CreateEffect), 3000);

                                new ECSGameTimer(Karl, new ECSGameTimer.ECSTimerCallback(timer => StartEffectPlayer(timer, player)), 1000);
                                quest.Step = 4;
                                GiveItem(player, magical_theresas_doll);
                                Karl.SayTo(player,
                                    L(player, "Quest.Atlas.PowerOfNature.KarlStep4", player.Name));
                            }

                            break;
                    }
                }
            }
        }

        private static int CreateEffect(ECSGameTimer timer)
        {
            // dont change it
            int effectCount = 5;
            for (int i = 0; i <= effectCount; i++)
            {
                MobEffect = new GameNPC();
                MobEffect.Model = 1;
                MobEffect.Name = "power of nature";
                MobEffect.GuildName = string.Empty;
                MobEffect.Realm = eRealm.Hibernia;
                MobEffect.Race = 2007;
                MobEffect.BodyType = (ushort) NpcTemplateMgr.eBodyType.Magical;
                MobEffect.Size = 100;
                MobEffect.Level = 65;
                MobEffect.Flags ^= GameNPC.eFlags.CANTTARGET;
                MobEffect.Flags ^= GameNPC.eFlags.DONTSHOWNAME;
                MobEffect.Flags ^= GameNPC.eFlags.PEACE;
                switch (i)
                {
                    case 0:
                        MobEffect.CurrentRegionID = 200;
                        MobEffect.X = 328403;
                        MobEffect.Y = 518387;
                        MobEffect.Z = 4273;
                        break;
                    case 1:
                        MobEffect.CurrentRegionID = 200;
                        MobEffect.X = 328293;
                        MobEffect.Y = 518506;
                        MobEffect.Z = 4366;
                        break;
                    case 2:
                        MobEffect.CurrentRegionID = 200;
                        MobEffect.X = 328323;
                        MobEffect.Y = 518693;
                        MobEffect.Z = 4416;
                        break;
                    case 3:
                        MobEffect.CurrentRegionID = 200;
                        MobEffect.X = 328482;
                        MobEffect.Y = 518752;
                        MobEffect.Z = 4364;
                        break;
                    case 4:
                        MobEffect.CurrentRegionID = 200;
                        MobEffect.X = 328612;
                        MobEffect.Y = 518663;
                        MobEffect.Z = 4274;
                        break;
                    case 5:
                        MobEffect.CurrentRegionID = 200;
                        MobEffect.X = 328700;
                        MobEffect.Y = 518409;
                        MobEffect.Z = 4233;
                        break;
                }
                MobEffect.AddToWorld();

                var brain = new StandardMobBrain();
                brain.AggroLevel = 200;
                brain.AggroRange = 500;
                MobEffect.SetOwnBrain(brain);

                MobEffect.AddToWorld();
            }

            new ECSGameTimer(Karl, new ECSGameTimer.ECSTimerCallback(StartEffect), 1000);

            new ECSGameTimer(Karl, new ECSGameTimer.ECSTimerCallback(StartEffect), 1000);

            return 0;
        }

        private static int StartEffect(ECSGameTimer timer)
        {
            foreach (GameNPC effect in Karl.GetNPCsInRadius(600))
            {
                if (effect.Name.ToLower() == "power of nature")
                {
                    effect.CastSpell(EffectSpell, SkillBase.GetSpellLine(GlobalSpellsLines.Mob_Spells));
                }
            }
            return 0;
        }

        private static int StartTheresaEffect(ECSGameTimer timer)
        {
            Theresa.CastSpell(EffectSpell, SkillBase.GetSpellLine(GlobalSpellsLines.Mob_Spells));
            return 0;
        }

        private static int StartEffectPlayer(ECSGameTimer timer, GamePlayer player)
        {
            player.Out.SendSpellEffectAnimation(player, player, 5005, 0, false, 1);

            RemoveEffectMob();
            return 0;
        }

        private static void RemoveEffectMob()
        {
            foreach (GameNPC effect in Karl.GetNPCsInRadius(600))
            {
                if (effect.Name.ToLower() == "power of nature")
                    effect.RemoveFromWorld();
            }
        }

        #region EffectSpell
        private static Spell m_effect;
        /// <summary>
        /// The Health Regen Song.
        /// </summary>
        protected static Spell EffectSpell
        {
            get
            {
                if (m_effect == null)
                {
                    DbSpell spell = new DbSpell();
                    spell.AllowAdd = false;
                    spell.CastTime = 0;
                    spell.Icon = 5005;
                    spell.ClientEffect = 5005;
                    spell.Damage = 0;
                    spell.Duration = 1;
                    spell.Name = "Power of Nature";
                    spell.Range = 0;
                    spell.Radius = 0;
                    spell.SpellID = 5005;
                    spell.Target = eSpellTarget.SELF.ToString();
                    spell.Type = "StrengthBuff";
                    spell.Uninterruptible = true;
                    spell.MoveCast = true;
                    spell.DamageType = 0;
                    spell.Message1 = "The power of nature surrounds you.";
                    m_effect = new Spell(spell, 1);
                }
                return m_effect;
            }
        }
        #endregion

        public override bool CheckQuestQualification(GamePlayer player)
        {
            // if the player is already doing the quest his level is no longer of relevance
            if (player.IsDoingQuest(typeof(PowerOfNature)) != null)
                return true;

            if (player.Level < minimumLevel || player.Level > maximumLevel)
                return false;

            return true;
        }

        private static void CheckPlayerAbortQuest(GamePlayer player, byte response)
        {
            PowerOfNature quest = player.IsDoingQuest(typeof(PowerOfNature)) as PowerOfNature;

            if (quest == null)
                return;

            if (response == 0x00)
            {
                SendSystemMessage(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.ContinueQuestWork"));
            }
            else
            {
                SendSystemMessage(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.AbortingQuestRestart", questTitle));
                quest.AbortQuest();
            }
        }

        protected static void SubscribeQuest(DOLEvent e, object sender, EventArgs args)
        {
            QuestEventArgs qargs = args as QuestEventArgs;
            if (qargs == null)
                return;

            if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(PowerOfNature)))
                return;

            if (e == GamePlayerEvent.AcceptQuest)
                CheckPlayerAcceptQuest(qargs.Player, 0x01);
            else if (e == GamePlayerEvent.DeclineQuest)
                CheckPlayerAcceptQuest(qargs.Player, 0x00);
        }

        private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
        {
            if (Theresa.CanGiveQuest(typeof(PowerOfNature), player) <= 0)
                return;

            if (player.IsDoingQuest(typeof(PowerOfNature)) != null)
                return;

            if (response == 0x00)
            {
                Theresa.SayTo(player,
                    L(player, "Quest.Atlas.PowerOfNature.Decline"));
            }
            else
            {
                //Check if we can add the quest!
                if (!Theresa.GiveQuest(typeof(PowerOfNature), player, 1))
                    return;

                Theresa.SayTo(player,
                    L(player, "Quest.Atlas.PowerOfNature.Accept"));
            }
        }

        //Set quest name
        public override string Name
        {
            get { return L(m_questPlayer, "Quest.Atlas.PowerOfNature.Name"); }
        }

        // Define Steps
        public override string Description
        {
            get
            {
                switch (Step)
                {
                    case 1:
                        return L(m_questPlayer, "Quest.Atlas.PowerOfNature.Description1");
                    case 2:
                        return L(m_questPlayer, "Quest.Atlas.PowerOfNature.Description2");
                    case 3:
                        return L(m_questPlayer, "Quest.Atlas.PowerOfNature.Description3");
                    case 4:
                        return L(m_questPlayer, "Quest.Atlas.PowerOfNature.Description4");
                }

                return base.Description;
            }
        }

        public override void Notify(DOLEvent e, object sender, EventArgs args)
        {
            GamePlayer player = sender as GamePlayer;

            if (player == null || player.IsDoingQuest(typeof(PowerOfNature)) == null)
                return;
        }

        public class PowerOfNatureTitle : EventPlayerTitle
        {
            /// <summary>
            /// The title description, shown in "Titles" window.
            /// </summary>
            /// <param name="player">The title owner.</param>
            /// <returns>The title description.</returns>
            public override string GetDescription(GamePlayer player)
            {
                return L(player, "Quest.Atlas.PowerOfNature.Title");
            }

            /// <summary>
            /// The title value, shown over player's head.
            /// </summary>
            /// <param name="source">The player looking.</param>
            /// <param name="player">The title owner.</param>
            /// <returns>The title value.</returns>
            public override string GetValue(GamePlayer source, GamePlayer player)
            {
                return L(player, "Quest.Atlas.PowerOfNature.Title");
            }

            /// <summary>
            /// The event to hook.
            /// </summary>
            public override DOLEvent Event
            {
                get { return GamePlayerEvent.GameEntered; }
            }

            /// <summary>
            /// Verify whether the player is suitable for this title.
            /// </summary>
            /// <param name="player">The player to check.</param>
            /// <returns>true if the player is suitable for this title.</returns>
            public override bool IsSuitable(GamePlayer player)
            {
                return player.HasFinishedQuest(typeof(PowerOfNature)) == 1;
            }

            /// <summary>
            /// The event callback.
            /// </summary>
            /// <param name="e">The event fired.</param>
            /// <param name="sender">The event sender.</param>
            /// <param name="arguments">The event arguments.</param>
            protected override void EventCallback(DOLEvent e, object sender, EventArgs arguments)
            {
                GamePlayer p = sender as GamePlayer;
                if (p != null && p.Titles.Contains(this))
                {
                    p.UpdateCurrentTitle();
                    return;
                }

                base.EventCallback(e, sender, arguments);
            }
        }

        public override void AbortQuest()
        {
            base.AbortQuest(); //Defined in Quest, changes the state, stores in DB etc ...
        }

        public override void FinishQuest()
        {
            m_questPlayer.GainExperience(eXPSource.Quest, 20, false);
            m_questPlayer.AddServerIssuedMoney(Money.GetMoney(0, 0, 1, 32, Util.Random(50)), L(m_questPlayer, "Quest.Atlas.PowerOfNature.MoneyReward"));

            base.FinishQuest(); //Defined in Quest, changes the state, stores in DB etc ...
        }

        private static string L(GamePlayer player, string key, params object[] args)
        {
            string language = player?.Client?.Account?.Language ?? DOL.Language.LanguageMgr.DefaultLanguage;
            return DOL.Language.LanguageMgr.GetTranslation(language, key, args);
        }
    }
}
