/*
*Author         : Kelt
*Editor         : Kelt, Clait
*Source         : Custom
*Date           : 20 December 2021
*Quest Name     : [Memorial] All in the gold
*Quest Classes  : all
*Quest Version  : v1.0
*
*Changes:
*
*/

using System;
using System.Collections.Generic;
using System.Reflection;
using DOL.Database;
using DOL.Events;
using DOL.GS.PacketHandler;
using DOL.GS.PlayerTitles;

namespace DOL.GS.Quests.Albion
{
	public class HelpSirLukas : BaseQuest
	{
		/// <summary>
		/// Defines a logger for this class.
		/// </summary>
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

		protected const string questTitle = "[Memorial] All in the Gold";
		protected const int minimumLevel = 1;
		protected const int maximumLevel = 50;

		private static GameNPC SirLukas = null; // Start NPC
		private static GameNPC Lukas = null; // Step 4 NPC
		private static GameMerchant EllynWeyland = null; // Step 1, speak and get questitem

		private static DbItemTemplate funeral_speech_scroll = null;
		private static DbItemTemplate FlitzitinaBow = null;

		private static DbWorldObject FlitzitinasGrave = null;

		private static IList<DbWorldObject> GetItems()
		{
			return GameServer.Database.SelectObjects<DbWorldObject>(DB.Column("Name").IsEqualTo("Flitzitina's Grave"));
		}

		// Constructors
		public HelpSirLukas() : base()
		{
		}

		public HelpSirLukas(GamePlayer questingPlayer) : base(questingPlayer)
		{
		}

		public HelpSirLukas(GamePlayer questingPlayer, int step) : base(questingPlayer, step)
		{
		}

		public HelpSirLukas(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest)
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


		[ScriptLoadedEvent]
		public static void ScriptLoaded(DOLEvent e, object sender, EventArgs args)
		{
			if (!ServerProperties.Properties.LOAD_QUESTS)
				return;


			#region defineNPCs

			GameNPC[] npcs = WorldMgr.GetNPCsByName("Sir Lukas", eRealm.Albion);

			if (npcs.Length > 0)
				foreach (GameNPC npc in npcs)
					if (npc.CurrentRegionID == 1 && npc.X == 505313 && npc.Y == 496252)
					{
						Lukas = npc;
						break;
					}

			if (Lukas == null)
			{
				if (log.IsWarnEnabled)
					log.Warn("Could not find Lukas , creating it ...");
				Lukas = new GameNPC();
				Lukas.Model = 33;
				Lukas.Name = "Sir Lukas";
				Lukas.GuildName = "Emissary of the King";
				Lukas.Realm = eRealm.Albion;
				Lukas.CurrentRegionID = 1;
				Lukas.LoadEquipmentTemplateFromDatabase("SirLukasVetusta");
				Lukas.Size = 50;
				Lukas.Level = 55;
				Lukas.X = 505313;
				Lukas.Y = 496252;
				Lukas.Z = 2432;
				Lukas.Heading = 820;
				Lukas.AddToWorld();
				if (SAVE_INTO_DATABASE)
				{
					Lukas.SaveIntoDatabase();
				}
			}

			npcs = WorldMgr.GetNPCsByName("Sir Lukas", eRealm.Albion);

			if (npcs.Length > 0)
				foreach (GameNPC npc in npcs)
					if (npc.CurrentRegionID == 10 && npc.X == 30763 && npc.Y == 29908)
					{
						SirLukas = npc;
						break;
					}

			if (SirLukas == null)
			{
				if (log.IsWarnEnabled)
					log.Warn("Could not find SirLukas , creating it ...");
				SirLukas = new GameNPC();
				SirLukas.Model = 33;
				SirLukas.Name = "Sir Lukas";
				SirLukas.GuildName = "Emissary of the King";
				SirLukas.Realm = eRealm.Albion;
				SirLukas.CurrentRegionID = 10;
				SirLukas.LoadEquipmentTemplateFromDatabase("SirLukas");
				SirLukas.Size = 52;
				SirLukas.Level = 55;
				SirLukas.X = 30763;
				SirLukas.Y = 29908;
				SirLukas.Z = 8000;
				SirLukas.Heading = 3083;
				SirLukas.AddToWorld();
				if (SAVE_INTO_DATABASE)
				{
					SirLukas.SaveIntoDatabase();
				}
			}
			// end npc

			npcs = WorldMgr.GetNPCsByName("Ellyn Weyland", eRealm.Albion);

			if (npcs.Length > 0)
				foreach (GameNPC merchant in npcs)
					if (merchant.CurrentRegionID == 1 && merchant.X == 561409 && merchant.Y == 509960)
					{
						EllynWeyland = (GameMerchant)merchant;
						break;
					}

			if (EllynWeyland == null)
			{
				if (log.IsWarnEnabled)
					log.Warn("Could not find EllynWeyland , creating it ...");
				EllynWeyland = new GameMerchant();
				EllynWeyland.TradeItems = new MerchantTradeItems("00c1e711-8d1b-4b72-8012-932d940f2567");
				EllynWeyland.LoadEquipmentTemplateFromDatabase("AlbMerchantArmorStudded");
				EllynWeyland.Model = 38;
				EllynWeyland.Name = "Ellyn Weyland";
				EllynWeyland.GuildName = "Armor Merchant";
				EllynWeyland.Realm = eRealm.Albion;
				EllynWeyland.CurrentRegionID = 1;
				EllynWeyland.Size = 50;
				EllynWeyland.Level = 1;
				EllynWeyland.X = 561409;
				EllynWeyland.Y = 509960;
				EllynWeyland.Z = 2423;
				EllynWeyland.Heading = 115;
				EllynWeyland.Flags ^= GameNPC.eFlags.PEACE;
				EllynWeyland.MaxSpeedBase = 200;
				EllynWeyland.AddToWorld();
				if (SAVE_INTO_DATABASE)
				{
					EllynWeyland.SaveIntoDatabase();
				}
			}
			// end npc

				#endregion

			#region defineItems

				funeral_speech_scroll = GameServer.Database.FindObjectByKey<DbItemTemplate>("funeral_speech_flitzitina");
			if (funeral_speech_scroll == null)
			{
				if (log.IsWarnEnabled)
					log.Warn("Could not find Funeral Speech for Flitzitina, creating it ...");
				funeral_speech_scroll = new DbItemTemplate();
				funeral_speech_scroll.Id_nb = "funeral_speech_flitzitina";
				funeral_speech_scroll.Name = "Funeral Speech for Flitzitina";
				funeral_speech_scroll.Level = 5;
				funeral_speech_scroll.Item_Type = 0;
				funeral_speech_scroll.Model = 498;
				funeral_speech_scroll.IsDropable = false;
				funeral_speech_scroll.IsTradable = false;
				funeral_speech_scroll.IsIndestructible = false;
				funeral_speech_scroll.IsPickable = false;
				funeral_speech_scroll.DPS_AF = 0;
				funeral_speech_scroll.SPD_ABS = 0;
				funeral_speech_scroll.Object_Type = 0;
				funeral_speech_scroll.Hand = 0;
				funeral_speech_scroll.Type_Damage = 0;
				funeral_speech_scroll.Quality = 100;
				funeral_speech_scroll.Weight = 1;
				funeral_speech_scroll.Description = string.Empty;
				if (SAVE_INTO_DATABASE)
				{
					GameServer.Database.AddObject(funeral_speech_scroll);
				}

			}

			FlitzitinaBow = GameServer.Database.FindObjectByKey<DbItemTemplate>("FlitzitinaBow");
			if (FlitzitinaBow == null)
			{
				if (log.IsWarnEnabled)
					log.Warn("Could not find Flitzitina Bow , creating it ...");
				FlitzitinaBow = new DbItemTemplate();
				FlitzitinaBow.Id_nb = "FlitzitinaBow";
				FlitzitinaBow.Name = "Flitzitina\'s Bow";
				FlitzitinaBow.Level = 50;
				FlitzitinaBow.Item_Type = 40;
				FlitzitinaBow.Model = 3275;
				FlitzitinaBow.IsDropable = true;
				FlitzitinaBow.IsPickable = true;
				FlitzitinaBow.DPS_AF = 50;
				FlitzitinaBow.SPD_ABS = 0;
				FlitzitinaBow.Object_Type = 9;
				FlitzitinaBow.Quality = 100;
				FlitzitinaBow.Weight = 10;
				FlitzitinaBow.Bonus = 35;
				FlitzitinaBow.MaxCondition = 50000;
				FlitzitinaBow.MaxDurability = 50000;
				FlitzitinaBow.Condition = 50000;
				FlitzitinaBow.Durability = 50000;
				if (SAVE_INTO_DATABASE)
				{
					GameServer.Database.AddObject(FlitzitinaBow);
				}

			} //end item

			//Item Descriptions End

			#endregion

			#region defineObject

			var graveCheck = GetItems();
			if (graveCheck.Count == 0)
			{
				if (log.IsWarnEnabled)
					log.Warn("Could not find Flitzitinas Grave, creating it ...");
				var FlitzitinasGrave = new DbWorldObject();
				FlitzitinasGrave.Name = "Flitzitina\'s Grave";
				FlitzitinasGrave.X = 505153;
				FlitzitinasGrave.Y = 496310;
				FlitzitinasGrave.Z = 2432;
				FlitzitinasGrave.Heading = 833;
				FlitzitinasGrave.Region = 1;
				FlitzitinasGrave.Model = 145;
				FlitzitinasGrave.ObjectId = "flitzitina_grave_questitem";
				if (SAVE_INTO_DATABASE)
				{
					GameServer.Database.AddObject(FlitzitinasGrave);
					HelpSirLukas.FlitzitinasGrave = FlitzitinasGrave;
				}

			}

			#endregion

			GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.AddHandler(SirLukas, GameObjectEvent.Interact, new DOLEventHandler(TalkToSirLukas));
			GameEventMgr.AddHandler(SirLukas, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToSirLukas));

			GameEventMgr.AddHandler(EllynWeyland, GameObjectEvent.Interact, new DOLEventHandler(TalkToEllynWeyland));
			GameEventMgr.AddHandler(EllynWeyland, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToEllynWeyland));

			/* Now we bring to Sir Lukas the possibility to give this quest to players */
			SirLukas.AddQuestToGive(typeof (HelpSirLukas));

			if (log.IsInfoEnabled)
				log.Info("Quest \"" + questTitle + "\" initialized");
		}

		[ScriptUnloadedEvent]
		public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
		{
			//if not loaded, don't worry
			if (SirLukas == null)
				return;
			// remove handlers
			GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.RemoveHandler(SirLukas, GameObjectEvent.Interact, new DOLEventHandler(TalkToSirLukas));
			GameEventMgr.RemoveHandler(SirLukas, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToSirLukas));

			GameEventMgr.RemoveHandler(EllynWeyland, GameObjectEvent.Interact, new DOLEventHandler(TalkToEllynWeyland));
			GameEventMgr.RemoveHandler(EllynWeyland, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToEllynWeyland));

			/* Now we remove to Sir Lukas the possibility to give this quest to players */
			SirLukas.RemoveQuestToGive(typeof (HelpSirLukas));
		}

		protected static void TalkToSirLukas(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(SirLukas.CanGiveQuest(typeof (HelpSirLukas), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			HelpSirLukas quest = player.IsDoingQuest(typeof (HelpSirLukas)) as HelpSirLukas;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							SirLukas.SayTo(player, L(player, "Quest.HelpSirLukas.SirLukas.Step1"));
							break;
						case 2:
							SirLukas.SayTo(player, L(player, "Quest.HelpSirLukas.SirLukas.Step2", player.Name));
							break;
						case 3:
							SirLukas.Emote(eEmote.No);
							SirLukas.SayTo(player, L(player, "Quest.HelpSirLukas.SirLukas.Step3", player.Name));
							break;
						case 4:
							SirLukas.SayTo(player, L(player, "Quest.HelpSirLukas.SirLukas.Step4", player.Name));
							break;
					}
				}
				else
				{
					SirLukas.SayTo(player, L(player, "Quest.HelpSirLukas.SirLukas.Greeting", player.Name, player.CharacterClass.Name));
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
							case "support Camelot":
							case "카멜롯 지원":
							player.Out.SendQuestSubscribeCommand(SirLukas, QuestMgr.GetIDForQuestType(typeof(HelpSirLukas)), L(player, "Quest.HelpSirLukas.SubscribePrompt"));
							break;
					}
				}
				else
				{
					switch (wArgs.Text)
					{
							case "this speech":
							case "장례 연설문":
							SirLukas.SayTo(player, L(player, "Quest.HelpSirLukas.SirLukas.ThisSpeech", player.Name));
							break;
							case "the grave":
							case "무덤":
							SirLukas.SayTo(player, L(player, "Quest.HelpSirLukas.SirLukas.TheGrave"));
							break;
							case "Vetusta Abbey":
							case "베투스타 수도원":


							if (quest.Step == 3)
							{
								SirLukas.SayTo(player, L(player, "Quest.HelpSirLukas.SirLukas.VetustaAbbey"));
								GiveItem(player, funeral_speech_scroll);
								quest.Step = 4;
							}
							break;
							case "delivery":
							case "전달품":
							SirLukas.SayTo(player, L(player, "Quest.HelpSirLukas.SirLukas.Delivery"));
							RemoveItem(player, FlitzitinaBow);
							quest.Step = 3;
							SirLukas.Interact(player);
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
					if (rArgs.Item.Id_nb == FlitzitinaBow.Id_nb)
					{
						SirLukas.SayTo(player, L(player, "Quest.HelpSirLukas.SirLukas.ReceiveBow", player.Name));
						//quest.Step = 3;
					}
				}
			}
		}

		protected static void TalkToEllynWeyland(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			//We also check if the player is already doing the quest
			HelpSirLukas quest = player.IsDoingQuest(typeof (HelpSirLukas)) as HelpSirLukas;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							EllynWeyland.SayTo(player, L(player, "Quest.HelpSirLukas.Ellyn.Step1", player.Name));
							break;
						case 2:
							EllynWeyland.SayTo(player, L(player, "Quest.HelpSirLukas.Ellyn.Step2", player.Name));
							break;
						case 3:
							EllynWeyland.SayTo(player, L(player, "Quest.HelpSirLukas.Ellyn.Step3"));
							break;
						case 4:
							EllynWeyland.SayTo(player, L(player, "Quest.HelpSirLukas.Ellyn.Step4"));
							break;
					}
				}
				else
				{
					EllynWeyland.SayTo(player, L(player, "Quest.HelpSirLukas.Ellyn.Greeting"));
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
						case "her bow":
						case "그녀의 활":
							if (quest.Step == 1)
							{
								EllynWeyland.SayTo(player, L(player, "Quest.HelpSirLukas.Ellyn.HerBow"));
								quest.Step = 2;
								GiveItem(player, FlitzitinaBow);
							}
							break;
					}
				}
			}
		}

		protected static void TalkToLukas(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			//We also check if the player is already doing the quest
			HelpSirLukas quest = player.IsDoingQuest(typeof (HelpSirLukas)) as HelpSirLukas;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 4:
							Lukas.SayTo(player, L(player, "Quest.HelpSirLukas.Lukas.Step4", player.Name));
							break;
					}
				}
				else
				{
					Lukas.SayTo(player, L(player, "Quest.HelpSirLukas.Lukas.Greeting", player.Name));
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
						case "visit me":
						case "나를 찾아오기":
							Lukas.SayTo(player, L(player, "Quest.HelpSirLukas.Lukas.VisitMe"));
							break;
					}
				}
				else
				{

				}
			}
		}

		public override bool CheckQuestQualification(GamePlayer player)
		{
			// if the player is already doing the quest his level is no longer of relevance
			if (player.IsDoingQuest(typeof (HelpSirLukas)) != null)
				return true;

			// This checks below are only performed is player isn't doing quest already

			//if (player.HasFinishedQuest(typeof(Academy_47)) == 0) return false;

			//if (!CheckPartAccessible(player,typeof(CityOfCamelot)))
			//	return false;

			if (player.Level < minimumLevel || player.Level > maximumLevel)
				return false;

			return true;
		}

		private static void CheckPlayerAbortQuest(GamePlayer player, byte response)
		{
			HelpSirLukas quest = player.IsDoingQuest(typeof (HelpSirLukas)) as HelpSirLukas;

			if (quest == null)
				return;

			if (response == 0x00)
			{
				SendSystemMessage(player, L(player, "Quest.Common.AbortCancelled"));
			}
			else
			{
				SendSystemMessage(player, L(player, "Quest.Common.AbortingQuestRestart", questTitle));
				quest.AbortQuest();
			}
		}

		protected static void SubscribeQuest(DOLEvent e, object sender, EventArgs args)
		{
			QuestEventArgs qargs = args as QuestEventArgs;
			if (qargs == null)
				return;

			if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(HelpSirLukas)))
				return;

			if (e == GamePlayerEvent.AcceptQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x01);
			else if (e == GamePlayerEvent.DeclineQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x00);
		}

		private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
		{
			if(SirLukas.CanGiveQuest(typeof (HelpSirLukas), player)  <= 0)
				return;

			if (player.IsDoingQuest(typeof (HelpSirLukas)) != null)
				return;

			if (response == 0x00)
			{
				player.Out.SendMessage(L(player, "Quest.HelpSirLukas.Decline"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
			}
			else
			{
				//Check if we can add the quest!
				if (!SirLukas.GiveQuest(typeof (HelpSirLukas), player, 1))
					return;

				SirLukas.SayTo(player, L(player, "Quest.HelpSirLukas.SirLukas.Step1"));

			}
		}

		//Set quest name
		public override string Name
		{
			get { return Q("Quest.HelpSirLukas.Name"); }
		}

		// Define Steps
		public override string Description
		{
			get
			{
				switch (Step)
				{
					case 1:
						return Q("Quest.HelpSirLukas.Description.Step1");
					case 2:
						return Q("Quest.HelpSirLukas.Description.Step2");
					case 3:
						return Q("Quest.HelpSirLukas.Description.Step3");
					case 4:
						return Q("Quest.HelpSirLukas.Description.Step4");
					case 5:
						return Q("Quest.HelpSirLukas.Description.Step5");
				}
				return base.Description;
			}
		}

		public override void Notify(DOLEvent e, object sender, EventArgs args)
		{
			GamePlayer player = sender as GamePlayer;

			if (player==null || player.IsDoingQuest(typeof (HelpSirLukas)) == null)
				return;

			if (Step == 1 && e == GameLivingEvent.Interact)
			{
				InteractEventArgs gArgs = (InteractEventArgs) args;
				if (gArgs.Source.Name == EllynWeyland.Name)
				{
					EllynWeyland.SayTo(player, L(player, "Quest.HelpSirLukas.Ellyn.Step1", player.Name));

					GiveItem(m_questPlayer, FlitzitinaBow);
					Step = 2;
					return;
				}
			}

			if (Step == 2 && e == GamePlayerEvent.ReceiveItem || Step == 3 && e == GameLivingEvent.Interact)
			{
				/*
				InteractEventArgs gArgs = (InteractEventArgs) args;
				if (gArgs.Source.Name == SirLukas.Name)
				{*/

				SirLukas.SayTo(player, L(player, "Quest.HelpSirLukas.SirLukas.PrepareFuneral"));
				Step = 4;
				GiveItem(m_questPlayer, funeral_speech_scroll);
				//}
			}

			if (Step == 4 && e == GameObjectEvent.InteractWith)
			{
				InteractWithEventArgs gArgs = (InteractWithEventArgs) args;
				if (gArgs.Target.Name.Equals("Flitzitina\'s Grave"))
				{
					RemoveItem(player, funeral_speech_scroll);
					Step = 5;
					FinishQuest();
				}
			}

		}
		public class HelpSirLukasTitle : EventPlayerTitle
    {
        /// <summary>
        /// The title description, shown in "Titles" window.
        /// </summary>
        /// <param name="player">The title owner.</param>
        /// <returns>The title description.</returns>
        public override string GetDescription(GamePlayer player)
        {
            return L(player, "Quest.HelpSirLukas.Title");
        }

        /// <summary>
        /// The title value, shown over player's head.
        /// </summary>
        /// <param name="source">The player looking.</param>
        /// <param name="player">The title owner.</param>
        /// <returns>The title value.</returns>
        public override string GetValue(GamePlayer source, GamePlayer player)
        {
            return L(source ?? player, "Quest.HelpSirLukas.Title");
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
	        return player.HasFinishedQuest(typeof(HelpSirLukas)) == 1;
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
			RemoveItem(m_questPlayer, FlitzitinaBow, false);
			RemoveItem(m_questPlayer, funeral_speech_scroll, false);
		}

		public override void FinishQuest()
		{
			Lukas.SayTo(m_questPlayer, L(m_questPlayer, "Quest.HelpSirLukas.Finish", m_questPlayer.Name));
			Lukas.TurnTo(m_questPlayer);
			Lukas.Emote(eEmote.Curtsey);
			Lukas.TurnTo(Lukas.SpawnHeading);

			m_questPlayer.GainExperience(eXPSource.Quest, 20, false);
			m_questPlayer.AddMoney(Money.GetMoney(0,0,1,32,Util.Random(50)), L(m_questPlayer, "Quest.Common.MoneyReward"));

			base.FinishQuest(); //Defined in Quest, changes the state, stores in DB etc ...

		}
	}
}
