# Korean Localization Change Summary

Current scope: finish server-side Korean localization for normal gameplay while excluding item names and boss/named-mob names for now.

## Completed Scope

- `GameServer/language/KR` exists with matching translation keys for the checked `EN` resources.
- Player-facing hardcoded output was broadly moved behind `LanguageMgr.GetTranslation(...)`.
- `/language en` and `/language kr` select English/Korean output for converted server text.
- Korean text was tuned for naturalness and short UI space where possible.
- Constitution terminology is `체력`.
- Item names and boss/named-mob names remain intentionally untranslated.
- The final in-game `@` rendering issue was fixed by changing the actual Atlantis/Isles UI font aliases from `TTFFont` to `GdiFont` with `Gulim` and `Charset 129`.

## Main Translated Areas

- character creation realm/race/class text and descriptions
- attribute descriptions
- game options and keyboard settings
- character info, bonuses, relic, and realm power windows
- player commands and command help
- GM/admin command output where useful for operation
- trainer prompts and specialization/respec text
- teleporter prompts and bracket destinations
- quest offer/progress/reward/completion text
- spell, style, effect, combat, death, resurrection, and crafting messages
- merchant, banker, vault, housing, guild, group, battlegroup, and social messages
- keep, relic, RvR, battleground, mission, and task messages
- zone descriptions and loading/screen descriptions

## Code-Side Localization Support

Several server classes now call `LanguageMgr.GetTranslation(...)` instead of directly sending English literals. This keeps Korean and English selectable through `/language`.

Teleporter code keeps Korean display text separate from DB lookup IDs by mapping Korean destination aliases back to the original English destination names. This prevents translated bracket links from breaking teleport behavior.

The Korean input/display path remains mixed by direction:

- client to server name/input packets decode as strict UTF-8 first, with CP949 fallback/preference for ambiguous Korean int-Pascal data
- server to client display strings encode as CP949
- pregame character-select fonts use Korean-capable TTFs
- in-game Atlantis/Isles UI fonts use `GdiFont` with `Gulim` and `Charset 129`
- client `game.dll` patching is still required

## Verification

Run:

```bash
tools/check-localization.sh --build
```

Expected current state:

- no missing checked EN/KR keys
- no blocked terminology such as `체질`
- build completes with warnings but no errors

Real client verification should follow:

```text
docs/korean-localization-test-checklist.md
```

Chronological notes and failed/final rendering experiments are recorded in:

```text
docs/korean-localization-history.md
```
