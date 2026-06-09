# OpenDAoC-Core Thread Starters

Copy one block into a new Codex thread when starting that topic.

## Control Thread

```text
OpenDAoC-Core 총괄 스레드다.

역할:
- 전체 우선순위 결정
- 작업 스레드 분배
- Codex subagent 사용 판단
- 최종 보고 취합
- Cursor/Antigravity는 Codex 할당량 부족 시에만 외주처럼 사용

운영 원칙:
- 실제 구현 로그와 긴 테스트 로그는 주제별 스레드에 둔다.
- 이 스레드는 결정, 지시, 최종 보고만 담당한다.
- 서버 시작/재시작은 start-main-server-visible.bat만 표준으로 사용한다.
- API 키/토큰/비밀번호는 절대 출력하거나 문서에 쓰지 않는다.

참고 파일:
- CODEX_THREAD_OPERATING_GUIDE.md
```

## Companion System Thread

```text
OpenDAoC-Core 용병 시스템 전용 스레드다.

범위:
- 용병 고용관
- live companion service
- 용병 명령/대사
- 역할별 행동
- 실제 플레이어 + 용병 파티
- LiteLLM 기반 대화 시스템

현재 정책:
- 플레이어 노출 명칭은 "용병"다.
- "dummy"는 내부 코드/테스트 용어로만 유지한다.
- 플레이어 slash command는 만들지 않는다.
- /dummy는 GM 테스트 명령으로만 유지한다.
- Cursor/Antigravity는 Codex 할당량 부족 시에만 사용한다.

주요 파일:
- tools/dummy-companion-service.py
- tools/behavior-dummy-client.py
- tools/run-live-companion-party-smoke.py
- tools/run-live-companion-player-driver-smoke.py
- tools/companion-dialogue-pools.json
- GameServer/API/DummyCompanion/*
- GameServer/commands/gmcommands/dummy.cs

최근 완료:
- player-command-modes smoke PASS
- player-command-all-roles smoke PASS
- 성격별/상황별 대사풀 확장
- 대사풀 깊이 테스트 추가

다음 후보:
- 용병 서비스 서버 시작 연동 안정화
- 고용관 UX 최종 점검
- 실제 플레이어 합류 시 용병 해산/역할 우선순위 확인
```

## Movement And Rewind Thread

```text
OpenDAoC-Core 이동/되감기 전용 스레드다.

범위:
- 용병/더미 이동
- Z값 공중부양
- 되감기
- 순간이동
- follow/catchup/teleport 정책
- movement audit 로그

원칙:
- 서버 movement tuning은 함부로 바꾸지 않는다.
- 서버 권위 로그와 dummy client movement jsonl로 원인을 먼저 확정한다.
- 비전투 장거리 이탈은 2500 이상부터 teleport 허용 가능하다.
- 전투 중 teleport/catchup speed는 금지한다.
- 이동 중에는 리더에게 최대한 가깝게 붙는다.

주요 파일:
- tools/headless-daoc-client.py
- tools/behavior-dummy-client.py
- tools/run-multi-dummy-movement-session.py
- GameServer/packets/Client/168/PlayerPositionUpdateHandler.cs
- GameServer/packets/Client/168/PlayerHeadingUpdateHandler.cs
- GameServer/packets/Server/PacketLib168.cs

최근 확인:
- 48896 점프는 packet speed/world speed 혼용이 유력 원인이었다.
- Z값/되감기 체감 문제가 아직 남아 있다.

다음 후보:
- movement-command smoke 추가
- 따라와/대기/여기로/소환 이동만 별도 검증
- movement audit와 client movement jsonl 자동 요약
```

## Combat AI And FSM Thread

```text
OpenDAoC-Core 전투 AI/FSM 전용 스레드다.

범위:
- behavior-dummy-client.py FSM
- hostile target gate
- travel aggro/drop aggro/recover
- 도주
- 힐/부활/해제
- CC/메즈/스턴
- 클래스별 스킬 사용

원칙:
- 편법 사냥터 변경으로 문제를 숨기지 않는다.
- 사람처럼 행동하는 AI가 목표다.
- 같은 문제가 반복되면 중앙 gate/policy/test로 고정한다.

주요 파일:
- tools/behavior-dummy-client.py
- tools/test_behavior_player_follow.py

최근 상태:
- FSM skeleton과 target gate skeleton이 들어갔다.
- 용병 명령 모드도 command mode로 정리되었다.
- healer/tank/dps/support 기본 역할 행동 smoke가 있다.

다음 후보:
- 클래스별 스킬/마법 사용 테이블 점검
- 힐러 어그로 시 파티원 중심 회피/구조 요청 개선
- CC/메즈/스턴 사용 조건 테스트 강화
```

## Growth Test Thread

```text
OpenDAoC-Core 성장 테스트 전용 스레드다.

범위:
- L1-L50 성장
- train 단계
- 장비 교체
- 아이템/골드/판매
- 사망 후 회복
- 파티/보스
- 성장몹 회귀

원칙:
- 테스트를 무작정 오래 돌리지 않는다.
- 소스/DB/로그로 예측 가능한 조건을 먼저 체크한다.
- 단일 실패 재현 -> 로그 원인 확정 -> 단위 테스트 -> 단일 재검증 -> 축소 매트릭스 -> 전체 매트릭스 순서로 진행한다.

주요 파일:
- tools/run-dummy-growth-suite.py
- tools/summarize-dummy-growth-run.py
- tools/test_dummy_growth_suite.py

최근 완료:
- growth-stage preset 추가
- summarize-dummy-growth-run.py 추가
- 기존 unittest/py_compile/server fast check 통과 이력 있음

다음 후보:
- 레벨별 사냥터 DB 기반 사전 산출
- L1/L6/L10 체크포인트 빠른 회귀
- L50 파티 보스 이후 RvR로 연결
```

## RvR And Frontier Thread

```text
OpenDAoC-Core RvR/프론티어 전용 스레드다.

범위:
- 3렐름 RvR smoke
- frontier 지역
- 성/공성
- 적 렐름 타겟팅
- 용병 RvR 기여 제한
- RP/kill credit 정책

원칙:
- 용병은 파티원이나 같은 렐름 아군을 hostile target으로 잡으면 안 된다.
- PvE 보상은 플레이어 우선이다.
- RvR 보상은 별도 제한/마커 정책으로 추적한다.

주요 파일:
- tools/behavior-dummy-client.py
- tools/run-live-companion-role-matrix.py
- RvR 관련 smoke/script 추가 예정

다음 후보:
- 3렐름 smoke 기본 골격
- realm target safety 테스트
- companion reward marker 정책 문서화
```

## Korean Client UI Thread

```text
KDAOC/OpenDAoC 클라이언트 한글화 전용 스레드다.

범위:
- UI font fallback
- @ 대체문자
- assets.xml font alias
- Gulim/Charset 129
- KoreanGothic.ttf 중복 정의

원칙:
- 이번 범위가 아니면 game.dll, glyph warmup, 0x488b8e 패치는 건드리지 않는다.

주요 파일:
- ui/custom/assets.xml
- ui/atlantis/assets.xml
- ui/isles/assets.xml

최근 작업:
- arial9/arial11/font_memo/Font_Memo alias 점검 및 한글 UI용 GdiFont/Gulim/Charset 129 방향으로 정리.

다음 후보:
- 사용자 클라이언트 재시작 후 @ 글리프 재확인
- 남는 alias 중복 제거
```

## Operations And API Thread

```text
OpenDAoC-Core 운영/인프라/API 전용 스레드다.

범위:
- WSL 안정화
- 서버 시작/재시작
- 용병 서비스 자동 시작
- LiteLLM
- OpenAI/Gemini API 무료 한도
- API 키 보안

원칙:
- API 키/토큰/비밀번호는 절대 출력하거나 커밋하지 않는다.
- paid API 사용은 무료 한도 초과 가능성이 있으면 중단한다.
- 서버 시작/재시작은 start-main-server-visible.bat만 표준이다.
- 서버 확인은 tools/check-main-server-fast.sh 또는 check-main-server-fast.bat로 한다.

주요 파일:
- start-main-server-visible.bat
- start-live-companion-service-visible.bat
- tools/start-main-visible-server.sh
- tools/start-live-companion-service.sh
- tools/opendaoc-ai-gateway.py
- tools/opendaoc-ai-gateway.json

다음 후보:
- 서버 API 준비 전 companion service가 Connection refused로 죽지 않게 retry/wait 추가
- LiteLLM config secret loading 점검
- API 무료 한도 guardrail 테스트
```
