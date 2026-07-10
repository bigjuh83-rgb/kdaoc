# Continuous Dummy Growth Audit

`tools/run-dummy-growth-suite.py --continuous-progression`은 캐릭터를 레벨마다 재접속하지 않고 한 로그인 세션에서 자연스럽게 L1부터 목표 레벨까지 성장시킨다.

## 검증 범위

- 자연 레벨업과 레벨별 XP 증가
- 몹 골드와 Dynamic Quest 보상 골드
- 자동 루팅한 아이템과 수량
- 전문화 훈련 명령과 실제 spec 증가
- usable skill/spell 추가·소실
- 잡템 판매, affordable upgrade 구매, 장착
- Dynamic Quest 완료, 정확한 XP/copper 보상, 명시적 난이도 패스
- 솔로, 모든 구성원이 L1부터 성장하는 자연 파티, 실제 Companion Service 용병

Target class는 L1에 seed한다. 실제 class trainer를 통한 base-class 승급은 이 감사와 분리된 E2E 항목이다.

## 빠른 Live Smoke

WSL에서 표준 서버가 실행 중인 상태로 먼저 L2까지만 확인한다.

```bash
python3 tools/run-dummy-growth-suite.py \
  --continuous-progression \
  --realms alb \
  --party-sizes 1 \
  --max-level 2 \
  --run-dir tools/test-output/continuous-alb-solo-l2
```

실제 용병 smoke는 별도 run-dir에서 실행한다.

```bash
python3 tools/run-dummy-growth-suite.py \
  --continuous-progression \
  --continuous-mercenary \
  --realms alb \
  --party-sizes 1 \
  --max-level 2 \
  --parallel-cases 1 \
  --run-dir tools/test-output/continuous-alb-mercenary-l2
```

`OPENDAOC_API_PASSWORD`가 설정돼 있으면 supervisor와 Companion Service가 mutation API에 자동 전달한다. 설정이 없으면 non-dry live 실행에서 DB의 `ServerProperty.api_password`를 읽는다. 명령 metadata에는 비밀번호 대신 `***`만 기록한다.

## L1-L50 Matrix

솔로:

```bash
python3 tools/run-dummy-growth-suite.py \
  --continuous-progression \
  --realms alb,mid,hib \
  --party-sizes 1 \
  --max-level 50 \
  --run-dir tools/test-output/continuous-solo-l50
```

자연 파티:

```bash
python3 tools/run-dummy-growth-suite.py \
  --continuous-progression \
  --realms alb,mid,hib \
  --party-sizes 2,4 \
  --max-level 50 \
  --run-dir tools/test-output/continuous-party-l50
```

실제 용병:

```bash
python3 tools/run-dummy-growth-suite.py \
  --continuous-progression \
  --continuous-mercenary \
  --realms alb,mid,hib \
  --party-sizes 1 \
  --max-level 50 \
  --parallel-cases 1 \
  --run-dir tools/test-output/continuous-mercenary-l50
```

용병 mode는 owner 1명과 Companion Service가 request/claim/attach한 실제 용병 1명이다. 자연 p2와 같은 결과로 취급하지 않는다. 용병 계정도 L1에서 시작하고 매 레벨 별도 service status를 남긴다. 계약이 끝나면 linkdead/cooldown 정리 뒤 같은 성장 상태로 재고용한다.

## 레벨 체크포인트

Supervisor가 모든 추적 계정의 자연 레벨 증가를 API에서 확인하면 다음 순서로 진행한다.

1. 전투 중지와 target 정리
2. player reset API로 realm service 지점 이동
3. service NPC 관측과 상호작용 확인
4. account spec plan에 따른 `/train`
5. 계획된 junk가 있으면 merchant 이동 후 판매
6. 돈이 충분하면 계획된 장비 구매와 장착
7. API snapshot과 status JSON 기록
8. 다음 레벨 사냥 route로 복귀

서비스 체크포인트는 NPC 대화 확인을 자동 수락하지 않는다. 부상 상태에서 치료 기부 dialog를 수락해 훈련과 무관한 골드가 빠지는 일을 막고, Dynamic Quest 수락은 별도 coordinator가 소유한다.

두 레벨 이상을 polling 사이에 건너뛰거나, service status가 없거나, 훈련 후 spec이 늘지 않거나, 경제 delta가 설명되지 않으면 anomaly로 기록한다. 오류 severity는 기본적으로 fail-fast한다.

## Dynamic Quest

Dynamic Quest는 기본 활성화이며 `--no-continuous-dynamic-quests`로만 끌 수 있다. 최종 성장 감사에서는 켠 상태가 기준이다.

다음 조건은 정상 난이도 패스 후보이다.

- 목표 수가 `--continuous-dynamic-quest-max-target-count` 초과
- 최소 목표 레벨이 캐릭터 레벨 + 허용 delta 초과
- 목표가 다른 region이거나 허용 거리 초과
- target 이름/위치 누락
- failed node 또는 자동화하기 어려운 choice/NPC/world-signal/party-size 대기
- 목표별 node/progress timeout
- 파티 구성원의 quest objective 불일치

서버 cancel API가 실제 active progress를 1건 이상 취소한 뒤에만 `difficulty_skip`을 기록한다. API 실패, 취소 0건, Dynamic Quest 비활성화는 난이도 패스가 아니라 시스템 오류다.

`waiting_for_location`, `waiting_for_kill_credit`, `target_reached_waiting_for_transition`은 정상 진행 상태다. 자동수락 시작 범위는 모든 파티원이 실제 반경에 들어온 뒤에만 activation timeout을 시작하고, Explore 노드는 objective 좌표로 이동시킨다. 기본 진행 예산은 Explore 60초, Kill `60초 + 남은 목표당 30초`이며 전체 `--continuous-dynamic-quest-timeout`을 넘지 않는다.

## 산출물

- `continuous-timeline.csv`: 레벨별 XP, 골드, 드랍, spec, skill/spell, 상점 결과
- `dynamic-quest-timeline.csv`: accepted/progress/routed/completed/difficulty_skip과 정확한 보상
- `mercenary-timeline.csv`: request 상태, attach 거리, owner/mercenary level delta, XP, 골드, service delta, skill/spec 수
- `checkpoints/level-NN.json`: service 전후 원본 API snapshot과 owner status
- `anomaly-summary.json`: code별 count, 최대 표본 2개, 모델 라우팅
- `continuous-result.json`: case 최종 결과
- run root의 `continuous-summary.md`와 병합 CSV: 여러 realm/case 요약

## 모델 사용

정상 실행과 알려진 deterministic anomaly에는 모델을 호출하지 않는다. 반복 anomaly는 code별 count로 합치고 원본 행은 최대 20개만 요약에 둔다.

- `modelRouting.decision=none`: 모델 호출 없음
- `modelRouting.decision=small`: `smallModelInput`의 미분류 표본만 소형 모델에 전달
- 같은 미분류 이상이 반복되거나 서버 규칙/코드 수정 판단이 필요할 때만 강한 모델로 승격

원본 encounter/movement JSONL은 summary만으로 원인이 좁혀지지 않을 때 실패 시각 전후만 읽는다.

## 현재 상태

구조와 단위/회귀 테스트를 통과했다. 2026-07-10 live acceptance에서 ALB solo L1-L2, 실제 Companion Service 용병 L1-L2, 자연 p2 L1-L2가 모두 `ok=true`로 끝났다. 용병은 20,982 거리에서 사냥터로 합류해 파티 XP로 L2가 됐고 service money delta 0, Crush 1→2, usable skill 12→13을 기록했다. 자연 p2는 L1 AutoAccept quest를 실제 수락했으며 어려운 L2 spriggarn 목표를 90초 뒤 취소 확인하고 일반 사냥으로 복귀해 두 계정 모두 L2가 됐다. 실제 장시간 3렐름 L1-L50 acceptance matrix는 아직 실행하지 않았다.
