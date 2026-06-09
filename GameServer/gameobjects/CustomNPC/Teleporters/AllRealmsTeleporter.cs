using System;
using System.Collections.Generic;
using System.Text;
using DOL.Database;
using DOL.GS.Housing;
using DOL.GS.Keeps;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS
{
	/// <summary>
	/// Albion teleporter.
	/// </summary>
	/// <author>Aredhel</author>
	public class AllRealmsTeleporter : GameTeleporter
	{
		private static new readonly Logging.Logger log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

		/// <summary>
		/// Display teleport destinations for passed realm
		/// </summary>
		/// <param name="destRealm">Realm to display destinations for</param>
		public String DisplayTeleportDestinations(eRealm destRealm, string language)
		{
			switch (destRealm)
			{
				case eRealm.Albion:
					return LanguageMgr.GetTranslation(language, "AllRealmsTeleporter.Menu.Albion");
				case eRealm.Midgard:
					return LanguageMgr.GetTranslation(language, "AllRealmsTeleporter.Menu.Midgard");
				case eRealm.Hibernia:
					return LanguageMgr.GetTranslation(language, "AllRealmsTeleporter.Menu.Hibernia");
				default:
					log.Warn(String.Format("DisplayTeleportDestinations does not handle player realm [{0}]", destRealm.ToString()));
					break;
			}

			return string.Empty;
		}

		/// <summary>
		/// Player right-clicked the teleporter.
		/// </summary>
		/// <param name="player"></param>
		/// <returns></returns>
		public override bool Interact(GamePlayer player)
		{
			String intro = DisplayTeleportDestinations(player.Realm, player.Client.Account.Language);
			if (intro != null)
				SayTo(player, intro);

			if (!base.Interact(player))
				return false;

			return true;
		}

		/// <summary>
		/// Talk to the teleporter.
		/// </summary>
		/// <param name="source"></param>
		/// <param name="text"></param>
		/// <returns></returns>
		public override bool WhisperReceive(GameLiving source, string text)
		{
			GamePlayer player = source as GamePlayer;
			if (player == null)
				return false;

			eRealm realmTarget = player.Realm;

			StringBuilder sRet = new StringBuilder();
				text = text switch
				{
					"알비온" => "Albion",
					"미드가드" => "Midgard",
					"미드가르드" => "Midgard",
					"하이버니아" => "Hibernia",
					"알비온 프론티어" => "Albion Frontiers",
					"미드가드 프론티어" => "Midgard Frontiers",
					"미드가르드 프론티어" => "Midgard Frontiers",
					"하이버니아 프론티어" => "Hibernia Frontiers",
					"알비온 아그라몬" => "Albion Agramon",
					"미드가드 아그라몬" => "Midgard Agramon",
					"미드가르드 아그라몬" => "Midgard Agramon",
					"하이버니아 아그라몬" => "Hibernia Agramon",
					"전장" => "Battlegrounds",
					"알비온 다크니스 폴스" => "Albion Darkness Falls",
					"미드가드 다크니스 폴스" => "Midgard Darkness Falls",
					"미드가르드 다크니스 폴스" => "Midgard Darkness Falls",
					"하이버니아 다크니스 폴스" => "Hibernia Darkness Falls",
					"알비온 본토" => "Albion Mainland",
					"미드가드 본토" => "Midgard Mainland",
					"미드가르드 본토" => "Midgard Mainland",
					"하이버니아 본토" => "Hibernia Mainland",
					"알비온 던전" => "Albion Dungeons",
					"미드가드 던전" => "Midgard Dungeons",
					"미드가르드 던전" => "Midgard Dungeons",
					"하이버니아 던전" => "Hibernia Dungeons",
					"알비온 슈라우디드 아일스" => "Albion Shrouded Isles",
					"미드가드 슈라우디드 아일스" => "Midgard Shrouded Isles",
					"미드가르드 슈라우디드 아일스" => "Midgard Shrouded Isles",
					"하이버니아 슈라우디드 아일스" => "Hibernia Shrouded Isles",
					"알비온 오세아누스" => "Albion Oceanus",
					"미드가드 오세아누스" => "Midgard Oceanus",
					"미드가르드 오세아누스" => "Midgard Oceanus",
					"하이버니아 오세아누스" => "Hibernia Oceanus",
						"주택" => "Housing",
						"입구" => "Entrance",
					"개인 주택" => "Personal",
					"길드 주택" => "Guild",
					"귀환 위치" => "Hearth",
					"카멜롯" => "Camelot",
					"요르드하임" => "Jordheim",
					"티르 나 노그" => "Tir na Nog",
					"소바쥬 숲" => "Forest Sauvage",
					"소바쥬 성" => "Castle Sauvage",
					"스노도니아 요새" => "Snowdonia Fortress",
					"업플란드" => "Uppland",
					"스바수드 파스테" => "Svasud Faste",
					"빈드사울 파스테" => "Vindsaul Faste",
					"크루아찬 협곡" => "Cruachan Gorge",
					"드루임 리겐" => "Druim Ligen",
					"드루임 케인" => "Druim Cain",
					"코츠월드 마을" => "Cotswold Village",
					"프리드웬 성채" => "Prydwen Keep",
					"케어 울프위치" => "Caer Ulfwych",
					"캄파코렌틴 기지" => "Campacorentin Station",
					"아드리바드 은거지" => "Adribard's Retreat",
					"콘월 기지" => "Cornwall Station",
					"스완턴 성채" => "Swanton Keep",
					"라이오네스" => "Lyonesse",
					"다트무어" => "Dartmoor",
					"인코뉴 납골당" => "Inconnu Crypt",
					"미트라 무덤" => "Tomb of Mithra",
					"켈토이 포구" => "Keltoi Fogou",
					"테폭 광산" => "Tepok's Mine",
					"카르도바 지하묘지" => "Catacombs of Cardova",
					"스톤헨지 고분" => "Stonehenge Barrows",
					"크론돈" => "Krondon",
					"아발론 시티" => "Avalon City",
					"케어 시디" => "Caer Sidi",
					"케어 고스웨이트" => "Caer Gothwaite",
					"위어리얼 마을" => "Wearyall Village",
					"귄텔 요새" => "Fort Gwyntell",
					"케어 디오겔" => "Caer Diogel",
					"물란" => "Mularn",
					"벨돈 요새" => "Fort Veldon",
					"아우들리텐" => "Audliten",
					"후긴펠" => "Huginfell",
					"아틀라 요새" => "Fort Atla",
					"그나 파스테" => "Gna Faste",
					"라우마리크" => "Raumarik",
					"말모후스" => "Malmohus",
					"코볼드 지하도시" => "Kobold Undercity",
					"니스의 소굴" => "Nisse's Lair",
					"저주받은 무덤" => "Cursed Tomb",
					"벤도 동굴" => "Vendo Caverns",
					"바룰브함" => "Varulvhamn",
					"스핀델할라" => "Spindelhalla",
					"이아른비디우르의 소굴" => "Iarnvidiur's Lair",
					"트롤하임" => "Trollheim",
					"투스카렌 빙하" => "Tuscaren Glacier",
					"에기르함" => "Aegirhamn",
					"비야르켄" => "Bjarken",
					"하갈" => "Hagall",
					"크나르" => "Knarr",
					"마그 멜" => "Mag Mell",
					"티르 나 므베오" => "Tir na mBeo",
					"아르다" => "Ardagh",
					"호스" => "Howth",
					"콘라" => "Connla",
					"이니스 카르사이그" => "Innis Carthaig",
					"저주받은 숲" => "Cursed Forest",
					"시어로 언덕" => "Sheeroe Hills",
					"샤르 미궁" => "Shar Labyrinth",
					"뮤어 무덤" => "Muire Tomb",
					"스프래곤 소굴" => "Spraggon Den",
					"코알린스 동굴" => "Koalinth Caverns",
					"트레이브 카일테" => "Treibh Caillte",
					"코러스케이팅 광산" => "Coruscating Mine",
					"투르 수일" => "Tur Suil",
					"포모르" => "Fomor",
					"갈라도리아" => "Galladoria",
					"돔난" => "Domnann",
					"드로하이드" => "Droighaid",
					"알리드 페이" => "Aalid Feie",
					"네흐트" => "Necht",
					_ => text
				};

			switch (text.ToUpper())
			{
				// Realm specific menus
				case "ALBION":
					SayTo(player, DisplayTeleportDestinations(eRealm.Albion, player.Client.Account.Language));
					return true;
				case "MIDGARD":
					SayTo(player, DisplayTeleportDestinations(eRealm.Midgard, player.Client.Account.Language));
					return true;
				case "HIBERNIA":
					SayTo(player, DisplayTeleportDestinations(eRealm.Hibernia, player.Client.Account.Language));
					return true;

				case "ALBION FRONTIERS":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.AlbionFrontiers"));
					return true;
				case "ALBION MAINLAND":
					sRet.Append(LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.AlbionMainland.Header"));
					if (!ServerProperties.Properties.DISABLE_TUTORIAL && player.Level <= 15)
						sRet.Append("[Holtham] (Levels 1-9)\n");
					sRet.Append(LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.AlbionMainland.Body"));
					SayTo(player, sRet.ToString());
					return true;
				case "ALBION DUNGEONS":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.AlbionDungeons"));
					return true;
				case "ALBION SHROUDED ISLES":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.AlbionShroudedIsles"));
					return true;

				case "MIDGARD FRONTIERS":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.MidgardFrontiers"));
					return true;
				case "MIDGARD MAINLAND":
					sRet.Append(LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.MidgardMainland.Header"));
					if (!ServerProperties.Properties.DISABLE_TUTORIAL && player.Level <= 15)
						sRet.Append("[Hafheim] (Levels 1-9)\n");
					sRet.Append(LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.MidgardMainland.Body"));
					SayTo(player, sRet.ToString());
					return true;
				case "MIDGARD DUNGEONS":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.MidgardDungeons"));
					return true;
				case "MIDGARD SHROUDED ISLES":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.MidgardShroudedIsles"));
					return true;

				case "HIBERNIA FRONTIERS":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.HiberniaFrontiers"));
					return true;
				case "HIBERNIA MAINLAND":
					sRet.Append(LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.HiberniaMainland.Header"));
					if (!ServerProperties.Properties.DISABLE_TUTORIAL && player.Level <= 15)
						sRet.Append("[Fintain] (Levels 1-9)\n");
					sRet.Append(LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.HiberniaMainland.Body"));
					SayTo(player, sRet.ToString());
					return true;
				case "HIBERNIA DUNGEONS":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.HiberniaDungeons"));
					return true;

				case "HIBERNIA SHROUDED ISLES":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.HiberniaShroudedIsles"));
					return true;

				case "HOUSING":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Menu.Housing"));
					return true;

				// DF locations
				case "ALBION DARKNESS FALLS":
					realmTarget = eRealm.Albion;
					text = "Darkness Falls";
					break;
				case "MIDGARD DARKNESS FALLS":
					realmTarget = eRealm.Midgard;
					text = "Darkness Falls";
					break;
				case "HIBERNIA DARKNESS FALLS":
					realmTarget = eRealm.Hibernia;
					text = "Darkness Falls";
					break;

				// Agramon
				case "ALBION AGRAMON":
					realmTarget = eRealm.Albion;
					text = "Agramon";
					break;
				case "MIDGARD AGRAMON":
					realmTarget = eRealm.Midgard;
					text = "Agramon";
					break;
				case "HIBERNIA AGRAMON":
					realmTarget = eRealm.Hibernia;
					text = "Agramon";
					break;

				// Albion destinations
				case "CAMELOT":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.GreatCityAwaits"));
					realmTarget = eRealm.Albion;
					break;
				case "ALBION OCEANUS":
					if (player.Client.Account.PrivLevel < ServerProperties.Properties.ATLANTIS_TELEPORT_PLVL)
					{
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.AtlantisUnauthorized"));
						return true;
					}
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.OceanusArrival"));
					realmTarget = eRealm.Albion;
					text = "Oceanus";
					break;
				// SI cities
				case "GOTHWAITE":
				case "DIOGEL":
				case "GWYNTELL":
				case "WEARYALL":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.ShroudedIslesAwait"));
					realmTarget = eRealm.Albion;
					break;
				// Mainland destinations
				case "COTSWOLD VILLAGE":
				case "PRYDWEN KEEP":
				case "CAER ULFWYCH":
				case "CAMPACORENTIN STATION":
				case "ADRIBARD'S RETREAT":
				case "CORNWALL STATION":
				case "SWANTON KEEP":
				case "LYONESSE":
				case "DARTMOOR":
				case "AVALON MARSH":
				// Dungeon destinations
				case "TOMB OF MITHRA":
				case "KELTOI FOGOU":
				case "TEPOK'S MINE":
				case "CATACOMBS OF CARDOVA":
				case "STONEHENGE BARROWS":
				case "KRONDON":
				case "AVALON CITY":
				case "CAER SIDI":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.ArriveIn", text));
					realmTarget = eRealm.Albion;
					break;
				case "FOREST SAUVAGE":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.ToFrontiers"));
					realmTarget = eRealm.Albion;
					break;
				case "CASTLE SAUVAGE":
				case "SNOWDONIA FORTRESS":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.SeekAndFind", text));
					realmTarget = eRealm.Albion;
					break;
				case "INCONNU CRYPT":
					//if (player.HasFinishedQuest(typeof(InconnuCrypt)) <= 0)
					//{
					//	SayTo(player, String.Format("I may only send those who know the way to this {0} {1}",
					//	                            "city. Seek out the path to the city and in future times I will aid you in",
					//	                            "this journey."));
					//	return;
					//}
					realmTarget = eRealm.Albion;
					break;
				case "HOLTHAM":
					if (ServerProperties.Properties.DISABLE_TUTORIAL)
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.PlaceUnavailableNow"));
					else if (player.Level > 15)
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.TooExperienced"));
					else
					{
						realmTarget = eRealm.Albion;
						break;
					}
					return true;

				// Midgard
				case "JORDHEIM":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.GreatCityAwaits"));
					realmTarget = eRealm.Midgard;
					break;
				case "MIDGARD OCEANUS":
					if (player.Client.Account.PrivLevel < ServerProperties.Properties.ATLANTIS_TELEPORT_PLVL)
					{
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.AtlantisUnauthorized"));
						return true;
					}
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.OceanusArrival"));
					realmTarget = eRealm.Midgard;
					text = "Oceanus";
					break;
				// SI cities
				case "AEGIRHAMN":
				case "BJARKEN":
				case "HAGALL":
				case "KNARR":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.ShroudedIslesAwait"));
					realmTarget = eRealm.Midgard;
					break;
				// Mainland destinations
				case "MULARN":
				case "FORT VELDON":
				case "AUDLITEN":
				case "HUGINFELL":
				case "FORT ATLA":
				case "GNA FASTE":
				case "RAUMARIK":
				case "MALMOHUS":
				case "GOTAR":
				// Dungeon destinations
				case "NISSE'S LAIR":
				case "CURSED TOMB":
				case "VENDO CAVERNS":
				case "VARULVHAMN":
				case "SPINDELHALLA":
				case "IARNVIDIUR'S LAIR":
				case "TROLLHEIM":
				case "TUSCAREN GLACIER":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.ArriveIn", text));
					realmTarget = eRealm.Midgard;
					break;
				case "KOBOLD UNDERCITY":
					//if (player.HasFinishedQuest(typeof(KoboldUndercity)) <= 0)
					//{
					//	SayTo(player, String.Format("I may only send those who know the way to this {0} {1}",
					//	                            "city. Seek out the path to the city and in future times I will aid you in",
					//	                            "this journey."));
					//	return;
					//}
					realmTarget = eRealm.Midgard;
					break;
				case "UPPLAND":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.ToFrontiers"));
					realmTarget = eRealm.Midgard;
					break;
				case "SVASUD FASTE":
				case "VINDSAUL FASTE":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.SeekAndFind", text));
					realmTarget = eRealm.Midgard;
					break;
				case "HAFHEIM":
					if (ServerProperties.Properties.DISABLE_TUTORIAL)
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.PlaceUnavailableNow"));
					else if (player.Level > 15)
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.TooExperienced"));
					else
					{
						realmTarget = eRealm.Midgard;
						break;
					}
					return true;

				// Hibernia
				case "TIR NA NOG":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.GreatCityAwaits"));
					realmTarget = eRealm.Hibernia;
					break;
				case "HIBERNIA OCEANUS":
					if (player.Client.Account.PrivLevel < ServerProperties.Properties.ATLANTIS_TELEPORT_PLVL)
					{
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.AtlantisUnauthorized"));
						return true;
					}
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.OceanusArrival"));
					realmTarget = eRealm.Hibernia;
					text = "Oceanus";
					break;
				// SI locations
				case "DOMNANN":
				case "NECHT":
				case "AALID FEIE":
				case "DROIGHAID":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.ShroudedIslesAwait"));
					realmTarget = eRealm.Hibernia;
					break;
				// Mainland locations
				case "MAG MELL":
				case "TIR NA MBEO":
				case "ARDAGH":
				case "HOWTH":
				case "CONNLA":
				case "INNIS CARTHAIG":
				case "CURSED FOREST":
				case "SHEEROE HILLS":
				case "SHANNON ESTUARY":
				// Dungeon destinations
				case "MUIRE TOMB":
				case "SPRAGGON DEN":
				case "KOALINTH CAVERNS":
				case "TREIBH CAILLTE":
				case "CORUSCATING MINE":
				case "TUR SUIL":
				case "FOMOR":
				case "GALLADORIA":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.ArriveIn", text));
					realmTarget = eRealm.Hibernia;
					break;
				case "CRUACHAN GORGE":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.ToFrontiers"));
					realmTarget = eRealm.Hibernia;
					break;
				case "DRUIM CAIN":
				case "DRUIM LIGEN":
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.SeekAndFind", text));
					realmTarget = eRealm.Hibernia;
					break;
				case "SHAR LABYRINTH":
					//if (player.HasFinishedQuest(typeof(SharLabyrinth)) <= 0)
					//{
					//	SayTo(player, String.Format("I may only send those who know the way to this {0} {1}",
					//	                            "city. Seek out the path to the city and in future times I will aid you in",
					//	                            "this journey."));
					//	return;
					//}
					realmTarget = eRealm.Hibernia;
					break;
				case "FINTAIN":
					if (ServerProperties.Properties.DISABLE_TUTORIAL)
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.PlaceUnavailableNow"));
					else if (player.Level > 15)
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.TooExperienced"));
					else
					{
						text = "Fintain";
						realmTarget = eRealm.Hibernia;
						break;
					}
					return true;
				// All realms
				case "BATTLEGROUNDS":
					if (!ServerProperties.Properties.BG_ZONES_OPENED && player.Client.Account.PrivLevel == (uint)ePrivLevel.Player)
					{
						SayTo(player, ServerProperties.Properties.BG_ZONES_CLOSED_MESSAGE);
						return true;
					}

					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.BattlegroundInfo"));
					break;
				case "ENTRANCE":
				case "PERSONAL":
				case "GUILD":
				case "HEARTH":
					realmTarget = player.Realm;
					break;
				default:
					return base.WhisperReceive(source, text);
			} // switch (text.ToLower())

			// Find the teleport location in the database.
			DbTeleport port = GetTeleportLocation(player, text, realmTarget);
			if (port == null)
			{
				SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Response.UnsupportedDestination"));
			}
			else if (IsDestinationAvailable(player, port))
			{
				OnTeleportSpell(player, port);
			}

			return true;
		}

		private static bool IsDestinationAvailable(GamePlayer player, DbTeleport destination)
		{
			Region region = WorldMgr.GetRegion((ushort)destination.RegionID);

			if (region != null && !region.IsDisabled)
				return true;

			player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client, "GameTeleporter.DestinationUnavailable"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
			return false;
		}

		protected DbTeleport GetTeleportLocation(GamePlayer player, string text, eRealm realm)
		{
			text = text switch
			{
				"주택" => "housing",
				"입구" => "entrance",
				"개인 주택" => "personal",
				"길드 주택" => "guild",
				"귀환 위치" => "hearth",
				_ => text
			};

			// Battlegrounds are specials, as the teleport location depends on
			// the level of the player, so let's deal with that first.
			if (text.ToLower() == "battlegrounds")
			{
				if (!ServerProperties.Properties.BG_ZONES_OPENED && player.Client.Account.PrivLevel == (uint)ePrivLevel.Player)
				{
					SayTo(player, ServerProperties.Properties.BG_ZONES_CLOSED_MESSAGE);
				}
				else
				{
					AbstractGameKeep portalKeep = GameServer.KeepManager.GetBGPK(player);
					if (portalKeep != null)
					{
						DbTeleport teleport = new DbTeleport();
						teleport.TeleportID = "battlegrounds";
						teleport.Realm = (byte)portalKeep.Realm;
						teleport.RegionID = portalKeep.Region;
						teleport.X = portalKeep.X;
						teleport.Y = portalKeep.Y;
						teleport.Z = portalKeep.Z;
						teleport.Heading = 0;
						return teleport;
					}
					else
					{
						if (player.Client.Account.PrivLevel > (uint)ePrivLevel.Player)
						{
							player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "GameTeleporter.NoPortalKeepFound"), eChatType.CT_Items, eChatLoc.CL_SystemWindow);
						}
						return null;
					}
				}
			}

			// Another special case is personal house, as there is no location
			// that will work for every player.
			if (text.ToLower() == "personal")
			{
				House house = HouseMgr.GetHouseByPlayer(player);

				if (house == null)
				{
					text = "entrance";  // Fall through, port to housing entrance.
				}
				else
				{
					IGameLocation location = house.OutdoorJumpPoint;
					DbTeleport teleport = new DbTeleport();
					teleport.TeleportID = "personal";
					teleport.Realm = (int)player.Realm;
					teleport.RegionID = location.RegionID;
					teleport.X = location.X;
					teleport.Y = location.Y;
					teleport.Z = location.Z;
					teleport.Heading = location.Heading;
					return teleport;
				}
			}

			// Yet another special case the port to the 'hearth' what means
			// that the player will be ported to the defined house bindstone
			if (text.ToLower() == "hearth")
			{
				// Check if player has set a house bind
				if (!(player.BindHouseRegion > 0))
				{
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Hearth.NoBindPoint"));
					return null;
				}

				// Check if the house at the player's house bind location still exists
				var houses = HouseMgr.GetHousesCloseToSpot((ushort)player.
					BindHouseRegion, player.BindHouseXpos, player.
					BindHouseYpos, 700);
				if (houses.Count == 0)
				{
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Hearth.HouseRemoved"));
					return null;
				}

				// Check if the house at the player's house bind location contains a bind stone
				House targetHouse = houses[0];
				var hookpointItems = targetHouse.HousePointItems;
				Boolean hasBindstone = false;

				foreach (KeyValuePair<uint, DbHouseHookPointItem> targetHouseItem in hookpointItems)
				{
					if (((GameObject)targetHouseItem.Value.GameObject).GetName(0, false).ToLower().EndsWith("bindstone"))
					{
						hasBindstone = true;
						break;
					}
				}

				if (!hasBindstone)
				{
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Hearth.BindstoneRemoved"));
					return null;
				}

				// Check if the player has the permission to bind at the house bind stone
				if (!targetHouse.CanBindInHouse(player))
				{
					SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Hearth.NoBindPermission"));
					return null;
				}

				DbTeleport teleport = new DbTeleport();
				teleport.TeleportID = "hearth";
				teleport.Realm = (int)player.Realm;
				teleport.RegionID = player.BindHouseRegion;
				teleport.X = player.BindHouseXpos;
				teleport.Y = player.BindHouseYpos;
				teleport.Z = player.BindHouseZpos;
				teleport.Heading = player.BindHouseHeading;
				return teleport;
			}

			if (text.ToLower() == "guild")
			{
				House house = HouseMgr.GetGuildHouseByPlayer(player);

				if (house == null)
				{
					return null;  // no teleport when guild house not found
				}
				else
				{
					IGameLocation location = house.OutdoorJumpPoint;
					DbTeleport teleport = new DbTeleport();
					teleport.TeleportID = "guild house";
					teleport.Realm = (int)player.Realm;
					teleport.RegionID = location.RegionID;
					teleport.X = location.X;
					teleport.Y = location.Y;
					teleport.Z = location.Z;
					teleport.Heading = location.Heading;
					return teleport;
				}
			}

			// Find the teleport location in the database.
			return WorldMgr.GetTeleportLocation(realm, String.Format(":{0}", text));
		}
	}
}
