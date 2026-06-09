using System;
using System.Buffers;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Numerics;
using System.Text;
using DOL.AI.Brain;
using DOL.Database;
using DOL.Events;
using DOL.GS.Keeps;
using DOL.GS.PacketHandler;
using DOL.GS.Realm;
using DOL.GS.Scheduler;
using DOL.Language;
using DOL.MPK;

namespace DOL.GS.GameEvents
{
	public static class KeepSupplyConvoyEvent
	{
		private const string PackageId = "KDAOCKeepSupplyConvoy";
		private const int PreparationDelayMilliseconds = 180000;
		private const int TickMilliseconds = 1000;
		private const int ArrivalRadius = 850;
		private const int PathNodeArrivalRadius = 700;
		private const int SpawnOffset = 650;
		private const int EscortFormationBehindDistance = 420;
		private const int EscortFormationSideDistance = 280;
		private const int EscortFormationArrivalRadius = 350;
		private const int EscortFollowMinDistance = 300;
		private const int EscortFollowMaxDistance = 20000;
		private const int EscortCatchUpDistance = 1800;
		private const int EscortDefenseRadius = 6000;
		private const int EscortCombatLeashRadius = 6000;
		private const int RewardRadius = 6000;
		private const int NavmeshRouteNodeCapacity = 512;
		private const int GraphStepDistance = 1024;
		private const int GraphSearchPadding = 32768;
		private const int GraphSearchMaxIterations = 50000;
		private const int PathPointSearchPadding = 65536;
		private const int PathPointConnectorRadius = 12000;
		private const int PathPointIntersectionRadius = 3500;
		private const int PathPointBucketSize = 4096;
		private const int MaxPathPointEndpointConnections = 24;
		private const double PathPointRouteCostMultiplier = 0.35;
		private const double PathPointConnectorCostMultiplier = 1.8;
		private const double PathPointIntersectionCostMultiplier = 0.8;
		private const float PathSnapRange = 4096f;
		private const int MaxPreferredSegmentZDelta = 512;
		private const int MaxFallbackSegmentZDelta = 1024;
		private const int TerrainSampleSpacing = 512;
		private const int MaxTerrainSampleZDelta = 640;
		private const int MaxTerrainSegmentZDelta = 1150;
		private const int MaxTerrainRoadSampleZDelta = 1200;
		private const int MaxTerrainRoadSegmentZDelta = 2200;
		private const double TerrainClimbCostMultiplier = 18.0;
		private const double FallbackSameZoneCostMultiplier = 8.0;
		private const double FallbackCrossZoneCostMultiplier = 14.0;
		private const int MinimapRoadSampleSpacing = 256;
		private const int MinimapRoadPixelSearchRadius = 3;
		private const int MinimapRoadSnapPixelRadius = 6;
		private const double MinimapStrongRoadScore = 0.45;
		private const double MinimapWeakRoadScore = 0.18;
		private const double MinimapStrongRoadCostMultiplier = 0.16;
		private const double MinimapWeakRoadCostMultiplier = 0.35;
		private const double MinimapOffRoadCostMultiplier = 10.0;
		private const short ConvoyMoveSpeed = 130;
		private const short EscortFollowMoveSpeed = 190;
		private const short EscortCatchUpMoveSpeed = 430;
		private static readonly ushort[] SupplyWagonModels = new ushort[] { 2027, 2028, 2029, 2030, 2031 };
		private const byte WagonLevel = 60;
		private const byte EscortLevel = 55;
		private const int EscortRealmPointReward = 450;
		private const int EscortBountyPointReward = 150;
		private const long SupportRealmPointRewardPerMinute = 200;
		private const long SupportBountyPointRewardPerMinute = 30;
		private const long InterceptRealmPointReward = 500;
		private const long InterceptBountyPointReward = 350;
		private const double UndersuppliedStructureDamageMultiplier = 1.5;

		private static readonly PlayerRace[] AlbionEscortRaces =
		{
			PlayerRace.Briton,
			PlayerRace.Avalonian,
			PlayerRace.Highlander,
			PlayerRace.Saracen,
			PlayerRace.Inconnu,
			PlayerRace.HalfOgre
		};

		private static readonly PlayerRace[] MidgardEscortRaces =
		{
			PlayerRace.Norseman,
			PlayerRace.Troll,
			PlayerRace.Dwarf,
			PlayerRace.Kobold,
			PlayerRace.Valkyn,
			PlayerRace.Frostalf
		};

		private static readonly PlayerRace[] HiberniaEscortRaces =
		{
			PlayerRace.Celt,
			PlayerRace.Firbolg,
			PlayerRace.Elf,
			PlayerRace.Lurikeen,
			PlayerRace.Sylvan,
			PlayerRace.Shar
		};

		private static readonly object ConvoyLock = new();
		private static readonly Dictionary<eRealm, ConvoyState> ActiveConvoysByRealm = new();
		private static readonly Dictionary<eRealm, ConvoyStartPosition> StartPositionsByRealm = new();
		private static readonly HashSet<int> PendingKeepIds = new();
		private static readonly HashSet<eRealm> PendingRealms = new();
		private static readonly HashSet<int> UndersuppliedKeepIds = new();

		[ScriptLoadedEvent]
		public static void OnScriptLoaded(DOLEvent e, object sender, EventArgs args)
		{
			LoadStartPositions();
			GameEventMgr.AddHandler(KeepEvent.KeepTaken, OnKeepTaken);
		}

		[ScriptUnloadedEvent]
		public static void OnScriptUnloaded(DOLEvent e, object sender, EventArgs args)
		{
			GameEventMgr.RemoveHandler(KeepEvent.KeepTaken, OnKeepTaken);

			lock (ConvoyLock)
			{
				foreach (ConvoyState state in ActiveConvoysByRealm.Values.ToList())
					CleanupConvoy(state);

				ActiveConvoysByRealm.Clear();
				PendingKeepIds.Clear();
				PendingRealms.Clear();
				UndersuppliedKeepIds.Clear();
			}
		}

		public static bool IsKeepUndersupplied(AbstractGameKeep keep)
		{
			if (keep == null || keep.IsPortalKeep)
				return false;

			lock (ConvoyLock)
				return UndersuppliedKeepIds.Contains(keep.KeepID);
		}

		public static int ApplyUndersuppliedStructureDamage(AbstractGameKeep keep, int damage)
		{
			if (damage <= 0 || !IsKeepUndersupplied(keep))
				return damage;

			return Math.Max(1, (int)Math.Round(damage * UndersuppliedStructureDamageMultiplier));
		}

		public static int ApplyUndersuppliedGuardDamage(AbstractGameKeep keep, int damage)
		{
			if (damage <= 0 || !IsKeepUndersupplied(keep))
				return damage;

			return Math.Max(1, (int)Math.Round(damage * UndersuppliedStructureDamageMultiplier));
		}

		public static bool SetStartPosition(eRealm realm, ushort regionId, int x, int y, int z, ushort heading, out string message)
		{
			if (realm is not (eRealm.Albion or eRealm.Midgard or eRealm.Hibernia))
			{
				message = "알비온, 미드가드, 하이버니아 중 하나만 설정할 수 있습니다.";
				return false;
			}

			DbKeepSupplyConvoyStart row = DOLDB<DbKeepSupplyConvoyStart>.SelectObject(DB.Column("Realm").IsEqualTo((int)realm));
			bool isNew = row == null;
			row ??= new DbKeepSupplyConvoyStart { Realm = (int)realm };

			row.RegionID = regionId;
			row.X = x;
			row.Y = y;
			row.Z = z;
			row.Heading = heading;

			bool saved = isNew ? GameServer.Database.AddObject(row) : GameServer.Database.SaveObject(row);
			if (!saved)
			{
				message = "DB 저장에 실패했습니다.";
				return false;
			}

			lock (ConvoyLock)
				StartPositionsByRealm[realm] = ConvoyStartPosition.From(row);

			message = $"{RealmName(realm)} 보급대 출발 위치를 region={regionId}, x={x}, y={y}, z={z}로 저장했습니다.";
			return true;
		}

		public static bool ClearStartPosition(eRealm realm, out string message)
		{
			DbKeepSupplyConvoyStart row = DOLDB<DbKeepSupplyConvoyStart>.SelectObject(DB.Column("Realm").IsEqualTo((int)realm));
			if (row == null)
			{
				lock (ConvoyLock)
					StartPositionsByRealm.Remove(realm);

				message = $"{RealmName(realm)} 보급대 출발 위치가 이미 비어 있습니다.";
				return true;
			}

			if (!GameServer.Database.DeleteObject(row))
			{
				message = "DB 삭제에 실패했습니다.";
				return false;
			}

			lock (ConvoyLock)
				StartPositionsByRealm.Remove(realm);

			message = $"{RealmName(realm)} 보급대 출발 위치를 삭제했습니다.";
			return true;
		}

		public static ConvoyStartPosition[] GetStartPositions()
		{
			lock (ConvoyLock)
				return StartPositionsByRealm.Values.OrderBy(start => start.Realm).ToArray();
		}

		private static void LoadStartPositions()
		{
			IList<DbKeepSupplyConvoyStart> rows = DOLDB<DbKeepSupplyConvoyStart>.SelectAllObjects();

			lock (ConvoyLock)
			{
				StartPositionsByRealm.Clear();

				foreach (DbKeepSupplyConvoyStart row in rows)
				{
					eRealm realm = (eRealm)row.Realm;
					if (realm is eRealm.Albion or eRealm.Midgard or eRealm.Hibernia)
						StartPositionsByRealm[realm] = ConvoyStartPosition.From(row);
				}
			}
		}

		private static bool TryGetStartPosition(eRealm realm, out ConvoyStartPosition start)
		{
			lock (ConvoyLock)
				return StartPositionsByRealm.TryGetValue(realm, out start);
		}

		public static bool ForceStartConvoy(int keepId, out string message)
		{
			AbstractGameKeep keep = GameServer.KeepManager.GetKeepByID(keepId);
			if (keep == null)
			{
				message = $"KeepID {keepId}를 찾을 수 없습니다.";
				return false;
			}

			if (keep is not GameKeep || keep.IsPortalKeep)
			{
				message = "보급대는 일반 킵으로만 강제 출발할 수 있습니다.";
				return false;
			}

			eRealm realm = keep.Realm;
			if (realm is eRealm.None)
			{
				message = $"{LanguageMgr.GetTranslatedKeepName(ServerProperties.Properties.SERV_LANGUAGE, keep.Name)}은 현재 소유 렐름이 없어 보급대를 출발시킬 수 없습니다.";
				return false;
			}

			lock (ConvoyLock)
			{
				if (ActiveConvoysByRealm.ContainsKey(realm))
				{
					message = $"이미 {RealmName(realm)} 보급대가 편성되어 있습니다.";
					return false;
				}

				PendingKeepIds.Remove(keep.KeepID);
				PendingRealms.Remove(realm);
			}

			if (!StartConvoy(keep, realm, true, true, out message))
				return false;

			message = $"{RealmName(realm)} 보급대를 {LanguageMgr.GetTranslatedKeepName(ServerProperties.Properties.SERV_LANGUAGE, keep.Name)}으로 강제 출발시켰습니다. {message}";
			return true;
		}

		private static void OnKeepTaken(DOLEvent e, object sender, EventArgs arguments)
		{
			if (arguments is not KeepEventArgs keepArgs || keepArgs.Keep == null)
				return;

			AbstractGameKeep capturedKeep = keepArgs.Keep;
			eRealm realm = capturedKeep.Realm;
			if (realm is eRealm.None || capturedKeep.IsPortalKeep || capturedKeep is not GameKeep)
				return;

			bool markedUndersupplied;
			lock (ConvoyLock)
			{
				markedUndersupplied = UndersuppliedKeepIds.Add(capturedKeep.KeepID);

				if (ActiveConvoysByRealm.ContainsKey(realm) || PendingRealms.Contains(realm) || PendingKeepIds.Contains(capturedKeep.KeepID))
				{
					Broadcast($"이미 {RealmName(realm)} 보급대가 편성되어 있어서 {capturedKeep.Name} 보급대는 편성되지 않았습니다. {capturedKeep.Name}은 미보급 상태로 약해졌습니다.", eChatType.CT_Important);
					return;
				}

				PendingKeepIds.Add(capturedKeep.KeepID);
				PendingRealms.Add(realm);
			}

			if (markedUndersupplied)
				Broadcast($"{capturedKeep.Name}은 미보급 상태입니다. 보급대가 도착하기 전까지 문, 성벽, 경비병이 받는 피해가 50% 증가합니다.", eChatType.CT_ScreenCenter);

			StartConvoy(capturedKeep, realm, false, false, out string ignoredMessage);
		}

		private static bool StartConvoy(AbstractGameKeep capturedKeep, eRealm realm, bool requireConfiguredStart, bool startImmediately, out string message)
		{
			lock (ConvoyLock)
			{
				PendingKeepIds.Remove(capturedKeep.KeepID);
				PendingRealms.Remove(realm);

				if (ActiveConvoysByRealm.ContainsKey(realm))
				{
					message = $"이미 {RealmName(realm)} 보급대가 편성되어 있습니다.";
					return false;
				}
			}

			if (capturedKeep.Realm != realm || capturedKeep.CurrentRegion == null)
			{
				message = $"{capturedKeep.Name}의 소유권이 바뀌어 보급대가 출발하지 않았습니다.";
				return false;
			}

			if (!TryGetConvoyOrigin(capturedKeep, realm, requireConfiguredStart, out ConvoyOrigin origin, out string originError))
			{
				Broadcast(originError, eChatType.CT_Important);
				message = originError;
				return false;
			}

			Region originRegion = WorldMgr.GetRegion(origin.RegionID);
			if (originRegion == null)
			{
				message = $"{RealmName(realm)} 보급대가 출발 지역을 찾지 못해 편성되지 않았습니다.";
				Broadcast(message, eChatType.CT_Important);
				return false;
			}

			Point3D destinationPoint = KeepPoint(capturedKeep);
			Point3D spawnPoint = origin.Point;
			if (!IsValidPoint(originRegion, spawnPoint))
			{
				message = $"{RealmName(realm)} 보급대 출발 위치가 유효한 지역 안에 있지 않아 편성되지 않았습니다.";
				Broadcast(message, eChatType.CT_Important);
				return false;
			}

			SupplyConvoyWagon wagon = CreateWagon(realm, spawnPoint, origin.RegionID, origin.Heading, capturedKeep);
			List<Point3D> route = BuildRoute(originRegion, spawnPoint, destinationPoint);
			if (route.Count == 0)
			{
				message = $"{RealmName(realm)} 보급대가 {capturedKeep.Name}까지 이동 가능한 보급로를 찾지 못해 출발하지 않았습니다.";
				Broadcast(message, eChatType.CT_Important);
				return false;
			}

			if (!wagon.AddToWorld())
			{
				message = $"{RealmName(realm)} 보급대가 출발하지 못했습니다.";
				Broadcast(message, eChatType.CT_Important);
				return false;
			}

			List<GameNPC> escorts = CreateEscorts(realm, spawnPoint, origin.RegionID, origin.Heading, capturedKeep).Where(AddEscortToWorld).ToList();
			ConvoyState state = new()
			{
				Realm = realm,
				OriginName = origin.Name,
				TargetKeep = capturedKeep,
				Origin = spawnPoint,
				Destination = destinationPoint,
				Wagon = wagon,
				Escorts = escorts,
				Route = route
			};

			wagon.State = state;
			GameEventMgr.AddHandler(wagon, GameLivingEvent.Dying, OnWagonDying);

			lock (ConvoyLock)
			{
				if (ActiveConvoysByRealm.ContainsKey(realm))
				{
					CleanupConvoy(state);
					message = $"이미 {RealmName(realm)} 보급대가 편성되어 있습니다.";
					return false;
				}

				ActiveConvoysByRealm[realm] = state;
			}

			if (startImmediately)
			{
				BeginConvoyMovement(state, out string ignoredDepartureMessage);
			}
			else
			{
				state.DepartureTimer = new ECSGameTimer(state.Wagon, _ =>
				{
					BeginConvoyMovement(state, out string ignoredDepartureMessage);
					return 0;
				}, PreparationDelayMilliseconds);

				Broadcast($"{RealmName(realm)} 보급대가 {origin.Name}에 집결했습니다. 3분 후 {capturedKeep.Name}으로 출발합니다.", eChatType.CT_ScreenCenter);
			}

			message = $"출발 위치: {origin.Name}, region={origin.RegionID}, x={spawnPoint.X}, y={spawnPoint.Y}, z={spawnPoint.Z}.";
			return true;
		}

		private static bool TryGetConvoyOrigin(AbstractGameKeep capturedKeep, eRealm realm, bool requireConfiguredStart, out ConvoyOrigin origin, out string error)
		{
			if (TryGetStartPosition(realm, out ConvoyStartPosition start))
			{
				if (start.RegionID != capturedKeep.Region)
				{
					origin = null;
					error = $"{RealmName(realm)} 보급대 출발 위치가 점령 킵과 다른 지역에 설정되어 편성되지 않았습니다.";
					return false;
				}

				origin = new ConvoyOrigin
				{
					Name = $"{RealmName(realm)} 보급 거점",
					RegionID = start.RegionID,
					Point = start.Point,
					Heading = start.Heading
				};
				error = string.Empty;
				return true;
			}

			if (requireConfiguredStart)
			{
				origin = null;
				error = $"{RealmName(realm)} 보급대 출발 위치가 설정되지 않았습니다. /keepsupplyconvoy setstart {RealmCommandName(realm)} 후 다시 시도하세요.";
				return false;
			}

			if (TryGetOriginKeep(capturedKeep, realm, out AbstractGameKeep originKeep))
			{
				Point3D point = GetOffsetPoint(KeepPoint(originKeep), KeepPoint(capturedKeep), SpawnOffset);
				if (!IsValidPoint(originKeep.CurrentRegion, point))
					point = new Point3D(originKeep.X, originKeep.Y, originKeep.Z);

				origin = new ConvoyOrigin
				{
					Name = originKeep.Name,
					RegionID = originKeep.Region,
					Point = point,
					Heading = 0
				};
				error = string.Empty;
				return true;
			}

			origin = null;
			error = $"{RealmName(realm)} 보급대가 출발 거점을 찾지 못해 편성되지 않았습니다.";
			return false;
		}

		private static bool TryGetOriginKeep(AbstractGameKeep capturedKeep, eRealm realm, out AbstractGameKeep originKeep)
		{
			originKeep = GameServer.KeepManager.GetKeepsOfRegion(capturedKeep.Region)
				.Where(keep => keep != capturedKeep && keep.Realm == realm && keep.IsPortalKeep)
				.OrderBy(keep => GetDistance(keep, capturedKeep))
				.FirstOrDefault();

			if (originKeep != null)
				return true;

			originKeep = GameServer.KeepManager.GetKeepsOfRegion(capturedKeep.Region)
				.Where(keep => keep != capturedKeep && keep.Realm == realm && keep is GameKeep)
				.OrderBy(keep => GetDistance(keep, capturedKeep))
				.FirstOrDefault();

			if (originKeep != null)
				return true;

			return false;
		}

		private static SupplyConvoyWagon CreateWagon(eRealm realm, Point3D spawnPoint, ushort regionId, ushort heading, AbstractGameKeep targetKeep)
		{
			SupplyConvoyWagon wagon = new()
			{
				Name = $"{RealmName(realm)} 보급 마차",
				GuildName = $"{targetKeep.Name} 보급대",
				Model = GetRandomSupplyWagonModel(),
				Size = 85,
				Level = WagonLevel,
				Realm = realm,
				CurrentRegionID = regionId,
				X = spawnPoint.X,
				Y = spawnPoint.Y,
				Z = spawnPoint.Z,
				Heading = heading,
				MaxSpeedBase = ConvoyMoveSpeed,
				PackageID = PackageId
			};
			PrepareWagonForConvoyMovement(wagon);
			wagon.Health = wagon.MaxHealth;
			return wagon;
		}

		private static IEnumerable<GameNPC> CreateEscorts(eRealm realm, Point3D spawnPoint, ushort regionId, ushort heading, AbstractGameKeep targetKeep)
		{
			for (int index = 0; index < 2; index++)
			{
				GameNPC escort = new SupplyConvoyEscort()
				{
					Name = $"{RealmName(realm)} 보급 호위병",
					GuildName = $"{targetKeep.Name} 보급대",
					Size = 50,
					Level = EscortLevel,
					Realm = realm,
					CurrentRegionID = regionId,
					X = spawnPoint.X + (index == 0 ? -160 : 160),
					Y = spawnPoint.Y + 180,
					Z = spawnPoint.Z,
					Heading = heading,
					MaxSpeedBase = EscortFollowMoveSpeed,
					PackageID = PackageId
				};

				ApplyEscortAppearance(escort, realm, regionId, spawnPoint, heading, targetKeep);
				escort.RespawnInterval = -1;
				PrepareEscortForConvoyMovement(escort);
				escort.Health = escort.MaxHealth;
				yield return escort;
			}
		}

		private static void ApplyEscortAppearance(GameNPC escort, eRealm realm, ushort regionId, Point3D spawnPoint, ushort heading, AbstractGameKeep targetKeep)
		{
			GuardFighter appearance = new()
			{
				Component = new GameKeepComponent { Keep = targetKeep },
				CurrentRegionID = regionId,
				X = spawnPoint.X,
				Y = spawnPoint.Y,
				Z = spawnPoint.Z,
				Heading = heading,
				Realm = realm,
				ModelRealm = realm,
				Level = EscortLevel,
				LoadedFromScript = true
			};

			appearance.RefreshTemplate();
			ApplyRandomRealmRaceAppearance(escort, realm, appearance);
			escort.Inventory = GetEscortInventoryTemplate(realm).CloneTemplate();
			escort.SwitchWeapon(Util.Chance(50) ? eActiveWeaponSlot.TwoHanded : eActiveWeaponSlot.Standard);
			escort.Name = $"{RealmName(realm)} 보급 호위병";
			escort.GuildName = $"{targetKeep.Name} 보급대";
		}

		private static void ApplyRandomRealmRaceAppearance(GameNPC escort, eRealm realm, GuardFighter fallbackAppearance)
		{
			PlayerRace[] raceCandidates = GetEscortRaceCandidates(realm);

			if (raceCandidates.Length == 0)
			{
				escort.Model = fallbackAppearance.Model;
				escort.Gender = fallbackAppearance.Gender;
				escort.Race = fallbackAppearance.Race;
				return;
			}

			PlayerRace selectedRace = raceCandidates[Util.Random(0, raceCandidates.Length - 1)];
			List<eGender> genderCandidates = new(2);
			if (selectedRace.GetModel(eGender.Male) != eLivingModel.None)
				genderCandidates.Add(eGender.Male);
			if (selectedRace.GetModel(eGender.Female) != eLivingModel.None)
				genderCandidates.Add(eGender.Female);

			eGender selectedGender = genderCandidates[Util.Random(0, genderCandidates.Count - 1)];
			escort.Race = (short)selectedRace.ID;
			escort.Gender = selectedGender;
			escort.Model = (ushort)selectedRace.GetModel(selectedGender);
		}

		private static PlayerRace[] GetEscortRaceCandidates(eRealm realm)
		{
			return realm switch
			{
				eRealm.Midgard => MidgardEscortRaces,
				eRealm.Hibernia => HiberniaEscortRaces,
				_ => AlbionEscortRaces
			};
		}

		private static GameNpcInventoryTemplate GetEscortInventoryTemplate(eRealm realm)
		{
			return realm switch
			{
				eRealm.Midgard => ClothingMgr.Midgard_Fighter,
				eRealm.Hibernia => ClothingMgr.Hibernia_Fighter,
				_ => ClothingMgr.Albion_Fighter
			};
		}

		private static bool AddEscortToWorld(GameNPC escort)
		{
			if (escort == null || !escort.AddToWorld())
				return false;

			PrepareEscortForConvoyMovement(escort);
			return true;
		}

		private static void PrepareEscortForConvoyMovement(GameNPC escort)
		{
			PrepareConvoyNpcForMovement(escort, EscortFollowMoveSpeed);
		}

		private static void PrepareWagonForConvoyMovement(SupplyConvoyWagon wagon)
		{
			PrepareConvoyNpcForMovement(wagon, ConvoyMoveSpeed);
		}

		private static void PrepareConvoyNpcForMovement(GameNPC npc, short moveSpeed)
		{
			while (npc.Brain is KeepGuardBrain keepBrain)
				npc.RemoveBrain(keepBrain);

			if (npc.Brain is not ConvoyMobBrain)
				npc.SetOwnBrain(new ConvoyMobBrain());

			if (npc.Brain is StandardMobBrain brain)
			{
				brain.AggroLevel = 0;
				brain.AggroRange = 0;
			}

			npc.RoamingRange = 0;
			npc.TetherRange = 0;
			npc.MaxSpeedBase = moveSpeed;
			npc.CancelReturnToSpawnPoint();
		}

		private static ushort GetRandomSupplyWagonModel()
		{
			return SupplyWagonModels[Util.Random(0, SupplyWagonModels.Length - 1)];
		}

		private static bool BeginConvoyMovement(ConvoyState state, out string message)
		{
			if (state?.Wagon == null)
			{
				message = "보급대 상태가 유효하지 않아 출발하지 못했습니다.";
				return false;
			}

			lock (ConvoyLock)
			{
				if (!ActiveConvoysByRealm.TryGetValue(state.Realm, out ConvoyState activeState) || activeState != state)
				{
					message = $"{RealmName(state.Realm)} 보급대가 이미 정리되어 출발하지 않습니다.";
					return false;
				}

				if (state.HasDeparted)
				{
					message = $"{RealmName(state.Realm)} 보급대가 이미 출발했습니다.";
					return false;
				}

				state.HasDeparted = true;
			}

			state.DepartureTimer?.Stop();
			state.DepartureTimer = null;

			if (state.Wagon.ObjectState != GameObject.eObjectState.Active || !state.Wagon.IsAlive)
			{
				message = $"{RealmName(state.Realm)} 보급대가 출발 전에 사라졌습니다.";
				return false;
			}

			if (state.TargetKeep.Realm != state.Realm)
			{
				message = $"{state.TargetKeep.Name}의 소유권이 바뀌어 {RealmName(state.Realm)} 보급대가 출발하지 않았습니다.";
				FinishConvoy(state, false, message);
				return false;
			}

			state.DepartedAt = DateTime.UtcNow;
			Broadcast($"{RealmName(state.Realm)} 보급대가 {state.OriginName}에서 {state.TargetKeep.Name}으로 출발했습니다.", eChatType.CT_ScreenCenter);
			MoveEscorts(state);
			StartConvoyTick(state);
			message = $"{RealmName(state.Realm)} 보급대가 출발했습니다.";
			return true;
		}

		private static void StartConvoyTick(ConvoyState state)
		{
			state.TickTimer = new ECSGameTimer(state.Wagon, _ =>
			{
				if (!TickConvoy(state))
					return 0;

				return TickMilliseconds;
			}, TickMilliseconds);
		}

		private static bool TickConvoy(ConvoyState state)
		{
			if (state?.Wagon == null || state.Wagon.ObjectState != GameObject.eObjectState.Active || !state.Wagon.IsAlive)
				return false;

			PrepareWagonForConvoyMovement(state.Wagon);

			if (state.TargetKeep.Realm != state.Realm)
			{
				FinishConvoy(state, false, $"{state.TargetKeep.Name}의 소유권이 바뀌어 {RealmName(state.Realm)} 보급대가 흩어졌습니다. 해당 킵은 미보급 상태로 약해진 채 남습니다.");
				return false;
			}

			RecordSupporterPresence(state);

			if (HasConvoyArrived(state))
			{
				FinishConvoy(state, true, $"{RealmName(state.Realm)} 보급대가 {state.TargetKeep.Name}에 도착했습니다. 미보급 약화가 해제되고 점령군의 방어 준비가 완료되었습니다.");
				return false;
			}

			Point3D nextPoint = GetNextRoutePoint(state);
			if (!IsValidPoint(state.Wagon.CurrentRegion, nextPoint))
				nextPoint = state.Destination;

			if (state.LastIssuedRouteIndex != state.RouteIndex || !state.Wagon.IsMoving)
			{
				state.Wagon.PathTo(nextPoint, ConvoyMoveSpeed);
				state.LastIssuedRouteIndex = state.RouteIndex;
			}

			MoveEscorts(state);
			return true;
		}

		private static bool HasConvoyArrived(ConvoyState state)
		{
			if (state?.Wagon == null || state.TargetKeep == null)
				return false;

			if (state.Wagon.CurrentRegionID == state.TargetKeep.Region
				&& state.TargetKeep.Area?.IsContaining(state.Wagon, false) == true)
			{
				return true;
			}

			return state.Wagon.GetDistanceTo(state.Destination, 0) <= ArrivalRadius;
		}

		private static Point3D GetNextRoutePoint(ConvoyState state)
		{
			if (state.Route == null || state.Route.Count == 0)
				return state.Destination;

			AdvanceRouteIndexPastReachedPoints(state);
			AdvanceRouteIndexPastPassedPoints(state);
			AdvanceRouteIndexPastReachedPoints(state);

			return state.Route[Math.Clamp(state.RouteIndex, 0, state.Route.Count - 1)];
		}

		private static void AdvanceRouteIndexPastReachedPoints(ConvoyState state)
		{
			while (state.RouteIndex < state.Route.Count - 1 && state.Wagon.GetDistanceTo(state.Route[state.RouteIndex], 0) <= PathNodeArrivalRadius)
				state.RouteIndex++;
		}

		private static void AdvanceRouteIndexPastPassedPoints(ConvoyState state)
		{
			while (state.RouteIndex < state.Route.Count - 1)
			{
				Point3D previousPoint = state.RouteIndex == 0 ? state.Origin : state.Route[state.RouteIndex - 1];
				Point3D currentPoint = state.Route[state.RouteIndex];
				if (!HasPassedRoutePoint(previousPoint, currentPoint, state.Wagon))
					return;

				state.RouteIndex++;
			}
		}

		private static bool HasPassedRoutePoint(IPoint3D previous, IPoint3D current, IPoint3D position)
		{
			if (previous == null || current == null || position == null)
				return false;

			double segmentX = current.X - previous.X;
			double segmentY = current.Y - previous.Y;
			double segmentLengthSquared = segmentX * segmentX + segmentY * segmentY;
			if (segmentLengthSquared <= 0)
				return false;

			double positionX = position.X - previous.X;
			double positionY = position.Y - previous.Y;
			double progress = (positionX * segmentX + positionY * segmentY) / segmentLengthSquared;
			return progress > 1.05;
		}

		private static void MoveEscorts(ConvoyState state)
		{
			for (int index = 0; index < state.Escorts.Count; index++)
			{
				GameNPC escort = state.Escorts[index];
				if (escort == null || escort.ObjectState != GameObject.eObjectState.Active || !escort.IsAlive)
					continue;

				PrepareEscortForConvoyMovement(escort);
				if (escort.Brain is StandardMobBrain escortBrain && escortBrain.HasAggro)
				{
					if (!ShouldEscortReturnToWagon(state, escort))
					{
						escort.MaxSpeedBase = EscortCatchUpMoveSpeed;
						continue;
					}

					ResetEscortCombat(escortBrain, escort);
				}

				FollowWagon(state, escort);
			}
		}

		private static void FollowWagon(ConvoyState state, GameNPC escort)
		{
			if (state?.Wagon == null || escort == null || state.Wagon.ObjectState != GameObject.eObjectState.Active)
				return;

			int distanceToWagon = escort.CurrentRegionID == state.Wagon.CurrentRegionID
				? escort.GetDistanceTo(state.Wagon, 0)
				: int.MaxValue;

			escort.MaxSpeedBase = distanceToWagon > EscortCatchUpDistance
				? EscortCatchUpMoveSpeed
				: EscortFollowMoveSpeed;

			escort.Follow(state.Wagon, EscortFollowMinDistance, EscortFollowMaxDistance);
		}

		private static bool ShouldEscortReturnToWagon(ConvoyState state, GameNPC escort)
		{
			return state?.Wagon == null
				|| escort.CurrentRegionID != state.Wagon.CurrentRegionID
				|| escort.GetDistanceTo(state.Wagon, 0) > EscortCombatLeashRadius;
		}

		private static void ResetEscortCombat(StandardMobBrain brain, GameNPC escort)
		{
			brain.Disengage();
			escort.StopFollowing();
			escort.StopMoving();
			escort.TargetObject = null;
			escort.CancelReturnToSpawnPoint();
		}

		private static Point3D GetEscortFormationPoint(ConvoyState state, int escortIndex)
		{
			Point3D nextPoint = state.Route != null && state.Route.Count > 0
				? state.Route[Math.Clamp(state.RouteIndex, 0, state.Route.Count - 1)]
				: state.Destination;

			double dx = nextPoint.X - state.Wagon.X;
			double dy = nextPoint.Y - state.Wagon.Y;
			double length = Math.Sqrt(dx * dx + dy * dy);
			if (length <= 0)
			{
				dx = Math.Cos(state.Wagon.Heading / 4096.0 * Math.PI * 2);
				dy = Math.Sin(state.Wagon.Heading / 4096.0 * Math.PI * 2);
				length = Math.Sqrt(dx * dx + dy * dy);
			}

			if (length <= 0)
				return new Point3D(state.Wagon.X, state.Wagon.Y, state.Wagon.Z);

			double forwardX = dx / length;
			double forwardY = dy / length;
			double sideX = -forwardY;
			double sideY = forwardX;
			double sideSign = escortIndex % 2 == 0 ? -1.0 : 1.0;

			int x = state.Wagon.X
				- (int)Math.Round(forwardX * EscortFormationBehindDistance)
				+ (int)Math.Round(sideX * EscortFormationSideDistance * sideSign);
			int y = state.Wagon.Y
				- (int)Math.Round(forwardY * EscortFormationBehindDistance)
				+ (int)Math.Round(sideY * EscortFormationSideDistance * sideSign);
			int z = ClientTerrainHeightSampler.TrySample(state.Wagon.CurrentRegion, x, y, out int terrainZ)
				? terrainZ
				: state.Wagon.Z;

			return new Point3D(x, y, z);
		}

		private static void DefendWagon(ConvoyState state, AttackData attackData)
		{
			if (state?.Wagon == null || attackData?.Attacker == null)
				return;

			GameLiving attacker = attackData.Attacker;
			if (!attacker.IsAlive || attacker.ObjectState != GameObject.eObjectState.Active || attacker == state.Wagon)
				return;

			if (attacker.CurrentRegionID != state.Wagon.CurrentRegionID || attacker.Realm is eRealm.None || attacker.Realm == state.Realm)
				return;

			if (attacker.GetDistanceTo(state.Wagon, 0) > EscortCombatLeashRadius)
				return;

			foreach (GameNPC escort in state.Escorts)
			{
				if (escort == null || escort.ObjectState != GameObject.eObjectState.Active || !escort.IsAlive)
					continue;

				if (escort.CurrentRegionID != state.Wagon.CurrentRegionID || escort.GetDistanceTo(state.Wagon, 0) > EscortDefenseRadius)
					continue;

				PrepareEscortForConvoyMovement(escort);
				if (escort.Brain is not StandardMobBrain brain)
					continue;

				escort.MaxSpeedBase = EscortCatchUpMoveSpeed;
				escort.StopFollowing();
				brain.AddToAggroList(attacker, Math.Max(1, attackData.Damage + attackData.CriticalDamage));
				escort.TargetObject = attacker;
				escort.StartAttack(attacker);
			}
		}

		private static void RecordInterceptorDamage(ConvoyState state, AttackData attackData)
		{
			if (state?.Wagon == null || attackData?.Attacker == null)
				return;

			int damage = Math.Max(0, attackData.Damage) + Math.Max(0, attackData.CriticalDamage);
			damage = Math.Min(damage, state.Wagon.Health);
			if (damage <= 0)
				return;

			GamePlayer player = GetRewardPlayer(attackData.Attacker);
			if (player == null || player.Realm is eRealm.None || player.Realm == state.Realm)
				return;

			if (attackData.Attacker.CurrentRegionID != state.Wagon.CurrentRegionID)
				return;

			state.InterceptorDamageByPlayer.TryGetValue(player, out long currentDamage);
			state.InterceptorDamageByPlayer[player] = currentDamage + damage;
		}

		private static GamePlayer GetRewardPlayer(GameLiving living)
		{
			if (living is GamePlayer player)
				return player;

			if (living is GameNPC npc && npc.Brain is IControlledBrain controlledBrain)
				return controlledBrain.GetPlayerOwner();

			return null;
		}

		private static void OnWagonDying(DOLEvent e, object sender, EventArgs args)
		{
			if (sender is not SupplyConvoyWagon wagon || wagon.State == null)
				return;

			string message = wagon.State.HasDeparted
				? $"{RealmName(wagon.State.Realm)} 보급대가 {wagon.State.TargetKeep.Name}으로 가는 길에 약탈당했습니다. {wagon.State.TargetKeep.Name}은 미보급 상태로 약해진 채 남습니다."
				: $"{RealmName(wagon.State.Realm)} 보급대가 출발 준비 중 약탈당했습니다. {wagon.State.TargetKeep.Name}은 미보급 상태로 약해진 채 남습니다.";

			FinishConvoy(wagon.State, false, message, true);
		}

		private static void FinishConvoy(ConvoyState state, bool success, string message, bool rewardAttackers = false)
		{
			lock (ConvoyLock)
			{
				if (!ActiveConvoysByRealm.TryGetValue(state.Realm, out ConvoyState activeState) || activeState != state)
					return;

				ActiveConvoysByRealm.Remove(state.Realm);
			}

			if (success)
			{
				lock (ConvoyLock)
					UndersuppliedKeepIds.Remove(state.TargetKeep.KeepID);

				RewardSupporters(state);
			}
			else if (rewardAttackers)
				RewardInterceptors(state);

			Broadcast(message, success ? eChatType.CT_ScreenCenter : eChatType.CT_Important);
			CleanupConvoy(state);
		}

		private static void RecordSupporterPresence(ConvoyState state)
		{
			foreach (GamePlayer player in ClientService.Instance.GetPlayers())
			{
				if (!IsRewardEligible(player, state.Realm, state.Wagon.CurrentRegionID, state.Wagon, true))
					continue;

				state.SupporterPresenceMilliseconds.TryGetValue(player, out long currentMilliseconds);
				state.SupporterPresenceMilliseconds[player] = currentMilliseconds + TickMilliseconds;
			}
		}

		private static void RewardSupporters(ConvoyState state)
		{
			long travelMilliseconds = GetConvoyTravelMilliseconds(state);
			if (travelMilliseconds <= 0)
				return;

			foreach (KeyValuePair<GamePlayer, long> pair in state.SupporterPresenceMilliseconds.ToList())
			{
				GamePlayer player = pair.Key;
				if (player == null || player.ObjectState != GameObject.eObjectState.Active || player.Realm != state.Realm)
					continue;

				long supportMilliseconds = Math.Clamp(pair.Value, 0, travelMilliseconds);
				double supportMinutes = supportMilliseconds / 60000.0;
				double participation = Math.Clamp(supportMilliseconds / (double)travelMilliseconds, 0.0, 1.0);
				long realmPointReward = (long)Math.Round(SupportRealmPointRewardPerMinute * supportMinutes);
				long bountyPointReward = (long)Math.Round(SupportBountyPointRewardPerMinute * supportMinutes);

				if (realmPointReward <= 0 && bountyPointReward <= 0)
					continue;

				if (realmPointReward > 0)
					player.GainRealmPoints(realmPointReward, true);

				if (bountyPointReward > 0)
					player.GainBountyPoints(bountyPointReward, false);

				player.Out.SendMessage($"보급대 호위 보상을 받았습니다. (호위 {supportMinutes:F1}분, 참여도 {participation:P0})", eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			}
		}

		private static long GetConvoyTravelMilliseconds(ConvoyState state)
		{
			if (state.DepartedAt == default)
				return 0;

			return Math.Max(TickMilliseconds, (long)(DateTime.UtcNow - state.DepartedAt).TotalMilliseconds);
		}

		private static void RewardInterceptors(ConvoyState state)
		{
			List<KeyValuePair<GamePlayer, long>> eligibleAttackers = state.InterceptorDamageByPlayer
				.Where(pair => pair.Value > 0 && IsRewardEligible(pair.Key, state.Realm, state.Wagon.CurrentRegionID, state.Wagon, false))
				.ToList();

			long totalDamage = eligibleAttackers.Sum(pair => pair.Value);
			if (totalDamage <= 0)
				return;

			foreach (KeyValuePair<GamePlayer, long> pair in eligibleAttackers)
			{
				GamePlayer player = pair.Key;
				double share = pair.Value / (double)totalDamage;
				long realmPointReward = (long)Math.Round(InterceptRealmPointReward * share);
				long bountyPointReward = (long)Math.Round(InterceptBountyPointReward * share);

				if (realmPointReward <= 0 && bountyPointReward <= 0)
					continue;

				if (realmPointReward > 0)
					player.GainRealmPoints(realmPointReward, true);

				if (bountyPointReward > 0)
					player.GainBountyPoints(bountyPointReward, false);

				player.Out.SendMessage($"보급대 약탈 보상을 받았습니다. (기여도 {share:P0})", eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			}
		}

		private static bool IsRewardEligible(GamePlayer player, eRealm convoyRealm, ushort regionId, IPoint3D point, bool sameRealm)
		{
			return player != null
				&& player.ObjectState == GameObject.eObjectState.Active
				&& player.IsAlive
				&& player.CurrentRegionID == regionId
				&& (sameRealm ? player.Realm == convoyRealm : player.Realm != eRealm.None && player.Realm != convoyRealm)
				&& player.GetDistanceTo(point, 0) <= RewardRadius;
		}

		private static void CleanupConvoy(ConvoyState state)
		{
			state.DepartureTimer?.Stop();
			state.TickTimer?.Stop();

			if (state.Wagon != null)
			{
				GameEventMgr.RemoveHandler(state.Wagon, GameLivingEvent.Dying, OnWagonDying);
				if (state.Wagon.ObjectState == GameObject.eObjectState.Active)
					state.Wagon.Delete();
			}

			foreach (GameNPC escort in state.Escorts)
			{
				if (escort?.ObjectState == GameObject.eObjectState.Active)
					escort.Delete();
			}
		}

		private static List<Point3D> BuildRoute(Region region, Point3D start, Point3D destination)
		{
			List<Point3D> route = TryBuildPathPointRoute(region, start, destination);
			if (route.Count > 0)
				return route;

			route = TryBuildGraphRoute(region, start, destination);
			if (route.Count > 0)
				return route;

			route = TryBuildNavmeshRoute(region, start, destination);
			if (route.Count > 0)
				return route;

			return new List<Point3D>();
		}

		private static List<Point3D> TryBuildNavmeshRoute(Region region, Point3D start, Point3D destination)
		{
			Zone startZone = region.GetZone(start.X, start.Y);
			Zone destinationZone = region.GetZone(destination.X, destination.Y);
			if (startZone == null || destinationZone == null || startZone.ID != destinationZone.ID)
				return new List<Point3D>();

			if (!startZone.IsPathfindingEnabled || !PathfindingProvider.Instance.HasNavmesh(startZone))
				return new List<Point3D>();

			if (!TrySnapToNavmesh(startZone, start, out Vector3 startVector) || !TrySnapToNavmesh(startZone, destination, out Vector3 destinationVector))
				return new List<Point3D>();

			WrappedPathfindingNode[] rentedNodes = ArrayPool<WrappedPathfindingNode>.Shared.Rent(NavmeshRouteNodeCapacity);
			try
			{
				PathfindingResult result = PathfindingProvider.Instance.GetPathStraight(
					startZone,
					startVector,
					destinationVector,
					PathfindingProvider.Instance.BlockingDoorAvoidanceFilters,
					rentedNodes.AsSpan(0, NavmeshRouteNodeCapacity));

				if (result.Status is not PathfindingStatus.PathFound || result.NodeCount <= 0)
					return new List<Point3D>();

				List<Point3D> route = new(result.NodeCount + 1);
				for (int index = 0; index < result.NodeCount; index++)
					route.Add(PointFromVector(rentedNodes[index].Position));

				return NormalizeRoute(start, destination, route);
			}
			finally
			{
				ArrayPool<WrappedPathfindingNode>.Shared.Return(rentedNodes);
			}
		}

		private static List<Point3D> TryBuildPathPointRoute(Region region, Point3D start, Point3D destination)
		{
			int minX = Math.Min(start.X, destination.X) - PathPointSearchPadding;
			int maxX = Math.Max(start.X, destination.X) + PathPointSearchPadding;
			int minY = Math.Min(start.Y, destination.Y) - PathPointSearchPadding;
			int maxY = Math.Max(start.Y, destination.Y) + PathPointSearchPadding;

			List<RoutePathPoint> pathPoints = PathPointRouteCache.GetPoints(region, minX, maxX, minY, maxY);
			if (pathPoints.Count == 0)
				return new List<Point3D>();

			List<Point3D> nodes = new(pathPoints.Count + 2) { start, destination };
			Dictionary<string, List<int>> byPath = new(StringComparer.OrdinalIgnoreCase);
			Dictionary<int, int> stepsByNode = new(pathPoints.Count);

			foreach (RoutePathPoint pathPoint in pathPoints)
			{
				int index = nodes.Count;
				nodes.Add(SnapPointToMinimapRoad(region, pathPoint.Point));
				stepsByNode[index] = pathPoint.Step;

				if (!byPath.TryGetValue(pathPoint.PathID, out List<int> pathIndexes))
				{
					pathIndexes = new List<int>();
					byPath[pathPoint.PathID] = pathIndexes;
				}

				pathIndexes.Add(index);
			}

			List<RouteEdge>[] edges = new List<RouteEdge>[nodes.Count];
			for (int index = 0; index < edges.Length; index++)
				edges[index] = new List<RouteEdge>();

			foreach (List<int> pathIndexes in byPath.Values)
			{
				pathIndexes.Sort((left, right) => stepsByNode[left].CompareTo(stepsByNode[right]));

				for (int index = 1; index < pathIndexes.Count; index++)
					TryAddRouteEdge(region, nodes, edges, pathIndexes[index - 1], pathIndexes[index], PathPointRouteCostMultiplier);
			}

			ConnectNearbyPathIntersections(region, nodes, edges);
			ConnectEndpointToPathPoints(region, nodes, edges, 0, pathPoints);
			ConnectEndpointToPathPoints(region, nodes, edges, 1, pathPoints);

			List<Point3D> route = SearchRouteGraph(nodes, edges, 0, 1);
			return route.Count > 0 ? NormalizeRoute(start, destination, route) : new List<Point3D>();
		}

		private static void ConnectEndpointToPathPoints(Region region, List<Point3D> nodes, List<RouteEdge>[] edges, int endpointIndex, List<RoutePathPoint> pathPoints)
		{
			Point3D endpoint = nodes[endpointIndex];
			foreach (int nodeIndex in Enumerable.Range(2, pathPoints.Count)
				.OrderBy(index => GetDistance(endpoint, nodes[index]))
				.Take(MaxPathPointEndpointConnections))
			{
				if (GetDistance(endpoint, nodes[nodeIndex]) > PathPointConnectorRadius)
					continue;

				TryAddRouteEdge(region, nodes, edges, endpointIndex, nodeIndex, PathPointConnectorCostMultiplier);
			}
		}

		private static void ConnectNearbyPathIntersections(Region region, List<Point3D> nodes, List<RouteEdge>[] edges)
		{
			Dictionary<RouteGraphNode, List<int>> buckets = new();
			for (int index = 2; index < nodes.Count; index++)
			{
				RouteGraphNode bucket = new(nodes[index].X / PathPointBucketSize, nodes[index].Y / PathPointBucketSize);
				if (!buckets.TryGetValue(bucket, out List<int> bucketNodes))
				{
					bucketNodes = new List<int>();
					buckets[bucket] = bucketNodes;
				}

				bucketNodes.Add(index);
			}

			for (int leftIndex = 2; leftIndex < nodes.Count; leftIndex++)
			{
				RouteGraphNode bucket = new(nodes[leftIndex].X / PathPointBucketSize, nodes[leftIndex].Y / PathPointBucketSize);
				for (int dx = -1; dx <= 1; dx++)
				{
					for (int dy = -1; dy <= 1; dy++)
					{
						if (!buckets.TryGetValue(new RouteGraphNode(bucket.X + dx, bucket.Y + dy), out List<int> bucketNodes))
							continue;

						foreach (int rightIndex in bucketNodes)
						{
							if (rightIndex <= leftIndex || GetDistance(nodes[leftIndex], nodes[rightIndex]) > PathPointIntersectionRadius)
								continue;

							TryAddRouteEdge(region, nodes, edges, leftIndex, rightIndex, PathPointIntersectionCostMultiplier);
						}
					}
				}
			}
		}

		private static void TryAddRouteEdge(Region region, List<Point3D> nodes, List<RouteEdge>[] edges, int left, int right, double multiplier)
		{
			if (!TryGetSegmentCost(region, nodes[left], nodes[right], out double cost))
				return;

			double weightedCost = cost * multiplier;
			edges[left].Add(new RouteEdge(right, weightedCost));
			edges[right].Add(new RouteEdge(left, weightedCost));
		}

		private static List<Point3D> SearchRouteGraph(List<Point3D> nodes, List<RouteEdge>[] edges, int startIndex, int destinationIndex)
		{
			PriorityQueue<int, double> open = new();
			Dictionary<int, int> cameFrom = new();
			Dictionary<int, double> gScore = new() { [startIndex] = 0 };
			HashSet<int> closed = new();

			open.Enqueue(startIndex, GetDistance(nodes[startIndex], nodes[destinationIndex]));

			while (open.Count > 0)
			{
				int current = open.Dequeue();
				if (!closed.Add(current))
					continue;

				if (current == destinationIndex)
					return ReconstructRoute(cameFrom, nodes, destinationIndex);

				foreach (RouteEdge edge in edges[current])
				{
					if (closed.Contains(edge.To))
						continue;

					double tentativeScore = gScore[current] + edge.Cost;
					if (gScore.TryGetValue(edge.To, out double oldScore) && tentativeScore >= oldScore)
						continue;

					cameFrom[edge.To] = current;
					gScore[edge.To] = tentativeScore;
					open.Enqueue(edge.To, tentativeScore + GetDistance(nodes[edge.To], nodes[destinationIndex]));
				}
			}

			return new List<Point3D>();
		}

		private static List<Point3D> ReconstructRoute(Dictionary<int, int> cameFrom, List<Point3D> nodes, int current)
		{
			List<Point3D> route = new() { nodes[current] };
			while (cameFrom.TryGetValue(current, out int previous))
			{
				current = previous;
				route.Add(nodes[current]);
			}

			route.Reverse();
			return route;
		}

		private static List<Point3D> TryBuildGraphRoute(Region region, Point3D start, Point3D destination)
		{
			int minX = Math.Min(start.X, destination.X) - GraphSearchPadding;
			int maxX = Math.Max(start.X, destination.X) + GraphSearchPadding;
			int minY = Math.Min(start.Y, destination.Y) - GraphSearchPadding;
			int maxY = Math.Max(start.Y, destination.Y) + GraphSearchPadding;

			RouteGraphNode startNode = new(start.X, start.Y);
			RouteGraphNode destinationNode = new(destination.X, destination.Y);
			PriorityQueue<RouteGraphNode, double> open = new();
			Dictionary<RouteGraphNode, RouteGraphNode> cameFrom = new();
			Dictionary<RouteGraphNode, double> gScore = new() { [startNode] = 0 };
			Dictionary<RouteGraphNode, Point3D> points = new() { [startNode] = start, [destinationNode] = destination };
			HashSet<RouteGraphNode> closed = new();

			open.Enqueue(startNode, GetDistance(start, destination));

			for (int iterations = 0; open.Count > 0 && iterations < GraphSearchMaxIterations; iterations++)
			{
				RouteGraphNode current = open.Dequeue();
				if (!closed.Add(current))
					continue;

				Point3D currentPoint = points[current];
				if (GetDistance(currentPoint, destination) <= GraphStepDistance
					&& TryGetSegmentCost(region, currentPoint, destination, out _))
				{
					cameFrom[destinationNode] = current;
					return NormalizeRoute(start, destination, ReconstructGraphRoute(cameFrom, points, destinationNode));
				}

				foreach (RouteGraphNode neighbor in GetGraphNeighbors(current, minX, maxX, minY, maxY))
				{
					if (closed.Contains(neighbor))
						continue;

					if (!points.TryGetValue(neighbor, out Point3D neighborPoint))
					{
						if (!TryCreateGraphPoint(region, start, destination, neighbor.X, neighbor.Y, out neighborPoint))
							continue;

						points[neighbor] = neighborPoint;
					}

					if (!TryGetSegmentCost(region, currentPoint, neighborPoint, out double segmentCost))
						continue;

					double tentativeScore = gScore[current] + segmentCost;
					if (gScore.TryGetValue(neighbor, out double oldScore) && tentativeScore >= oldScore)
						continue;

					cameFrom[neighbor] = current;
					gScore[neighbor] = tentativeScore;
					double priority = tentativeScore + GetDistance(neighborPoint, destination);
					open.Enqueue(neighbor, priority);
				}
			}

			return new List<Point3D>();
		}

		private static IEnumerable<RouteGraphNode> GetGraphNeighbors(RouteGraphNode node, int minX, int maxX, int minY, int maxY)
		{
			for (int dx = -1; dx <= 1; dx++)
			{
				for (int dy = -1; dy <= 1; dy++)
				{
					if (dx == 0 && dy == 0)
						continue;

					int x = node.X + dx * GraphStepDistance;
					int y = node.Y + dy * GraphStepDistance;
					if (x < minX || x > maxX || y < minY || y > maxY)
						continue;

					yield return new RouteGraphNode(x, y);
				}
			}
		}

		private static bool TryCreateGraphPoint(Region region, Point3D start, Point3D destination, int x, int y, out Point3D point)
		{
			if (ClientMinimapRoadSampler.TrySnapToRoad(region, x, y, out int snappedX, out int snappedY))
			{
				x = snappedX;
				y = snappedY;
			}

			Zone zone = region.GetZone(x, y);
			if (zone == null)
			{
				point = null;
				return false;
			}

			int z = ClientTerrainHeightSampler.TrySample(region, x, y, out int terrainZ)
				? terrainZ
				: ProjectZ(start, destination, x, y);

			point = new Point3D(x, y, z);
			if (zone.IsPathfindingEnabled && PathfindingProvider.Instance.HasNavmesh(zone))
			{
				if (!TrySnapToNavmesh(zone, point, out Vector3 vector))
					return false;

				point = PointFromVector(vector);
			}

			return IsValidPoint(region, point);
		}

		private static Point3D SnapPointToMinimapRoad(Region region, Point3D point)
		{
			if (point == null || !ClientMinimapRoadSampler.TrySnapToRoad(region, point.X, point.Y, out int snappedX, out int snappedY))
				return point;

			int z = ClientTerrainHeightSampler.TrySample(region, snappedX, snappedY, out int terrainZ)
				? terrainZ
				: point.Z;

			return new Point3D(snappedX, snappedY, z);
		}

		private static List<Point3D> ReconstructGraphRoute(
			Dictionary<RouteGraphNode, RouteGraphNode> cameFrom,
			Dictionary<RouteGraphNode, Point3D> points,
			RouteGraphNode current)
		{
			List<Point3D> route = new() { points[current] };
			while (cameFrom.TryGetValue(current, out RouteGraphNode previous))
			{
				current = previous;
				route.Add(points[current]);
			}

			route.Reverse();
			return route;
		}

		private static bool TryGetSegmentCost(Region region, Point3D from, Point3D to, out double cost)
		{
			cost = GetDistance(from, to);
			if (cost <= 0)
				return false;

			Zone fromZone = region.GetZone(from.X, from.Y);
			Zone toZone = region.GetZone(to.X, to.Y);
			if (fromZone == null || toZone == null)
				return false;

			bool hasMinimapRoadScore = ClientMinimapRoadSampler.TryGetSegmentRoadScore(region, from, to, out double minimapRoadScore);
			bool minimapRoadPreferred = hasMinimapRoadScore && minimapRoadScore >= MinimapWeakRoadScore;
			bool hasTerrainCost = TryGetTerrainSegmentCost(region, from, to, minimapRoadPreferred, out double terrainCost);

			if (fromZone.ID == toZone.ID && TryGetNavmeshSegmentCost(fromZone, from, to, out double navmeshCost))
			{
				cost = hasTerrainCost ? Math.Max(navmeshCost, terrainCost) * 0.55 : navmeshCost * 0.55;
			}
			else
			{
				if (hasTerrainCost)
				{
					cost = terrainCost * (fromZone.ID == toZone.ID ? FallbackSameZoneCostMultiplier : FallbackCrossZoneCostMultiplier);
				}
				else
				{
					int maxZDelta = fromZone.ID == toZone.ID ? MaxFallbackSegmentZDelta : MaxPreferredSegmentZDelta;
					if (!IsSafeHeightDelta(from, to, maxZDelta))
						return false;

					cost *= fromZone.ID == toZone.ID ? FallbackSameZoneCostMultiplier : FallbackCrossZoneCostMultiplier;
				}
			}

			Zone zone = region.GetZone(to.X, to.Y);
			if (zone != null && zone.Waterlevel > to.Z + 64)
				cost *= 2.5;

			if (hasMinimapRoadScore)
			{
				if (minimapRoadScore >= MinimapStrongRoadScore)
					cost *= MinimapStrongRoadCostMultiplier;
				else if (minimapRoadScore >= MinimapWeakRoadScore)
					cost *= MinimapWeakRoadCostMultiplier;
				else
					cost *= MinimapOffRoadCostMultiplier;
			}

			return true;
		}

		private static bool TryGetTerrainSegmentCost(Region region, Point3D from, Point3D to, bool minimapRoadPreferred, out double cost)
		{
			cost = GetDistance(from, to);
			if (cost <= 0)
				return false;

			int samples = Math.Max(1, (int)Math.Ceiling(cost / TerrainSampleSpacing));
			if (!ClientTerrainHeightSampler.TrySample(region, from.X, from.Y, out int startZ)
				|| !ClientTerrainHeightSampler.TrySample(region, to.X, to.Y, out int endZ))
			{
				return false;
			}

			int maxSegmentZDelta = minimapRoadPreferred ? MaxTerrainRoadSegmentZDelta : MaxTerrainSegmentZDelta;
			int maxSampleZDelta = minimapRoadPreferred ? MaxTerrainRoadSampleZDelta : MaxTerrainSampleZDelta;

			if (Math.Abs(endZ - startZ) > maxSegmentZDelta)
				return false;

			double totalClimb = 0;
			int previousZ = startZ;

			for (int index = 1; index <= samples; index++)
			{
				double progress = index / (double)samples;
				int x = from.X + (int)Math.Round((to.X - from.X) * progress);
				int y = from.Y + (int)Math.Round((to.Y - from.Y) * progress);

				if (!ClientTerrainHeightSampler.TrySample(region, x, y, out int sampledZ))
					return false;

				int delta = Math.Abs(sampledZ - previousZ);
				if (delta > maxSampleZDelta)
					return false;

				totalClimb += delta;
				previousZ = sampledZ;
			}

			cost += totalClimb * TerrainClimbCostMultiplier;
			return true;
		}

		private static bool TryGetNavmeshSegmentCost(Zone zone, Point3D from, Point3D to, out double cost)
		{
			cost = 0;
			if (zone == null || !zone.IsPathfindingEnabled || !PathfindingProvider.Instance.HasNavmesh(zone))
				return false;

			if (!TrySnapToNavmesh(zone, from, out Vector3 fromVector) || !TrySnapToNavmesh(zone, to, out Vector3 toVector))
				return false;

			WrappedPathfindingNode[] rentedNodes = ArrayPool<WrappedPathfindingNode>.Shared.Rent(64);
			try
			{
				PathfindingResult result = PathfindingProvider.Instance.GetPathStraight(
					zone,
					fromVector,
					toVector,
					PathfindingProvider.Instance.BlockingDoorAvoidanceFilters,
					rentedNodes.AsSpan(0, 64));

				if (result.Status is not PathfindingStatus.PathFound || result.NodeCount <= 0)
					return false;

				Vector3 previous = fromVector;
				for (int index = 0; index < result.NodeCount; index++)
				{
					Vector3 current = rentedNodes[index].Position;
					if (Math.Abs(current.Z - previous.Z) > MaxFallbackSegmentZDelta)
						return false;

					cost += Vector3.Distance(previous, current);
					previous = current;
				}

				if (Math.Abs(toVector.Z - previous.Z) > MaxFallbackSegmentZDelta)
					return false;

				cost += Vector3.Distance(previous, toVector);
				return cost > 0;
			}
			finally
			{
				ArrayPool<WrappedPathfindingNode>.Shared.Return(rentedNodes);
			}
		}

		private static bool TrySnapToNavmesh(Zone zone, Point3D point, out Vector3 vector)
		{
			vector = new Vector3(point.X, point.Y, point.Z);
			return zone != null
				&& zone.IsPathfindingEnabled
				&& PathfindingProvider.Instance.HasNavmesh(zone)
				&& PathfindingProvider.Instance.TrySnapToMesh(zone, ref vector, PathSnapRange);
		}

		private static bool IsSafeHeightDelta(IPoint3D from, IPoint3D to, int maxDelta)
		{
			return Math.Abs(from.Z - to.Z) <= maxDelta;
		}

		private static List<Point3D> NormalizeRoute(Point3D start, Point3D destination, List<Point3D> route)
		{
			List<Point3D> normalized = new(route.Count + 1);
			foreach (Point3D point in route)
			{
				if (point == null || GetDistance(point, start) <= PathNodeArrivalRadius)
					continue;

				if (normalized.Count > 0 && GetDistance(normalized[normalized.Count - 1], point) <= PathNodeArrivalRadius)
					continue;

				normalized.Add(point);
			}

			if (normalized.Count == 0 || GetDistance(normalized[normalized.Count - 1], destination) > PathNodeArrivalRadius)
				normalized.Add(destination);

			return normalized;
		}

		private static bool IsUsablePathResult(PathfindingStatus status)
		{
			return status is PathfindingStatus.PathFound or PathfindingStatus.PartialPathFound or PathfindingStatus.BufferTooSmall;
		}

		private static Point3D PointFromVector(Vector3 vector)
		{
			return new Point3D((int)Math.Round(vector.X), (int)Math.Round(vector.Y), (int)Math.Round(vector.Z));
		}

		private static int ProjectZ(Point3D start, Point3D destination, int x, int y)
		{
			double total = Math.Max(1, GetDistance(start, destination));
			double current = Math.Min(total, GetDistance(start, new Point3D(x, y, start.Z)));
			double progress = current / total;
			return start.Z + (int)((destination.Z - start.Z) * progress);
		}

		private static Point3D GetOffsetPoint(IPoint3D origin, IPoint3D target, int offset)
		{
			double dx = target.X - origin.X;
			double dy = target.Y - origin.Y;
			double length = Math.Sqrt(dx * dx + dy * dy);
			if (length <= 0)
				return new Point3D(origin);

			int x = origin.X + (int)(dx / length * offset);
			int y = origin.Y + (int)(dy / length * offset);
			return new Point3D(x, y, origin.Z);
		}

		private static Point3D KeepPoint(AbstractGameKeep keep)
		{
			return new Point3D(keep.X, keep.Y, keep.Z);
		}

		private static int GetDistance(AbstractGameKeep origin, AbstractGameKeep target)
		{
			return KeepPoint(origin).GetDistanceTo(KeepPoint(target));
		}

		private static int GetDistance(IPoint3D origin, IPoint3D target)
		{
			return new Point3D(origin).GetDistanceTo(target);
		}

		private static Point3D GetStepPoint(IPoint3D origin, IPoint3D target, int stepDistance)
		{
			double dx = target.X - origin.X;
			double dy = target.Y - origin.Y;
			double length = Math.Sqrt(dx * dx + dy * dy);
			if (length <= stepDistance || length <= 0)
				return new Point3D(target.X, target.Y, target.Z);

			int x = origin.X + (int)(dx / length * stepDistance);
			int y = origin.Y + (int)(dy / length * stepDistance);
			int z = origin.Z + (int)((target.Z - origin.Z) * (stepDistance / length));
			return new Point3D(x, y, z);
		}

		private static bool IsValidPoint(Region region, Point3D point)
		{
			return region != null && point != null && region.GetZone(point.X, point.Y) != null;
		}

		private static void Broadcast(string message, eChatType chatType)
		{
			foreach (GamePlayer player in ClientService.Instance.GetPlayers())
				player.Out.SendMessage(message, chatType, eChatLoc.CL_SystemWindow);
		}

		private static string RealmName(eRealm realm)
		{
			return GlobalConstants.RealmToName(realm);
		}

		private static string RealmCommandName(eRealm realm)
		{
			return realm switch
			{
				eRealm.Albion => "albion",
				eRealm.Midgard => "midgard",
				eRealm.Hibernia => "hibernia",
				_ => realm.ToString().ToLowerInvariant()
			};
		}

		private static class ClientMinimapRoadSampler
		{
			private static readonly object Sync = new();
			private static readonly Dictionary<ushort, DdsRoadMap> Maps = new();
			private static readonly HashSet<ushort> MissingZones = new();
			private static string MapsRoot;

			public static bool TryGetSegmentRoadScore(Region region, Point3D from, Point3D to, out double score)
			{
				score = 0;
				if (region == null || from == null || to == null)
					return false;

				double distance = GetDistance(from, to);
				if (distance <= 0)
					return false;

				int samples = Math.Max(1, (int)Math.Ceiling(distance / MinimapRoadSampleSpacing));
				double totalScore = 0;
				int validSamples = 0;
				int roadSamples = 0;

				for (int index = 0; index <= samples; index++)
				{
					double progress = index / (double)samples;
					int x = from.X + (int)Math.Round((to.X - from.X) * progress);
					int y = from.Y + (int)Math.Round((to.Y - from.Y) * progress);

					if (!TryGetPointRoadScore(region, x, y, out double pointScore))
						continue;

					totalScore += pointScore;
					validSamples++;
					if (pointScore >= MinimapWeakRoadScore)
						roadSamples++;
				}

				if (validSamples == 0)
					return false;

				double averageScore = totalScore / validSamples;
				double roadCoverage = roadSamples / (double)validSamples;
				score = averageScore * roadCoverage;
				return true;
			}

			public static bool TrySnapToRoad(Region region, int worldX, int worldY, out int snappedX, out int snappedY)
			{
				snappedX = worldX;
				snappedY = worldY;

				Zone zone = region?.GetZone(worldX, worldY);
				if (zone == null)
					return false;

				DdsRoadMap map = GetMap(zone.ID);
				return map != null && map.TrySnapToRoad(zone, worldX, worldY, out snappedX, out snappedY);
			}

			private static bool TryGetPointRoadScore(Region region, int worldX, int worldY, out double score)
			{
				score = 0;

				Zone zone = region?.GetZone(worldX, worldY);
				if (zone == null)
					return false;

				DdsRoadMap map = GetMap(zone.ID);
				return map != null && map.TryGetRoadScore(zone, worldX, worldY, out score);
			}

			private static DdsRoadMap GetMap(ushort zoneId)
			{
				lock (Sync)
				{
					if (Maps.TryGetValue(zoneId, out DdsRoadMap cached))
						return cached;

					if (MissingZones.Contains(zoneId))
						return null;

					DdsRoadMap loaded = LoadMap(zoneId);
					if (loaded == null)
					{
						MissingZones.Add(zoneId);
						return null;
					}

					Maps[zoneId] = loaded;
					return loaded;
				}
			}

			private static DdsRoadMap LoadMap(ushort zoneId)
			{
				string mapsRoot = GetMapsRoot();
				if (string.IsNullOrEmpty(mapsRoot))
					return null;

				string mapPath = FindMapPath(mapsRoot, zoneId);
				if (mapPath == null)
					return null;

				try
				{
					return new DdsRoadMap(File.ReadAllBytes(mapPath));
				}
				catch
				{
					return null;
				}
			}

			private static string GetMapsRoot()
			{
				if (!string.IsNullOrEmpty(MapsRoot) && Directory.Exists(MapsRoot))
					return MapsRoot;

				foreach (string candidate in GetMapRootCandidates())
				{
					if (string.IsNullOrWhiteSpace(candidate))
						continue;

					string fullPath = Path.GetFullPath(candidate);
					if (!Directory.Exists(fullPath))
						continue;

					MapsRoot = fullPath;
					return MapsRoot;
				}

				return null;
			}

			private static IEnumerable<string> GetMapRootCandidates()
			{
				string serverRoot = GameServer.Instance?.Configuration?.RootDirectory;
				if (!string.IsNullOrWhiteSpace(serverRoot))
				{
					yield return Path.Combine(serverRoot, "..", "OpenDAoCClient", "ui", "maps");
					yield return Path.Combine(serverRoot, "..", "..", "OpenDAoCClient", "ui", "maps");
					yield return Path.Combine(serverRoot, "OpenDAoCClient", "ui", "maps");
				}

				string current = Directory.GetCurrentDirectory();
				yield return Path.Combine(current, "..", "OpenDAoCClient", "ui", "maps");
				yield return Path.Combine(current, "OpenDAoCClient", "ui", "maps");

				string baseDirectory = AppDomain.CurrentDomain.BaseDirectory;
				yield return Path.Combine(baseDirectory, "..", "..", "OpenDAoCClient", "ui", "maps");
				yield return Path.Combine(baseDirectory, "..", "..", "..", "OpenDAoCClient", "ui", "maps");
				yield return Path.Combine(baseDirectory, "..", "..", "..", "..", "OpenDAoCClient", "ui", "maps");
			}

			private static string FindMapPath(string mapsRoot, ushort zoneId)
			{
				string zoneNumber = zoneId.ToString("D3");
				foreach (string fileName in new[] { $"z{zoneNumber}.dds", $"z{zoneNumber}.DDS", $"Z{zoneNumber}.dds", $"Z{zoneNumber}.DDS" })
				{
					string candidate = Path.Combine(mapsRoot, fileName);
					if (File.Exists(candidate))
						return candidate;
				}

				return null;
			}
		}

		private sealed class DdsRoadMap
		{
			private readonly byte[] Pixels;
			private readonly bool HasRedRoadPixels;

			public DdsRoadMap(byte[] data)
			{
				if (data == null || data.Length < 136)
					throw new ArgumentException("Invalid DDS data.", nameof(data));

				if (!Encoding.ASCII.GetString(data, 0, 4).Equals("DDS ", StringComparison.Ordinal))
					throw new ArgumentException("Invalid DDS magic.", nameof(data));

				Height = (int)BitConverter.ToUInt32(data, 12);
				Width = (int)BitConverter.ToUInt32(data, 16);
				string fourCC = Encoding.ASCII.GetString(data, 84, 4);
				if (!fourCC.Equals("DXT1", StringComparison.Ordinal))
					throw new ArgumentException("Only DXT1 minimap DDS files are supported.", nameof(data));

				Pixels = DecodeDxt1(data, Width, Height);
				HasRedRoadPixels = CountRedRoadPixels() > 32;
			}

			public int Width { get; }
			public int Height { get; }

			public bool TryGetRoadScore(Zone zone, int worldX, int worldY, out double score)
			{
				score = 0;
				if (zone == null || Pixels == null)
					return false;

				if (!TryWorldToPixel(zone, worldX, worldY, out int centerX, out int centerY))
					return false;

				for (int dx = -MinimapRoadPixelSearchRadius; dx <= MinimapRoadPixelSearchRadius; dx++)
				{
					for (int dy = -MinimapRoadPixelSearchRadius; dy <= MinimapRoadPixelSearchRadius; dy++)
					{
						int x = centerX + dx;
						int y = centerY + dy;
						if (x < 0 || x >= Width || y < 0 || y >= Height)
							continue;

						score = Math.Max(score, GetRoadColorScore(x, y));
						if (score >= 1.0)
							return true;
					}
				}

				return true;
			}

			public bool TrySnapToRoad(Zone zone, int worldX, int worldY, out int snappedX, out int snappedY)
			{
				snappedX = worldX;
				snappedY = worldY;
				if (zone == null || Pixels == null || !TryWorldToPixel(zone, worldX, worldY, out int centerX, out int centerY))
					return false;

				int bestX = 0;
				int bestY = 0;
				int bestDistanceSquared = int.MaxValue;
				double bestScore = 0;

				for (int radius = 0; radius <= MinimapRoadSnapPixelRadius; radius++)
				{
					for (int dx = -radius; dx <= radius; dx++)
					{
						for (int dy = -radius; dy <= radius; dy++)
						{
							if (Math.Max(Math.Abs(dx), Math.Abs(dy)) != radius)
								continue;

							int x = centerX + dx;
							int y = centerY + dy;
							if (x < 0 || x >= Width || y < 0 || y >= Height)
								continue;

							double score = GetRoadColorScore(x, y);
							if (score <= 0)
								continue;

							int distanceSquared = dx * dx + dy * dy;
							if (score < bestScore || (Math.Abs(score - bestScore) < 0.001 && distanceSquared >= bestDistanceSquared))
								continue;

							bestScore = score;
							bestDistanceSquared = distanceSquared;
							bestX = x;
							bestY = y;
						}
					}

					if (bestScore >= 1.0)
						break;
				}

				if (bestScore <= 0)
					return false;

				PixelToWorld(zone, bestX, bestY, out snappedX, out snappedY);
				return true;
			}

			private bool TryWorldToPixel(Zone zone, int worldX, int worldY, out int pixelX, out int pixelY)
			{
				pixelX = 0;
				pixelY = 0;

				int localX = worldX - zone.XOffset;
				int localY = worldY - zone.YOffset;
				if (localX < 0 || localY < 0 || localX > zone.Width || localY > zone.Height)
					return false;

				double xPixel = localX / Math.Max(1.0, zone.Width / (double)Width);
				double yPixel = localY / Math.Max(1.0, zone.Height / (double)Height);
				pixelX = Math.Clamp((int)Math.Round(xPixel), 0, Width - 1);
				pixelY = Math.Clamp((int)Math.Round(yPixel), 0, Height - 1);
				return true;
			}

			private void PixelToWorld(Zone zone, int pixelX, int pixelY, out int worldX, out int worldY)
			{
				double worldPerPixelX = zone.Width / (double)Width;
				double worldPerPixelY = zone.Height / (double)Height;
				worldX = zone.XOffset + (int)Math.Round((pixelX + 0.5) * worldPerPixelX);
				worldY = zone.YOffset + (int)Math.Round((pixelY + 0.5) * worldPerPixelY);
			}

			private int CountRedRoadPixels()
			{
				int count = 0;
				for (int index = 0; index < Width * Height; index++)
				{
					GetPixel(index, out byte r, out byte g, out byte b);
					if (IsRedRoadColor(r, g, b))
						count++;
				}

				return count;
			}

			private double GetRoadColorScore(int x, int y)
			{
				GetPixel(y * Width + x, out byte r, out byte g, out byte b);
				if (IsRedRoadColor(r, g, b))
					return 1.0;

				if (!HasRedRoadPixels && IsMutedRoadColor(r, g, b))
					return 0.45;

				return 0;
			}

			private void GetPixel(int index, out byte r, out byte g, out byte b)
			{
				int offset = index * 3;
				r = Pixels[offset];
				g = Pixels[offset + 1];
				b = Pixels[offset + 2];
			}

			private static bool IsRedRoadColor(byte r, byte g, byte b)
			{
				return r >= 58 && r > g + 16 && r > b + 16 && g <= 125 && b <= 115;
			}

			private static bool IsMutedRoadColor(byte r, byte g, byte b)
			{
				int max = Math.Max(r, Math.Max(g, b));
				int min = Math.Min(r, Math.Min(g, b));
				return max - min <= 28 && max >= 72 && max <= 165 && min >= 55;
			}

			private static byte[] DecodeDxt1(byte[] data, int width, int height)
			{
				byte[] pixels = new byte[width * height * 3];
				int cursor = 128;

				for (int blockY = 0; blockY < height; blockY += 4)
				{
					for (int blockX = 0; blockX < width; blockX += 4)
					{
						if (cursor + 8 > data.Length)
							throw new ArgumentException("Truncated DXT1 image data.", nameof(data));

						ushort color0 = BitConverter.ToUInt16(data, cursor);
						ushort color1 = BitConverter.ToUInt16(data, cursor + 2);
						uint codes = BitConverter.ToUInt32(data, cursor + 4);
						cursor += 8;

						byte[] palette = new byte[12];
						SetPaletteColor(palette, 0, color0);
						SetPaletteColor(palette, 1, color1);

						if (color0 > color1)
						{
							InterpolatePaletteColor(palette, 2, 0, 1, 2, 1, 3);
							InterpolatePaletteColor(palette, 3, 0, 1, 1, 2, 3);
						}
						else
						{
							InterpolatePaletteColor(palette, 2, 0, 1, 1, 1, 2);
							palette[9] = 0;
							palette[10] = 0;
							palette[11] = 0;
						}

						for (int py = 0; py < 4; py++)
						{
							for (int px = 0; px < 4; px++)
							{
								int x = blockX + px;
								int y = blockY + py;
								if (x >= width || y >= height)
									continue;

								int paletteIndex = (int)((codes >> (2 * (py * 4 + px))) & 0x03);
								int sourceOffset = paletteIndex * 3;
								int targetOffset = (y * width + x) * 3;
								pixels[targetOffset] = palette[sourceOffset];
								pixels[targetOffset + 1] = palette[sourceOffset + 1];
								pixels[targetOffset + 2] = palette[sourceOffset + 2];
							}
						}
					}
				}

				return pixels;
			}

			private static void SetPaletteColor(Span<byte> palette, int index, ushort color)
			{
				int offset = index * 3;
				palette[offset] = (byte)Math.Round(((color >> 11) & 0x1F) * 255 / 31.0);
				palette[offset + 1] = (byte)Math.Round(((color >> 5) & 0x3F) * 255 / 63.0);
				palette[offset + 2] = (byte)Math.Round((color & 0x1F) * 255 / 31.0);
			}

			private static void InterpolatePaletteColor(Span<byte> palette, int targetIndex, int leftIndex, int rightIndex, int leftWeight, int rightWeight, int divisor)
			{
				int targetOffset = targetIndex * 3;
				int leftOffset = leftIndex * 3;
				int rightOffset = rightIndex * 3;
				for (int channel = 0; channel < 3; channel++)
				{
					int value = palette[leftOffset + channel] * leftWeight + palette[rightOffset + channel] * rightWeight;
					palette[targetOffset + channel] = (byte)Math.Round(value / (double)divisor);
				}
			}
		}

		private static class ClientTerrainHeightSampler
		{
			private static readonly object Sync = new();
			private static readonly Dictionary<ushort, ClientTerrainMap> Maps = new();
			private static readonly HashSet<ushort> MissingZones = new();
			private static string ZonesRoot;

			public static bool TrySample(Region region, int worldX, int worldY, out int height)
			{
				height = 0;

				Zone zone = region?.GetZone(worldX, worldY);
				if (zone == null)
					return false;

				ClientTerrainMap map = GetMap(zone.ID);
				return map != null && map.TrySample(zone, worldX, worldY, out height);
			}

			private static ClientTerrainMap GetMap(ushort zoneId)
			{
				lock (Sync)
				{
					if (Maps.TryGetValue(zoneId, out ClientTerrainMap cached))
						return cached;

					if (MissingZones.Contains(zoneId))
						return null;

					ClientTerrainMap loaded = LoadMap(zoneId);
					if (loaded == null)
					{
						MissingZones.Add(zoneId);
						return null;
					}

					Maps[zoneId] = loaded;
					return loaded;
				}
			}

			private static ClientTerrainMap LoadMap(ushort zoneId)
			{
				string zonesRoot = GetZonesRoot();
				if (string.IsNullOrEmpty(zonesRoot))
					return null;

				string zonePath = FindZonePath(zonesRoot, zoneId);
				if (zonePath == null)
					return null;

				string zoneNumber = zoneId.ToString("D3");
				string datPath = Path.Combine(zonePath, $"dat{zoneNumber}.mpk");
				if (!File.Exists(datPath))
					return null;

				try
				{
					MpkHandler archive = new(datPath, false);
					byte[] terrain = archive["terrain.pcx"]?.Data;
					byte[] offset = archive["offset.pcx"]?.Data;
					if (terrain == null || offset == null)
						return null;

					ReadTerrainScale(archive["sector.dat"]?.Data, out int scaleFactor, out int offsetFactor);
					return new ClientTerrainMap(new PcxMap(terrain), new PcxMap(offset), scaleFactor, offsetFactor);
				}
				catch
				{
					return null;
				}
			}

			private static string GetZonesRoot()
			{
				if (!string.IsNullOrEmpty(ZonesRoot) && Directory.Exists(ZonesRoot))
					return ZonesRoot;

				foreach (string candidate in GetZoneRootCandidates())
				{
					if (string.IsNullOrWhiteSpace(candidate))
						continue;

					string fullPath = Path.GetFullPath(candidate);
					if (!Directory.Exists(fullPath))
						continue;

					ZonesRoot = fullPath;
					return ZonesRoot;
				}

				return null;
			}

			private static IEnumerable<string> GetZoneRootCandidates()
			{
				string serverRoot = GameServer.Instance?.Configuration?.RootDirectory;
				if (!string.IsNullOrWhiteSpace(serverRoot))
				{
					yield return Path.Combine(serverRoot, "..", "OpenDAoCClient", "zones");
					yield return Path.Combine(serverRoot, "OpenDAoCClient", "zones");
				}

				string current = Directory.GetCurrentDirectory();
				yield return Path.Combine(current, "..", "OpenDAoCClient", "zones");
				yield return Path.Combine(current, "OpenDAoCClient", "zones");

				string baseDirectory = AppDomain.CurrentDomain.BaseDirectory;
				yield return Path.Combine(baseDirectory, "..", "..", "OpenDAoCClient", "zones");
				yield return Path.Combine(baseDirectory, "..", "..", "..", "OpenDAoCClient", "zones");
			}

			private static string FindZonePath(string zonesRoot, ushort zoneId)
			{
				string zoneNumber = zoneId.ToString("D3");
				foreach (string name in new[] { $"zone{zoneNumber}", $"Zone{zoneNumber}", $"ZONE{zoneNumber}" })
				{
					string candidate = Path.Combine(zonesRoot, name);
					if (Directory.Exists(candidate))
						return candidate;
				}

				return null;
			}

			private static void ReadTerrainScale(byte[] sectorData, out int scaleFactor, out int offsetFactor)
			{
				scaleFactor = 8;
				offsetFactor = 32;
				if (sectorData == null || sectorData.Length == 0)
					return;

				string sector = Encoding.Latin1.GetString(sectorData);
				foreach (string rawLine in sector.Split('\n'))
				{
					string line = rawLine.Trim();
					int equalsIndex = line.IndexOf('=');
					if (equalsIndex <= 0)
						continue;

					string key = line[..equalsIndex].Trim();
					string value = line[(equalsIndex + 1)..].Trim();
					if (!int.TryParse(value, out int parsed))
						continue;

					if (key.Equals("scalefactor", StringComparison.OrdinalIgnoreCase))
						scaleFactor = parsed;
					else if (key.Equals("offsetfactor", StringComparison.OrdinalIgnoreCase))
						offsetFactor = parsed;
				}
			}
		}

		private sealed class ClientTerrainMap
		{
			private readonly PcxMap Terrain;
			private readonly PcxMap Offset;
			private readonly int ScaleFactor;
			private readonly int OffsetFactor;

			public ClientTerrainMap(PcxMap terrain, PcxMap offset, int scaleFactor, int offsetFactor)
			{
				Terrain = terrain;
				Offset = offset;
				ScaleFactor = scaleFactor;
				OffsetFactor = offsetFactor;
			}

			public bool TrySample(Zone zone, int worldX, int worldY, out int height)
			{
				height = 0;
				if (zone == null || Terrain == null || Offset == null)
					return false;

				int localX = worldX - zone.XOffset;
				int localY = worldY - zone.YOffset;
				if (localX < 0 || localY < 0 || localX > zone.Width || localY > zone.Height)
					return false;

				double xPixel = localX / Math.Max(1.0, zone.Width / (double)Terrain.Width);
				double yPixel = localY / Math.Max(1.0, zone.Height / (double)Terrain.Height);
				double terrain = Terrain.SampleBilinear(xPixel, yPixel);
				double offset = Offset.SampleBilinear(xPixel, yPixel);
				height = (int)Math.Round(terrain * ScaleFactor + offset * OffsetFactor);
				return true;
			}
		}

		private sealed class PcxMap
		{
			private readonly byte[] Pixels;

			public PcxMap(byte[] data)
			{
				if (data == null || data.Length < 128)
					throw new ArgumentException("Invalid PCX data.", nameof(data));

				int bitsPerPixel = data[3];
				int xMin = BitConverter.ToUInt16(data, 4);
				int yMin = BitConverter.ToUInt16(data, 6);
				int xMax = BitConverter.ToUInt16(data, 8);
				int yMax = BitConverter.ToUInt16(data, 10);
				int planes = data[65];
				int bytesPerLine = BitConverter.ToUInt16(data, 66);

				if (bitsPerPixel != 8 || planes != 1)
					throw new ArgumentException("Only 8-bit single-plane PCX maps are supported.", nameof(data));

				Width = xMax - xMin + 1;
				Height = yMax - yMin + 1;
				Pixels = DecodePixels(data, Width, Height, bytesPerLine);
			}

			public int Width { get; }
			public int Height { get; }

			public double SampleBilinear(double xPixel, double yPixel)
			{
				double x = Math.Clamp(xPixel, 0, Width - 1);
				double y = Math.Clamp(yPixel, 0, Height - 1);
				int x0 = (int)x;
				int y0 = (int)y;
				int x1 = Math.Min(x0 + 1, Width - 1);
				int y1 = Math.Min(y0 + 1, Height - 1);
				double tx = x - x0;
				double ty = y - y0;

				double top = GetPixel(x0, y0) * (1.0 - tx) + GetPixel(x1, y0) * tx;
				double bottom = GetPixel(x0, y1) * (1.0 - tx) + GetPixel(x1, y1) * tx;
				return top * (1.0 - ty) + bottom * ty;
			}

			private byte GetPixel(int x, int y)
			{
				return Pixels[y * Width + x];
			}

			private static byte[] DecodePixels(byte[] data, int width, int height, int bytesPerLine)
			{
				int expected = height * bytesPerLine;
				byte[] decoded = new byte[expected];
				int decodedIndex = 0;
				int cursor = 128;
				int end = data.Length >= 769 && data[^769] == 12 ? data.Length - 769 : data.Length;

				while (cursor < end && decodedIndex < expected)
				{
					byte value = data[cursor++];
					int runLength = 1;

					if (value >= 0xC0)
					{
						runLength = value & 0x3F;
						if (cursor >= end)
							break;

						value = data[cursor++];
					}

					for (int count = 0; count < runLength && decodedIndex < expected; count++)
						decoded[decodedIndex++] = value;
				}

				if (decodedIndex < expected)
					throw new ArgumentException("Truncated PCX image data.", nameof(data));

				byte[] pixels = new byte[width * height];
				for (int y = 0; y < height; y++)
					Buffer.BlockCopy(decoded, y * bytesPerLine, pixels, y * width, width);

				return pixels;
			}
		}

		private static class PathPointRouteCache
		{
			private static readonly object Sync = new();
			private static List<RoutePathPoint> Points;

			public static List<RoutePathPoint> GetPoints(Region region, int minX, int maxX, int minY, int maxY)
			{
				if (region == null)
					return new List<RoutePathPoint>();

				List<RoutePathPoint> points = GetAllPoints();
				return points
					.Where(point => point.Point.X >= minX
						&& point.Point.X <= maxX
						&& point.Point.Y >= minY
						&& point.Point.Y <= maxY
						&& region.GetZone(point.Point.X, point.Point.Y) != null)
					.ToList();
			}

			private static List<RoutePathPoint> GetAllPoints()
			{
				lock (Sync)
				{
					if (Points != null)
						return Points;

					Points = LoadPoints();
					return Points;
				}
			}

			private static List<RoutePathPoint> LoadPoints()
			{
				try
				{
					HashSet<string> usablePathIds = GameServer.Database.SelectAllObjects<DbPath>()
						.Where(IsUsableRoadPath)
						.Select(path => path.PathID)
						.ToHashSet(StringComparer.OrdinalIgnoreCase);

					if (usablePathIds.Count == 0)
						return new List<RoutePathPoint>();

					return GameServer.Database.SelectAllObjects<DbPathPoint>()
						.Where(point => !string.IsNullOrWhiteSpace(point.PathID) && usablePathIds.Contains(point.PathID))
						.Select(point => new RoutePathPoint(point.PathID, point.Step, new Point3D(point.X, point.Y, point.Z)))
						.ToList();
				}
				catch
				{
					return new List<RoutePathPoint>();
				}
			}

			private static bool IsUsableRoadPath(DbPath path)
			{
				if (path == null || path.PathType != (int)EPathType.Once || string.IsNullOrWhiteSpace(path.PathID))
					return false;

				string pathId = path.PathID.ToLowerInvariant();
				return !pathId.Contains("guard")
					&& !pathId.Contains("patrol")
					&& !pathId.Contains("test")
					&& !pathId.StartsWith("wp_");
			}
		}

		private sealed class SupplyConvoyEscort : GameNPC
		{
			public override int RealmPointsValue => EscortRealmPointReward;
			public override int BountyPointsValue => EscortBountyPointReward;
		}

		private sealed class SupplyConvoyWagon : GameNPC
		{
			public ConvoyState State;

			public override void OnAttackedByEnemy(AttackData ad)
			{
				base.OnAttackedByEnemy(ad);
				RecordInterceptorDamage(State, ad);
				DefendWagon(State, ad);
			}
		}

		private sealed class ConvoyMobBrain : StandardMobBrain
		{
			public override void Think()
			{
				if (Body == null || !Body.IsAlive || Body.ObjectState != GameObject.eObjectState.Active)
					return;

				if (HasAggro)
				{
					AttackMostWanted();
					return;
				}

				CheckProximityAggro();
			}

			public override bool Stop()
			{
				ClearAggroList();
				Body?.ClearObjectsInRadiusCache();
				FSM?.SetCurrentState(eFSMStateType.WAKING_UP);
				return ServiceObjectStore.Remove((DOL.AI.ABrain)this);
			}
		}

		public readonly struct ConvoyStartPosition
		{
			public ConvoyStartPosition(eRealm realm, ushort regionId, Point3D point, ushort heading)
			{
				Realm = realm;
				RegionID = regionId;
				Point = point;
				Heading = heading;
			}

			public eRealm Realm { get; }
			public ushort RegionID { get; }
			public Point3D Point { get; }
			public ushort Heading { get; }

			public static ConvoyStartPosition From(DbKeepSupplyConvoyStart row)
			{
				return new ConvoyStartPosition(
					(eRealm)row.Realm,
					(ushort)row.RegionID,
					new Point3D(row.X, row.Y, row.Z),
					(ushort)row.Heading);
			}
		}

		private sealed class ConvoyOrigin
		{
			public string Name;
			public ushort RegionID;
			public Point3D Point;
			public ushort Heading;
		}

		private readonly record struct RouteGraphNode(int X, int Y);
		private readonly record struct RouteEdge(int To, double Cost);
		private readonly record struct RoutePathPoint(string PathID, int Step, Point3D Point);

		private sealed class ConvoyState
		{
			public eRealm Realm;
			public string OriginName;
			public AbstractGameKeep TargetKeep;
			public Point3D Origin;
			public Point3D Destination;
			public SupplyConvoyWagon Wagon;
			public List<GameNPC> Escorts = new();
			public List<Point3D> Route = new();
			public Dictionary<GamePlayer, long> SupporterPresenceMilliseconds = new();
			public Dictionary<GamePlayer, long> InterceptorDamageByPlayer = new();
			public int RouteIndex;
			public int LastIssuedRouteIndex = -1;
			public bool HasDeparted;
			public DateTime DepartedAt;
			public ECSGameTimer DepartureTimer;
			public ECSGameTimer TickTimer;
		}
	}
}
