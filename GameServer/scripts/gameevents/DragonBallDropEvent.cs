using System;
using System.Collections.Generic;
using System.Reflection;
using DOL.AI.Brain;
using DOL.Database;
using DOL.Events;
using DOL.GS.PacketHandler;
using DOL.GS.Scheduler;
using DOL.GS.ServerProperties;

namespace DOL.GS.GameEvents
{
	public static class DragonBallDropEvent
	{
		private const string PackageId = "KDAOCDragonBall";
		private const int DragonBallModel = 485;
		private const int DragonBallItemType = 40;
		private const int OneMillion = 1000000;
		private const string WishTokenTemplateId = "kdaoc_dragon_wish_token";
		private const string SummonBusyProperty = "KDAOC_DRAGON_BALL_SUMMON_BUSY_UNTIL";
		private const string SummonPhrase = "나오너라 신룡이여";
		private const string WealthWishPhrase = "부자가 되게 해줘";
		private const uint DefaultSummonWeatherWidth = 300000;
		private const ushort DefaultSummonWeatherSpeed = 1;
		private const ushort InitialSummonWeatherDiffusion = 20;
		private const ushort InitialSummonWeatherIntensity = 20;
		private const ushort DefaultSummonWeatherDiffusion = 110;
		private const ushort DefaultSummonWeatherIntensity = 110;
		private const int SummonDragonSpawnDelayMilliseconds = 60000;
		private const int SummonWeatherFadeOutMilliseconds = 60000;
		private const int SummonWeatherRampSteps = 5;
		private const int SummonDragonAscendMilliseconds = 6000;
		private const int SummonDragonAscendZOffset = 2500;
		private const short SummonDragonAscendSpeed = 420;
		private const int SummonDragonSpawnXYOffset = 200;
		private const int SummonDragonSpawnZOffset = 300;
		private const int WishGrantDelayMilliseconds = 300;
		private static readonly long WealthWishReward = Money.GetMoney(0, 10, 0, 0, 0);

		private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);
		private static readonly object SummonLock = new();
		private static readonly Dictionary<int, SummonState> ActiveSummons = new();

		private static readonly string[] TemplateIds =
		{
			"kdaoc_dragon_ball_1",
			"kdaoc_dragon_ball_2",
			"kdaoc_dragon_ball_3",
			"kdaoc_dragon_ball_4",
			"kdaoc_dragon_ball_5",
			"kdaoc_dragon_ball_6",
			"kdaoc_dragon_ball_7"
		};

		private static readonly string[] Names =
		{
			"드래곤볼 1성구",
			"드래곤볼 2성구",
			"드래곤볼 3성구",
			"드래곤볼 4성구",
			"드래곤볼 5성구",
			"드래곤볼 6성구",
			"드래곤볼 7성구"
		};

		public static string GetCollectionStatusMessage(GamePlayer player)
		{
			if (player == null)
				return "드래곤볼 수집 상태를 확인할 수 없습니다.";

			bool[] ownedStars = GetOwnedStars(player);
			List<string> owned = new();
			List<string> missing = new();

			for (int index = 0; index < ownedStars.Length; index++)
			{
				string starName = $"{index + 1}성구";
				if (ownedStars[index])
					owned.Add(starName);
				else
					missing.Add(starName);
			}

			if (missing.Count == 0)
				return $"드래곤볼 1성구부터 7성구까지 모두 모았습니다. 7개를 가방에 넣고 /yell {SummonPhrase} 로 신룡을 부를 수 있습니다.";

			return $"드래곤볼 수집 현황: {owned.Count}/7 | 보유: {FormatStarList(owned)} | 부족: {FormatStarList(missing)}";
		}

		public static bool TryStartSummoning(GamePlayer player, out string message)
		{
			message = string.Empty;

			if (!Properties.KDAOC_DRAGON_BALL_ENABLED)
			{
				message = "드래곤볼 시스템이 비활성화되어 있습니다.";
				return false;
			}

			if (player?.Client == null || player.CurrentRegion == null || player.ObjectState != GameObject.eObjectState.Active)
			{
				message = "지금은 신룡을 부를 수 없습니다.";
				return false;
			}

			long busyUntil = player.TempProperties.GetProperty<long>(SummonBusyProperty);
			if (busyUntil > GameLoop.GameLoopTime)
			{
				message = "이미 신룡 소환 의식이 진행 중입니다.";
				return false;
			}

			if (!TryGetBackpackDragonBallSet(player, out List<DbInventoryItem> dragonBalls))
			{
				message = "신룡을 부르려면 드래곤볼 1성구부터 7성구까지 모두 가방에 넣어야 합니다.";
				return false;
			}

			EnsureTemplates();

			if (!ConsumeBackpackDragonBalls(player, dragonBalls))
			{
				message = "드래곤볼을 모으는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.";
				return false;
			}

			player.TempProperties.SetProperty(SummonBusyProperty, GameLoop.GameLoopTime + (GetSummonDurationSeconds() + SummonDragonSpawnDelayMilliseconds / 1000 + 5) * 1000);
			StartSummonPresentation(player);
			message = "일곱 성구가 하늘로 떠오르며 신룡 소환이 시작됩니다. 주변 유저는 신룡을 클릭하고 /yell 로 먼저 소원을 말할 수 있습니다.";
			return true;
		}

		[ScriptLoadedEvent]
		public static void OnScriptLoaded(DOLEvent e, object sender, EventArgs args)
		{
			EnsureTemplates();
			GameEventMgr.AddHandlerUnique(GamePlayerEvent.GameEntered, PlayerEntered);
			GameEventMgr.AddHandlerUnique(GamePlayerEvent.Quit, PlayerQuit);

			foreach (GamePlayer player in ClientService.Instance.GetPlayers())
				AttachPlayer(player);
		}

		[ScriptUnloadedEvent]
		public static void OnScriptUnloaded(DOLEvent e, object sender, EventArgs args)
		{
			GameEventMgr.RemoveHandler(GamePlayerEvent.GameEntered, PlayerEntered);
			GameEventMgr.RemoveHandler(GamePlayerEvent.Quit, PlayerQuit);

			foreach (GamePlayer player in ClientService.Instance.GetPlayers())
				DetachPlayer(player);
		}

		private static void PlayerEntered(DOLEvent e, object sender, EventArgs args)
		{
			if (sender is GamePlayer player)
				AttachPlayer(player);
		}

		private static void PlayerQuit(DOLEvent e, object sender, EventArgs args)
		{
			if (sender is GamePlayer player)
				DetachPlayer(player);
		}

		private static void AttachPlayer(GamePlayer player)
		{
			RepairWishTokens(player);
			GameEventMgr.AddHandlerUnique(player, GameLivingEvent.EnemyKilled, EnemyKilled);
			GameEventMgr.AddHandlerUnique(player, GameLivingEvent.Yell, PlayerYelled);
		}

		private static void DetachPlayer(GamePlayer player)
		{
			GameEventMgr.RemoveHandler(player, GameLivingEvent.EnemyKilled, EnemyKilled);
			GameEventMgr.RemoveHandler(player, GameLivingEvent.Yell, PlayerYelled);
		}

		private static void PlayerYelled(DOLEvent e, object sender, EventArgs args)
		{
			try
			{
				if (sender is not GamePlayer player || args is not YellEventArgs yellArgs)
					return;

				string text = yellArgs.Text?.Trim();
				if (string.IsNullOrWhiteSpace(text))
					return;

				if (IsSummonPhrase(text))
				{
					if (TryStartSummoning(player, out string summonMessage))
						player.Out.SendMessage(summonMessage, eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
					else
						player.Out.SendMessage(summonMessage, eChatType.CT_Important, eChatLoc.CL_SystemWindow);

					return;
				}

				ScheduleWishFromYell(player, text);
			}
			catch (Exception ex)
			{
				if (log.IsErrorEnabled)
					log.Error("Error while handling Dragon Ball yell.", ex);
			}
		}

		private static bool IsSummonPhrase(string text)
		{
			return string.Equals(NormalizeDragonBallSpeech(text), NormalizeDragonBallSpeech(SummonPhrase), StringComparison.OrdinalIgnoreCase);
		}

		private static string NormalizeDragonBallSpeech(string text)
		{
			return string.IsNullOrWhiteSpace(text) ? string.Empty : text.Replace(" ", string.Empty).Trim();
		}

		private static void ScheduleWishFromYell(GamePlayer player, string wishText)
		{
			if (player == null || !IsWealthWish(wishText))
				return;

			string delayedWishText = wishText;
			new ECSGameTimer(player, _ =>
			{
				if (player.ObjectState == GameObject.eObjectState.Active)
					TryGrantWishFromYell(player, delayedWishText);

				return 0;
			}, WishGrantDelayMilliseconds);
		}

		private static void TryGrantWishFromYell(GamePlayer player, string wishText)
		{
			if (!IsWealthWish(wishText))
				return;

			if (!TryGetWishDragon(player, out GameNPC dragon, out SummonState state))
				return;

			lock (SummonLock)
			{
				if (state.WishGranted || !ActiveSummons.TryGetValue(dragon.ObjectID, out SummonState activeState) || activeState != state)
					return;

				state.WishGranted = true;
				ActiveSummons.Remove(dragon.ObjectID);
				state.ExpireTimer?.Stop();
			}

			GrantWealthWish(player);
			SendNearbyMessage(player, $"{player.Name}의 소원이 신룡에게 닿았습니다.", eChatType.CT_ScreenCenter);
			EndSummon(state, true);
		}

		private static bool IsWealthWish(string text)
		{
			return string.Equals(NormalizeDragonBallSpeech(text), NormalizeDragonBallSpeech(WealthWishPhrase), StringComparison.OrdinalIgnoreCase);
		}

		private static void GrantWealthWish(GamePlayer player)
		{
			player.AddServerIssuedMoney(WealthWishReward, "신룡의 힘으로 {0}을 받았습니다.", eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			player.Out.SendMessage("신룡의 재물이 당신에게 내려옵니다.", eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
		}

		private static bool TryGetWishDragon(GamePlayer player, out GameNPC dragon, out SummonState state)
		{
			dragon = null;
			state = null;

			if (player == null)
				return false;

			lock (SummonLock)
			{
				if (player.TargetObject is GameNPC targetedDragon &&
					IsActiveWishDragon(player, targetedDragon, out state))
				{
					dragon = targetedDragon;
					return true;
				}

				foreach (SummonState activeState in ActiveSummons.Values)
				{
					if (activeState?.Dragon == null || !IsActiveWishDragon(player, activeState.Dragon, out _))
						continue;

					dragon = activeState.Dragon;
					state = activeState;
					return true;
				}
			}

			return false;
		}

		private static bool IsActiveWishDragon(GamePlayer player, GameNPC dragon, out SummonState state)
		{
			state = null;

			if (player == null ||
				dragon == null ||
				dragon.ObjectState != GameObject.eObjectState.Active ||
				player.CurrentRegionID != dragon.CurrentRegionID ||
				!ActiveSummons.TryGetValue(dragon.ObjectID, out state) ||
				state == null ||
				state.Dragon != dragon ||
				state.WishGranted)
			{
				return false;
			}

			return player.GetDistanceTo(dragon, 0) <= WorldMgr.YELL_DISTANCE;
		}

		private static void EnemyKilled(DOLEvent e, object sender, EventArgs args)
		{
			try
			{
				if (!Properties.KDAOC_DRAGON_BALL_ENABLED ||
					sender is not GamePlayer player ||
					args is not EnemyKilledEventArgs killArgs ||
					killArgs.Target is not GameNPC mob ||
					!IsEligibleKill(player, mob) ||
					!RollDrop())
				{
					return;
				}

				int star = RollMissingStar(player);
				if (star <= 0)
					return;

				GiveDragonBall(player, star);
			}
			catch (Exception ex)
			{
				if (log.IsErrorEnabled)
					log.Error("Error while rolling Dragon Ball drop.", ex);
			}
		}

		private static bool IsEligibleKill(GamePlayer player, GameNPC mob)
		{
			if (player == null || mob == null)
				return false;

			if (mob.Level < Math.Max(1, Properties.KDAOC_DRAGON_BALL_MIN_MOB_LEVEL))
				return false;

			if (mob.Brain is IControlledBrain)
				return false;

			return player.Inventory.IsSlotsFree(1, eInventorySlot.FirstBackpack, eInventorySlot.LastBackpack);
		}

		private static bool RollDrop()
		{
			int chance = Math.Clamp(Properties.KDAOC_DRAGON_BALL_DROP_CHANCE_PER_MILLION, 0, OneMillion);
			return chance > 0 && Util.Random(1, OneMillion) <= chance;
		}

		private static int RollMissingStar(GamePlayer player)
		{
			bool[] ownedStars = GetOwnedStars(player);
			int missingCount = 0;

			for (int index = 0; index < ownedStars.Length; index++)
			{
				if (!ownedStars[index])
					missingCount++;
			}

			if (missingCount <= 0)
				return 0;

			int selectedMissing = Util.Random(1, missingCount);
			for (int index = 0; index < ownedStars.Length; index++)
			{
				if (ownedStars[index])
					continue;

				selectedMissing--;
				if (selectedMissing == 0)
					return index + 1;
			}

			return 0;
		}

		private static bool HasMissingDragonBall(GamePlayer player)
		{
			bool[] ownedStars = GetOwnedStars(player);
			for (int index = 0; index < ownedStars.Length; index++)
			{
				if (!ownedStars[index])
					return true;
			}

			return false;
		}

		private static string FormatStarList(List<string> stars)
		{
			return stars == null || stars.Count == 0 ? "없음" : string.Join(", ", stars);
		}

		private static bool TryGetBackpackDragonBallSet(GamePlayer player, out List<DbInventoryItem> dragonBalls)
		{
			dragonBalls = new List<DbInventoryItem>();
			if (player == null)
				return false;

			bool[] foundStars = new bool[TemplateIds.Length];
			ICollection<DbInventoryItem> backpackItems = player.Inventory.GetItemRange(eInventorySlot.FirstBackpack, eInventorySlot.LastBackpack);
			if (backpackItems == null)
				return false;

			foreach (DbInventoryItem item in backpackItems)
			{
				int star = GetDragonBallStar(item);
				if (star <= 0 || foundStars[star - 1])
					continue;

				foundStars[star - 1] = true;
				dragonBalls.Add(item);
			}

			return dragonBalls.Count == TemplateIds.Length;
		}

		private static bool ConsumeBackpackDragonBalls(GamePlayer player, List<DbInventoryItem> dragonBalls)
		{
			if (player == null || dragonBalls == null || dragonBalls.Count != TemplateIds.Length)
				return false;

			foreach (DbInventoryItem item in dragonBalls)
			{
				if (item == null || item.OwnerID != player.InternalID)
					return false;
			}

			foreach (DbInventoryItem item in dragonBalls)
			{
				if (!player.Inventory.RemoveItem(item))
					return false;

				InventoryLogging.LogInventoryAction(player, "(dragon_ball_summon)", eInventoryActionType.Other, item.Template);
			}

			return true;
		}

		private static bool GiveWishToken(GamePlayer player)
		{
			DbItemTemplate template = GetWishTokenTemplate();
			if (template == null)
				return false;

			GameInventoryItem item = GameInventoryItem.Create(template);
			item.IsIndestructible = false;
			if (!player.Inventory.AddItem(eInventorySlot.FirstEmptyBackpack, item))
				return false;

			player.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
			InventoryLogging.LogInventoryAction("(dragon_ball_summon)", player, eInventoryActionType.Loot, template);
			player.Out.SendMessage($"{template.Name}을 획득했습니다.", eChatType.CT_Important, eChatLoc.CL_SystemWindow);
			return true;
		}

		private static bool[] GetOwnedStars(GamePlayer player)
		{
			bool[] ownedStars = new bool[TemplateIds.Length];

			if (player == null)
				return ownedStars;

			MarkOwnedStars(ownedStars, player.Inventory.GetItemRange(eInventorySlot.FirstBackpack, eInventorySlot.LastVault));
			MarkOwnedStars(ownedStars, GetActiveStorageItems(player));
			MarkOwnedStars(ownedStars, GetAccountVaultItems(player));
			MarkOwnedStars(ownedStars, GetPersonalHouseVaultItems(player));

			return ownedStars;
		}

		private static void MarkOwnedStars(bool[] ownedStars, IEnumerable<DbInventoryItem> items)
		{
			if (ownedStars == null || items == null)
				return;

			foreach (DbInventoryItem item in items)
			{
				int star = GetDragonBallStar(item);
				if (star > 0)
					ownedStars[star - 1] = true;
			}
		}

		private static int GetDragonBallStar(DbInventoryItem item)
		{
			if (item == null || string.IsNullOrEmpty(item.Id_nb))
				return 0;

			for (int index = 0; index < TemplateIds.Length; index++)
			{
				if (string.Equals(item.Id_nb, TemplateIds[index], StringComparison.OrdinalIgnoreCase))
					return index + 1;
			}

			return 0;
		}

		private static IEnumerable<DbInventoryItem> GetActiveStorageItems(GamePlayer player)
		{
			if (player?.ActiveInventoryObject == null)
				return Array.Empty<DbInventoryItem>();

			return player.ActiveInventoryObject.GetDbItems();
		}

		private static IEnumerable<DbInventoryItem> GetAccountVaultItems(GamePlayer player)
		{
			string ownerId = GetAccountVaultOwner(player);
			if (string.IsNullOrEmpty(ownerId))
				return Array.Empty<DbInventoryItem>();

			WhereClause accountVaultSlots = BuildSlotRange(eInventorySlot.AccountVault_First, eInventorySlot.AccountVault_Last);

			return DOLDB<DbInventoryItem>.SelectObjects(DB.Column("OwnerID").IsEqualTo(ownerId).And(accountVaultSlots));
		}

		private static IEnumerable<DbInventoryItem> GetPersonalHouseVaultItems(GamePlayer player)
		{
			List<string> ownerIds = GetPersonalHouseVaultOwnerIds(player);
			if (ownerIds.Count <= 0)
				return Array.Empty<DbInventoryItem>();

			WhereClause houseVaultSlots = BuildSlotRange(eInventorySlot.HouseVault_First, eInventorySlot.HouseVault_Last);

			return DOLDB<DbInventoryItem>.SelectObjects(DB.Column("OwnerID").IsIn(ownerIds).And(houseVaultSlots));
		}

		private static List<string> GetPersonalHouseVaultOwnerIds(GamePlayer player)
		{
			List<string> ownerIds = new();
			if (player?.Client?.Account == null)
				return ownerIds;

			foreach (DbCoreCharacter character in player.Client.Account.Characters)
			{
				if ((eRealm)character.Realm != player.Realm || string.IsNullOrEmpty(character.ObjectId))
					continue;

				if (!ownerIds.Contains(character.ObjectId))
					ownerIds.Add(character.ObjectId);
			}

			if (!string.IsNullOrEmpty(player.ObjectId) && !ownerIds.Contains(player.ObjectId))
				ownerIds.Add(player.ObjectId);

			return ownerIds;
		}

		private static WhereClause BuildSlotRange(eInventorySlot firstSlot, eInventorySlot lastSlot)
		{
			return DB.Column("SlotPosition").IsGreaterOrEqualTo((int)firstSlot)
				.And(DB.Column("SlotPosition").IsLessOrEqualTo((int)lastSlot));
		}

		private static string GetAccountVaultOwner(GamePlayer player)
		{
			if (player?.Client?.Account == null)
				return string.Empty;

			return $"{player.Client.Account.Name}_{player.Realm}";
		}

		private static void GiveDragonBall(GamePlayer player, int star)
		{
			DbItemTemplate template = GetTemplate(star);
			if (template == null)
				return;

			GameInventoryItem item = GameInventoryItem.Create(template);
			if (!player.Inventory.AddItem(eInventorySlot.FirstEmptyBackpack, item))
				return;

			player.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
			InventoryLogging.LogInventoryAction("(dragon_ball_drop)", player, eInventoryActionType.Loot, template);
			player.Out.SendMessage($"{template.Name}를 획득했습니다.", eChatType.CT_Loot, eChatLoc.CL_SystemWindow);

			if (!HasMissingDragonBall(player))
				SendCollectionCompleteMessage(player);
		}

		private static void SendCollectionCompleteMessage(GamePlayer player)
		{
			const string message = "드래곤볼 1성구부터 7성구까지 모두 모았습니다!";
			player.Out.SendMessage(message, eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
			player.Out.SendMessage(message, eChatType.CT_Important, eChatLoc.CL_SystemWindow);
		}

		private static void StartSummonPresentation(GamePlayer player)
		{
			bool weatherStarted = TryStartSummonWeather(player);
			ushort regionId = player.CurrentRegionID;

			SendNearbyMessage(player, "하늘이 어두워지고 짙은 안개가 몰려옵니다.", eChatType.CT_ScreenCenter);
			PlaySummonEffect(player, null);
			ScheduleNearbyMessage(player, 10000, "일곱 성구가 눈부신 빛을 내며 하늘로 떠오릅니다.", eChatType.CT_ScreenCenter);
			ScheduleNearbyMessage(player, 50000, "짙은 안개 속에서 거대한 기운이 하늘을 뒤덮습니다.", eChatType.CT_ScreenCenter);

			new ECSGameTimer(player, _ =>
			{
				if (player?.ObjectState != GameObject.eObjectState.Active || player.CurrentRegionID != regionId)
				{
					if (weatherStarted)
						StopSummonWeather(regionId);

					return 0;
				}

				GameNPC dragon = CreateSummonDragon(player);
				PlaySummonEffect(player, dragon);
				SendNearbyMessage(player, "짙은 안개 속에서 신룡이 모습을 드러냅니다.", eChatType.CT_ScreenCenter);
				ScheduleDragonMessage(player, dragon, 3000, "나를 불러낸 자여, 소원을 말하라.");
				ScheduleNearbyMessage(player, 5000, "신룡을 클릭한 뒤 /yell 로 소원을 외치면 가장 먼저 외친 자의 소원이 접수됩니다.", eChatType.CT_Important);

				if (dragon == null)
				{
					if (weatherStarted)
						StopSummonWeather(regionId);

					return 0;
				}

				SummonState state = new()
				{
					Dragon = dragon,
					RegionId = regionId,
					WeatherStarted = weatherStarted,
					WeatherTimerOwner = player
				};

				state.ExpireTimer = new ECSGameTimer(dragon, __ =>
				{
					EndSummon(state, false);
					return 0;
				}, GetSummonDurationSeconds() * 1000);

				lock (SummonLock)
					ActiveSummons[dragon.ObjectID] = state;

				return 0;
			}, SummonDragonSpawnDelayMilliseconds);
		}

		private static bool TryStartSummonWeather(GamePlayer player)
		{
			if (!Properties.KDAOC_DRAGON_BALL_SUMMON_WEATHER_ENABLED || player?.CurrentRegion == null)
				return false;

			RegionWeather weather = GameServer.Instance.WorldManager.WeatherManager[player.CurrentRegionID];
			if (weather == null || weather.StartTime != 0)
				return false;

			uint width = DefaultSummonWeatherWidth;
			uint position = (uint)Math.Max(0, player.X + (int)(width / 2));
			bool started = StartSummonWeather(
				player.CurrentRegionID,
				position,
				width,
				InitialSummonWeatherDiffusion,
				InitialSummonWeatherIntensity);

			if (started)
				ScheduleSummonWeatherRamp(player, player.CurrentRegionID, position, width);

			return started;
		}

		private static void ScheduleSummonWeatherRamp(GamePlayer player, ushort regionId, uint position, uint width)
		{
			if (player == null)
				return;

			int stepDelay = SummonDragonSpawnDelayMilliseconds / (SummonWeatherRampSteps + 1);
			for (int step = 1; step <= SummonWeatherRampSteps; step++)
			{
				int rampStep = step;
				new ECSGameTimer(player, _ =>
				{
					ApplySummonWeatherRamp(regionId, position, width, rampStep);
					return 0;
				}, stepDelay * step);
			}
		}

		private static void ApplySummonWeatherRamp(ushort regionId, uint position, uint width, int step)
		{
			RegionWeather weather = GameServer.Instance.WorldManager.WeatherManager[regionId];
			if (weather == null || weather.StartTime == 0)
				return;

			ushort diffusion = GetWeatherRampValue(InitialSummonWeatherDiffusion, DefaultSummonWeatherDiffusion, step);
			ushort intensity = GetWeatherRampValue(InitialSummonWeatherIntensity, DefaultSummonWeatherIntensity, step);

			GameServer.Instance.WorldManager.WeatherManager.ChangeWeather(
				regionId,
				currentWeather => currentWeather.CreateWeather(
					position,
					width,
					DefaultSummonWeatherSpeed,
					intensity,
					diffusion,
					SimpleScheduler.Ticks));
		}

		private static ushort GetWeatherRampValue(ushort initialValue, ushort finalValue, int step)
		{
			step = Math.Clamp(step, 1, SummonWeatherRampSteps);
			return (ushort)(initialValue + ((finalValue - initialValue) * step / SummonWeatherRampSteps));
		}

		private static bool StartSummonWeather(ushort regionId, uint position, uint width, ushort diffusion, ushort intensity)
		{
			return GameServer.Instance.WorldManager.WeatherManager.StartWeather(
				regionId,
				position,
				width,
				DefaultSummonWeatherSpeed,
				diffusion,
				intensity);
		}

		private static void StopSummonWeather(ushort regionId)
		{
			RegionWeather weather = GameServer.Instance.WorldManager.WeatherManager[regionId];
			if (weather != null && weather.StartTime != 0)
				GameServer.Instance.WorldManager.WeatherManager.StopWeather(regionId);
		}

		private static void EndSummon(SummonState state, bool wishGranted)
		{
			if (state == null)
				return;

			GameNPC dragon = state.Dragon;
			lock (SummonLock)
			{
				if (dragon != null &&
					ActiveSummons.TryGetValue(dragon.ObjectID, out SummonState activeState) &&
					activeState == state)
				{
					ActiveSummons.Remove(dragon.ObjectID);
				}

				state.ExpireTimer?.Stop();
			}

			if (wishGranted && dragon != null && dragon.ObjectState == GameObject.eObjectState.Active)
				dragon.Yell("소원은 이루어졌다.");

			BeginDragonAscendAndDelete(dragon, () =>
			{
				if (state.WeatherStarted)
					ScheduleSummonWeatherFadeOut(state.WeatherTimerOwner ?? dragon, state.RegionId);
			});
		}

		private static void ScheduleSummonWeatherFadeOut(GameObject timerOwner, ushort regionId)
		{
			if (timerOwner == null)
			{
				StopSummonWeather(regionId);
				return;
			}

			int stepDelay = SummonWeatherFadeOutMilliseconds / (SummonWeatherRampSteps + 1);
			for (int step = 1; step <= SummonWeatherRampSteps; step++)
			{
				int fadeStep = step;
				new ECSGameTimer(timerOwner, _ =>
				{
					ApplySummonWeatherFadeOut(regionId, fadeStep);
					return 0;
				}, stepDelay * step);
			}

			new ECSGameTimer(timerOwner, _ =>
			{
				StopSummonWeather(regionId);
				return 0;
			}, SummonWeatherFadeOutMilliseconds);
		}

		private static void ApplySummonWeatherFadeOut(ushort regionId, int step)
		{
			RegionWeather weather = GameServer.Instance.WorldManager.WeatherManager[regionId];
			if (weather == null || weather.StartTime == 0)
				return;

			ushort diffusion = GetWeatherRampValue(DefaultSummonWeatherDiffusion, InitialSummonWeatherDiffusion, step);
			ushort intensity = GetWeatherRampValue(DefaultSummonWeatherIntensity, InitialSummonWeatherIntensity, step);
			uint position = weather.Position;
			uint width = weather.Width;

			GameServer.Instance.WorldManager.WeatherManager.ChangeWeather(
				regionId,
				currentWeather => currentWeather.CreateWeather(
					position,
					width,
					DefaultSummonWeatherSpeed,
					intensity,
					diffusion,
					SimpleScheduler.Ticks));
		}

		private static void BeginDragonAscendAndDelete(GameNPC dragon, Action afterDelete)
		{
			if (dragon == null || dragon.ObjectState != GameObject.eObjectState.Active)
			{
				afterDelete?.Invoke();
				return;
			}

			dragon.WalkTo(new Point3D(dragon.X, dragon.Y, dragon.Z + SummonDragonAscendZOffset), SummonDragonAscendSpeed);
			new ECSGameTimer(dragon, _ =>
			{
				if (dragon.ObjectState == GameObject.eObjectState.Active)
					dragon.Delete();

				afterDelete?.Invoke();
				return 0;
			}, SummonDragonAscendMilliseconds);
		}

		private static GameNPC CreateSummonDragon(GamePlayer player)
		{
			if (player?.CurrentRegion == null)
				return null;

			int x = player.X + SummonDragonSpawnXYOffset;
			int y = player.Y + SummonDragonSpawnXYOffset;
			if (player.CurrentRegion.GetZone(x, y) == null)
			{
				x = player.X;
				y = player.Y;
			}

			GameNPC dragon = new SummonedWishDragon()
			{
				Name = "신룡",
				GuildName = "일곱 성구의 용",
				Model = (ushort)Math.Clamp(Properties.KDAOC_DRAGON_BALL_SUMMON_DRAGON_MODEL, 1, ushort.MaxValue),
				Size = (byte)Math.Clamp(Properties.KDAOC_DRAGON_BALL_SUMMON_DRAGON_SIZE, 1, byte.MaxValue),
				Level = 99,
				Realm = player.Realm,
				CurrentRegionID = player.CurrentRegionID,
				X = x,
				Y = y,
				Z = player.Z + SummonDragonSpawnZOffset,
				Heading = (ushort)((player.Heading + 2048) % 4096),
				Flags = GameNPC.eFlags.PEACE | GameNPC.eFlags.FLYING
			};

			return dragon.AddToWorld() ? dragon : null;
		}

		private static void ShowWishOptions(GamePlayer player, GameNPC dragon)
		{
			if (player == null || dragon == null || !IsActiveWishDragon(player, dragon, out _))
				return;

			player.Out.SendMessage($"신룡이 이룰 수 있는 소원입니다.\n[{WealthWishPhrase}]", eChatType.CT_Say, eChatLoc.CL_PopupWindow);
		}

		private static void PlaySummonEffect(GamePlayer player, GameNPC dragon)
		{
			ushort effect = (ushort)Math.Clamp(Properties.KDAOC_DRAGON_BALL_SUMMON_EFFECT, 0, ushort.MaxValue);
			if (player == null || effect == 0)
				return;

			GameObject effectTarget = dragon != null ? dragon : player;
			foreach (GamePlayer nearbyPlayer in player.GetPlayersInRadius(WorldMgr.VISIBILITY_DISTANCE))
				nearbyPlayer.Out.SendSpellEffectAnimation(effectTarget, effectTarget, effect, 0, false, 1);
		}

		private static void ScheduleNearbyMessage(GamePlayer player, int delayMilliseconds, string message, eChatType chatType)
		{
			new ECSGameTimer(player, _ =>
			{
				if (player?.ObjectState == GameObject.eObjectState.Active)
					SendNearbyMessage(player, message, chatType);

				return 0;
			}, delayMilliseconds);
		}

		private static void ScheduleDragonMessage(GamePlayer player, GameNPC dragon, int delayMilliseconds, string message)
		{
			GameObject timerOwner = dragon != null ? dragon : player;
			new ECSGameTimer(timerOwner, _ =>
			{
				if (dragon != null && dragon.ObjectState == GameObject.eObjectState.Active)
					dragon.Yell(message);
				else if (player?.ObjectState == GameObject.eObjectState.Active)
					SendNearbyMessage(player, $"신룡이 말합니다. '{message}'", eChatType.CT_ScreenCenter);

				return 0;
			}, delayMilliseconds);
		}

		private static void SendNearbyMessage(GamePlayer player, string message, eChatType chatType)
		{
			if (player == null)
				return;

			foreach (GamePlayer nearbyPlayer in player.GetPlayersInRadius(WorldMgr.VISIBILITY_DISTANCE))
				nearbyPlayer.Out.SendMessage(message, chatType, eChatLoc.CL_SystemWindow);
		}

		private static int GetSummonDurationSeconds()
		{
			return Math.Clamp(Properties.KDAOC_DRAGON_BALL_SUMMON_DURATION_SECONDS, 300, 600);
		}

		private static DbItemTemplate GetTemplate(int star)
		{
			if (star < 1 || star > TemplateIds.Length)
				return null;

			DbItemTemplate template = GameServer.Database.FindObjectByKey<DbItemTemplate>(TemplateIds[star - 1]);
			if (template != null)
				return template;

			EnsureTemplate(star);
			return GameServer.Database.FindObjectByKey<DbItemTemplate>(TemplateIds[star - 1]);
		}

		private static void EnsureTemplates()
		{
			for (int star = 1; star <= TemplateIds.Length; star++)
				EnsureTemplate(star);

			EnsureWishTokenTemplate();
		}

		private static void EnsureTemplate(int star)
		{
			string id = TemplateIds[star - 1];
			if (GameServer.Database.FindObjectByKey<DbItemTemplate>(id) != null)
				return;

			DbItemTemplate template = new()
			{
				Id_nb = id,
				Name = Names[star - 1],
				Level = 1,
				BonusLevel = 1,
				LevelRequirement = 1,
				Model = DragonBallModel,
				Item_Type = DragonBallItemType,
				Object_Type = 0,
				Quality = 100,
				Condition = 50000,
				MaxCondition = 50000,
				Durability = 50000,
				MaxDurability = 50000,
				IsPickable = true,
				IsDropable = false,
				IsTradable = false,
				CanDropAsLoot = false,
				IsIndestructible = true,
				MaxCount = 1,
				PackSize = 1,
				Weight = 1,
				Price = 0,
				PackageID = PackageId,
				Description = $"{star}개의 별이 빛나는 신비한 구슬입니다."
			};

			GameServer.Database.AddObject(template);
		}

		private static DbItemTemplate GetWishTokenTemplate()
		{
			DbItemTemplate template = GameServer.Database.FindObjectByKey<DbItemTemplate>(WishTokenTemplateId);
			if (template != null)
			{
				RepairWishTokenTemplate(template);
				return template;
			}

			EnsureWishTokenTemplate();
			return GameServer.Database.FindObjectByKey<DbItemTemplate>(WishTokenTemplateId);
		}

		private static void EnsureWishTokenTemplate()
		{
			DbItemTemplate existingTemplate = GameServer.Database.FindObjectByKey<DbItemTemplate>(WishTokenTemplateId);
			if (existingTemplate != null)
			{
				RepairWishTokenTemplate(existingTemplate);
				return;
			}

			DbItemTemplate template = new()
			{
				Id_nb = WishTokenTemplateId,
				Name = "드래곤의 소원권",
				Level = 1,
				BonusLevel = 1,
				LevelRequirement = 1,
				Model = DragonBallModel,
				Item_Type = DragonBallItemType,
				Object_Type = 0,
				Quality = 100,
				Condition = 50000,
				MaxCondition = 50000,
				Durability = 50000,
				MaxDurability = 50000,
				IsPickable = true,
				IsDropable = false,
				IsTradable = false,
				CanDropAsLoot = false,
				IsIndestructible = false,
				MaxCount = 1,
				PackSize = 1,
				Weight = 1,
				Price = 0,
				PackageID = PackageId,
				Description = "일곱 성구를 모아 신룡을 불러낸 증표입니다."
			};

			GameServer.Database.AddObject(template);
		}

		private static void RepairWishTokenTemplate(DbItemTemplate template)
		{
			if (template == null || !template.IsIndestructible)
				return;

			template.IsIndestructible = false;
			GameServer.Database.SaveObject(template);
		}

		private static void RepairWishTokens(GamePlayer player)
		{
			if (player == null)
				return;

			RepairWishTokens(player.Inventory.GetItemRange(eInventorySlot.FirstBackpack, eInventorySlot.LastVault));
			RepairWishTokens(GetActiveStorageItems(player));
			RepairWishTokens(GetAccountVaultItems(player));
			RepairWishTokens(GetPersonalHouseVaultItems(player));
		}

		private static void RepairWishTokens(IEnumerable<DbInventoryItem> items)
		{
			if (items == null)
				return;

			foreach (DbInventoryItem item in items)
			{
				if (item == null ||
					!string.Equals(item.Id_nb, WishTokenTemplateId, StringComparison.OrdinalIgnoreCase) ||
					!item.IsIndestructible)
				{
					continue;
				}

				item.IsIndestructible = false;
				GameServer.Database.SaveObject(item);
			}
		}

		private sealed class SummonState
		{
			public GameNPC Dragon;
			public ushort RegionId;
			public bool WeatherStarted;
			public bool WishGranted;
			public GameObject WeatherTimerOwner;
			public ECSGameTimer ExpireTimer;
		}

		private sealed class SummonedWishDragon : GameNPC
		{
			public override bool Interact(GamePlayer player)
			{
				if (!base.Interact(player))
					return false;

				ShowWishOptions(player, this);
				return true;
			}

			public override bool WhisperReceive(GameLiving source, string text)
			{
				if (source is GamePlayer player &&
					IsWealthWish(text) &&
					IsActiveWishDragon(player, this, out _))
				{
					player.TargetObject = this;
					player.Yell(WealthWishPhrase);
					return true;
				}

				return base.WhisperReceive(source, text);
			}
		}
	}
}
