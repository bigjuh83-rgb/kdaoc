# Korean Localization Test Checklist

Use this when a real client is available. Item and boss names are intentionally outside the current translation scope.

## Preflight

- Build passes with `tools/check-localization.sh --build`.
- Server starts from `OpenDAoC-Core`, not `DOLSharp-master`.
- Client uses the patched `game.dll` only; backup DLLs stay unused.
- `main.dat` has `mbcs=1` and `codepage=949`.
- Pregame UI fonts point to Korean-capable TTF fonts.
- In-game Atlantis/Isles UI font aliases use `GdiFont`, `Gulim`, and `Charset 129`.

## Login And Language

- Log in with a fresh account or existing local account.
- Run `/language kr`.
- Run `/kotest`.
- Confirm Korean appears in:
  - system window
  - chat window
  - popup window
  - custom text window

Switch back with `/language en` and confirm English still appears normally.

## Character Creation

- Create an English-name character.
- Create a Korean-name character with fully composed Hangul, for example `가나다`.
- Confirm incomplete Hangul composition is not submitted accidentally before pressing Create.
- Confirm character creation does not crash or disconnect.
- Confirm character select shows the Korean name correctly.
- Enter the world and confirm overhead nameplate shows the Korean name correctly.

## Character Creation Text

Check all three realms:

- realm names and realm descriptions
- race names and race descriptions
- class names and class descriptions
- attribute descriptions only; attribute labels stay in English by design
- character select lines such as level/class/zone text

Expected terminology:

- Constitution is `체력`, not `체질`.
- Class names may stay short if a long Korean form overflows the UI.

## In-Game Windows

Open and scan:

- Game Options
- Keyboard Settings
- character information
- bonuses/resists
- relic and realm power windows
- trainer windows
- merchant/banker/vault windows
- housing windows if available
- guild/group/battlegroup/social windows
- quest journal
- help/info/delve/detail windows

Watch for:

- `@` replacement characters
- `???`
- broken byte-looking text
- line overflow or clipped text
- clickable bracket tokens that no longer work

## Commands

Run common player commands in Korean mode:

```text
/help
/realm
/relic
/where
/played
/xp
/combatstats
/friend
/ignore
/group
/guild
```

Then run a small GM/admin smoke test if the account has permission:

```text
/player
/mob
/npc
/teleport
/reload
```

Only player-facing output needs polished Korean. Debug-only or GM-only wording can be fixed later if it does not affect normal gameplay.

## Teleporters

Test Korean bracket links and aliases:

- normal realm teleporters
- Shrouded Isles teleporters
- inland/live teleporters
- all-realms teleporter
- Ancient Bound Djinn

Click Korean destination tokens and confirm the teleport still resolves to the correct English DB destination.

## Quests And Trainers

Start at least one low-level quest per realm:

- Albion
- Midgard
- Hibernia

Check:

- offer text
- objectives
- progress text
- reward text
- completion text
- trainer specialization/respec prompts

## Regression Notes

If Korean appears as `???`, check font coverage and client-side rendering first.

If Korean appears as `@`, check the actual UI font path first. In-game text windows and keyboard/realm/relic UI use `ui/atlantis/assets.xml` or `ui/isles/assets.xml`; changing only `uifont.dat` or `cmfont.dat` is not enough.

If Korean appears like mojibake, check the direction:

- client to server creation/name packets should decode UTF-8
- server to client display packets should encode CP949

If character select columns drift or class text merges into the name, keep `WritePascalStringIntLE()` on CP949 rather than UTF-8.
