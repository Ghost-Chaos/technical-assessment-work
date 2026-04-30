import json
from datetime import datetime, timezone
from pathlib import Path


class RunLogger:
    def __init__(self, root: Path):
        self.root = root
        self.stages = []
        self.llm_log = root / "llm_calls.jsonl"
        self.llm_log.write_text("", encoding="utf-8")

    def stage(self, name: str, **details):
        event = {
            "stage": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
        }
        self.stages.append(event)
        print(f"[{name}]")

    def llm_call(self, record: dict):
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **record,
        }
        with self.llm_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def write_metrics(self):
        metrics = {
            "stages": self.stages,
            "stage_count": len(self.stages),
            "completed": bool(self.stages and self.stages[-1]["stage"] == "RESULTS_FINALISED"),
        }
        (self.root / "run_metrics.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
