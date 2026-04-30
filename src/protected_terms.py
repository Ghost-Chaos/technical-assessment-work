import json
import re
from pathlib import Path


DEFAULT_TERMS = [
    "Synthetic Indices",
    "Deriv Bot",
    "Deriv MT5",
    "Deriv X",
    "SmartTrader",
    "Multipliers",
    "Forex",
    "CFDs",
    "Deriv",
]

TOKEN_PATTERNS = [
    r"\{\{[^}]+\}\}",
    r"\{[A-Za-z_][A-Za-z0-9_]*\}",
    r"%\([A-Za-z_][A-Za-z0-9_]*\)s",
    r"\b[A-Za-z_]+_id\b",
]


def identify_terms(pages, root: Path):
    text = "\n".join(page["html"] for page in pages)
    terms = [term for term in DEFAULT_TERMS if re.search(rf"\b{re.escape(term)}\b", text)]
    path = root / "protected_terms.json"
    path.write_text(json.dumps(terms, ensure_ascii=False, indent=2), encoding="utf-8")
    return terms


def protect_text(text: str, protected_terms):
    mapping = {}
    protected = text
    items = list(protected_terms)
    for pattern in TOKEN_PATTERNS:
        items.extend(re.findall(pattern, text))
    items.extend(re.findall(r"https?://[^\s\"'<>)]+", text))
    unique = []
    for item in sorted(set(items), key=len, reverse=True):
        if item and item in protected and item not in unique:
            unique.append(item)
    for index, item in enumerate(unique):
        placeholder = f"__PROTECTED_{index}__"
        protected = protected.replace(item, placeholder)
        mapping[placeholder] = item
    return protected, mapping


def restore_text(text: str, mapping: dict):
    restored = text
    for placeholder, original in mapping.items():
        restored = restored.replace(placeholder, original)
    return restored
