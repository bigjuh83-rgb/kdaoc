/*
 * DAWN OF LIGHT - The first free open source DAoC server emulator
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 *
 */
using System;
using System.Reflection;
using DOL.Events;
using DOL.Database;
using DOL.GS.PacketHandler;
using DOL.GS.Housing;
using DOL.Language;

namespace DOL.GS
{
    /// <summary>
    /// Ancient bound djinn (Atlantis teleporter).
    /// </summary>
    /// <author>Aredhel</author>
    public abstract class AncientBoundDjinn : GameTeleporter
    {
        private const int NpcTemplateId = 3000;
        private const int ZOffset = 63;

        /// <summary>
        /// Creates a new djinn.
        /// </summary>
        public AncientBoundDjinn(DjinnStone djinnStone) : base()
        {
            NpcTemplate npcTemplate = NpcTemplateMgr.GetTemplate(NpcTemplateId);

            if (npcTemplate == null)
                throw new ArgumentNullException("Can't find NPC template for ancient bound djinn");

            LoadTemplate(npcTemplate);

            CurrentRegion = djinnStone.CurrentRegion;
            Heading = djinnStone.Heading;
            Realm = eRealm.None;
            Flags ^= GameNPC.eFlags.FLYING | GameNPC.eFlags.PEACE;
            X = djinnStone.X;
            Y = djinnStone.Y;
            Z = djinnStone.Z + HoverHeight;
            base.Size = Size;
        }

        /// <summary>
        /// Gets the actual size.
        /// </summary>
        virtual protected new byte Size
        {
            get { return base.Size; }
        }

        /// <summary>
        /// Gets the height at which the djinn is hovering.
        /// </summary>
        virtual protected int HoverHeight
        {
            get { return 63; }
        }

        /// <summary>
        /// Teleporter type, needed to pick the right TeleportID.
        /// </summary>
        protected override String Type
        {
            get { return "Djinn"; }
        }

        /// <summary>
        /// The destination realm.
        /// </summary>
        protected override eRealm DestinationRealm
        {
            get
            {
				return CurrentZone.Realm;
            }
        }

        private static string T(GamePlayer player, string key, params object[] args)
            => LanguageMgr.GetTranslation(player.Client.Account.Language, key, args);


        /// <summary>
        /// Pick a model for this zone.
        /// </summary>
        protected ushort VisibleModel
        {
            get
            {
                switch (CurrentZone.ID)
                {
                    // Oceanus Hesperos.

                    case 73:            // Albion.
                    case 30:            // Midgard.
                    case 130:           // Hibernia.
                        return 0x4aa;

                    // Stygian Delta.

                    case 81:
                    case 38:
                    case 138:
                        return 0x4ac;

                    // Oceanus Notos.

                    case 76:
                    case 33:
                    case 133:
                        return 0x4ae;

                    // Oceanus Anatole:

                    case 77:
                    case 34:
                    case 134:
                        return 0x4aa;

                    // Temple of Twilight:
                    case 80:
                    case 37:
                    case 137:
                        return 0x4ad;

                    default:
                        return 0x4aa;
                }
            }
        }

        /// <summary>
        /// Summon the djinn.
        /// </summary>
        public virtual void Summon()
        {
        }

        /// <summary>
        /// Whether or not the djinn is summoned.
        /// </summary>
        public virtual bool IsSummoned
        {
            get { return false; }
        }

        /// <summary>
        /// Player right-clicked the djinn.
        /// </summary>
        /// <param name="player"></param>
        /// <returns></returns>
        public override bool Interact(GamePlayer player)
        {
            if (!base.Interact(player))
                return false;

            String intro = T(player, "AncientBoundDjinn.Interact.Intro");

            String destinations;

            switch (player.Realm)
            {
                case eRealm.Albion:
                    destinations = T(player, "AncientBoundDjinn.Interact.Destinations.Albion");
                    break;
                case eRealm.Midgard:
                    destinations = T(player, "AncientBoundDjinn.Interact.Destinations.Midgard");
                    break;
                case eRealm.Hibernia:
                    destinations = T(player, "AncientBoundDjinn.Interact.Destinations.Hibernia");
                    break;
                default:
                    SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AncientBoundDjinn.Interact.UnknownRealm"));
                    return true;
            }

            SayTo(player, String.Format("{0} {1}", intro, destinations));
            return true;
        }

        /// <summary>
        /// Talk to the djinn.
        /// </summary>
        /// <param name="source"></param>
        /// <param name="text"></param>
        /// <returns></returns>
        public override bool WhisperReceive(GameLiving source, String text)
        {
            if (!(source is GamePlayer))
                return false;

            GamePlayer player = source as GamePlayer;
			text = text switch
			{
					"마스터" => "masters",
					"아틀란티스 던전" => "dungeons of Atlantis",
					"오케아노스" => "Oceanus",
					"스티지아" => "Stygia",
					"볼카누스" => "Volcanus",
					"에어러스" => "Aerus",
					"케어웬트" => "Caerwent",
					"에릭스타드" => "Erikstaad",
					"미스" => "Meath",
					"돔난 숲" => "Grove of Domnann",
					"코볼드" => "Kobold",
					"헤스페로스" => "Hesperos",
					"세투스 구덩이" => "Cetus' Pit",
					"소베카이트 이터널" => "Sobekite Eternal",
					"신전" => "Temple",
					"델타" => "Delta",
					"아툼의 땅" => "Land of Atum",
					"티폰의 영역" => "Typhon's Reach",
					"투시아 네소스" => "Thusia Nesos",
					"아폴로" => "Apollo",
					"바줄의 요새" => "Vazul's Fortress",
					"키메라" => "Chimera",
					"초록 숲" => "Green Glades",
					"탈로스" => "Talos",
					"황혼" => "Twilight",
					"대피라미드" => "Great Pyramid",
					"마아티의 전당" => "Halls of Ma'ati",
					"심연" => "Deep",
					"도시" => "City",
					"아누바이트" => "Anubite",
					"암무트의 방" => "Chamber of Ammut",
						"입구" => "entrance",
						"개인 주택" => "personal",
						"길드 주택" => "guild",
						"귀환 위치" => "hearth",
					"남서쪽" => "southwest",
					"북동쪽" => "northeast",
					"티폰 본인" => "Typhon himself",
					"포털" => "portal",
					"고대 왕들" => "ancient kings",
					_ => text
				};

            // Manage the chit-chat.

            switch (text.ToLower())
            {
                case "masters":
                    String reply = LanguageMgr.GetTranslation(player.Client.Account.Language, "AncientBoundDjinn.Whisper.Masters");
                    SayTo(player, reply);
                    return true;
                case "we":
                    return true;    // No reply on live.
            }

            return base.WhisperReceive(source, text);
        }


		protected override bool GetTeleportLocation(GamePlayer player, string text)
		{
			text = text switch
			{
					"아틀란티스 던전" => "dungeons of Atlantis",
					"오케아노스" => "Oceanus",
					"스티지아" => "Stygia",
					"볼카누스" => "Volcanus",
					"에어러스" => "Aerus",
					"케어웬트" => "Caerwent",
					"에릭스타드" => "Erikstaad",
					"미스" => "Meath",
					"돔난 숲" => "Grove of Domnann",
					"코볼드" => "Kobold",
					"헤스페로스" => "Hesperos",
					"세투스 구덩이" => "Cetus' Pit",
					"소베카이트 이터널" => "Sobekite Eternal",
					"신전" => "Temple",
					"델타" => "Delta",
					"아툼의 땅" => "Land of Atum",
					"티폰의 영역" => "Typhon's Reach",
					"투시아 네소스" => "Thusia Nesos",
					"아폴로" => "Apollo",
					"바줄의 요새" => "Vazul's Fortress",
					"키메라" => "Chimera",
					"초록 숲" => "Green Glades",
					"탈로스" => "Talos",
					"황혼" => "Twilight",
					"대피라미드" => "Great Pyramid",
					"마아티의 전당" => "Halls of Ma'ati",
					"심연" => "Deep",
					"도시" => "City",
					"아누바이트" => "Anubite",
					"암무트의 방" => "Chamber of Ammut",
						"입구" => "entrance",
					"개인 주택" => "personal",
					"길드 주택" => "guild",
					"귀환 위치" => "hearth",
					"남서쪽" => "southwest",
					"북동쪽" => "northeast",
					"티폰 본인" => "Typhon himself",
					"포털" => "portal",
					"고대 왕들" => "ancient kings",
					_ => text
				};

			// special cases
			if (text.ToLower() == "battlegrounds" || text.ToLower() == "personal" || text.ToLower() == "guild" || text.ToLower() == "hearth")
			{
				return base.GetTeleportLocation(player, text);
			}

			// Find the teleport location in the database.  For Djinns use the player realm to match Interact list given.
			DbTeleport port = WorldMgr.GetTeleportLocation(player.Realm, String.Format("{0}:{1}", Type, text));

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
        /// Player has picked a subselection.
        /// </summary>
        /// <param name="player"></param>
        /// <param name="subSelection"></param>
        protected override void OnSubSelectionPicked(GamePlayer player, DbTeleport subSelection)
        {
            switch (subSelection.TeleportID.ToLower())
            {
                case "oceanus":
                    {
                        SayTo(player, T(player, "AncientBoundDjinn.SubSelection.Oceanus"));
                        return;
                    }
                case "stygia":
                    {
                        SayTo(player, T(player, "AncientBoundDjinn.SubSelection.Stygia"));
                        return;
                    }
                case "volcanus":
                    {
                        SayTo(player, T(player, "AncientBoundDjinn.SubSelection.Volcanus"));
                        return;
                    }
                case "aerus":
                    {
                        SayTo(player, T(player, "AncientBoundDjinn.SubSelection.Aerus"));
                        return;
                    }
                case "dungeons of atlantis":
                    {
                        SayTo(player, T(player, "AncientBoundDjinn.SubSelection.Dungeons"));
                        return;
                    }
                case "twilight":
                    {
                        SayTo(player, T(player, "AncientBoundDjinn.SubSelection.Twilight"));
                        return;
                    }
                case "halls of ma'ati":
                    {
                        SayTo(player, T(player, "AncientBoundDjinn.SubSelection.HallsOfMaati"));
                        return;
                    }
                case "deep":
                    {
                        SayTo(player, T(player, "AncientBoundDjinn.SubSelection.Deep"));
                        return;
                    }
                case "city":
                    {
                        SayTo(player, T(player, "AncientBoundDjinn.SubSelection.City"));
                        return;
                    }

            }

            base.OnSubSelectionPicked(player, subSelection);
        }

        /// <summary>
        /// Player has picked a teleport destination.
        /// </summary>
        /// <param name="player"></param>
        /// <param name="destination"></param>
        protected override void OnDestinationPicked(GamePlayer player, DbTeleport destination)
        {
            if (player == null)
                return;

            if (Region.IsAtlantis(player.CurrentRegionID) &&
                Region.IsAtlantis(destination.RegionID))
            {
                destination = CopyTeleport(destination);
                destination.RegionID = player.CurrentRegionID;
            }

            switch (destination.TeleportID.ToLower())
            {
                case "hesperos":
                    {
                        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "AncientBoundDjinn.Teleport.DeliversToHaven", Name, "Oceanus"),
                            eChatType.CT_System, eChatLoc.CL_SystemWindow);
                        base.OnTeleport(player, destination);
                        return;
                    }
                case "delta":
                    {
                        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "AncientBoundDjinn.Teleport.DeliversToHaven", Name, "Stygia"),
                            eChatType.CT_System, eChatLoc.CL_SystemWindow);
                        base.OnTeleport(player, destination);
                        return;
                    }
                case "green glades":
                    {
                        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "AncientBoundDjinn.Teleport.DeliversToHaven", Name, "Aerus"),
                            eChatType.CT_System, eChatLoc.CL_SystemWindow);
                        base.OnTeleport(player, destination);
                        return;
                    }
            }

            base.OnDestinationPicked(player, destination);
        }

        private static DbTeleport CopyTeleport(DbTeleport source)
        {
            return new DbTeleport
            {
                Type = source.Type,
                TeleportID = source.TeleportID,
                Realm = source.Realm,
                RegionID = source.RegionID,
                X = source.X,
                Y = source.Y,
                Z = source.Z,
                Heading = source.Heading
            };
        }

        /// <summary>
        /// Teleport the player to the designated coordinates.
        /// </summary>
        /// <param name="player"></param>
        /// <param name="destination"></param>
        protected override void OnTeleport(GamePlayer player, DbTeleport destination)
        {
            player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "AncientBoundDjinn.Teleport.Distortion"),
                eChatType.CT_System, eChatLoc.CL_SystemWindow);

            base.OnTeleport(player, destination);
        }

        /// <summary>
        /// "Say" content sent to the system window.
        /// </summary>
        /// <param name="message"></param>
        /// <returns></returns>
        public override bool Say(String message)
        {
			foreach (GamePlayer player in GetPlayersInRadius(WorldMgr.SAY_DISTANCE))
			{
				player.Out.SendMessage(T(player, "AncientBoundDjinn.Say", this.Name, message), eChatType.CT_System, eChatLoc.CL_SystemWindow);
			}

            return true;
        }
    }
}
