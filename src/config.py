import json
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_config(root: Path):
    pages = load_json(root / "pages.json")
    languages = load_json(root / "target_languages.json")
    if not pages:
        raise ValueError("pages.json must include at least one page")
    if not any(lang.get("code") == "ar" for lang in languages):
        raise ValueError("target_languages.json must include Arabic (ar)")
    return pages, languages
