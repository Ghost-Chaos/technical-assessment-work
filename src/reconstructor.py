import json
from pathlib import Path

from bs4 import BeautifulSoup


def write_translations(root: Path, translations):
    base = root / "translations"
    for language_code, language_translations in translations.items():
        lang_dir = base / language_code
        lang_dir.mkdir(parents=True, exist_ok=True)
        (lang_dir / "segments.json").write_text(
            json.dumps(language_translations, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def reconstruct_html(root: Path, prepared_pages, languages, translations):
    output_root = root / "output"
    for language in languages:
        code = language["code"]
        lang_dir = output_root / code
        lang_dir.mkdir(parents=True, exist_ok=True)
        for page in prepared_pages:
            soup = BeautifulSoup(page["html"], "lxml")
            html_tag = soup.find("html")
            if html_tag:
                html_tag["lang"] = code
                if language.get("rtl"):
                    html_tag["dir"] = "rtl"
                elif html_tag.has_attr("dir"):
                    del html_tag["dir"]
            for tag in soup.select("[data-segment-id]"):
                segment_id = tag.get("data-segment-id")
                translated = translations[code].get(segment_id, {}).get("translated")
                if translated:
                    for child in list(tag.children):
                        if isinstance(child, str):
                            child.replace_with(translated)
                            break
                    del tag["data-segment-id"]
            for tag in soup.select("[data-alt-segment-id]"):
                segment_id = tag.get("data-alt-segment-id")
                translated = translations[code].get(segment_id, {}).get("translated")
                if translated:
                    tag["alt"] = translated
                del tag["data-alt-segment-id"]
            (lang_dir / f"{page['id']}.html").write_text(str(soup), encoding="utf-8")
