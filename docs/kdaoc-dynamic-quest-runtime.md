# KDAOC 메모리 동적 퀘스트

KDAOC 동적 퀘스트는 DB에 저장하지 않는 휘발성 컨텐츠다. 서버 재시작, 프로세스 종료, `/dynamicquest clear` 시 생성된 퀘스트와 플레이어 진행 상태가 모두 사라진다.

## 서버프로퍼티

| Key | 기본값 | 설명 |
| --- | ---: | --- |
| `kdaoc_dynamic_quest_enabled` | `false` | 메모리 동적 퀘스트 활성화 |
| `kdaoc_dynamic_quest_max_active_per_player` | `1` | 플레이어당 동시에 진행 가능한 동적 퀘스트 수 |
| `kdaoc_dynamic_quest_max_active_per_npc` | `1` | NPC 하나가 동시에 제공 가능한 동적 퀘스트 수 |
| `kdaoc_dynamic_quest_max_kill_count` | `20` | 단일 동적 퀘스트 처치 목표 최대 수 |
| `kdaoc_dynamic_quest_reward_xp_multiplier` | `1.0` | 완료 경험치 배율 |
| `kdaoc_dynamic_quest_reward_money_multiplier` | `1.0` | 완료 돈 보상 배율 |

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

## 동작 방식

동적 퀘스트는 `DynamicQuestRuntimeService`의 메모리 Dictionary에만 존재한다. NPC 클릭 시 퀘스트가 있으면 Accept/Decline 팝업을 보여주고, 수락 후 처치 카운트는 `GamePlayer.EnemyKilled`에서 갱신한다.

현재 MVP는 Kill 퀘스트만 지원한다. 완료 후 시작 NPC에게 돌아가면 경험치와 돈 보상을 지급하고 진행 상태를 메모리에서 제거한다.

## 안전 제한

LLM 출력은 다음 필드를 포함하면 거부된다.

```text
reward, gold, realm_points, command, spawn, delete, database, sql, script, code
```

LLM은 제목/대사/목표/카운트/레벨 범위만 제안하고, 실제 보상 수치는 서버 공식으로 계산한다.

## 구현 파일

- 런타임 서비스: `GameServer/WorldAI/DynamicQuestRuntimeService.cs`
- GM 명령어: `GameServer/commands/gmcommands/dynamicquest.cs`
- NPC 클릭/퀘스트 아이콘 연결: `GameServer/gameobjects/GameNPC.cs`
- 처치 카운트 연결: `GameServer/gameobjects/GamePlayer.cs`
- 서버프로퍼티: `GameServer/serverproperty/ServerProperties.cs`
