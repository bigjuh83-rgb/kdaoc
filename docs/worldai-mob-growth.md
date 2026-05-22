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
- Grown monsters can receive a capped level bonus and health multiplier.
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
```

When the active Boss cap is full, newly grown monsters can still accumulate
score but remain capped at `Champion` until an existing Boss is killed, reset,
or otherwise marked inactive.

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

Regions can be excluded by region id:

```text
worldai_mob_growth_excluded_regions=1,10,27
```

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
/mobgrowth top [limit]
/mobgrowth inspect
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
/mobgrowth inspect
/worldai jobs detail
/worldai processllm 5
/worldai approvals
/worldai approve <eventId>
/worldnews
/history
/mobgrowth disable
```

`/mobgrowth inspect` should be used with a monster targeted. It creates or
updates that monster's growth row and shows score, stage, level, region, combat
count, player kills, and idle ticks.

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
- `GrowthScore`
- `SurvivalTicks`, `UnhuntedTicks`, `CombatCount`, `PlayerKills`
- `Stage`
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
- map certain approved boss personalities to existing safe spell/ability sets
