import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
GATEWAY_PATH = ROOT / "tools" / "opendaoc-ai-gateway.py"


def load_gateway():
    spec = importlib.util.spec_from_file_location("opendaoc_ai_gateway", GATEWAY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
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

    def test_model_policy_rejects_configured_large_model_for_small_alias(self) -> None:
        gateway = load_gateway()
        config = gateway.GatewayConfig(
            provider="litellm",
            daily_token_cap=500_000,
            warning_token_cap=400_000,
            feature_token_caps={"companion_dialogue": 350_000},
            model_aliases={
                "small-dialogue": gateway.ModelAlias(
                    provider_model="openai/gpt-4.1",
                    features=("companion_dialogue",),
                    max_output_tokens=80,
                    temperature=0.4,
                )
            },
            usage_log="usage.jsonl",
            ledger_file="ledger.json",
        )

        self.assertFalse(gateway.ModelPolicy(config).is_allowed("small-dialogue", "companion_dialogue"))

    def test_config_file_overrides_caps_without_real_keys(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gateway.json"
            path.write_text(
                json.dumps(
                    {
                        "provider": "litellm",
                        "daily_token_cap": 12345,
                        "feature_token_caps": {"companion_dialogue": 6789},
                        "model_aliases": {
                            "small-dialogue": {
                                "provider_model": "openai/gpt-4.1-nano",
                                "features": ["companion_dialogue"],
                                "max_output_tokens": 64,
                                "temperature": 0.4,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = gateway.GatewayConfig.load(path)

        self.assertEqual(config.provider, "litellm")
        self.assertEqual(config.daily_token_cap, 12345)
        self.assertEqual(config.feature_token_caps["companion_dialogue"], 6789)
        self.assertEqual(config.model_aliases["small-dialogue"].provider_model, "openai/gpt-4.1-nano")
        self.assertEqual(config.model_aliases["small-dialogue"].max_output_tokens, 64)

    def test_config_file_accepts_windows_utf8_bom(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gateway.json"
            path.write_text('{"provider": "litellm"}', encoding="utf-8-sig")

            config = gateway.GatewayConfig.load(path)

        self.assertEqual(config.provider, "litellm")


class OpenDaocAiGatewayValidationTests(unittest.TestCase):
    def test_sanitize_companion_context_removes_private_fields(self) -> None:
        gateway = load_gateway()
        payload = {
            "feature": "companion_dialogue",
            "event_type": "player_requested_heal",
            "account": "secret_account",
            "player_name": "Huhu",
            "x": 123,
            "y": 456,
            "raw_chat": "heal me at exact place",
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
                "say_text": "Healing now. Hold position.",
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
                "say_text": "/release now",
                "intent_hint": "heal_priority",
                "urgency": "high",
            }
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "slash_command_in_say_text")

    def test_validate_response_downgrades_unknown_hint_to_none(self) -> None:
        gateway = load_gateway()

        result = gateway.validate_companion_response(
            {
                "say_channel": "party",
                "say_text": "I am with you.",
                "intent_hint": "protect_the_leader",
                "urgency": "normal",
            }
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.value["intent_hint"], "none")

    def test_validate_response_maps_common_hint_aliases(self) -> None:
        gateway = load_gateway()

        result = gateway.validate_companion_response(
            {
                "say_channel": "party",
                "say_text": "I will heal now.",
                "intent_hint": "heal",
                "urgency": "high",
            }
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.value["intent_hint"], "heal_priority")

    def test_validate_response_accepts_cure_hint_aliases(self) -> None:
        gateway = load_gateway()

        result = gateway.validate_companion_response(
            {
                "say_channel": "party",
                "say_text": "I will cure that now.",
                "intent_hint": "cure",
                "urgency": "normal",
            }
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.value["intent_hint"], "cure_priority")

    def test_build_companion_prompt_uses_sanitized_json_only(self) -> None:
        gateway = load_gateway()
        sanitized = gateway.sanitize_companion_payload(
            {
                "feature": "companion_dialogue",
                "event_type": "add_detected",
                "role": "support",
                "personality": "tactical_support",
                "raw_chat": "go to the exact coordinate",
                "state": {"combat": True, "adds": 2},
            }
        )

        messages = gateway.build_companion_messages(sanitized)
        combined = json.dumps(messages, ensure_ascii=False)

        self.assertIn("companion_dialogue", combined)
        self.assertIn("add_detected", combined)
        self.assertIn("support", combined)
        self.assertNotIn("exact coordinate", combined)
        self.assertIn("JSON", combined)
        self.assertIn("heal_priority", combined)
        self.assertIn("cc_add", combined)


class OpenDaocAiGatewayGenerationTests(unittest.TestCase):
    def config_with_paths(self, temp_dir: str, **overrides):
        gateway = load_gateway()
        config = gateway.GatewayConfig.default()
        values = {
            "provider": config.provider,
            "daily_token_cap": config.daily_token_cap,
            "warning_token_cap": config.warning_token_cap,
            "feature_token_caps": dict(config.feature_token_caps),
            "model_aliases": dict(config.model_aliases),
            "usage_log": str(Path(temp_dir) / "usage.jsonl"),
            "ledger_file": str(Path(temp_dir) / "ledger.json"),
        }
        values.update(overrides)
        return gateway.GatewayConfig(**values)

    def test_token_ledger_blocks_daily_cap_before_provider_call(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config_with_paths(temp_dir, daily_token_cap=1)

            result = gateway.generate_dialogue({"event_type": "status"}, config)

        self.assertFalse(result["allowed"])
        self.assertEqual(result["blocked_reason"], "daily_token_cap_exceeded")

    def test_token_ledger_uses_utc_budget_date(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config_with_paths(temp_dir)
            ledger = gateway.TokenLedger(config, now=86399)

        self.assertEqual(ledger.date, "1970-01-01")

    def test_token_ledger_reservations_reload_under_lock(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config_with_paths(temp_dir, daily_token_cap=100)
            first = gateway.TokenLedger(config)
            second = gateway.TokenLedger(config)

            reservation, reason = first.reserve("companion_dialogue", "small-dialogue", 80)
            blocked, blocked_reason = second.reserve("companion_dialogue", "small-dialogue", 30)

        self.assertIsNotNone(reservation)
        self.assertEqual(reason, "")
        self.assertIsNone(blocked)
        self.assertEqual(blocked_reason, "daily_token_cap_exceeded")

    def test_token_ledger_logs_budget_warning_when_threshold_is_crossed(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config_with_paths(temp_dir, daily_token_cap=500, warning_token_cap=40)

            result = gateway.generate_dialogue({"event_type": "status"}, config)
            usage_events = [
                json.loads(line)
                for line in Path(config.usage_log).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertTrue(result["allowed"])
        self.assertTrue(any(row.get("event") == "budget_warning" for row in usage_events))

    def test_fake_provider_generates_valid_heal_response_and_usage_log(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config_with_paths(temp_dir)

            result = gateway.generate_dialogue(
                {
                    "event_type": "player_requested_heal",
                    "role": "healer",
                    "state": {"combat": True, "leader_health_band": "low", "player_called": True},
                },
                config,
            )
            ledger = json.loads(Path(config.ledger_file).read_text(encoding="utf-8"))
            usage_line = Path(config.usage_log).read_text(encoding="utf-8").strip()

        self.assertTrue(result["allowed"])
        self.assertEqual(result["response"]["intent_hint"], "heal_priority")
        self.assertEqual(result["usage"]["total_tokens"], 42)
        self.assertEqual(ledger["total_tokens"], 42)
        self.assertIn("companion_dialogue", usage_line)
        self.assertNotIn("OPENAI", usage_line)

    def test_fake_provider_generates_resurrect_cc_and_join_responses(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config_with_paths(temp_dir)

            resurrect = gateway.generate_dialogue(
                {"event_type": "party_member_dead", "role": "healer", "state": {"party_dead": 1}},
                config,
            )
            crowd_control = gateway.generate_dialogue(
                {"event_type": "add_pressure", "role": "support", "state": {"adds": 2, "combat": True}},
                config,
            )
            joined = gateway.generate_dialogue(
                {"event_type": "companion_joined", "role": "tank", "state": {"combat": False}},
                config,
            )

        self.assertEqual(resurrect["response"]["intent_hint"], "resurrect_priority")
        self.assertEqual(crowd_control["response"]["intent_hint"], "cc_add")
        self.assertEqual(joined["response"]["intent_hint"], "follow")

    def test_litellm_adapter_uses_alias_model_and_validates_json(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config_with_paths(
                temp_dir,
                provider="litellm",
                model_aliases={
                    "small-dialogue": gateway.ModelAlias(
                        provider_model="openai/gpt-4.1-nano",
                        features=("companion_dialogue",),
                        max_output_tokens=60,
                        temperature=0.4,
                    )
                },
            )
            calls = []

            def fake_completion(**kwargs):
                calls.append(kwargs)
                return {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "say_channel": "party",
                                        "say_text": "I will heal now.",
                                        "intent_hint": "heal_priority",
                                        "urgency": "high",
                                    }
                                )
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                }

            with mock.patch.object(gateway, "litellm_completion", fake_completion):
                result = gateway.generate_dialogue({"event_type": "player_requested_heal"}, config)

        self.assertTrue(result["allowed"])
        self.assertEqual(calls[0]["model"], "openai/gpt-4.1-nano")
        self.assertEqual(calls[0]["max_tokens"], 60)
        self.assertEqual(result["usage"]["total_tokens"], 15)

    def test_litellm_provider_exception_fails_closed_and_disables_current_window(self) -> None:
        gateway = load_gateway()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config_with_paths(
                temp_dir,
                provider="litellm",
                model_aliases={
                    "small-dialogue": gateway.ModelAlias(
                        provider_model="openai/gpt-4.1-nano",
                        features=("companion_dialogue",),
                        max_output_tokens=60,
                        temperature=0.4,
                    )
                },
            )

            def failing_completion(**kwargs):
                raise ValueError("quota details are intentionally not exposed")

            with mock.patch.object(gateway, "litellm_completion", failing_completion):
                first = gateway.generate_dialogue({"event_type": "player_requested_heal"}, config)
            with mock.patch.object(gateway, "litellm_completion") as completion:
                second = gateway.generate_dialogue({"event_type": "player_requested_heal"}, config)

            ledger = json.loads(Path(config.ledger_file).read_text(encoding="utf-8"))

        self.assertFalse(first["allowed"])
        self.assertEqual(first["blocked_reason"], "provider_error:ValueError")
        self.assertFalse(second["allowed"])
        self.assertEqual(second["blocked_reason"], "provider_disabled:provider_error:ValueError")
        completion.assert_not_called()
        self.assertEqual(ledger["total_tokens"], 0)


class OpenDaocAiGatewayCliTests(unittest.TestCase):
    def test_generate_cli_returns_allowed_fake_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "provider": "fake",
                        "daily_token_cap": 1000,
                        "feature_token_caps": {"companion_dialogue": 1000},
                        "usage_log": str(Path(temp_dir) / "usage.jsonl"),
                        "ledger_file": str(Path(temp_dir) / "ledger.json"),
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(GATEWAY_PATH),
                    "--config",
                    str(config_path),
                    "generate",
                    "--feature",
                    "companion_dialogue",
                    "--payload-json",
                    json.dumps({"event_type": "player_requested_heal", "role": "healer"}),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row = json.loads(completed.stdout)
        self.assertTrue(row["allowed"])
        self.assertEqual(row["provider"], "fake")

    def test_generate_cli_accepts_payload_file_with_windows_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path = Path(temp_dir) / "payload.json"
            payload_path.write_text(
                json.dumps({"event_type": "player_requested_heal", "role": "healer"}),
                encoding="utf-8-sig",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(GATEWAY_PATH),
                    "generate",
                    "--feature",
                    "companion_dialogue",
                    "--payload-file",
                    str(payload_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row = json.loads(completed.stdout)
        self.assertTrue(row["allowed"])

    def test_generate_cli_blocks_disallowed_model_alias(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(GATEWAY_PATH),
                "generate",
                "--feature",
                "companion_dialogue",
                "--model-alias",
                "openai/gpt-4.1",
                "--payload-json",
                "{}",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        row = json.loads(completed.stdout)
        self.assertFalse(row["allowed"])
        self.assertEqual(row["blocked_reason"], "model_or_feature_not_allowed")


if __name__ == "__main__":
    unittest.main()
