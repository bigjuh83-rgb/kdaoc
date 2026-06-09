# LiteLLM AI Gateway And Companion Dialogue Design

## Goal

Add a live companion dialogue system that makes companions feel like party
members without putting API keys, billing risk, or LLM latency inside the game
server.

The first implementation uses OpenAI small models through LiteLLM, but the
architecture must be ready for later routing across OpenAI, Gemini, Claude,
OpenRouter, local models, and other providers.

Core rule:

```text
GameServer owns gameplay.
AI Gateway owns model routing, token budgets, prompts, and failure isolation.
LiteLLM normalizes provider calls.
Companions never bypass existing FSM and target gates.
```

## Current Decisions

- Use LiteLLM now.
- Start with the LiteLLM Python SDK inside a local OpenDAoC AI Gateway service.
- Do not start with the full LiteLLM Proxy stack.
- Keep LiteLLM Proxy as a later upgrade when multiple apps/users need virtual
  keys, central spend tracking, admin UI, and Postgres-backed management.
- Use only small model aliases for the current OpenAI free-token exploration.
- Default model alias: `small-dialogue`.
- Initial mapped provider model: `openai/gpt-4.1-nano`.
- Daily hard cap: 500K total tokens.
- Daily soft warning: 400K total tokens.
- Player-facing companion term: `용병`.
- Internal code may continue using `dummy`.
- GameServer and C# code must not read OpenAI or provider API keys.
- Repository files must not contain real API keys.

## Scope

In scope for v1:

- A local Python AI Gateway service.
- LiteLLM SDK adapter for model calls.
- Small-model allowlist and alias mapping.
- Daily token ledger, feature caps, and fail-closed quota handling.
- Companion dialogue as the first AI feature.
- Event-reactive companion speech.
- Triggered player-response speech for clear companion calls or commands.
- Mixed output channels:
  - party chat for tactical information;
  - `/say` for light social flavor.
- Structured JSON model output.
- Strict validation before sending any command to a companion client.
- Short session memory only.
- Minimal sanitized context sent to the model.
- Usage logs for comparison with OpenAI Platform usage.

Out of scope for v1:

- LiteLLM Proxy deployment.
- Postgres-backed LiteLLM virtual keys.
- Long-term companion memory.
- Sending raw chat logs, account names, exact coordinates, or full player
  history to a provider.
- Letting the LLM execute arbitrary commands.
- Letting the LLM choose hostile targets, teleport, grant items, alter gold, or
  change rewards.
- Direct LLM control over combat or movement.
- Using large models by default.

## Why SDK First, Proxy Later

LiteLLM supports both a Python SDK and a proxy server. The proxy is best when an
organization needs a central LLM gateway with authentication, authorization,
virtual keys, spend management, and management UI. It also introduces more
infrastructure: proxy process, master key, database URL, and operational
configuration.

For this project, the first useful step is one local game-adjacent AI service
owned by the server operator. The SDK gives provider routing and OpenAI-format
normalization now, while avoiding proxy infrastructure until it is needed.

Upgrade path:

```text
v1: OpenDAoC AI Gateway -> LiteLLM SDK -> provider
v2: OpenDAoC AI Gateway -> local LiteLLM Proxy -> provider
v3: Multiple game/ops tools -> LiteLLM Proxy virtual keys -> provider fleet
```

The feature code should call an internal gateway interface, not LiteLLM
directly, so moving from SDK to Proxy later changes only the adapter.

## Architecture

```text
GameServer
  -> Companion request/status APIs
  -> Combat/group/player state APIs
  -> future WorldAI LLM job APIs

Dummy Companion Service
  -> starts companion behavior clients
  -> tracks requester and group state
  -> asks AI Gateway for dialogue decisions
  -> writes validated live-control JSON

OpenDAoC AI Gateway
  -> request sanitizer
  -> prompt builder
  -> session memory
  -> model policy
  -> token budget ledger
  -> LiteLLM SDK adapter
  -> response validator
  -> usage/audit logs

Behavior Dummy Client
  -> polls live-control JSON
  -> sends allowed chat commands
  -> applies only allowed short-lived behavior hints
```

## AI Gateway Responsibilities

The AI Gateway is the only local component that reads provider credentials.

It must:

- read provider keys from process environment only;
- expose a local API or command interface for feature services;
- reject requests when no allowed model is configured;
- reject requests after daily token caps are reached;
- reject requests if model alias is not in the allowlist;
- sanitize feature payloads before prompt construction;
- build short prompts;
- call LiteLLM;
- parse structured JSON;
- validate output fields, length, channel, and hint;
- log usage without provider secrets;
- disable calls until the next budget window after quota or billing errors.

It must not:

- write real API keys to repository files;
- expose provider keys through GameServer endpoints;
- forward raw chat logs by default;
- accept arbitrary model names from gameplay code;
- trust model output as an executable command.

## LiteLLM Model Policy

Feature code asks for aliases, not provider model names.

Initial aliases:

```json
{
  "small-dialogue": {
    "provider_model": "openai/gpt-4.1-nano",
    "features": ["companion_dialogue"],
    "max_output_tokens": 80,
    "temperature": 0.7
  }
}
```

Allowed classes:

- `small-dialogue`
- future `small-summary`
- future `small-news`

Disallowed by default:

- large chat models;
- reasoning models;
- tool/search/browser-capable models;
- image/audio/video models;
- arbitrary user-supplied model ids.

If a provider model changes later, update the alias mapping. Do not change
companion code.

## Token Budgets

The project cannot rely only on provider billing dashboards or LiteLLM dollar
cost estimates because the current target is a free-token allocation. The AI
Gateway keeps its own token ledger.

Daily UTC budget:

```text
global hard cap: 500,000 tokens/day
global warning: 400,000 tokens/day
companion_dialogue cap: 350,000 tokens/day
mob_dialogue reserve: 100,000 tokens/day
event_news reserve: 30,000 tokens/day
manual_test reserve: 20,000 tokens/day
```

Runtime limits:

- per party: at most one LLM call every 5 seconds;
- per companion: short cooldown after speaking;
- repeated identical events are suppressed;
- API errors with quota/billing/rate-limit signals disable LLM calls for the
  rest of the budget window unless manually reset.

Usage log fields:

```text
timestamp_utc
feature
model_alias
provider_model
request_id
party_id_hash
companion_role
event_type
prompt_tokens
completion_tokens
total_tokens
blocked_reason
latency_ms
```

No API key or raw provider credential is logged.

## Companion Dialogue Inputs

Only minimal sanitized context is sent.

Allowed context:

- feature name;
- event type;
- realm name;
- companion role;
- personality profile id;
- combat state;
- leader health band;
- companion health/mana band;
- add count;
- party death count;
- whether player explicitly requested help;
- abstract command intent;
- short session memory summary.

Forbidden context by default:

- account names;
- exact coordinates;
- IP addresses;
- full raw chat logs;
- long player history;
- inventory contents unless later explicitly designed;
- provider API key or local secrets.

Examples:

```json
{
  "feature": "companion_dialogue",
  "event_type": "player_requested_heal",
  "realm": "albion",
  "role": "healer",
  "personality": "calm_support",
  "state": {
    "combat": true,
    "leader_health_band": "low",
    "companion_mana_band": "normal",
    "adds": 1,
    "party_dead": 0
  },
  "memory": "leader recently asked for healing support"
}
```

The model does not need player names. If a response should address a player by
name, the local service can add it after validation.

## Companion Dialogue Outputs

The model must return one JSON object:

```json
{
  "say_channel": "party",
  "say_text": "바로 치유하겠습니다. 조금만 버텨주세요.",
  "intent_hint": "heal_priority",
  "urgency": "high"
}
```

Allowed `say_channel`:

- `party`
- `say`
- `none`

Allowed `intent_hint`:

- `none`
- `heal_priority`
- `resurrect_priority`
- `follow`
- `wait`
- `assist`
- `flee`
- `cc_add`

Allowed `urgency`:

- `low`
- `normal`
- `high`

Validation:

- `say_text` max 80 Korean-visible characters for v1;
- no newline spam;
- no slash command inside `say_text`;
- no coordinates;
- no account-like or key-like strings;
- no claims about rewards, drops, gold, realm points, bans, or GM authority;
- invalid JSON falls back to silence or local canned speech.

## Personality Policy

Companions have light role-based personality. The goal is party-member flavor,
not long roleplay.

Profiles:

- tank: steady, protective, leads from the front;
- healer: calm, watchful, supportive;
- dps: confident, brief, eager to finish fights;
- support: tactical, tracks adds and crowd control.

Rules:

- combat speech is short and practical;
- idle speech can be warmer but still brief;
- no long monologues;
- no modern out-of-world explanations;
- no jokes during emergency events;
- obey player commands when they map to safe intent hints.

## Trigger Policy

Dialogue sources:

1. Event-reactive:
   - low health;
   - add detected;
   - crowd control attempt;
   - heal or resurrection started;
   - flee or recovery started;
   - objective reached;
   - target removed;
   - level-up/train milestone.

2. Player-triggered:
   - companion name;
   - `용병`;
   - `힐`, `치유`, `살려`, `부활`;
   - `도와줘`, `지원`;
   - `공격`, `잡아`;
   - `멈춰`, `기다려`, `따라와`, `가자`.

Clear mechanical commands can be handled without LLM. For example, `힐해줘`
should raise a local `heal_priority` hint even if budget is exhausted.

## Behavior Hint Application

The LLM may suggest a limited hint. It does not execute behavior.

The companion service converts valid hints into short-lived live-control
metadata. The behavior client then applies the hint only if existing FSM policy
allows it.

Suggested TTLs:

- `heal_priority`: 8 seconds;
- `resurrect_priority`: 15 seconds;
- `follow`: 15 seconds;
- `wait`: 10 seconds;
- `assist`: 8 seconds;
- `flee`: 8 seconds;
- `cc_add`: 8 seconds.

Rejected hints are logged with reason and do not affect combat.

## Session Memory

Use short in-memory session memory only.

- Keep 5-10 recent sanitized events per companion.
- Store summaries, not raw transcripts.
- Clear memory when the companion leaves, process exits, or service restarts.
- No database long-term memory in v1.

Examples:

- `leader asked for healing recently`;
- `party fled from multiple adds`;
- `healer resurrected one member`;
- `tank was told to wait`.

## Integration With Existing Systems

Existing `dummy-companion-service.py` already manages live companion processes.
It should remain focused on companion lifecycle and group behavior.

Recommended v1 addition:

- Add `tools/opendaoc-ai-gateway.py`.
- Add `tools/opendaoc-ai-gateway.example.json`.
- Add gateway client helpers in `dummy-companion-service.py`.
- Reuse existing behavior client `live_control_file` support for speech.
- Extend live-control JSON later for safe `intent_hint` metadata if needed.

Existing WorldAI docs describe a local LLM worker and server-side job queue.
The new AI Gateway should be compatible with that direction:

- companion dialogue uses near-real-time local service calls;
- WorldAI news/mob text can continue using DB jobs or later call the gateway;
- both paths share model policy, sanitizer, and token ledger once unified.

## Failure Handling

Fail closed:

- missing API key -> no LLM calls;
- missing LiteLLM dependency -> no LLM calls;
- disallowed model -> reject request;
- budget exceeded -> local fallback or silence;
- rate limit/quota/billing error -> disable until next day;
- invalid JSON -> fallback or silence;
- validator rejection -> fallback or silence;
- gateway down -> companion behavior continues.

Fallback speech:

- local canned tactical lines for critical events;
- no speech for idle/social events;
- local command hints may still apply for clear player commands.

## Security And Repository Policy

No real API keys in Git.

Allowed:

- Windows user environment variable `OPENAI_API_KEY`;
- process environment variables;
- ignored local operator files outside Git tracking;
- example config files with placeholder values only.

Forbidden:

- real keys in `.cs`, `.py`, `.json`, `.md`, `.bat`, `.sh`, or committed
  config files;
- echoing keys in logs;
- printing keys in test output;
- storing keys inside GameServer database rows;
- sending keys to Chrome/Gemini/other tools.

Before any commit touching AI config, run a secret scan for provider key
patterns.

## Testing

Unit tests:

- model alias allowlist accepts only small aliases;
- large model names are rejected;
- budget ledger blocks after feature and global caps;
- quota/rate-limit errors set disabled state;
- sanitizer strips forbidden raw fields;
- prompt builder uses sanitized context only;
- response validator rejects invalid channels, hints, long text, slash commands,
  and forbidden gameplay claims;
- fallback returns no LLM speech when budget is exhausted.

Integration tests:

- gateway dry-run returns deterministic fake JSON without provider calls;
- LiteLLM adapter can be mocked;
- companion service sends dialogue request for a low-health event;
- companion service writes a valid live-control `say`;
- behavior client sends the speech command from live-control;
- existing companion combat and real-player-join smoke still pass with dialogue
  disabled.

Manual smoke:

- one player role dummy and one healer companion;
- trigger low-health or explicit heal request;
- verify at most one LLM request per 5 seconds;
- verify token ledger updates;
- verify OpenAI Platform usage roughly matches local ledger;
- verify budget cap stops further calls.

## Rollout

1. Add AI Gateway config schema and example config.
2. Add token ledger and model policy with fake provider only.
3. Add LiteLLM adapter behind the gateway interface.
4. Add companion dialogue prompt and validator.
5. Add dummy companion service gateway client.
6. Add live-control speech path for party and `/say`.
7. Add local fallback lines and budget disable handling.
8. Run unit tests with fake provider.
9. Run one live companion smoke with LLM disabled.
10. Run one short live companion dialogue smoke with `small-dialogue`.
11. Compare local token ledger to provider usage page.
12. Only then raise frequency or duration.

## References

- LiteLLM docs: SDK and Proxy both provide a unified interface over many LLM
  providers, while the Proxy is intended as a central gateway with spend
  tracking, auth, and virtual keys.
- LiteLLM Virtual Keys docs: Proxy key management and spend tracking require a
  database URL and master key, which makes it a better later upgrade than the
  first local companion dialogue step.
- OpenAI data sharing/free-token help article: free daily token behavior depends
  on eligible data sharing settings and resets daily on UTC boundaries, so the
  gateway must keep its own token cap and fail closed.
