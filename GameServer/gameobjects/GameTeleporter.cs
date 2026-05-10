using System;
using System.Collections.Generic;
using DOL.Database;
using DOL.GS.Housing;
using DOL.GS.Keeps;
using DOL.GS.PacketHandler;
using DOL.GS.Spells;
using DOL.Language;

namespace DOL.GS
{
	/// <summary>
	/// Base class for all teleporter type NPCs.
	/// </summary>
	/// <author>Aredhel</author>
	public class GameTeleporter : GameNPC
	{
		public GameTeleporter()
			: base() { }

        /// <summary>
        /// The type of teleporter; this is used in order to be able to handle
        /// identical TeleportIDs differently, depending on the actual teleporter.
        /// </summary>
        protected virtual String Type
        {
            get { return string.Empty; }
        }

        /// <summary>
        /// The destination realm.
        /// </summary>
        protected virtual eRealm DestinationRealm
        {
            get { return Realm; }
        }

		/// <summary>
		/// Turn the teleporter to face the player.
		/// </summary>
		/// <param name="player"></param>
		/// <returns></returns>
		public override bool Interact(GamePlayer player)
		{
			if (!base.Interact(player) || GameRelic.IsPlayerCarryingRelic(player))
				return false;

			TurnTo(player, 10000);
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
			if (!base.WhisperReceive(source, text))
				return false;

			GamePlayer player = source as GamePlayer;
			if (player == null)
				return false;

			if (GameRelic.IsPlayerCarryingRelic(player))
				return false;

			return GetTeleportLocation(player, text);
		}

		protected virtual bool GetTeleportLocation(GamePlayer player, string text)
		{
			text = text switch
			{
					"주택" => "housing",
					"슈라우디드 아일스" => "shrouded isles",
					"마을" => "towns",
					"입구" => "Entrance",
					"개인 주택" => "personal",
					"길드 주택" => "guild",
					"귀환 위치" => "hearth",
					"소바쥬 성" => "Castle Sauvage",
					"스노도니아 요새" => "Snowdonia Fortress",
					"아발론 습지" => "Avalon Marsh",
					"고스웨이트 항구" => "Gothwaite Harbor",
					"카멜롯" => "Camelot",
					"고스웨이트" => "Gothwaite",
					"위어리얼 마을" => "Wearyall Village",
					"귄텔 요새" => "Gwyntell",
					"케어 디오겔" => "Caer Diogel",
					"코츠월드 마을" => "Cotswold Village",
					"프리드웬 성채" => "Prydwen Keep",
					"케어 울프위치" => "Caer Ulfwych",
					"캄파코렌틴 기지" => "Campacorentin Station",
					"아드리바드 은거지" => "Adribard's Retreat",
					"야를리 농장" => "Yarley's Farm",
					"스바수드 파스테" => "Svasud Faste",
					"빈드사울 파스테" => "Vindsaul Faste",
					"고타르" => "Gotar",
					"에기르함" => "Aegirhamn",
					"요르드하임" => "Jordheim",
					"비야르켄" => "Bjarken",
					"하갈" => "Hagall",
					"크나르" => "Knarr",
					"물란" => "Mularn",
					"벨돈 요새" => "Fort Veldon",
					"아우들리텐" => "Audliten",
					"후긴펠" => "Huginfell",
					"아틀라 요새" => "Fort Atla",
					"웨스트 스코나" => "West Skona",
					"드루임 리겐" => "Druim Ligen",
					"드루임 케인" => "Druim Cain",
					"섀넌 하구" => "Shannon Estuary",
					"돔난" => "Domnann",
					"티르 나 노그" => "Tir na Nog",
					"드로하이드" => "Droighaid",
					"알리드 페이" => "Aalid Feie",
					"네흐트" => "Necht",
					"마그 멜" => "Mag Mell",
					"티르 나 므베오" => "Tir na mBeo",
					"아르다" => "Ardagh",
					"호스" => "Howth",
					"콘라" => "Connla",
					"이니스 카르사이그" => "Innis Carthaig",
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
						OnDestinationPicked(player, teleport);
						return true;
					}
					else
					{
						if (player.Client.Account.PrivLevel > (uint)ePrivLevel.Player)
						{
							player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client, "GameTeleporter.NoPortalKeepFound"), eChatType.CT_Items, eChatLoc.CL_SystemWindow);
						}
						return true;
					}
				}
			}

			if (text == "Entrance") text = text.ToLower();

			// Another special case is personal house, as there is no location
			// that will work for every player.
			if (text.ToLower() == "personal")
			{
				House house = HouseMgr.GetHouseByPlayer(player);

				if(house == null)
				{
					text = "entrance";	// Fall through, port to housing entrance.
				}
				else
				{
					IGameLocation location = house.OutdoorJumpPoint;
					DbTeleport teleport = new DbTeleport();
					teleport.TeleportID = "personal";
					teleport.Realm = (int)DestinationRealm;
					teleport.RegionID = location.RegionID;
					teleport.X = location.X;
					teleport.Y = location.Y;
					teleport.Z = location.Z;
					teleport.Heading = location.Heading;
					OnDestinationPicked(player, teleport);
					return true;
				}
			}

			// Yet another special case the port to the 'hearth' what means
			// that the player will be ported to the defined house bindstone
			if (text.ToLower() == "hearth")
			{
				// Check if player has set a house bind
				if (!(player.BindHouseRegion > 0))
				{
					SayTo(player, LanguageMgr.GetTranslation(player.Client, "GameTeleporter.NoHouseBindPoint"));
					return false;
				}

				// Check if the house at the player's house bind location still exists
				var houses = HouseMgr.GetHousesCloseToSpot((ushort)player.
					BindHouseRegion, player.BindHouseXpos, player.
					BindHouseYpos, 700);
				if (houses.Count == 0)
				{
					SayTo(player, LanguageMgr.GetTranslation(player.Client, "GameTeleporter.HouseBindHouseTornDown"));
					return false;
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
					SayTo(player, LanguageMgr.GetTranslation(player.Client, "GameTeleporter.HouseBindstoneRemoved"));
					return false;
				}

				// Check if the player has the permission to bind at the house bind stone
				if (!targetHouse.CanBindInHouse(player))
				{
					SayTo(player, LanguageMgr.GetTranslation(player.Client, "GameTeleporter.HouseBindNoPermission"));
					return false;
				}

				DbTeleport teleport = new DbTeleport();
				teleport.TeleportID = "hearth";
				teleport.Realm = (int)DestinationRealm;
				teleport.RegionID = player.BindHouseRegion;
				teleport.X = player.BindHouseXpos;
				teleport.Y = player.BindHouseYpos;
				teleport.Z = player.BindHouseZpos;
				teleport.Heading = player.BindHouseHeading;
				OnDestinationPicked(player, teleport);
				return true;
			}

			if (text.ToLower() == "guild")
			{
				House house = HouseMgr.GetGuildHouseByPlayer(player);

				if (house == null)
				{
					return false;  // no teleport when guild house not found
				}
				else
				{
					IGameLocation location = house.OutdoorJumpPoint;
					DbTeleport teleport = new DbTeleport();
					teleport.TeleportID = "guild house";
					teleport.Realm = (int)DestinationRealm;
					teleport.RegionID = location.RegionID;
					teleport.X = location.X;
					teleport.Y = location.Y;
					teleport.Z = location.Z;
					teleport.Heading = location.Heading;
					OnDestinationPicked(player, teleport);
					return true;
				}
			}

			// Find the teleport location in the database.
			DbTeleport port = WorldMgr.GetTeleportLocation(DestinationRealm, String.Format("{0}:{1}", Type, text));
			if (port != null)
			{
				if (port.RegionID == 0 && port.X == 0 && port.Y == 0 && port.Z == 0)
				{
					OnSubSelectionPicked(player, port);
				}
				else
				{
					OnDestinationPicked(player, port);
				}
				return false;
			}

			return true;	// Needs further processing.
		}

		/// <summary>
		/// Player has picked a destination.
		/// Override if you need the teleporter to say something to the player
		/// before porting him.
		/// </summary>
		/// <param name="player"></param>
		/// <param name="destination"></param>
		protected virtual void OnDestinationPicked(GamePlayer player, DbTeleport destination)
		{
			Region region = WorldMgr.GetRegion((ushort)destination.RegionID);

			if (region == null || region.IsDisabled)
			{
				player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client, "GameTeleporter.DestinationUnavailable"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				return;
			}

			OnTeleport(player, destination);
		}

		/// <summary>
		/// Player has picked a subselection.
		/// Override to pass teleport options on to the player.
		/// </summary>
		/// <param name="player"></param>
		/// <param name="subSelection"></param>
		protected virtual void OnSubSelectionPicked(GamePlayer player, DbTeleport subSelection)
		{
		}

		/// <summary>
		/// Teleport the player to the designated coordinates using the
		/// portal spell.
		/// </summary>
		/// <param name="player"></param>
		/// <param name="destination"></param>
		protected virtual void OnTeleportSpell(GamePlayer player, DbTeleport destination)
		{
			SpellLine spellLine = SkillBase.GetSpellLine(GlobalSpellsLines.Mob_Spells);
			List<Spell> spellList = SkillBase.GetSpellList(GlobalSpellsLines.Mob_Spells);
			Spell spell = SkillBase.GetSpellByID(5999);	// UniPortal spell.

			if (spell != null)
			{
				UniPortal portalHandler = new UniPortal(this, spell, spellLine, destination);
				portalHandler.StartSpell(player);
				return;
			}

			// Spell not found in the database, fall back on default procedure.

			if (player.Client.Account.PrivLevel > 1)
				player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client, "GameTeleporter.UniPortalSpellNotFound"),
					eChatType.CT_Items, eChatLoc.CL_SystemWindow);

			this.OnTeleport(player, destination);
		}

		/// <summary>
		/// Teleport the player to the designated coordinates.
		/// </summary>
		/// <param name="player"></param>
		/// <param name="destination"></param>
		protected virtual void OnTeleport(GamePlayer player, DbTeleport destination)
		{
			if (player.InCombat == false && GameRelic.IsPlayerCarryingRelic(player) == false)
			{
				player.LeaveHouse();
				GameLocation currentLocation = new GameLocation("TeleportStart", player.CurrentRegionID, player.X, player.Y, player.Z);
				player.MoveTo((ushort)destination.RegionID, destination.X, destination.Y, destination.Z, (ushort)destination.Heading);
				GameServer.ServerRules.OnPlayerTeleport(player, currentLocation, destination);
			}
		}
	}
}
