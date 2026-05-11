/*
*Author         : Kelt
*Editor			: Kelt
*Source         : SI Quest
*Date           : 09 June 2022
*Quest Name     : The Lost Seed
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
	public class TheLostSeed : BaseQuest
	{
		/// <summary>
		/// Defines a logger for this class.
		/// </summary>
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

		private const string questTitle = "The Lost Seed";
		private const int minimumLevel = 48;
		private const int maximumLevel = 50;

		private static GameNPC Terod = null; // Start NPC + Finish NPC
		private static GameNPC Kredril = null; // step 2
		private static HiberniaSITeleporter Emolia = null; // step 3
		private static GameNPC Jandros = null; // step 4 + 6

		private static GameNPC Feairna_Athar = null; //Mob to Kill

		private static readonly GameLocation treantLocation = new("Feairna-Athar", 181, 288348, 319950, 2328);

		private static AbstractArea treantArea;

		private static DbItemTemplate paidrean_necklace;
		private static DbItemTemplate glowing_red_jewel;
		// Constructors
		public TheLostSeed() : base()
		{
		}

		public TheLostSeed(GamePlayer questingPlayer) : base(questingPlayer)
		{
		}

		public TheLostSeed(GamePlayer questingPlayer, int step) : base(questingPlayer, step)
		{
		}

		public TheLostSeed(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest)
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

			 var npcs = WorldMgr.GetNPCsByName("Terod", eRealm.Hibernia);

        if (npcs.Length > 0)
            foreach (var npc in npcs)
                if (npc.CurrentRegionID == 181 && npc.X == 382809 && npc.Y == 421409)
                {
	                Terod = npc;
                    break;
                }

        if (Terod == null)
        {
            if (log.IsWarnEnabled)
                log.Warn("Could not find Terod, creating it ...");
            Terod = new GameNPC();
            Terod.Model = 382;
            Terod.Name = "Terod";
            Terod.GuildName = string.Empty;
            Terod.Realm = eRealm.Hibernia;
            Terod.CurrentRegionID = 181;
            Terod.LoadEquipmentTemplateFromDatabase("Terod");
            Terod.Size = 50;
            Terod.Level = 50;
            Terod.X = 382809;
            Terod.Y = 421409;
            Terod.Z = 5604;
            Terod.Heading = 1044;
            Terod.AddToWorld();
            if (SAVE_INTO_DATABASE) Terod.SaveIntoDatabase();
        }

        npcs = WorldMgr.GetNPCsByName("Kredril", eRealm.Hibernia);

        if (npcs.Length > 0)
            foreach (var npc in npcs)
                if (npc.CurrentRegionID == 181 && npc.X == 380514 && npc.Y == 421419)
                {
	                Kredril = npc;
                    break;
                }

        if (Kredril == null)
        {
            if (log.IsWarnEnabled)
                log.Warn("Could not find Kredril , creating it ...");
            Kredril = new GameNPC();
            Kredril.Model = 352;
            Kredril.Name = "Kredril";
            Kredril.GuildName = string.Empty;
            Kredril.Realm = eRealm.Hibernia;
            Kredril.CurrentRegionID = 181;
            Kredril.LoadEquipmentTemplateFromDatabase("Kredril");
            Kredril.Size = 51;
            Kredril.Level = 52;
            Kredril.X = 380514;
            Kredril.Y = 421419;
            Kredril.Z = 5520;
            Kredril.Heading = 1420;
            Kredril.AddToWorld();
            if (SAVE_INTO_DATABASE) Kredril.SaveIntoDatabase();
        }
        // end npc

        npcs = WorldMgr.GetNPCsByName("Emolia", eRealm.Hibernia);
        if (npcs.Length > 0)
            foreach (var npc in npcs)
                if (npc.CurrentRegionID == 181 && npc.X == 404696 && npc.Y == 503469)
                {
	                Emolia = (HiberniaSITeleporter)npc;
                    break;
                }

        if (Emolia == null)
        {
            if (log.IsWarnEnabled)
                log.Warn("Could not find Emolia , creating it ...");
            Emolia = new HiberniaSITeleporter();
            //should load equipment from script
            //Emolia.LoadEquipmentTemplateFromDatabase("Emolia");
            Emolia.Model = 714;
            Emolia.Name = "Emolia";
            Emolia.GuildName = string.Empty;
            Emolia.Realm = eRealm.Hibernia;
            Emolia.CurrentRegionID = 181;
            Emolia.Size = 50;
            Emolia.Level = 50;
            Emolia.X = 378864;
            Emolia.Y = 421086;
            Emolia.Z = 5528;
            Emolia.Heading = 3054;
            Emolia.VisibleActiveWeaponSlots = 34;
            Emolia.MaxSpeedBase = 200;
            Emolia.AddToWorld();
            if (SAVE_INTO_DATABASE) Emolia.SaveIntoDatabase();
        }
        // end npc

        npcs = WorldMgr.GetNPCsByName("Jandros", eRealm.Hibernia);
        if (npcs.Length > 0)
	        foreach (var npc in npcs)
		        if (npc.CurrentRegionID == 181 && npc.X == 404696 && npc.Y == 503469)
		        {
			        Jandros = npc;
			        break;
		        }

        if (Jandros == null)
        {
	        if (log.IsWarnEnabled)
		        log.Warn("Could not find Jandros , creating it ...");
	        Jandros = new GameNPC();
	        Jandros.LoadEquipmentTemplateFromDatabase("d26b8dab-dbdd-4d82-b265-9376cab4deb7");
	        Jandros.Model = 734;
	        Jandros.Name = "Jandros";
	        Jandros.GuildName = string.Empty;
	        Jandros.Realm = eRealm.Hibernia;
	        Jandros.CurrentRegionID = 181;
	        Jandros.Size = 53;
	        Jandros.Level = 54;
	        Jandros.X = 310873;
	        Jandros.Y = 349961;
	        Jandros.Z = 3571;
	        Jandros.Heading = 1459;
	        Jandros.VisibleActiveWeaponSlots = 34;
	        Jandros.MaxSpeedBase = 200;
	        Jandros.AddToWorld();
	        if (SAVE_INTO_DATABASE) Jandros.SaveIntoDatabase();
        }
        // end npc
			#endregion

			#region defineItems
			paidrean_necklace = GameServer.Database.FindObjectByKey<DbItemTemplate>("Paidrean Necklace");

	        glowing_red_jewel = GameServer.Database.FindObjectByKey<DbItemTemplate>("glowing_red_jewel");
	        if (glowing_red_jewel == null)
	        {
		        if (log.IsWarnEnabled)
			        log.Warn("Could not find Glowing Red Jewel, creating it ...");
		        glowing_red_jewel = new DbItemTemplate();
		        glowing_red_jewel.Id_nb = "glowing_red_jewel";
		        glowing_red_jewel.Name = "Glowing Red Jewel";
		        glowing_red_jewel.Level = 55;
		        glowing_red_jewel.Item_Type = 0;
		        glowing_red_jewel.Model = 110;
		        glowing_red_jewel.IsDropable = true;
		        glowing_red_jewel.IsTradable = false;
		        glowing_red_jewel.IsIndestructible = true;
		        glowing_red_jewel.IsPickable = true;
		        glowing_red_jewel.DPS_AF = 0;
		        glowing_red_jewel.SPD_ABS = 0;
		        glowing_red_jewel.Object_Type = 0;
		        glowing_red_jewel.Hand = 0;
		        glowing_red_jewel.Type_Damage = 0;
		        glowing_red_jewel.Quality = 100;
		        glowing_red_jewel.Weight = 1;
		        glowing_red_jewel.Description = "A jewel of unnatural power.";
		        if (SAVE_INTO_DATABASE) GameServer.Database.AddObject(glowing_red_jewel);
	        }
			#endregion

			const int radius = 1500;
			var region = WorldMgr.GetRegion(treantLocation.RegionID);
			if (region == null)
			{
				log.Error("Could not find region " + treantLocation.RegionID + " when trying to create " + questTitle + " treant area.");
				return;
			}

			treantArea = new Area.Circle("accursed piece of forest", treantLocation.X, treantLocation.Y, treantLocation.Z,
				radius);
			treantArea.CanBroadcast = false;
			treantArea.DisplayMessage = false;
			region.AddArea(treantArea);
			treantArea.RegisterPlayerEnter(PlayerEnterTreantArea);

			GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.AddHandler(Terod, GameObjectEvent.Interact, TalkToTerod);
			GameEventMgr.AddHandler(Terod, GameLivingEvent.WhisperReceive, TalkToTerod);

			GameEventMgr.AddHandler(Kredril, GameObjectEvent.Interact, TalkToKredril);
			GameEventMgr.AddHandler(Kredril, GameLivingEvent.WhisperReceive, TalkToKredril);

			GameEventMgr.AddHandler(Emolia, GameObjectEvent.Interact, TalkToEmolia);
			GameEventMgr.AddHandler(Emolia, GameLivingEvent.WhisperReceive, TalkToEmolia);

			GameEventMgr.AddHandler(Jandros, GameObjectEvent.Interact, TalkToJandros);
			GameEventMgr.AddHandler(Jandros, GameLivingEvent.WhisperReceive, TalkToJandros);

			/* Now we bring to Terod the possibility to give this quest to players */
			Terod?.AddQuestToGive(typeof (TheLostSeed));

			if (log.IsInfoEnabled)
				log.Info("Quest \"" + questTitle + "\" initialized");
		}

		[ScriptUnloadedEvent]
		public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
		{
			//if not loaded, don't worry
			if (Terod == null)
				return;

			// remove handlers
			treantArea.UnRegisterPlayerEnter(PlayerEnterTreantArea);
			WorldMgr.GetRegion(treantLocation.RegionID)?.RemoveArea(treantArea);

			GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.RemoveHandler(Terod, GameObjectEvent.Interact, TalkToTerod);
			GameEventMgr.RemoveHandler(Terod, GameLivingEvent.WhisperReceive, TalkToTerod);

			GameEventMgr.RemoveHandler(Kredril, GameObjectEvent.Interact, TalkToKredril);
			GameEventMgr.RemoveHandler(Kredril, GameLivingEvent.WhisperReceive, TalkToKredril);

			GameEventMgr.RemoveHandler(Emolia, GameObjectEvent.Interact, TalkToEmolia);
			GameEventMgr.RemoveHandler(Emolia, GameLivingEvent.WhisperReceive, TalkToEmolia);

			GameEventMgr.RemoveHandler(Jandros, GameObjectEvent.Interact, TalkToJandros);
			GameEventMgr.RemoveHandler(Jandros, GameLivingEvent.WhisperReceive, TalkToJandros);

			/* Now we remove to Terod the possibility to give this quest to players */
			Terod.RemoveQuestToGive(typeof (TheLostSeed));
		}

		protected virtual void CreateFeairnaAthar(GamePlayer player)
		{
			foreach (GameNPC npc in WorldMgr.GetNPCsCloseToSpot(181, 288348, 319950, 2328,8000))
			{
				if (npc.Brain is SINeckBossBrain)
					return;
			}
			Feairna_Athar = new SINeckBoss();
			Feairna_Athar.Model = 767;
			Feairna_Athar.Name = "Feairna-Athar";
			Feairna_Athar.GuildName = string.Empty;
			Feairna_Athar.Realm = eRealm.None;
			Feairna_Athar.Race = 2007;
			Feairna_Athar.BodyType = (ushort) NpcTemplateMgr.eBodyType.Plant;
			Feairna_Athar.CurrentRegionID = 181;
			Feairna_Athar.Size = 100;
			Feairna_Athar.Level = 65;
			Feairna_Athar.X = 288348;
			Feairna_Athar.Y = 319950;
			Feairna_Athar.Z = 2328;
			Feairna_Athar.MaxSpeedBase = 250;

			var brain = new SINeckBossBrain();
			brain.AggroLevel = 200;
			brain.AggroRange = 500;
			Feairna_Athar.SetOwnBrain(brain);
			Feairna_Athar.LoadedFromScript = true;
			Feairna_Athar.RespawnInterval = -1;

			Feairna_Athar.AddToWorld();

			Feairna_Athar.StartAttack(player);

			GameEventMgr.AddHandler(Feairna_Athar,GameLivingEvent.Dying, FaeiarnaAtharDying);
		}
		private void FaeiarnaAtharDying(DOLEvent e, object sender, EventArgs arguments)
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

			GameEventMgr.RemoveHandler(Feairna_Athar, GameLivingEvent.Dying, FaeiarnaAtharDying);
			Feairna_Athar.Delete();
		}
		private static void AdvanceAfterKill(GamePlayer player)
		{
			var quest = player.IsDoingQuest(typeof(TheLostSeed)) as TheLostSeed;
			if (quest is not {Step: 5}) return;
			if (!player.Inventory.IsSlotsFree(1, eInventorySlot.FirstBackpack, eInventorySlot.LastBackpack))
				player.Out.SendMessage(
					L(player, "Quest.Hibernia.TheLostSeed.NoRoomForJewel", glowing_red_jewel.Name),
					eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			GiveItem(player, glowing_red_jewel);
			quest.Step = 6;
		}
		private static void PlayerEnterTreantArea(DOLEvent e, object sender, EventArgs args)
		{
			var aargs = args as AreaEventArgs;
			var player = aargs?.GameObject as GamePlayer;

			if (player == null)
				return;

			var quest = player.IsDoingQuest(typeof(TheLostSeed)) as TheLostSeed;

			if (quest is not {Step: 5}) return;

			var existingCopy = WorldMgr.GetNPCsByName("Feairna-Athar", eRealm.None);

			if (existingCopy.Length > 0) return;

			//only try to spawn him once per trigger even if multiple people enter at the same time
			if (_spawnLock.TryEnter())
			{
				try
				{
					// player near demon
					SendSystemMessage(player, L(player, "Quest.Hibernia.TheLostSeed.LeavesRustle"));
					player.Out.SendMessage(L(player, "Quest.Hibernia.TheLostSeed.FeairnaAtharAmbush"), eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
					quest.CreateFeairnaAthar(player);
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

		protected static void TalkToTerod(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(Terod.CanGiveQuest(typeof (TheLostSeed), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			TheLostSeed quest = player.IsDoingQuest(typeof (TheLostSeed)) as TheLostSeed;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							Terod.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Terod.Step1"));
							break;
						case 2:
							Terod.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Terod.Step2"));
							break;
						case 3:
							Terod.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Terod.Step3", player.CharacterClass.Name));
							break;
						case 4:
							Terod.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Terod.Step4", player.Name));
							break;
						case 5:
							Terod.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Terod.Step5"));
							break;
						case 6:
							Terod.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Terod.Step6"));
							break;
						case 7:
							Terod.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Terod.Step7"));
							break;
					}
				}
				else
				{
					Terod.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Terod.Intro", player.Name));
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
							case "help us":
							case "도와줄":
							Terod.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Terod.HelpUs"));
							break;

							case "Lost Seed":
							case "잃어버린 씨앗":
							player.Out.SendQuestSubscribeCommand(Terod, QuestMgr.GetIDForQuestType(typeof(TheLostSeed)), L(player, "Quest.Hibernia.TheLostSeed.Subscribe"));
							break;
					}
				}
				else
				{
					switch (wArgs.Text)
					{
							case "treant":
							case "트리언트":
							if (quest.Step == 1)
							{
								Terod.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Terod.Treant"));
								quest.Step = 2;
							}
							break;
							case "reward":
							case "보상":
							if (quest.Step == 7)
							{
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
				{

				}
			}
		}

		protected static void TalkToKredril(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(Terod.CanGiveQuest(typeof (TheLostSeed), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			TheLostSeed quest = player.IsDoingQuest(typeof (TheLostSeed)) as TheLostSeed;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							Kredril.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Kredril.Step1"));
							break;
						case 2:
							Kredril.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Kredril.Step2", player.CharacterClass.Name));
							break;
						case 3:
							Kredril.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Kredril.Step3", player.Name));
							break;
						case 4:
							Kredril.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Kredril.Step4", player.Name));
							break;
						case 5:
							Kredril.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Kredril.Step5"));
							break;
						case 6:
							Kredril.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Kredril.Step6"));
							break;
						case 7:
							Kredril.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Kredril.Step7", player.Name));
							break;
					}
				}
				else
				{
					Kredril.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Kredril.Intro", player.Name));
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
							case "the Lost Seed":
							case "잃어버린 씨앗":
							Kredril.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Kredril.TheLostSeed"));
							break;
						case "Jandros":
							if (quest.Step == 2)
							{
								Kredril.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Kredril.Jandros"));
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

		protected static void TalkToEmolia(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(Terod.CanGiveQuest(typeof (TheLostSeed), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			TheLostSeed quest = player.IsDoingQuest(typeof (TheLostSeed)) as TheLostSeed;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							break;
						case 2:
							break;
						case 3:
							Emolia.Say(L(player, "Quest.Hibernia.TheLostSeed.Emolia.Step3"));
							break;
						case 4:
							Emolia.Say(L(player, "Quest.Hibernia.TheLostSeed.Emolia.Step4"));
							break;
						case 5:
							Emolia.Say(L(player, "Quest.Hibernia.TheLostSeed.Emolia.Step5"));
							break;
						case 6:
							Emolia.Say(L(player, "Quest.Hibernia.TheLostSeed.Emolia.Step6"));
							break;
						case 7:
							Emolia.Say(L(player, "Quest.Hibernia.TheLostSeed.Emolia.Step7"));
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
						case "Aalid Feie":
							if (quest.Step == 3)
							{
								quest.Step = 4;
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

		protected static void TalkToJandros(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(Terod.CanGiveQuest(typeof (TheLostSeed), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			TheLostSeed quest = player.IsDoingQuest(typeof (TheLostSeed)) as TheLostSeed;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.Step1", player.CharacterClass.Name));
							break;
						case 2:
							Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.Step2", player.CharacterClass.Name));
							break;
						case 3:
							Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.Step3", player.Name));
							break;
						case 4:
							Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.Step4", player.Name));
							break;
						case 5:
							Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.Step5", player.Name));
							break;
						case 6:
							Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.Step6", player.Name));
							break;
						case 7:
							Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.Step7", player.Name));
							break;
					}
				}
				else
				{
					Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.Intro", player.Name));
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
						case "Kredril":
							Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.Kredril"));
							break;
							case "the Lost Seed":
							case "잃어버린 씨앗":
							Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.TheLostSeed"));
							break;
							case "died":
							case "죽었습니다":
							Jandros.Emote(eEmote.Cry);
							Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.Died"));
							break;
						case "Feairna-Athar":
							if (quest.Step == 4)
							{
								Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.FeairnaAthar"));
								quest.Step = 5;
							}
							break;
							case "the Jewel":
							case "보석":
							if (quest.Step == 6)
							{
								RemoveItem(player, glowing_red_jewel);
								Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.ReturnToTerod"));
								quest.Step = 7;
							}
							break;
					}
				}
			}
			else if (e == GameLivingEvent.ReceiveItem)
			{
				ReceiveItemEventArgs rArgs = (ReceiveItemEventArgs) args;
				if (quest != null)
					if (rArgs.Item.Id_nb == glowing_red_jewel.Id_nb)
					{
						if (quest.Step == 6)
						{
							Jandros.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Jandros.ReceiveJewel", player.Name));
							Jandros.Emote(eEmote.Smile);
							quest.Step = 7;
						}
					}
			}
		}

		public override bool CheckQuestQualification(GamePlayer player)
		{
			// if the player is already doing the quest his level is no longer of relevance
			if (player.IsDoingQuest(typeof (TheLostSeed)) != null)
				return true;

			if (player.Level < minimumLevel || player.Level > maximumLevel)
				return false;

			return true;
		}

		private static void CheckPlayerAbortQuest(GamePlayer player, byte response)
		{
			TheLostSeed quest = player.IsDoingQuest(typeof (TheLostSeed)) as TheLostSeed;

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

			if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(TheLostSeed)))
				return;

			if (e == GamePlayerEvent.AcceptQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x01);
			else if (e == GamePlayerEvent.DeclineQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x00);
		}

		private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
		{
			if(Terod.CanGiveQuest(typeof (TheLostSeed), player)  <= 0)
				return;

			if (player.IsDoingQuest(typeof (TheLostSeed)) != null)
				return;

			if (response == 0x00)
			{
				Terod.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.ComeBackIfChangedMind"));
			}
			else
			{
				//Check if we can add the quest!
				if (!Terod.GiveQuest(typeof (TheLostSeed), player, 1))
					return;
			}
			Terod.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Terod.Accepted"));
			Terod.SayTo(player, L(player, "Quest.Hibernia.TheLostSeed.Terod.Step1"));
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
						return Q("Quest.Hibernia.TheLostSeed.Description.Step1");
					case 2:
						return Q("Quest.Hibernia.TheLostSeed.Description.Step2");
					case 3:
						return Q("Quest.Hibernia.TheLostSeed.Description.Step3");
					case 4:
						return Q("Quest.Hibernia.TheLostSeed.Description.Step4");
					case 5:
						return Q("Quest.Hibernia.TheLostSeed.Description.Step5");
					case 6:
						return Q("Quest.Hibernia.TheLostSeed.Description.Step6");
					case 7:
						return Q("Quest.Hibernia.TheLostSeed.Description.Step7");
				}
				return base.Description;
			}
		}
		public override void AbortQuest()
		{
			base.AbortQuest(); //Defined in Quest, changes the state, stores in DB etc ...
			RemoveItem(m_questPlayer, glowing_red_jewel);
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
				RemoveItem(m_questPlayer, glowing_red_jewel);
				GiveItem(m_questPlayer, paidrean_necklace);
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
