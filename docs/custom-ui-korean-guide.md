# Custom UI Korean Patch Guide

Last updated: 2026-05-23

This note records how the local DAoC custom UI was prepared for Korean text so the same method can later be explained to cafe users.

## Tested UI

The current local custom UI was installed from:

```text
https://github.com/CynicalJedi/DAOC-UI-Chooser
```

It was copied into:

```text
OpenDAoCClient/ui/custom
```

The first test target is the root `ui/custom` layout. Do not run `OptionsChooser.exe` while testing Korean, because the chooser can overwrite root XML files with option presets that still use the original English/font definitions.

## Required Font Fix

Korean text in DAoC UI XML should use Korean-capable GDI fonts. Bitmap/old TTF font paths often turn Hangul into `@` or mojibake.

Patch `ui/custom/assets.xml` and `ui/custom/ChatFont.xml` so common UI fonts use `GdiFont`, `Gulim`, and charset `129`.

`Gulim` is the current recommended custom UI font for this client path. It is less pretty than newer fonts, but it has been the most reliable option for this old DAoC GDI rendering path.

The small quest/trainer Accept/Decline dialog is a separate client path. It does not become Korean just because `ui/custom/popup.xml` or Atlantis/Isles XML fonts are correct. The real permanent fix is in `game.dll`: the popup font-loader caller was passing an empty filename, so the client never opened `fonts/uifont.dat` and always rebuilt the hardcoded bitmap fallback table. The local Korean build now patches that caller to pass `fonts\\uifont.dat`, and it also keeps `0x1005ee` on `eb` so the parsed popup font sections stay on the GDI branch.

Example:

```xml
<GdiFont>
  <Name>Font_Buttons</Name>
  <Height>13</Height>
  <Charset>129</Charset>
  <Face>Gulim</Face>
</GdiFont>
```

Use the same pattern for the main custom UI font aliases:

```text
Font_Memo
Font_Buttons
Font_Buttons_Small
Font_Social
Font_Headings
Font_Headings_Small
Font_Titles
Font_Transparent
Font_TransparentSmall
Font_TransparentBold
Font_ChampXP
Font_Chat
```

Leave icon/symbol-only fonts alone unless they are proven to render Korean text.

## Required XML Encoding Fix

Many DAOC-UI-Chooser XML files declare:

```xml
<?xml version="1.0" encoding="ISO-8859-1"?>
```

Any custom UI XML file that directly contains Korean text must instead declare:

```xml
<?xml version="1.0" encoding="UTF-8"?>
```

Without this, Korean labels can display as broken Latin characters or question marks.

## Chat/System Message Line Spacing

Korean glyphs are taller than the original English bitmap-style chat font. If the custom chat window keeps the original tight line spacing, system/chat messages can look vertically cramped even when Hangul itself renders correctly.

Patch the chat control in:

```text
ui/custom/chat_window.xml
```

Use a larger `LinePadding`:

```xml
<ChatControlDef>
  ...
  <LinePadding>3</LinePadding>
  ...
</ChatControlDef>
```

If a user's preferred custom UI option replaces `chat_window.xml`, apply the same change to that option's chat window file too.

## Clickable NPC Text

For NPC interaction windows, bracketed text must remain in the normal interact popup path to be clickable.

The custom UI interact window should include:

```xml
<HotspotDelineator>[</HotspotDelineator>
```

The local test build added this to:

```text
ui/custom/interact_window.xml
ui/custom/Options/Interact/Style 01/interact_window.xml
```

Keep clickable command keys inside brackets in English, then place the Korean label next to them.

Example:

```text
[Castle Sauvage] 소바쥬 성 - 카멜롯 힐스
```

## Local Korean Label Pass

The custom UI Korean passes translated the visible labels in the root files and the option preset files.

Root files covered first:

```text
ui/custom/custom0_window.xml
ui/custom/command_window.xml
ui/custom/menu_bar_window.xml
ui/custom/main_menu_window.xml
ui/custom/stats_group_window.xml
ui/custom/interface_elements_window.xml
ui/custom/community_window.xml
```

The second pass covered broader in-game custom UI files and option presets:

```text
ui/custom/key_config.xml
ui/custom/lfg_window.xml
ui/custom/options_window.xml
ui/custom/merchant_window.xml
ui/custom/hookpoint_merchant_window.xml
ui/custom/stats_spec_abil_window.xml
ui/custom/Options/- Main Menu -/
ui/custom/Options/Armor Resists/
ui/custom/Options/Keyboard Options/
ui/custom/Options/Interface Options/
ui/custom/Options/Menu Bar/
ui/custom/Options/Command*/
ui/custom/Options/Quest/
ui/custom/Options/Stats Skills/
ui/custom/Options/Status Index/
```

Short labels are preferred because many custom UI buttons are only 60 to 68 pixels wide.

Examples:

```text
Actions -> 동작
Group -> 그룹
Realm -> 렐름
Utility -> 도구
Health -> 체력
Endurance -> 지구력
Power -> 마나
War Map -> 전쟁지도
Rlm Bonus -> 렐름보너스
Lag Meter -> 지연측정
Menu -> 메뉴
Journal -> 퀘스트
Inventory -> 가방
```

For LFG class filters, do not leave `class0`, `class59`, or `직업59` placeholders visible. Map them to short class labels such as `팔라딘`, `블레이드마스터`, `히어로`, `밴시`, `뱀피르`, `워락`, and `마울러`.

For the key configuration action list, the visible action names do not all come from `ui/custom/key_config.xml`. Many of them come from fixed byte slots inside `game.dll`. The local patch uses short CP949 labels that fit the original slots, for example:

```text
Nearest Enemy -> 근처적
Ground Target -> 지면 대상
Target Group -> 그룹 대상
Camera Toggle -> 카메라전환
Take Screenshot -> 스크린샷촬영
Mouselook Toggle -> 마우스룩전환
Move Forward -> 앞으로이동
```

When patching those built-in labels, keep the Korean string shorter than or equal to the original byte length, and encode it as CP949. `game.dll` is the live client DLL; the other `game*.dll` files in the local client folder are backups unless deliberately selected.

For the popup/dialog font path, keep these `game.dll` fixes together:

- `0x0b90e0`: change the popup font-loader caller from `push 0x937c08` (empty filename) to `push 0x97f9a3`, where `0x97f9a3` contains `fonts\\uifont.dat\\0` in `.data` slack.
- `0x1005ee`: keep this as `eb` so the parsed popup font sections skip the bitmap branch and use the GDI entries from `fonts/uifont.dat`.

Without the caller patch, the popup path never opens `uifont.dat` and still rebuilds the old 13-slot bitmap table on every restart.

## 2026-05-23 Custom UI Cleanup Notes

The later custom UI pass fixed several issues that only appeared after the Korean font size and tab labels were made readable in game.

Chat font:

- The Atlantis and Custom UI chat font paths must be patched together. Patching only one skin makes the font-size menu look like it works in one UI but not the other.
- The chat font size menu is live enough for the local client, but the chosen GDI/font file and `LinePadding` still decide whether Korean looks cramped or too loose.
- If the chat input looks vertically too tall after increasing the font size, reduce the chat control padding before changing the font again.

Character creation:

- Realm/race/class labels use phonetic Korean names when possible, not meaning translations.
- Keep names short enough for the original button slots. Examples: `피르볼그`, `드루이드`, `블레이드`.
- The realm description text needs extra vertical spacing because Korean glyphs are taller than the original English text. Apply the same spacing fix to Albion, Hibernia, and Midgard description panels.

Stats windows:

- Character stat labels should stay Korean where they are normal user-facing stats: `힘`, `체력`, `민첩`, `순발`, `지능`, `공감`, `신앙`, `매력`.
- Damage/resist type labels use English phonetic Korean where that is clearer and shorter: `크러쉬`, `슬래쉬`, `피어싱`, `콜드`, `히트`, `매터`, `바디`, `스피릿`, `에너지`.
- Do not translate database skill rows for this client patch. Server/database Korean skill-name changes affect English users and can drift from source expectations. Keep the DB reverted and handle display/UI wording in client resources where possible.

Custom tab overlap:

Some Bob's UI custom windows draw both the tab caption and a duplicate title label for the active first tab. With Korean, these labels overlap when the first tab has focus. Do not move the tab bar first; remove or blank the duplicate content title label for the active first tab.

Confirmed local fixes:

```text
ui/custom/custom13_window.xml
ui/custom/Options/Armor Resists/Style 09/custom13_window.xml
  - first tab: 크러쉬
  - duplicate inner first-tab label ControlId 1106 blanked

ui/custom/custom17_window.xml
ui/custom/Options/Realm Ranks/Style 01/custom17_window.xml
  - first tab: 그래프
  - duplicate inner title label ControlId 1102 blanked

ui/custom/custom11_window.xml
ui/custom/Options/Tabbed XP/Style 01/custom11_window.xml
  - first tab: 경험
  - duplicate inner title label ControlId 1209 blanked

ui/custom/custom9_window.xml
ui/custom/Options/Mini Resists/Style 01/custom9_window.xml
  - mini resist labels widened and value columns shifted for Korean phonetic labels
```

The tab template itself was not the root cause of the first-tab overlap. The root cause was duplicate labels in each affected custom window.

## Verification

After patching, restart the DAoC client completely. UI XML is loaded at startup.

Basic checks:

1. Character select or in-game options select `Custom Skin`.
2. Open the custom UI/BobsUI panel.
3. Open command window tabs.
4. Open menu bar buttons.
5. Open group, social, help, keyboard, NPC interact windows.
6. Click a bracketed NPC destination such as `[Castle Sauvage]`.

A quick XML syntax check can be run from WSL:

```bash
python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path('/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoCClient/ui/custom')
errors = []
count = 0

for path in root.rglob('*.xml'):
    count += 1
    try:
        ET.parse(path)
    except ET.ParseError as exc:
        errors.append((path, exc))

print('xml files checked:', count)
print('xml errors:', len(errors))
for path, exc in errors[:20]:
    print(path, exc)
PY
```

Current local verification result:

```text
xml files checked: 1443
xml errors: 0
```

## Cafe User Instructions Draft

For users, the short version is:

1. Download the custom UI and place it under `Dark Age of Camelot/ui/custom`.
2. Apply the KDAOC Korean custom UI patch files over that folder.
3. Make sure patched XML files are saved as UTF-8.
4. Start the client, choose `Custom Skin`, then fully restart once.
5. If Korean becomes `@`, the custom UI is still using old bitmap/TTF fonts or a poorly matched GDI face. Use Korean-capable GDI fonts such as `Gulim`.

Package the patched `ui/custom` folder later instead of asking normal users to edit XML by hand.
