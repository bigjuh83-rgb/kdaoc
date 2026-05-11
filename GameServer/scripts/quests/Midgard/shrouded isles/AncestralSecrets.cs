/*
*Author         : Kelt
*Editor			: Kelt
*Source         : SI Quest
*Date           : 09 June 2022
*Quest Name     : Ancestral Secrets
*Quest Classes  : all
*Quest Version  : v1.0
*
*Changes:
*
*/

using System;
using System.Reflection;
using System.Threading;
using DOL.AI.Brain;
using DOL.Database;
using DOL.Events;
using DOL.GS.PacketHandler;

namespace DOL.GS.Quests.Hibernia
{
	public class AncestralSecrets : BaseQuest
	{
		/// <summary>
		/// Defines a logger for this class.
		/// </summary>
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

		private const string questTitle = "Ancestral Secrets";
		private const int minimumLevel = 48;
		private const int maximumLevel = 50;

		private static GameNPC OtaYrling = null; // Start NPC + Finish NPC
		private static GameNPC Jaklyr = null; //
		private static GameNPC Longbeard = null; //
		private static GameNPC Styr = null; //

		private static GameNPC AncestralKeeper = null; //Mob to Kill

		private static readonly GameLocation keeperLocation = new("Ancestral Keeper", 151, 363016, 310849, 3933);

		private static AbstractArea keeperArea;

		private static DbItemTemplate beaded_resisting_stone;
		private static DbItemTemplate stone_pendant;
		private static DbItemTemplate quest_pendant;

		// Constructors
		public AncestralSecrets() : base()
		{
		}

		public AncestralSecrets(GamePlayer questingPlayer) : base(questingPlayer)
		{
		}

		public AncestralSecrets(GamePlayer questingPlayer, int step) : base(questingPlayer, step)
		{
		}

		public AncestralSecrets(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest)
		{
		}

		private static string L(GamePlayer player, string key, params object[] args)
		{
			return DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, key, args);
		}

		private string Q(string key, params object[] args)
		{
			string language = m_questPlayer != null && m_questPlayer.Client != null && m_questPlayer.Client.Account != null
				? m_questPlayer.Client.Account.Language
				: ServerProperties.Properties.SERV_LANGUAGE;
			return DOL.Language.LanguageMgr.GetTranslation(language, key, args);
		}

		public override int Level =>
			// Quest Level
			minimumLevel;

		[ScriptLoadedEvent]
		public static void ScriptLoaded(DOLEvent e, object sender, EventArgs args)
		{
			if (!ServerProperties.Properties.LOAD_QUESTS)
				return;

			#region defineNPCs

			 var npcs = WorldMgr.GetNPCsByName("Ota Yrling", eRealm.Midgard);

        if (npcs.Length > 0)
            foreach (var npc in npcs)
                if (npc.CurrentRegionID == 151 && npc.X == 291615 && npc.Y == 354310)
                {
	                OtaYrling = npc;
                    break;
                }

        if (OtaYrling == null)
        {
            if (log.IsWarnEnabled)
                log.Warn("Could not find Ota Yrling, creating it ...");
            OtaYrling = new GameNPC();
            OtaYrling.Model = 230;
            OtaYrling.Name = "Ota Yrling";
            OtaYrling.GuildName = string.Empty;
            OtaYrling.Realm = eRealm.Midgard;
            OtaYrling.CurrentRegionID = 151;
            OtaYrling.LoadEquipmentTemplateFromDatabase("95ff9192-4787-4dca-bcbb-7a081d801074");
            OtaYrling.Size = 49;
            OtaYrling.Level = 50;
            OtaYrling.X = 291615;
            OtaYrling.Y = 354310;
            OtaYrling.Z = 3866;
            OtaYrling.Heading = 739;
            OtaYrling.AddToWorld();
            if (SAVE_INTO_DATABASE) OtaYrling.SaveIntoDatabase();
        }

        npcs = WorldMgr.GetNPCsByName("Jaklyr", eRealm.Midgard);

        if (npcs.Length > 0)
            foreach (var npc in npcs)
                if (npc.CurrentRegionID == 151 && npc.X == 289376 && npc.Y == 304521)
                {
	                Jaklyr = npc;
                    break;
                }

        if (Jaklyr == null)
        {
            if (log.IsWarnEnabled)
                log.Warn("Could not find Jaklyr , creating it ...");
            Jaklyr = new GameNPC();
            Jaklyr.Model = 203;
            Jaklyr.Name = "Jaklyr";
            Jaklyr.GuildName = string.Empty;
            Jaklyr.Realm = eRealm.Midgard;
            Jaklyr.CurrentRegionID = 151;
            Jaklyr.LoadEquipmentTemplateFromDatabase("MidTownsperson4");
            Jaklyr.Size = 52;
            Jaklyr.Level = 60;
            Jaklyr.X = 289376;
            Jaklyr.Y = 304521;
            Jaklyr.Z = 4253;
            Jaklyr.Heading = 1841;
            Jaklyr.AddToWorld();
            if (SAVE_INTO_DATABASE) Jaklyr.SaveIntoDatabase();
        }
        // end npc

        npcs = WorldMgr.GetNPCsByName("Longbeard", eRealm.Midgard);
        if (npcs.Length > 0)
            foreach (var npc in npcs)
                if (npc.CurrentRegionID == 151 && npc.X == 290742 && npc.Y == 355471)
                {
	                Longbeard = npc;
                    break;
                }

        if (Longbeard == null)
        {
            if (log.IsWarnEnabled)
                log.Warn("Could not find Longbeard, creating it ...");
            Longbeard = new GameNPC();
            Longbeard.LoadEquipmentTemplateFromDatabase("be600079-ca29-4093-953a-3ee3aa1552e8");
            Longbeard.Model = 232;
            Longbeard.Name = "Longbeard";
            Longbeard.GuildName = string.Empty;
            Longbeard.Realm = eRealm.Midgard;
            Longbeard.CurrentRegionID = 151;
            Longbeard.Size = 53;
            Longbeard.Level = 50;
            Longbeard.X = 290742;
            Longbeard.Y = 355471;
            Longbeard.Z = 3867;
            Longbeard.Heading = 1695;
            Longbeard.VisibleActiveWeaponSlots = 34;
            Longbeard.MaxSpeedBase = 200;
            Longbeard.AddToWorld();
            if (SAVE_INTO_DATABASE) Longbeard.SaveIntoDatabase();
        }
        // end npc

        npcs = WorldMgr.GetNPCsByName("Styr", eRealm.Midgard);
        if (npcs.Length > 0)
	        foreach (var npc in npcs)
		        if (npc.CurrentRegionID == 151 && npc.X == 290643 && npc.Y == 355275)
		        {
			        Styr = npc;
			        break;
		        }

        if (Styr == null)
        {
	        if (log.IsWarnEnabled)
		        log.Warn("Could not find Styr, creating it ...");
	        Styr = new GameNPC();
	        Styr.LoadEquipmentTemplateFromDatabase("dbdb0127-cbbe-42b5-b60a-3cdc27256ae9");
	        Styr.Model = 235;
	        Styr.Name = "Styr";
	        Styr.GuildName = string.Empty;
	        Styr.Realm = eRealm.Midgard;
	        Styr.CurrentRegionID = 151;
	        Styr.Size = 51;
	        Styr.Level = 50;
	        Styr.X = 290643;
	        Styr.Y = 355275;
	        Styr.Z = 3867;
	        Styr.Heading = 3725;
	        Styr.VisibleActiveWeaponSlots = 34;
	        Styr.MaxSpeedBase = 200;
	        Styr.AddToWorld();
	        if (SAVE_INTO_DATABASE) Styr.SaveIntoDatabase();
        }
        // end npc
			#endregion

			#region defineItems
			beaded_resisting_stone = GameServer.Database.FindObjectByKey<DbItemTemplate>("Beaded Resisting Stones");

			quest_pendant = GameServer.Database.FindObjectByKey<DbItemTemplate>("quest_pendant");
	        if (quest_pendant == null)
	        {
		        if (log.IsWarnEnabled)
			        log.Warn("Could not find Lightly Decorated Pendant, creating it ...");
		        quest_pendant = new DbItemTemplate();
		        quest_pendant.Id_nb = "quest_pendant";
		        quest_pendant.Name = "Lightly Decorated Pendant";
		        quest_pendant.Level = 50;
		        quest_pendant.Item_Type = 0;
		        quest_pendant.Model = 101;
		        quest_pendant.IsDropable = true;
		        quest_pendant.IsTradable = false;
		        quest_pendant.IsIndestructible = true;
		        quest_pendant.IsPickable = true;
		        quest_pendant.DPS_AF = 0;
		        quest_pendant.SPD_ABS = 0;
		        quest_pendant.Object_Type = 0;
		        quest_pendant.Hand = 0;
		        quest_pendant.Type_Damage = 0;
		        quest_pendant.Quality = 100;
		        quest_pendant.Weight = 1;
		        quest_pendant.Description = "A lightly decorated pendant with slight rusted spots.";
		        if (SAVE_INTO_DATABASE) GameServer.Database.AddObject(quest_pendant);
	        }

	        stone_pendant = GameServer.Database.FindObjectByKey<DbItemTemplate>("stone_pendant");
	        if (stone_pendant == null)
	        {
		        if (log.IsWarnEnabled)
			        log.Warn("Could not find Stone Pendant, creating it ...");
		        stone_pendant = new DbItemTemplate();
		        stone_pendant.Id_nb = "stone_pendant";
		        stone_pendant.Name = "Stone Pendant";
		        stone_pendant.Level = 50;
		        stone_pendant.Item_Type = 0;
		        stone_pendant.Model = 624;
		        stone_pendant.IsDropable = true;
		        stone_pendant.IsTradable = false;
		        stone_pendant.IsIndestructible = true;
		        stone_pendant.IsPickable = true;
		        stone_pendant.DPS_AF = 0;
		        stone_pendant.SPD_ABS = 0;
		        stone_pendant.Object_Type = 0;
		        stone_pendant.Hand = 0;
		        stone_pendant.Type_Damage = 0;
		        stone_pendant.Quality = 100;
		        stone_pendant.Weight = 1;
		        stone_pendant.Description = "A stone pendant with magical decorative writings.";
		        if (SAVE_INTO_DATABASE) GameServer.Database.AddObject(stone_pendant);
	        }
			#endregion

			const int radius = 1000;
			var region = WorldMgr.GetRegion(keeperLocation.RegionID);
			if (region == null)
			{
				log.Error("Could not find region " + keeperLocation.RegionID + " when trying to create " + questTitle + " keeper area.");
				return;
			}

			keeperArea = new Area.Circle("cursed crystals", keeperLocation.X, keeperLocation.Y, keeperLocation.Z,
				radius);
			keeperArea.CanBroadcast = false;
			keeperArea.DisplayMessage = false;
			region.AddArea(keeperArea);
			keeperArea.RegisterPlayerEnter(PlayerEnterKeeperArea);

			GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.AddHandler(OtaYrling, GameObjectEvent.Interact, TalkToOtaYrling);
			GameEventMgr.AddHandler(OtaYrling, GameLivingEvent.WhisperReceive, TalkToOtaYrling);

			GameEventMgr.AddHandler(Jaklyr, GameObjectEvent.Interact, TalkToJaklyr);
			GameEventMgr.AddHandler(Jaklyr, GameLivingEvent.WhisperReceive, TalkToJaklyr);

			GameEventMgr.AddHandler(Longbeard, GameObjectEvent.Interact, TalkToLongbeard);
			GameEventMgr.AddHandler(Longbeard, GameLivingEvent.WhisperReceive, TalkToLongbeard);

			GameEventMgr.AddHandler(Styr, GameObjectEvent.Interact, TalkToStyr);
			GameEventMgr.AddHandler(Styr, GameLivingEvent.WhisperReceive, TalkToStyr);

			/* Now we bring to Ota Yrling the possibility to give this quest to players */
			OtaYrling?.AddQuestToGive(typeof (AncestralSecrets));

			if (log.IsInfoEnabled)
				log.Info("Quest \"" + questTitle + "\" initialized");
		}

		[ScriptUnloadedEvent]
		public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
		{
			//if not loaded, don't worry
			if (OtaYrling == null)
				return;

			// remove handlers
			keeperArea.UnRegisterPlayerEnter(PlayerEnterKeeperArea);
			WorldMgr.GetRegion(keeperLocation.RegionID)?.RemoveArea(keeperArea);

			GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.RemoveHandler(OtaYrling, GameObjectEvent.Interact, TalkToOtaYrling);
			GameEventMgr.RemoveHandler(OtaYrling, GameLivingEvent.WhisperReceive, TalkToOtaYrling);

			GameEventMgr.RemoveHandler(Jaklyr, GameObjectEvent.Interact, TalkToJaklyr);
			GameEventMgr.RemoveHandler(Jaklyr, GameLivingEvent.WhisperReceive, TalkToJaklyr);

			GameEventMgr.RemoveHandler(Longbeard, GameObjectEvent.Interact, TalkToLongbeard);
			GameEventMgr.RemoveHandler(Longbeard, GameLivingEvent.WhisperReceive, TalkToLongbeard);

			GameEventMgr.RemoveHandler(Styr, GameObjectEvent.Interact, TalkToStyr);
			GameEventMgr.RemoveHandler(Styr, GameLivingEvent.WhisperReceive, TalkToStyr);

			/* Now we remove to Ota Yrling the possibility to give this quest to players */
			OtaYrling.RemoveQuestToGive(typeof (AncestralSecrets));
		}

		protected virtual void CreateAncestralKeeper(GamePlayer player)
		{
			foreach (GameNPC npc in WorldMgr.GetNPCsCloseToSpot(151, 363016, 310849, 3933, 8000))
			{
				if (npc.Brain is SINeckBossBrain)
					return;
			}
			AncestralKeeper = new SINeckBoss();
			AncestralKeeper.Model = 951;
			AncestralKeeper.Name = "Ancestral Keeper";
			AncestralKeeper.GuildName = string.Empty;
			AncestralKeeper.Realm = eRealm.None;
			AncestralKeeper.Race = 2003;
			AncestralKeeper.BodyType = (ushort) NpcTemplateMgr.eBodyType.Elemental;
			AncestralKeeper.CurrentRegionID = 151;
			AncestralKeeper.Size = 140;
			AncestralKeeper.Level = 65;
			AncestralKeeper.X = player.X;
			AncestralKeeper.Y = player.Y;
			AncestralKeeper.Z = player.Z;
			AncestralKeeper.MaxSpeedBase = 250;
			//AncestralKeeper.AddToWorld();

			var brain = new SINeckBossBrain();
			brain.AggroLevel = 200;
			brain.AggroRange = 500;
			AncestralKeeper.SetOwnBrain(brain);

			AncestralKeeper.AddToWorld();

			AncestralKeeper.StartAttack(player);

			GameEventMgr.AddHandler(AncestralKeeper, GameLivingEvent.Dying, AncestralKeeperDying);
		}
		private void AncestralKeeperDying(DOLEvent e, object sender, EventArgs arguments)
		{
			var args = (DyingEventArgs) arguments;

			var player = args.Killer as GamePlayer;

			if (args.Killer is GameSummonedPet pet)
			{
				if(pet != null && pet.Owner != null)
                {
					GamePlayer pet_owner = pet.Owner as GamePlayer;
					if (pet_owner != null && pet_owner.IsAlive)
					{
						if (pet_owner.Group != null)
						{
							foreach (var gpl in pet_owner.Group.GetPlayersInTheGroup())//gain credit for every one in petowner grp
							{
								AdvanceAfterKill(gpl);
							}
						}
						else//player not in grp
						{
							AdvanceAfterKill(pet_owner);
						}
					}
				}
			}

			if (player == null)
            {
				AncestralKeeper.Delete();
				GameEventMgr.RemoveHandler(AncestralKeeper, GameLivingEvent.Dying, AncestralKeeperDying);
				return;
			}

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

			GameEventMgr.RemoveHandler(AncestralKeeper, GameLivingEvent.Dying, AncestralKeeperDying);
			AncestralKeeper.Delete();
		}
		private static void AdvanceAfterKill(GamePlayer player)
		{
			var quest = player.IsDoingQuest(typeof(AncestralSecrets)) as AncestralSecrets;
			if (quest is not {Step: 4}) return;
			RemoveItem(player, quest_pendant);
			SendMessage(player, L(player, "Quest.Midgard.AncestralSecrets.CurseLifted"), 0, eChatType.CT_System, eChatLoc.CL_SystemWindow);
			GiveItem(player, stone_pendant);
			quest.Step = 5;
		}

		private static void PlayerEnterKeeperArea(DOLEvent e, object sender, EventArgs args)
		{
			var aargs = args as AreaEventArgs;
			var player = aargs?.GameObject as GamePlayer;

			if (player == null)
				return;

			var quest = player.IsDoingQuest(typeof(AncestralSecrets)) as AncestralSecrets;

			if (quest is not {Step: 4}) return;

			var existingCopy = WorldMgr.GetNPCsByName("Ancestral Keeper", eRealm.None);

			if (existingCopy.Length > 0) return;


			//only try to spawn him once per trigger even if multiple people enter at the same time
			if (_spawnLock.TryEnter())
			{
				try
				{
					// player near ancestral keeper
					SendSystemMessage(player, L(player, "Quest.Midgard.AncestralSecrets.CrystalBreaks"));
					player.Out.SendMessage(L(player, "Quest.Midgard.AncestralSecrets.AncestralKeeperAmbush"), eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
					quest.CreateAncestralKeeper(player);
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

		protected static void TalkToOtaYrling(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(OtaYrling.CanGiveQuest(typeof (AncestralSecrets), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			AncestralSecrets quest = player.IsDoingQuest(typeof (AncestralSecrets)) as AncestralSecrets;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.Step1"));
							break;
						case 2:
							OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.Step2", player.Name));

							int random = Util.Random(0, 3);
							var message = string.Empty;
							switch (random)
							{
								case 0:
									Longbeard.Emote(eEmote.Laugh);
									Longbeard.TurnTo(player);
									Styr.Emote(eEmote.Laugh);
									message = L(player, "Quest.Midgard.AncestralSecrets.Longbeard.TauntOta");
									break;
								case 1:
									Longbeard.Emote(eEmote.Rofl);
									Longbeard.TurnTo(player);
									Styr.Emote(eEmote.Laugh);
									message = L(player, "Quest.Midgard.AncestralSecrets.Longbeard.TauntStyr", player.CharacterClass.Name);
									break;
								case 2:
									Longbeard.Emote(eEmote.Laugh);
									Styr.TurnTo(player);
									Styr.Emote(eEmote.Rofl);
									message = L(player, "Quest.Midgard.AncestralSecrets.Styr.TauntLongbeard", player.CharacterClass.Name);
									break;
								case 3:
									Longbeard.Emote(eEmote.Laugh);
									Styr.TurnTo(player);
									Styr.Emote(eEmote.Laugh);
									message = L(player, "Quest.Midgard.AncestralSecrets.Styr.TauntOta");
									break;
							}
							SendMessage(player, message, 0,eChatType.CT_Say, eChatLoc.CL_ChatWindow);
							break;
						case 3:
							OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.Step3", player.Name));
							break;
						case 4:
							OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.Step4"));
							break;
						case 5:
							OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.Step5"));
							break;
						case 6:
							OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.Step6"));
							break;
					}
				}
				else
				{
					OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.Intro", player.Name));
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
							case "Curse":
							case "저주":
							player.Out.SendQuestSubscribeCommand(OtaYrling, QuestMgr.GetIDForQuestType(typeof(AncestralSecrets)), L(player, "Quest.Midgard.AncestralSecrets.Subscribe"));
							break;
					}
				}
				else
				{
					switch (wArgs.Text)
					{
							case "impact":
							case "충돌":
							OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.Impact", player.Name));
							break;
							case "secrets":
							case "비밀":
							if (quest.Step == 1)
							{
								OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.Secrets"));
								Longbeard.Yell(L(player, "Quest.Midgard.AncestralSecrets.Longbeard.YellNeedHelp", player.CharacterClass.Name));
								Longbeard.Emote(eEmote.Laugh);
								Styr.Emote(eEmote.Laugh);
								quest.Step = 2;
							}
							break;
							case "reward":
							case "보상":
							if (quest.Step == 6)
							{
								Longbeard.Yell(L(player, "Quest.Midgard.AncestralSecrets.Longbeard.RewardThanks", player.Name));
								Longbeard.Emote(eEmote.Clap);
								Styr.Emote(eEmote.Cheer);
								quest.FinishQuest();
							}
							break;
						case "abort":
							player.Out.SendCustomDialog(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.AbortConfirm"), new CustomDialogResponse(CheckPlayerAbortQuest));
							break;
					}
				}
			}
			else if (e == GameLivingEvent.ReceiveItem)
			{
				ReceiveItemEventArgs rArgs = (ReceiveItemEventArgs) args;
				if (quest != null)
					if (rArgs.Item.Id_nb == stone_pendant.Id_nb)
					{
						if (quest.Step == 6)
						{
							OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.ReceiveStonePendant"));
						}
					}
			}
		}

		protected static void TalkToJaklyr(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(OtaYrling.CanGiveQuest(typeof (AncestralSecrets), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			AncestralSecrets quest = player.IsDoingQuest(typeof (AncestralSecrets)) as AncestralSecrets;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							Jaklyr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Jaklyr.Step1"));
							break;
						case 2:
							Jaklyr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Jaklyr.Step2", player.CharacterClass.Name));
							break;
						case 3:
							Jaklyr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Jaklyr.Step3", player.CharacterClass.Name));
							break;
						case 4:
							Jaklyr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Jaklyr.Step4Wish"));
							Jaklyr.SayTo(player,
								L(player, "Quest.Midgard.AncestralSecrets.Jaklyr.Step4Directions"));
							break;
						case 5:
							Jaklyr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Jaklyr.Step5"));
							break;
						case 6:
							Jaklyr.SayTo(player, "");
							break;
					}
				}
				else
				{
					Jaklyr.SayTo(player, "");
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
							case "sent":
							case "보냈습니까":
							Jaklyr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Jaklyr.Sent"));
							break;
							case "Delling Crater":
							case "델링 분화구":
							if (quest.Step == 3)
							{
								if (player.Inventory.IsSlotsFree(1, eInventorySlot.FirstBackpack,
									    eInventorySlot.LastBackpack))
								{
									Jaklyr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Jaklyr.DellingCrater"));
									GiveItem(player, quest_pendant);
									quest.Step = 4;
								}
								else
								{
									Jaklyr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Jaklyr.InventoryFull"));
								}
							}
							break;
							case "pendant":
							case "펜던트":
							RemoveItem(player, stone_pendant);
							Jaklyr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Jaklyr.Pendant"));
							Jaklyr.Emote(eEmote.Cheer);
							break;
							case "trapped":
							case "갇혀":
							if (quest.Step == 5)
							{
								Jaklyr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Jaklyr.Trapped"));
								GiveItem(player, stone_pendant);
								quest.Step = 6;
							}
							break;
					}
				}
			}
			else if (e == GameLivingEvent.ReceiveItem)
			{
				ReceiveItemEventArgs rArgs = (ReceiveItemEventArgs) args;
				if (quest != null)
					if (rArgs.Item.Id_nb == stone_pendant.Id_nb)
					{
						if (quest.Step == 5)
						{
							Jaklyr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Jaklyr.Pendant"));
							Jaklyr.Emote(eEmote.Cheer);
						}
					}
			}
		}

		protected static void TalkToLongbeard(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(OtaYrling.CanGiveQuest(typeof (AncestralSecrets), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			AncestralSecrets quest = player.IsDoingQuest(typeof (AncestralSecrets)) as AncestralSecrets;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							Longbeard.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Longbeard.Step1"));
							break;
						case 2:
							Longbeard.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Longbeard.Step2"));
							break;
						case 3:
							Longbeard.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Longbeard.Step3", player.CharacterClass.Name));
							break;
						case 4:
							Longbeard.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Longbeard.Step4"));
							break;
						case 5:
							Longbeard.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Longbeard.Step5"));
							break;
						case 6:
							Longbeard.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Longbeard.Step6", player.Name));
							break;
					}
				}
				else
				{
					Longbeard.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Longbeard.Intro"));
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
							case "don't try":
							case "시도하지 마":
							Longbeard.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Longbeard.DontTry"));
							break;
							case "the crater":
							case "분화구":
							Longbeard.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Longbeard.TheCrater"));
							Longbeard.Emote(eEmote.Induct);
							break;
							case "challenge":
							case "도전":
							if (quest.Step == 2)
							{
								Longbeard.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Longbeard.Challenge"));
								Longbeard.Emote(eEmote.Wave);
								quest.Step = 3;
							}
							break;
					}
				}
			}
			else if (e == GameLivingEvent.ReceiveItem)
			{
				ReceiveItemEventArgs rArgs = (ReceiveItemEventArgs) args;
				if (quest != null)
				{

				}
			}
		}

		protected static void TalkToStyr(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(OtaYrling.CanGiveQuest(typeof (AncestralSecrets), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			AncestralSecrets quest = player.IsDoingQuest(typeof (AncestralSecrets)) as AncestralSecrets;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							Styr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Styr.Step1"));
							break;
						case 2:
							Styr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Styr.Step2"));
							break;
						case 3:
							Styr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Styr.Step3"));
							break;
						case 4:
							Styr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Styr.Step4"));
							break;
						case 5:
							Styr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Styr.Step5"));
							break;
						case 6:
							Styr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Styr.Step6"));
							break;

					}
				}
				else
				{
					Styr.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Styr.Intro"));
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
					}
				}
			}
			else if (e == GameLivingEvent.ReceiveItem)
			{
				ReceiveItemEventArgs rArgs = (ReceiveItemEventArgs) args;
				if (quest != null){}

			}
		}

		public override bool CheckQuestQualification(GamePlayer player)
		{
			// if the player is already doing the quest his level is no longer of relevance
			if (player.IsDoingQuest(typeof (AncestralSecrets)) != null)
				return true;

			if (player.Level < minimumLevel || player.Level > maximumLevel)
				return false;

			return true;
		}

		private static void CheckPlayerAbortQuest(GamePlayer player, byte response)
		{
			AncestralSecrets quest = player.IsDoingQuest(typeof (AncestralSecrets)) as AncestralSecrets;

			if (quest == null)
				return;

			if (response == 0x00)
			{
				SendSystemMessage(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.AbortCancelled"));
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

			if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(AncestralSecrets)))
				return;

			if (e == GamePlayerEvent.AcceptQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x01);
			else if (e == GamePlayerEvent.DeclineQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x00);
		}

		private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
		{
			if(OtaYrling.CanGiveQuest(typeof (AncestralSecrets), player)  <= 0)
				return;

			if(player.IsDoingQuest(typeof (AncestralSecrets)) != null)
				return;

			if (response == 0x00)
			{
				OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.Decline"));
			}
			else
			{
				//Check if we can add the quest!
				if (!OtaYrling.GiveQuest(typeof (AncestralSecrets), player, 1))
					return;
			}
			OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.Accepted", player.Name));
			OtaYrling.SayTo(player, L(player, "Quest.Midgard.AncestralSecrets.Ota.Step1Accepted"));

		}

		//Set quest name
		public override string Name
		{
			get { return questTitle; }
		}

		// Define Steps
		public override string Description
		{
			get
			{
				switch (Step)
				{
					case 1:
						return Q("Quest.Midgard.AncestralSecrets.Description.Step1");
					case 2:
						return Q("Quest.Midgard.AncestralSecrets.Description.Step2");
					case 3:
						return Q("Quest.Midgard.AncestralSecrets.Description.Step3");
					case 4:
						return Q("Quest.Midgard.AncestralSecrets.Description.Step4");
					case 5:
						return Q("Quest.Midgard.AncestralSecrets.Description.Step5");
					case 6:
						return Q("Quest.Midgard.AncestralSecrets.Description.Step6");
				}
				return base.Description;
			}
		}
		public override void AbortQuest()
		{
			base.AbortQuest(); //Defined in Quest, changes the state, stores in DB etc ...
			RemoveItem(m_questPlayer, quest_pendant);
			RemoveItem(m_questPlayer, stone_pendant);
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
				RemoveItem(m_questPlayer, stone_pendant);
				GiveItem(m_questPlayer, beaded_resisting_stone);
				m_questPlayer.AddServerIssuedMoney(Money.GetMoney(0, 0, 121, 41, Util.Random(50)), Q("Quest.Common.MoneyReward"));


				base.FinishQuest(); //Defined in Quest, changes the state, stores in DB etc ...
			}
			else
			{
				m_questPlayer.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.NotEnoughInventorySpace"),
					eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			}
		}
	}
}
