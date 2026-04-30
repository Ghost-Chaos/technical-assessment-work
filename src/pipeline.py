import json
from pathlib import Path

from .cache import load_cache, save_cache
from .config import load_config
from .cost import write_cost_report
from .extractor import extract_segments
from .fetcher import fetch_pages
from .logger import RunLogger
from .protected_terms import identify_terms
from .qa import run_qa
from .reconstructor import reconstruct_html, write_translations
from .translator import translate_segments


STAGES = [
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


def run_pipeline(root: Path | None = None):
    root = root or Path.cwd()
    logger = RunLogger(root)
    logger.stage("INIT")

    pages, languages = load_config(root)
    logger.stage("CONFIG_LOADED", pages=len(pages), languages=[language["code"] for language in languages])

    fetched_pages = fetch_pages(pages, root, limit=2)
    logger.stage("PAGES_FETCHED", pages=len(fetched_pages), sources=[page["source"] for page in fetched_pages])

    segments, prepared_pages = extract_segments(fetched_pages, root)
    logger.stage("CONTENT_EXTRACTED", segments=len(segments))

    protected_terms = identify_terms(fetched_pages, root)
    logger.stage("PROTECTED_TERMS_IDENTIFIED", terms=len(protected_terms))

    logger.stage("SEGMENTS_PREPARED", segments=len(segments))

    cache = load_cache(root)
    unique_texts = len({segment["text"] for segment in segments})
    logger.stage("SEGMENTS_DEDUPED_OR_CACHE_CHECKED", unique_texts=unique_texts, cached_entries=len(cache))

    translations, stats = translate_segments(segments, languages, protected_terms, cache, logger)
    save_cache(root, cache)
    write_translations(root, translations)
    logger.stage("TRANSLATION_COMPLETE", stats=stats)

    reconstruct_html(root, prepared_pages, languages, translations)
    logger.stage("HTML_RECONSTRUCTED")

    qa_report = run_qa(root, segments, languages, translations, protected_terms)
    logger.stage("QA_COMPLETE", critical_issues=qa_report["summary"]["critical_issues"])

    write_cost_report(root, stats)
    logger.stage("COST_REPORT_GENERATED")

    manifest = {
        "stages": STAGES,
        "pages_processed": len(fetched_pages),
        "languages": [language["code"] for language in languages],
        "artifacts": [
            "extracted_segments.json",
            "protected_terms.json",
            "translations/",
            "output/",
            "qa_report.json",
            "cost_report.json",
            "translation_cache.json",
            "llm_calls.jsonl",
            "run_metrics.json",
        ],
    }
    (root / "outputs" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.stage("RESULTS_FINALISED")
    logger.write_metrics()
    print("Pipeline complete. Run `python validate.py` to verify artifacts.")
