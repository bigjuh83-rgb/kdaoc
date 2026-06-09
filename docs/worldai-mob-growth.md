# WorldAI Monster Survival Growth

This document covers the first playable server-side version of the living-world
monster growth system. It does not let an LLM directly control combat. The game
server owns every gameplay value, cap, and state change.

## Current Scope

- Eligible hostile NPCs can be tracked in `mob_growth_state`.
- Monsters gain growth from survival scan ticks.
- Monsters gain extra growth when they have not been killed for a configured
  idle window.
- Monsters gain growth from combat contact and from killing players.
- Growth stages are `Normal`, `Elite`, `Champion`, and `Boss`.
- Grown monsters can receive a capped level bonus, size bonus, health
  multiplier, and random bonus spells/styles/traits.
- Frequently killed monsters can queue a mutant respawn. A mutant is not a
  separate stage; it can still grow into Elite, Champion, or Boss.
- When a monster first reaches `Boss`, the server records a WorldAI event and
  queues normal WorldNews and ChronicleEntry LLM jobs.
- Boss promotion events require GM approval before becoming public news/history.

## Safety Defaults

The system is OFF by default:

```text
worldai_mob_growth_enabled=false
```

This lets operators test it in game before opening it to players. Runtime GM
commands can enable or disable it immediately, but permanent startup behavior
should be controlled through server properties.

Default caps are intentionally modest:

```text
worldai_mob_growth_max_level_bonus=5
worldai_mob_growth_max_health_multiplier=1.5
worldai_mob_growth_max_active_bosses=5
worldai_mob_growth_max_active_bosses_per_region=1
```

When the active Boss cap is full, newly grown monsters can still accumulate
score but remain capped at `Champion` until an existing Boss is killed, reset,
or otherwise marked inactive.

The regional Boss cap is checked separately. A region that already has the
configured number of active `우두머리` monsters will hold additional candidates
at `Champion` even if the global cap still has room.

Mutation defaults are also modest but noticeable:

```text
worldai_mob_growth_mutation_enabled=true
worldai_mob_growth_mutation_death_window_minutes=10
worldai_mob_growth_mutation_death_threshold=5
worldai_mob_growth_mutation_chance_step_percent=10
worldai_mob_growth_mutation_max_chance_percent=100
```

Inside that 10-minute window, the fifth death rolls a 10% mutation chance, the
sixth death rolls 20%, the seventh rolls 30%, and so on until the configured
maximum. A successful roll queues the next alive observation/spawn as mutant.

## Growth Rules

Each automatic scan observes eligible hostile NPCs and adds:

```text
worldai_mob_growth_survival_score=2
```

If the monster has not been killed for the idle window, it also gains:

```text
worldai_mob_growth_unhunted_after_minutes=360
worldai_mob_growth_unhunted_score=8
```

This is the "not hunted enough" growth path. A quiet corner of the world can
still produce a dangerous local threat over time.

Combat and player-kill growth are separate:

```text
worldai_mob_growth_combat_score=12
worldai_mob_growth_combat_cooldown_seconds=30
worldai_mob_growth_player_kill_score=50
```

Combat growth is throttled per monster. Extra hits inside the cooldown window do
not add growth score or force another `mob_growth_state` save.

Stage thresholds:

```text
worldai_mob_growth_elite_score=60
worldai_mob_growth_champion_score=180
worldai_mob_growth_boss_score=420
```

Stage identity changes are cumulative. Player-facing monster names use readable
Korean prefixes: `노련한 <name>` for Elite, `흉포한 <name>` for Champion,
`우두머리 <name>` for Boss, and `돌연변이` stays at the very front when active.

- `Elite`: name prefix, level bonus, size bonus, and one random bonus per pool
- `Champion`: stronger level/size bonus and more cumulative pool picks
- `Boss`: max level bonus, largest size bonus, boss-style pool picks, and the
  existing WorldAI boss promotion event
- `Mutant`: adds a mutant prefix and extra level/size bonus on top of the stage

The default size bonuses are:

```text
worldai_mob_growth_mutation_size_bonus_percent=15
worldai_mob_growth_elite_size_bonus_percent=10
worldai_mob_growth_champion_size_bonus_percent=25
worldai_mob_growth_boss_size_bonus_percent=45
```

Regions can be excluded by region id:

```text
worldai_mob_growth_excluded_regions=1,10,27
```

Safety exclusions are separate from operator exclusions:

```text
worldai_mob_growth_protected_regions=27
worldai_mob_growth_protected_name_tokens=quest;trainer;merchant;master;훈련;상인;퀘스트
worldai_mob_growth_minimum_eligible_level=5
worldai_mob_growth_low_level_max_base_level=15
worldai_mob_growth_low_level_max_stage=Elite
```

Protected regions and protected name tokens are ignored by growth, combat
growth, death mutation tracking, and scan commands. Low-level monsters can still
become visibly different, but by default they cannot grow past `Elite`.

Stale rows can be cleaned manually:

```text
worldai_mob_growth_decay_enabled=true
worldai_mob_growth_decay_after_minutes=720
worldai_mob_growth_decay_score=60
worldai_mob_growth_reset_inactive_after_minutes=10080
```

`/mobgrowth decay` reduces stale active monsters and deletes very old inactive
rows. This prevents forgotten grown monsters from permanently filling a region.

## Bonus Pools

Bonus pools are server properties. They are semicolon-separated and resolved at
runtime; missing spell/style/ability IDs are skipped instead of crashing the
mob.

```text
worldai_mob_growth_mutation_spell_pool=11890;11891;11933;11934;12006;12008
worldai_mob_growth_elite_spell_pool=11874;11892;11899;12001
worldai_mob_growth_champion_spell_pool=11893;11902;11979;12003
worldai_mob_growth_boss_spell_pool=11840;11841;11842;11955;11956;11957;11958;12013

worldai_mob_growth_mutation_style_pool=103|2;247|44;240|10
worldai_mob_growth_elite_style_pool=103|2;247|44
worldai_mob_growth_champion_style_pool=108|2;112|2;246|44;247|44
worldai_mob_growth_boss_style_pool=256|44;259|44;292|44;302|44;157|22;178|22;167|22

worldai_mob_growth_mutation_ability_pool=Enhanced Evade|1;Tireless|1;CCImmunity|1
worldai_mob_growth_elite_ability_pool=Evade|1;Tireless|1
worldai_mob_growth_champion_ability_pool=Advanced Evade|1;Stoicism|1;CCImmunity|1
worldai_mob_growth_boss_ability_pool=CCImmunity|1;Stoicism|1;Advanced Evade|1;Enhanced Evade|1
```

Boss-stage monsters draw from all earlier eligible pools plus the boss pool, so
they can randomly combine existing boss-like magic, combat styles, and defensive
traits. The chosen loadout is stored in `mob_growth_state`, so the same grown
monster remains stable across scans and respawns until its stage or mutant state
changes.

When a grown monster is applied to a live NPC, the standard monster brain is
also hardened by stage. Elite, Champion, and Boss monsters receive increasing
minimum aggro level and aggro range, and mutant monsters add a small extra
pressure bonus. This keeps grown monsters visibly more dangerous even when the
base spawn was passive or low-threat.

## Dynamic Quest Signals

When a player or credited party member kills a grown or mutant monster, dynamic
quests receive one ordered set of `WorldSignal` candidates. Normal monsters do
not emit these signals.

```text
mob-growth:killed:mob:<mobInternalId>
mob-growth:killed:<elite|champion|boss>
mob-growth:killed:stage:<elite|champion|boss>
mob-growth:killed:mutant
mob-growth:killed:region:<regionId>
mob-growth:killed
```

The dynamic quest runtime applies only the first matching signal for that kill
event, so a single boss kill cannot accidentally advance multiple consecutive
WorldSignal nodes for the same active quest. This gives LLM-authored quest
graphs stable hooks for “defeat the newly grown threat”, “hunt any mutant”, or
“clean up a dangerous region” branches without GM commands.

Dynamic quest story-cache world prefill uses the stable regional form:
`world-signal:mob-growth:killed:region:<regionId>`. The cached story text stays
rebindable, while `DynamicQuestTemplateService` turns that tag into an optional
`followup -> observe_signal -> complete` branch at bind time using the current
target location.

## Eligible NPCs

The first version tracks normal hostile NPCs only:

- must be alive
- must have an internal id
- must have `Realm == None`
- must be targetable
- must not be peace flagged
- level must be greater than 0 and lower than 75

Friendly NPCs, untargetable helper objects, peace NPCs, and extreme-level mobs
are ignored.

## GM Commands

```text
/mobgrowth status
/mobgrowth enable
/mobgrowth disable
/mobgrowth scan [limit]
/mobgrowth top [limit|boss|mutant|region <regionId>]
/mobgrowth region [regionId]
/mobgrowth inspect
/mobgrowth promote <normal|elite|champion|boss> [mobId|target]
/mobgrowth mutate <on|off> [mobId|target]
/mobgrowth deaths <count> [mobId|target]
/mobgrowth decay [limit]
/mobgrowth validatepools
/mobgrowth reset <mobId|target>
```

## API

The local API exposes an operator summary for dashboards and smoke tests:

```text
GET /api/world/mob-growth/summary?limit=20
```

The response includes whether the system is enabled, active grown mob count,
active boss count versus cap, per-stage counts, top regions, and the highest
score active monsters. This is read-only and does not trigger a scan; use
`/mobgrowth scan [limit]` or the runtime timer to populate `mob_growth_state`.

Recommended manual test flow:

```text
/mobgrowth status
/mobgrowth enable
/mobgrowth scan 250
/mobgrowth top 20
/mobgrowth top boss
/mobgrowth top mutant
/mobgrowth region
/mobgrowth inspect
/mobgrowth promote boss target
/mobgrowth mutate on target
/mobgrowth deaths 4 target
/mobgrowth validatepools
/mobgrowth decay 1000
/worldai jobs detail
/worldai processllm 5
/worldai approvals
/worldai approve <eventId>
/worldnews
/history
/mobgrowth disable
```

`/mobgrowth inspect` should be used with a monster targeted. It creates or
updates that monster's growth row and shows score, stage, mutation state, level,
size, region, combat count, player kills, recent death count, idle ticks, and
the selected bonus loadout.

GM force commands operate on the selected target by default, or on an explicit
`mobId` when supplied. `promote` rewrites the persisted stage and refreshes the
derived name, level, size, and bonus loadout. `mutate on/off` toggles mutant
state immediately. `deaths` seeds the recent-death counter so mutation threshold
testing can be performed without waiting for repeated live kills.

`/mobgrowth validatepools` checks configured spell/style/ability pool syntax.
It is intended as a quick operator smoke test after changing server properties.
`/mobgrowth region` shows regional pressure and boss counts; `/mobgrowth top
boss`, `/mobgrowth top mutant`, and `/mobgrowth top region <regionId>` focus the
same top list for live triage.

`/mobgrowth reset target` deletes the selected monster's growth row. The already
spawned object may keep its visible name/level until respawn, but the persistent
growth record is removed.

## Database

New table:

```text
mob_growth_state
```

Important columns:

- `MobId`: persistent NPC id
- `BaseName`, `CurrentName`
- `Region`, `RegionId`
- `BaseLevel`, `GrowthLevel`, `EffectiveLevel`
- `BaseSize`, `EffectiveSize`
- `GrowthScore`
- `SurvivalTicks`, `UnhuntedTicks`, `CombatCount`, `PlayerKills`
- `Stage`
- `RecentDeathCount`, `DeathWindowStartedAt`
- `MutationPending`, `IsMutant`, `LastMutationAt`, `LastMutationChancePercent`,
  `MutationCount`
- `BonusLoadoutKey`, `BonusSpellIds`, `BonusStyleIds`, `BonusAbilityKeys`
- `IsActive`
- `FirstSeenAt`, `LastSeenAt`, `LastKilledAt`, `LastCombatGrowthAt`,
  `LastStageEventAt`

## LLM Boundary

The LLM only receives the boss promotion event after the server has already
decided that a monster reached the Boss stage. The LLM may produce news/history
text, but it cannot change HP, damage, rewards, drops, spawn count, bans, or
commands because the existing WorldAI validator rejects those fields.

## Next Content Layer

Good next steps after live testing:

- add zone danger summaries for `/worldnews`
- expose grown boss counts on the web dashboard
- add GM approval actions that can mark a grown boss as featured server news
- add loot/title/reputation hooks for defeating grown bosses
