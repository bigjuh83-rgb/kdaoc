# WorldAI LLM Worker Contract

This document describes the server-side contract that exists before wiring a real
local LLM such as Ollama, Qwen, Gemma, or Mistral.

## Current Scope

- The game server owns all gameplay state, validation, publishing, and history.
- The LLM worker only turns a queued job into one JSON object.
- The worker must not output combat numbers, rewards, spawn counts, bans, or
  commands.
- A fake processor still exists for local testing through `/worldai processfake`.
- A built-in OpenAI-compatible processor can call the local AI endpoint configured
  by server properties.

## Worker Flow

1. GM or future game logic creates a world event.
2. The server creates `Pending` rows in `llm_job`.
3. The worker claims jobs from:

```http
POST http://localhost:5000/api/world/llm/jobs/claim?limit=10
```

Claiming moves jobs from `Pending` to `Claimed`, so a later worker will not pick
up the same row. `GET /api/world/llm/jobs?limit=10` still exists as a read-only
peek endpoint for debugging.

4. The worker reads `jobType`, `payloadJson`, `schemaJson`, and `instructions`.
5. The worker generates exactly one JSON object.
6. The worker submits either the raw generated JSON object or a wrapper:

```http
POST http://localhost:5000/api/world/llm/jobs/{jobId}/result
Content-Type: application/json

{
  "resultJson": "{\"title\":\"숲의 위협\",\"body\":\"새로운 보스가 모습을 드러냈습니다.\",\"importance\":\"Major\"}"
}
```

Raw object submission is also accepted:

```http
POST http://localhost:5000/api/world/llm/jobs/{jobId}/result
Content-Type: application/json

{
  "title": "숲의 위협",
  "body": "새로운 보스가 모습을 드러냈습니다.",
  "importance": "Major"
}
```

The server accepts results only for `Pending` or `Claimed` jobs. Valid results
move the job to `Completed`. Invalid JSON, missing fields, or forbidden fields
move the job to `Rejected`. Missing source events move the job to `Failed`.

## Worker Operations

```http
GET  http://localhost:5000/api/world/llm/jobs/detail?limit=20
GET  http://localhost:5000/api/world/llm/health
GET  http://localhost:5000/api/world/llm/config
GET  http://localhost:5000/api/world/llm/check
POST http://localhost:5000/api/world/llm/jobs/reclaim?minutes=15
POST http://localhost:5000/api/world/llm/jobs/{jobId}/retry
POST http://localhost:5000/api/world/llm/jobs/{jobId}/reject
```

`health` returns queue counts and the oldest pending/claimed ages. `config`
returns the currently configured OpenAI-compatible endpoint. `check` calls
`/v1/models` on that endpoint. `reclaim` moves old `Claimed` jobs back to
`Pending` when a worker died or was interrupted.

`retry` moves a non-completed job back to `Pending`. `reject` accepts either a
plain text body or a JSON body such as:

```json
{ "reason": "Operator rejected this draft." }
```

Current job statuses:

- `Pending`
- `Claimed`
- `Completed`
- `Failed`
- `Rejected`

## Job Schemas

### WorldNews

Required fields:

- `title`: string, max 120 characters
- `body`: string, max 500 characters
- `importance`: `Minor`, `Normal`, `Major`, or `Legendary`

### ChronicleEntry

Required fields:

- `summary`: string, max 200 characters
- `chronicle`: string, max 1000 characters

## Forbidden Fields

The validator rejects these field names at any JSON depth, case-insensitive:

- `hp`
- `damage`
- `reward`
- `gold`
- `realm_points`
- `drop_rate`
- `spawn_count`
- `cooldown`
- `ban`
- `command`

## GM Commands

```text
/worldai jobs
/worldai jobs detail [all] [limit]
/worldai seed bossborn
/worldai see bossborn
/worldai clearpreview
/worldai processfake [count]
/worldai processllm [count]
/worldai llmcheck
/worldai llmconfig
/worldai health
/worldai reclaim [minutes]
/worldai cleanup bossborn
/worldai approvals [limit]
/worldai approve <eventId>
/worldai retry <jobId>
/worldai reject <jobId> [reason]
```

`/worldai jobs detail` shows active jobs by default: `Pending`, `Claimed`, and
`Failed`. Use `/worldai jobs detail all` when completed or rejected historical
jobs are also needed.

`/worldai seed bossborn` is idempotent for the built-in sample. If the existing
sample already points to `붉은 송곳니 그락` in `북부 숲`, it reuses that event
and its jobs instead of creating another identical sample.

`/worldai see bossborn` moves the GM to the latest stored `bossborn` sample
location. If no sample exists yet, it seeds one first.

`/worldai clearpreview` removes the temporary bossborn preview NPC created by
`/worldai see bossborn`.

`/worldai cleanup bossborn` marks duplicate active built-in bossborn sample
jobs as `Rejected`, keeping one active job per job type.

`/worldai processllm [count]` sends pending jobs to the configured
OpenAI-compatible local AI server. The current default endpoint is:

```text
worldai_llm_api_url=http://192.168.0.42:1234
worldai_llm_model=gemma-4-e4b-it
worldai_llm_timeout_seconds=45
```

The local AI server at `http://192.168.0.42:1234` currently responds to
`/v1/models`, and the configured default model `gemma-4-e4b-it` is present in
that model list.

`/worldai llmcheck` calls `/v1/models` on the configured endpoint and displays
whether the server is reachable plus the first available model ids. Use this
before `/worldai processllm` after starting or changing the local AI server.

`/worldai llmconfig` shows these values in game. The generated JSON still goes
through the same validator and publication path as fake processing.

`/worldai health` displays queue counts, active job count, and oldest
pending/claimed ages. `/worldai reclaim [minutes]` returns old `Claimed` jobs to
`Pending`; use it if an external worker or a manual `processllm` run was
interrupted.

## What Is Still Not Implemented

- Reward, drop, spawn, economy, or city-state changes.
- Direct LLM control over monster combat.
- Authentication for a remote worker. The API is currently intended for local
  `localhost` use.

## Related Systems

- `worldai-mob-growth.md`: server-owned monster survival growth. This records
  boss ascension events and queues LLM text jobs, while gameplay values remain
  capped and validated by the server.
