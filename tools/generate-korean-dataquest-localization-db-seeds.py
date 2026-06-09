#!/usr/bin/env python3
"""Generate/apply Korean DataQuest localization rows.

DataQuest progression still uses the original DB fields for matching whisper
tokens and target names. This tool only adds display strings to
LanguageDataQuest so KR clients can see Korean quest text without changing EN
behavior.
"""

from __future__ import annotations

import argparse
import re
import runpy
import uuid
from dataclasses import dataclass


BASE = runpy.run_path("tools/generate-korean-localization-db-seeds.py")
connect = BASE["connect"]
translate_item_name = BASE["translate_item_name"]

TAG = "korean-localization-auto-dataquest"

QUEST_ITEM_WORDS = {
    "a": "",
    "an": "",
    "the": "",
    "of": "의",
    "ancient": "고대",
    "apple": "사과",
    "arrow": "화살",
    "arrowhead": "화살촉",
    "arrowheads": "화살촉",
    "arrows": "화살",
    "belt": "벨트",
    "berry": "베리",
    "bits": "조각",
    "blood": "피",
    "bloody": "피 묻은",
    "bodyguard": "경호병",
    "bone": "뼈",
    "bones": "뼈",
    "bottle": "병",
    "bow": "활",
    "bracer": "팔찌",
    "bronze": "청동",
    "boar": "멧돼지",
    "claw": "발톱",
    "claws": "발톱",
    "cliff": "절벽",
    "cloak": "망토",
    "cord": "끈",
    "crystallized": "결정화된",
    "crawler": "크롤러",
    "crafted": "제작된",
    "cyclops": "사이클롭스",
    "dark": "어두운",
    "darkfire": "암흑불꽃",
    "danaoin": "다나오인",
    "decayed": "부패한",
    "decorative": "장식용",
    "deep": "깊은",
    "dried": "말린",
    "drakoran": "드라코란",
    "ear": "귀",
    "ears": "귀",
    "egg": "알",
    "ember": "불씨",
    "enchanted": "마법부여된",
    "eye": "눈",
    "eyes": "눈",
    "faerie": "페어리",
    "fang": "송곳니",
    "fangs": "송곳니",
    "feather": "깃털",
    "feathers": "깃털",
    "fire": "불",
    "fishing": "낚시",
    "flesh": "살점",
    "fly": "파리",
    "footman": "보병",
    "footman's": "보병의",
    "frog": "개구리",
    "gem": "보석",
    "ghostly": "유령의",
    "giant": "거대",
    "glowing": "빛나는",
    "goblin": "고블린",
    "gold": "금빛",
    "grain": "곡물",
    "granite": "화강암",
    "great": "대형",
    "guardian": "수호자",
    "hair": "털",
    "hand": "손",
    "hands": "손",
    "harvest": "수확",
    "head": "머리",
    "heads": "머리",
    "heart": "심장",
    "hide": "가죽",
    "huntress": "여사냥꾼",
    "jeweled": "보석 장식",
    "key": "열쇠",
    "kitten": "새끼 고양이",
    "larva": "유충",
    "leech": "거머리",
    "leg": "다리",
    "legs": "다리",
    "list": "목록",
    "lizard": "도마뱀",
    "lost": "잃어버린 자",
    "melted": "녹은",
    "metal": "금속",
    "mirror": "거울",
    "mist": "안개",
    "mottled": "얼룩진",
    "monk": "수도승",
    "mummified": "미라화된",
    "obsidian": "흑요석",
    "oily": "기름진",
    "orb": "구슬",
    "pelt": "가죽",
    "pendant": "펜던트",
    "pendants": "펜던트",
    "piece": "조각",
    "pieces": "조각",
    "poison": "독",
    "polished": "윤이 나는",
    "pristine": "온전한",
    "pictish": "픽트",
    "red": "붉은",
    "ring": "반지",
    "rotted": "부패한",
    "rusted": "녹슨",
    "sack": "자루",
    "sap": "수액",
    "scaled": "비늘 덮인",
    "shell": "껍데기",
    "shredded": "찢어진",
    "shroud": "수의",
    "silver": "은",
    "sinew": "힘줄",
    "skin": "가죽",
    "skull": "해골",
    "skirmisher": "척후병",
    "soul": "영혼",
    "spear": "창",
    "spines": "가시",
    "stone": "돌",
    "stolen": "훔친",
    "strangler": "교살자",
    "studs": "징",
    "tail": "꼬리",
    "tattooed": "문신 새긴",
    "thick": "두꺼운",
    "tibia": "정강이뼈",
    "tips": "끝부분",
    "tip": "끝부분",
    "tooth": "이빨",
    "unused": "사용하지 않은",
    "warm": "따뜻한",
    "warrior": "전사",
    "wristband": "손목띠",
    "water": "물",
    "white": "흰",
    "wine": "포도주",
    "wings": "날개",
    "worn": "낡은",
}


@dataclass
class DataQuestTranslation:
    id: int
    name: str
    description: str
    source_text: str
    step_text: str
    target_text: str
    finish_text: str


def has_final_consonant(text: str) -> bool:
    for ch in reversed(text.strip()):
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            return (code - 0xAC00) % 28 != 0
        if ch.isalnum():
            return True
    return False


def particle(text: str, with_final: str, without_final: str) -> str:
    return with_final if has_final_consonant(text) else without_final


def obj(text: str) -> str:
    return particle(text, "을", "를")


def subj(text: str) -> str:
    return particle(text, "은", "는")


def translate_quest_item_name(english_name: str) -> str:
    of_match = re.match(r"^(.+?)\s+of\s+(?:the\s+)?(.+)$", english_name, re.IGNORECASE)
    if of_match:
        left = translate_quest_item_name(of_match.group(1))
        right = translate_quest_item_name(of_match.group(2))
        if left in {"병", "자루"}:
            return f"{right} {left}"
        return f"{right}의 {left}"

    parts = re.findall(r"[A-Za-z']+|[0-9]+|[^A-Za-z0-9']+", english_name)
    translated: list[str] = []

    for part in parts:
        if not re.search(r"[A-Za-z0-9]", part):
            translated.append(" " if part.strip() else part)
            continue

        word = QUEST_ITEM_WORDS.get(part.lower())
        if word is None:
            translated.append(part)
        elif word:
            translated.append(word)

    text = " ".join("".join(translated).split())
    text = text.replace(" 의 ", "의 ")
    return text or english_name


def looks_like_bad_phonetic(name: str) -> bool:
    return any(fragment in name for fragment in ("으에", "오르", "아느", "트우", "르에", "우이"))


def normalize_item_name(kr_name: str | None, english_name: str | None, fallback: str) -> str:
    if kr_name and not looks_like_bad_phonetic(kr_name):
        return kr_name.strip()

    cleaned = (english_name or fallback).replace("_", " ").strip()
    translated = translate_quest_item_name(cleaned)
    if translated != cleaned:
        return translated

    conservative = translate_item_name(cleaned, broad=False)
    return conservative or cleaned


def load_item_names(cur) -> tuple[dict[str, str], dict[str, str]]:
    english_names: dict[str, str] = {}
    korean_names: dict[str, str] = {}

    cur.execute("SELECT Id_nb, Name FROM itemtemplate")
    for template_id, name in cur.fetchall():
        english_names[template_id] = name

    cur.execute("SELECT TranslationId, Name FROM languageitem WHERE Language='KR' AND Name IS NOT NULL AND Name<>''")
    for translation_id, name in cur.fetchall():
        korean_names[translation_id] = name

    return english_names, korean_names


def collect_rows(cur) -> list[DataQuestTranslation]:
    english_item_names, korean_item_names = load_item_names(cur)
    rows: list[DataQuestTranslation] = []

    cur.execute(
        """
        SELECT ID, Name, CollectItemTemplate
        FROM dataquest
        WHERE StartType = 1
        ORDER BY ID
        """
    )

    for quest_id, quest_name, collect_item_template in cur.fetchall():
        item_name = normalize_item_name(
            korean_item_names.get(collect_item_template),
            english_item_names.get(collect_item_template),
            collect_item_template or quest_name,
        )

        rows.append(
            DataQuestTranslation(
                id=quest_id,
                name=f"{item_name} 반납",
                description=f"{item_name}{obj(item_name)} 찾고 있습니다. 가지고 있다면 반납해 주세요.",
                source_text=f"{item_name}{obj(item_name)} 가져와 주셔서 감사합니다!",
                step_text="아직 이 일을 맡기에는 조금 약합니다. 더 강해진 뒤 다시 오세요.",
                target_text=f"오, {item_name}{subj(item_name)}군요. 더 가지고 있습니까?",
                finish_text=f"이제 {item_name}{subj(item_name)} 더 필요하지 않습니다.",
            )
        )

    return rows


def ensure_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS languagedataquest (
          Name text NULL,
          Description text NULL,
          SourceText text NULL,
          StepText text NULL,
          TargetText text NULL,
          FinishText text NULL,
          TranslationId varchar(255) NOT NULL,
          Language varchar(255) NOT NULL,
          Tag text NULL,
          LastTimeRowUpdated datetime NOT NULL DEFAULT '2000-01-01 00:00:00',
          LanguageDataQuest_ID varchar(255) NOT NULL,
          PRIMARY KEY (LanguageDataQuest_ID),
          KEY TranslationId (TranslationId),
          KEY Language (Language)
        )
        """
    )


def apply_rows(cur, rows: list[DataQuestTranslation]) -> None:
    ensure_table(cur)
    cur.execute("DELETE FROM languagedataquest WHERE Language='KR' AND Tag=%s", (TAG,))
    cur.executemany(
        """
        INSERT INTO languagedataquest
          (LanguageDataQuest_ID, TranslationId, Language, Name, Description, SourceText, StepText, TargetText, FinishText, Tag, LastTimeRowUpdated)
        VALUES
          (%s, %s, 'KR', %s, %s, %s, %s, %s, %s, %s, NOW())
        """,
        [
            (
                str(uuid.uuid4()),
                str(row.id),
                row.name,
                row.description,
                row.source_text,
                row.step_text,
                row.target_text,
                row.finish_text,
                TAG,
            )
            for row in rows
        ],
    )


def print_samples(rows: list[DataQuestTranslation], count: int) -> None:
    print(f"DataQuest KR auto seed: {len(rows)} generated")
    for row in rows[:count]:
        print(f"  {row.id}\t{row.name}\t{row.description}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply generated rows to the local DB.")
    parser.add_argument("--samples", type=int, default=12)
    args = parser.parse_args()

    conn = connect()
    try:
        with conn.cursor() as cur:
            rows = collect_rows(cur)
            print_samples(rows, args.samples)

            if args.apply:
                apply_rows(cur, rows)
                conn.commit()
                print("Applied generated KR DataQuest localization rows.")
            else:
                print("Dry run only. Pass --apply to write generated rows.")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
