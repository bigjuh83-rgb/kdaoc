# OpenDAoC 1.127 Korean Localization Patch Notes

This note records the working Korean text setup for the local OpenDAoC 1.127 client/server test environment.

Last verified: 2026-05-10

## Current Status

Server-side Korean localization is considered feature-complete for the current scope, excluding item names and boss/named-mob names by choice.

Recent server-side pass:

- Added/cleaned `GameServer/language/KR` translations with `EN`/`KR` key parity.
- Converted broad player-facing hardcoded output to `LanguageMgr.GetTranslation(...)` so `/language en` and `/language kr` can select output.
- Koreanized realm/race/class/descriptions, option-window text, keyboard-setting text, bonus/relic/realm-power text, trainer prompts, command output, teleporter text, quest text, spell/effect/style/combat messaging, keep/relic/RvR messaging, housing/social/vault/merchant/crafting output, and zone descriptions.
- Kept item names and boss/named-mob names out of scope for now.
- Standardized Constitution as `체력`, not `체질`.
- Removed the visible `http://planner.atlasfreeshard.com` planner text from the relevant client-facing output.
- Added Korean teleporter destination aliases so Korean bracket text can still resolve to English DB destination IDs.
- Preserved English fallback behavior through `/language en`.

Current checks:

```bash
tools/check-localization.sh --build
```

See also:

- `docs/localization-checks.md`
- `docs/korean-localization-change-summary.md`
- `docs/local-mariadb-dotnet-runbook.md`
- `docs/korean-localization-test-checklist.md`

## Goal

Make Korean display and input work in these places:

- In-game chat window.
- Popup/custom text windows.
- Player overhead nameplate.
- Character select screen.
- Korean character names such as `짱이다`.

## Important Conclusion

The final working setup is mixed:

- Client -> server 1.125+ int-length Pascal strings: read as strict UTF-8 first, with strict CP949 fallback/preference for ambiguous Korean byte sequences.
- Server -> client normal Pascal strings: write as CP949.
- Server -> client 1.126 character overview int-length Pascal strings: write as CP949.
- Pregame client UI fonts: replace bitmap fonts with Korean-capable TTF fonts.
- In-game Atlantis/Isles UI fonts: use `GdiFont`, `Gulim`, and `Charset 129`.
- Client `game.dll`: patch codepage/MBSC/name validation checks.

Do not blindly convert every outgoing string to UTF-8. That broke overhead player names. When UTF-8 bytes for `짱이다` were interpreted as CP949, the nameplate appeared like `吏깃씠??` / `吏깆씠...`.

## Paths Used

Server repo:

```text
/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core
```

Client folders patched:

```text
/mnt/c/Program Files (x86)/Electronic Arts/Dark Age of Camelot
/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoCClient
```

Reference-only old server:

```text
/mnt/c/Users/uihan/Desktop/다옥프리서버/DOLSharp-master
```

`DOLSharp-master` is kept for reference only. Run the live server from `OpenDAoC-Core`.

Old Docker executable path from WSL, kept only for historical notes below:

```bash
'/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe'
```

## Server Code Changes

### 1. Default Encoding: CP949

File:

```text
CoreBase/Network/BaseServer.cs
```

Change:

```csharp
public static readonly Encoding DefaultEncoding = CodePagesEncodingProvider.Instance.GetEncoding(949);
```

Original was codepage `1252`.

This makes normal `WritePascalString`, `WriteString`, `FillString`, and other default-encoding packet output use CP949.

### 2. Read 1.125+ Int Pascal Strings As UTF-8 With CP949 Fallback

File:

```text
CoreBase/Network/PacketIn.cs
```

`ReadIntPascalStringLowEndian()` was changed from `ReadString((int) ReadIntLowEndian())` to reading raw bytes. It now tries strict UTF-8 first, then compares strict CP949 when both decoders succeed so CP949 Korean that also forms valid UTF-8-like bytes is not misread.

Why:

- Korean character creation/name input from the 1.127 client arrived correctly through UTF-8 decoding.
- Some client/server int-Pascal paths can still contain CP949 bytes, so ambiguous Korean byte sequences prefer the decoded form that actually contains Hangul.
- This affected client -> server paths such as login/name/create data.

Working shape:

```csharp
public string ReadIntPascalStringLowEndian()
{
    uint declaredLength = ReadIntLowEndian();
    int maxlen = GetReadableLength(declaredLength);

    if (maxlen <= 0)
        return string.Empty;

    // Read only the bytes actually available, trim at NUL, then:
    // 1. decode strict UTF-8;
    // 2. if strict CP949 also succeeds and produces Hangul where UTF-8 does not,
    //    prefer CP949;
    // 3. otherwise keep UTF-8, falling back to default CP949 only on UTF-8 failure.
    return DecodeIntPascalString(readBytes);
}
```

Requires:

```csharp
using System.Text;
```

### 3. Keep Outgoing Int Pascal Strings As CP949

File:

```text
CoreBase/Network/PacketOut.cs
```

Final working `WritePascalStringIntLE()` uses `BaseServer.DefaultEncoding`, not UTF-8:

```csharp
public void WritePascalStringIntLE(ReadOnlySpan<char> chars)
{
    if (chars.IsEmpty)
    {
        WriteIntLowEndian(0);
        return;
    }

    int byteCount = BaseServer.DefaultEncoding.GetByteCount(chars);
    WriteIntLowEndian((uint) byteCount + 1);
    WriteNonNullTerminatedString(chars);
    WriteByte(0);
}
```

Why:

- Character select screen uses `PacketLib1126.SendCharacterOverview()` with `WritePascalStringIntLE(character.Name)`.
- UTF-8 here produced broken text and field drift such as `pF ??the Fighter`.
- CP949 plus Korean-capable pregame font fixed character select.

### 4. Hangul Name Validation

File:

```text
GameServer/packets/Client/168/CharacterCreateRequestHandler.cs
```

Replace both name regex checks:

```csharp
var nameCheck = new Regex(@"^(?:[A-Z][a-zA-Z]|[\p{IsHangulSyllables}\p{IsHangulJamo}\p{IsHangulCompatibilityJamo}])");
```

This allows a Korean first character, while keeping the original English-name path.

### 5. Korean Test GM Command

File:

```text
GameServer/commands/gmcommands/KoreanTest.cs
```

Command:

```text
/kotest
```

It sends Korean text to:

- System window.
- Chat window.
- Popup window.
- Custom text window.

Test string:

```text
한글 테스트 가나다라마바사
```

Use this after each server/client text change.

## Client main.dat

Both client folders need this:

```ini
[main]

[international]
mbcs=1
codepage=949
```

Files:

```text
C:\Program Files (x86)\Electronic Arts\Dark Age of Camelot\main.dat
C:\Users\uihan\Desktop\다옥프리서버\OpenDAoCClient\main.dat
```

WSL paths:

```text
/mnt/c/Program Files (x86)/Electronic Arts/Dark Age of Camelot/main.dat
/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoCClient/main.dat
```

## Client Fonts

### Runtime UI Fonts

Files referenced by Atlantis/Isles UI:

```text
ui/fonts/KoreanGothic.ttf
ui/fonts/KoreanGothic-Bold.ttf
```

Current final choice:

```text
C:\Windows\Fonts\malgunbd.ttf
```

It was copied over both `KoreanGothic.ttf` and `KoreanGothic-Bold.ttf`.

Reason:

- `NotoSansKR-VF.ttf` worked, but looked too light/blurry in the DAoC client renderer.
- `malgunbd.ttf` looked darker and clearer, and was accepted as the final font choice.

If files are read-only, use:

```bash
for dir in '/mnt/c/Program Files (x86)/Electronic Arts/Dark Age of Camelot/ui/fonts' '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoCClient/ui/fonts'; do
  ts=$(date +%Y%m%d-%H%M%S)
  chmod u+w "$dir/KoreanGothic.ttf" "$dir/KoreanGothic-Bold.ttf"
  cp "$dir/KoreanGothic.ttf" "$dir/KoreanGothic.ttf.backup-before-malgunbold-$ts"
  cp "$dir/KoreanGothic-Bold.ttf" "$dir/KoreanGothic-Bold.ttf.backup-before-malgunbold-$ts"
  cp '/mnt/c/Windows/Fonts/malgunbd.ttf' "$dir/KoreanGothic.ttf"
  cp '/mnt/c/Windows/Fonts/malgunbd.ttf' "$dir/KoreanGothic-Bold.ttf"
  chmod 555 "$dir/KoreanGothic.ttf" "$dir/KoreanGothic-Bold.ttf"
done
```

### Atlantis/Isles UI XML

Files:

```text
ui/atlantis/assets.xml
ui/isles/assets.xml
```

Final in-game UI fix: important font entries should use `GdiFont` with Korean charset `129`. The keyboard config, realm/relic windows, Help/custom text windows, and generic text areas use these UI font aliases. Changing only `uifont.dat` or `cmfont.dat` did not fix those windows.

```xml
<GdiFont>
    <Name>arial11</Name>
    <Height>13</Height>
    <Charset>129</Charset>
    <Face>Gulim</Face>
</GdiFont>
```

Similar entries were applied for:

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

Bold aliases such as `button_large` and `myriadbold` include `<Bold>true</Bold>`.

The final `@` replacement issue was resolved after applying this to both Atlantis and Isles assets, then fully restarting the client.

### Pregame / Character Select Fonts

Character select does not use the in-game Atlantis skin font entries. It uses:

```text
pregame/asset.xml
pregame/styles.xml
```

The first working fix was converting `pregame/asset.xml` bitmap font entries to `TTFFont` entries. Later race/class description testing showed that the pregame TTF path could still render some Hangul syllables as `@`, so the current working direction is to match the in-game fix: use `GdiFont`, `Gulim`, and Korean charset `129` for the main pregame font aliases.

Most important:

```xml
<GdiFont>
    <Name>button_large</Name>
    <Height>13</Height>
    <Bold>true</Bold>
    <Charset>129</Charset>
    <Face>Gulim</Face>
</GdiFont>
```

Why:

- `pregame/styles.xml` template `256x16_no_bg` uses `<Name>button_large</Name>`.
- Character select top line uses `256x16_no_bg`.
- The original `button_large` was `ui/fonts/button_12.tga`, a bitmap font without Hangul glyphs.
- Replacing it with Korean-capable fonts fixed `짱이다 the Fighter` on character select.
- Using `GdiFont` avoids the pregame TTF renderer replacing some valid Korean syllables with `@` in race/class descriptions.

Pregame font names converted:

```text
button_small
button_large
arial9
arial11
arial14
large_gold
med_gold
medium
```

Client must be fully restarted after pregame font XML changes.

### Overhead Name Font

Files:

```text
fonts/namefont.dat
```

Current content:

```ini
[font00]
type=gdi
height=16
bold=1
charset=129
```

This alone did not fix the overhead nameplate, but it is kept in the working setup.

### Font Defaults

File:

```text
fonts/defaults.dat
```

Current important setting:

```ini
charset=129
face=굴림
english_face=Gulim
```

## game.dll Patches

Patch both client folders:

```text
C:\Program Files (x86)\Electronic Arts\Dark Age of Camelot\game.dll
C:\Users\uihan\Desktop\다옥프리서버\OpenDAoCClient\game.dll
```

### Current Verified Bytes

Current verified offsets:

```text
0x0b90e0 = 68 a3 f9 97 00
0x57f9a3 = 66 6f 6e 74 73 5c 75 69 66 6f 6e 74 2e 64 61 74 00
0x1005ee = eb 5a 57 68 64 c8 93 00
0x88b8e  = eb 72 ff 05 e0 f3 f4 00
0x1a3b35 = eb 0d 85 f6 74 61 68 20
0x1a3695 = eb 0b 56 e8 a0 01 00 00
0x37b7e2 = b8 b5 03 00 00 90
0x107c39 = 68 b5 03 00 00
```

Meaning:

- `0x0b90e0`: patch the popup font-loader caller so it pushes `0x97f9a3` instead of the old empty-string pointer `0x937c08`. `0x97f9a3` is a writable `.data` slack slot that now stores `fonts\\uifont.dat\\0`. Without this, the popup loader never opens `uifont.dat` and always rebuilds the hardcoded bitmap fallback table on restart.
- `0x57f9a3`: injected `fonts\\uifont.dat\\0` string used by the caller patch above.
- `0x1005ee`: keep the parsed popup font-section loader on the non-bitmap path so the `type=gdi` entries from `fonts/uifont.dat` win once the caller actually passes the right filename.
- `0x88b8e`: MBCS/crash-protection branch patch. Keep as `EB`; restoring this caused crashes.
- `0x1a3b35`: bypass rename confirm A-Z-only validation.
- `0x1a3695`: bypass character select/play A-Z-only validation.
- `0x37b7e2`: force the client CRT `GetACP()` path to return CP949 (`mov eax, 949; nop`). This is required when Windows has the UTF-8 beta/system ANSI codepage (`ACP=65001`), otherwise legacy Dialog windows decode Korean CP949 packet text as mojibake.
- `0x107c39`: replace the remaining numeric `push 1252` codepage branch with `push 949`; this covers legacy Dialog text paths that still decode CP949 packet bytes as Windows-1252.

Also patch all codepage string/table occurrences from `1252` to `949`. Current DLLs have no `1252` string hits and many `949` hits.

### Reapply Script

Run from WSL. This patches one or more `game.dll` files and creates timestamped backups.

```bash
python3 /mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoCClient/tools/apply-korean-game-dll-patch.py \
  /mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoCClient/game.dll \
  '/mnt/c/Program Files (x86)/Electronic Arts/Dark Age of Camelot/game.dll'
```

## Docker Build And Restart

Build:

```bash
'/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe' compose -f docker-compose.local.yml build gameserver
```

Restart server:

```bash
'/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe' compose -f docker-compose.local.yml up -d gameserver
```

Tail logs:

```bash
'/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe' compose -f docker-compose.local.yml logs --tail=80 gameserver
```

Normal startup includes:

```text
Server is now listening for incoming connections on 0.0.0.0:10320
GameServer startup completed
```

There is an existing startup noise error from `GameLoopTickPacerStats` index range. It did not prevent the server from working.

## DB Checks

Confirm the character name is stored correctly:

```bash
'/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe' compose -f docker-compose.local.yml exec -T db mariadb --ssl=0 -uroot -p'<DB_PASSWORD>' -e "SELECT Name, HEX(Name), CHAR_LENGTH(Name), LENGTH(Name), Class, Race, Region FROM opendaoc.DOLCharacters WHERE AccountName='bigjuh';"
```

Good result for `짱이다`:

```text
Name    HEX(Name)                 CHAR_LENGTH(Name) LENGTH(Name)
짱이다  ECA7B1EC9DB4EB8BA4         3                 9
```

The DB stores UTF-8 correctly.

## Verification Checklist

1. Restart the game client after any client font/XML/DLL change.
2. Restart the Docker gameserver after server code changes.
3. Log in with the 1.127 client.
4. On character select, verify:

```text
짱이다 the Fighter
```

5. Enter game and verify overhead nameplate:

```text
짱이다
<Clan Cotswold>
```

6. Use GM command:

```text
/kotest
```

7. Verify Korean appears in:

- System window.
- Chat window.
- Popup window.
- Custom text window.

## Known Failed Attempts

Do not repeat these unless intentionally testing:

- Sending `PacketLib1124.SendPlayerCreate()` player name/guild/last/title as UTF-8 broke or did not fix overhead nameplate.
- Sending `PacketLib179.SendUpdatePlayer()` player name/guild/last/title as UTF-8 broke or did not fix overhead nameplate.
- Sending custom text window strings as UTF-8 made Korean appear as replacement characters in custom windows.
- Making `WritePascalStringIntLE()` UTF-8 caused character select field drift, e.g. name text merging into `the Fighter`.
- Only adding `charset=129` to `fonts/namefont.dat` did not fix overhead Korean by itself.
- Only adding `charset=129` to `uifont.dat` or `cmfont.dat` did not fix in-game keyboard/realm/relic/custom text windows because those windows use `ui/atlantis/assets.xml` or `ui/isles/assets.xml`.
- Using the default pregame bitmap `button_large` font cannot render Hangul correctly on character select.

## Quick Mental Model

If Korean appears as `???`, the client likely cannot render glyphs or input validation rejected/replaced characters.

If Korean appears like `吏깃씠??` / `吏깆씠...`, UTF-8 bytes are being read as CP949.

If Korean appears like `¯�̴�`, CP949 bytes are being read as UTF-8.

For the current 1.127 setup:

- Incoming Korean from client creation/name packets: UTF-8, with CP949 fallback/preference for ambiguous int-Pascal data.
- Outgoing display text to DAoC client: CP949.
- Pregame fonts must support Hangul.
- In-game Atlantis/Isles font aliases must use the Korean GDI font path.

## History

The chronological Korean-localization history, including the final `@` rendering fix and failed experiments, is recorded in:

```text
docs/korean-localization-history.md
```
