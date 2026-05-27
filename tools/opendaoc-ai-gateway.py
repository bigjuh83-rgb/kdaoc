#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable


VALID_FEATURES = {"companion_dialogue", "mob_dialogue", "event_news", "manual_test"}
ALLOWED_CHANNELS = {"party", "say", "none"}
ALLOWED_HINTS = {"none", "heal_priority", "resurrect_priority", "follow", "wait", "assist", "flee", "cc_add"}
ALLOWED_URGENCY = {"low", "normal", "high"}
DEFAULT_FAKE_USAGE = {"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": 42}

litellm_completion: Callable[..., Any] | None = None


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


@dataclasses.dataclass(frozen=True)
class ValidationResult:
    allowed: bool
    value: dict[str, Any]
    reason: str = ""


@dataclasses.dataclass(frozen=True)
class ProviderResult:
    response: dict[str, Any]
    usage: dict[str, int]


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def bounded_int(value: Any, minimum: int, maximum: int, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def health_band(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"critical", "low", "normal", "high", "dead", "unknown"}:
        return text
    return "unknown"


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
    if text.startswith("/") or "\n/" in text or " /" in text:
        return ValidationResult(False, {}, "slash_command_in_say_text")
    lowered = text.lower()
    forbidden = ("gold", "realm point", "drop rate", "ban", "gm", "\ubcf4\uc0c1", "\uace8\ub4dc", "\ucd94\ubc29")
    if any(word in lowered for word in forbidden):
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


def estimate_tokens(messages: list[dict[str, str]], max_output_tokens: int) -> int:
    chars = sum(len(message.get("content", "")) for message in messages)
    return max_output_tokens + max(1, chars // 4)


class TokenLedger:
    def __init__(self, config: GatewayConfig, now: float | None = None) -> None:
        self.config = config
        self.now = time.time() if now is None else now
        self.path = Path(config.ledger_file)
        self.usage_path = Path(config.usage_log)
        self.date = time.strftime("%Y-%m-%d", time.localtime(self.now))
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"date": self.date, "total_tokens": 0, "features": {}}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if loaded.get("date") != self.date:
            return {"date": self.date, "total_tokens": 0, "features": {}}
        loaded.setdefault("total_tokens", 0)
        loaded.setdefault("features", {})
        return loaded

    def spent_total(self) -> int:
        return int(self.data.get("total_tokens") or 0)

    def spent_feature(self, feature: str) -> int:
        return int(self.data.get("features", {}).get(feature, 0) or 0)

    def can_spend(self, feature: str, estimated_tokens: int) -> tuple[bool, str]:
        if self.spent_total() + estimated_tokens > self.config.daily_token_cap:
            return False, "daily_token_cap_exceeded"
        feature_cap = int(self.config.feature_token_caps.get(feature, self.config.daily_token_cap))
        if self.spent_feature(feature) + estimated_tokens > feature_cap:
            return False, "feature_token_cap_exceeded"
        return True, ""

    def record(self, feature: str, model_alias: str, usage: dict[str, Any]) -> dict[str, int]:
        normalized = {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
        if normalized["total_tokens"] <= 0:
            normalized["total_tokens"] = normalized["prompt_tokens"] + normalized["completion_tokens"]
        self.data["total_tokens"] = self.spent_total() + normalized["total_tokens"]
        features = self.data.setdefault("features", {})
        features[feature] = self.spent_feature(feature) + normalized["total_tokens"]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": int(self.now),
            "date": self.date,
            "feature": feature,
            "model_alias": model_alias,
            "usage": normalized,
            "total_after": self.data["total_tokens"],
        }
        with self.usage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        return normalized


class FakeDialogueProvider:
    def generate(self, messages: list[dict[str, str]], alias: ModelAlias) -> ProviderResult:
        payload = {}
        if len(messages) >= 2:
            try:
                payload = json.loads(messages[-1].get("content", "{}"))
            except json.JSONDecodeError:
                payload = {}
        state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
        role = str(payload.get("role") or "fill").lower()
        if bounded_int(state.get("party_dead"), 0, 8) > 0:
            response = {
                "say_channel": "party",
                "say_text": "\ubd80\ud65c \uc900\ube44\ud560\uac8c\uc694. \uc704\uce58\ub9cc \uc9c0\ucf1c\uc8fc\uc138\uc694.",
                "intent_hint": "resurrect_priority",
                "urgency": "high",
            }
        elif bounded_int(state.get("adds"), 0, 8) >= 2 and role in {"support", "healer"}:
            response = {
                "say_channel": "party",
                "say_text": "\ucd94\uac00 \uc801 \ubb36\uc744\uac8c\uc694. \uc9c0\uae08 \ud558\ub098\uc529 \ucc98\ub9ac\ud574\uc694.",
                "intent_hint": "cc_add",
                "urgency": "high",
            }
        elif state.get("leader_health_band") in {"critical", "low"} or state.get("command_intent") == "heal_priority":
            response = {
                "say_channel": "party",
                "say_text": "\ubc14\ub85c \uce58\uc720\ud558\uaca0\uc2b5\ub2c8\ub2e4. \uc870\uae08\ub9cc \ubc84\ud140\uc8fc\uc138\uc694.",
                "intent_hint": "heal_priority",
                "urgency": "high",
            }
        elif payload.get("event_type") == "player_requested_wait":
            response = {
                "say_channel": "party",
                "say_text": "\uc5ec\uae30\uc11c \ub300\uae30\ud558\uaca0\uc2b5\ub2c8\ub2e4.",
                "intent_hint": "wait",
                "urgency": "normal",
            }
        else:
            response = {
                "say_channel": "party",
                "say_text": "\ub530\ub77c\uac00\uaca0\uc2b5\ub2c8\ub2e4. \ud544\uc694\ud558\uba74 \ubc14\ub85c \ub9d0\uc500\ud574\uc8fc\uc138\uc694.",
                "intent_hint": "follow",
                "urgency": "normal",
            }
        return ProviderResult(response=response, usage=dict(DEFAULT_FAKE_USAGE))


class LiteLlmDialogueProvider:
    def generate(self, messages: list[dict[str, str]], alias: ModelAlias) -> ProviderResult:
        completion_func = litellm_completion
        if completion_func is None:
            try:
                from litellm import completion as imported_completion
            except Exception as exc:  # pragma: no cover - depends on operator environment
                raise RuntimeError(f"litellm_unavailable:{exc.__class__.__name__}") from exc
            completion_func = imported_completion
        response = completion_func(
            model=alias.provider_model,
            messages=messages,
            temperature=alias.temperature,
            max_tokens=alias.max_output_tokens,
            response_format={"type": "json_object"},
        )
        content = extract_litellm_content(response)
        usage = extract_litellm_usage(response)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("provider_returned_non_json") from exc
        return ProviderResult(response=parsed, usage=usage)


def extract_litellm_content(response: Any) -> str:
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict):
                return str(message.get("content") or "")
    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", "") if message is not None else ""
        return str(content or "")
    return ""


def extract_litellm_usage(response: Any) -> dict[str, int]:
    usage = response.get("usage") if isinstance(response, dict) else getattr(response, "usage", None)
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    getter = usage.get if isinstance(usage, dict) else lambda key, default=0: getattr(usage, key, default)
    return {
        "prompt_tokens": int(getter("prompt_tokens", 0) or 0),
        "completion_tokens": int(getter("completion_tokens", 0) or 0),
        "total_tokens": int(getter("total_tokens", 0) or 0),
    }


def provider_for(config: GatewayConfig) -> FakeDialogueProvider | LiteLlmDialogueProvider:
    if config.provider == "fake":
        return FakeDialogueProvider()
    if config.provider == "litellm":
        return LiteLlmDialogueProvider()
    raise RuntimeError(f"unknown_provider:{config.provider}")


def generate_dialogue(
    payload: dict[str, Any],
    config: GatewayConfig,
    feature: str = "companion_dialogue",
    model_alias: str = "small-dialogue",
) -> dict[str, Any]:
    policy = ModelPolicy(config)
    if not policy.is_allowed(model_alias, feature):
        return {"allowed": False, "blocked_reason": "model_or_feature_not_allowed"}
    alias = config.model_aliases[model_alias]
    sanitized = sanitize_companion_payload(payload) if feature == "companion_dialogue" else dict(payload)
    messages = build_companion_messages(sanitized)
    ledger = TokenLedger(config)
    allowed, reason = ledger.can_spend(feature, estimate_tokens(messages, alias.max_output_tokens))
    if not allowed:
        return {"allowed": False, "blocked_reason": reason}
    try:
        provider_result = provider_for(config).generate(messages, alias)
    except RuntimeError as exc:
        return {"allowed": False, "blocked_reason": str(exc)}
    validation = validate_companion_response(provider_result.response)
    if not validation.allowed:
        return {"allowed": False, "blocked_reason": validation.reason}
    usage = ledger.record(feature, model_alias, provider_result.usage)
    return {
        "allowed": True,
        "response": validation.value,
        "usage": usage,
        "model_alias": model_alias,
        "provider": config.provider,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenDAoC local AI gateway")
    parser.add_argument("--config", default=os.environ.get("OPENDAOC_AI_GATEWAY_CONFIG", ""))
    subparsers = parser.add_subparsers(dest="command")

    generate = subparsers.add_parser("generate")
    generate.add_argument("--feature", default="companion_dialogue")
    generate.add_argument("--model-alias", default="small-dialogue")
    generate.add_argument("--payload-json", default="")
    generate.add_argument("--payload-file", default="")
    return parser


def load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.payload_file:
        return json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    if args.payload_json:
        return json.loads(args.payload_json)
    return json.loads(sys.stdin.read())


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "generate":
        build_parser().print_help()
        return 2
    try:
        payload = load_payload(args)
    except json.JSONDecodeError as exc:
        print(json.dumps({"allowed": False, "blocked_reason": "invalid_payload_json", "detail": str(exc)}))
        return 2
    config = GatewayConfig.load(args.config)
    result = generate_dialogue(payload, config, feature=args.feature, model_alias=args.model_alias)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
