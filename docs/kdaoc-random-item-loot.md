# KDAOC 랜덤 아이템 드랍

KDAOC 랜덤 아이템 드랍은 기존 Atlas ROG 생성기를 기반으로 몬스터 사냥 보상을 전역 랜덤 드랍으로 바꾸는 컨텐츠다. 서버프로퍼티 카테고리는 `kdaoc`로 묶어 두었고, 기본값은 비활성화다.

## 서버프로퍼티

| Key | 기본값 | 설명 |
| --- | ---: | --- |
| `kdaoc_random_item_enabled` | `false` | 전역 랜덤 아이템 드랍 사용 여부 |
| `kdaoc_random_item_suppress_existing_loot` | `true` | 켜면 기존 일반 아이템 드랍 대신 랜덤 아이템 generator만 사용 |
| `kdaoc_random_item_exclusive_priority` | `1000` | 기존 loot generator보다 우선하기 위한 독점 우선순위 |
| `kdaoc_random_item_min_mob_level` | `1` | 랜덤 아이템을 드랍할 최소 몬스터 레벨 |
| `kdaoc_random_item_max_item_level` | `50` | 생성 아이템 최대 레벨 |
| `kdaoc_random_item_drop_grey_mobs` | `false` | 회색 몬스터도 랜덤 아이템을 드랍할지 여부 |
| `kdaoc_random_item_base_drop_chance` | `12` | 일반 몬스터 기본 드랍 확률(%) |
| `kdaoc_random_item_named_drop_bonus` | `20` | 네임드/에픽 NPC 추가 드랍 확률(%) |
| `kdaoc_random_item_boss_drop_bonus` | `55` | 보스 추가 드랍 확률(%) |
| `kdaoc_random_item_normal_drop_rolls` | `1` | 일반 몬스터 독립 드랍 롤 수 |
| `kdaoc_random_item_named_drop_rolls` | `2` | 네임드/에픽 NPC 독립 드랍 롤 수 |
| `kdaoc_random_item_boss_drop_rolls` | `6` | 보스 독립 드랍 롤 수. 각 롤은 기존 등급 확률표를 그대로 사용 |
| `kdaoc_random_item_max_drop_rolls` | `12` | 몬스터 한 마리당 드랍 롤 안전 상한 |
| `kdaoc_random_item_boss_max_premium_drops` | `2` | 보스 한 마리에서 Heroic 이상 고등급 아이템 최대 개수. 초과 고등급 롤은 Rare로 낮춤 |
| `kdaoc_random_item_min_level_offset` | `-2` | 생성 아이템 레벨 최소 보정 |
| `kdaoc_random_item_max_level_offset` | `1` | 생성 아이템 레벨 최대 보정 |
| `kdaoc_random_item_named_level_bonus` | `2` | 네임드/에픽 NPC 아이템 레벨 보너스 |
| `kdaoc_random_item_boss_level_bonus` | `4` | 보스 아이템 레벨 보너스 |
| `kdaoc_random_item_max_generation_attempts` | `5` | 안전 검증을 통과할 때까지 재생성하는 최대 횟수 |

몬스터 성장 시스템의 `worldai_mob_growth_*` 키도 카테고리만 `kdaoc`로 이동했다. 키 이름은 유지했기 때문에 기존 DB 값과 코드는 그대로 호환된다.

## 등급

랜덤 아이템은 생성 후 등급을 한 번 더 적용한다. 네임드와 보스는 등급 roll에 보너스를 받아 더 좋은 아이템이 나올 확률이 높다.

보스는 파티 공략 보상량을 맞추기 위해 여러 번 독립 드랍 롤을 굴린다. 단, 고등급 아이템 확률표 자체는 올리지 않고 `kdaoc_random_item_boss_max_premium_drops`로 Heroic 이상 아이템 수를 제한한다. 기본값에서는 보스가 최대 6번 드랍을 시도하며, 신화/전설/영웅급은 합쳐서 최대 2개까지만 유지되고 초과분은 `희귀:` 등급으로 내려간다. 따라서 “높은 등급 1~2개 + 낮은 등급 여러 개” 구조가 된다.

| 등급 | 이름 접두어 | 최소 품질 | 최소 보너스 |
| --- | --- | ---: | ---: |
| Common | 없음 | 89 | 0 |
| Magic | `마력:` | 92 | 8 |
| Rare | `희귀:` | 95 | 15 |
| Heroic | `영웅:` | 97 | 22 |
| Legendary | `전설:` | 99 | 30 |
| Mythic | `신화:` | 100 | 35 |

예시: `전설: asterite sword`, `희귀: arcanium ring`

## 더미 보스전 검증

2026-05-20 기준 더미 파티 보스전으로 실제 autoloot 획득까지 확인했다.

| 리포트 | 보스 | 결과 | 드랍 |
| --- | --- | --- | --- |
| `tools/reports/boss-barfog-pve40-rangedsafe2-20260519-233416` | King of the Barfog Hills | 40/40 접속, 사망 2, target_removed 38, 타임아웃 0 | 6개: 신화 2, 희귀 2, 일반 2 |
| `tools/reports/boss-elidyn-pve40-rescuegrace-20260520-001440` | Lord Elidyn | 40/40 접속, 사망 0, target_removed 40, 타임아웃 0 | 5개: 신화 1, 마력 3, 일반 1 |
| `tools/reports/boss-cailleach-uragaig-pve40-20260520-015654` | Cailleach Uragaig | 40/40 접속, 사망 1, target_removed 39, 타임아웃 0 | 1개: 영웅 1 |
| `tools/reports/boss-legendary-afanc-pve40-objective-match-20260520-015016` | Legendary Afanc | 40/40 접속, 사망 13, target_removed 27, 타임아웃 0 | 0개 |

Barfog 24인 풀피 테스트(`boss-barfog-pve24-rangedsafe-20260519-232517`)는 사망 24, target_removed 0, loot 0이었다. 현재 더미 장비/구성 기준으로 Barfog는 40인급 테스트 보스로 본다.

추가 실패/한계 기록:

- `tools/reports/boss-golestandt-pve40-20260520-012838`: Golestandt는 사망 40, target_removed 0, loot 0. 랜덤템 문제가 아니라 드래곤급 보스 생존전략 미완성으로 분리한다.
- `tools/reports/boss-moran-pve40-20260520-013454`: Moran the Mighty는 사망 26, target_removed 14, loot 0. 처치는 일부 확인됐지만 안정 공략에는 부족하다.

## 안전 검증

무기 슬롯 아이템은 `Object_Type`이 실제 무기 타입이어야 하며 `GenericItem(0)`이나 `GenericWeapon(1)`은 차단된다. 무기에는 DPS, 속도, 데미지 타입이 필요하다.

방어구 슬롯 아이템은 실제 방어구 타입이어야 하며 AF가 필요하다. 장신구 슬롯 아이템은 `Magical` 타입이어야 하고 DPS, 속도, 데미지 타입 같은 무기 수치를 가질 수 없다.

무기 이펙트는 현재 안전한 조합만 허용한다. 기존 ROG가 사용하던 피스트랩 이펙트 `48`, `49`, `102`만 유지하고, 다른 무기/모델 조합의 랜덤 이펙트는 `0`으로 제거한다. 이는 무기 모델과 이펙트 조합 불일치로 인한 클라이언트 표시 문제를 피하기 위한 보수적 처리다.

## 연결 위치

- 안전 검증/등급 처리: `GameServer/gameutils/KdaocRandomItemService.cs`
- 전역 loot generator: `GameServer/gameutils/KdaocRandomItemLootGenerator.cs`
- LootMgr 연결: `GameServer/gameutils/LootMgr.cs`
- 서버프로퍼티: `GameServer/serverproperty/ServerProperties.cs`
- 단위 테스트: `Tests/UnitTests/UT_KdaocRandomItemService.cs`
