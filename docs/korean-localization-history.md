# Korean Localization History

This records the Korean localization work and the fixes that mattered in the local OpenDAoC setup.

Last updated: 2026-05-12

## Context

Live server repo:

```text
/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core
```

Live client folder:

```text
/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoCClient
```

`DOLSharp-master` is an old reference server only. Do not use it as the live server.

The local target is Docker-free server execution with local MariaDB and the .NET 10 SDK.

## Scope Completed

- Korean server language resources were added under `GameServer/language/KR`.
- Broad player-facing hardcoded server text was moved behind `LanguageMgr.GetTranslation(...)`.
- `/language en` and `/language kr` select English or Korean output for converted server messages.
- Character creation, realm/race/class text, descriptions, command output, trainer/teleporter/quest/combat/crafting/social/RvR text were Koreanized within the current scope.
- Item names and boss/named-mob names are intentionally excluded for now.
- Constitution is translated as `체력`, not `체질`.

## Encoding Model That Worked

The final setup is mixed by direction.

- Client to server Korean name/input packets: strict UTF-8 first, with CP949 fallback/preference for ambiguous int-Pascal data.
- Server to client normal display strings: CP949.
- Server to client character overview int-length Pascal strings: CP949.
- Database storage: UTF-8.
- Client rendering: Korean-capable fonts plus the correct DAoC font path.

Important lesson: do not blindly convert outgoing server display strings to UTF-8. That caused broken nameplates or custom text windows. The DAoC client expects many display packets as CP949.

## Main Timeline

### 1. Korean Name Input And Character Select

Korean character creation initially failed or displayed broken text. The working split became:

- decode incoming 1.125+ int-length Pascal strings as UTF-8, with CP949 fallback/preference for ambiguous Korean byte sequences
- keep outgoing character select strings as CP949
- patch client-side `game.dll` validation/codepage behavior
- use Korean-capable pregame fonts

This fixed Korean names on character creation, character select, and in-game overhead nameplates.

### 2. Server-Side Translation Pass

The server language folder was expanded and hardcoded output was converted so Korean and English can be selected through `/language`.

Examples of covered areas:

- `/help`, `/realm`, `/relic`, player commands, GM/admin operational text
- trainer prompts and respec text
- teleporters and Korean bracket aliases
- quests, tasks, missions, battleground/RvR/relic/keep text
- spells, styles, effects, combat, death, resurrection, crafting, merchants, vaults, housing, guild/group/social text

### 3. Client UI Translation Pass

Client-side visible text was translated or adjusted for:

- character creation realm/race/class names and descriptions
- attribute descriptions
- game options
- keyboard settings
- character info, bonuses/resists, relic, and realm power windows
- selected Help window static labels

Long class names were shortened or kept as familiar English-style class names when Korean wording overflowed.

### 4. Failed Rendering Hypotheses

These did not solve the final `@` replacement problem:

- sending custom text windows as UTF-8
- only changing `fonts/uifont.dat`
- only changing `fonts/cmfont.dat`
- only adding `charset=129` to the old `.dat` font configs
- assuming the problem was rare Hangul outside EUC-KR or CP949

The screenshots showed ordinary CP949 Hangul becoming `@`, so the real problem was the specific client UI font path.

### 5. Final In-Game UI Rendering Fix

The in-game text windows, keyboard config, realm/relic windows, and many UI labels do not primarily use `uifont.dat` or `cmfont.dat`.

They use font names from:

```text
OpenDAoCClient/ui/atlantis/assets.xml
OpenDAoCClient/ui/isles/assets.xml
```

The working fix was to change the UI font definitions from `TTFFont` entries pointing at `fonts/KoreanGothic.ttf` into `GdiFont` entries using `Gulim` with Korean charset `129`.

Representative shape:

```xml
<GdiFont>
    <Name>arial11</Name>
    <Height>13</Height>
    <Charset>129</Charset>
    <Face>Gulim</Face>
</GdiFont>
```

Bold UI fonts keep:

```xml
<Bold>true</Bold>
```

The same pattern was applied to the main in-game font aliases such as:

```text
button_small
button_large
arial9
arial11
arial14
chat_small
chat_large
myriadbold
minion
```

`OpenDAoCClient/fonts/defaults.dat` was also set to:

```ini
charset=129
face=굴림
english_face=Gulim
```

After a full client restart, `/keyboard`, `/realm`, `/relic`, server custom text windows, and Help/custom windows displayed Korean normally.

### 6. Pregame Race/Class Description Rendering Fix

Character creation and character select use the separate pregame UI:

```text
OpenDAoCClient/pregame/asset.xml
OpenDAoCClient/pregame/styles.xml
```

The earlier TTF replacement fixed the worst bitmap-font Hangul issue, but later race/class description testing showed that valid Korean syllables in the DLL descriptions could still appear as `@`.

Current pregame guidance matches the in-game fix: define the main pregame font aliases as `GdiFont` entries using `Gulim` with Korean charset `129`.

Representative shape:

```xml
<GdiFont>
    <Name>button_large</Name>
    <Height>13</Height>
    <Bold>true</Bold>
    <Charset>129</Charset>
    <Face>Gulim</Face>
</GdiFont>
```

Apply this to `button_small`, `button_large`, `arial9`, `arial11`, `arial14`, `large_gold`, `med_gold`, and `medium`, then fully restart the client.

### 7. Client UI Readability And Menu Pass

The May 11 pass focused on visible client-side polish after the server translation work:

- `ui/atlantis/styles.xml` and `ui/isles/styles.xml` now use larger `LinePadding` for text areas so Korean lines have more vertical breathing room.
- Text-area active/hotspot color was normalized to orange so clickable `[destination]` text stands out like the original English dialogs.
- Teleporter Korean text in `GameServer/language/KR/OtherSentences.txt` was reformatted so clickable destinations start each line.
- `data/loading/tips.dat` was replaced with Korean loading tips.
- `default*.ini` name options now default to `Visibility=127`, enabling the player's own name display for new/default profiles.
- Atlantis/Isles command, interface-elements, menu bar, social/guild, mount, group, mini-pet, target, keep/siege labels were translated where the client XML exposes visible labels.
- `game.dll` class/race strings were patched only inside existing safe byte slots. Examples: `영웅 -> 히어로`, `검의달인 -> 블마스터`, `정신술사 -> 멘탈리스트`, `이단자 -> 헤러틱`, `노르스 -> 노스맨`.

Because the client resources are loaded at startup, a full client restart is required after these changes.

Follow-up correction from the same pass:

- Several client XML files originally declared `ISO-8859-1`. Adding UTF-8 Korean text without changing that declaration caused menu/interface mojibake.
- Korean UI XML files that contain Hangul should declare `encoding="UTF-8"`.
- `data/loading/tips.dat` is not XML and should be saved as CP949/ANSI Korean for this client path.

NPC interact-window hotspot correction:

- The DAoC interact window treats bracketed text as clickable hotspots, but only the normal interact popup path applies hotspot coloring and click handling.
- Korean NPC popup text had been routed through `SendCustomTextWindow` to improve rendering/wrapping, but that window type does not support NPC hotspot clicks.
- `GameNPC.SayTo` now keeps non-interactive Korean popup text on `SendCustomTextWindow`, while messages containing bracket hotspots use the normal popup path.
- Keep the clickable token inside `[]` as the original English teleport/command keyword, then put the Korean label beside it.
- Example: `[Castle Sauvage] 소바쥬 성 - 카멜롯 힐스`.
- `ui/atlantis/interact_window.xml` and `ui/isles/interact_window.xml` now explicitly declare `[` as `HotspotDelineator` for interact text.

### 8. Custom UI Korean Patch Pass

The first custom UI test target is `DAOC-UI-Chooser`, a Bob's UI based custom UI copied into:

```text
OpenDAoCClient/ui/custom
```

The same Korean rendering model applies to custom UI files:

- replace text fonts in `ui/custom/assets.xml` and `ui/custom/ChatFont.xml` with `GdiFont`, `Gulim`, `Charset 129`
- change any custom XML file that directly contains Korean labels from `ISO-8859-1` to `UTF-8`
- add `HotspotDelineator` to custom interact windows so bracketed NPC destinations remain clickable
- keep `OptionsChooser.exe` out of the first Korean test loop, because option presets can overwrite patched root XML files

Initial visible custom UI labels were translated in:

```text
ui/custom/custom0_window.xml
ui/custom/command_window.xml
ui/custom/menu_bar_window.xml
ui/custom/main_menu_window.xml
ui/custom/stats_group_window.xml
ui/custom/interface_elements_window.xml
ui/custom/community_window.xml
```

Follow-up custom UI correction on 2026-05-12:

- `ui/custom/key_config.xml` and `ui/custom/Options/Keyboard Options/- Disable/key_config.xml` now use UTF-8 Korean static labels.
- The key configuration action list has built-in labels from `game.dll`, so the live `game.dll` was patched with short CP949 Korean strings for actions/categories such as `지면 대상`, `그룹 대상`, `근처적`, `카메라전환`, `스크린샷촬영`, `마우스룩전환`, and `앞으로이동`.
- `ui/custom/lfg_window.xml` no longer leaves `class0`/`class59` or `직업59` placeholders visible; class filters use short Korean class names.
- Custom UI chooser/menu preset labels under `ui/custom/Options/- Main Menu -/`, armor-resist helper text, quest/merchant coin labels, stats point labels, and several option preset copies were translated.
- XML validation after the pass: `1443` custom UI XML files checked, `0` parse errors.

The cafe-facing method is recorded in:

```text
docs/custom-ui-korean-guide.md
```

## Current Important Files

Server:

```text
CoreBase/Network/BaseServer.cs
CoreBase/Network/PacketIn.cs
CoreBase/Network/PacketOut.cs
GameServer/language/KR/
GameServer/language/EN/
GameServer/packets/Server/PacketLib168.cs
GameServer/packets/Server/PacketLib175.cs
GameServer/packets/Server/PacketLib181.cs
GameServer/packets/Client/168/CharacterCreateRequestHandler.cs
GameServer/packets/Client/168/PlayerInitRequestHandler.cs
GameServer/gameobjects/GameNPC.cs
```

Client:

```text
OpenDAoCClient/game.dll
OpenDAoCClient/main.dat
OpenDAoCClient/pregame/asset.xml
OpenDAoCClient/pregame/styles.xml
OpenDAoCClient/fonts/defaults.dat
OpenDAoCClient/fonts/namefont.dat
OpenDAoCClient/ui/atlantis/assets.xml
OpenDAoCClient/ui/isles/assets.xml
OpenDAoCClient/ui/atlantis/help_window.xml
OpenDAoCClient/ui/isles/help_window.xml
```

Use `game.dll` only. Backup DLLs are historical safety copies.

## Verification Used

Server-side translation/build check:

```bash
tools/check-localization.sh --build
```

Focused unit tests used during packet/client-window work:

```bash
dotnet test Tests/Tests.csproj --filter "WriteCustomTextWindowData_WithLongKoreanText_ShouldSplitByDefaultEncodedByteLength|WriteCustomTextWindowString_WithKoreanText_ShouldWriteDefaultEncodedPascalString|WriteDialogMessage_WithKoreanText_ShouldKeepAllDefaultEncodedBytesAndNullTerminate|ShouldUseCustomTextWindowForSayTo_ShouldOnlyRouteKoreanPopups|ShouldUseCustomTextWindowForStarterHelp_ShouldOnlyRouteKoreanClients"
```

Client smoke test:

```text
/language kr
/kotest
/keyboard
/realm
/relic
```

Confirmed result after the final font-path fix:

```text
모두 다 잘나와
```

## Watchouts

- Restart the client after any XML/font/DLL change. The client caches UI assets.
- Restart the server after server code or language-file changes.
- Built-in client Help content is separate from server custom text windows.
- If Korean appears as `@`, check the actual UI font alias path first.
- If `@` appears only on character creation/select descriptions, check `pregame/asset.xml` first.
- If Korean appears as mojibake, check whether UTF-8 bytes are being read as CP949 or CP949 bytes are being read as UTF-8.
- If character select columns drift, do not switch `WritePascalStringIntLE()` to UTF-8.
