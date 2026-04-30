import json
import re
from pathlib import Path


URL_RE = re.compile(r"https?://[^\s\"'<>)]+")
PLACEHOLDER_RE = re.compile(r"(\{\{[^}]+\}\}|\{[A-Za-z_][A-Za-z0-9_]*\}|%\([A-Za-z_][A-Za-z0-9_]*\)s|\b[A-Za-z_]+_id\b)")


def run_qa(root: Path, segments, languages, translations, protected_terms):
    issues = []
    for language in languages:
        code = language["code"]
        for segment in segments:
            translation = translations[code][segment["id"]]
            translated = translation["translated"]
            unresolved = translation.get("unresolved_protected_placeholders") or re.findall(r"__PROTECTED_\d+__", translated)
            if unresolved:
                missing = translation.get("missing_placeholder_mappings") or []
                detail = f": {', '.join(unresolved)}"
                if missing:
                    detail += f"; missing mappings: {', '.join(missing)}"
                issues.append({"severity": "critical", "segment_id": segment["id"], "language": code, "issue": f"Unresolved protected placeholder remains{detail}"})
            for term in protected_terms:
                source_count = segment["text"].count(term)
                translated_count = translated.count(term)
                if source_count > 0 and translated_count < source_count:
                    issues.append({"severity": "critical", "segment_id": segment["id"], "language": code, "issue": f"Protected term missing or reduced: {term} ({source_count} -> {translated_count})"})
                elif source_count == 0 and translated_count > 0:
                    issues.append({"severity": "warning", "segment_id": segment["id"], "language": code, "issue": f"Protected term added: {term} (0 -> {translated_count})"})
            for url in URL_RE.findall(segment["text"]):
                if url not in translated:
                    issues.append({"severity": "critical", "segment_id": segment["id"], "language": code, "issue": f"URL missing: {url}"})
            for token in PLACEHOLDER_RE.findall(segment["text"]):
                if token not in translated:
                    issues.append({"severity": "critical", "segment_id": segment["id"], "language": code, "issue": f"Placeholder missing: {token}"})
        lang_dir = root / "output" / code
        if not any(lang_dir.glob("*.html")):
            issues.append({"severity": "critical", "language": code, "issue": "No reconstructed HTML output"})
        if code == "ar":
            ar_html = "\n".join(path.read_text(encoding="utf-8") for path in lang_dir.glob("*.html"))
            if 'lang="ar"' not in ar_html and 'dir="rtl"' not in ar_html:
                issues.append({"severity": "critical", "language": code, "issue": "Arabic output is missing lang=\"ar\" or dir=\"rtl\""})
    report = {
        "summary": {
            "segments_checked": len(segments),
            "languages_checked": [language["code"] for language in languages],
            "critical_issues": sum(1 for issue in issues if issue["severity"] == "critical"),
            "warnings": sum(1 for issue in issues if issue["severity"] == "warning"),
        },
        "issues": issues,
    }
    (root / "qa_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
