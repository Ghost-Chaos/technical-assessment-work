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
            translated = translations[code][segment["id"]]["translated"]
            for term in protected_terms:
                if term in segment["text"] and term not in translated:
                    issues.append({"severity": "critical", "segment_id": segment["id"], "language": code, "issue": f"Protected term missing: {term}"})
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
        },
        "issues": issues,
    }
    (root / "qa_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
