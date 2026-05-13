# Headless/Behavior Dummy Client

OpenDAoC 서버를 실제 DAoC 클라이언트 UI 없이 접속 테스트하기 위한 도구다.

이 도구는 게임 클라이언트 파일을 실행하지 않고 TCP 패킷으로 로그인, 캐릭터 선택, 월드 진입, 주변 NPC 수집, 타겟 지정, 공격 모드, 명령 전송을 수행한다. 서버 입장에서는 일반 클라이언트가 접속한 것처럼 보이므로 스모크 테스트와 부하 테스트에 사용할 수 있다.

## 파일

- `tools/headless-daoc-client.py`: 단일 캐릭터 접속과 명령 전송용 최소 클라이언트.
- `tools/behavior-dummy-client.py`: 여러 더미를 띄워 핑, 방향 전환, 타겟 해제, 명령 전송을 반복하는 행동형 더미.
- `tools/provision-dummy-accounts.py`: 기존 캐릭터를 템플릿으로 더미 계정과 캐릭터를 DB에 생성하는 도구.
- `tools/worldai-smoke-test.py`: WorldAI, MobGrowth, 공개 API를 한 번에 확인하는 서버 스모크 테스트.
- `tools/dummy-accounts.example.csv`: 여러 계정 테스트용 CSV 예시.

## WorldAI/API 스모크 테스트

서버가 켜져 있고 `atlas_api=True`이면 아래 명령으로 WorldAI, MobGrowth, 대시보드 API를 한 번에 확인할 수 있다.

```bash
OPENDAOC_PASSWORD='PASSWORD' python3 tools/worldai-smoke-test.py \
  --require-api \
  --mob-scan 50
```

성공 기준:

- 샘플 월드 이벤트가 기록된다.
- fake LLM 작업이 완료되고 검증 결과가 저장된다.
- `/api/world/news`, `/api/world/events`, `/api/live`가 응답한다.
- MobGrowth 상태가 DB에 기록된다.

## 단일 접속 스모크 테스트

```bash
python3 tools/headless-daoc-client.py \
  --username bigjuh \
  --password 'PASSWORD' \
  --realm 1 \
  --char-index 0 \
  --command '/mobgrowth status' \
  --command '/worldai jobs' \
  --hold 5
```

성공하면 서버 로그에 `Incoming connection`, `logging on`, `entering Region` 로그가 찍힌다.

주변 NPC 패킷 수집을 확인하려면:

```bash
python3 tools/headless-daoc-client.py \
  --username dummy001 \
  --password dummy-pass \
  --realm 1 \
  --char-index 0 \
  --hold 3 \
  --show-npcs
```

성공하면 `npc oid=... level=... name=...` 형식으로 서버가 보낸 NPC 목록이 출력된다.

주변 플레이어 생성 패킷 수집을 확인하려면 `--show-players`를 함께 쓴다.

```bash
python3 tools/headless-daoc-client.py \
  --username dummy001 \
  --password dummy-pass \
  --realm 1 \
  --char-index 0 \
  --hold 5 \
  --show-players
```

성공하면 `player oid=... level=... realm=... name=...` 형식으로 같은 시야권에 들어온 플레이어 목록이 출력된다.

## 행동형 더미 테스트

```bash
python3 tools/behavior-dummy-client.py \
  --hold 60 \
  --ping-interval 10 \
  --turn-interval 5 \
  --command-interval 30 \
  --clear-target-interval 15
```

기본 명령은 다음 3개다.

- `/mobgrowth status`
- `/worldnews`
- `/worldai jobs`

명령 없이 순수 접속 유지만 테스트하려면:

```bash
python3 tools/behavior-dummy-client.py --hold 60 --command ''
```

## 여러 계정 부하 테스트

동시 접속은 계정 수만큼만 가능하다. 같은 계정으로 여러 더미를 동시에 접속시키면 기존 접속이 끊기거나 로그인이 실패할 수 있다.

더미 계정은 템플릿 계정/캐릭터를 복제해서 만든다. 알비온 캐릭터의 DB 슬롯은 `100`번대여야 하고, CSV의 `char_index`는 클라이언트가 보는 첫 번째 캐릭터라서 `0`으로 둔다.

```bash
python3 tools/provision-dummy-accounts.py \
  --count 6 \
  --replace \
  --password dummy-pass \
  --csv tools/dummy-accounts.csv
```

AI 플레이어용으로 눈에 보이는 캐릭터명을 자연스럽게 만들려면:

```bash
python3 tools/provision-dummy-accounts.py \
  --count 12 \
  --replace \
  --password dummy-pass \
  --character-name-mode natural \
  --csv tools/ai-accounts.csv
```

직접 이름 풀을 주려면 `|`로 구분한다.

```bash
python3 tools/provision-dummy-accounts.py \
  --count 4 \
  --replace \
  --character-name-mode natural \
  --character-names '가온|라온|이든|하람' \
  --csv tools/ai-accounts.csv
```

`tools/dummy-accounts.csv`에는 테스트용 비밀번호가 그대로 들어간다. 로컬 테스트용으로만 쓰고 공개 저장소에는 실제 운영 계정 정보를 넣지 않는다.

CSV 형식:

```csv
username,password,realm,char_index
dummy001,password1,1,0
dummy002,password2,1,0
dummy003,password3,2,0
```

실행 예시:

```bash
python3 tools/behavior-dummy-client.py \
  --accounts tools/dummy-accounts.csv \
  --concurrency 50 \
  --hold 300 \
  --ramp-up 60 \
  --ping-interval 15 \
  --turn-interval 8 \
  --command-interval 45 \
  --clear-target-interval 20 \
  --jitter 2.0
```

짧은 로컬 검증 예시:

```bash
python3 tools/behavior-dummy-client.py \
  --accounts tools/dummy-accounts.csv \
  --concurrency 3 \
  --hold 20 \
  --ramp-up 4 \
  --ping-interval 5 \
  --turn-interval 3 \
  --clear-target-interval 7 \
  --command '' \
  --jitter 0.5 \
  --tick 0.05
```

성공하면 서버 로그에 각 더미 계정의 `entering Region` 로그가 찍히고, 연결 종료 시 `state:Playing`으로 링크데드 처리된다.

## 전투형 더미 테스트

`--combat`을 켜면 더미가 서버에서 받은 `NPCCreate` 패킷을 바탕으로 가까운 NPC 후보를 기억하고, 주기적으로 타겟 지정과 공격 모드 패킷을 보낸다. `--move`까지 켜면 선택한 NPC 쪽으로 위치 갱신 패킷을 보내며 접근한다.

```bash
python3 tools/behavior-dummy-client.py \
  --accounts tools/dummy-accounts.csv \
  --concurrency 3 \
  --hold 25 \
  --ramp-up 4 \
  --ping-interval 5 \
  --turn-interval 0 \
  --combat \
  --move \
  --combat-interval 1.8 \
  --target-pool 3 \
  --attack-range 400 \
  --move-step 450 \
  --clear-target-interval 10 \
  --command '' \
  --jitter 0.2 \
  --tick 0.05
```

전투형 옵션:

- `--combat`: 주변 NPC 타겟/공격 모드 루프를 켠다.
- `--combat-interval`: 타겟/공격 루프 주기.
- `--target-pool`: 가까운 NPC N개 중 무작위 선택.
- `--include-peace-npcs`: 평화 NPC까지 타겟 후보에 포함한다. 기본은 제외.
- `--interact`: 공격 전 상호작용 패킷도 보낸다.
- `--move`: 선택한 NPC를 향해 1.127 위치 갱신 패킷을 보낸다.
- `--move-step`: 한 번에 이동시키는 좌표 거리.
- `--attack-range`: 이 거리 안에 들어오면 공격 모드를 켠다.

더미는 서버의 `CheckLOSRequest`에도 자동으로 성공 응답을 보낸다. NPC 원거리 공격이나 시야 체크가 들어와도 LoS 타임아웃 로그가 쌓이지 않도록 하기 위해서다.

전투형 더미는 기본값으로는 “사냥 흉내 부하” 검증용이다. 더 실제 유저처럼 움직여야 하는 시나리오는 아래 graph pathing 옵션을 함께 사용한다.

## Graph Pathing

`--nav-api-url`을 주면 더미는 먼저 서버의 `/api/dummy/nav/path`에 경로를 요청한다. 이 API는 서버가 로드한 zone navmesh와 `PathfindingProvider`를 사용하므로, navmesh가 있는 지역에서는 실제 서버 지형 판정에 가까운 경로를 받는다. navmesh가 없거나 API가 실패하면 `--path-graph`의 region별 waypoint graph로 자동 fallback한다. 둘 다 실패하면 더미는 목표로 직선 순간이동하지 않고 정지한다.

nav API 응답의 `snappedStart`, `snappedEnd`, `floor`, `lineOfSight`도 보존한다. 더미는 snapped start/end를 경로 경유점으로 반영하고, API가 경로 노드 없이 snapped end만 돌려줄 때는 `lineOfSight=true`인 경우에만 직접 이동 후보로 인정한다.

`--nav-segment-validate`는 각 waypoint/nav point로 이동하기 직전에 현재 위치에서 다음 지점까지의 짧은 segment를 nav API로 다시 확인한다. segment 검증이 실패하면 더미는 이동하지 않고 route를 버린 뒤 다음 replan까지 대기한다. API 부하가 문제 되는 대규모 테스트에서는 `--no-nav-segment-validate`로 끌 수 있다.

`--path-graph`만 주는 경우에도 더미는 목표 좌표로 곧장 직선 이동하지 않고 region별 waypoint graph 위에서 A* 경로를 먼저 계산한다. 이동 중에는 다음 graph 노드까지만 한 스텝씩 움직이고, 목표와 충분히 가까운 `last mile` 구간에서만 짧은 직접 이동을 허용한다.

```bash
python3 tools/behavior-dummy-client.py \
  --accounts tools/dummy-accounts.csv \
  --concurrency 3 \
  --hold 120 \
  --hunter \
  --smooth-movement \
  --path-graph tools/pathing/regions/albion-lowlevel.json \
  --path-region 1 \
  --path-last-mile-distance 450 \
  --path-node-arrival-distance 160
```

graph JSON은 `regions -> regionId -> nodes/edges/collisions` 구조를 쓴다. edge나 collision에 `wall`, `cliff`, `water`, `closed_door`, `keep_door` 같은 플래그를 달면 기본적으로 지나가지 않는다. 필요할 때만 `--path-allow-water`, `--path-allow-closed-door`, `--path-allow-keep-door`, `--path-allow-cliff`로 허용한다. 높이 차이는 `--path-max-height-delta`, edge 길이는 `--path-max-edge-length`, graph 노드 탐색 반경은 `--path-max-node-distance`로 제한한다.

현재 포함된 샘플 graph는 `tools/pathing/regions/albion-lowlevel.json`이며, `newbie-solo`, `solo-melee`, `ai-pve-casual`, `ai-filler-casual` 시나리오는 이 graph를 자동으로 사용한다. graph는 전체 DAoC 지형 파일을 파싱한 완전 navmesh가 아니라, 운영자가 안전한 이동 노드를 직접 늘려가는 seed 데이터다. 서버 navmesh가 준비된 지역은 `--nav-api-url http://127.0.0.1:5000`처럼 API를 켜고 쓰면 되고, navmesh가 없는 지역은 graph를 계속 보강한다.

## 밸런스 측정 지표

행동형 더미는 전투 중인 대상이 서버의 object remove 패킷으로 사라지면 `target_removed`로 기록한다. 이 값은 “처치 추정”이다. 플레이어가 죽으면 `player_death`, 같은 대상을 너무 오래 잡고 있으면 `target_timeout`, 라운드 종료까지 대상이 남아 있으면 `round_end`로 기록한다.

`--metrics-csv`와 `--report-md`를 함께 쓰면 계정/라운드별 전투 수, 처치 추정 수, 사망 수, 타임아웃 수, 평균 처치 시간을 남긴다. 리포트의 `Balance Metrics`와 `Target Summary` 섹션은 몬스터별 위험도와 처치 시간을 빠르게 비교하기 위한 요약이다.
`--combat-csv`를 함께 쓰면 전투 단위 상세 행을 따로 저장한다. 각 행에는 계정, 라운드, 대상 이름/레벨, 결과, 지속 시간, 공격/스킬 시도 횟수, 시작/종료 거리가 들어간다.

```bash
python3 tools/behavior-dummy-client.py \
  --accounts tools/dummy-accounts.csv \
  --concurrency 3 \
  --hold 120 \
  --behavior-profile solo-melee \
  --metrics-csv tools/reports/balance/metrics.csv \
  --combat-csv tools/reports/balance/combat.csv \
  --report-md tools/reports/balance/report.md
```

현재 지표는 서버가 클라이언트에 보내는 패킷 기준이라 정확한 DPS 미터가 아니다. 밸런스 1차 판단에는 `처치 추정 수`, `플레이어 사망 수`, `평균 처치 시간`, `타임아웃 수`를 같이 본다.

## 초보 사냥형 Hunter 모드

`--hunter`는 전투형 더미를 조금 더 유저처럼 움직이게 하는 모드다. 주변 NPC 중 레벨 조건에 맞는 대상을 고르고, 가까워질 때까지 이동한 뒤 공격 모드를 켠다. 대상이 오래 잡히지 않으면 포기하고 다른 대상을 찾으며, 가끔 쉬거나 주변을 배회한다.

`--use-skills`를 함께 켜면 공격 사거리 안에서 `UseSkill` 패킷도 보내므로, 서버의 스타일/능력 사용 처리까지 같이 부하에 포함된다. `--auto-release-on-death`는 서버의 `PlayerDeath` 패킷을 감지해 공격을 멈추고 `/release`를 보낸다. `--recovery`는 사냥 중 가끔 `/release` 또는 `/pray`를 보내 사망 복구 행동을 흉내낸다. 살아있을 때는 서버가 “죽지 않았다” 같은 메시지를 돌려줄 수 있지만, 의도적으로 회복 명령 경로를 같이 태우기 위한 옵션이다.

```bash
python3 tools/provision-dummy-accounts.py \
  --start 10 \
  --count 9 \
  --replace \
  --password dummy-pass \
  --csv tools/dummy-accounts.csv

python3 tools/behavior-dummy-client.py \
  --accounts tools/dummy-accounts.csv \
  --concurrency 3 \
  --hold 45 \
  --ramp-up 4 \
  --ping-interval 5 \
  --turn-interval 0 \
  --hunter \
  --player-level 1 \
  --min-target-level 1 \
  --max-target-level-delta 3 \
  --target-timeout 12 \
  --combat-interval 1.6 \
  --target-pool 4 \
  --attack-range 400 \
  --move-step 360 \
  --use-skills \
  --skill-interval 3 \
  --skill-indexes 0,1,2 \
  --skill-type 1 \
  --auto-release-on-death \
  --death-release-delay 2 \
  --death-recovery-cooldown 8 \
  --post-release-rest 3 \
  --recovery \
  --recovery-interval 20 \
  --rest-chance 0.10 \
  --rest-min 1 \
  --rest-max 2.5 \
  --think-min 0.2 \
  --think-max 0.8 \
  --command '' \
  --jitter 0.2 \
  --tick 0.05 \
  --metrics-csv tools/dummy-hunter-metrics.csv \
  --report-md tools/dummy-hunter-report.md
```

Hunter 옵션:

- `--hunter`: `--combat`, `--move`, `--wander`를 함께 켠다.
- `--player-level`: 더미 캐릭터의 기준 레벨. 서버에서 직접 읽는 값이 아니라 타겟 필터용 기준값이다.
- `--ideal-target-level`: 점수 기반 타겟 선택에서 선호하는 몬스터 레벨. `0`이면 `--player-level`을 쓴다.
- `--min-target-level`: 이 레벨보다 낮은 NPC는 무시한다.
- `--max-target-level-delta`: `player-level + delta`보다 높은 NPC는 무시한다.
- `--max-target-distance`: 이 거리보다 먼 NPC는 무시한다. `0`이면 거리 제한을 끈다.
- `--target-selection`: `smart`, `nearest`, `random` 중 하나. `smart`는 레벨 적합도, 거리, 선호/회피 이름을 점수화한다.
- `--target-level-weight`, `--target-distance-weight`, `--target-randomness`: `smart` 타겟 점수 계산의 레벨/거리/무작위 가중치.
- `--prefer-target-name`, `--avoid-target-name`: 쉼표로 구분한 이름 조각. 특정 몹을 우선하거나 아예 피할 때 쓴다.
- `--target-timeout`: 같은 타겟을 이 시간 안에 해결하지 못하면 포기하고 다른 타겟을 찾는다.
- `--target-failure-cooldown`: 타임아웃된 타겟을 다시 고르지 않는 시간.
- `--stick-to-target-chance`: 현재 타겟이 보이면 계속 붙잡고 싸울 확률. 높을수록 실제 유저처럼 한 대상을 오래 친다.
- `--wander-step`: 사냥 대상이 없을 때 주변을 배회하는 좌표 거리.
- `--rest-chance`, `--rest-min`, `--rest-max`: 사냥 중 잠깐 쉬는 행동의 확률과 시간.
- `--think-min`, `--think-max`: 행동 사이의 짧은 판단 지연. 너무 낮추면 더미가 기계적으로 빠르게 움직인다.
- `--position-heartbeat-interval`: 제자리 대기 중에도 위치 패킷을 보내는 주기. 서버는 마지막 위치 패킷 기준으로 소프트 링크데드를 판단하므로 기본값 3초를 유지하는 것이 좋다.
- `--flee-health-percent`: 체력이 이 값 이하로 떨어지면 공격을 끊고 후퇴한다. `0`이면 비활성화다.
- `--flee-duration`, `--flee-step`, `--flee-move-interval`: 후퇴 시간, 이동 거리, 후퇴 이동 주기.
- `--use-skills`: 공격 사거리 안에서 스킬/스타일 사용 패킷을 보낸다.
- `--action-rotation`: `auto`, `melee-basic`, `melee-burst`, `caster-basic`, `healer-support`, `hybrid`, `none` 중 하나. 역할별로 UseSkill/UseSpell 패킷을 다르게 보낸다.
- `--skill-interval`: 스킬/스타일 버튼을 누르는 주기.
- `--skill-indexes`: 더미가 누를 `UseSkill` 인덱스 목록. 예: `0,1,2`.
- `--skill-type`: `UseSkill`의 type 바이트. 기본값 `1`은 전문화 항목을 건너뛴 사용 가능 스킬 목록을 대상으로 한다.
- `--spell-levels`, `--spell-line-index`, `--spell-range`: caster/hybrid 로테이션에서 사용할 주문 레벨, 주문 라인, 사거리.
- `--heal-spell-levels`, `--heal-spell-line-index`, `--healer-self-health-percent`: healer-support 로테이션의 자가 회복 시도 조건.
- `--support-spell-chance`, `--hybrid-melee-chance`: 지원 주문/하이브리드 근접 행동 확률.
- `--auto-release-on-death`: `PlayerDeath` 패킷 또는 체력 0 상태를 감지하면 `/release`를 보낸다.
- `--death-release-delay`: 죽음 감지 후 `/release`까지 기다리는 시간.
- `--death-recovery-cooldown`: 죽은 상태에서 `/release`를 반복 시도하는 최소 간격.
- `--post-release-rest`: 부활 패킷을 받은 뒤 다시 행동하기 전 쉬는 시간.
- `--recovery`: 사망 복구 흉내를 위해 가끔 `/release` 또는 `/pray` 명령을 보낸다.
- `--recovery-interval`: 복구 명령을 시도하는 주기.
- `--metrics-csv`: 계정/라운드별 결과와 액션별 카운트를 CSV로 저장한다.
- `--report-md`: 성공률, 총 액션, 액션 분포, 라운드 결과를 마크다운 리포트로 저장한다.

행동 프리셋:

- `--behavior-profile solo-melee`: 기본 근접 솔플러. 사냥, 이동, 스킬 사용, 사망 후 release를 켠다.
- `--behavior-profile cautious-solo`: 신중한 솔플러. 낮은 체력에서 후퇴하고, 높은 레벨 대상을 덜 건드린다.
- `--behavior-profile pve-casual`: 생활형 PvE AI 플레이어. 사냥, 배회, 휴식, 판단 지연, 낮은 체력 후퇴를 섞는다.
- `--behavior-profile party-tank`: 파티 리더/탱커에 가까운 행동. 타겟을 오래 유지한다.
- `--behavior-profile party-dps`: 파티 딜러에 가까운 행동. 스킬 사용 주기가 더 짧다.
- `--behavior-profile custom`: 직접 지정한 옵션만 쓴다.

액션 로테이션:

- `melee-basic`: 공격 사거리 안에서 기본 UseSkill을 누른다.
- `melee-burst`: 더 공격적인 근접 스타일. 리포트에는 `burst_skill`로 기록된다.
- `caster-basic`: 주문 사거리 안에서 UseSpell을 보낸다.
- `healer-support`: 체력이 낮으면 자가 회복 주문을 시도하고, 가끔 지원 주문을 보낸다.
- `hybrid`: 근접 거리에서는 UseSkill, 주문 거리에서는 UseSpell을 섞는다.
- `auto`: 행동 프리셋과 파티 슬롯에 따라 자동 선택한다.

빠르게 반복해서 돌릴 때는 이전 계정이 링크데드 상태로 남을 수 있다. 위 예시처럼 `--start`를 바꿔 새 더미 계정 범위를 만들거나, 반복 테스트에서는 `--fresh-account-per-round`를 사용한다.

## 파티형 더미 테스트

`--party-size`가 2 이상이면 더미를 `party-size` 단위로 묶는다. 각 묶음의 첫 번째 계정이 리더가 되고, 나머지는 추종자가 된다.

리더는 주기적으로 파티원에게 `/invite`를 보내고, 자신의 위치와 현재 타겟을 같은 프로세스의 추종자에게 공유한다. 추종자는 그룹 초대 수락 패킷을 보내고, 리더 위치를 따라가며, 리더 타겟을 직접 지정하거나 `/assist 리더명`을 보내 같은 대상을 공격한다.

```bash
python3 tools/provision-dummy-accounts.py \
  --start 40 \
  --count 3 \
  --replace \
  --password dummy-pass \
  --csv tools/dummy-accounts.csv

python3 tools/behavior-dummy-client.py \
  --accounts tools/dummy-accounts.csv \
  --concurrency 3 \
  --party-size 3 \
  --hold 35 \
  --ramp-up 3 \
  --ping-interval 5 \
  --turn-interval 0 \
  --hunter \
  --player-level 1 \
  --min-target-level 1 \
  --max-target-level-delta 3 \
  --target-timeout 10 \
  --combat-interval 1.6 \
  --target-pool 4 \
  --attack-range 400 \
  --move-step 340 \
  --use-skills \
  --skill-interval 3 \
  --skill-indexes 0,1,2 \
  --skill-type 1 \
  --party-invite-interval 6 \
  --party-accept-interval 3 \
  --party-assist-interval 3 \
  --party-follow-interval 1.2 \
  --party-follow-step 320 \
  --party-follow-distance 500 \
  --party-use-assist-command \
  --rest-chance 0.05 \
  --rest-min 1 \
  --rest-max 2 \
  --think-min 0.2 \
  --think-max 0.7 \
  --command '' \
  --jitter 0.2 \
  --tick 0.05 \
  --metrics-csv tools/dummy-party-metrics.csv \
  --report-md tools/dummy-party-report.md
```

파티 옵션:

- `--party-size`: 리더 1명과 추종자 N명을 묶는 크기. 예: `3`이면 1리더 + 2추종자.
- `--party-invite-interval`: 리더가 파티 초대를 반복하는 주기.
- `--party-accept-interval`: 추종자가 그룹 초대 수락 패킷을 보내는 주기.
- `--party-assist-interval`: 추종자가 리더 타겟을 따라잡는 주기.
- `--party-follow-interval`: 추종자가 리더 위치를 따라가는 주기.
- `--party-follow-step`: 추종자가 한 번에 이동하는 좌표 거리.
- `--party-follow-distance`: 리더와 이 거리 안이면 제자리 유지로 본다.
- `--party-state-max-age`: 리더 위치 정보가 이 시간보다 오래되면 추종자가 따라가지 않는다.
- `--party-use-assist-command`: 공유 타겟 지정 외에 `/assist 리더명` 명령도 함께 보낸다.
- `--party-role-strategy`: `mixed`면 파티 슬롯에 따라 근접/버스트/지원 로테이션을 섞고, `same`이면 모두 같은 로테이션을 쓴다.

리포트에서는 `party_invite`, `party_accept`, `party_assist`, `party_assist_command`, `party_follow`, `party_hold` 액션 카운트로 파티 동작을 확인한다.
사망 복구가 발생하면 `death_detected`, `death_release`, `death_recovered` 액션 카운트가 함께 기록된다.
`Role Rotations` 섹션은 이번 테스트에서 몇 명이 어떤 로테이션으로 동작했는지 보여준다.

## AI 플레이어 모드

`--ai-player`는 더미를 단순 부하용 로봇이 아니라 생활형 AI 플레이어처럼 움직이게 하는 모드다. 기존 사냥 루프 위에 아래 행동을 추가한다.

- 전투가 없을 때 가끔 주변을 둘러본다.
- 사냥 중간에 짧게 쉬거나 오래 앉아 쉰다.
- 낮은 체력에서는 전투를 끊고 물러난다.
- 새 타겟을 잡을 때 가끔 살펴보기 타겟팅을 한다.
- 전투가 없을 때 근처에 보이는 플레이어가 있으면 너무 붙지 않는 거리까지 자연스럽게 따라간다.
- 가까운 플레이어에게는 쿨다운을 두고 낮은 확률로 짧은 인사를 한다.
- 설정한 확률로 간단한 일반 채팅이나 감정표현 명령을 보낸다.
- 기본 `/worldnews`, `/worldai jobs` 같은 테스트 명령은 AI 모드에서 자동으로 꺼진다.

기본값인 `--ai-persona auto`는 계정명과 seed를 기준으로 안정적인 성향을 배정한다. 같은 계정은 다시 실행해도 같은 성향을 받기 때문에 재현 가능한 테스트가 가능하고, 여러 계정을 띄우면 행동 주기와 휴식/동행/사회 행동 빈도가 자연스럽게 갈라진다.

현재 성향:

- `quiet-grinder`: 말수 적고 사냥 위주로 움직인다.
- `social-roamer`: 주변 유저를 더 자주 따라가고 채팅/감정표현 빈도가 높다.
- `cautious-hunter`: 쉬는 시간이 많고 타겟 확인을 더 자주 한다.
- `helpful-follower`: 근처 유저를 빠르게 따라붙는 보조형 성향이다.

짧은 테스트:

```bash
python3 tools/behavior-dummy-client.py \
  --accounts tools/dummy-accounts.csv \
  --concurrency 3 \
  --hold 120 \
  --ai-player \
  --ai-persona auto \
  --behavior-profile pve-casual \
  --action-rotation auto \
  --player-level 1 \
  --ideal-target-level 2 \
  --min-target-level 1 \
  --max-target-level-delta 2 \
  --target-selection smart \
  --target-examine-chance 0.20 \
  --social-interval 75 \
  --social-chance 0.08 \
  --player-greet-interval 45 \
  --player-greet-chance 0.06 \
  --emote-interval 55 \
  --emote-chance 0.12 \
  --look-around-interval 12 \
  --long-rest-chance 0.06 \
  --player-follow-interval 2 \
  --player-follow-distance 850 \
  --follow-player-max-distance 3500 \
  --metrics-csv tools/reports/ai-player/metrics.csv \
  --combat-csv tools/reports/ai-player/combat.csv \
  --report-md tools/reports/ai-player/report.md
```

동행 행동은 최신 클라의 `PlayerCreate`와 `PlayerPosition` 패킷을 읽어 보이는 플레이어 위치를 갱신한다. 서버가 UDP 미확정 클라이언트에게 위치 패킷을 TCP fallback으로 내려주기 때문에 더미는 별도 UDP 소켓 없이도 이동 중인 플레이어 위치를 따라갈 수 있다.

특정 캐릭터 근처를 우선 따라가게 하려면 이름 일부를 지정한다.

```bash
python3 tools/behavior-dummy-client.py \
  --accounts tools/ai-accounts.csv \
  --concurrency 3 \
  --hold 180 \
  --ai-player \
  --ai-persona helpful-follower \
  --follow-player-name 라온
```

래퍼에서는 `ai-pve-casual` 시나리오를 사용한다. 이 시나리오는 캐릭터 이름도 기본적으로 `Dummy###` 대신 자연스러운 이름 풀에서 생성한다.

```bash
python3 tools/run-dummy-load-test.py smoke \
  --scenario ai-pve-casual \
  --host 192.168.0.24 \
  --count 12 \
  --concurrency 3 \
  --hold 180 \
  --name ai-pve-casual
```

파티형 AI 플레이어는 `ai-party-casual` 시나리오를 사용한다. 파티 크기 단위로 리더/딜러/지원 역할이 섞이고, 초대/수락/따라가기/어시스트 행동을 함께 수행한다.

```bash
python3 tools/run-dummy-load-test.py party-small \
  --scenario ai-party-casual \
  --host 192.168.0.24 \
  --count 12 \
  --concurrency 6 \
  --party-size 3 \
  --hold 300 \
  --name ai-party-casual
```

운영 보충형으로는 `ai-filler-small` 또는 `ai-filler-medium` 프리셋과 `ai-filler-casual` 시나리오를 사용한다. 이 조합은 파티 초대/어시스트 루프가 과하게 돌지 않도록 기본 `party_size=1`이며, 사냥/휴식/동행/짧은 인사만 낮은 빈도로 섞는다.

```bash
python3 tools/run-dummy-load-test.py ai-filler-small \
  --scenario ai-filler-casual \
  --host 192.168.0.24 \
  --realm-strategy least-populated \
  --live-api-url http://192.168.0.24:5000/api/dashboard/live \
  --accounts-csv tools/ai-accounts-all-realms.csv \
  --name ai-filler-small
```

`ai-filler-small`은 10명/30분, `ai-filler-medium`은 30명/1시간 기준이다. 실제 운영에서는 먼저 `--dry-run`으로 생성되는 명령과 `run.json`의 `ai_persona`, 인사/추종 확률, 선택 렐름 값을 확인한 뒤 실행한다.

실제 운영에 가까운 방향으로는 여러 렐름 계정 CSV를 준비한 뒤, 접속 직전에 대시보드 API를 보고 인구가 가장 적은 렐름 계정을 고르게 한다.

```bash
python3 tools/behavior-dummy-client.py \
  --accounts tools/ai-accounts-all-realms.csv \
  --concurrency 12 \
  --hold 1800 \
  --ai-player \
  --behavior-profile pve-casual \
  --realm-strategy least-populated \
  --live-api-url http://192.168.0.24:5000/api/dashboard/live
```

`least-populated`는 API의 `realms` 값을 보고 가장 인구가 적은 렐름을 고른다. CSV 안에 해당 렐름 계정이 `--concurrency`만큼 있어야 하며, 부족하면 명확한 오류로 중단한다.

RvR/순찰형 AI의 기반은 `--waypoints`다. 아직 적 플레이어 인식이나 성/타워 목표 판단까지 하는 완성형 RvR AI는 아니지만, 지정 좌표를 따라 이동하는 순찰 루프를 만들 수 있다.

```bash
python3 tools/behavior-dummy-client.py \
  --accounts tools/ai-accounts-all-realms.csv \
  --concurrency 6 \
  --ai-player \
  --behavior-profile pve-casual \
  --realm-strategy least-populated \
  --live-api-url http://192.168.0.24:5000/api/dashboard/live \
  --waypoints '1000,2000,300|1400,2300,300|1700,2600,310' \
  --waypoint-mode loop \
  --waypoint-interval 1.5
```

좌표는 현재 캐릭터가 있는 지역 기준이다. 실제 RvR 콘텐츠로 올리려면 나중에 “전장 진입 위치”, “성/타워 좌표”, “적 플레이어 패킷 인식”, “도주/집결 규칙”을 이 waypoint 기반 위에 얹는다.

## 반복 라운드와 CSV 지표

소켓을 닫으면 서버는 잠시 링크데드 상태를 유지한다. 같은 계정을 곧바로 다시 쓰면 `User is still being logged out from linkdeath`가 뜨며 다음 라운드 로그인이 실패할 수 있다.

빠른 반복 테스트는 계정을 라운드마다 바꿔 쓰는 방식이 가장 안정적이다. 필요한 계정 수는 `concurrency * rounds`개다.

```bash
python3 tools/provision-dummy-accounts.py \
  --count 6 \
  --replace \
  --password dummy-pass \
  --csv tools/dummy-accounts.csv

python3 tools/behavior-dummy-client.py \
  --accounts tools/dummy-accounts.csv \
  --concurrency 2 \
  --rounds 2 \
  --fresh-account-per-round \
  --round-delay 1 \
  --hold 12 \
  --ramp-up 2 \
  --ping-interval 4 \
  --turn-interval 0 \
  --combat \
  --move \
  --combat-interval 1.8 \
  --target-pool 3 \
  --attack-range 400 \
  --move-step 450 \
  --clear-target-interval 8 \
  --command '' \
  --jitter 0.2 \
  --tick 0.05 \
  --metrics-csv tools/dummy-metrics.csv
```

CSV 형식:

```csv
username,round,ok,actions,elapsed_seconds,error
dummy001,1,true,20,19.089,
dummy003,2,true,20,19.101,
```

`--fresh-account-per-round`를 쓰지 않고 같은 계정으로 반복하려면 `--round-delay`를 링크데드 해제 시간보다 길게 잡아야 한다.

## 권장 부하 단계

처음부터 큰 숫자를 넣지 말고 아래 순서로 올린다.

1. 1명 접속 유지, 1분
2. 3명 이동+전투, 30초
3. 5명 이동+전투, 3분
4. 20명 이동+전투, 5분
5. 50명 이동+전투, 10분
6. 100명 이상, 15분 이상

각 단계에서 확인할 것:

- 서버 크래시 여부
- `Game loop TPS`
- 메모리 증가 추세
- 로그인 실패/링크데드 로그
- MariaDB CPU와 디스크 사용량

## 부하 테스트 프리셋 래퍼

긴 명령어를 매번 직접 입력하지 않으려면 `tools/run-dummy-load-test.py`를 사용한다. 이 래퍼는 더미 계정 생성, 행동형 더미 실행, CSV/마크다운 리포트, 실행 로그, 실행 명령 JSON을 한 번에 저장한다.

```bash
python3 tools/run-dummy-load-test.py smoke
```

기본 리포트 위치:

```text
tools/reports/dummy-load/YYYYMMDD-HHMMSS-프리셋/
```

생성 파일:

- `accounts.csv`: 이번 실행에 사용한 더미 계정 목록.
- `metrics.csv`: 계정/라운드/액션별 CSV 지표.
- `combat.csv`: 대상별 전투 상세 CSV 지표.
- `report.md`: 사람이 읽는 요약 리포트.
- `output.log`: 계정 생성과 더미 실행 콘솔 로그.
- `run.json`: 실행 프리셋과 실제 명령어 기록.
- `server-stats.csv`: `--server-log`를 지정했을 때 테스트 시간대의 서버 StatPrint 원본 지표.
- `server-stats.json`: `--server-log`를 지정했을 때 CPU/메모리/TPS 요약.

프리셋:

- `smoke`: 3명, 35초, 3명 파티. 서버 수정 후 빠른 확인용.
- `party-small`: 6명, 3분, 3명 파티 2개.
- `party-medium`: 20명, 5분, 4명 파티 5개.
- `party-large`: 50명, 10분, 5명 파티 10개.

예시:

```bash
python3 tools/run-dummy-load-test.py party-small --scenario solo-melee --start 200 --name after-mobgrowth
```

시나리오는 “무엇을 검증할지”를 정한다.

- `newbie-solo`: 초보 솔플러 기준. 낮은 레벨 몬스터가 과하게 아픈지 본다.
- `solo-melee`: 일반 근접 솔플러 기준. 기본 사냥 속도와 사망률을 본다.
- `party-assist`: 파티 지원/집중 공격 기준. 파티 사냥 처리량과 서버 부하를 본다.
- `mobgrowth-pressure`: 몬스터 성장/전투 이벤트 압박용. 많은 타겟 교전과 처치 추정을 만든다.

프리셋은 “몇 명, 몇 분 돌릴지”를 정하고, 시나리오는 “어떤 행동과 타겟 조건으로 돌릴지”를 정한다. 예를 들어 초보존 20명 검증은 아래처럼 실행한다.

```bash
python3 tools/run-dummy-load-test.py party-medium \
  --scenario newbie-solo \
  --name newbie-zone-balance
```

몹 성장 시스템 압박 테스트는 아래처럼 실행한다.

```bash
python3 tools/run-dummy-load-test.py party-large \
  --scenario mobgrowth-pressure \
  --name mobgrowth-pressure
```

## 밸런스 스위트 러너

여러 시나리오를 한 번에 돌려 비교하려면 `tools/run-dummy-balance-suite.py`를 사용한다. 이 도구는 각 시나리오를 순서대로 실행하고, 전체 결과를 `summary.md`와 `summary.csv`로 묶는다.

```bash
python3 tools/run-dummy-balance-suite.py \
  --preset smoke \
  --scenarios newbie-solo,solo-melee,party-assist,mobgrowth-pressure \
  --host 192.168.0.24 \
  --accounts-csv tools/reports/subcomputer/account-slices/accounts-1000.csv \
  --account-start-offset 40 \
  --count 12 \
  --concurrency 3 \
  --hold 60 \
  --party-size 3 \
  --name balance-check
```

생성 위치:

```text
tools/reports/dummy-balance-suite/YYYYMMDD-HHMMSS-balance-check/
```

생성 파일:

- `summary.md`: 시나리오별 성공 여부, 교전 수, 처치 추정, 사망, 타임아웃, TPS/CPU/메모리 요약.
- `summary.csv`: 같은 내용을 스프레드시트에서 보기 좋은 CSV로 저장.
- `comparison.md`: `--baseline-summary`를 지정했을 때 이전 결과 대비 증감 요약.
- `suite.log`: 전체 실행 로그.
- `accounts/*.csv`: 시나리오별로 자동 분리한 계정 목록.
- `runs/*/report.md`: 각 시나리오의 상세 리포트.
- `runs/*/combat.csv`: 각 시나리오의 전투 단위 상세 지표.

기본 동작은 시나리오마다 계정 CSV를 자동으로 잘라서 쓴다. 연속 테스트에서 같은 계정을 즉시 재사용하면 서버의 링크데드 보호에 걸릴 수 있기 때문이다. 계정을 일부 건너뛰고 싶으면 `--account-start-offset`을 사용하고, 일부러 같은 계정을 재사용하려면 `--reuse-accounts`를 붙인다.

서버 로그를 함께 넘기면 전체 비교표에 TPS, CPU, 메모리도 들어간다.

```bash
python3 tools/run-dummy-balance-suite.py \
  --preset party-small \
  --host 192.168.0.24 \
  --accounts-csv tools/reports/subcomputer/account-slices/accounts-1000.csv \
  --server-log tools/reports/subcomputer/server-tail.log \
  --server-log-time-offset-hours -9 \
  --warn-process-cpu 70 \
  --warn-system-cpu 80 \
  --max-memory-used-mb 6144 \
  --name party-small-balance
```

패치 전후 밸런스 변화를 빠르게 보려면 이전 실행의 `summary.csv`를 기준선으로 넘긴다.

```bash
python3 tools/run-dummy-balance-suite.py \
  --preset party-small \
  --host 192.168.0.24 \
  --accounts-csv tools/reports/subcomputer/account-slices/accounts-1000.csv \
  --baseline-summary tools/reports/dummy-balance-suite/이전실행/summary.csv \
  --name after-balance-change
```

서버 상태까지 같은 리포트에 붙이려면 서버 로그 파일을 함께 넘긴다. 로컬 기본 로그는 보통 `Debug/logs/server.log`다.

```bash
python3 tools/run-dummy-load-test.py smoke \
  --start 300 \
  --name with-server-stats \
  --server-log Debug/logs/server.log
```

이 경우 러너가 더미 실행 시작/종료 시간을 기록하고, 그 시간창에 찍힌 `DOL.GS.StatPrint` 로그만 뽑아 `report.md` 마지막에 `Server Stats` 섹션을 붙인다. 확인 항목은 최대 접속자, CPU 평균/최대, 메모리 최대, 10/30/60초 TPS 최소/평균이다.

또한 `report.md` 맨 위에는 자동 판정이 붙는다.

- `PASS`: 더미 라운드가 모두 성공했고 TPS 기준을 통과했다.
- `WARN`: 테스트는 성공했지만 서버 로그를 지정하지 않았거나 CPU/메모리 경고 기준을 넘었다.
- `FAIL`: 더미 라운드 실패, 오류 메시지 발생, 서버 지표 누락, TPS 기준 미달, 메모리 상한 초과 중 하나가 발생했다.

기본 기준:

- TPS 10/30/60초 최저값이 모두 `95%` 이상이어야 한다.
- `--server-log`를 지정했다면 StatPrint 샘플이 최소 1개 있어야 한다.
- CPU process 최대 `80%`, system 최대 `85%` 초과는 `WARN`이다.
- 사망과 `/release`는 유저 행동 시뮬레이션의 일부라서 실패로 보지 않는다.

기준값은 필요하면 조정할 수 있다.

```bash
python3 tools/run-dummy-load-test.py party-small \
  --server-log Debug/logs/server.log \
  --min-tps10 95 \
  --min-tps30 95 \
  --min-tps60 95 \
  --warn-memory-used-mb 4096 \
  --max-memory-used-mb 6144
```

실행하지 않고 명령어와 출력 폴더만 확인하려면:

```bash
python3 tools/run-dummy-load-test.py party-medium --dry-run
```

주요 오버라이드:

- `--start`: 생성할 더미 계정 시작 번호.
- `--count`: 생성할 더미 계정 수.
- `--concurrency`: 동시 접속 수.
- `--hold`: 더미 유지 시간.
- `--party-size`: 파티 크기.
- `--ramp-up`: 동시 접속을 서서히 올리는 시간.
- `--report-root`: 리포트 저장 루트.
- `--server-log`: 서버 `server.log`를 읽어 부하 테스트 시간대의 StatPrint 지표를 리포트에 합친다.
- `--scenario`: 밸런스 시나리오를 선택한다. 기본 `solo-melee`.
- `--behavior-profile`: 시나리오가 고른 행동 프리셋만 따로 덮어쓴다.
- `--action-rotation`: 시나리오가 고른 액션 로테이션만 따로 덮어쓴다.
- `--min-target-removed`: 처치 추정 수가 이 값보다 낮으면 `FAIL`로 판정한다.
- `--max-player-deaths`: 전투 중 플레이어 사망 수가 이 값을 넘으면 `FAIL`로 판정한다.
- `--min-tps10`, `--min-tps30`, `--min-tps60`: 자동 판정에 사용할 TPS 최저 기준. 기본 `95`.
- `--min-server-stat-samples`: `--server-log` 사용 시 필요한 StatPrint 샘플 수. 기본 `1`.
- `--warn-process-cpu`, `--warn-system-cpu`: CPU 경고 기준. 기본 `80`, `85`.
- `--warn-memory-used-mb`: 메모리 사용량 경고 기준.
- `--max-memory-used-mb`: 메모리 사용량 실패 기준.
- `--no-fail-on-assessment`: 판정이 `FAIL`이어도 프로세스 종료 코드를 0으로 유지한다.

서버 로그만 따로 요약하려면:

```bash
python3 tools/summarize-server-stats.py Debug/logs/server.log \
  --since-time 09:00:00 \
  --until-time 09:10:00 \
  --csv tools/reports/server-stats.csv \
  --json tools/reports/server-stats.json
```

## 현재 한계

- 스킬 사용, 인벤토리 조작은 아직 하지 않는다.
- 이동은 실제 클라이언트 렌더링/충돌 계산이 아니라 서버 위치 패킷 기반의 단순 직선 접근이다.
- 더미가 몬스터에게 죽을 수 있다. 테스트를 반복하기 전에는 `tools/provision-dummy-accounts.py --replace`로 템플릿 위치를 다시 복제하면 깨끗하다.
- `--fresh-account-per-round`는 빠른 반복을 위해 링크데드 대기 중인 계정을 재사용하지 않는다. 라운드 수만큼 더미 계정을 넉넉히 만들어야 한다.
- 연결 종료는 정상 로그아웃 패킷이 아니라 소켓 종료라서 서버 로그에는 링크데드로 남을 수 있다.

다음 확장 후보:

- 랜덤 순찰 이동
- 실제 사거리 접근 후 스킬/스타일 사용 루프
- 시나리오 파일 기반 테스트
- 서버 지표 임계치 기반 자동 실패 처리
