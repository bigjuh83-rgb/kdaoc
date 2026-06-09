# OpenDAoC 더미 이동속도 상태 기반화 작업 지시서

## 현재 상황

장거리 이동/되감기 테스트 중 더미가 스텔스처럼 보였고, 이동속도가 정상속도 191로 유지되는 문제가 있었다.

조사 결과:
- 장거리 이동런의 더미 클래스는 정상이다.
  - 가온 Armsman
  - 라온 Mercenary
  - 이든 Cleric
  - 하람 Wizard
- 스텔스처럼 보인 이유는 클래스 문제가 아니라 계정 권한 문제다.
- `tools/run-multi-dummy-movement-session.py`가 더미 계정을 `--priv-level 2`로 생성하고 있었고, 서버 `WorldInitRequestHandler`가 GM 계정을 로그인 시 자동 스텔스 처리한다.
- 서버 `MaxSpeedCalculator`는 스텔스 감속을 `PrivLevel == 1` 일반 플레이어에게만 적용한다.
- 그래서 GM 더미는 "스텔스 외형/가시성 상태"인데 속도는 감속되지 않는 이상한 관찰 조건이었다.

이미 한 수정:
- `tools/run-multi-dummy-movement-session.py`
  - `--priv-level` CLI 옵션 추가
  - 기본값 `1`
  - provision 호출에서 하드코딩 `"2"` 대신 `str(args.priv_level)` 사용
- 기존 GM 스텔스 장거리런은 종료됨.
- `python3 -m py_compile tools/run-multi-dummy-movement-session.py` 통과.

## 핵심 목표

더미 이동속도를 "현재 상태 기반 속도"로 완성한다.

현재는 일부만 되어 있다:
- 서버 `SendUpdateMaxSpeed` 패킷을 더미가 받아 `client.max_speed_percent`로 저장한다.
- `run_dummy_round` 루프에서 `args.movement_speed = args.base_movement_speed * client.max_speed_percent / 100.0`로 갱신한다.
- 일반 이동/대부분 추격은 `dummy_movement_kwargs(args)`를 타므로 어느 정도 상태 기반 속도를 따른다.

하지만 아직 완성은 아니다:
- `--flee-movement-speed 240` 같은 도주용 고정 override가 상태 기반 속도를 우회할 수 있다.
- 스텔스/스프린트/스피드송/질병/스네어/root/encumberance/PvE speed 같은 상태가 모두 일관되게 반영되는지 테스트가 부족하다.

## 작업 범위

### 1. 현재 상태 기반 속도 레이어 정리

대상 파일:
- `tools/behavior-dummy-client.py`
- `tools/headless-daoc-client.py`
- 필요 시 테스트 파일 추가/수정

확인할 기존 함수:
- `dummy_travel_movement_speed`
- `dummy_packet_movement_speed`
- `dummy_movement_kwargs`
- `combat_chase_movement_speed`
- `move_towards_destination`
- `start_or_refresh_flee`
- `move_towards_position`
- `observe_max_speed_update`

원칙:
- 서버가 보내는 `max_speed_percent`를 권위 있는 현재 속도 계수로 사용한다.
- 더미가 자체적으로 스텔스/스피드송 수식을 서버와 중복 계산하지 않는다.
- 단, 도주/스프린트 같은 의도적 빠른 이동은 서버 max speed를 초과하지 않도록 clamp한다.
- 상태 기반 속도 최종값은 `base_movement_speed * max_speed_percent / 100` 이하가 되어야 한다.
- `flee_movement_speed` 같은 override도 현재 max speed보다 빠르면 clamp한다.
- root/mez/snare/disease/sprint/stealth/speed-song은 서버 max speed 패킷을 통해 반영되게 한다.

### 2. GM 스텔스 관찰 조건 방지

`tools/run-multi-dummy-movement-session.py`:
- 기본 `--priv-level 1` 유지.
- 장거리 이동 관찰런에서 GM 권한이 필요 없게 한다.
- `--audit`를 위해 GM 권한이 필요해서 더미를 GM으로 올리는 방식은 금지.
- movement audit는 가능하면 관리자/서버 측에서 특정 캐릭터 audit를 켜거나, 별도 테스트 훅/명령으로 처리한다.
- 최소한 visual movement test 기본은 일반 플레이어 권한이어야 한다.

주의:
- `PrivLevel=2`로 켜야 하는 진단 모드는 별도 옵션으로만 허용.
- 그 경우 "GM auto stealth 때문에 visual movement 판정 부정확" 경고를 출력해도 좋다.

### 3. 테스트 추가

추가할 테스트 예시:

1. max speed percent 반영
- `client.max_speed_percent = 50`
- `args.base_movement_speed = 191`
- 이동 kwargs가 95.5 근처로 나온다.

2. flee override clamp
- `args.flee_movement_speed = 240`
- `client.max_speed_percent = 50`
- 도주 이동속도는 95.5를 넘지 않는다.

3. normal speed
- `max_speed_percent = 100`
- 이동속도 191 유지.

4. speed song/sprint 시뮬레이션
- `max_speed_percent = 130` 또는 150 이상
- 더미 이동속도가 base보다 증가하되 서버 percent 기반으로만 증가.

5. GM visual movement guard
- `run-multi-dummy-movement-session.py` command construction에서 기본 `--priv-level 1`.
- `--audit` 사용 시에도 기본이 1인지 확인.

6. 기존 speed decouple 회귀 유지
- 1.124+ C2S speed는 191 같은 world speed float이어야 함.
- 48896 legacy packed speed가 C2S speed로 나가면 안 됨.

### 4. 현재 이동 관련 기존 수정 유지

이미 해결된 부분은 건드리지 말 것:
- 48896 순간이동 원인:
  - `191 * 256 = 48896` legacy packet speed를 travel distance로 사용하던 문제.
  - 현재는 modern C2S float speed로 191을 보내는 방향.
- visible movement Z floating 원인:
  - visible movement에서도 `--ground-z-map tools/pathing/heightmaps/region001_client_zones.json`을 붙이도록 수정됨.
- `/facegloc` 방향보정 문제:
  - movement 관찰런에서는 `--target-face-command-interval 0`으로 서버 heading-only jump 보정 패킷을 없앰.
- `--client-grid-nav-map` / `--path-graph`는 visible movement에서 계속 꺼져야 함.

### 5. 검증 순서

서버 재시작 없이 가능한 코드/단위 검증 먼저:

```bash
python3 -m py_compile tools/headless-daoc-client.py tools/behavior-dummy-client.py tools/run-multi-dummy-movement-session.py
python3 -m unittest tools.test_dummy_movement_speed_decouple tools.test_multi_dummy_movement_session -v
```

그 다음 서버 확인:

```bash
bash tools/check-main-server-fast.sh
```

장거리 런은 Codex/사용자 확인 후:

```bash
python3 tools/run-multi-dummy-movement-session.py \
  --mode move \
  --prefix movelong \
  --start 1 \
  --count 4 \
  --hold 900 \
  --ramp-up 2 \
  --movement-speed 191 \
  --move-update-interval 0 \
  --priv-level 1
```

audit가 필요하면 GM auto stealth를 유발하지 않는 방식으로 별도 설계 후 사용.

## 기대 결과

- 일반 장거리 이동 더미는 스텔스 상태가 아니어야 한다.
- 스텔스 상태가 진짜로 걸린 일반 플레이어 더미는 서버 max speed percent를 받아 느리게 이동해야 한다.
- 스피드송/스프린트/질병/스네어/root 등은 서버 max speed 패킷을 통해 더미 이동속도에 반영되어야 한다.
- flee나 chase override도 현재 max speed를 초과하면 안 된다.
- 관찰런에서 이동은 C2S world speed float, 지형 Z, no `/facegloc` 조건을 유지해야 한다.
