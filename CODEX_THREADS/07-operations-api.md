# OpenDAoC-Core Operations And API Thread

## Scope

- WSL stability
- Server startup/restart
- Companion service startup
- LiteLLM/OpenAI/Gemini routing
- API free quota and cost guardrails
- Secret handling

## Rules

- Never print or commit API keys, tokens, passwords, or secrets.
- Paid API use must stay below free quota or be disabled.
- Start/restart main server only with `start-main-server-visible.bat`.
- Check server with `tools/check-main-server-fast.sh` or `check-main-server-fast.bat`.
- Repeated PowerShell work should use `.ps1` files, not fragile inline quoting.

## Main Files

- `start-main-server-visible.bat`
- `start-live-companion-service-visible.bat`
- `tools/start-main-visible-server.sh`
- `tools/start-live-companion-service.sh`
- `tools/opendaoc-ai-gateway.py`
- `tools/opendaoc-ai-gateway.json`
- `tools/test_opendaoc_ai_gateway.py`
- `tools/test_operational_scripts.py`

## Known Facts

- Current WSL service name is `WSLService`, not `LxssManager`.
- WSL version observed: 2.7.3.0.
- Companion service has failed with `ConnectionRefusedError` when started before server API readiness.
- LiteLLM is planned as the model routing layer.
- Secrets must live outside the public repo or in local-only ignored config.

## Next Work

1. Done: companion service startup waits/retries server API readiness by default.
2. Done: visible main server startup now starts a PowerShell API waiter, which launches the visible companion service only after API readiness.
3. Done: API gateway config loading rejects embedded secret fields.
4. Done: checked-in AI gateway config defaults to fake provider and documents local paid-provider opt-in guardrails.
