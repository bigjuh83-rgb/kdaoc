#!/usr/bin/env python3
"""Check OpenDAoC server localization coverage and common Korean QA issues."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


KEY_LINE_RE = re.compile(r"^\s*([^:#][^:]*?)\s*:\s*(.*)$")
KEY_LIKE_RE = re.compile(r"^(?:[A-Za-z0-9]+\.)+[A-Za-z0-9_.:-]+$")
ENGLISH_WORD_RE = re.compile(r"[A-Za-z]{3,}")
KOREAN_RE = re.compile(r"[\uac00-\ud7a3]")

TARGET_OUTPUT_METHODS = {
    "SendMessage",
    "BroadcastMessage",
    "SayTo",
    "SendDialogBox",
    "SendCustomTextWindow",
    "SendReply",
    "DisplayMessage",
    "MessageToLiving",
    "SystemToOthers",
}

FORBIDDEN_KR_TERMS = {
    "체질": "체력",
    "스텟": "스탯",
    "릴름": "렐름",
    "릴릭": "렐릭",
}


@dataclass(frozen=True)
class Occurrence:
    path: Path
    line: int
    text: str = ""

    def format(self, root: Path) -> str:
        rel = self.path.relative_to(root).as_posix()
        suffix = f": {self.text}" if self.text else ""
        return f"{rel}:{self.line}{suffix}"


@dataclass
class TranslationData:
    values: dict[str, str]
    occurrences: dict[str, list[Occurrence]]


@dataclass
class IgnoreRule:
    path: str = ""
    contains: str = ""
    regex: str = ""
    reason: str = ""

    def matches(self, root: Path, occurrence: Occurrence) -> bool:
        rel = occurrence.path.relative_to(root).as_posix()
        if self.path and self.path not in rel:
            return False
        if self.contains and self.contains not in occurrence.text:
            return False
        if self.regex and not re.search(self.regex, occurrence.text):
            return False
        return True


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Validate localization files and server text output.")
    parser.add_argument("--root", type=Path, default=default_root, help="Repository root.")
    parser.add_argument("--langs", nargs=2, default=["EN", "KR"], metavar=("BASE", "TARGET"))
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary.")
    parser.add_argument("--build", action="store_true", help="Run dotnet build after localization checks pass.")
    parser.add_argument("--strict-warnings", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--strict-hardcoded", action="store_true", help="Treat hardcoded English candidates as failures.")
    parser.add_argument("--max-kr-chars", type=int, default=120, help="Warn on KR values longer than this.")
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def load_ignores(root: Path) -> dict[str, list[IgnoreRule]]:
    path = root / "tools" / "localization-ignore.json"
    if not path.exists():
        return {"hardcoded_allow": [], "dynamic_translation_allow": []}

    raw = json.loads(read_text(path))
    result: dict[str, list[IgnoreRule]] = {}
    for group, rules in raw.items():
        result[group] = [IgnoreRule(**rule) for rule in rules]
    return result


def is_ignored(root: Path, occurrence: Occurrence, rules: Iterable[IgnoreRule]) -> bool:
    return any(rule.matches(root, occurrence) for rule in rules)


def load_language(root: Path, lang: str) -> TranslationData:
    lang_dir = root / "GameServer" / "language" / lang
    values: dict[str, str] = {}
    occurrences: dict[str, list[Occurrence]] = {}

    for path in sorted(lang_dir.rglob("*.txt")):
        for idx, line in enumerate(read_text(path).splitlines(), start=1):
            match = KEY_LINE_RE.match(line)
            if not match:
                continue
            key = match.group(1).strip()
            value = match.group(2).strip()
            if not key:
                continue
            occurrences.setdefault(key, []).append(Occurrence(path, idx, value))
            values.setdefault(key, value)

    return TranslationData(values=values, occurrences=occurrences)


def csharp_files(root: Path) -> list[Path]:
    return sorted((root / "GameServer").rglob("*.cs"))


def strip_csharp_comments(text: str) -> str:
    out: list[str] = []
    i = 0
    state = "normal"

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if state == "normal":
            if ch == "/" and nxt == "/":
                out.extend("  ")
                i += 2
                state = "line_comment"
                continue
            if ch == "/" and nxt == "*":
                out.extend("  ")
                i += 2
                state = "block_comment"
                continue
            if ch == "@" and nxt == '"':
                out.append(ch)
                out.append(nxt)
                i += 2
                state = "verbatim_string"
                continue
            if ch == "$" and nxt == "@":
                third = text[i + 2] if i + 2 < len(text) else ""
                if third == '"':
                    out.extend([ch, nxt, third])
                    i += 3
                    state = "verbatim_string"
                    continue
            if ch == "@" and nxt == "$":
                third = text[i + 2] if i + 2 < len(text) else ""
                if third == '"':
                    out.extend([ch, nxt, third])
                    i += 3
                    state = "verbatim_string"
                    continue
            if ch == '"':
                out.append(ch)
                i += 1
                state = "string"
                continue
            if ch == "'":
                out.append(ch)
                i += 1
                state = "char"
                continue
            out.append(ch)
            i += 1
            continue

        if state == "line_comment":
            if ch == "\n":
                out.append(ch)
                state = "normal"
            else:
                out.append(" ")
            i += 1
            continue

        if state == "block_comment":
            if ch == "*" and nxt == "/":
                out.extend("  ")
                i += 2
                state = "normal"
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue

        if state == "string":
            out.append(ch)
            if ch == "\\" and nxt:
                out.append(nxt)
                i += 2
                continue
            if ch == '"':
                state = "normal"
            i += 1
            continue

        if state == "verbatim_string":
            out.append(ch)
            if ch == '"' and nxt == '"':
                out.append(nxt)
                i += 2
                continue
            if ch == '"':
                state = "normal"
            i += 1
            continue

        if state == "char":
            out.append(ch)
            if ch == "\\" and nxt:
                out.append(nxt)
                i += 2
                continue
            if ch == "'":
                state = "normal"
            i += 1
            continue

    return "".join(out)


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def find_matching_paren(text: str, open_index: int) -> int:
    depth = 0
    i = open_index
    state = "normal"
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if state == "normal":
            if ch == "@" and nxt == '"':
                i += 2
                state = "verbatim_string"
                continue
            if ch == '"':
                i += 1
                state = "string"
                continue
            if ch == "'":
                i += 1
                state = "char"
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
            continue

        if state == "string":
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                state = "normal"
            i += 1
            continue

        if state == "verbatim_string":
            if ch == '"' and nxt == '"':
                i += 2
                continue
            if ch == '"':
                state = "normal"
            i += 1
            continue

        if state == "char":
            if ch == "\\":
                i += 2
                continue
            if ch == "'":
                state = "normal"
            i += 1
            continue

    return -1


def split_top_level_args(text: str) -> list[str]:
    args: list[str] = []
    start = 0
    depth = 0
    i = 0
    state = "normal"
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if state == "normal":
            if ch == "@" and nxt == '"':
                i += 2
                state = "verbatim_string"
                continue
            if ch == '"':
                i += 1
                state = "string"
                continue
            if ch == "'":
                i += 1
                state = "char"
                continue
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(0, depth - 1)
            elif ch == "," and depth == 0:
                args.append(text[start:i].strip())
                start = i + 1
            i += 1
            continue

        if state == "string":
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                state = "normal"
            i += 1
            continue

        if state == "verbatim_string":
            if ch == '"' and nxt == '"':
                i += 2
                continue
            if ch == '"':
                state = "normal"
            i += 1
            continue

        if state == "char":
            if ch == "\\":
                i += 2
                continue
            if ch == "'":
                state = "normal"
            i += 1
            continue

    tail = text[start:].strip()
    if tail:
        args.append(tail)
    return args


def regular_string_literal(arg: str) -> str | None:
    arg = arg.strip()
    match = re.fullmatch(r'(?:"((?:\\.|[^"\\])*)")', arg, re.DOTALL)
    if not match:
        return None
    value = match.group(1)
    return bytes(value, "utf-8").decode("unicode_escape", errors="replace")


def all_regular_string_literals(text: str) -> list[str]:
    values: list[str] = []
    for match in re.finditer(r'"((?:\\.|[^"\\])*)"', text, re.DOTALL):
        raw = match.group(1)
        values.append(bytes(raw, "utf-8").decode("unicode_escape", errors="replace"))
    return values


def iter_calls(text: str, method: str) -> Iterable[tuple[int, str]]:
    pattern = re.compile(rf"\b{re.escape(method)}\s*\(")
    for match in pattern.finditer(text):
        open_index = text.find("(", match.start())
        close_index = find_matching_paren(text, open_index)
        if close_index == -1:
            continue
        yield match.start(), text[open_index + 1 : close_index]


def extract_translation_keys(root: Path) -> tuple[dict[str, list[Occurrence]], list[Occurrence]]:
    keys: dict[str, list[Occurrence]] = {}
    dynamic: list[Occurrence] = []

    for path in csharp_files(root):
        text = strip_csharp_comments(read_text(path))
        for start, args_text in iter_calls(text, "LanguageMgr.GetTranslation"):
            args = split_top_level_args(args_text)
            key = regular_string_literal(args[1]) if len(args) >= 2 else None
            if key and KEY_LIKE_RE.match(key):
                keys.setdefault(key, []).append(Occurrence(path, line_number(text, start)))
            else:
                snippet = " ".join(args_text.split())[:140]
                dynamic.append(Occurrence(path, line_number(text, start), snippet))

    return keys, dynamic


def is_hardcoded_candidate(value: str) -> bool:
    if not value or KEY_LIKE_RE.match(value):
        return False
    if KOREAN_RE.search(value):
        return False
    if value.startswith("/") or value.startswith("#"):
        return False
    if len(value) <= 3 and value.isupper():
        return False
    if re.fullmatch(r"[\w:./{}%<>\-+ ]+", value) and not ENGLISH_WORD_RE.search(value):
        return False
    return bool(ENGLISH_WORD_RE.search(value))


def extract_hardcoded_candidates(root: Path, ignores: list[IgnoreRule]) -> list[Occurrence]:
    candidates: list[Occurrence] = []
    for path in csharp_files(root):
        text = strip_csharp_comments(read_text(path))
        for method in TARGET_OUTPUT_METHODS:
            for start, args_text in iter_calls(text, method):
                if "LanguageMgr.GetTranslation" in args_text:
                    continue
                for value in all_regular_string_literals(args_text):
                    if not is_hardcoded_candidate(value):
                        continue
                    occurrence = Occurrence(path, line_number(text, start), value)
                    if not is_ignored(root, occurrence, ignores):
                        candidates.append(occurrence)
    return candidates


def find_duplicates(data: TranslationData) -> dict[str, list[Occurrence]]:
    return {key: occ for key, occ in data.occurrences.items() if len(occ) > 1}


def find_terminology_issues(root: Path, data: TranslationData) -> list[Occurrence]:
    issues: list[Occurrence] = []
    for occurrences in data.occurrences.values():
        for occurrence in occurrences:
            for bad, good in FORBIDDEN_KR_TERMS.items():
                if bad in occurrence.text:
                    issues.append(Occurrence(occurrence.path, occurrence.line, f"{bad} -> {good}: {occurrence.text}"))
    return issues


def find_long_kr_values(data: TranslationData, max_chars: int) -> list[Occurrence]:
    long_values: list[Occurrence] = []
    for occurrences in data.occurrences.values():
        for occurrence in occurrences:
            if KOREAN_RE.search(occurrence.text) and len(occurrence.text) > max_chars:
                long_values.append(occurrence)
    return long_values


def print_section(title: str, rows: list[str], limit: int = 40) -> None:
    print(f"\n{title}: {len(rows)}")
    for row in rows[:limit]:
        print(f"  - {row}")
    if len(rows) > limit:
        print(f"  ... {len(rows) - limit} more")


def run_build(root: Path) -> int:
    dotnet = os.environ.get("DOTNET", "/home/bigjuh/.dotnet/dotnet")
    if not Path(dotnet).exists():
        dotnet = "dotnet"
    print("\nBuild:")
    print(f"  running {dotnet} build GameServer/GameServer.csproj --no-restore")
    completed = subprocess.run(
        [dotnet, "build", "GameServer/GameServer.csproj", "--no-restore"],
        cwd=root,
        text=True,
    )
    return completed.returncode


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    base_lang, target_lang = args.langs
    ignores = load_ignores(root)

    languages = {lang: load_language(root, lang) for lang in args.langs}
    used_keys, dynamic_calls = extract_translation_keys(root)
    hardcoded = extract_hardcoded_candidates(root, ignores.get("hardcoded_allow", []))

    base = languages[base_lang]
    target = languages[target_lang]
    used = set(used_keys)
    missing_base = sorted(used - set(base.values))
    missing_target = sorted(used - set(target.values))
    base_only = sorted(set(base.values) - set(target.values))
    target_only = sorted(set(target.values) - set(base.values))
    duplicates = {lang: find_duplicates(data) for lang, data in languages.items()}
    terminology = find_terminology_issues(root, target)
    long_kr = find_long_kr_values(target, args.max_kr_chars)

    if args.json:
        payload = {
            "used_translation_keys": len(used),
            "missing_base": missing_base,
            "missing_target": missing_target,
            "base_only": base_only,
            "target_only": target_only,
            "duplicates": {lang: {key: [o.format(root) for o in occ] for key, occ in dup.items()} for lang, dup in duplicates.items()},
            "dynamic_translation_calls": [o.format(root) for o in dynamic_calls],
            "hardcoded_candidates": [o.format(root) for o in hardcoded],
            "terminology": [o.format(root) for o in terminology],
            "long_kr": [o.format(root) for o in long_kr],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Localization check summary")
        print(f"  repo: {root}")
        print(f"  languages: {base_lang}, {target_lang}")
        print(f"  literal translation keys used by code: {len(used)}")
        print(f"  {base_lang} keys: {len(base.values)}")
        print(f"  {target_lang} keys: {len(target.values)}")

        print_section(
            f"ERROR keys used by code but missing in {base_lang}",
            [f"{key} ({used_keys[key][0].format(root)})" for key in missing_base],
        )
        print_section(
            f"ERROR keys used by code but missing in {target_lang}",
            [f"{key} ({used_keys[key][0].format(root)})" for key in missing_target],
        )
        print_section(f"WARN keys only in {base_lang}", base_only)
        print_section(f"WARN keys only in {target_lang}", target_only)
        for lang, duplicate_map in duplicates.items():
            rows = [f"{key}: {', '.join(o.format(root) for o in occurrences[:4])}" for key, occurrences in sorted(duplicate_map.items())]
            print_section(f"WARN duplicate keys in {lang}", rows)
        print_section("INFO dynamic translation calls", [o.format(root) for o in dynamic_calls])
        hardcoded_label = "ERROR" if args.strict_hardcoded else "WARN"
        print_section(f"{hardcoded_label} hardcoded English output candidates", [o.format(root) for o in hardcoded], limit=80)
        print_section("ERROR forbidden Korean terminology", [o.format(root) for o in terminology], limit=80)
        print_section("WARN long KR strings", [o.format(root) for o in long_kr], limit=60)

    error_count = len(missing_base) + len(missing_target) + len(terminology)
    if args.strict_hardcoded:
        error_count += len(hardcoded)
    warning_count = len(base_only) + len(target_only) + sum(len(v) for v in duplicates.values()) + len(dynamic_calls) + len(long_kr)
    if not args.strict_hardcoded:
        warning_count += len(hardcoded)
    if args.strict_warnings:
        error_count += warning_count

    if error_count:
        if not args.json:
            print(f"\nResult: FAILED ({error_count} errors, {warning_count} warnings)")
        return 1

    if not args.json:
        print(f"\nResult: OK ({warning_count} warnings)")
    if args.build:
        return run_build(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
