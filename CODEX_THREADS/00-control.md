# OpenDAoC-Core Control Thread

## Mission

Use this thread for project control only:
- Overall priority
- Topic routing
- Final report review
- Cross-topic decisions
- Codex subagent coordination
- Cursor/Antigravity handoff only when Codex quota is low or explicitly requested

## Current Project Snapshot

Read:
- `CODEX_CURRENT_PROJECT_STATUS.md`
- `CODEX_THREAD_OPERATING_GUIDE.md`
- `CODEX_THREAD_STARTERS.md`

## Operating Rules

- Keep implementation logs in topic-specific threads.
- Keep this thread compact.
- If a topic becomes large, move it to the matching `CODEX_THREADS/*.md` topic.
- Prefer Codex subagents over Cursor/Antigravity for parallel work.
- Cursor/Antigravity are fallback workers, not the default path.

## Recommended Next Topics

1. Operations/API: make companion service startup wait for server API readiness.
2. Movement/Rewind: create movement-command smoke when the user wants to resume movement work.
3. Companion System: in-game recruiter UX and real-player join release polish.

## Report Format

```text
## Topic
## Changed files
## Tests run
## Result
## Remaining risk
## Recommended next step
```
