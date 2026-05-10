# Korean Localization History

This records the Korean localization work and the fixes that mattered in the local OpenDAoC setup.

Last updated: 2026-05-10

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
- If Korean appears as mojibake, check whether UTF-8 bytes are being read as CP949 or CP949 bytes are being read as UTF-8.
- If character select columns drift, do not switch `WritePascalStringIntLE()` to UTF-8.
