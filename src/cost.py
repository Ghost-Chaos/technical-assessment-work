import json
from pathlib import Path


def write_cost_report(root: Path, stats: dict):
    usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    openrouter_calls = 0
    llm_log = root / "llm_calls.jsonl"
    if llm_log.exists():
        for line in llm_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("provider") == "openrouter" and record.get("status") == "success":
                openrouter_calls += 1
                usage = record.get("usage") or {}
                usage_totals["prompt_tokens"] += usage.get("prompt_tokens") or usage.get("input_tokens") or 0
                usage_totals["completion_tokens"] += usage.get("completion_tokens") or usage.get("output_tokens") or 0
                usage_totals["total_tokens"] += usage.get("total_tokens") or 0
    report = {
        "currency": "USD",
        "estimated_cost": None,
        "note": "OpenRouter pricing varies by routed provider. Token usage is reported when returned by the API; cost is marked unknown instead of guessed.",
        "openrouter_success_calls": openrouter_calls,
        "usage_totals": usage_totals,
        "stats": stats,
    }
    (root / "cost_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report
