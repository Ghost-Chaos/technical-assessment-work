import json
from pathlib import Path


def write_cost_report(root: Path, stats: dict):
    report = {
        "currency": "USD",
        "estimated_cost": 0.0,
        "note": "Mock translations are free. OpenRouter cost depends on provider billing and response usage.",
        "stats": stats,
    }
    (root / "cost_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report
