import json
import re
import sys
from pathlib import Path


ROOT = Path.cwd()
REQUIRED_FILES = [
    "main.py",
    "validate.py",
    "requirements.txt",
    ".env.example",
    "pages.json",
    "target_languages.json",
    "extracted_segments.json",
    "protected_terms.json",
    "qa_report.json",
    "cost_report.json",
    "translation_cache.json",
    "llm_calls.jsonl",
]
REQUIRED_MODULES = [
    "src/config.py",
    "src/fetcher.py",
    "src/extractor.py",
    "src/protected_terms.py",
    "src/translator.py",
    "src/cache.py",
    "src/reconstructor.py",
    "src/qa.py",
    "src/cost.py",
    "src/logger.py",
    "src/pipeline.py",
]


def load_json(path):
    with (ROOT / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fail(errors, message):
    errors.append(message)
    print(f"FAIL: {message}")


def ok(message):
    print(f"OK: {message}")


def main():
    errors = []
    for path in REQUIRED_FILES + REQUIRED_MODULES:
        if not (ROOT / path).exists():
            fail(errors, f"Missing {path}")
    if errors:
        return 1

    pages = load_json("pages.json")
    languages = load_json("target_languages.json")
    segments = load_json("extracted_segments.json")
    protected_terms = load_json("protected_terms.json")
    qa_report = load_json("qa_report.json")
    cache = load_json("translation_cache.json")

    ok("Required files exist and JSON files are valid")

    if len(pages) < 1:
        fail(errors, "pages.json must include at least one page")
    if not any(language.get("code") == "ar" and language.get("rtl") for language in languages):
        fail(errors, "Arabic target language with rtl=true is required")
    else:
        ok("Arabic target language is configured with RTL")

    required_segment_fields = {"id", "page_id", "field", "tag", "type", "text"}
    if not segments:
        fail(errors, "No extracted segments found")
    elif not required_segment_fields.issubset(segments[0]):
        fail(errors, "extracted_segments.json is missing required segment fields")
    else:
        ok(f"Extracted segments found: {len(segments)}")

    if not protected_terms:
        fail(errors, "No protected terms identified")
    else:
        ok(f"Protected terms identified: {', '.join(protected_terms[:5])}")

    for language in languages:
        code = language["code"]
        translation_path = ROOT / "translations" / code / "segments.json"
        output_dir = ROOT / "output" / code
        if not translation_path.exists():
            fail(errors, f"Missing translations for {code}")
            continue
        translations = json.loads(translation_path.read_text(encoding="utf-8"))
        if not any(output_dir.glob("*.html")):
            fail(errors, f"Missing reconstructed HTML for {code}")
        for segment in segments:
            translated = translations.get(segment["id"], {}).get("translated", "")
            for term in protected_terms:
                if term in segment["text"] and term not in translated:
                    fail(errors, f"Protected term not restored for {code}: {term}")
            for url in re.findall(r"https?://[^\s\"'<>)]+", segment["text"]):
                if url not in translated:
                    fail(errors, f"URL not preserved for {code}: {url}")
            for token in re.findall(r"(\{\{[^}]+\}\}|\{[A-Za-z_][A-Za-z0-9_]*\}|%\([A-Za-z_][A-Za-z0-9_]*\)s|\b[A-Za-z_]+_id\b)", segment["text"]):
                if token not in translated:
                    fail(errors, f"Placeholder not preserved for {code}: {token}")
        if code == "ar":
            ar_html = "\n".join(path.read_text(encoding="utf-8") for path in output_dir.glob("*.html"))
            if 'lang="ar"' not in ar_html and 'dir="rtl"' not in ar_html:
                fail(errors, "Arabic HTML missing lang=\"ar\" or dir=\"rtl\"")
            else:
                ok("Arabic HTML includes lang=\"ar\" or dir=\"rtl\"")

    if not qa_report.get("summary"):
        fail(errors, "qa_report.json missing summary")
    else:
        critical = qa_report["summary"].get("critical_issues", 0)
        print(f"QA critical issues: {critical}")
        for issue in qa_report.get("issues", []):
            if issue.get("severity") == "critical":
                print(f"CRITICAL: {issue}")

    if not cache:
        fail(errors, "translation_cache.json is empty")
    if not (ROOT / "llm_calls.jsonl").read_text(encoding="utf-8").strip():
        fail(errors, "llm_calls.jsonl is empty")

    if errors:
        print(f"Validation failed with {len(errors)} issue(s).")
        return 1
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
