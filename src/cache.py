import hashlib
import json
from pathlib import Path


def content_hash(text: str, language_code: str):
    return hashlib.sha256(f"{language_code}\n{text}".encode("utf-8")).hexdigest()


def load_cache(root: Path):
    path = root / "translation_cache.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_cache(root: Path, cache: dict):
    (root / "translation_cache.json").write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
