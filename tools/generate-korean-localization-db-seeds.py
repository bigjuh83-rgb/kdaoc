#!/usr/bin/env python3
"""Generate/apply conservative Korean DB localization seeds.

This tool intentionally keeps existing curated KR translations intact and only
adds rows tagged as generated seeds. It reads the local serverconfig.xml for the
DB connection string but never prints credentials.
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import pymysql


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "CoreServer" / "config" / "serverconfig.xml"
NPC_TAG = "korean-localization-auto-mob-names"
ITEM_TAG = "korean-localization-auto-item-names"
EQUIPMENT_ITEM_SLOTS = (10, 11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27, 28, 29, 32, 33, 34, 35, 36, 37)

REALM_NAMES = {
    "albion": "알비온",
    "hibernia": "하이버니아",
    "hibernian": "하이버니아",
    "midgard": "미드가르드",
}

HOUSE_TYPE_NAMES = {
    "cottage": "코티지",
    "house": "주택",
    "villa": "빌라",
    "mansion": "맨션",
}

CRAFT_NAMES = {
    "alchemy": "연금술",
    "armorcrafter": "아머크래프터",
    "armorcrafting": "아머크래프트",
    "clothworking": "천 작업",
    "fletching": "활 제작",
    "incantation": "주문",
    "leatherworking": "가죽 작업",
    "metalworking": "금속 작업",
    "siegecraft": "공성 제작",
    "siegecrafter": "공성 제작자",
    "spellcraft": "스펠크래프트",
    "spellcrafter": "스펠크래프터",
    "spellcrafting": "스펠크래프트",
    "tailoring": "재봉",
    "weaponcrafting": "무기 제작",
    "woodworking": "목공",
}

PLACE_NAMES = {
    "Adribard's Retreat": "아드리바드 은거지",
    "Aegirhamn": "에기르함",
    "Aberillan": "아베릴란",
    "Aalid Feie": "알리드 페이",
    "Alainn Bin": "알라인 빈",
    "Albion Darkness Fall Entrance": "알비온 다크니스 폴스 입구",
    "Anniogel": "아니오겔",
    "Ardagh": "아르다",
    "Ardee": "아르디",
    "Arothi": "아로시",
    "Audliten": "아우들리텐",
    "Avalon City Entrance": "아발론 시티 입구",
    "Avalon Portal": "아발론 포털",
    "Aylesbury": "에일즈버리",
    "Bann Didein": "반 디딘",
    "Barfog Outpost": "바포그 전초기지",
    "Basar": "바사르",
    "Bjarken": "비야르켄",
    "Brisworthy": "브리스워디",
    "Broughshane": "브러프셰인",
    "Brynach": "브리나크",
    "Caennai": "카에나이",
    "Caer Diogel": "케어 디오겔",
    "Caer Gothwaite": "케어 고스웨이트",
    "Caer Sidi Entrance": "케어 시디 입구",
    "Caer Ulfwich": "케어 울프위치",
    "Caer Ulfwych": "케어 울프위치",
    "Caerwent": "케어웬트",
    "Caer Witrin": "케어 위트린",
    "Caifelle": "카이펠레",
    "Caille": "카일레",
    "Camelot East Entrance": "카멜롯 동쪽 입구",
    "Camelot East Exit": "카멜롯 동쪽 출구",
    "Camelot North Entrance": "카멜롯 북쪽 입구",
    "Camelot North Exit": "카멜롯 북쪽 출구",
    "Camelot Estuary": "카멜롯 하구",
    "Camelot Round Table": "카멜롯 원탁",
    "Campacorentin Station": "캄파코렌틴 기지",
    "Castle Sauvage": "소바쥬 성",
    "Catacomb of Cordova Entrance": "카르도바 지하묘지 입구",
    "Catacombs of Cordova": "카르도바 지하묘지",
    "Carlingford": "칼링퍼드",
    "Chiltern": "칠턴",
    "Clifton": "클리프턴",
    "Cliffton": "클리프턴",
    "Connla": "콘라",
    "Connla's Well": "콘라의 우물",
    "Cornwall Station": "콘월 기지",
    "Coruscanting Mines Entrance": "코러스케이팅 광산 입구",
    "Cotswold Village": "코츠월드 마을",
    "Cotswold": "코츠월드",
    "Culraid": "컬레이드",
    "Cursed Tomb Entrance": "저주받은 무덤 입구",
    "Daingean": "댕건",
    "Dalton": "달턴",
    "Dellingstad": "델링스타드",
    "Domnann": "돔난",
    "Droighaid": "드로하이드",
    "Druim Cain": "드루임 케인",
    "Druim Ligen": "드루임 리겐",
    "Dunshire": "던셔",
    "Dyrfjell": "디르피엘",
    "Erikstaad": "에릭스타드",
    "Faraheim": "파라헤임",
    "Fomor Entrance": "포모르 입구",
    "Fort Atla": "아틀라 요새",
    "Fort Gwyntell": "귄텔 요새",
    "Fort Veldon": "벨돈 요새",
    "Galladoria Entrance": "갈라도리아 입구",
    "Galplen": "갈플렌",
    "Gna Faste": "그나 파스테",
    "Gothwaite Harbor": "고스웨이트 항구",
    "Grony's Farm": "그로니의 농장",
    "Groove of Aalid Feie": "알리드 페이 숲",
    "Grove of Domnann": "돔난 숲",
    "Haggerfel": "하거펠",
    "Hagall": "하갈",
    "Hibernia Darkness Falls Entrance": "하이버니아 다크니스 폴스 입구",
    "Hibernian Atlantis Ship Route": "하이버니아 아틀란티스 항로",
    "Holtham": "홀담",
    "Howth": "호스",
    "Huginfel": "후긴펠",
    "Humberton Castle": "험버턴 성",
    "Humberton Village": "험버턴 마을",
    "Iarn Dwarf Encampment": "이아른 드워프 야영지",
    "Iarnvidiur's Lair Entrance": "이아른비디우르의 소굴 입구",
    "Iarnvidiur's Lair": "이아른비디우르의 소굴",
    "Innis Carthaig": "이니스 카르사이그",
    "Keltoi Fogou Entrance": "켈토이 포구 입구",
    "Knarr": "크나르",
    "Koalinth Caverns Entrance": "코알린스 동굴 입구",
    "Krondon Entrance": "크론돈 입구",
    "Krrzck": "크르직",
    "Lammia Camp": "라미아 캠프",
    "Lethantis Association": "레탄티스 협회",
    "Ludlow": "러들로",
    "Mag Mell": "마그 멜",
    "Mardagh": "마르다그",
    "Midgard Darkness Falls Entrance": "미드가르드 다크니스 폴스 입구",
    "Midgard Grifon Stable": "미드가르드 그리폰 마구간",
    "Mithra's Tomb Entrance": "미트라 무덤 입구",
    "Muire Tomb Entrance": "뮤어 무덤 입구",
    "Mularn": "물란",
    "Nalliten": "나일리텐",
    "Necht": "네흐트",
    "Nisse's Lair Entrance": "니스의 소굴 입구",
    "Nob's Stable": "놉의 마구간",
    "Outland Wharf": "아웃랜드 부두",
    "Parthenon Farm": "파르테논 농장",
    "Prydwen Bridge": "프리드웬 다리",
    "Prywden Bridge": "프리드웬 다리",
    "Prywden Keep": "프리드웬 성채",
    "Raumaric": "라우마리크",
    "Siopa": "시오파",
    "Snowdonia Fortress": "스노도니아 요새",
    "Snowdonia Station": "스노도니아 기지",
    "Spindelhalla Entrance": "스핀델할라 입구",
    "Spraggon Den Entrance": "스프래곤 소굴 입구",
    "Stonehenge Barrows Entrance": "스톤헨지 고분 입구",
    "Svasud Faste": "스바수드 파스테",
    "Swanton Keep": "스완턴 성채",
    "Tepok's Mine Entrance": "테폭 광산 입구",
    "Tir Garda": "티르 가르다",
    "Tir Na mbeo": "티르 나 므베오",
    "Tir na mBeo": "티르 나 므베오",
    "Tir Na Nog East Entrance": "티르 나 노그 동쪽 입구",
    "Tir Na Nog East Exit": "티르 나 노그 동쪽 출구",
    "Tir Na Nog North Entrance": "티르 나 노그 북쪽 입구",
    "Tir Na Nog North Exit": "티르 나 노그 북쪽 출구",
    "Tir Na Nog Throne": "티르 나 노그 왕좌",
    "Tir Urphost": "티르 어포스트",
    "Treibh Caillte Entrance": "트레이브 카일테 입구",
    "Trollheim": "트롤하임",
    "Trollheim Lair Entrance": "트롤하임 소굴 입구",
    "Tur Suil Entrance": "투르 수일 입구",
    "Tuscaren Glacier": "투스카렌 빙하",
    "Varulvhamn Entrance": "바룰브함 입구",
    "Vasudheim": "바수드헤임",
    "Vendo Cavern's Entrance": "벤도 동굴 입구",
    "Vetusta Abbey": "베투스타 수도원",
    "Vindsaul Faste": "빈드사울 파스테",
    "Wearyall Village": "위어리얼 마을",
    "West Downs": "웨스트 다운스",
    "West Skona": "웨스트 스코나",
    "Yarley's Farm": "야를리 농장",
}

PLACE_NAME_ALIASES = {
    "AdribardsRetreat": "Adribard's Retreat",
    "Adribards Retreat": "Adribard's Retreat",
    "Aegirhamm": "Aegirhamn",
    "AlainnBin": "Alainn Bin",
    "AvalonCity": "Avalon City Entrance",
    "BannDidein": "Bann Didein",
    "CaerDiogel": "Caer Diogel",
    "CaerGothwaite": "Caer Gothwaite",
    "CaerSidi": "Caer Sidi Entrance",
    "CaerUlfwych": "Caer Ulfwych",
    "CaerWitrin": "Caer Witrin",
    "CamelotEst": "Camelot East Entrance",
    "CamelotNoth": "Camelot North Entrance",
    "CampacorentinStation": "Campacorentin Station",
    "CastleSauvage": "Castle Sauvage",
    "CatacombsofCorvoda": "Catacombs of Cordova",
    "catacombsofcordoveentrance": "Catacombs of Cordova",
    "Catacombs of Corvoda": "Catacombs of Cordova",
    "Tuscaren Glacier Entrance": "Tuscaren Glacier",
    "Cliffton": "Clifton",
    "CornwallStation": "Cornwall Station",
    "DruimCain": "Druim Cain",
    "DruimLigen": "Druim Ligen",
    "GothwaiteHarbor": "Gothwaite Harbor",
    "GroveofDomnann": "Grove of Domnann",
    "HibSI AtlantisShipRoute": "Hibernian Atlantis Ship Route",
    "IarnDwarfEncampment": "Iarn Dwarf Encampment",
    "IarnvidiursLair": "Iarnvidiur's Lair",
    "KeltoyFogou": "Keltoi Fogou Entrance",
    "Krondon": "Krondon Entrance",
    "LlynBarfog": "Barfog Outpost",
    "MidGrifonStable": "Midgard Grifon Stable",
    "MithrasTomb": "Mithra's Tomb Entrance",
    "NobsFarm": "Nob's Stable",
    "SnowdoniaFortress": "Snowdonia Fortress",
    "SnowdoniaStation": "Snowdonia Station",
    "StonehengeBarrows": "Stonehenge Barrows Entrance",
    "TepoksMine": "Tepok's Mine Entrance",
    "TirNaNogEast": "Tir Na Nog East Entrance",
    "TirNaNogNord": "Tir Na Nog North Entrance",
    "Trollheim": "Trollheim",
    "TuscarenGlacier": "Tuscaren Glacier",
    "TurSuil": "Tur Suil Entrance",
    "Wearyall": "Wearyall Village",
    "WesternCornwall": "Cornwall Station",
}


ITEM_WORDS = {
    "a": "",
    "adroit": "능숙한",
    "aged": "오래된",
    "alloy": "합금",
    "amber": "호박",
    "ancient": "고대",
    "arcanium": "아케이니움",
    "ash": "물푸레나무",
    "ashen": "잿빛",
    "axe": "액스",
    "banded": "밴디드",
    "barely": "살짝",
    "bark": "나무껍질",
    "battle": "배틀",
    "beaded": "구슬장식",
    "belt": "벨트",
    "big": "대형",
    "black": "검은",
    "blade": "블레이드",
    "bladed": "날 달린",
    "boots": "부츠",
    "bow": "보우",
    "bracelet": "팔찌",
    "bracer": "브레이서",
    "breastplate": "흉갑",
    "brilliant": "찬란한",
    "broad": "브로드",
    "brocade": "브로케이드",
    "bronze": "청동",
    "buckler": "버클러",
    "cap": "모자",
    "chain": "체인",
    "chest": "가슴",
    "cloth": "천",
    "club": "클럽",
    "claw": "클로",
    "coif": "코이프",
    "copper": "구리",
    "condensation": "응결",
    "coral": "산호",
    "cracked": "금이 간",
    "crude": "조잡한",
    "crystal": "수정",
    "dagger": "단검",
    "dark": "어두운",
    "deep": "깊은",
    "diamond": "다이아몬드",
    "dirk": "더크",
    "dolomite": "돌로마이트",
    "dress": "드레스",
    "dull": "무딘",
    "dwarven": "드워븐",
    "ebony": "흑단",
    "elm": "느릅나무",
    "emerald": "에메랄드",
    "etched": "문양 새긴",
    "exceptional": "우수한",
    "fancy": "화려한",
    "fang": "송곳니",
    "ferrite": "페라이트",
    "fine": "고급",
    "fire": "불",
    "fired": "구운",
    "flail": "플레일",
    "fortified": "강화된",
    "frosted": "서리 낀",
    "full": "풀",
    "gem": "보석",
    "gilded": "금도금",
    "gloves": "장갑",
    "gold": "금",
    "golden": "황금",
    "gossamer": "고사머",
    "great": "그레이트",
    "greave": "그리브",
    "green": "초록",
    "hammer": "해머",
    "hand": "핸드",
    "hard": "단단한",
    "hardened": "단련한",
    "hauberk": "하우버크",
    "heavy": "헤비",
    "helm": "투구",
    "helmet": "투구",
    "hide": "가죽",
    "hinge": "경첩",
    "hood": "후드",
    "ice": "얼음",
    "iron": "철",
    "ironwood": "아이언우드",
    "javelin": "자벨린",
    "jerkin": "저킨",
    "jewel": "주얼",
    "key": "열쇠",
    "kite": "카이트",
    "large": "대형",
    "leather": "가죽",
    "leggings": "레깅스",
    "linen": "리넨",
    "long": "롱",
    "longbow": "롱보우",
    "longsword": "롱 소드",
    "mace": "메이스",
    "magical": "마법",
    "mail": "메일",
    "medium": "중형",
    "moon": "문",
    "oak": "참나무",
    "oaken": "참나무",
    "old": "오래된",
    "orb": "오브",
    "padded": "패딩",
    "pants": "바지",
    "plain": "평범한",
    "plate": "플레이트",
    "quartz": "석영",
    "rawhide": "생가죽",
    "recurve": "리커브",
    "red": "붉은",
    "reinforced": "강화",
    "robe": "로브",
    "round": "원형",
    "rowan": "로완",
    "ruby": "루비",
    "rusty": "녹슨",
    "sacrificial": "희생",
    "sapphire": "사파이어",
    "scale": "스케일",
    "scimitar": "시미터",
    "shield": "방패",
    "shirt": "셔츠",
    "short": "쇼트",
    "shod": "보강",
    "silk": "실크",
    "silver": "은",
    "silvered": "은빛",
    "sleeves": "소매",
    "small": "소형",
    "spear": "스피어",
    "spiked": "스파이크",
    "staff": "스태프",
    "steel": "강철",
    "stiletto": "스틸레토",
    "stone": "스톤",
    "studded": "스터디드",
    "sword": "소드",
    "tanned": "무두질한",
    "tattered": "해진",
    "thorn": "가시",
    "torn": "찢어진",
    "tower": "타워",
    "training": "수련",
    "trapper": "사냥꾼",
    "two": "투",
    "two-hand": "투핸드",
    "two-handed": "투핸드",
    "vest": "조끼",
    "war": "워",
    "worn": "낡은",
    "wrap": "랩",
}

NPC_WORDS = {
    "acolyte": "수행원",
    "adder": "독사",
    "aged": "늙은",
    "air": "공기",
    "ancient": "고대",
    "anger": "분노",
    "ant": "개미",
    "apprentice": "견습",
    "archer": "아처",
    "army": "군대",
    "badger": "오소리",
    "bandit": "도적",
    "bat": "박쥐",
    "bear": "곰",
    "beetle": "딱정벌레",
    "black": "검은",
    "blackthorn": "블랙쏜",
    "bog": "늪",
    "bogman": "보그맨",
    "bone": "뼈",
    "boy": "소년",
    "brown": "갈색",
    "brownie": "브라우니",
    "calf": "새끼",
    "cat": "캣",
    "cave": "동굴",
    "celtic": "켈틱",
    "collector": "수집꾼",
    "corpse": "시체",
    "crawler": "크롤러",
    "crab": "게",
    "crag": "바위",
    "creeping": "기어다니는",
    "crone": "노파",
    "cub": "새끼",
    "dark": "어두운",
    "death": "죽음",
    "decayed": "부패한",
    "deep": "깊은",
    "dergan": "더건",
    "dew": "이슬",
    "dirge": "더지",
    "dragonfly": "잠자리",
    "drakeling": "드레이크 새끼",
    "earth": "대지",
    "ebony": "흑단",
    "elder": "장로",
    "emerald": "에메랄드",
    "enchanter": "인챈터",
    "envy": "질투",
    "ettin": "에틴",
    "fading": "희미해지는",
    "fellwood": "펠우드",
    "filidh": "필리드",
    "fire": "불",
    "flicker": "플리커",
    "forest": "숲",
    "frog": "개구리",
    "ghastly": "섬뜩한",
    "ghost": "유령",
    "ghoul": "구울",
    "giant": "거대",
    "gray": "회색",
    "green": "녹색",
    "grendelorm": "그렌델오름",
    "grip": "손아귀",
    "guard": "경비병",
    "guardian": "수호자",
    "haunt": "유령",
    "henchman": "부하",
    "hill": "언덕",
    "hobgoblin": "홉고블린",
    "hooligan": "훌리건",
    "host": "숙주",
    "hunter": "사냥꾼",
    "imp": "임프",
    "insect": "벌레",
    "knight": "기사",
    "lake": "호수",
    "large": "큰",
    "leaper": "리퍼",
    "luricaduane": "루리카두안",
    "mauler": "마울러",
    "minion": "부하",
    "mist": "안개",
    "mother": "어미",
    "mudman": "머드맨",
    "muryan": "뮤리안",
    "nipper": "니퍼",
    "nordic": "노르딕",
    "nomad": "유목민",
    "oaken": "참나무",
    "orc": "오크",
    "page": "페이지",
    "parthanan": "파르타난",
    "person": "사람",
    "phantom": "팬텀",
    "pixie": "픽시",
    "primrose": "프림로즈",
    "putrid": "썩은",
    "rabid": "광견",
    "rat": "쥐",
    "red": "붉은",
    "river": "강",
    "rock": "바위",
    "rot": "부패",
    "sand": "모래",
    "scimitar": "시미터",
    "serpent": "뱀",
    "shadow": "그림자",
    "shambler": "샴블러",
    "sheerie": "쉬리",
    "shriller": "슈릴러",
    "skeleton": "해골",
    "skogsfru": "스코그스프루",
    "slough": "늪지",
    "small": "작은",
    "snake": "뱀",
    "spider": "거미",
    "spirit": "영혼",
    "sprite": "스프라이트",
    "sprout": "새싹",
    "stalker": "추적자",
    "stone": "돌",
    "strider": "소금쟁이",
    "sveawolf": "스베아울프",
    "sylvan": "실반",
    "thug": "폭력배",
    "toad": "두꺼비",
    "tomb": "무덤",
    "tomte": "톰테",
    "tree": "나무",
        "trip": "트립",
        "undead": "언데드",
        "urchin": "어친",
        "vendo": "벤도",
        "viking": "바이킹",
        "vines": "덩굴",
    "warrior": "전사",
    "water": "물",
    "werewolf": "웨어울프",
    "wild": "야생",
    "wildling": "와일들링",
    "willow": "버드나무",
    "wind": "바람",
    "wolf": "늑대",
    "wolfhound": "울프하운드",
    "worker": "일꾼",
    "worm": "벌레",
    "young": "어린",
    "youth": "청년",
    "zombie": "좀비",
}

ITEM_WORDS.update(
    {
        "adamantium": "아다만티움",
        "aegir": "에이기르",
        "airy": "에어리",
        "amulet": "아뮬렛",
        "antlered": "뿔 달린",
        "arcanite": "아카나이트",
        "asterite": "아스테라이트",
        "bar": "바",
        "barbed": "가시 달린",
        "bars": "바",
        "box": "박스",
        "bracket": "브래킷",
        "essence": "에센스",
        "fist": "피스트",
        "for": "용",
        "cheese": "치즈",
        "hero": "영웅",
        "hibernia": "하이버니아",
        "jewelry": "주얼리",
        "lantern": "랜턴",
        "market": "시장",
        "metal": "금속",
        "mirror": "거울",
        "mithril": "미스릴",
        "netherium": "네더리움",
        "of": "의",
        "plans": "설계도",
        "razored": "칼날 달린",
        "remains": "유해",
        "rent": "임대",
        "return": "귀환",
        "riveted": "리벳 박힌",
        "roughhewn": "거칠게 깎은",
        "shop": "상점",
        "shard": "파편",
        "signpost": "표지판",
        "strips": "조각",
        "svarkedja": "스바르케드야",
        "starkakedja": "스타르카케드야",
        "tapestry": "태피스트리",
        "token": "토큰",
        "toughened": "강화된",
        "wall": "벽",
        "wrought": "가공",
        "yr": "년",
    }
)

NPC_WORDS.update(
    {
        "accursed": "저주받은",
        "algae": "조류",
        "albion": "알비온",
        "alespiar": "알레스피어",
        "animus": "애니머스",
        "arboreal": "아보리얼",
        "arawnite": "아라운나이트",
        "banshee": "밴시",
        "basalt": "현무암",
        "bayer": "베이어",
        "beachcomber": "해변수색꾼",
        "bestigar": "베스티가르",
        "blighter": "블라이터",
        "blodfelag": "블로드펠라그",
        "blood": "피",
        "boar": "멧돼지",
        "bone-eater": "뼈먹보",
        "boogey": "부기",
        "boreal": "북풍",
        "bounder": "바운더",
        "brigand": "약탈자",
        "broms": "브롬스",
        "bwca": "부카",
        "captain": "대장",
        "captive": "포로",
        "changeling": "체인질링",
        "chattering": "재잘대는",
        "chiller": "칠러",
        "chillsome": "한기 어린",
        "cicada": "매미",
        "clanmother": "클랜 어미",
        "clerk": "서기",
        "cliff": "절벽",
        "commander": "커맨더",
        "condemned": "단죄받은",
        "corybantic": "코리반틱",
        "crazed": "광기 어린",
        "cyclops": "사이클롭스",
        "danaoin": "다나오인",
        "deamhan": "데이반",
        "decaying": "부패해가는",
        "defender": "방어자",
        "disperser": "분산체",
        "djur": "드유르",
        "doe": "암사슴",
        "doomed": "파멸한",
        "drake": "드레이크",
        "drakoran": "드라코란",
        "drakulv": "드라쿨브",
        "dwarf": "드워프",
        "dweller": "거주자",
        "eater": "먹보",
        "creeper": "크리퍼",
        "eviscerater": "절단자",
        "fairy": "페어리",
        "fallen": "타락한",
        "faraheim": "파라헤임",
        "fawn": "새끼 사슴",
        "fearann": "피어란",
        "feeder": "먹이꾼",
        "fenrir": "펜리르",
        "fiend": "핀드",
        "finliath": "핀리아스",
        "diamondback": "다이아몬드백",
        "ellyll": "엘릴",
        "fomorian": "포모리안",
        "finguard": "핀가드",
        "fisher": "낚시꾼",
        "fisherman": "어부",
        "fly": "파리",
        "frore": "서리",
        "glacial": "빙하",
        "glimmer": "글리머",
        "goblin": "고블린",
        "golem": "골렘",
        "gnarled": "뒤틀린",
        "granite": "화강암",
        "greater": "상급",
        "griffon": "그리폰",
        "guardsman": "경비병",
        "gurite": "구라이트",
        "hagbui": "하그부이",
        "harvester": "수확자",
        "hatchling": "해츨링",
        "headhunter": "헤드헌터",
        "hibernian": "하이버니아",
        "hound": "하운드",
        "howler": "하울러",
        "hrimthursa": "흐림투르사",
        "huscarl": "후스카를",
        "ice": "얼음",
        "icestrider": "아이스스트라이더",
        "interceptor": "요격병",
        "invader": "침략자",
        "jotun": "요툰",
        "keltoi": "켈토이",
        "king": "왕",
        "koalinth": "코알린스",
        "kudzu": "칡덩굴",
        "lammia": "라미아",
        "larling": "라를링",
        "legionnaire": "군단병",
        "leprechaun": "레프러콘",
        "lesser": "하급",
        "lich": "리치",
        "magi": "마기",
        "mammoth": "매머드",
        "man": "남자",
        "mantid": "맨티드",
        "marauder": "약탈자",
        "master": "마스터",
        "mature": "성숙한",
        "menace": "위협",
        "midgard": "미드가르드",
        "molochian": "몰로키안",
        "morvalt": "모르발트",
        "mountain": "산",
        "myling": "마일링",
        "myrmidon": "미르미돈",
        "necyomancer": "네시오맨서",
        "ogre": "오우거",
        "oracle": "오라클",
        "orm": "오름",
        "patrol": "순찰대",
        "plated": "갑옷 입은",
        "protector": "수호자",
        "quasit": "쿼짓",
        "raider": "레이더",
        "rainbow": "무지개",
        "ranger": "레인저",
        "ravenclan": "레이븐클랜",
        "redcap": "레드캡",
        "remnant": "잔재",
        "scout": "정찰병",
        "sentry": "파수병",
        "shale": "셰일",
        "shard": "파편",
        "shrouder": "슈라우더",
        "siabra": "시아브라",
        "sidhe": "시드",
        "skrat": "스크랫",
        "skugga": "스쿠가",
        "soldier": "병사",
        "soultorn": "영혼 찢긴",
        "spectral": "스펙트럴",
        "svartalf": "스바르탈프",
        "tempter": "유혹자",
        "thrawn": "뒤틀린",
        "snowcrab": "눈게",
        "snowshoe": "스노우슈",
        "scrag": "스크래그",
        "snowscout": "눈 정찰병",
        "sjoalf": "쇼알프",
        "tracker": "추적자",
        "tidal": "조수",
        "torpor": "혼미",
        "treant": "트리언트",
        "troll": "트롤",
        "tylwyth": "틸위스",
        "unearthed": "파헤쳐진",
        "unseelie": "언실리",
        "up": "",
        "vanvettig": "반베티그",
        "walking": "걸어다니는",
        "weatherwitch": "날씨마녀",
        "whelp": "새끼",
        "washed": "떠밀려온",
        "weeping": "우는",
        "winged": "날개 달린",
        "wight": "와이트",
        "winter": "겨울",
        "wintery": "겨울의",
        "villager": "마을 주민",
        "cutthroat": "악랄한",
        "pitch": "검은",
        "wyvern": "와이번",
        "yale": "예일",
        "yeti": "예티",
    }
)

NPC_WORDS.update(
    {
        "avernal": "어버널",
        "cavernous": "동굴의",
        "crater": "크레이터",
        "rocot": "로콧",
        "teg": "테그",
        "wayguard": "길목 경비병",
        "waylayer": "매복자",
    }
)

NPC_WORDS.update(
    {
        "amadan": "아마단",
        "ambusher": "매복병",
        "aonghus": "아옹구스",
        "arachite": "아라카이트",
        "armiger": "아미거",
        "avenger": "복수자",
        "balorian": "발로리안",
        "banty": "밴티",
        "barkstripper": "나무껍질 벗기는 자",
        "basilisk": "바실리스크",
        "boobrie": "부브리",
        "botonid": "보토니드",
        "broodmother": "무리어미",
        "cluricaun": "클루리컨",
        "cockatrice": "코카트리스",
        "curmudgeon": "커머전",
        "cutter": "절단자",
        "dauber": "도버",
        "darrig": "다리그",
        "dervish": "더비시",
        "demolisher": "파괴자",
        "drinker": "흡혈자",
        "drau'gyn": "드라우긴",
        "dry'ak": "드라이악",
        "dryad": "드라이어드",
        "empyrean": "엠피리언",
        "energy": "에너지",
        "eriu": "에리우",
        "etvarg": "에트바르그",
        "eyrie": "둥지",
        "far": "파르",
        "frukta": "프룩타",
        "fuath": "푸아스",
        "gasher": "가셔",
        "gladiator": "검투사",
        "goborchend": "고보르첸드",
        "grazer": "풀뜯이",
        "greenhand": "초록손",
        "greensilk": "그린실크",
        "griffman": "그리프맨",
        "grovewood": "그로브우드",
        "hamadryad": "하마드라이어드",
        "iceberg": "빙산",
        "irewood": "아이어우드",
        "ixthiar": "익스티아르",
        "keeper": "수호자",
        "mender": "수선자",
        "mephit": "메피트",
        "merman": "머맨",
        "mass": "덩어리",
        "muire": "무이레",
        "naburite": "나부라이트",
        "occupier": "점령자",
        "of": "의",
        "ooze": "우즈",
        "peallaidh": "펠라이",
        "presence": "존재",
        "priest": "사제",
        "queen": "여왕",
        "rencan": "렌칸",
        "runes": "룬",
        "sentinel": "감시자",
        "skadedjur": "스카데듀르",
        "skogsra": "스코그스라",
        "soul": "영혼",
        "spore": "포자",
        "spraggonale": "스프라곤에일",
        "stonecrush": "스톤크러쉬",
        "succubus": "서큐버스",
        "sylvanshade": "실반셰이드",
        "syhr'phint": "시르핀트",
        "tender": "관리자",
        "tingler": "팅글러",
        "thrall": "노예",
        "touched": "손댄",
        "twisted": "뒤틀린",
        "waterstrider": "물소금쟁이",
        "wi'voron": "위보론",
        "wisp": "위습",
        "wolfaur": "울포어",
        "wood": "나무",
        "wolverine": "울버린",
        "wraith": "망령",
    }
)

ITEM_WORDS.update(
    {
        "abysmal": "어비스",
        "accursed": "저주받은",
        "accommodation": "조정",
        "alacritous": "민첩한",
        "albion": "알비온",
        "arcane": "아케인",
        "arms": "암즈",
        "armsman": "암즈맨",
        "avernal": "어버널",
        "azure": "하늘빛",
        "bladeblocker": "블레이드블로커",
        "blood": "피",
        "bloody": "피 묻은",
        "bone": "뼈",
        "boned": "뼈 덧댄",
        "cailiocht": "카일리오흐트",
        "carbide": "카바이드",
        "chain": "체인",
        "circlet": "서클릿",
        "cloak": "망토",
        "cobalt": "코발트",
        "commands": "커맨드",
        "constaic": "콘스테이크",
        "curative": "큐러티브",
        "crystallized": "결정화된",
        "cured": "가공한",
        "daemon": "데몬",
        "darkened": "어두워진",
        "darkspire": "다크스파이어",
        "darksteel": "다크스틸",
        "defender": "디펜더",
        "demon": "데몬",
        "dextera": "덱스테라",
        "dragonslayer": "드래곤슬레이어",
        "dragonsworn": "드래곤스원",
        "drakescale": "드레이크스케일",
        "embossed": "엠보스",
        "encrusted": "박힌",
        "exquisite": "정교한",
        "ethereal": "에테리얼",
        "flawless": "완벽한",
        "forlorn": "쓸쓸한",
        "frozen": "얼어붙은",
        "gauntlets": "건틀릿",
        "glaive": "글레이브",
        "greaves": "그리브",
        "hat": "모자",
        "heater": "히터",
        "imbued": "주입된",
        "infernal": "인퍼널",
        "ivy": "아이비",
        "labyrinth": "라비린스",
        "lamellar": "라멜라",
        "leaf": "잎",
        "legs": "다리",
        "light": "라이트",
        "lightning": "번개",
        "lute": "류트",
        "maleficent": "악의적인",
        "maligned": "악명 높은",
        "malison": "저주",
        "mantle": "맨틀",
        "martial": "무술",
        "medal": "메달",
        "medallion": "메달리온",
        "morning": "모닝",
        "mythirian": "미시리안",
        "necklace": "목걸이",
        "netherite": "네더라이트",
        "nightshade": "나이트셰이드",
        "pendant": "펜던트",
        "protector": "프로텍터",
        "quarterstaff": "쿼터스태프",
        "quilted": "퀼팅",
        "rapier": "레이피어",
        "resisting": "저항",
        "rigid": "단단한",
        "ring": "반지",
        "ringed": "고리장식",
        "runed": "룬 새긴",
        "runewood": "룬우드",
        "runic": "룬",
        "sash": "새시",
        "shadow": "섀도우",
        "shadowed": "그림자진",
        "shimmering": "희미하게 빛나는",
        "shroud": "슈라우드",
        "sigil": "시길",
        "silken": "실크",
        "silksteel": "실크스틸",
        "soul": "소울",
        "soulbound": "소울바운드",
        "steeple": "첨탑",
        "suede": "스웨이드",
        "symbiotic": "공생",
        "superior": "상급",
        "tempered": "단련된",
        "threaded": "실로 엮은",
        "thought": "사념",
        "tunic": "튜닉",
        "tuscarian": "투스카리안",
        "vambraces": "뱀브레이스",
        "vigilant": "비질런트",
        "vine": "덩굴",
        "vigor": "활력",
        "woven": "직조된",
        "wreath": "화환",
    }
)

ITEM_WORDS.update(
    {
        "adribard": "아드리바드",
        "adze": "자귀",
        "benthic": "심해",
        "broadsword": "브로드소드",
        "cave": "동굴",
        "chitin": "키틴",
        "cleaver": "클리버",
        "cloud": "구름",
        "covered": "덮인",
        "crossbow": "크로스보우",
        "crown": "왕관",
        "cursed": "저주받은",
        "death": "죽음",
        "defiled": "더럽혀진",
        "dochar": "도하르",
        "drum": "드럼",
        "duskwood": "더스크우드",
        "dust": "가루",
        "ebon": "흑단",
        "edge": "엣지",
        "eldritch": "엘드리치",
        "enchanted": "마법부여된",
        "encrusted": "박힌",
        "ensorcelled": "마법 걸린",
        "eye": "눈",
        "flute": "플루트",
        "focus": "포커스",
        "forged": "제련된",
        "free": "프리",
        "fur": "털",
        "glacier": "빙하",
        "goblin": "고블린",
        "granite": "화강암",
        "guard": "가드",
        "handed": "핸드",
        "harp": "하프",
        "harvest": "하베스트",
        "heartwood": "하트우드",
        "hooded": "후드 달린",
        "hunter": "헌터",
        "kobold": "코볼드",
        "magus": "마구스",
        "mighty": "강력한",
        "one": "원",
        "pick": "픽",
        "petrified": "석화된",
        "rune": "룬",
        "satago": "사타고",
        "sanguine": "상귀네",
        "scepter": "셉터",
        "shell": "껍질",
        "skin": "가죽",
        "speedy": "빠른",
        "spider": "거미",
        "storm": "스톰",
        "stitched": "꿰맨",
        "tipped": "끝장식",
        "tooth": "이빨",
        "throwing": "투척",
        "trophy": "트로피",
        "trident": "트라이던트",
        "twilight": "트와일라잇",
        "twisted": "뒤틀린",
        "whip": "채찍",
        "wind": "윈드",
        "wind-wrought": "바람으로 벼린",
        "wulfen": "울펜",
    }
)

ITEM_WORDS.update(
    {
        "abyssal": "어비스",
        "adremel": "아드레멜",
        "advisor": "어드바이저",
        "aerial": "에어리얼",
        "animist": "애니미스트",
        "ansuz": "안수즈",
        "aptitude": "적성",
        "astral": "아스트랄",
        "average": "평균",
        "avoidance": "회피",
        "bainshee": "밴시",
        "balanced": "균형 잡힌",
        "band": "밴드",
        "barricading": "방벽",
        "basalt": "현무암",
        "bastard": "바스타드",
        "beads": "비즈",
        "bedlam": "베들램",
        "bespelled": "주문 걸린",
        "blackheart": "블랙하트",
        "blackthorn": "블랙쏜",
        "blaze": "블레이즈",
        "block": "블록",
        "bodybender": "바디벤더",
        "bonedancer": "본댄서",
        "bracer": "브레이서",
        "braided": "브레이디드",
        "brimstone": "브림스톤",
        "brute": "브루트",
        "cabalist": "카발리스트",
        "chaos": "카오스",
        "choker": "초커",
        "collar": "칼라",
        "command": "커맨드",
        "composite": "컴포지트",
        "corcra": "코크라",
        "corrupted": "오염된",
        "coward": "카워드",
        "cruaigh": "크루아이",
        "cruanach": "크루아나흐",
        "crypt": "크립트",
        "crystalized": "결정화된",
        "cutter": "커터",
        "cymric": "컴릭",
        "daingean": "다인건",
        "daring": "대담한",
        "darkness": "다크니스",
        "dealrach": "델라흐",
        "depths": "심연",
        "desert": "사막",
        "despoiled": "훼손된",
        "devourer": "데바우러",
        "diabolic": "디아볼릭",
        "dire": "다이어",
        "dismal": "음울한",
        "double": "더블",
        "dragon": "드래곤",
        "dread": "드레드",
        "dreams": "꿈",
        "dried": "말린",
        "earth": "대지",
        "ebonwood": "흑단나무",
        "edgebender": "엣지벤더",
        "eloquent": "엘로퀀트",
        "enchanter": "인챈터",
        "eternal": "이터널",
        "evasion": "회피",
        "faded": "빛바랜",
        "falcata": "팔카타",
        "fantasy": "판타지",
        "fiendish": "핀디시",
        "fiery": "불타는",
        "fluted": "플루티드",
        "focal": "포컬",
        "fossil": "화석",
        "fortifying": "강화",
        "fuliginous": "검댕빛",
        "gale": "강풍",
        "ghostly": "고스트리",
        "girdle": "거들",
        "greater": "상급",
        "greenmaw": "그린모",
        "heatbender": "히트벤더",
        "honor": "명예",
        "honour": "명예",
        "hooked": "갈고리형",
        "icebender": "아이스벤더",
        "illusions": "환영",
        "improved": "개량된",
        "insightful": "통찰",
        "intellect": "지성",
        "jester": "제스터",
        "kel": "켈",
        "lesser": "하급",
        "lithic": "석질",
        "lucerne": "루체른",
        "luminescent": "루미네센트",
        "luminous": "루미너스",
        "lupine": "루핀",
        "lustrous": "광택",
        "magic": "마법",
        "magma": "마그마",
        "mana": "마나",
        "marked": "표식",
        "mattock": "매톡",
        "mauler": "마울러",
        "malevolent": "악의적인",
        "mentalist": "멘탈리스트",
        "midgard": "미드가르드",
        "might": "힘",
        "mittens": "장갑",
        "mjuklaedar": "뮤클레다르",
        "moldy": "곰팡이 슨",
        "moss": "이끼",
        "mystic": "미스틱",
        "mystical": "미스티컬",
        "mysticism": "미스티시즘",
        "nadurtha": "나두르사",
        "nature": "네이처",
        "noble": "노블",
        "noble's": "노블의",
        "nokkvi": "노크비",
        "notes": "노트",
        "oblivion": "오블리비언",
        "ornate": "장식",
        "osnadurtha": "오스나두르사",
        "overlord": "오버로드",
        "pansarkedja": "판사르케드야",
        "parry": "패리",
        "passage": "통행",
        "path": "길",
        "paths": "길",
        "phosphorescent": "인광",
        "pictslayer": "픽트슬레이어",
        "pitted": "패인",
        "pike": "파이크",
        "polished": "광택낸",
        "pointed": "뾰족한",
        "power": "파워",
        "prayerbound": "프레이어바운드",
        "protector": "프로텍터",
        "pyroclasmic": "파이로클라스믹",
        "recruit": "리크루트",
        "reed": "리드",
        "regal": "리갈",
        "reinforcing": "보강",
        "rest": "안식",
        "robes": "로브",
        "rod": "로드",
        "roman": "로만",
        "root": "루트",
        "royal": "로열",
        "ruin": "파멸",
        "runemaster": "룬마스터",
        "sacristan": "사크리스탄",
        "savage": "새비지",
        "scaled": "스케일드",
        "scythe": "사이드",
        "seamist": "시미스트",
        "sentinel": "센티넬",
        "shattering": "섀터링",
        "shillelagh": "실레일리",
        "sinew": "힘줄",
        "siphoning": "시포닝",
        "slith": "슬리스",
        "sliths": "슬리스",
        "smoldering": "그을린",
        "sorcerer": "소서러",
        "soulbinder": "소울바인더",
        "soultorn": "소울톤",
        "speedy": "스피디",
        "spined": "가시 박힌",
        "spirit": "스피릿",
        "spiritmaster": "스피릿마스터",
        "star": "스타",
        "stained": "물든",
        "starkaskodd": "스타르카스코드",
        "starklaedar": "스타르클레다르",
        "stelskodd": "스텔스코드",
        "stonewood": "스톤우드",
        "stones": "스톤",
        "sturdy": "튼튼한",
        "suppression": "서프레션",
        "surefooting": "확고한 발걸음",
        "svarlaedar": "스바르레다르",
        "svarskodd": "스바르스코드",
        "sylvan": "실반",
        "tacuil": "타쿠일",
        "tainted": "오염된",
        "tail": "꼬리",
        "tarboosh": "타부시",
        "tempestuous": "템페스추어스",
        "the": "",
        "theurgist": "서지스트",
        "thick": "두꺼운",
        "thurisaz": "투리사즈",
        "tomte": "톰테",
        "truesilver": "트루실버",
        "verdant": "초록빛",
        "villianous": "빌러너스",
        "void": "보이드",
        "weighted": "무게추 달린",
        "woolen": "울",
        "woodsman": "우즈맨",
        "wyvernskin": "와이번스킨",
    }
)

ITEM_WORDS.update(
    {
        "ageless": "에이지리스",
        "and": "와",
        "anarchy": "아나키",
        "arboreal": "아보리얼",
        "armguards": "암가드",
        "augmented": "오그먼트",
        "bangle": "뱅글",
        "bardiche": "바디슈",
        "bauble": "장식구",
        "bearded": "비어디드",
        "blademaster": "블레이드마스터",
        "blighted": "오염된",
        "bolstering": "보강",
        "carved": "조각된",
        "chasm": "캐즘",
        "deathly": "죽음의",
        "demise": "데마이즈",
        "dementia": "디멘시아",
        "demonic": "데모닉",
        "elder": "엘더",
        "ember": "잿불",
        "engraved": "새긴",
        "faithbound": "페이스바운드",
        "fell": "펠",
        "flecked": "얼룩진",
        "flesh": "플레시",
        "footman": "풋맨",
        "gaudy": "화려한",
        "gladius": "글라디우스",
        "grave": "그레이브",
        "guarded": "가드형",
        "guerdon": "보상",
        "gusting": "돌풍",
        "halberd": "할버드",
        "hammers": "해머",
        "health": "생명",
        "honed": "연마된",
        "honored": "명예로운",
        "icebound": "아이스바운드",
        "icy": "얼음의",
        "inconnu": "인콘누",
        "infused": "주입된",
        "insidious": "음흉한",
        "intent": "의지",
        "knives": "나이프",
        "lochaber": "로하버",
        "loyalist": "로열리스트",
        "matter": "매터",
        "matterbender": "매터벤더",
        "mercenary": "머서너리",
        "mercurial": "머큐리얼",
        "midnight": "미드나이트",
        "molded": "성형된",
        "mourning": "애도",
        "otherworld": "아더월드",
        "outcast": "아웃캐스트",
        "partisan": "파르티잔",
        "pewter": "퓨터",
        "protection": "보호",
        "queen": "퀸",
        "render": "렌더",
        "reaver": "리버",
        "sable": "세이블",
        "scarab": "스카라브",
        "scathing": "스케이싱",
        "seer": "시어",
        "shar": "샤르",
        "souls": "영혼",
        "spell": "스펠",
        "spellbound": "스펠바운드",
        "spiritist": "스피리티스트",
        "sweet": "달콤한",
        "tether": "테더",
        "tidings": "소식",
        "torment": "고통",
        "transient": "일시적인",
        "undaunted": "용맹한",
        "underground": "언더그라운드",
        "velvet": "벨벳",
        "walker": "워커",
        "warlock": "워록",
        "warrior": "워리어",
        "watery": "물빛",
        "widower": "위도어",
        "widowers": "위도어",
        "wisdom": "지혜",
        "wizard": "위저드",
        "zenith": "제니스",
    }
)

NPC_PREFIXES = (
    "a ",
    "an ",
    "the ",
)

TRANSLIT_DIGRAPHS = (
    ("tion", "션"),
    ("sion", "전"),
    ("ough", "오"),
    ("eigh", "에이"),
    ("augh", "오"),
    ("igh", "아이"),
    ("ph", "프"),
    ("ch", "치"),
    ("sh", "쉬"),
    ("th", "스"),
    ("qu", "쿼"),
    ("ck", "크"),
    ("ng", "응"),
    ("oo", "우"),
    ("ee", "이"),
    ("ea", "이"),
    ("ai", "에이"),
    ("ay", "에이"),
    ("ow", "오우"),
    ("ou", "우"),
)

TRANSLIT_CHARS = {
    "a": "아",
    "b": "브",
    "c": "크",
    "d": "드",
    "e": "에",
    "f": "프",
    "g": "그",
    "h": "흐",
    "i": "이",
    "j": "지",
    "k": "크",
    "l": "르",
    "m": "므",
    "n": "느",
    "o": "오",
    "p": "프",
    "q": "큐",
    "r": "르",
    "s": "스",
    "t": "트",
    "u": "우",
    "v": "브",
    "w": "우",
    "x": "크스",
    "y": "이",
    "z": "즈",
}


@dataclass(frozen=True)
class GeneratedRow:
    translation_id: str
    name: str


def parse_connection_string() -> dict[str, str]:
    root = ET.parse(CONFIG).getroot()
    value = root.findtext(".//DBConnectionString")
    if not value:
        raise RuntimeError(f"DBConnectionString not found in {CONFIG}")

    return {
        match.group(1).strip().lower(): match.group(2)
        for match in re.finditer(r"([^=;]+)=([^;]*)", value)
    }


def connect():
    parts = parse_connection_string()
    return pymysql.connect(
        host=parts.get("server", "127.0.0.1"),
        port=int(parts.get("port", "3306")),
        user=parts.get("userid") or parts.get("user id") or parts.get("user"),
        password=parts.get("password", ""),
        database=parts.get("database"),
        charset="utf8mb4",
        autocommit=False,
    )


def normalize_name(name: str) -> str:
    value = name.replace("`", "'").replace("_", " ")
    value = re.sub(r"\s*\((cancel|Cancel)\)\s*$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def split_words(name: str) -> list[str]:
    value = normalize_name(name)
    value = value.replace("/", " ").replace(":", " ")
    return [part for part in re.split(r"\s+", value) if part]


def build_npc_translation_id(name: str) -> str:
    builder = ["npc."]
    for char in name.strip().lower():
        if char.isalnum():
            builder.append(char)
        elif char in " -_":
            builder.append("_")
    return "".join(builder)


def transliterate_ascii_word(word: str) -> str:
    raw = word.strip()
    if not raw:
        return ""

    pieces = re.findall(r"[A-Za-z]+|\d+|[^A-Za-z\d]+", raw)
    rendered = []
    for piece in pieces:
        if piece.isdigit():
            rendered.append(piece)
            continue
        if not re.search(r"[A-Za-z]", piece):
            continue

        value = piece.lower()
        if value.endswith("ing") and len(value) > 4:
            rendered.append(transliterate_ascii_word(value[:-3]) + "잉")
            continue
        if value.endswith("ers") and len(value) > 4:
            rendered.append(transliterate_ascii_word(value[:-3]) + "어스")
            continue
        if value.endswith("er") and len(value) > 4:
            rendered.append(transliterate_ascii_word(value[:-2]) + "어")
            continue
        if value.endswith("y") and len(value) > 3:
            rendered.append(transliterate_ascii_word(value[:-1]) + "이")
            continue

        out = []
        index = 0
        while index < len(value):
            matched = False
            for source, target in TRANSLIT_DIGRAPHS:
                if value.startswith(source, index):
                    out.append(target)
                    index += len(source)
                    matched = True
                    break
            if matched:
                continue

            out.append(TRANSLIT_CHARS.get(value[index], value[index]))
            index += 1

        rendered.append("".join(out))

    return "".join(rendered) or raw


def translate_word(word: str, lexicon: dict[str, str]) -> tuple[str, bool]:
    raw = word.strip()
    if not raw:
        return "", True

    possessive = re.match(r"^(.+)'s$", raw)
    if possessive:
        base, known = translate_word(possessive.group(1), lexicon)
        return f"{base}의", known

    lower = raw.lower()
    if lower in lexicon:
        return lexicon[lower], True

    if "-" in lower:
        translated_parts = []
        known_count = 0
        for part in lower.split("-"):
            translated, known = translate_word(part, lexicon)
            translated_parts.append(translated)
            known_count += 1 if known else 0
        if known_count:
            return " ".join(part for part in translated_parts if part), known_count == len(translated_parts)

    if raw.isupper() and len(raw) <= 4:
        return transliterate_ascii_word(raw), False

    return transliterate_ascii_word(raw), False


def strip_possessive_suffix(word: str) -> str:
    lower = word.lower()
    return lower[:-2] if lower.endswith("'s") else lower


def compact_korean_order(words: list[str]) -> str:
    return " ".join(word for word in words if word)


def translate_place_name(name: str) -> str:
    normalized = normalize_name(name)
    if normalized in PLACE_NAMES:
        return PLACE_NAMES[normalized]

    translated = []
    place_words = ITEM_WORDS | {
        "bridge": "다리",
        "darkness": "다크니스",
        "encampment": "야영지",
        "entrance": "입구",
        "estuary": "하구",
        "fall": "폴스",
        "falls": "폴스",
        "frontier": "프론티어",
        "grifon": "그리폰",
        "griffon": "그리폰",
        "haven": "헤이븐",
        "keep": "성채",
        "lair": "소굴",
        "outpost": "전초기지",
        "portal": "포털",
        "retreat": "은거지",
        "stable": "마구간",
        "station": "기지",
        "village": "마을",
    }
    for word in split_words(normalized):
        result, _ = translate_word(word, place_words)
        if result:
            translated.append(result)
    return compact_korean_order(translated) or normalized


def try_translate_known_place_name(name: str) -> str | None:
    normalized = normalize_name(name)
    alias = PLACE_NAME_ALIASES.get(normalized)
    if alias:
        normalized = alias
    if normalized in PLACE_NAMES:
        return PLACE_NAMES[normalized]

    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalized)
    spaced = re.sub(r"\bEst\b", "East", spaced)
    spaced = re.sub(r"\bNoth\b", "North", spaced)
    alias = PLACE_NAME_ALIASES.get(spaced)
    if alias:
        spaced = alias
    return PLACE_NAMES.get(spaced)


def translate_craft_name(name: str) -> str:
    lowered = normalize_name(name).lower()
    if lowered in CRAFT_NAMES:
        return CRAFT_NAMES[lowered]

    translated = []
    for word in split_words(name):
        result, _ = translate_word(word, ITEM_WORDS | CRAFT_NAMES)
        if result:
            translated.append(result)
    return compact_korean_order(translated) or name


def translate_common_special_item_name(name: str) -> str | None:
    normalized = normalize_name(name)
    lowered = normalized.lower()

    exact = {
        "alchemy kit": "연금술 키트",
        "alchemy supplies": "연금술 보급품",
        "alchemy table": "연금술 테이블",
        "apprentice merchant": "견습 상인",
        "100 yr old cheese": "100년 숙성 치즈",
        "a rusty key": "녹슨 열쇠",
        "adder venom": "독사 독",
        "adult demestid beetles": "성체 데메스티드 딱정벌레",
        "aged fermented wode extract": "오래 숙성한 워드 추출물",
        "airy distill": "공기의 증류액",
        "albion tonic": "알비온 토닉",
        "alum": "명반",
        "amber ornate lamp": "호박 장식 램프",
        "amber small lamp": "호박 소형 램프",
        "amber strips": "호박 조각",
        "chestnut horse voucher": "밤색 말 교환권",
        "consignment merchant": "위탁 상인",
        "crafted weapon luster remover": "제작 무기 광택 제거제",
        "deed of guild transfer": "길드 이전 증서",
        "grandmaster merchant": "그랜드마스터 상인",
        "guild house medallion of passage": "길드 주택 통행 메달",
        "hearth bind medallion of passage": "귀환 위치 통행 메달",
        "horse voucher": "말 교환권",
        "house for sale signpost": "매물 주택 표지판",
        "house removal deed": "주택 철거 증서",
        "incantation merchant": "주문 상인",
        "porch deed": "현관 증서",
        "porch remove deed": "현관 제거 증서",
        "potion tincture enchantment supplies": "포션/팅크처/인챈트 보급품",
        "siegecraft supplies": "공성 제작 보급품",
        "spellcraft kit": "스펠크래프트 키트",
        "vault keeper": "금고지기",
    }
    if lowered in exact:
        return exact[lowered]

    match = re.match(r"^(\d+) gold rent token$", lowered)
    if match:
        return f"{match.group(1)} 골드 임대 토큰"

    match = re.match(r"^(albion|hibernia|midgard) (cottage|house|villa|mansion) deed$", lowered)
    if match:
        return f"{REALM_NAMES[match.group(1)]} {HOUSE_TYPE_NAMES[match.group(2)]} 증서"

    match = re.match(r"^(albion|hibernia|midgard) bindstone$", lowered)
    if match:
        return f"{REALM_NAMES[match.group(1)]} 바인드스톤"

    match = re.match(r"^(albion|hibernia|midgard) teleporter$", lowered)
    if match:
        return f"{REALM_NAMES[match.group(1)]} 텔레포터"

    match = re.match(r"^(albion|hibernia|midgard) vault$", lowered)
    if match:
        return f"{REALM_NAMES[match.group(1)]} 금고"

    match = re.match(r"^(albion|hibernia|midgard) vault keeper$", lowered)
    if match:
        return f"{REALM_NAMES[match.group(1)]} 금고지기"

    match = re.match(r"^amulet for (.+)$", normalized, re.IGNORECASE)
    if match:
        place = try_translate_known_place_name(match.group(1))
        return f"{place}행 아뮬렛" if place else None

    match = re.match(r"^fly to (.+)$", normalized, re.IGNORECASE)
    if match:
        place = try_translate_known_place_name(match.group(1))
        return f"{place}행 비행권" if place else None

    match = re.match(r"^(?:dragonfly )?ticket to (.+)$", normalized, re.IGNORECASE)
    if match:
        place = try_translate_known_place_name(match.group(1))
        return f"{place}행 티켓" if place else None

    match = re.match(r"^(.+) market return token$", normalized, re.IGNORECASE)
    if match:
        place = try_translate_known_place_name(match.group(1))
        return f"{place} 시장 귀환 토큰" if place else None

    match = re.match(r"^(.+) entrance return token$", normalized, re.IGNORECASE)
    if match:
        place = try_translate_known_place_name(match.group(1))
        return f"{place} 입구 귀환 토큰" if place else None

    match = re.match(r"^(.+) materials available signpost$", normalized, re.IGNORECASE)
    if match:
        craft = CRAFT_NAMES.get(normalize_name(match.group(1)).lower())
        return f"{craft} 재료 판매 표지판" if craft else None

    match = re.match(r"^(.+) for hire signpost$", normalized, re.IGNORECASE)
    if match:
        craft = CRAFT_NAMES.get(normalize_name(match.group(1)).lower())
        return f"{craft} 고용 표지판" if craft else None

    match = re.match(r"^(.+) supplies$", normalized, re.IGNORECASE)
    if match and re.search(r"(alchemy|siegecraft|spellcraft|potion|tincture|enchantment)", lowered):
        return f"{translate_craft_name(match.group(1))} 보급품"

    match = re.match(r"^(.+) metal bars?$", normalized, re.IGNORECASE)
    if match:
        return f"{translate_place_name(match.group(1))} 금속 바"

    match = re.match(r"^(.+) hinge$", normalized, re.IGNORECASE)
    if match:
        return f"{translate_place_name(match.group(1))} 경첩"

    match = re.match(r"^(.+) bracket$", normalized, re.IGNORECASE)
    if match:
        return f"{translate_place_name(match.group(1))} 브래킷"

    match = re.match(r"^(.+) small lantern$", normalized, re.IGNORECASE)
    if match:
        return f"{translate_place_name(match.group(1))} 소형 랜턴"

    match = re.match(r"^(.+) jewelry box$", normalized, re.IGNORECASE)
    if match:
        return f"{translate_place_name(match.group(1))} 주얼리 박스"

    match = re.match(r"^barrel of (.+)$", normalized, re.IGNORECASE)
    if match:
        return f"{translate_place_name(match.group(1))} 배럴"

    match = re.match(r"^(greater|superior)?\s*elixir of (.+)$", normalized, re.IGNORECASE)
    if match:
        prefix = {"greater": "상급 ", "superior": "고급 "}.get((match.group(1) or "").lower(), "")
        return f"{prefix}{translate_place_name(match.group(2))} 엘릭서"

    match = re.match(r"^draught of (.+)$", normalized, re.IGNORECASE)
    if match:
        return f"{translate_place_name(match.group(1))} 드래프트"

    match = re.match(r"^(minor|lethal)?\s*(.+) poison$", normalized, re.IGNORECASE)
    if match:
        prefix = {"minor": "하급 ", "lethal": "치명적인 "}.get((match.group(1) or "").lower(), "")
        return f"{prefix}{translate_place_name(match.group(2))} 포이즌"

    if lowered.endswith(" buff token"):
        return f"{translate_place_name(normalized[:-len(' buff token')])} 버프 토큰"

    if lowered.endswith(" voucher"):
        return f"{translate_place_name(normalized[:-len(' voucher')])} 교환권"

    return None


def is_common_special_item_candidate(item_id: str, level: int, item_type: int, name: str) -> bool:
    normalized = normalize_name(name)
    lowered = normalized.lower()
    item_key = (item_id or "").lower()

    common_patterns = (
        r"^\d+ gold rent token$",
        r"^(albion|hibernia|midgard) (bindstone|teleporter|vault|vault keeper)$",
        r"^(albion|hibernia|midgard) (cottage|house|villa|mansion) deed$",
        r"^amulet for .+",
        r"^fly to .+",
        r"^(dragonfly )?ticket to .+",
        r"^.+ (market|entrance) return token$",
        r"^.+ materials available signpost$",
        r"^.+ for hire signpost$",
        r"^.+ supplies$",
        r"^.+ (metal bars?|hinge|bracket|small lantern|jewelry box)$",
        r"^barrel of .+",
        r"^(greater|superior)?\s*elixir of .+",
        r"^draught of .+",
        r"^(minor|lethal)?\s*.+ poison$",
        r"^.+ buff token$",
        r"^.+ voucher$",
    )
    if any(re.match(pattern, lowered) for pattern in common_patterns):
        return True

    exact_names = {
        "100 yr old cheese",
        "a rusty key",
        "adder venom",
        "adult demestid beetles",
        "aged fermented wode extract",
        "airy distill",
        "albion tonic",
        "alchemy kit",
        "alchemy supplies",
        "alchemy table",
        "alum",
        "amber ornate lamp",
        "amber small lamp",
        "amber strips",
        "apprentice merchant",
        "chestnut horse voucher",
        "consignment merchant",
        "crafted weapon luster remover",
        "deed of guild transfer",
        "grandmaster merchant",
        "guild house medallion of passage",
        "hearth bind medallion of passage",
        "horse voucher",
        "house for sale signpost",
        "house removal deed",
        "incantation merchant",
        "porch deed",
        "porch remove deed",
        "potion tincture enchantment supplies",
        "siegecraft supplies",
        "spellcraft kit",
        "vault keeper",
    }
    if lowered in exact_names:
        return True

    if level == 0 and item_type == 0 and item_key.startswith("housing_"):
        return any(keyword in lowered for keyword in ("deed", "merchant", "signpost", "supplies", "teleporter", "vault"))

    return False


def translate_item_name(name: str, broad: bool = False) -> str | None:
    special = translate_common_special_item_name(name)
    if special:
        return special

    normalized = normalize_name(name)
    of_match = re.match(r"^(.+?)\s+of\s+(?:the\s+)?(.+)$", normalized, re.IGNORECASE)
    if of_match:
        left = translate_item_name(of_match.group(1), broad)
        right = translate_item_name(of_match.group(2), broad)
        if left and right:
            return f"{right}의 {left}"

    words = split_words(name)
    if not words:
        return None

    translated = []
    known_count = 0
    for word in words:
        result, known = translate_word(word, ITEM_WORDS)
        if result:
            translated.append(result)
        if known:
            known_count += 1

    if not translated:
        return None

    known_ratio = known_count / len(words)
    has_equipment_noun = any(
        strip_possessive_suffix(word) in ITEM_WORDS
        and ITEM_WORDS[strip_possessive_suffix(word)] in {
            "액스",
            "벨트",
            "보우",
            "팔찌",
            "브레이서",
            "흉갑",
            "부츠",
            "모자",
            "클럽",
            "단검",
            "장갑",
            "해머",
            "투구",
            "저킨",
            "주얼",
            "레깅스",
            "메이스",
            "메달",
            "메달리온",
            "목걸이",
            "미시리안",
            "바지",
            "반지",
            "새시",
            "로브",
            "방패",
            "셔츠",
            "소매",
            "스피어",
            "스태프",
            "소드",
            "조끼",
            "랩",
        }
        for word in words
    )

    if not broad and known_ratio < 0.5 and not has_equipment_noun:
        return None

    candidate = compact_korean_order(translated)
    if not re.search("[가-힣]", candidate) or candidate == normalized:
        return None
    if re.search("[A-Za-z]", candidate):
        return None
    return candidate


def translate_npc_name(name: str, broad: bool = False) -> str | None:
    normalized = normalize_name(name)
    lowered = normalized.lower()
    for prefix in NPC_PREFIXES:
        if lowered.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break

    words = split_words(normalized)
    if not words:
        return None

    translated = []
    known_count = 0
    for word in words:
        result, known = translate_word(word, NPC_WORDS)
        if result:
            translated.append(result)
        if known:
            known_count += 1

    if not translated:
        return None

    known_ratio = known_count / len(words)
    last_word = strip_possessive_suffix(words[-1])
    last_word_known = last_word in NPC_WORDS
    if not broad and known_ratio < 0.5 and not last_word_known:
        return None

    candidate = compact_korean_order(translated)
    if not re.search("[가-힣]", candidate) or candidate == normalized:
        return None
    if re.search("[A-Za-z]", candidate):
        return None
    return candidate


def load_existing_translation_ids(cur, table: str, tag: str) -> set[str]:
    cur.execute(
        f"SELECT TranslationId FROM {table} WHERE Language='KR' AND (Tag IS NULL OR Tag<>%s)",
        (tag,),
    )
    return {row[0] for row in cur.fetchall() if row[0]}


def collect_npc_rows(cur, limit: int | None, broad: bool) -> list[GeneratedRow]:
    existing = load_existing_translation_ids(cur, "languagenpc", NPC_TAG)
    cur.execute(
        """
        SELECT Name, COUNT(*) AS cnt
        FROM mob
        WHERE Name REGEXP '[A-Za-z]'
        GROUP BY Name
        ORDER BY cnt DESC, Name
        """
    )
    rows = []
    seen = set()
    for name, _ in cur.fetchall():
        translation_id = build_npc_translation_id(name)
        if translation_id in existing or translation_id in seen:
            continue
        translated = translate_npc_name(name, broad)
        if not translated:
            continue
        rows.append(GeneratedRow(translation_id, translated))
        seen.add(translation_id)
        if limit and len(rows) >= limit:
            break
    return rows


def collect_item_rows(cur, limit: int | None, broad: bool, all_items: bool, common_special_items: bool) -> list[GeneratedRow]:
    existing = load_existing_translation_ids(cur, "languageitem", ITEM_TAG)
    equipment_slots = ",".join(str(slot) for slot in EQUIPMENT_ITEM_SLOTS)
    if all_items:
        item_filter = ""
    elif common_special_items:
        item_filter = f"AND ((Level > 0 AND Item_Type IN ({equipment_slots})) OR Level = 0)"
    else:
        item_filter = f"AND Level > 0 AND Item_Type IN ({equipment_slots})"

    cur.execute(
        f"""
        SELECT Id_nb, TranslationId, Name, Level, Item_Type
        FROM itemtemplate
        WHERE Name REGEXP '[A-Za-z]'
          {item_filter}
        ORDER BY Level, Name, Id_nb
        """
    )
    rows = []
    seen = set()
    for item_id, translation_id, name, level, item_type in cur.fetchall():
        if item_id in existing or item_id in seen:
            continue
        if translation_id and translation_id in existing:
            continue

        if common_special_items and not all_items and level == 0:
            if not is_common_special_item_candidate(item_id, level, item_type, name):
                continue
            translated = translate_common_special_item_name(name)
        else:
            translated = translate_item_name(name, broad)

        if not translated:
            continue
        rows.append(GeneratedRow(item_id, translated))
        seen.add(item_id)
        if limit and len(rows) >= limit:
            break
    return rows


def apply_rows(cur, table: str, tag: str, rows: list[GeneratedRow]) -> None:
    cur.execute(f"DELETE FROM {table} WHERE Language='KR' AND Tag=%s", (tag,))
    if not rows:
        return

    id_column = "LanguageNPC_ID" if table == "languagenpc" else "LanguageItem_ID"
    cur.executemany(
        f"""
        INSERT INTO {table}
          ({id_column}, TranslationId, Language, Name, Suffix, GuildName, ExamineArticle, MessageArticle, Tag, LastTimeRowUpdated)
        VALUES
          (UUID(), %s, 'KR', %s, NULL, NULL, NULL, NULL, %s, NOW())
        """
        if table == "languagenpc"
        else f"""
        INSERT INTO {table}
          ({id_column}, TranslationId, Language, Name, Description, ExamineArticle, MessageArticle, Tag, LastTimeRowUpdated)
        VALUES
          (UUID(), %s, 'KR', %s, NULL, NULL, NULL, %s, NOW())
        """,
        [(row.translation_id, row.name, tag) for row in rows],
    )


def print_samples(title: str, rows: list[GeneratedRow], count: int) -> None:
    print(f"{title}: {len(rows)} generated")
    for row in rows[:count]:
        print(f"  {row.translation_id}\t{row.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply generated rows to the local DB.")
    parser.add_argument("--npc-limit", type=int, default=None)
    parser.add_argument("--item-limit", type=int, default=None)
    parser.add_argument("--broad", action="store_true", help="Also generate fallback transliterations for otherwise unknown names.")
    parser.add_argument("--all-items", action="store_true", help="Generate item rows outside equipment slots too. Default is equipment only.")
    parser.add_argument("--common-special-items", action="store_true", help="Also generate safe common level-0 item rows such as rent tokens, housing service items, and basic travel vouchers.")
    parser.add_argument("--skip-npcs", action="store_true")
    parser.add_argument("--skip-items", action="store_true")
    parser.add_argument("--samples", type=int, default=12)
    args = parser.parse_args()

    conn = connect()
    try:
        cur = conn.cursor()
        npc_rows = [] if args.skip_npcs else collect_npc_rows(cur, args.npc_limit, args.broad)
        item_rows = [] if args.skip_items else collect_item_rows(cur, args.item_limit, args.broad, args.all_items, args.common_special_items)

        print_samples("NPC auto seed", npc_rows, args.samples)
        print_samples("Item auto seed", item_rows, args.samples)

        if args.apply:
            if not args.skip_npcs:
                apply_rows(cur, "languagenpc", NPC_TAG, npc_rows)
            if not args.skip_items:
                apply_rows(cur, "languageitem", ITEM_TAG, item_rows)
            conn.commit()
            print("Applied generated KR localization rows.")
        else:
            conn.rollback()
            print("Dry run only. Pass --apply to write generated rows.")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
