using System;
using System.Collections.Generic;
using System.Linq;
using DOL.AI.Brain;
using DOL.Database;
using DOL.GS.ServerProperties;

namespace DOL.GS
{
	public class KdaocRandomItemLootGenerator : LootGeneratorBase
	{
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

		public override LootList GenerateLoot(GameNPC mob, GameObject killer)
		{
			LootList loot = new(0);

			if (!Properties.KDAOC_RANDOM_ITEM_ENABLED || mob == null || mob.Level < Properties.KDAOC_RANDOM_ITEM_MIN_MOB_LEVEL)
				return loot;

			GamePlayer player = ResolveLootPlayer(killer, mob);
			if (player == null)
				return loot;

			if (!Properties.KDAOC_RANDOM_ITEM_DROP_GREY_MOBS && player.GetConLevel(mob) <= (int)ConColor.GREY)
				return loot;

			KdaocRandomMobRank rank = ResolveMobRank(mob);
			int dropChance = ResolveDropChance(rank);
			int dropRolls = ResolveDropRollCount(rank);
			List<KdaocRandomItemTier> rolledTiers = new(dropRolls);
			for (int roll = 0; roll < dropRolls; roll++)
			{
				if (Util.Chance(dropChance))
					rolledTiers.Add(KdaocRandomItemService.RollTier(rank));
			}

			if (rank == KdaocRandomMobRank.Boss)
			{
				rolledTiers = KdaocRandomItemService.ApplyBossPremiumDropCap(rolledTiers, Properties.KDAOC_RANDOM_ITEM_BOSS_MAX_PREMIUM_DROPS).ToList();
				rolledTiers = KdaocRandomItemService.EnsureBossMinimumLowTierDrops(
					rolledTiers,
					Properties.KDAOC_RANDOM_ITEM_BOSS_MIN_TOTAL_DROPS,
					Properties.KDAOC_RANDOM_ITEM_MAX_DROP_ROLLS).ToList();
			}

			foreach (KdaocRandomItemTier tier in rolledTiers)
			{
				DbItemTemplate item = GenerateSafeItem(mob, player, rank, tier);
				if (item == null)
					continue;

				item.MaxCount = 1;
				loot.AddFixed(item, 1);
			}

			return loot;
		}

		private static DbItemTemplate GenerateSafeItem(GameNPC mob, GamePlayer player, KdaocRandomMobRank rank, KdaocRandomItemTier tier)
		{
			int attempts = Math.Max(1, Properties.KDAOC_RANDOM_ITEM_MAX_GENERATION_ATTEMPTS);
			eCharacterClass classForLoot = ResolveLootClass(player);
			int level = ResolveItemLevel(mob, rank);

			for (int attempt = 0; attempt < attempts; attempt++)
			{
				GeneratedUniqueItem item = AtlasROGManager.GenerateMonsterLootROG(player.Realm, classForLoot, (byte)level, player.CurrentZone?.IsOF ?? false);
				KdaocRandomItemService.NormalizeGeneratedItem(item);
				KdaocRandomItemService.ApplyTierBonuses(item, tier, rank, Properties.KDAOC_RANDOM_ITEM_MAX_ITEM_LEVEL);

				if (KdaocRandomItemService.ValidateGeneratedItem(item, out string reason))
					return item;

				if (log.IsDebugEnabled)
					log.Debug($"KDAOC random item rejected: {reason} ({item?.Name})");
			}

			return null;
		}

		private static int ResolveDropChance(KdaocRandomMobRank rank)
		{
			int chance = Properties.KDAOC_RANDOM_ITEM_BASE_DROP_CHANCE;
			if (rank == KdaocRandomMobRank.Named)
				chance += Properties.KDAOC_RANDOM_ITEM_NAMED_DROP_BONUS;
			else if (rank == KdaocRandomMobRank.Boss)
				chance += Properties.KDAOC_RANDOM_ITEM_NAMED_DROP_BONUS + Properties.KDAOC_RANDOM_ITEM_BOSS_DROP_BONUS;

			return Math.Clamp(chance, 0, 100);
		}

		public static int ResolveDropRollCount(KdaocRandomMobRank rank)
		{
			int rolls = rank switch
			{
				KdaocRandomMobRank.Boss => Properties.KDAOC_RANDOM_ITEM_BOSS_DROP_ROLLS,
				KdaocRandomMobRank.Named => Properties.KDAOC_RANDOM_ITEM_NAMED_DROP_ROLLS,
				_ => Properties.KDAOC_RANDOM_ITEM_NORMAL_DROP_ROLLS,
			};

			return Math.Clamp(rolls, 1, Math.Max(1, Properties.KDAOC_RANDOM_ITEM_MAX_DROP_ROLLS));
		}

		private static int ResolveItemLevel(GameNPC mob, KdaocRandomMobRank rank)
		{
			int minOffset = Math.Min(Properties.KDAOC_RANDOM_ITEM_MIN_LEVEL_OFFSET, Properties.KDAOC_RANDOM_ITEM_MAX_LEVEL_OFFSET);
			int maxOffset = Math.Max(Properties.KDAOC_RANDOM_ITEM_MIN_LEVEL_OFFSET, Properties.KDAOC_RANDOM_ITEM_MAX_LEVEL_OFFSET);
			int level = mob.Level + Util.Random(minOffset, maxOffset);

			if (rank == KdaocRandomMobRank.Named)
				level += Properties.KDAOC_RANDOM_ITEM_NAMED_LEVEL_BONUS;
			else if (rank == KdaocRandomMobRank.Boss)
				level += Properties.KDAOC_RANDOM_ITEM_BOSS_LEVEL_BONUS;

			return Math.Clamp(level, 1, Math.Max(1, Properties.KDAOC_RANDOM_ITEM_MAX_ITEM_LEVEL));
		}

		private static KdaocRandomMobRank ResolveMobRank(GameNPC mob)
		{
			if (mob is GameEpicBoss)
				return KdaocRandomMobRank.Boss;

			if (KdaocRandomItemService.LooksLikeBossTitle(
				mob.Name,
				mob.Level,
				Properties.KDAOC_RANDOM_ITEM_BOSS_TITLE_TOKENS,
				Properties.KDAOC_RANDOM_ITEM_BOSS_TITLE_MIN_LEVEL))
				return KdaocRandomMobRank.Boss;

			if (mob is IGameEpicNpc || mob is GameEpicDungeonNPC)
				return KdaocRandomMobRank.Named;

			return KdaocRandomMobRank.Normal;
		}

		private static eCharacterClass ResolveLootClass(GamePlayer player)
		{
			if (player.Group == null)
				return (eCharacterClass)player.CharacterClass.ID;

			List<GamePlayer> members = player.Group.GetMembersInTheGroup().OfType<GamePlayer>().Where(member => member.CharacterClass != null).ToList();
			if (members.Count == 0)
				return (eCharacterClass)player.CharacterClass.ID;

			return (eCharacterClass)members[Util.Random(members.Count - 1)].CharacterClass.ID;
		}

		public static GamePlayer ResolveLootPlayer(GameObject killer, GameNPC mob = null)
		{
			if (killer is GamePlayer player)
				return player;

			if (killer is GameNPC npc && npc.Brain is IControlledBrain controlledBrain)
				return controlledBrain.GetPlayerOwner();

			if (mob == null)
				return null;

			lock (mob.XpGainersLock)
			{
				List<KeyValuePair<GamePlayer, double>> candidates = mob.XPGainers
					.Select(pair => new
					{
						Player = ResolveLootPlayer(pair.Key),
						Damage = pair.Value
					})
					.Select(entry => new KeyValuePair<GamePlayer, double>(entry.Player, entry.Damage))
					.ToList();

				return SelectHighestDamageLootPlayer(candidates);
			}
		}

		public static TPlayer SelectHighestDamageLootPlayer<TPlayer>(IEnumerable<KeyValuePair<TPlayer, double>> candidates)
			where TPlayer : class
		{
			if (candidates == null)
				return null;

			return candidates
				.Where(candidate => candidate.Key != null && candidate.Value > 0)
				.OrderByDescending(candidate => candidate.Value)
				.Select(candidate => candidate.Key)
				.FirstOrDefault();
		}

		private static GamePlayer ResolveLootPlayer(GameLiving living)
		{
			if (living is GamePlayer player)
				return player;

			if (living is GameNPC npc && npc.Brain is IControlledBrain controlledBrain)
				return controlledBrain.GetPlayerOwner();

			return null;
		}
	}
}
