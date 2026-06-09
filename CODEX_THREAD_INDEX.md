# OpenDAoC-Core Thread Index

Use this file first when splitting work into Codex threads.

## Default Workflow

1. Keep one lightweight control thread.
2. For real work, open a topic thread.
3. In the new thread, paste:

```text
OpenDAoC-Core 작업을 이어간다. 먼저 CODEX_THREADS/<topic-file>.md를 읽고 그 범위만 진행해줘.
```

4. Replace `<topic-file>` with one of the files below.
5. When topic work ends, ask the topic thread for a control-thread report.

## Which Thread Should I Use?

| If the work is about... | Use |
| --- | --- |
| Priority, next steps, final reports, task split | `CODEX_THREADS/00-control.md` |
| Companion recruiter, service, commands, dialogue, real player party | `CODEX_THREADS/01-companion-system.md` |
| Rewind, floating, Z mismatch, movement audit, catchup/teleport | `CODEX_THREADS/02-movement-rewind.md` |
| FSM, target gate, aggro, flee, heal/res/cure/CC, skills | `CODEX_THREADS/03-combat-ai-fsm.md` |
| L1-L50 growth, train, gear, death/recover, growth monster regression | `CODEX_THREADS/04-growth-tests.md` |
| RvR, frontier, siege, realm target safety, reward policy | `CODEX_THREADS/05-rvr-frontier.md` |
| Korean UI, fonts, `@` glyphs, assets.xml | `CODEX_THREADS/06-korean-client-ui.md` |
| WSL, startup scripts, LiteLLM, API quotas, secrets | `CODEX_THREADS/07-operations-api.md` |

## Control Thread Report Request

Use this when a topic thread finishes work:

```text
총괄 스레드에 붙일 보고서로 정리해줘.
형식:
## Topic
## Changed files
## Tests run
## Result
## Remaining risk
## Recommended next step
```

## External Worker Rule

Cursor and Antigravity are not the default workflow.

Use them only when:
- Codex quota is low.
- The user explicitly asks to use them.
- A long external handoff is necessary while Codex is unavailable.

Otherwise Codex should work directly and use Codex subagents for parallel subtasks.

## Existing Reference Files

- `CODEX_THREAD_OPERATING_GUIDE.md`: detailed operating rules.
- `CODEX_THREAD_STARTERS.md`: copy/paste starter prompts.
- `CODEX_CURRENT_PROJECT_STATUS.md`: compact current project status.
- `CODEX_THREADS/README.md`: per-topic handoff overview.
