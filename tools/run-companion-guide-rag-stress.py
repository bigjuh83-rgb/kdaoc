#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ".superpowers/opendaoc-ai-gateway-live.json"
DEFAULT_MODEL_ALIAS = "openai-small-guide"


@dataclasses.dataclass(frozen=True)
class GuideQuestionCase:
    question: str
    category: str
    role: str = "healer-support"
    realm: str = "1"
    region: int = 1
    player_level: int = 0
    expect_knowledge: bool = True


BASE_CASES: tuple[GuideQuestionCase, ...] = (
    GuideQuestionCase("5렙 사냥 어디서해", "hunting", player_level=0),
    GuideQuestionCase("용병아 5레벨 안전한 사냥터 알려줘", "hunting", player_level=5),
    GuideQuestionCase("10렙 솔플 어디가 좋아?", "hunting", player_level=10),
    GuideQuestionCase("20렙 사냥 어디?", "hunting", player_level=20),
    GuideQuestionCase("35레벨 파티 사냥터 추천해줘", "hunting", player_level=35),
    GuideQuestionCase("50렙에서 뭐 잡으면 돼?", "hunting", player_level=50),
    GuideQuestionCase("힐러 스킬 뭐 찍어?", "skill", role="healer-support", player_level=20),
    GuideQuestionCase("탱커면 어떤 스킬부터 봐야돼?", "skill", role="tank", player_level=20),
    GuideQuestionCase("마법사 주문 뭐 써?", "skill", role="caster-basic", player_level=15),
    GuideQuestionCase("5레벨 퀘스트 뭐부터 해?", "quest", player_level=5),
    GuideQuestionCase("초반 장비는 뭘 주워야 해?", "item", player_level=8),
    GuideQuestionCase("독 걸리면 어떻게 해?", "mechanic", player_level=12),
    GuideQuestionCase("말 타는 법 알려줘", "mechanic", player_level=10),
    GuideQuestionCase("파티원이 죽으면 용병은 뭘 해야 해?", "companion", player_level=20),
    GuideQuestionCase("ㄱㄱ", "chat", expect_knowledge=False),
    GuideQuestionCase("고마워", "chat", expect_knowledge=False),
    GuideQuestionCase("asdf 1234 ???", "fuzz", expect_knowledge=False),
)

HUNTING_TEMPLATES = (
    "{level}렙 사냥 어디서해",
    "{level}레벨 어디가 안전해?",
    "용병아 {level}렙 사냥터 추천",
    "{level}렙 솔플 몹 뭐 잡아?",
    "{level}레벨 파티 사냥 어디?",
)
SKILL_TEMPLATES = (
    "{role_ko} 스킬 뭐 찍어?",
    "{role_ko} 주문 뭐 써?",
    "{level}렙 {role_ko} 운용법 알려줘",
)
ROLE_NAMES = {
    "healer-support": "힐러",
    "tank": "탱커",
    "melee-dps": "딜러",
    "caster-basic": "마법사",
    "support": "서포터",
}


def build_cases(seed: int, count: int, include_fuzz: bool) -> list[GuideQuestionCase]:
    rng = random.Random(seed)
    cases = list(BASE_CASES)
    levels = [1, 3, 5, 8, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    roles = list(ROLE_NAMES)
    while len(cases) < count:
        bucket = rng.choice(["hunting", "hunting", "skill", "quest", "item", "mechanic", "fuzz" if include_fuzz else "hunting"])
        level = rng.choice(levels)
        role = rng.choice(roles)
        if bucket == "hunting":
            question = rng.choice(HUNTING_TEMPLATES).format(level=level)
            cases.append(GuideQuestionCase(question, "hunting", role=role, player_level=0 if rng.random() < 0.35 else level))
        elif bucket == "skill":
            question = rng.choice(SKILL_TEMPLATES).format(level=level, role_ko=ROLE_NAMES[role])
            cases.append(GuideQuestionCase(question, "skill", role=role, player_level=level))
        elif bucket == "quest":
            cases.append(GuideQuestionCase(f"{level}렙 퀘스트 뭐 하면 돼?", "quest", role=role, player_level=level))
        elif bucket == "item":
            cases.append(GuideQuestionCase(f"{level}렙 장비 뭐 챙겨?", "item", role=role, player_level=level))
        elif bucket == "mechanic":
            question = rng.choice(["스킬 초기화 가능해?", "전투 중이면 어떻게 물러나?", "파티 사냥할 때 용병 명령 뭐 써?"])
            cases.append(GuideQuestionCase(question, "mechanic", role=role, player_level=level))
        else:
            question = rng.choice(["", "ㅋㅋㅋㅋ", "123123", "어디", "그거 뭐임?", "알려줘!!! " * 8]).strip()
            cases.append(GuideQuestionCase(question or "?", "fuzz", role=role, player_level=level, expect_knowledge=False))
    rng.shuffle(cases)
    return cases[:count]


def payload_for_case(case: GuideQuestionCase) -> dict[str, Any]:
    return {
        "question": case.question,
        "role": case.role,
        "realm": case.realm,
        "region": case.region,
        "player_level": case.player_level,
        "state": {"combat": False, "region": case.region},
    }


def dotenv_subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    env_file = Path(env.get("OPENDAOC_COMPANION_ENV_FILE") or ROOT / ".env")
    if not env_file.exists():
        return env
    for raw_line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if not name.isidentifier() or env.get(name):
            continue
        value = value.strip().strip("'\"")
        env[name] = value
    return env


def run_gateway(args: argparse.Namespace, case: GuideQuestionCase) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / "tools" / "opendaoc-ai-gateway.py"),
        "--config",
        args.config,
        "generate",
        "--feature",
        "companion_guide",
        "--model-alias",
        args.model_alias,
        "--payload-json",
        json.dumps(payload_for_case(case), ensure_ascii=False),
    ]
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=float(args.timeout),
        check=False,
        env=getattr(args, "gateway_env", None),
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if completed.returncode != 0:
        return {
            "ok": False,
            "hard_fail": True,
            "reason": "gateway_process_failed",
            "stderr_tail": completed.stderr[-400:],
            "elapsed_ms": elapsed_ms,
        }
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "hard_fail": True,
            "reason": "gateway_invalid_json",
            "stdout_tail": completed.stdout[-400:],
            "elapsed_ms": elapsed_ms,
        }
    return classify_result(case, result, elapsed_ms)


def classify_result(case: GuideQuestionCase, result: dict[str, Any], elapsed_ms: int) -> dict[str, Any]:
    response = result.get("response") if isinstance(result.get("response"), dict) else {}
    lines = response.get("guide_lines") if isinstance(response, dict) else []
    source_ids = response.get("source_ids") if isinstance(response, dict) else []
    if not isinstance(lines, list):
        lines = []
    if not isinstance(source_ids, list):
        source_ids = []
    text = "\n".join(str(line or "") for line in lines)
    issues: list[str] = []
    if not result.get("allowed"):
        issues.append(str(result.get("blocked_reason") or "not_allowed"))
    if result.get("allowed") and not (3 <= len(lines) <= 5):
        issues.append("bad_line_count")
    if any(str(line).startswith("/") for line in lines):
        issues.append("slash_line")
    if "API" in text or "vector" in text.lower() or "embedding" in text.lower():
        issues.append("internal_term_leak")
    if "X " in text and "Y " in text:
        issues.append("coordinate_leak")
    if case.expect_knowledge and result.get("blocked_reason") == "knowledge_unavailable":
        issues.append("coverage_gap")
    hard_fail = any(issue not in {"coverage_gap", "coordinate_leak"} for issue in issues)
    return {
        "ok": not hard_fail,
        "hard_fail": hard_fail,
        "issues": issues,
        "allowed": bool(result.get("allowed")),
        "blocked_reason": result.get("blocked_reason", ""),
        "cache": result.get("cache", ""),
        "model_alias": result.get("model_alias", ""),
        "provider_model": result.get("provider_model", ""),
        "line_count": len(lines),
        "source_count": len(source_ids),
        "elapsed_ms": elapsed_ms,
        "usage": result.get("usage", {}),
        "sample_lines": [str(line) for line in lines[:2]],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress companion guide RAG with expected and random Korean questions.")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--model-alias", default=DEFAULT_MODEL_ALIAS)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260601)
    parser.add_argument("--timeout", type=float, default=35.0)
    parser.add_argument("--out-dir", default="test-output/companion-guide-rag-stress")
    parser.add_argument("--include-fuzz", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-hard-failures", type=int, default=0)
    args = parser.parse_args()
    args.gateway_env = dotenv_subprocess_env()

    out_dir = Path(args.out_dir)
    cases = build_cases(args.seed, max(1, int(args.count)), bool(args.include_fuzz))
    rows: list[dict[str, Any]] = []
    hard_failures = 0
    coverage_gaps = 0
    coordinate_leaks = 0
    cache_hits = 0
    total_tokens = 0

    results_path = out_dir / "results.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)
    with results_path.open("w", encoding="utf-8") as handle:
        for index, case in enumerate(cases, start=1):
            row = {
                "index": index,
                "question": case.question,
                "category": case.category,
                "player_level": case.player_level,
                "region": case.region,
            }
            result = run_gateway(args, case)
            row.update(result)
            rows.append(row)
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            if row.get("hard_fail"):
                hard_failures += 1
            issues = row.get("issues") if isinstance(row.get("issues"), list) else []
            if "coverage_gap" in issues:
                coverage_gaps += 1
            if "coordinate_leak" in issues:
                coordinate_leaks += 1
            if row.get("cache") == "hit":
                cache_hits += 1
            usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
            total_tokens += int(usage.get("total_tokens") or 0)
            print(
                f"[{index:03d}/{len(cases):03d}] "
                f"{case.category} ok={row.get('ok')} allowed={row.get('allowed')} "
                f"issues={','.join(issues) if issues else '-'} cache={row.get('cache') or '-'} "
                f"{case.question}",
                flush=True,
            )

    summary = {
        "total": len(rows),
        "hard_failures": hard_failures,
        "coverage_gaps": coverage_gaps,
        "coordinate_leaks": coordinate_leaks,
        "cache_hits": cache_hits,
        "total_tokens": total_tokens,
        "results_path": str(results_path),
        "failures": [
            {
                "index": row["index"],
                "question": row["question"],
                "category": row["category"],
                "issues": row.get("issues", []),
                "blocked_reason": row.get("blocked_reason", ""),
                "sample_lines": row.get("sample_lines", []),
            }
            for row in rows
            if row.get("hard_fail") or row.get("issues")
        ][:50],
    }
    write_json(out_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if hard_failures <= max(0, int(args.max_hard_failures)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
