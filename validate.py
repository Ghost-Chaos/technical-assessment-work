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
    "outputs/manifest.json",
    "run_metrics.json",
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


def scan_for_unresolved_placeholders(errors, directory):
    root = ROOT / directory
    if not root.exists():
        fail(errors, f"Missing {directory}")
        return
    for path in root.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if "__PROTECTED_" in text:
                fail(errors, f"Unresolved protected placeholder found in {path.relative_to(ROOT)}")


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
    manifest = load_json("outputs/manifest.json")
    run_metrics = load_json("run_metrics.json")

    ok("Required files exist and JSON files are valid")

    if len(pages) < 1:
        fail(errors, "pages.json must include at least one page")
    if manifest.get("pages_processed", 0) < 1:
        fail(errors, "No pages were processed in outputs/manifest.json")
    required_stages = [
        "INIT",
        "CONFIG_LOADED",
        "PAGES_FETCHED",
        "CONTENT_EXTRACTED",
        "PROTECTED_TERMS_IDENTIFIED",
        "SEGMENTS_PREPARED",
        "SEGMENTS_DEDUPED_OR_CACHE_CHECKED",
        "TRANSLATION_COMPLETE",
        "HTML_RECONSTRUCTED",
        "QA_COMPLETE",
        "COST_REPORT_GENERATED",
        "RESULTS_FINALISED",
    ]
    actual_stages = [event.get("stage") for event in run_metrics.get("stages", [])]
    missing_stages = [stage for stage in required_stages if stage not in actual_stages]
    if missing_stages:
        fail(errors, f"Missing completed pipeline stages: {', '.join(missing_stages)}")
    elif not run_metrics.get("completed"):
        fail(errors, "run_metrics.json does not mark the run as completed")
    else:
        ok("Required pipeline stages completed")
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
            translation = translations.get(segment["id"], {})
            translated = translation.get("translated", "")
            unresolved = translation.get("unresolved_protected_placeholders") or re.findall(r"__PROTECTED_\d+__", translated)
            if unresolved:
                missing = translation.get("missing_placeholder_mappings") or []
                detail = f"{', '.join(unresolved)}"
                if missing:
                    detail += f"; missing mappings: {', '.join(missing)}"
                fail(errors, f"Unresolved protected placeholder for {code}: {segment['id']} ({detail})")
            for term in protected_terms:
                source_count = segment["text"].count(term)
                translated_count = translated.count(term)
                if source_count > 0 and translated_count < source_count:
                    fail(errors, f"Protected term missing or reduced for {code}: {term} ({source_count} -> {translated_count})")
                elif source_count == 0 and translated_count > 0:
                    print(f"WARNING: Protected term added for {code}: {term} ({source_count} -> {translated_count})")
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
    scan_for_unresolved_placeholders(errors, "translations")
    scan_for_unresolved_placeholders(errors, "output")
    llm_lines = [line for line in (ROOT / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if not llm_lines:
        fail(errors, "llm_calls.jsonl is empty")
    else:
        required_call_fields = {"segment_id", "language", "provider", "model", "status", "cache_hit", "source_hash", "input_chars", "output_chars", "usage", "estimated_cost"}
        for index, line in enumerate(llm_lines, start=1):
            record = json.loads(line)
            missing = required_call_fields - set(record)
            if missing:
                fail(errors, f"llm_calls.jsonl line {index} missing fields: {', '.join(sorted(missing))}")

    if errors:
        print(f"Validation failed with {len(errors)} issue(s).")
        return 1
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
