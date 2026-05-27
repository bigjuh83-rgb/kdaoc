# LiteLLM AI Gateway Companion Dialogue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LiteLLM-backed OpenDAoC AI Gateway and use it for v1 live companion dialogue with small-model-only routing, local token caps, sanitized context, and safe live-control delivery.

**Architecture:** Add a focused Python AI Gateway module/script that owns model policy, token ledger, prompt construction, LiteLLM calls, and output validation. Keep GameServer unaware of provider keys; integrate the existing `dummy-companion-service.py` through a thin local client that writes validated speech to existing behavior-client live-control files.

**Tech Stack:** Python standard library, optional `litellm` package loaded only by the provider adapter, existing `unittest` suite, existing dummy companion service, existing behavior client live-control JSON path.

---

## File Structure

- Create `tools/opendaoc-ai-gateway.py`
  - Main AI Gateway module and CLI.
  - Contains config loading, model policy, sanitizer, token ledger, fake provider, optional LiteLLM provider, companion prompt builder, response validator, and local JSON request handler.

- Create `tools/opendaoc-ai-gateway.example.json`
  - Commit-safe example config with model aliases, caps, and fake provider default.
  - Contains no real API keys.

- Create `tools/test_opendaoc_ai_gateway.py`
  - Unit tests for the gateway.
  - Uses fake provider and mocked LiteLLM adapter; no external API calls.

- Modify `tools/dummy-companion-service.py`
  - Add dialogue config flags.
  - Build sanitized companion dialogue events.
  - Call AI Gateway helper with strict cooldown and budget-aware fallback.
  - Write live-control JSON for the selected companion run directory.

- Modify `tools/test_dummy_companion_service.py`
  - Add tests for dialogue event construction, gateway call wiring, live-control writing, and disabled-mode behavior.

- Modify `tools/behavior-dummy-client.py`
  - Extend live-control speech handling from `say` only to `say_text` + `say_channel`.
  - `say_channel=party` sends `/g <message>`.
  - `say_channel=say` sends `/say <message>`.
  - Reject unknown channels by doing nothing.

- Modify `tools/test_behavior_player_follow.py`
  - Add tests around live-control party/say command formatting using a small helper extracted from behavior client.

- Optional local operator file, not committed:
  - `.opendaoc-ai-gateway.local.json`
  - This file is ignored by `.gitignore` only if the implementation creates one during local testing. Real keys still stay in environment variables.

## Implementation Tasks

### Task 1: Gateway Config And Model Policy

**Files:**
- Create: `tools/opendaoc-ai-gateway.py`
- Create: `tools/opendaoc-ai-gateway.example.json`
- Test: `tools/test_opendaoc_ai_gateway.py`

- [ ] **Step 1: Write failing tests for config defaults and model allowlist**

Add `tools/test_opendaoc_ai_gateway.py`:

```python
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATEWAY_PATH = ROOT / "tools" / "opendaoc-ai-gateway.py"


def load_gateway():
    spec = importlib.util.spec_from_file_location("opendaoc_ai_gateway", GATEWAY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OpenDaocAiGatewayConfigTests(unittest.TestCase):
    def test_default_config_uses_fake_provider_and_small_dialogue_alias(self) -> None:
        gateway = load_gateway()

        config = gateway.GatewayConfig.default()

        self.assertEqual(config.provider, "fake")
        self.assertIn("small-dialogue", config.model_aliases)
        self.assertEqual(config.model_aliases["small-dialogue"].provider_model, "fake/small-dialogue")
        self.assertEqual(config.model_aliases["small-dialogue"].max_output_tokens, 80)

    def test_model_policy_rejects_raw_large_model_names(self) -> None:
        gateway = load_gateway()
        policy = gateway.ModelPolicy(gateway.GatewayConfig.default())

        self.assertTrue(policy.is_allowed("small-dialogue", "companion_dialogue"))
        self.assertFalse(policy.is_allowed("gpt-4.1", "companion_dialogue"))
        self.assertFalse(policy.is_allowed("openai/gpt-4.1", "companion_dialogue"))
        self.assertFalse(policy.is_allowed("small-dialogue", "event_news"))

    def test_config_file_overrides_caps_without_real_keys(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gateway.json"
            path.write_text(
                "{\n"
                '  "provider": "litellm",\n'
                '  "daily_token_cap": 12345,\n'
                '  "feature_token_caps": {"companion_dialogue": 6789},\n'
                '  "model_aliases": {\n'
                '    "small-dialogue": {\n'
                '      "provider_model": "openai/gpt-4.1-nano",\n'
                '      "features": ["companion_dialogue"],\n'
                '      "max_output_tokens": 64,\n'
                '      "temperature": 0.4\n'
                "    }\n"
                "  }\n"
                "}\n",
                encoding="utf-8",
            )

            config = gateway.GatewayConfig.load(path)

        self.assertEqual(config.provider, "litellm")
        self.assertEqual(config.daily_token_cap, 12345)
        self.assertEqual(config.feature_token_caps["companion_dialogue"], 6789)
        self.assertEqual(config.model_aliases["small-dialogue"].provider_model, "openai/gpt-4.1-nano")
        self.assertEqual(config.model_aliases["small-dialogue"].max_output_tokens, 64)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test and verify it fails because the module does not exist**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_opendaoc_ai_gateway
```

Expected: FAIL with `FileNotFoundError` or module loading error for `tools/opendaoc-ai-gateway.py`.

- [ ] **Step 3: Add minimal config and policy implementation**

Create `tools/opendaoc-ai-gateway.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


VALID_FEATURES = {"companion_dialogue", "mob_dialogue", "event_news", "manual_test"}


@dataclasses.dataclass(frozen=True)
class ModelAlias:
    provider_model: str
    features: tuple[str, ...]
    max_output_tokens: int = 80
    temperature: float = 0.7

    @staticmethod
    def from_dict(row: dict[str, Any]) -> "ModelAlias":
        return ModelAlias(
            provider_model=str(row.get("provider_model") or "fake/small-dialogue"),
            features=tuple(str(value) for value in row.get("features", ["companion_dialogue"])),
            max_output_tokens=int(row.get("max_output_tokens", 80)),
            temperature=float(row.get("temperature", 0.7)),
        )


@dataclasses.dataclass(frozen=True)
class GatewayConfig:
    provider: str
    daily_token_cap: int
    warning_token_cap: int
    feature_token_caps: dict[str, int]
    model_aliases: dict[str, ModelAlias]
    usage_log: str
    ledger_file: str

    @staticmethod
    def default() -> "GatewayConfig":
        return GatewayConfig(
            provider="fake",
            daily_token_cap=500_000,
            warning_token_cap=400_000,
            feature_token_caps={
                "companion_dialogue": 350_000,
                "mob_dialogue": 100_000,
                "event_news": 30_000,
                "manual_test": 20_000,
            },
            model_aliases={
                "small-dialogue": ModelAlias(
                    provider_model="fake/small-dialogue",
                    features=("companion_dialogue",),
                    max_output_tokens=80,
                    temperature=0.7,
                )
            },
            usage_log="test-output/ai-gateway/usage.jsonl",
            ledger_file="test-output/ai-gateway/ledger.json",
        )

    @staticmethod
    def load(path: str | Path | None) -> "GatewayConfig":
        base = GatewayConfig.default()
        if not path:
            return base
        config_path = Path(path)
        if not config_path.exists():
            return base
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        aliases = {
            name: ModelAlias.from_dict(row)
            for name, row in raw.get("model_aliases", {}).items()
            if isinstance(row, dict)
        } or base.model_aliases
        return GatewayConfig(
            provider=str(raw.get("provider") or base.provider),
            daily_token_cap=int(raw.get("daily_token_cap", base.daily_token_cap)),
            warning_token_cap=int(raw.get("warning_token_cap", base.warning_token_cap)),
            feature_token_caps={
                **base.feature_token_caps,
                **{str(key): int(value) for key, value in raw.get("feature_token_caps", {}).items()},
            },
            model_aliases=aliases,
            usage_log=str(raw.get("usage_log") or base.usage_log),
            ledger_file=str(raw.get("ledger_file") or base.ledger_file),
        )


class ModelPolicy:
    def __init__(self, config: GatewayConfig) -> None:
        self.config = config

    def is_allowed(self, model_alias: str, feature: str) -> bool:
        alias = self.config.model_aliases.get(str(model_alias or ""))
        return alias is not None and feature in alias.features and feature in VALID_FEATURES
```

Create `tools/opendaoc-ai-gateway.example.json`:

```json
{
  "provider": "litellm",
  "daily_token_cap": 500000,
  "warning_token_cap": 400000,
  "feature_token_caps": {
    "companion_dialogue": 350000,
    "mob_dialogue": 100000,
    "event_news": 30000,
    "manual_test": 20000
  },
  "model_aliases": {
    "small-dialogue": {
      "provider_model": "openai/gpt-4.1-nano",
      "features": ["companion_dialogue"],
      "max_output_tokens": 80,
      "temperature": 0.7
    }
  },
  "usage_log": "test-output/ai-gateway/usage.jsonl",
  "ledger_file": "test-output/ai-gateway/ledger.json"
}
```

- [ ] **Step 4: Run config tests and verify they pass**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_opendaoc_ai_gateway.OpenDaocAiGatewayConfigTests
```

Expected: `Ran 3 tests` and `OK`.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add tools/opendaoc-ai-gateway.py tools/opendaoc-ai-gateway.example.json tools/test_opendaoc_ai_gateway.py
git commit -m "feat: add ai gateway config policy"
```

Expected: commit includes only the three listed files.

### Task 2: Sanitizer, Response Validator, And Prompt Builder

**Files:**
- Modify: `tools/opendaoc-ai-gateway.py`
- Test: `tools/test_opendaoc_ai_gateway.py`

- [ ] **Step 1: Add failing tests for sanitized context and response validation**

Append these tests before the `if __name__ == "__main__":` line:

```python
class OpenDaocAiGatewayValidationTests(unittest.TestCase):
    def test_sanitize_companion_context_removes_private_fields(self) -> None:
        gateway = load_gateway()
        payload = {
            "feature": "companion_dialogue",
            "event_type": "player_requested_heal",
            "account": "secret_account",
            "player_name": "후후",
            "x": 123,
            "y": 456,
            "raw_chat": "동료야 힐해줘",
            "role": "healer",
            "personality": "calm_support",
            "state": {
                "combat": True,
                "leader_health_band": "low",
                "adds": 2,
                "exact_position": "123,456,789",
            },
        }

        sanitized = gateway.sanitize_companion_payload(payload)

        self.assertEqual(sanitized["feature"], "companion_dialogue")
        self.assertEqual(sanitized["event_type"], "player_requested_heal")
        self.assertEqual(sanitized["role"], "healer")
        self.assertNotIn("account", sanitized)
        self.assertNotIn("player_name", sanitized)
        self.assertNotIn("raw_chat", sanitized)
        self.assertNotIn("x", sanitized)
        self.assertNotIn("exact_position", sanitized["state"])

    def test_validate_response_accepts_short_safe_json(self) -> None:
        gateway = load_gateway()

        result = gateway.validate_companion_response(
            {
                "say_channel": "party",
                "say_text": "바로 치유하겠습니다. 조금만 버텨주세요.",
                "intent_hint": "heal_priority",
                "urgency": "high",
            }
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.value["say_channel"], "party")
        self.assertEqual(result.value["intent_hint"], "heal_priority")

    def test_validate_response_rejects_unsafe_command_text(self) -> None:
        gateway = load_gateway()

        result = gateway.validate_companion_response(
            {
                "say_channel": "party",
                "say_text": "/release 하겠습니다",
                "intent_hint": "heal_priority",
                "urgency": "high",
            }
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "slash_command_in_say_text")

    def test_build_companion_prompt_uses_sanitized_json_only(self) -> None:
        gateway = load_gateway()
        sanitized = gateway.sanitize_companion_payload(
            {
                "feature": "companion_dialogue",
                "event_type": "add_detected",
                "role": "support",
                "personality": "tactical_support",
                "raw_chat": "동료야 저 좌표로 가",
                "state": {"combat": True, "adds": 2},
            }
        )

        messages = gateway.build_companion_messages(sanitized)
        combined = json.dumps(messages, ensure_ascii=False)

        self.assertIn("companion_dialogue", combined)
        self.assertIn("add_detected", combined)
        self.assertIn("support", combined)
        self.assertNotIn("저 좌표", combined)
        self.assertIn("JSON", combined)
```

- [ ] **Step 2: Run validation tests and verify they fail**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_opendaoc_ai_gateway.OpenDaocAiGatewayValidationTests
```

Expected: FAIL with missing functions such as `sanitize_companion_payload`.

- [ ] **Step 3: Add sanitizer, validator, and prompt builder**

Append to `tools/opendaoc-ai-gateway.py` after `ModelPolicy`:

```python
ALLOWED_CHANNELS = {"party", "say", "none"}
ALLOWED_HINTS = {"none", "heal_priority", "resurrect_priority", "follow", "wait", "assist", "flee", "cc_add"}
ALLOWED_URGENCY = {"low", "normal", "high"}


@dataclasses.dataclass(frozen=True)
class ValidationResult:
    allowed: bool
    value: dict[str, Any]
    reason: str = ""


def health_band(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"critical", "low", "normal", "high", "dead", "unknown"}:
        return text
    return "unknown"


def bool_value(value: Any) -> bool:
    return bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "on"}


def bounded_int(value: Any, minimum: int, maximum: int, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def sanitize_companion_payload(payload: dict[str, Any]) -> dict[str, Any]:
    state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    return {
        "feature": "companion_dialogue",
        "event_type": str(payload.get("event_type") or "status").strip()[:64],
        "realm": str(payload.get("realm") or "unknown").strip().lower()[:24],
        "role": str(payload.get("role") or "fill").strip().lower()[:24],
        "personality": str(payload.get("personality") or "steady_companion").strip().lower()[:40],
        "state": {
            "combat": bool_value(state.get("combat")),
            "leader_health_band": health_band(state.get("leader_health_band")),
            "companion_health_band": health_band(state.get("companion_health_band")),
            "companion_mana_band": health_band(state.get("companion_mana_band")),
            "adds": bounded_int(state.get("adds"), 0, 8),
            "party_dead": bounded_int(state.get("party_dead"), 0, 8),
            "player_called": bool_value(state.get("player_called")),
            "command_intent": str(state.get("command_intent") or "none").strip().lower()[:32],
        },
        "memory": str(payload.get("memory") or "").strip()[:160],
    }


def validate_companion_response(row: dict[str, Any]) -> ValidationResult:
    if not isinstance(row, dict):
        return ValidationResult(False, {}, "not_object")
    channel = str(row.get("say_channel") or "none").strip().lower()
    if channel not in ALLOWED_CHANNELS:
        return ValidationResult(False, {}, "invalid_channel")
    hint = str(row.get("intent_hint") or "none").strip().lower()
    if hint not in ALLOWED_HINTS:
        return ValidationResult(False, {}, "invalid_hint")
    urgency = str(row.get("urgency") or "normal").strip().lower()
    if urgency not in ALLOWED_URGENCY:
        return ValidationResult(False, {}, "invalid_urgency")
    text = " ".join(str(row.get("say_text") or "").split())
    if len(text) > 80:
        return ValidationResult(False, {}, "say_text_too_long")
    if text.startswith("/") or " /" in text:
        return ValidationResult(False, {}, "slash_command_in_say_text")
    lowered = text.lower()
    for forbidden in ("gold", "realm point", "drop rate", "ban", "gm", "보상", "골드", "추방"):
        if forbidden in lowered:
            return ValidationResult(False, {}, "forbidden_claim")
    return ValidationResult(
        True,
        {
            "say_channel": channel,
            "say_text": text,
            "intent_hint": hint,
            "urgency": urgency,
        },
    )


def build_companion_messages(sanitized: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "You write one short Korean line for a DAoC party companion. "
        "Return JSON only with say_channel, say_text, intent_hint, urgency. "
        "Do not include commands, coordinates, rewards, account names, or explanations."
    )
    user = json.dumps(sanitized, ensure_ascii=False, sort_keys=True)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
```

- [ ] **Step 4: Run validation tests and verify they pass**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_opendaoc_ai_gateway.OpenDaocAiGatewayValidationTests
```

Expected: `Ran 4 tests` and `OK`.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add tools/opendaoc-ai-gateway.py tools/test_opendaoc_ai_gateway.py
git commit -m "feat: validate companion dialogue payloads"
```

Expected: commit includes gateway and gateway tests only.

### Task 3: Token Ledger And Gateway Generate Flow

**Files:**
- Modify: `tools/opendaoc-ai-gateway.py`
- Test: `tools/test_opendaoc_ai_gateway.py`

- [ ] **Step 1: Add failing tests for token caps, fake provider, and usage logs**

Append these tests:

```python
class OpenDaocAiGatewayGenerationTests(unittest.TestCase):
    def test_token_ledger_blocks_after_feature_cap(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger_path = Path(temp_dir) / "ledger.json"
            config = dataclasses.replace(
                gateway.GatewayConfig.default(),
                ledger_file=str(ledger_path),
                feature_token_caps={"companion_dialogue": 10},
                daily_token_cap=100,
            )
            ledger = gateway.TokenLedger(config)

            self.assertTrue(ledger.can_spend("companion_dialogue", 10).allowed)
            ledger.record("companion_dialogue", 10)
            self.assertFalse(ledger.can_spend("companion_dialogue", 1).allowed)

    def test_fake_provider_returns_valid_companion_response(self) -> None:
        gateway = load_gateway()
        provider = gateway.FakeProvider()
        response = provider.complete(
            model="fake/small-dialogue",
            messages=[],
            max_output_tokens=80,
            temperature=0.7,
        )

        self.assertEqual(response["usage"]["total_tokens"], 42)
        self.assertEqual(response["content"]["say_channel"], "party")
        self.assertEqual(response["content"]["intent_hint"], "heal_priority")

    def test_generate_companion_dialogue_records_usage(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            usage_log = Path(temp_dir) / "usage.jsonl"
            ledger_file = Path(temp_dir) / "ledger.json"
            config = dataclasses.replace(
                gateway.GatewayConfig.default(),
                usage_log=str(usage_log),
                ledger_file=str(ledger_file),
            )
            service = gateway.AiGateway(config, provider=gateway.FakeProvider())

            result = service.generate_companion_dialogue(
                {
                    "event_type": "player_requested_heal",
                    "role": "healer",
                    "state": {"combat": True, "leader_health_band": "low", "player_called": True},
                }
            )

            self.assertTrue(result["allowed"])
            self.assertEqual(result["response"]["intent_hint"], "heal_priority")
            rows = [json.loads(line) for line in usage_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["feature"], "companion_dialogue")
            self.assertEqual(rows[0]["total_tokens"], 42)

    def test_generate_companion_dialogue_blocks_when_budget_exhausted(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = dataclasses.replace(
                gateway.GatewayConfig.default(),
                usage_log=str(Path(temp_dir) / "usage.jsonl"),
                ledger_file=str(Path(temp_dir) / "ledger.json"),
                daily_token_cap=1,
            )
            service = gateway.AiGateway(config, provider=gateway.FakeProvider())

            result = service.generate_companion_dialogue({"event_type": "status", "role": "healer"})

            self.assertFalse(result["allowed"])
            self.assertEqual(result["blocked_reason"], "global_budget_exhausted")
```

- [ ] **Step 2: Run generation tests and verify they fail**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_opendaoc_ai_gateway.OpenDaocAiGatewayGenerationTests
```

Expected: FAIL with missing `TokenLedger`, `FakeProvider`, or `AiGateway`.

- [ ] **Step 3: Implement token ledger, fake provider, and generation flow**

Add to `tools/opendaoc-ai-gateway.py`:

```python
@dataclasses.dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str = ""


def current_day_key() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


class TokenLedger:
    def __init__(self, config: GatewayConfig) -> None:
        self.config = config
        self.path = Path(config.ledger_file)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"day": current_day_key(), "features": {}, "total": 0}
        try:
            row = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"day": current_day_key(), "features": {}, "total": 0}
        if row.get("day") != current_day_key():
            return {"day": current_day_key(), "features": {}, "total": 0}
        return row

    def _save(self, row: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    def can_spend(self, feature: str, estimated_tokens: int) -> BudgetDecision:
        row = self._load()
        if int(row.get("total", 0)) + estimated_tokens > self.config.daily_token_cap:
            return BudgetDecision(False, "global_budget_exhausted")
        feature_total = int(row.get("features", {}).get(feature, 0))
        feature_cap = int(self.config.feature_token_caps.get(feature, self.config.daily_token_cap))
        if feature_total + estimated_tokens > feature_cap:
            return BudgetDecision(False, "feature_budget_exhausted")
        return BudgetDecision(True)

    def record(self, feature: str, tokens: int) -> None:
        row = self._load()
        features = dict(row.get("features", {}))
        features[feature] = int(features.get(feature, 0)) + int(tokens)
        row["features"] = features
        row["total"] = int(row.get("total", 0)) + int(tokens)
        self._save(row)


class FakeProvider:
    def complete(self, model: str, messages: list[dict[str, str]], max_output_tokens: int, temperature: float) -> dict[str, Any]:
        return {
            "content": {
                "say_channel": "party",
                "say_text": "바로 치유하겠습니다. 조금만 버텨주세요.",
                "intent_hint": "heal_priority",
                "urgency": "high",
            },
            "usage": {"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": 42},
            "provider_model": model,
        }


class AiGateway:
    def __init__(self, config: GatewayConfig, provider: Any | None = None) -> None:
        self.config = config
        self.policy = ModelPolicy(config)
        self.ledger = TokenLedger(config)
        self.provider = provider if provider is not None else FakeProvider()

    def _log_usage(self, row: dict[str, Any]) -> None:
        path = Path(self.config.usage_log)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    def generate_companion_dialogue(self, payload: dict[str, Any], model_alias: str = "small-dialogue") -> dict[str, Any]:
        feature = "companion_dialogue"
        if not self.policy.is_allowed(model_alias, feature):
            return {"allowed": False, "blocked_reason": "model_not_allowed"}
        budget = self.ledger.can_spend(feature, 64)
        if not budget.allowed:
            return {"allowed": False, "blocked_reason": budget.reason}
        alias = self.config.model_aliases[model_alias]
        sanitized = sanitize_companion_payload(payload)
        messages = build_companion_messages(sanitized)
        started = time.monotonic()
        try:
            provider_response = self.provider.complete(
                model=alias.provider_model,
                messages=messages,
                max_output_tokens=alias.max_output_tokens,
                temperature=alias.temperature,
            )
        except Exception as exc:
            return {"allowed": False, "blocked_reason": "provider_error", "error": exc.__class__.__name__}
        usage = provider_response.get("usage", {})
        total_tokens = int(usage.get("total_tokens") or usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0) or 0)
        validation = validate_companion_response(provider_response.get("content", {}))
        self.ledger.record(feature, total_tokens)
        self._log_usage(
            {
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "feature": feature,
                "model_alias": model_alias,
                "provider_model": alias.provider_model,
                "event_type": sanitized.get("event_type", ""),
                "companion_role": sanitized.get("role", ""),
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "total_tokens": total_tokens,
                "blocked_reason": "" if validation.allowed else validation.reason,
                "latency_ms": int((time.monotonic() - started) * 1000),
            }
        )
        if not validation.allowed:
            return {"allowed": False, "blocked_reason": validation.reason}
        return {"allowed": True, "response": validation.value, "usage": usage}
```

- [ ] **Step 4: Run generation tests and verify they pass**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_opendaoc_ai_gateway.OpenDaocAiGatewayGenerationTests
```

Expected: `Ran 4 tests` and `OK`.

- [ ] **Step 5: Commit Task 3**

Run:

```powershell
git add tools/opendaoc-ai-gateway.py tools/test_opendaoc_ai_gateway.py
git commit -m "feat: add ai gateway token ledger"
```

Expected: commit includes gateway and gateway tests only.

### Task 4: LiteLLM Adapter And CLI

**Files:**
- Modify: `tools/opendaoc-ai-gateway.py`
- Test: `tools/test_opendaoc_ai_gateway.py`

- [ ] **Step 1: Add failing tests for LiteLLM adapter and CLI JSON mode**

Append:

```python
class OpenDaocAiGatewayCliTests(unittest.TestCase):
    def test_litellm_provider_parses_json_content_and_usage(self) -> None:
        gateway = load_gateway()

        class FakeLiteLLM:
            @staticmethod
            def completion(**kwargs):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"say_channel":"party","say_text":"알겠습니다. 지원하겠습니다.",'
                                    '"intent_hint":"assist","urgency":"normal"}'
                                )
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
                }

        provider = gateway.LiteLlmProvider(litellm_module=FakeLiteLLM)
        result = provider.complete("openai/gpt-4.1-nano", [], 80, 0.7)

        self.assertEqual(result["content"]["intent_hint"], "assist")
        self.assertEqual(result["usage"]["total_tokens"], 18)

    def test_cli_generate_returns_json_without_external_provider_in_fake_mode(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "gateway.json"
            config_path.write_text(
                json.dumps(
                    {
                        "provider": "fake",
                        "usage_log": str(Path(temp_dir) / "usage.jsonl"),
                        "ledger_file": str(Path(temp_dir) / "ledger.json"),
                    }
                ),
                encoding="utf-8",
            )
            payload = json.dumps({"event_type": "player_requested_heal", "role": "healer"})

            rc, output = gateway.run_cli(
                ["generate", "--config", str(config_path), "--feature", "companion_dialogue", "--payload-json", payload]
            )

        self.assertEqual(rc, 0)
        row = json.loads(output)
        self.assertTrue(row["allowed"])
        self.assertEqual(row["response"]["say_channel"], "party")
```

- [ ] **Step 2: Run CLI tests and verify they fail**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_opendaoc_ai_gateway.OpenDaocAiGatewayCliTests
```

Expected: FAIL with missing `LiteLlmProvider` and `run_cli`.

- [ ] **Step 3: Implement LiteLLM adapter and CLI**

Add:

```python
class LiteLlmProvider:
    def __init__(self, litellm_module: Any | None = None) -> None:
        if litellm_module is None:
            import litellm as litellm_module
        self.litellm = litellm_module

    def complete(self, model: str, messages: list[dict[str, str]], max_output_tokens: int, temperature: float) -> dict[str, Any]:
        response = self.litellm.completion(
            model=model,
            messages=messages,
            max_tokens=max_output_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        choice = response["choices"][0]["message"]["content"]
        content = json.loads(choice) if isinstance(choice, str) else dict(choice)
        usage = response.get("usage", {})
        return {
            "content": content,
            "usage": {
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
            },
            "provider_model": model,
        }


def provider_from_config(config: GatewayConfig) -> Any:
    if config.provider == "litellm":
        return LiteLlmProvider()
    return FakeProvider()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenDAoC local AI Gateway.")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--config", default="")
    gen.add_argument("--feature", default="companion_dialogue")
    gen.add_argument("--model-alias", default="small-dialogue")
    gen.add_argument("--payload-json", default="{}")
    return parser


def run_cli(argv: list[str] | None = None) -> tuple[int, str]:
    args = build_parser().parse_args(argv)
    config = GatewayConfig.load(args.config)
    service = AiGateway(config, provider=provider_from_config(config))
    payload = json.loads(args.payload_json)
    if args.feature != "companion_dialogue":
        output = {"allowed": False, "blocked_reason": "unsupported_feature"}
    else:
        output = service.generate_companion_dialogue(payload, model_alias=args.model_alias)
    return 0, json.dumps(output, ensure_ascii=False, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    rc, output = run_cli(argv)
    print(output)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
```

Remove the old bottom `if __name__ == "__main__":` block from the test file only if duplicate execution blocks appear in the test file. The gateway file should have one final `main` block.

- [ ] **Step 4: Run CLI tests and verify they pass**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_opendaoc_ai_gateway.OpenDaocAiGatewayCliTests
```

Expected: `Ran 2 tests` and `OK`.

- [ ] **Step 5: Run all gateway tests**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_opendaoc_ai_gateway
```

Expected: all gateway tests pass.

- [ ] **Step 6: Commit Task 4**

Run:

```powershell
git add tools/opendaoc-ai-gateway.py tools/test_opendaoc_ai_gateway.py
git commit -m "feat: add litellm ai gateway cli"
```

Expected: commit includes gateway and gateway tests only.

### Task 5: Behavior Client Live-Control Channels

**Files:**
- Modify: `tools/behavior-dummy-client.py`
- Modify: `tools/test_behavior_player_follow.py`

- [ ] **Step 1: Add failing tests for live-control channel command formatting**

Add to `tools/test_behavior_player_follow.py` near other small helper tests:

```python
class LiveControlSpeechCommandTests(unittest.TestCase):
    def test_live_control_party_speech_uses_group_chat(self) -> None:
        behavior = load_behavior()

        self.assertEqual(
            behavior.live_control_speech_command({"say_channel": "party", "say_text": "바로 지원하겠습니다."}),
            "/g 바로 지원하겠습니다.",
        )

    def test_live_control_say_speech_uses_say(self) -> None:
        behavior = load_behavior()

        self.assertEqual(
            behavior.live_control_speech_command({"say_channel": "say", "say_text": "잠깐 숨을 고르겠습니다."}),
            "/say 잠깐 숨을 고르겠습니다.",
        )

    def test_live_control_legacy_say_field_still_works(self) -> None:
        behavior = load_behavior()

        self.assertEqual(
            behavior.live_control_speech_command({"say": "따라가겠습니다."}),
            "/say 따라가겠습니다.",
        )

    def test_live_control_unknown_channel_is_ignored(self) -> None:
        behavior = load_behavior()

        self.assertEqual(
            behavior.live_control_speech_command({"say_channel": "guild", "say_text": "안전하지 않음"}),
            "",
        )
```

If the file does not already expose `load_behavior`, reuse the existing module loader used by other tests in that file.

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_behavior_player_follow.LiveControlSpeechCommandTests
```

Expected: FAIL with missing `live_control_speech_command`.

- [ ] **Step 3: Add speech command helper**

Add near `format_say_command` in `tools/behavior-dummy-client.py`:

```python
def live_control_speech_command(payload: dict[str, object]) -> str:
    text = str(payload.get("say_text") or payload.get("say") or "").strip()
    if not text:
        return ""
    channel = str(payload.get("say_channel") or ("say" if payload.get("say") else "say")).strip().lower()
    if channel == "party":
        message = " ".join(text.split())[:120]
        return f"/g {message}" if message else ""
    if channel == "say":
        return format_say_command(text)
    if channel == "none":
        return ""
    return ""
```

- [ ] **Step 4: Use helper in live-control handling**

Replace this block in the live-control section:

```python
say_text = live_payload.get("say", "")
if isinstance(say_text, str) and say_text.strip():
    client.send_command(format_say_command(say_text))
    sent_commands.append("/say")
    actions += add_action(action_counts, "live_control_say")
```

with:

```python
speech_command = live_control_speech_command(live_payload)
if speech_command:
    client.send_command(speech_command)
    sent_commands.append(speech_command.split(" ", 1)[0])
    actions += add_action(action_counts, "live_control_say")
    if speech_command.startswith("/g "):
        actions += add_action(action_counts, "live_control_party_say")
```

- [ ] **Step 5: Run speech tests and focused behavior tests**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_behavior_player_follow.LiveControlSpeechCommandTests
```

Expected: new speech tests pass.

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m py_compile tools/behavior-dummy-client.py
```

Expected: no output and exit code 0.

- [ ] **Step 6: Commit Task 5**

Run:

```powershell
git add tools/behavior-dummy-client.py tools/test_behavior_player_follow.py
git commit -m "feat: support live control party speech"
```

Expected: commit includes behavior client and behavior tests only.

### Task 6: Companion Service Dialogue Client

**Files:**
- Modify: `tools/dummy-companion-service.py`
- Modify: `tools/test_dummy_companion_service.py`

- [ ] **Step 1: Add failing tests for dialogue payloads and live-control writes**

Add to `DummyCompanionServiceTests`:

```python
    def test_dialogue_payload_uses_sanitized_state_only(self) -> None:
        service = load_service()
        companion = service.ActiveCompanion(
            {"id": "req1", "requesterName": "LeaderName", "requesterAccount": "leader1", "requestedRole": "healer"},
            mock.Mock(),
            account="albhealer",
        )
        requester_state = {
            "player": {"name": "LeaderName", "account": "leader1", "healthPercent": 31, "inCombat": True},
            "groupMembers": [{"name": "LeaderName", "account": "leader1"}],
            "npcs": [],
        }

        payload = service.build_companion_dialogue_payload(companion, requester_state, "player_requested_heal")

        self.assertEqual(payload["feature"], "companion_dialogue")
        self.assertEqual(payload["event_type"], "player_requested_heal")
        self.assertEqual(payload["role"], "healer")
        self.assertEqual(payload["state"]["leader_health_band"], "low")
        self.assertNotIn("requesterAccount", payload)
        self.assertNotIn("LeaderName", json.dumps(payload, ensure_ascii=False))

    def test_write_companion_live_control_writes_party_speech(self) -> None:
        service = load_service()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "req1" / "control.json"
            service.write_companion_live_control(
                path,
                {"say_channel": "party", "say_text": "바로 지원하겠습니다.", "intent_hint": "assist", "urgency": "normal"},
            )
            row = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(row["say_channel"], "party")
        self.assertEqual(row["say_text"], "바로 지원하겠습니다.")
        self.assertEqual(row["intent_hint"], "assist")

    def test_request_dialogue_skips_when_disabled(self) -> None:
        service = load_service()
        args = mock.Mock(dialogue_enabled=False)
        result = service.request_companion_dialogue(args, {}, Path("control.json"))

        self.assertFalse(result)

    def test_request_dialogue_calls_gateway_and_writes_allowed_response(self) -> None:
        service = load_service()
        args = mock.Mock(dialogue_enabled=True, ai_gateway_config="", ai_gateway_model_alias="small-dialogue")
        response = {
            "allowed": True,
            "response": {
                "say_channel": "party",
                "say_text": "바로 지원하겠습니다.",
                "intent_hint": "assist",
                "urgency": "normal",
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            control = Path(temp_dir) / "control.json"
            with mock.patch.object(service, "call_ai_gateway", return_value=response) as call:
                result = service.request_companion_dialogue(args, {"event_type": "add_detected"}, control)
            row = json.loads(control.read_text(encoding="utf-8"))

        self.assertTrue(result)
        call.assert_called_once()
        self.assertEqual(row["say_text"], "바로 지원하겠습니다.")
```

Add `import json` near the top of `tools/test_dummy_companion_service.py` if it is not already imported.

- [ ] **Step 2: Run companion dialogue tests and verify they fail**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_dummy_companion_service.DummyCompanionServiceTests
```

Expected: FAIL with missing dialogue helper functions.

- [ ] **Step 3: Add dialogue helper functions**

Add to `tools/dummy-companion-service.py` after API helpers:

```python
def health_band_from_percent(value: Any) -> str:
    try:
        percent = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if percent <= 0:
        return "dead"
    if percent < 30:
        return "critical"
    if percent < 55:
        return "low"
    if percent < 85:
        return "normal"
    return "high"


def companion_personality_for_role(role: Any) -> str:
    role = normalize_role(role)
    return {
        "tank": "steady_protector",
        "healer": "calm_support",
        "support": "tactical_support",
        "dps": "confident_striker",
        "fill": "steady_companion",
    }.get(role, "steady_companion")


def build_companion_dialogue_payload(
    companion: ActiveCompanion,
    requester_state: dict[str, Any] | None,
    event_type: str,
) -> dict[str, Any]:
    player = requester_state.get("player", {}) if isinstance(requester_state, dict) else {}
    role = request_value(companion.request, "requestedRole", "RequestedRole", default="fill")
    return {
        "feature": "companion_dialogue",
        "event_type": str(event_type or "status"),
        "realm": str(request_value(companion.request, "realm", "Realm", default="unknown")),
        "role": normalize_role(role),
        "personality": companion_personality_for_role(role),
        "state": {
            "combat": bool(player.get("inCombat")),
            "leader_health_band": health_band_from_percent(player.get("healthPercent")),
            "companion_health_band": "unknown",
            "companion_mana_band": "unknown",
            "adds": 0,
            "party_dead": 0,
            "player_called": event_type.startswith("player_requested_"),
            "command_intent": "heal_priority" if event_type == "player_requested_heal" else "none",
        },
        "memory": "",
    }


def write_companion_live_control(path: Path, response: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "revision": int(time.time() * 1000),
        "say_channel": str(response.get("say_channel") or "none"),
        "say_text": str(response.get("say_text") or ""),
        "intent_hint": str(response.get("intent_hint") or "none"),
        "urgency": str(response.get("urgency") or "normal"),
    }
    path.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def call_ai_gateway(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    command = [
        sys.executable,
        "tools/opendaoc-ai-gateway.py",
        "generate",
        "--feature",
        "companion_dialogue",
        "--model-alias",
        str(getattr(args, "ai_gateway_model_alias", "small-dialogue") or "small-dialogue"),
        "--payload-json",
        json.dumps(payload, ensure_ascii=False),
    ]
    config = str(getattr(args, "ai_gateway_config", "") or "")
    if config:
        command[3:3] = ["--config", config]
    completed = subprocess.run(command, cwd=getattr(args, "repo_root", ROOT), text=True, capture_output=True, timeout=5)
    if completed.returncode != 0:
        return {"allowed": False, "blocked_reason": "gateway_process_failed"}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"allowed": False, "blocked_reason": "gateway_invalid_stdout"}


def request_companion_dialogue(args: argparse.Namespace, payload: dict[str, Any], control_path: Path) -> bool:
    if not getattr(args, "dialogue_enabled", False):
        return False
    result = call_ai_gateway(args, payload)
    if not result.get("allowed"):
        return False
    response = result.get("response")
    if not isinstance(response, dict):
        return False
    write_companion_live_control(control_path, response)
    return True
```

If `ROOT` is not defined in `dummy-companion-service.py`, add:

```python
ROOT = Path(__file__).resolve().parents[1]
```

near the existing path constants.

- [ ] **Step 4: Add parser flags**

Add to `build_parser()`:

```python
    parser.add_argument("--dialogue-enabled", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--ai-gateway-config", default="")
    parser.add_argument("--ai-gateway-model-alias", default="small-dialogue")
    parser.add_argument("--dialogue-min-interval", type=float, default=5.0)
```

- [ ] **Step 5: Run companion service tests**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_dummy_companion_service.DummyCompanionServiceTests
```

Expected: companion service tests pass.

- [ ] **Step 6: Commit Task 6**

Run:

```powershell
git add tools/dummy-companion-service.py tools/test_dummy_companion_service.py
git commit -m "feat: add companion dialogue gateway client"
```

Expected: commit includes companion service and tests only.

### Task 7: Wire Dialogue Into Active Companion Polling

**Files:**
- Modify: `tools/dummy-companion-service.py`
- Modify: `tools/test_dummy_companion_service.py`

- [ ] **Step 1: Add failing test for active polling dialogue event**

Add:

```python
    def test_poll_active_requests_dialogue_for_low_health_requester(self) -> None:
        service = load_service()
        args = mock.Mock(dialogue_enabled=True, dialogue_min_interval=5.0)
        process = mock.Mock()
        process.poll.return_value = None
        active = {
            "req1": service.ActiveCompanion(
                {"id": "req1", "requesterAccount": "leader1", "requestedRole": "healer"},
                process,
                account="albhealer",
            )
        }
        state = {"player": {"healthPercent": 41, "inCombat": True, "isAlive": True, "isDead": False}}
        dialogue_state = {}

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "request_companion_dialogue", return_value=True
        ) as request_dialogue:
            service.poll_active(args, active, release_counts={}, dialogue_state=dialogue_state)

        request_dialogue.assert_called_once()
        self.assertIn("req1:low_health", dialogue_state)
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_dummy_companion_service.DummyCompanionServiceTests.test_poll_active_requests_dialogue_for_low_health_requester
```

Expected: FAIL because `poll_active` does not accept `dialogue_state`.

- [ ] **Step 3: Add dialogue event selection and control path**

Add:

```python
def companion_control_path(args: argparse.Namespace, request_id: str) -> Path:
    return Path(args.run_dir) / request_id / "live-control.json"


def should_emit_dialogue(dialogue_state: dict[str, float], key: str, now: float, interval: float) -> bool:
    previous = float(dialogue_state.get(key, 0.0) or 0.0)
    if now - previous < max(0.0, interval):
        return False
    dialogue_state[key] = now
    return True


def dialogue_event_for_requester_state(requester_state: dict[str, Any] | None) -> str:
    player = requester_state.get("player", {}) if isinstance(requester_state, dict) else {}
    try:
        hp = float(player.get("healthPercent") or 100)
    except (TypeError, ValueError):
        hp = 100
    if bool(player.get("inCombat")) and hp < 55:
        return "player_requested_heal"
    return ""
```

Update `poll_active` signature:

```python
def poll_active(
    args: argparse.Namespace,
    active: dict[str, ActiveCompanion],
    release_counts: dict[str, int] | None = None,
    dialogue_state: dict[str, float] | None = None,
) -> None:
```

Inside the live-process branch after requester offline check:

```python
            dialogue_state = dialogue_state if dialogue_state is not None else {}
            event_type = dialogue_event_for_requester_state(requester_state)
            if event_type:
                dialogue_key = f"{request_id}:low_health"
                if should_emit_dialogue(dialogue_state, dialogue_key, time.monotonic(), getattr(args, "dialogue_min_interval", 5.0)):
                    payload = build_companion_dialogue_payload(companion, requester_state, event_type)
                    request_companion_dialogue(args, payload, companion_control_path(args, request_id))
```

In `main`, create and pass:

```python
    dialogue_state: dict[str, float] = {}
```

and call:

```python
            poll_active(args, active, release_counts, dialogue_state)
```

for both polling calls.

- [ ] **Step 4: Ensure behavior command receives live-control file path**

In `build_behavior_command`, add these flags to the returned command:

```python
        "--live-control-file",
        str(run_path / "live-control.json"),
        "--live-control-interval",
        "0.5",
```

Add an assertion to `test_behavior_command_follows_real_player_and_disables_autoloot`:

```python
        self.assertIn("--live-control-file", command)
        self.assertTrue(command[command.index("--live-control-file") + 1].endswith("live-control.json"))
```

- [ ] **Step 5: Run companion tests**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_dummy_companion_service
```

Expected: all companion service tests pass.

- [ ] **Step 6: Commit Task 7**

Run:

```powershell
git add tools/dummy-companion-service.py tools/test_dummy_companion_service.py
git commit -m "feat: trigger companion dialogue events"
```

Expected: commit includes companion service and tests only.

### Task 8: Dependency And Secret Safety Checks

**Files:**
- Modify: `docs/superpowers/specs/2026-05-27-litellm-ai-gateway-companion-dialogue-design.md` only if a tiny clarification is needed
- No required code file changes

- [ ] **Step 1: Confirm LiteLLM import behavior without dependency**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 tools/opendaoc-ai-gateway.py generate --feature companion_dialogue --payload-json '{"event_type":"player_requested_heal","role":"healer"}'
```

Expected: fake provider returns JSON and does not require `litellm`.

- [ ] **Step 2: Secret scan staged and working tree changes**

Run:

```powershell
git grep -n -E "provider secret pattern|api key assignment|google ai key pattern" -- ':!docs/superpowers/specs/2026-05-27-litellm-ai-gateway-companion-dialogue-design.md'
```

Expected: no real key values. The command may exit 1 when there are no matches.

Run:

```powershell
git status --short -- .env .opendaoc-ai-gateway.local.json tools/opendaoc-ai-gateway.example.json
```

Expected: `.env` and `.opendaoc-ai-gateway.local.json` are not staged; example config may be tracked.

- [ ] **Step 3: Optional LiteLLM install check for local runtime**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 - <<'PY'
try:
    import litellm
except Exception as exc:
    print("LITELLM_NOT_AVAILABLE", exc.__class__.__name__)
else:
    print("LITELLM_AVAILABLE", getattr(litellm, "__version__", "unknown"))
PY
```

Expected: either `LITELLM_AVAILABLE ...` or `LITELLM_NOT_AVAILABLE ModuleNotFoundError`. A missing package is acceptable until the first real provider smoke; fake-provider tests must still pass.

### Task 9: Full Regression And Build Verification

**Files:**
- No planned edits

- [ ] **Step 1: Run Python compile**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m py_compile tools/opendaoc-ai-gateway.py tools/dummy-companion-service.py tools/behavior-dummy-client.py tools/run-live-companion-party-smoke.py
```

Expected: no output and exit code 0.

- [ ] **Step 2: Run focused Python tests**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_opendaoc_ai_gateway tools.test_dummy_companion_service tools.test_behavior_player_follow
```

Expected: all focused tests pass.

- [ ] **Step 3: Run existing broader Python regression**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_behavior_player_follow tools.test_dummy_companion_service tools.test_dummy_growth_suite tools.test_operational_scripts
```

Expected: all tests pass.

- [ ] **Step 4: Build GameServer only if C# files changed during execution**

If no C# files were changed in this implementation, skip this step and state that the build was not needed. If C# files changed, run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec bash tools/build-main-server.sh
```

Expected: `0 Error(s)`.

- [ ] **Step 5: Check server status**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec bash tools/check-main-server-fast.sh
```

Expected:

```text
OK tcp 10300
OK udp 10400
OK db 3306
```

- [ ] **Step 6: Commit verification-safe final state**

Run:

```powershell
git status --short
```

Expected: only intentional changes remain. If the implementation tasks already committed all changed files, do not create an empty commit.

### Task 10: Short Live Smoke With LLM Disabled

**Files:**
- No planned edits unless the smoke reveals a bug

- [ ] **Step 1: Run live companion smoke with dialogue disabled**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 tools/run-live-companion-party-smoke.py --replace --real-player-join --roles healer --leader-hold 75 --leader-startup-delay 15 --companion-hold 45 --service-max-runtime 60 --request-active-timeout 40 --release-timeout 35 --joiner-hold 35 --joiner-startup-delay 1 --joiner-invite-delay 2 --login-retries 10 --login-retry-delay 2
```

Expected:

- exit code 0;
- request becomes active;
- real-player join release still works;
- companion behavior still records damage or healing;
- no gateway process is required.

- [ ] **Step 2: Inspect for leftover processes**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec bash -lc "pgrep -af 'behavior-dummy-client.py|dummy-companion-service.py|run-live-companion-party-smoke.py|opendaoc-ai-gateway.py' || true"
```

Expected: no long-running test processes remain.

### Task 11: Short Fake Dialogue Smoke

**Files:**
- No planned edits unless the smoke reveals a bug

- [ ] **Step 1: Run gateway fake provider manually**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 tools/opendaoc-ai-gateway.py generate --feature companion_dialogue --payload-json '{"event_type":"player_requested_heal","role":"healer","state":{"combat":true,"leader_health_band":"low","player_called":true}}'
```

Expected JSON:

```json
{"allowed": true, "response": {"intent_hint": "heal_priority", "say_channel": "party", "say_text": "바로 치유하겠습니다. 조금만 버텨주세요.", "urgency": "high"}, "usage": {"completion_tokens": 12, "prompt_tokens": 30, "total_tokens": 42}}
```

The exact field order may differ.

- [ ] **Step 2: Verify usage ledger exists and has no secrets**

Run:

```powershell
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec bash -lc "tail -n 3 test-output/ai-gateway/usage.jsonl | grep -E 'OPENAI_API_KEY|api_key|secret' && exit 1 || exit 0"
```

Expected: exit code 0.

### Task 12: Real LiteLLM Smoke With Hard Guard

**Files:**
- No planned edits unless the smoke reveals a bug

- [ ] **Step 1: Confirm operator key is only in environment**

Run:

```powershell
$hasUserKey = [bool][Environment]::GetEnvironmentVariable('OPENAI_API_KEY', 'User')
$hasProcessKey = [bool]$env:OPENAI_API_KEY
"user_key_set=$hasUserKey process_key_set=$hasProcessKey"
```

Expected: at least one value is `True`. Do not print the key.

- [ ] **Step 2: Run a single real-provider call with tiny cap**

Create a temporary config outside the repository or under `test-output`:

```powershell
$config = 'C:\Users\uihan\Desktop\다옥프리서버\OpenDAoC-Core\test-output\ai-gateway\real-smoke-config.json'
New-Item -ItemType Directory -Force -Path (Split-Path $config) | Out-Null
@'
{
  "provider": "litellm",
  "daily_token_cap": 1000,
  "warning_token_cap": 800,
  "feature_token_caps": {"companion_dialogue": 1000},
  "model_aliases": {
    "small-dialogue": {
      "provider_model": "openai/gpt-4.1-nano",
      "features": ["companion_dialogue"],
      "max_output_tokens": 60,
      "temperature": 0.4
    }
  },
  "usage_log": "test-output/ai-gateway/real-smoke-usage.jsonl",
  "ledger_file": "test-output/ai-gateway/real-smoke-ledger.json"
}
'@ | Set-Content -LiteralPath $config -Encoding UTF8
& 'C:\Windows\System32\wsl.exe' --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 tools/opendaoc-ai-gateway.py generate --config test-output/ai-gateway/real-smoke-config.json --feature companion_dialogue --payload-json '{"event_type":"player_requested_heal","role":"healer","state":{"combat":true,"leader_health_band":"low","player_called":true}}'
```

Expected:

- If `litellm` is installed and the environment key is visible to WSL, output has `"allowed": true`.
- If `litellm` is missing, output or error clearly indicates dependency missing. Install is a separate operator step.
- If WSL cannot see the Windows user environment variable, set it only for the current process before retrying. Do not write it to repo files.

- [ ] **Step 3: Compare local ledger to provider usage page**

OpenAI Platform usage should show a tiny request. Local `real-smoke-usage.jsonl`
should show the same order of magnitude for total tokens.

Expected: one small request, far below 1000 tokens.

## Completion Criteria

This implementation is complete when:

- `tools/opendaoc-ai-gateway.py` supports fake provider and LiteLLM adapter.
- Real provider mode is disabled unless explicitly configured.
- No real provider key exists in repository files.
- Model alias allowlist blocks raw large model names.
- Token ledger blocks after global and feature caps.
- Companion dialogue payloads contain only sanitized summary data.
- Model output is schema-validated before use.
- Behavior client can send both `/g` and `/say` via live-control.
- Dummy companion service can request dialogue and write live-control speech.
- Existing dummy growth and companion regression tests pass.
- LLM-disabled live companion smoke still passes.
- One tiny real LiteLLM smoke can be run or a clear dependency/environment blocker is recorded.

## Rollback Plan

If dialogue integration causes runtime issues:

1. Run companion service without `--dialogue-enabled`.
2. Keep `tools/opendaoc-ai-gateway.py` unused.
3. Existing live companion combat, follow, attach, release, and growth tests should continue to work.
4. Revert only the dialogue commits if needed; do not revert unrelated dummy FSM or companion lifecycle changes.
