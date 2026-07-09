# KDAOC 동적 퀘스트 런타임

KDAOC 동적 퀘스트는 스토리 템플릿과 런타임 바인딩을 분리한다. LLM/시더가 만든 스토리 의도는 `dynamic_quest_template`에 보관할 수 있지만, 실제 시작 NPC, 목표 NPC, 위치, 바인딩 키는 서버 시작/시드 틱/월드 리비전 변경 시 현재 세계 상태에 맞춰 다시 결정된다. 플레이어 진행 상태는 `dynamic_quest_progress`에 저장되어 같은 월드 리비전과 바인딩이 유지될 때 재로딩할 수 있고, 월드 리비전이 바뀌면 진행 중 퀘스트는 취소될 수 있다.

## 서버프로퍼티

| Key | 기본값 | 설명 |
| --- | ---: | --- |
| `kdaoc_dynamic_quest_enabled` | `false` | 동적 퀘스트 런타임 활성화 |
| `kdaoc_dynamic_quest_max_active_per_player` | `1` | 플레이어당 동시에 진행 가능한 동적 퀘스트 수 |
| `kdaoc_dynamic_quest_max_active_per_npc` | `1` | NPC 하나가 동시에 제공 가능한 동적 퀘스트 수 |
| `kdaoc_dynamic_quest_max_kill_count` | `20` | 단일 동적 퀘스트 처치 목표 최대 수 |
| `kdaoc_dynamic_quest_reward_xp_multiplier` | `1.0` | 완료 경험치 배율 |
| `kdaoc_dynamic_quest_reward_money_multiplier` | `1.0` | 완료 돈 보상 배율 |
| `kdaoc_dynamic_quest_auto_seed_enabled` | `false` | 서버 시작/주기 틱에서 동적 퀘스트 자동 시드 |
| `kdaoc_dynamic_quest_auto_seed_tick_minutes` | `30` | 자동 시드 재확인 주기 |
| `kdaoc_dynamic_quest_auto_seed_max_quests` | `3` | 한 번의 시드 패스에서 만들 최대 퀘스트 수 |
| `kdaoc_dynamic_quest_auto_seed_definitions` | 3렐름 시작 지역 seed | `StartNpcName|RegionId|TargetName|Count|MinLevel|MaxLevel|StartMode|Trigger` 목록. `StartMode`, `Trigger`는 선택값이며 시작/목표 칸은 `selector:<name>`도 사용할 수 있다 |
| `kdaoc_dynamic_quest_world_revision` | `default` | 세계관/월드 스냅샷 리비전. 값이 바뀌면 진행 중 동적 퀘스트를 취소하고 기존 오퍼를 재바인딩 |
| `kdaoc_dynamic_quest_auto_seed_use_llm` | `false` | deterministic 텍스트 대신 LLM으로 퀘스트 대사 생성 |
| `kdaoc_dynamic_quest_story_provider_order` | `openai,main-local,secondary-local` | 스토리 생성 provider 우선순위. OpenAI 실패/쿼터 소진 시 로컬 provider로 fallback. Gemini 무료 할당량 보호를 위해 기본 order에서는 제외 |
| `kdaoc_dynamic_quest_story_minimum_score` | `50` | deterministic 평가 점수가 이 값보다 낮은 생성 결과는 버리고 다음 provider를 시도 |
| `kdaoc_dynamic_quest_story_compare_providers_enabled` | `false` | 여러 provider 후보를 비교해 최고 점수 스토리를 고를지 여부. 기본은 quota 보호를 위해 꺼짐 |
| `kdaoc_dynamic_quest_story_compare_max_per_prefill` | `2` | provider 비교 모드에서 prefill 후보 하나당 평가할 최대 생성 후보 수 |
| `kdaoc_dynamic_quest_story_openai_model` | `gpt-5.4` | OpenAI Responses API로 호출할 고품질 퀘스트 스토리 생성 모델 |
| `kdaoc_dynamic_quest_story_openai_per_minute_limit` | `2` | OpenAI 스토리 생성 분당 호출 상한. 서버 내부 quota guard로 초과 호출을 막고 fallback |
| `kdaoc_dynamic_quest_story_openai_daily_limit` | `5` | OpenAI 스토리 생성 일일 호출 상한. 정식 서비스 전 캐시 선생성 비용/호출량을 제한 |
| `kdaoc_dynamic_quest_story_openai_daily_token_limit` | `500000` | OpenAI 스토리 생성 일일 토큰 선예약 상한. AI Gateway의 OpenAI 무료 토큰 예산과 별도로 동적 퀘스트 기능만 쓰는 예산 |
| `kdaoc_dynamic_quest_story_gemini_model` | `gemini-3.5-flash` | Gemini fallback 호출 모델 |
| `kdaoc_dynamic_quest_story_gemini_per_minute_limit` | `0` | Gemini 스토리 생성 분당 호출 상한. 0이면 Gemini 호출 비활성 |
| `kdaoc_dynamic_quest_story_gemini_daily_limit` | `0` | Gemini 스토리 생성 일일 호출 상한. 0이면 Gemini 호출 비활성 |
| `kdaoc_dynamic_quest_story_gemini_daily_token_limit` | `0` | Gemini 스토리 생성 일일 토큰 선예약 상한. 0이면 Gemini 토큰 사용 비활성 |
| `kdaoc_dynamic_quest_story_cache_max_templates` | `500` | DB에 유지할 active LLM 스토리 템플릿 최대 수 |
| `kdaoc_dynamic_quest_story_cache_prune_count` | `50` | 캐시가 가득 찼을 때 하루 1회 낮은 점수부터 정리할 수 |
| `kdaoc_dynamic_quest_story_cache_prefill_batch_size` | `5` | 한 번의 자동 시드 패스에서 미리 생성할 LLM 스토리 템플릿 최대 수 |
| `kdaoc_dynamic_quest_story_cache_world_prefill_enabled` | `true` | LLM 캐시 prefill 때 현재 월드 NPC/몬스터 데이터에서 추가 스토리 후보를 자동 파생 |
| `kdaoc_dynamic_quest_story_cache_world_prefill_max_candidates` | `60` | 한 번의 시드 패스에서 검토할 현재 월드 기반 추가 후보 최대 수 |
| `kdaoc_dynamic_quest_story_cache_offer_enabled` | `true` | 자동 시드 슬롯이 남으면 DB의 active LLM 스토리 캐시를 현재 월드에 바인딩해 live offer로 승격 |
| `kdaoc_dynamic_quest_story_cache_offer_min_slots` | `3` | LLM+캐시 offer가 켜진 운영에서 설정 seed가 슬롯을 다 써도 캐시 story offer를 최소 이 개수만큼 추가 승격 |
| `kdaoc_dynamic_quest_cinematic_max_actors_per_action` | `100` | cinematic action 하나가 생성할 임시 NPC actor 최대 수. 0/미설정 또는 과거 기본값 8이면 기본 100으로 동작하고, 서버는 어떤 값이 들어와도 100을 넘기지 않는다. 작은 장면은 각 presentation beat의 `actorCount`와 cinematic tag로 직접 낮게 제어한다 |
| `kdaoc_dynamic_quest_story_gemini_reset_delay_minutes` | `10` | Gemini RPD 리셋(Pacific midnight) 뒤 캐시 정리/보충을 시작하기 전 대기 시간 |
| `kdaoc_dynamic_quest_story_gemini_reset_window_minutes` | `360` | 리셋 대기 후 캐시 정리/보충을 허용할 시간 창 |

OpenAI와 Gemini의 무료 할당량은 서로 다른 provider 예산으로 취급한다. AI Gateway 문서에는 OpenAI Tier 3 data-sharing complimentary 계획을 하루 1000만 토큰 예산으로 기록해 두었지만, 동적 퀘스트는 그 전체 예산을 공유해서 소진하지 않도록 별도 기능 cap(`kdaoc_dynamic_quest_story_openai_daily_token_limit`)을 둔다. Gemini의 실제 RPM/RPD/토큰 한도는 모델, quota tier, 계정 상태에 따라 바뀔 수 있고 프로젝트의 활성 limit은 Google AI Studio에서 확인한다. `gemini-3.1-*` 계열 한도를 `gemini-3.5-flash`에 그대로 대입하지 않는다. 무료 일일 할당량을 절대 넘기지 않기 위해 기본값은 Gemini 호출 비활성이고, 필요할 때만 실제 무료 한도보다 낮은 값으로 명시 설정한다. OpenAI/Gemini의 일일 호출 수와 일일 토큰 사용량은 Pacific day 기준으로 `ServerProperty`에 각각 `kdaoc_dynamic_quest_story_quota_<provider>_daily_usage = yyyy-MM-dd|count`, `kdaoc_dynamic_quest_story_quota_<provider>_daily_tokens = yyyy-MM-dd|tokens` 형태로 저장되어 서버 재시작 후에도 유지된다. 운영 중 모델/가드/사용량은 `GET /api/world/dynamic-quests/story-config`로 확인한다.

## GM 명령어

시작 NPC를 타겟한 상태에서 사용한다.

```text
/dynamicquest status
/dynamicquest fakekill <target mob name> [count]
/dynamicquest llm [seed text]
/dynamicquest list
/dynamicquest clear
```

`fakekill`은 LLM 없이 즉시 처치 퀘스트를 만든다. `llm`은 기존 `worldai_llm_api_url`, `worldai_llm_model`, `worldai_llm_timeout_seconds` 설정을 사용해서 OpenAI-compatible 로컬 LLM에 JSON 퀘스트 초안을 요청한다.

더미 난이도 테스트에서는 GM 명령어를 쓰지 않는다. 운영/테스트 서버에서 `kdaoc_dynamic_quest_enabled=true`, `kdaoc_dynamic_quest_auto_seed_enabled=true`를 켜면 서버 시작 시 `DynamicQuestSeedRuntime`이 설정된 NPC/지역/목표 몹으로 퀘스트를 생성한다.

기본 deterministic seed는 3렐름 저레벨 시작 지역을 골고루 덮는다.

```text
Brother Penric|1|black wolf pup|1|1|5|NpcOffer||mob-growth:killed:region:1
Aud|100|young sveawolf|1|1|5|NpcOffer||mob-growth:killed:region:100
Ionhar|200|water beetle larva|1|1|5|NpcOffer||mob-growth:killed:region:200
```

NPC 없는 자동 수락형 seed는 시작 NPC 이름을 비우고 `AutoAccept`를 지정한다. trigger를 지정하면 해당 서버 컨텐츠 신호로 수락되고, trigger를 비워두면 플레이어 위치 업데이트에서 현재 지역 태그(`region:<id>`)와 맞는 AutoAccept 퀘스트를 자동 수락한다.

```text
|1|forest spiderling|1|1|5|AutoAccept|rift-entered
|1|forest spiderling|1|1|5|AutoAccept|
```

동적 seed는 고정 NPC/몹 이름 대신 selector를 쓸 수 있다. selector seed의 퀘스트 ID는 selector 의도, 지역, 레벨대, 시작 모드, trigger로 안정화되고, 실제 시작 NPC/목표 몹/좌표는 서버 시작, 시드 틱, 월드 리비전 변경 때 현재 세계 상태에 맞춰 다시 바인딩된다.

```text
selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|
selector:world|1|selector:hostile|1|1|5|AutoAccept|region:1
```

지원 selector는 시작 칸의 `town-npc`, `quest-giver`, `npc`, `world`와 목표 칸의 `hostile-near-start`, `near-start`, `hostile`이다. `town-npc`/`quest-giver`/`npc`는 같은 지역의 퀘스트 제공자 성격 NPC만 고르며, 확실한 후보가 없으면 몹으로 fallback하지 않고 해당 seed를 스킵한다. 이름이 `ambient ...`인 장식 NPC와 서비스 NPC가 아닌 저레벨 Realm NPC는 시작 NPC 후보에서 제외한다. `world`는 NPC 없는 `WorldOffer`/`AutoAccept`에 사용할 수 있다. `hostile-near-start`는 시작 NPC 주변의 레벨대 목표를 우선 고르고, 같은 레벨 후보가 여러 개면 시작 NPC에 너무 붙은 목표보다 안전 거리대 목표를 먼저 고른다. `hostile`은 같은 지역/레벨대의 월드 목표를 고른다.

기존 DB에 알비온 단일 seed 기본값(`Brother Penric|1|black wolf pup|1|1|5`)이 남아 있으면 런타임에서 3렐름 기본 seed로 자동 확장한다.

## 동작 방식

동적 퀘스트 오퍼는 `DynamicQuestRuntimeService`의 메모리 Dictionary에 존재한다. NPC 클릭 시 퀘스트가 있으면 Accept/Decline 팝업을 보여주고, 수락 후 그래프 노드 진행은 NPC 상호작용과 `GamePlayer.EnemyKilled` 처치 이벤트에서 갱신한다.

현재 v1은 그래프 기반 진행을 지원한다. 기존 단일 Kill 퀘스트는 런타임에서 `Kill -> ReturnToNpc -> Complete` 호환 그래프로 materialize되고, deterministic starter seed는 `Talk -> Explore -> Kill -> ReturnToNpc -> Choice -> Complete` 그래프로 생성된다. NPC 없는 `WorldOffer`/`AutoAccept` seed는 시작 NPC를 요구하지 않고 `Explore -> Kill -> Complete` 그래프로 생성된다.

완료 후 시작 NPC에게 돌아가고 Choice 노드를 통과하면 경험치와 돈 보상을 지급하고 진행 상태를 활성 목록에서 제거한다. 레거시 단일 Kill 퀘스트는 기존 보상과 호환되며, 자동 seed 그래프는 완료한 플레이어블 단계 수에 따라 작은 단계 보너스를 받는다.

완료했지만 시작 NPC에게 반납하지 않은 퀘스트는 계속 열린 진행 상태로 취급한다. 반납 완료 후에는 같은 메모리 퀘스트를 같은 플레이어가 다시 수락하지 못하도록 완료 이력을 보관한다.

자동 시더는 seed 정의를 스토리 템플릿처럼 취급한다. `TargetName`은 exact match 필수가 아니라 목표 힌트이며, 현재 세계에 같은 이름이 없으면 같은 지역/레벨대의 후보 NPC로 재바인딩한다. selector seed는 처음부터 concrete 이름이 아니라 의도 기반 템플릿으로 취급한다. 바인딩 결과는 `bindingKey`, `worldRevision`, `dynamic-rebind`, `target:<actual target>`, `selector:start:<name>`, `selector:target:<name>` 태그로 노출된다.

LLM 스토리 캐시는 별도 테이블이 아니라 `dynamic_quest_template`을 사용한다. 스토리 본문, provider(`StoryProvider`), 모델명(`StoryModel`), 평가점수(`StoryQualityScore`), 평가 breakdown(`StoryQualityJson`), 몰입형 장면/저널(`StoryNarrativeJson`), 대사/감정/이모트 beat(`StoryPresentationJson`), 생성/마지막 사용 시각을 함께 저장한다. 최종 퀘스트 태그에도 `llm-provider:<provider>`, `llm-model:<model>`, `llm-score:<score>`가 붙어 이후 모델 품질 비교와 낮은 점수 정리에 사용할 수 있다.

스토리 평가는 LLM 호출 없이 서버가 deterministic하게 계산한다. 구조, 한국어 텍스트, 목표 일치, 몰입감, narrative scene, presentation beat, 재바인딩 안전성, 금지 필드/원시 이모트 id 같은 safety 항목을 점수화한다. 캐시 정리는 총점이 낮은 row를 먼저 고르고, 총점이 같으면 safety/structure 점수가 낮은 row를 먼저 비활성화한다. 따라서 오래됐다는 이유만으로 양호한 스토리가 같은 점수의 위험한 스토리보다 먼저 지워지지 않는다.

운영 안전성 평가는 스토리 품질 평가와 별도 단계다. `DynamicQuestOperationalEvaluator`는 바인딩된 `DynamicQuestDefinition`을 대상으로 완료 조건을 서버가 추적할 수 있는지, 시작/목표 NPC가 현재 월드에 존재하는지, 목표 수량이 주변 같은 이름 cluster 수를 넘지 않는지, starter/NpcOffer 목표 레벨이 안전선을 넘지 않는지, 시작/목표 위치가 알려진 zone 안에 있는지, 같은 zone 안에서 navmesh 경로를 찾을 수 있는지, 보상 multiplier가 정책 상한을 넘지 않는지, 너무 짧은 반복 보상 루프 위험이 있는지를 rule-based로 확인한다. 템플릿 바인딩 결과가 운영 평가를 통과하지 못하면 live offer로 승격하지 않고, 런타임에 직접 추가되는 퀘스트도 기본 보상/완료 조건 검사를 통과해야 등록된다.

운영 평가는 현재 서버가 확실히 아는 정보만 hard fail로 사용한다. zone 미확인, target zone 누락, 같은 zone 안에서 확인한 navmesh 경로 실패는 폐기 사유가 되며, 서로 다른 zone 간 세부 이동성, 실제 지형 내부/벽 내부 여부, 직업별 장비 격차, 아이템 상점가 기반 악용 가능성은 현재 데이터가 충분하지 않으므로 경고 또는 후속 평가 항목으로 남긴다. NPC 없는 `AutoAccept` starter는 기존 템플릿 바인더가 안전 후보를 고르는 정책을 우선 사용하며, evaluator는 높은 레벨 후보를 추가 hard fail로 다시 막지 않고 난이도 경고로만 남긴다.

`kdaoc_dynamic_quest_auto_seed_use_llm=true`이면 자동 시더는 실제 오퍼 생성 전에 seed 정의의 missing story template을 `kdaoc_dynamic_quest_story_cache_prefill_batch_size` 개수만큼 미리 채운다. 따라서 `kdaoc_dynamic_quest_auto_seed_max_quests` 때문에 이번 틱에 오퍼로 뜨지 않는 정의도 DB에 스토리만 선생성될 수 있다. `kdaoc_dynamic_quest_story_cache_world_prefill_enabled=true`이면 설정 seed뿐 아니라 현재 월드의 살아있는 공격 가능 NPC/몬스터 이름, 지역, 레벨대에서 `AutoAccept` 스토리 후보를 추가로 파생한다. 월드 프리필 후보는 스토리 텍스트와 별도로 `branch:mob-growth`, `world-signal:mob-growth:killed:region:<regionId>` 태그를 저장한다. 이 캐시가 나중에 live offer로 승격되면 템플릿 바인더가 현재 월드의 목표 위치에 맞춰 `observe_signal` 분기 노드를 만들고, 성장 몬스터 처치 신호가 들어왔을 때 followup 경로를 완료로 진행시킨다. 자동 시더는 먼저 설정 seed를 active offer로 만들고, `kdaoc_dynamic_quest_story_cache_offer_enabled=true`이면 DB의 active story cache를 점수/마지막 사용 시각/렐름 라운드로빈 기준으로 골라 현재 월드에 바인딩해 추가 offer로 만든다. LLM+캐시 offer 운영에서는 `kdaoc_dynamic_quest_story_cache_offer_min_slots`만큼 유효 seed 슬롯을 추가로 확보하므로, 기본 3렐름 NPC offer가 모두 생성되어도 NPC 없는 `AutoAccept` 캐시 offer가 같이 live offer로 뜬다. 캐시가 꽉 차면 Gemini RPD 리셋 이후 허용 창에서만 낮은 점수 row를 정리하고, 그 뒤 새 스토리 생성이 가능해진다.

서버 시작 시 첫 자동 시드 패스는 월드/NPC 로딩이 끝날 시간을 주기 위해 짧은 지연 후 백그라운드에서 실행된다. 로컬 LLM이나 Gemini가 느리거나 꺼져 있어도 `GameServerStarted` 이벤트와 게임/API 리스너 부팅을 막지 않으며, 같은 시드 패스가 오래 걸리면 다음 타이머 틱과 중복 실행하지 않는다.

`kdaoc_dynamic_quest_world_revision`이 바뀌면 다음 자동 시드 패스에서 기존 월드 리비전의 진행 중 퀘스트를 `world_revision_changed` 사유로 취소하고, 리비전이 다른 기존 오퍼를 제거한 뒤 현재 NPC/지역/레벨대에 맞춰 다시 바인딩한다. 이 취소는 메모리에 올라온 온라인 진행뿐 아니라 `dynamic_quest_progress`에 저장된 오프라인 active row도 포함한다. 리비전이 같으면 서버 재접속 후에도 저장된 진행 상태를 유지할 수 있다.

동적 퀘스트 시작 모드는 `NpcOffer`, `WorldOffer`, `AutoAccept`다. `NpcOffer`는 기존처럼 시작 NPC 식별자를 필수로 요구한다. `WorldOffer`와 `AutoAccept`는 NPC 없이도 수락할 수 있으며, 지역 진입, 월드 이벤트, 동료 시스템, 몬스터 성장 시스템 같은 서버 내부 컨텐츠가 `TryAcceptWorldQuest(player, questId, source)` 또는 `TryAcceptAvailableWorldQuest(player, trigger)`를 호출해 시작시킬 수 있다. 트리거 자동 선택은 원시 태그(`region:1` 같은 값)와 `trigger:<name>`, `world:<name>`, `signal:<name>`, `autoaccept:<name>` 태그를 사용한다.

플레이어 위치 업데이트는 `AutoAccept`만 지역 기반으로 자동 수락한다. `WorldOffer`는 같은 `region:<id>` 태그가 있어도 자동 수락되지 않으며, 월드 이벤트나 동료/몬스터 성장 컨텐츠가 명시적으로 호출해야 시작된다.

진행 중인 퀘스트의 `WorldSignal` 엣지는 서버 내부 컨텐츠가 `DynamicQuestRuntimeService.Instance.RecordWorldSignal(player, signal)`을 호출해 진행시킨다. 이 경로는 진행 상태를 DB에 저장하고 `timeline`에 `world_signal`, `node_advanced`, 필요 시 `quest_completed`를 남긴다. 몬스터 성장 단계 변화, 지역 방어 성공, 동료 대화 완료 같은 시스템은 GM 명령 없이 이 메서드만 호출하면 현재 노드의 `WorldSignal` 조건과 일치하는 퀘스트를 다음 노드로 보낼 수 있다.

LLM narrative/presentation 메타가 있는 퀘스트는 노드 진입 때 추가 timeline 이벤트를 남긴다. `narrative_scene`은 장면 제목/본문, `journal_entry`는 재접속 후에도 읽을 수 있는 짧은 저널 문장, `presentation_beat`는 speaker/emotion/emote/text 요약이다. 실제 `GamePlayer`가 있는 수락/상호작용/선택/탐험/처치/월드신호 경로에서는 `narrative_scene_presented`도 남기고 장면 제목과 본문을 플레이어 시스템창에 즉시 출력한다. 시작 NPC와 대화하는 노드에서는 서버 allowlist를 통과한 emote 이름만 `GameNPC.Emote(eEmote)`로 재생하고, 원시 emote id/opcode는 저장/실행하지 않는다. 이 연출은 진행 상태를 밀지 않는 cosmetic layer이며, 상태 변경은 기존 노드 objective/edge 처리에서만 일어난다.

cinematic action layer는 presentation/narrative 문맥을 읽어 임시 marker object와 임시 NPC actor를 배치한다. marker는 clue/record/relic/flame/weapon/structure 카테고리 중 현재 장면에 맞는 모델을 카탈로그에서 고르고, NPC actor는 challenge, guard_advance, fallback_guard, combat_stance, hold_ground, witness_point, ambush_reveal, defender_intercept, scout_retreat, ritual_interrupt, threat_standoff 같은 액션으로 짧게 이동/방어/후퇴/대치한다. actor는 완료/정리 시 `cinematic_cleanup`으로 제거되고, 자체 보상/진행 상태를 바꾸지 않는다.

Scene Director layer는 같은 actor/marker 시스템을 순차 beat로 묶는다. `scene-director`, `story-cinematic`, `dark-brotherhood` 태그 또는 암살/목격자/매복/탈출 문맥이 있으면 기존 Talk/Explore/Kill/Choice/Return 노드 안에서 `scene_beat` action을 만든다. 대표 beat는 contract, witness, lookout, ambush, intercept, witness_escape, confrontation, fallout, debrief이며, 각 beat는 `SceneBeatIndex`, `SceneDelayMs`, `SceneRole`, `Formation`을 가진다. formation은 escort/line/ambush/escape/patrol/ring을 사용해 단순 원형 스폰보다 더 장면 같은 배치를 만든다. 이 layer도 완료 조건을 직접 바꾸지 않고 timeline의 `cinematic_action`으로 기록된다.

다중 actor는 action 단위로 `ActorCount`를 가진다. 기본 설정 `kdaoc_dynamic_quest_cinematic_max_actors_per_action=100`은 클라이맥스 장면을 최대 100명까지 허용하기 위한 상한이고, 일반 퀘스트의 부담은 각 presentation beat의 `actorCount`와 `cinematic-actors:<action>:<count>` 태그로 낮게 유지한다. 서버는 0/미설정 또는 과거 기본값 8이면 100으로 되돌리고 100 초과 값은 100으로 clamp한다. `mass-cinematic` 태그는 대규모 장면 의도를 나타내며, 실제 수는 서버 설정 상한을 넘지 않는다.

더미 matrix는 `cinematic_density_score`를 별도로 계산한다. 이 점수는 narrative scene, presentation beat, cinematic action, scene director beat, choice/world signal, world impact, 완료/보상 관측을 합산해 스토리/연출 밀도를 본다. 더미 평가 API에 `cinematicDensityScore`와 `sceneDirectorBeat`가 들어오고 기준 미만이면 story cache row를 비활성화할 수 있으므로, 완료 가능성과 별개로 연출이 너무 빈약한 캐시를 걸러낼 수 있다.

Choice 노드는 선택지가 `consequence` 문장을 가질 수 있다. 플레이어가 선택하면 `choice_selected`와 별도로 `choice_consequence` timeline 이벤트가 남고, 실제 플레이어가 있는 상호작용에서는 선택 결과 문장을 즉시 시스템창에 보여준다. 이 값은 보상 수치나 명령이 아니라 후속 스토리/관측 API가 참고할 수 있는 짧은 서사 결과만 담는다.

NPC 반납형 퀘스트는 그래프가 `Complete`에 도착해도 보상 수령 전까지 DB의 active progress로 남는다. 따라서 서버 재시작/재접속 후에도 시작 NPC에게 돌아가 보상을 받을 수 있으며, 세계관 변경이나 월드 리비전 변경 시에는 이 반납 대기 상태도 진행 중 퀘스트로 보고 취소된다. NPC 없는 `WorldOffer`/`AutoAccept` 퀘스트는 `Complete` 도착 시 서버가 즉시 보상 완료 처리하고 active 목록에서 숨긴다.

몬스터 성장 시스템은 플레이어/파티가 성장 또는 돌연변이 몬스터를 처치할 때 active quest에 다음 신호를 자동 전달한다. Normal 상태의 일반 몹 첫 처치는 신호를 만들지 않는다.

```text
mob-growth:killed:mob:<mobInternalId>
mob-growth:killed:boss
mob-growth:killed:stage:boss
mob-growth:killed:mutant
mob-growth:killed:region:<regionId>
mob-growth:killed
```

`elite`, `champion`, `boss` 단계는 각각 `mob-growth:killed:<stage>`와 `mob-growth:killed:stage:<stage>` 두 형태를 제공한다. 런타임은 한 번의 처치 이벤트에서 가장 먼저 일치한 신호 하나만 현재 플레이어의 퀘스트에 적용해서, 같은 이벤트가 연속 WorldSignal 노드를 한꺼번에 밀어버리지 않게 한다.

자동 시더 정의에서 `StartMode`를 생략하면 기존 호환을 위해 `NpcOffer`로 처리한다. `WorldOffer`/`AutoAccept`는 `StartNpcName`이 비어 있어도 생성되며, 현재 월드의 `RegionId`, 레벨대, `TargetName` 힌트에 맞는 NPC를 목표로 바인딩한다.

## 읽기 API

난이도 테스트 관측용 API는 상태를 바꾸지 않는다. 표준 메인 서버의 기본 API base는 `http://127.0.0.1:5000`이고, 서버 환경변수 `OPENDAOC_API_PORT`가 있으면 그 값을 따른다. `8084`, `8086`, `8088`은 동적 퀘스트 API의 기본 포트가 아니므로 테스트/관측 스크립트는 명시적으로 `5000` 또는 `OPENDAOC_API_PORT`를 사용한다.

```text
GET http://127.0.0.1:5000/api/world/dynamic-quests
GET http://127.0.0.1:5000/api/world/dynamic-quests/progress?player=<character>
GET http://127.0.0.1:5000/api/world/dynamic-quests/progress?account=<account>
GET http://127.0.0.1:5000/api/world/dynamic-quests/timeline?player=<character>&limit=50
GET http://127.0.0.1:5000/api/world/dynamic-quests/timeline?account=<account>&limit=50
GET http://127.0.0.1:5000/api/world/dynamic-quests/story-cache?limit=50&includeText=false
GET http://127.0.0.1:5000/api/world/dynamic-quests/story-config
GET http://127.0.0.1:5000/api/world/dynamic-quests/seed/status
```

`progress`와 `timeline`은 조회 대상 캐릭터/계정이 현재 서버에서 찾을 수 없으면 `404 PlayerNotFound`를 반환한다. 이 응답은 상태 변경이 아니며, 더미 이름 오타나 아직 접속하지 않은 계정을 조회했다는 뜻이다.

`dynamic-quests` 목록의 각 quest는 `realm` 요약 필드를 포함한다. 값은 `realm:<name>` 태그가 있으면 그 태그를 우선 사용하고, 없으면 `startRegionId`로 Albion/Midgard/Hibernia/Unknown을 계산한다. 따라서 `seed/status.createdByRealm`뿐 아니라 active quest 목록 자체에서도 더미 매트릭스가 렐름 분포를 바로 확인할 수 있다.

`seed/status`는 `worldRevision`, `cancelledByWorldRevision`, `removedStaleOffers`, `storyCachePrefillCandidates`, `storyCachePrefilled`, `storyCacheOffered`, `createdByRealm`, `skippedByRealm`, `failedByRealm` 카운터를 포함한다. 이 값으로 자동 시더가 특정 realm에만 쏠렸는지, NPC/목표몹 누락 때문에 스킵됐는지, 세계 변경으로 진행/오퍼가 정리됐는지, 현재 월드 기반 LLM 캐시 후보가 얼마나 잡혔고 그중 몇 개가 실제 active offer가 됐는지 즉시 확인할 수 있다.

`story-cache`는 active LLM story cache row를 점수 낮은 순서로 반환한다. `totalActive`, `byRealm`, `byProvider`, `byModel` 집계와 각 row의 `storyQualityScore`, `quality`, `narrativeScenes`, `presentationBeats`, `storyProvider`, `storyModel`, `tags`, `branchWorldSignal`, `startMode`, `targetNameHint`, `lastBindingKey`를 포함하지만 상태를 변경하지 않는다. 스토리 본문(`storySeed`, `offerText`, `progressText`, `finishText`)과 narrative body/journal, presentation text는 기본으로 비워서 내려주며, 운영자가 명시적으로 `includeText=true`를 붙였을 때만 반환한다. 제목, mood, emotion, emote 같은 요약 메타는 `includeText=false`에서도 관측할 수 있다.

`story-config`는 비밀키 없이 auto seed의 설정/유효 live offer 수, provider 순서, 최소 품질 점수, provider 비교 모드, 메인컴/세컨컴 로컬 모델, OpenAI/Gemini 모델명, provider별 RPM/RPD/일일 토큰 가드, 현재 일일 호출/토큰 사용량, 캐시 최대치/정리 정책만 반환한다. 현재 운영 기본 우선순위는 `openai -> main-local -> secondary-local`이며, OpenAI 기능 cap이 남아 있으면 먼저 스토리를 만들고, 실패하거나 쿼터가 막히면 로컬 LLM으로 fallback한다. Gemini는 무료 할당량 보호를 위해 기본 비활성이고, 실제 무료 한도보다 낮은 서버 cap을 명시했을 때만 provider order에 넣어 사용한다.

`timeline`은 `quest_accepted`, `explore_complete`, `kill_progress`, `npc_interaction`, `choice_selected`, `choice_consequence`, `node_advanced`, `quest_completed`, `quest_rewarded`, `world_signal`, `narrative_scene`, `narrative_scene_presented`, `journal_entry`, `presentation_beat` 같은 관측 이벤트를 반환한다. 이 API는 진행 상태를 바꾸지 않으며, 더미 난이도 테스트 실패 원인 분석용이다.

더미는 완료 목표 처치 후 시작 NPC에게 돌아갈 때 서버 상호작용 거리(`WorldMgr.INTERACT_DISTANCE = 192`)보다 작은 180 거리 안에서만 `interact_object`를 보낸다. 커스텀 다이얼로그 응답 패킷은 `messageType=0x06`(CustomDialog)을 사용한다. 기본 `--dynamic-quest-return-dialog-response accept`는 `response=0x01`로 첫 번째 선택지를 고르고, `decline`은 `response=0x00`으로 두 번째 선택지를 고른다.

더미 E2E 완료 판정은 `dynamic_quest_return_interact` 후 읽기 API의 active 목록이 비는 `dynamic_quest_complete_verified` 이벤트를 기준으로 한다. 동적 퀘스트 모드에서는 `target_removed`나 파티 공유 완료만으로 시작 NPC에게 돌아가지 않고, 읽기 API에서 현재 노드가 `return`으로 바뀐 것을 확인한 뒤 `dynamic_quest_return_start_from_progress`로 복귀한다. `--dynamic-quest-require-timeline-events choice_selected,world_signal`을 주면 라운드 마지막에 read-only `timeline` API를 조회해 해당 이벤트가 실제로 찍혔는지까지 실패 조건으로 본다. 동적 퀘스트 반납 전 연결 끊김은 완료로 간주하지 않는다.

반복 검증은 독립 matrix 러너를 사용한다. 이 러너는 GM 명령을 만들지 않고, 더미 클라이언트의 실제 상호작용 플로우만 실행한다.

```bash
python3 tools/run-dummy-dynamic-quest-matrix.py \
  --matrix realm-smoke \
  --party-sizes 1,2 \
  --accounts-pattern 'tools/dummy-accounts-{realm_slug}-40.csv'
```

NPC 없는 `AutoAccept` seed는 별도 모드로 검증한다. 이 모드는 시작 NPC 상호작용과 반납 플래그를 쓰지 않고, `/api/world/dynamic-quests`에서 현재 live quest의 `startNodeId` objective 좌표를 읽어 더미 시작 위치를 세팅한다. 서버 재시작이나 월드 리비전 변경으로 퀘스트 위치가 재바인딩되어도 고정 좌표에 묶이지 않는다.

```bash
python3 tools/run-dummy-dynamic-quest-matrix.py \
  --matrix quick \
  --quest-start-mode autoaccept \
  --party-sizes 1 \
  --player-level 50 \
  --min-target-level 0 \
  --max-target-level 50
```

매트릭스는 기본적으로 각 case 시작 전에 CSV의 첫 party size 계정 위치를 퀘스트 NPC 근처로 DB 리셋하고 `Health`, `Mana`, `Endurance`를 풀 자원 값으로 복구한다. 이 준비 단계는 GM 명령이 아니며, 더미가 로그인 후 실제 `interact_object`와 커스텀 다이얼로그로만 퀘스트를 진행하게 만들기 위한 테스트 위치 고정이다. 필요하면 `--no-reset-start-positions`로 끌 수 있다.

라이브 퀘스트 스모크에서는 완료/진행 중인 계정을 read-only API/DB 조회로 건너뛰고, 남은 계정 중 근접 가능 직업을 우선 선택한다. 이 정책은 퀘스트 시스템 경로를 안정적으로 확인하기 위한 기본값이며, 실제 난이도 측정에서는 `--no-prefer-melee-smoke-accounts`로 끄고 힐러/캐스터/혼합 파티를 따로 측정한다.

`--quest-start-mode autoaccept`에서는 시작 위치 리셋 대상이 퀘스트 NPC 근처가 아니라 현재 live quest의 시작 objective다. 더미는 위치 업데이트로 자동 수락/탐색 완료를 발생시키고, 목표 처치 후 읽기 API의 active 목록이 비는 `action_dynamic_quest_final_inactive`를 완료 지표로 기록한다.

`--dry-run`을 붙이면 `test-output/dynamic-quest-matrix/commands.txt`에 실행 명령만 기록한다. 실제 난이도 판정은 각 case의 `metrics.csv`에서 `ok`, `target_removed`, `player_deaths`, `action_dynamic_quest_complete_verified`, `action_dynamic_quest_expected_active_node_verified`, `action_dynamic_quest_final_inactive`, `action_dynamic_quest_final_expected_active_node`를 집계한다. `--dynamic-quest-expected-final-node observe_signal`을 주면 followup 분기처럼 월드 신호를 기다리며 active 상태로 남는 퀘스트도 해당 노드에 도착한 것을 성공으로 본다. `action_dynamic_quest_timeline_choice_selected`, `action_dynamic_quest_timeline_world_signal`은 분기와 월드 신호 관측 지표다. `action_dynamic_quest_reward_observed`는 채팅 관측 기반 보조 지표로 리포트에 남기지만, 더미가 보상 채팅을 놓칠 수 있으므로 완료 성공의 필수 조건으로 쓰지 않는다.

더미 매트릭스의 `evaluation_score`는 스토리/연출 핵심 점수다. 더미 레벨이 낮아서 죽거나 완료에 실패한 경우를 스카이림급 대화/연출 점수에 섞지 않기 위해, 운영 관측값은 별도 `operationalEvaluation` 블록과 `matrix-summary.md`의 `operational_score`, `operational_grade`, `operational_passed`, `operational_exploit_penalty`로 기록한다. 이 블록은 완료 관측, 보상 관측, 사망, 긴 동선, 매우 짧은 보상 완료 같은 운영 신호를 남기지만, 인프라/더미 준비 실패나 저레벨 더미 난이도 문제를 스토리 점수로 오염시키지 않는다.

성장 몬스터 분기 스모크는 현재 live quest 중 `branch:mob-growth`와 특정 `world-signal:` 태그가 있는 offer를 고르고, 두 번째 선택지로 진입해 timeline을 확인한다.

```bash
python3 tools/run-dummy-dynamic-quest-matrix.py \
  --matrix quick \
  --dynamic-quest-return-dialog-response decline \
  --require-quest-tag branch:mob-growth \
  --require-world-signal mob-growth:killed:region:1 \
  --dynamic-quest-require-timeline-events choice_selected \
  --dynamic-quest-expected-final-node observe_signal
```

실제 성장 몬스터 처치 신호까지 한 번에 검증할 수 있는 월드 상태에서는 `--dynamic-quest-require-timeline-events choice_selected,world_signal`을 사용한다. 일반 비성장 몹 처치만으로는 `mob-growth:killed:region:<regionId>` 신호가 발생하지 않는다.

매트릭스 러너의 기본값은 퀘스트 시작 NPC 상호작용, 목표 지점 이동, 사냥, 시작 NPC 복귀, 완료 다이얼로그까지 한 번에 검증하도록 `--hold 260`, `--safe-exit-max-seconds 240`, `--smooth-movement`, `--movement-speed 240`, `--smooth-move-interval 0.20`, `--encounter-log-interval 1.0`을 사용한다. 이 기본값은 사냥 직후 바로 종료되어 `ReturnToNpc` 노드를 완료하지 못하는 테스트 오염을 막기 위한 값이다.

## Quest Graph v1

그래프 노드 타입은 `Talk`, `Explore`, `Kill`, `ReturnToNpc`, `Choice`, `Complete`, `Fail`이다. v1 starter seed는 첫 상호작용 직후 Talk 노드를 완료 처리하고 Explore 노드로 넘어가며, 지정 좌표 반경 진입 후 Kill, 목표 처치 후 ReturnToNpc, Choice, Complete 순서로 진행한다.

엣지 조건은 런타임 내부에서 `ObjectiveComplete`, `ChoiceSelected`, `WorldSignal`을 처리할 수 있다. `WorldSignal`은 몬스터 성장, 지역 이벤트, 동료 시스템 같은 외부 컨텐츠가 나중에 퀘스트 분기를 밀어 넣을 수 있는 서버 내부 연결점이다. LLM v1 파서는 `ObjectiveComplete`, `ChoiceSelected`, 그리고 allowlist에 들어간 서버 소유 `WorldSignal`만 허용한다.

LLM graph가 사용할 수 있는 `WorldSignal` 값은 안정적인 일반 신호로 제한된다. 특정 live mob internal id는 서버 재시작/월드 리비전 변경 때 바뀔 수 있으므로 LLM allowlist에는 넣지 않는다.

```text
mob-growth:killed
mob-growth:killed:mutant
mob-growth:killed:<elite|champion|boss>
mob-growth:killed:stage:<elite|champion|boss>
mob-growth:killed:region:<regionId>
region-entered
region-entered:<regionId>
region:<regionId>
```

읽기 API는 다음 그래프 상태를 노출한다.

```text
active[].currentNodeId
active[].currentNodeType
active[].currentObjective
active[].completedNodeIds
active[].nodes
active[].choices
active[].isComplete
active[].failed
active[].bindingKey
active[].worldRevision
active[].cancelReason
```

더미와 난이도 테스트는 이 API를 관측 전용으로만 사용한다. 상태 변경은 실제 NPC 상호작용, 커스텀 다이얼로그 응답, 사냥 이벤트로만 발생해야 하며 GM 명령어로 진행 상태를 만들거나 넘기지 않는다.

NPC 없는 퀘스트는 상태 변경이 실제 월드 트리거 또는 서버 컨텐츠 호출로만 발생해야 한다. 테스트에서 `AutoAccept`를 검증할 때도 GM 명령 대신 런타임의 트리거 수락 경로를 사용한다.

Choice v1은 커스텀 다이얼로그의 Accept/Decline 구조를 사용한다. Accept는 첫 번째 choice id, Decline은 두 번째 choice id를 선택한다. 현재 deterministic seed의 choice id는 `safe`, `followup`이다. 기본 3렐름 deterministic seed는 `safe`가 즉시 완료되고, `followup`은 `mob-growth:killed:region:<regionId>`를 기다리는 `observe_signal` Explore 노드로 이어진다. LLM/world-cache 퀘스트도 템플릿 태그에 allowlist를 통과한 `world-signal:<signal>`이 있으면 같은 방식으로 `followup`이 해당 WorldSignal을 기다린다.

## 보상 v1

기본 보상은 기존과 같이 서버 프로퍼티 배율을 적용한다.

```text
xp = level * level * 12 * targetCount * kdaoc_dynamic_quest_reward_xp_multiplier
money = level * 20 * targetCount * kdaoc_dynamic_quest_reward_money_multiplier
```

그래프 퀘스트는 `DynamicQuestRewardDefinition`으로 추가 배율을 가진다.

```text
finalScale = rewardMultiplier * partyMultiplier * (1 + max(0, completedPlayableSteps - 1) * stepBonusMultiplier) * choiceScale
```

`Complete`와 `Fail`은 터미널 노드라 단계 보너스에 포함하지 않는다. 자동 deterministic seed는 `stepBonusMultiplier=0.25`를 사용한다. 예를 들어 `Talk`, `Kill`, `ReturnToNpc`, `Choice`까지 4개 플레이어블 노드를 완료하면 `1 + 3*0.25 = 1.75x` 단계 보너스가 붙는다. `DynamicQuestRewardDefinition.ChoiceBonusKey`가 있고 플레이어가 같은 choice id를 선택했다면 `choiceScale=1.15`가 추가되고, 보상 처리 timeline에 `choice_reward_bonus`가 남는다.

## 안전 제한

LLM 출력은 다음 필드를 포함하면 거부된다.

```text
reward, gold, realm_points, command, spawn, delete, database, sql, script, code
```

LLM은 제목/대사/목표/카운트/레벨 범위를 제안할 수 있고, 선택적으로 v1 graph 템플릿도 제안할 수 있다. 실제 보상 수치는 서버 공식으로 계산하며, LLM이 보상/DB/명령/스폰/스크립트 필드를 포함하면 중첩 위치와 무관하게 거부된다.

허용되는 LLM graph v1 템플릿은 `graph.start`와 `graph.nodes[]`만 사용한다. 노드 타입은 `Talk`, `Kill`, `ReturnToNpc`, `Choice`, `Complete`이며, 엣지 조건은 `ObjectiveComplete`, `ChoiceSelected`, allowlist를 통과한 `WorldSignal`만 허용한다. 이외 조건은 파서 단계에서 거부한다. Talk/ReturnToNpc의 NPC 식별자는 LLM 값을 믿지 않고 서버가 전달한 시작 NPC의 `InternalID`, 이름, 지역으로 고정한다.

## 구현 파일

- 런타임 서비스: `GameServer/WorldAI/DynamicQuestRuntimeService.cs`
- 자동 시더: `GameServer/WorldAI/DynamicQuestSeedService.cs`
- 스토리 템플릿/바인딩 서비스: `GameServer/WorldAI/DynamicQuestTemplateService.cs`
- 자동 시더 타이머: `GameServer/WorldAI/DynamicQuestSeedRuntime.cs`
- 읽기 API: `GameServer/API/WorldAI/WorldAiRoutes.cs`
- 템플릿 DB 테이블: `CoreDatabase/Tables/DbDynamicQuestTemplate.cs`
- 진행 DB 테이블: `CoreDatabase/Tables/DbDynamicQuestProgress.cs`
- 더미 E2E 매트릭스: `tools/run-dummy-dynamic-quest-matrix.py`
- GM 명령어: `GameServer/commands/gmcommands/dynamicquest.cs`
- NPC 클릭/퀘스트 아이콘 연결: `GameServer/gameobjects/GameNPC.cs`
- 처치 카운트 연결: `GameServer/gameobjects/GamePlayer.cs`
- 서버프로퍼티: `GameServer/serverproperty/ServerProperties.cs`
