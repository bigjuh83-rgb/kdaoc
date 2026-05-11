# OpenDAoC Local LLM World System Design

## Goal

KDAOC/OpenDAoC 서버를 단순 반복 사냥 서버가 아니라, 플레이어 행동과 몬스터 생존, 지역 상태가 서로 영향을 주는 살아있는 MMORPG 월드로 만든다.

최종 목표:

```text
플레이어의 행동은 세계를 변화시키고,
살아남은 몬스터는 세력과 역사를 만들며,
보스는 지역과 마을을 뒤흔드는 세계 사건이 된다.
그 모든 흔적은 서버의 역사로 기록되고,
서버 자체가 살아있는 판타지 세계처럼 진화하는 MMORPG를 만든다.
```

핵심 원칙:

```text
서버는 세계의 법이고, LLM은 세계관 작가다.
전투는 서버가 한다. LLM은 전투의 이야기를 만든다.
LLM 생성 가능 = 표현과 제안
LLM 생성 금지 = 수치와 실행
```

## Scope

In scope:

- 몬스터 생존 기반 성장 시스템.
- Elite, Champion, Boss, World Boss 후보 승급 흐름.
- 보스 주변 몬스터 그룹 AI 설계.
- 지역 위험도와 세계 영향 시스템.
- 플레이어 공략 학습과 보스 기억 시스템.
- AI 보스 설계, 대사, 성격, 연출 생성.
- 서버 역사, 뉴스, 기록관, 게시판 설계.
- 메인 OpenDAoC 서버와 메인 PC 로컬 LLM 서버의 역할 분리.
- MariaDB 기반 비동기 LLM 작업 큐.
- JSON 기반 LLM 출력과 서버 검증.
- 운영 안정성을 위한 금지 구조와 밸런스 제한.

Out of scope for the first implementation:

- LLM이 실시간 전투를 직접 조종하는 구조.
- LLM이 DB, 스폰, 보상, 계정, 경제 수치를 직접 변경하는 구조.
- 네이버 카페 자동 게시. 첫 단계는 카페 공지 초안 생성까지만 한다.
- 월드 보스와 도시 함락 같은 Legendary급 이벤트의 완전 자동 적용.
- 모든 몬스터의 영구 추적. 의미 있는 생존 후보만 기록한다.

## System Roles

OpenDAoC 서버:

- 게임 루프, 전투, 스폰, 보상, DB 원본 기록을 처리한다.
- 몬스터 생존 시간, 전투 통계, 지역 위험도, 성장 점수를 계산한다.
- 보스 후보와 허용 패턴 템플릿을 결정한다.
- LLM 작업을 큐에 등록한다.
- LLM 결과를 JSON 스키마, 금칙어, 길이, 템플릿, 밸런스 규칙으로 검증한다.
- GM 승인 여부를 판단하고 실제 게임에 적용한다.

LLM 서버:

- 메인 PC에서 로컬 모델을 실행하는 보조 서버다.
- 보스 이름, 칭호, 세력명, 성격, 말투, 대사, 연출, 소문, 뉴스, 역사 문장, 퀘스트 설명, 패턴 아이디어, GM 요약, 카페 공지 초안만 생성한다.
- JSON만 반환한다.
- 게임 서버의 생명줄이 아니며, 꺼져도 게임은 계속 돌아가야 한다.

GM:

- World Boss, 도시 함락, 경제 변화, 강한 지역 이벤트, 카페 공지 후보를 승인한다.
- 지형 악용 의심, 비정상 전투, 과도한 LLM 결과를 검토한다.

Player:

- 몬스터 생존, 지역 위험도, 보스 기억, 서버 역사에 원인을 만든다.
- 방치한 위협은 커지고, 해결한 위협은 기록으로 남는다.

## Recommended Architecture

```text
OpenDAoC Server
  -> World Event Collector
  -> World State DB
  -> LLM Job Queue
  -> Local LLM Worker on Main PC
  -> Local LLM Model
  -> LLM Result DB
  -> Validation Layer
  -> GM Review / Auto Apply
  -> Game / Dashboard / Cafe Draft
```

권장 통신 방식은 MariaDB 기반 작업 큐다.

```text
1. OpenDAoC 서버가 llm_job 테이블에 작업을 등록한다.
2. 메인 PC LLM Worker가 Pending 작업을 조회한다.
3. Worker가 Qwen 같은 로컬 모델을 호출한다.
4. JSON 결과를 llm_result 테이블에 저장한다.
5. OpenDAoC 서버가 결과를 읽고 검증한다.
6. 자동 적용하거나 GM 승인 대기 상태로 둔다.
```

이 구조의 장점:

- LLM 서버가 느리거나 꺼져도 게임 서버는 계속 동작한다.
- 전투 중 지연이 없다.
- 실패, 재시도, 검증, 감사 로그를 관리하기 쉽다.
- OpenDAoC 서버와 LLM 서버의 책임이 명확하다.
- 추후 LLM Worker를 여러 개로 늘릴 수 있다.

## Main Server Design

OpenDAoC 서버는 C# 기반 로직으로 모든 실제 판정과 적용을 담당한다.

후보 모듈:

```text
WorldStateService.cs
MonsterSurvivalService.cs
RegionDangerService.cs
BossMemoryService.cs
BossCandidateService.cs
BossPatternTemplateService.cs
BossDesignApplyService.cs
WorldEventHistoryService.cs
LlmJobQueueService.cs
LlmResultValidationService.cs
ChronicleService.cs
ServerNewsService.cs
GmApprovalService.cs
```

서버 흐름:

```text
게임 이벤트 발생
-> C# 서버 로직이 상태 계산
-> 원본 로그를 DB에 저장
-> 필요하면 LLM 작업 큐 등록
-> LLM 결과 도착
-> C# 서버가 검증
-> GM 승인 또는 자동 적용
-> 게임, 뉴스, 기록에 반영
```

서버가 직접 계산해야 하는 상태:

- 지역 위험도.
- 몬스터 점령도.
- 보스 생존 시간.
- 보스 성장 단계.
- 플레이어 전투 방식.
- 상인 습격 여부.
- NPC 이동 제한 여부.
- 마을 경제 상태.
- 경비병 증원 상태.
- 월드 이벤트 진행 여부.
- 기록 중요도.
- GM 승인 필요 여부.

LLM은 이 계산 결과를 이야기로 바꾼다. LLM이 상태를 판정하지 않는다.

## Local LLM Server

메인 PC는 로컬 LLM을 실행하는 보조 서버로 사용한다.

구성 후보:

```text
Ollama 또는 llama.cpp
LLM Worker
Qwen 중심 로컬 모델
```

모델 역할:

- Qwen: 한국어 창작, 보스 이름, 대사, 소문, 뉴스, 연대기, 카페 공지 초안.
- Mistral 계열: 전투 로그 요약, 공략 패턴 분류 보조, 이벤트 중요도 초안, JSON 구조화.
- Gemma: 빠른 요약, 짧은 GM 요약, 내부 태그 생성.

초기 MVP는 Qwen 단일 모델로 시작한다. 작업량과 속도 병목이 보이면 Mistral이나 Gemma를 보조 모델로 붙인다.

LLM 출력 규칙:

- JSON만 출력한다.
- 마크다운, 설명문, 주석을 출력하지 않는다.
- 서버가 제공한 스키마만 사용한다.
- 허용된 패턴 템플릿 목록 안에서만 제안한다.
- 수치, 보상, 드롭률, 스폰 수, 서버 명령을 생성하지 않는다.

## Monster Survival And Growth

핵심 문장:

```text
죽지 않은 몬스터는 성장한다.
```

모든 몬스터를 영구 저장하지 않는다. 다음 조건을 만족하는 의미 있는 후보만 추적한다.

- 전투에서 살아남았다.
- 도망쳤다.
- 플레이어를 처치했다.
- Elite 또는 Champion 후보가 되었다.
- Boss/Champion 주변 전투에 참여했다.
- 지역 위상 변화에 관여했다.

성장 흐름:

```text
Normal
-> Survivor
-> Elite
-> Champion
-> Boss
-> WorldBossCandidate
```

성장 점수 후보:

```text
growth_score =
  survival_score
+ combat_score
+ player_kill_score
+ escape_score
+ region_pressure_score
```

성장 조건:

- 생존 시간.
- 플레이어 처치 수.
- 지역 점령.
- 전투 횟수.
- 도망 성공.
- 그룹 전투 생존.
- 보스/Champion 주변 생존.
- 밤/날씨 같은 환경 조건.

예시 성장 라인:

```text
일반 고블린
-> 고블린 정찰병
-> 고블린 척후병
-> 고블린 전투대장
-> 붉은 송곳니 부족장
-> 북부의 고블린 왕
```

늑대:

```text
일반 늑대
-> 상처입은 늑대
-> 굶주린 늑대
-> 변이 늑대
-> 회색갈기 우두머리
-> 피묻은 갈퀴 로한
```

서버는 성장 여부와 실제 스탯/스폰/패턴을 결정한다. LLM은 성장 후 이름, 칭호, 소문, 대사, 역사 문장을 만든다.

## Random Elite And Boss Generation

일반 몬스터 중 일부는 월드 상태와 생존 기록에 따라 승급할 수 있다.

```text
Normal -> Elite -> Champion -> Boss
```

승급은 단순 랜덤이 아니라 다음 흐름을 따른다.

```text
플레이어 반복 행동
-> 지역 압력 변화
-> 몬스터 집단 반응
-> 이름 있는 위협 등장
-> 소문과 역사 기록 생성
```

등급 역할:

- Elite: 작은 변수, 이름, 약한 스탯 증가, 짧은 대사, 간단한 행동 변화.
- Champion: 지역 대표 위협, 파티 전투, 소문/뉴스, 1-2개 패턴 후보.
- Boss: 서버 이벤트급 위협, 지역 영향, GM 승인 가능, 2-4개 패턴 후보.
- WorldBossCandidate: GM 승인 필수, 카페/월드 뉴스/연대기 대상.

## Group AI

보스 주변의 같은 이름, 같은 종족, 같은 모델, 같은 지역 몬스터는 그룹으로 묶일 수 있다.

그룹화 우선순위:

1. 같은 보스 주변.
2. 같은 이름 또는 접두사.
3. 같은 종족.
4. 같은 모델.
5. 같은 지역.
6. 일정 거리 이내.

그룹 상태:

```text
Idle
Alert
Engaged
Reinforcing
Patrolling
Retreating
Collapsed
```

그룹 역할:

```text
Leader
Guard
Scout
Caller
Caster
Fodder
Fleeing
```

행동:

- 집단 어그로.
- 지원 요청.
- 보호 행동.
- 순찰.
- 플레이어 추격.
- 도주.
- 붕괴/해산.
- 상황 대사 출력.

안전 제한:

- 응답 몬스터 수 제한.
- 지원 요청 쿨다운.
- 초보 지역 약화.
- 마을/안전지대 끌고 오기 방지.
- 서버 틱 부하 제한.

## World Influence System

보스가 오래 살아남으면 보스는 단순 몬스터가 아니라 세계 사건이 된다.

영향 흐름:

```text
보스 생존 / 몬스터 승리
-> 지역 위험도 상승
-> NPC 이동 제한
-> 상인 습격
-> 마을 경제 불안
-> 경비병 증원
-> 신규 퀘스트 발생
-> 플레이어 개입
-> 지역 안정화
-> 월드 기록 생성
```

지역 위험도 단계:

```text
0-24: 안정
25-49: 불안정
50-74: 위험
75-100: 장악
```

세계 영향 예:

- NPC 이동 제한: 상인 마차, 전령, 순찰 NPC가 위험 지역을 피한다.
- 상인 습격: 보급 마차, 이동 상인, 보조 상인이 습격당한다.
- 특정 지역 위험화: 몬스터 순찰과 지원 요청이 증가한다.
- 마을 경제 변화: 지역 한정 보조 상점 가격이나 보급 상태가 소폭 변한다.
- 신규 퀘스트 생성: 토벌, 정찰, 회수, 호위, 방어, 복구 퀘스트가 생성된다.
- 경비병 증원: 마을이나 길목에 임시 경비병이 배치된다.

안전 제한:

- 필수 NPC와 초보자 필수 물품은 막지 않는다.
- 가격 변화는 제한적이고 지역 한정이다.
- 지역 영향은 시간 경과, 보스 처치, GM 초기화로 해제 가능하다.
- 보스 생존만으로 무한 강화하지 않는다.

## Player Strategy Learning

서버는 보스전과 중요 몬스터 전투에서 플레이어 공략 방식을 통계로 수집한다.

수집 항목:

- 원거리 비율.
- 독/지속 피해 비율.
- 카이팅 비율.
- 근접 피해 비율.
- 마법 피해 비율.
- 군중제어 사용량.
- 회복량.
- 전투 시간.
- 참여 인원.
- 사망자 수.
- 평균 거리.
- 반복 지형 사용 여부.
- 보스 처치/도주 여부.

분류 예:

```text
ArcherPressure
RangedKite
PoisonPressure
DotAttrition
BurstDamage
CrowdControlHeavy
LongAttrition
TerrainAbuseSuspected
```

허용 대응 후보:

- 궁수 우선 타겟.
- 짧은 돌진.
- 척후병 호출.
- 독 저항 획득.
- 독/디버프 일부 정화.
- 방어 자세.
- 힐러 압박.
- 본거지 복귀.
- GM 검토 알림.

핵심 원칙:

```text
보스는 플레이어를 완벽하게 카운터 치는 것이 아니라,
지난 전투를 기억한 것처럼 조금씩 대응한다.
```

지형 악용 의심은 자동 강화하지 않는다. GM 알림과 전투 로그 저장으로 처리한다.

## AI Boss Design System

서버가 보스 후보를 만들면 LLM은 그 보스를 캐릭터 있는 사건으로 설계한다.

서버 입력 예:

```json
{
  "requestType": "BossDesign",
  "serverName": "KDAOC",
  "language": "kr",
  "region": {
    "id": "camelot_hills_north",
    "name": "카멜롯 힐스 북부",
    "realm": "Albion",
    "dangerLevel": 72,
    "phase": "위험"
  },
  "monster": {
    "family": "Goblin",
    "baseName": "고블린",
    "rankCandidate": "Boss",
    "survivalHours": 8,
    "playerKills": 3,
    "encounterCount": 12,
    "escapedCount": 2,
    "growthReason": "오래 생존하고 플레이어를 처치함"
  },
  "combatMemory": {
    "dominantStrategy": "RangedKite",
    "secondaryStrategy": "PoisonPressure",
    "rangedDamageRatio": 0.68,
    "poisonDamageRatio": 0.28
  },
  "allowedDesign": {
    "maxNameLength": 24,
    "maxTitleLength": 32,
    "maxLineLength": 80,
    "allowedPatternTemplates": [
      "CallScout",
      "ShortCharge",
      "PoisonResistance"
    ],
    "forbiddenEffects": [
      "InstantKill",
      "PermanentCrowdControl",
      "FullImmunity",
      "InfiniteSummon",
      "RewardCreation"
    ],
    "allowNewReward": false,
    "requiresGMApproval": true
  }
}
```

LLM 출력 예:

```json
{
  "boss_name": "붉은 송곳니 그락",
  "personality": "aggressive",
  "personality_kr": "공격적이고 성급하며, 자신에게 도전한 적을 끝까지 추격하는 성격",
  "dialogue": "겁쟁이 궁수들!",
  "new_skill": "warcry_charge",
  "new_skill_kr": "전투 함성 돌격",
  "combat_style": "anti-ranged",
  "combat_style_kr": "원거리 견제형",
  "title": "북부 길목을 막은 자",
  "boss_rank": "Boss",
  "group_name": "붉은 송곳니 부족",
  "backstory": "그락은 물러서는 법을 모르는 고블린 우두머리다.",
  "intro_line": "내 길에 선 놈은 모두 물어뜯겠다!",
  "combat_lines": [
    "겁쟁이 궁수들!",
    "도망치지 마라!",
    "멀리 숨어도 소용없다!"
  ],
  "pattern_ideas": [
    {
      "name": "전투 함성 돌격",
      "template": "ShortCharge",
      "concept": "보스가 전투 함성을 지른 뒤 멀리 떨어진 대상을 향해 짧게 돌진한다."
    }
  ],
  "npc_rumor": "붉은 송곳니 그락은 활잡이와 마법사를 먼저 노린다더군요.",
  "world_news": "붉은 송곳니 그락이 원거리 전술에 적응하며 북부 길목의 모험가들을 위협하고 있습니다.",
  "chronicle": "붉은 송곳니 그락은 멀리서 쏘는 적들에게 반복해서 당한 뒤, 원거리 전술을 봉쇄하는 우두머리로 변해갔다."
}
```

서버는 LLM 출력을 그대로 믿지 않는다.

검증 순서:

```text
JSON 파싱
-> 스키마 검증
-> 필수 필드 검사
-> 금칙어/길이 검사
-> 실제 스킬 매핑
-> 수치 필드 제거
-> 밸런스 제한 검사
-> GM 승인 여부 판단
-> 서버 적용
```

## Pattern Template Mapping

LLM이 만든 스킬 컨셉은 실제 서버 템플릿에만 매핑한다.

매핑 예:

```text
warcry_charge     -> ShortCharge
call_scouts       -> CallScout
poison_resistance -> PoisonResistance
cleanse_poison    -> CleansePoison
pressure_archer   -> PressureArcher
defensive_stance  -> DefensiveStance
rally_minions     -> RallyMinions
return_to_camp    -> ReturnToCamp
```

템플릿 속성:

```text
template_id
allowed_boss_ranks
allowed_monster_families
cooldown_seconds
max_uses_per_fight
range_limit
effect_strength
requires_gm_approval
```

LLM이 수치나 보상을 넣으면 무시한다. 서버는 템플릿에 정의된 수치만 사용한다.

## Balance Limits

밸런스 원칙:

```text
보스는 적응하지만, 불공정해지면 안 된다.
```

등급 제한:

- Elite: 이름, 대사, 약한 행동 변화.
- Champion: 패턴 1개, 지역 소문.
- Boss: 패턴 1-2개, 지역 영향.
- WorldBoss: GM 승인 필수, 서버 뉴스와 카페 공지 후보.

금지 효과:

- 즉사.
- 완전 면역.
- 무한 소환.
- 영구 군중제어.
- 특정 직업 완전 봉쇄.
- 초보 지역 강한 적응.
- LLM 보상 생성.

수치 검증:

- 보스 체력 배율.
- 공격력 배율.
- 방어/저항 보정.
- 이동 속도.
- 돌진 거리.
- 소환 수.
- 소환 쿨다운.
- 패턴 사용 횟수.
- 패턴 지속 시간.
- 보상 배율.
- 경험치/RP/골드 지급량.
- 지역 위험도 변화량.
- 상점 가격 보정.

## AI Dialogue And Personality

LLM은 보스와 중요 NPC의 성격과 상황별 대사 묶음을 만든다. 전투 중 실시간으로 LLM을 호출하지 않는다.

성격 예:

```text
aggressive
cunning
vengeful
cowardly
proud
ancient
```

대사 슬롯:

```text
Idle
IdleDetect
AggroStart
Advantage
Pressure
LowHealth
Summoning
Poisoned
RangedPressure
Retreating
Returned
Remembering
FinalForm
Defeated
```

예:

```json
{
  "boss_name": "붉은 송곳니 그락",
  "personality": "aggressive",
  "dialogue_lines": {
    "IdleDetect": "인간이다! 죽여라!",
    "Remembering": "또 너희인가...",
    "FinalForm": "이 숲은 이제 내 왕국이다."
  }
}
```

서버 출력 규칙:

- 대사는 사전 생성해서 DB에 저장한다.
- 전투 중에는 저장된 대사만 출력한다.
- 같은 대사 반복을 방지한다.
- 대사별 쿨다운을 적용한다.
- 출력 범위를 주변, 지역, 월드로 구분한다.
- 플레이어 이름 직접 조롱과 운영자 사칭을 금지한다.

## Server History System

서버에서 발생한 중요한 사건은 원본 데이터와 사람이 읽기 좋은 역사 문장으로 남긴다.

기록 대상:

- 특정 보스 장기 생존.
- 도시 함락.
- 플레이어 레이드 성공.
- 월드 이벤트 발생.
- 상인 습격.
- 지역 안정화.
- 보급로 복구.
- 렐릭 이동.
- 성/타워 점령.
- 서버 최초 업적.
- GM 이벤트.

중요도:

```text
Minor: 짧은 로그만 저장.
Normal: 인게임 히스토리에 표시.
Major: 월드 뉴스와 대시보드 표시.
Legendary: 카페 공지와 연대기 후보.
```

기록 위치:

- DB 원본 기록.
- 도서관 NPC.
- 마을 게시판.
- 왕국 기록관.
- 서버 뉴스.
- 웹 대시보드.
- 네이버 카페 주간 연대기 초안.
- GM 관리 화면.
- 감사/디버그 로그.

정보 채널 역할:

- 게시판: 지금 할 일, 현재 위험, 짧은 공지.
- 도서관 NPC: 지난 사건 열람, 지역/보스별 기록.
- 왕국 기록관: 공식 역사, 렐름/월드 단위 기록.
- 서버 뉴스: 현재 서버에서 일어난 주요 소식.
- 카페 연대기: 유저 커뮤니티용 주간/월간 요약.

흐름:

```text
서버 사건 발생
-> 원본 이벤트 로그 저장
-> 중요도 판정
-> LLM 역사 문장 생성
-> 검증/GM 승인
-> 게시판/기록관/뉴스/카페 초안에 공개
```

## Data Model Candidates

초기 후보 테이블:

```text
world_region_state
monster_survivor
boss_memory
boss_design
boss_dialogue
world_event_log
chronicle_entry
server_news
llm_job
llm_result
gm_approval_request
```

`llm_job` 후보 필드:

```text
id
job_type
status
payload_json
attempt_count
last_error
created_at
updated_at
```

`llm_result` 후보 필드:

```text
id
job_id
status
result_json
validation_status
validation_errors
created_at
updated_at
```

`world_event_log` 후보 필드:

```text
id
event_type
importance
region_id
actor_type
actor_id
result
raw_data_json
public_text
gm_note
is_public
created_at
```

## Strictly Forbidden Designs

금지:

- LLM이 실시간 전투 전체를 직접 조종.
- LLM이 직접 몬스터 스폰.
- LLM이 직접 NPC 삭제/이동.
- LLM이 직접 아이템, 골드, RP, 경험치 지급.
- LLM이 직접 드롭률, 보스 스탯, 스킬 수치 결정.
- LLM이 직접 지역 위험도, 상점 가격, 퀘스트 완료 상태 변경.
- LLM이 직접 DB 수정.
- LLM이 직접 서버 명령 실행.
- LLM이 직접 계정 제재 판단.
- LLM이 GM 권한 행사.
- LLM 응답 실패 시 게임 로직 중단.
- 검증되지 않은 JSON 적용.
- LLM 출력 자동 카페 게시.
- 외부 LLM API에 민감한 서버 데이터 전송.

실시간 전투 LLM 조종을 금지하는 이유:

- 느림.
- 토큰 과다.
- 불안정.
- 반복 행동 문제.
- 서버 부하 증가.
- 디버깅 어려움.
- 밸런스 재현 불가능.

대신:

```text
전투 전: LLM이 이름, 성격, 대사, 패턴 컨셉 생성
전투 중: C# 서버 AI가 검증된 패턴 템플릿만 실행
전투 후: 서버가 통계 수집, LLM이 뉴스/역사/다음 학습 아이디어 생성
```

## MVP Rollout

1. 원본 이벤트 로그와 서버 뉴스/역사 문장 생성부터 만든다.
2. MariaDB 기반 `llm_job` / `llm_result` 큐를 만든다.
3. 메인 PC에서 Qwen 기반 LLM Worker를 돌린다.
4. JSON 스키마 검증과 금칙어/길이 검사를 붙인다.
5. 보스 대사/성격 사전 생성과 캐시를 적용한다.
6. 몬스터 생존 후보와 성장 점수 저장을 시작한다.
7. 보스 후보 설계안을 생성하되, 실제 패턴 적용은 비활성으로 둔다.
8. GM 승인 화면 또는 명령어로 적용 여부를 확인한다.
9. 검증된 패턴 템플릿을 Elite/Champion/Boss 순서로 제한 적용한다.
10. 지역 위험도, 상인 습격, 게시판/기록관/뉴스와 연결한다.

첫 구현 우선순위는 안전한 읽기/문장화 계층이다. 실제 전투 패턴과 경제 변화는 로그와 검증 체계가 안정된 뒤 붙인다.

## Acceptance Criteria

- LLM 서버가 꺼져도 OpenDAoC 서버가 정상 동작한다.
- LLM 작업은 비동기로 처리되고 게임 루프를 막지 않는다.
- LLM 출력은 JSON 스키마 검증을 통과해야만 적용된다.
- LLM이 만든 수치, 보상, 드롭률, 서버 명령은 무시되거나 차단된다.
- 보스 대사와 뉴스는 사전 생성/캐시 기반으로 출력된다.
- 서버 역사 기록은 원본 이벤트와 공개 문장을 분리해서 저장한다.
- World Boss, 도시 함락, 강한 경제 변화는 GM 승인 없이는 자동 적용되지 않는다.
- 플레이어는 인게임 또는 대시보드에서 최근 서버 사건을 확인할 수 있다.
