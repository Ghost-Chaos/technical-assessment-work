import json
from pathlib import Path

from bs4 import BeautifulSoup


TEXT_TAGS = {
    "a",
    "button",
    "figcaption",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "label",
    "li",
    "p",
    "span",
    "strong",
    "title",
}


def _segment_type(tag, attr=None):
    if attr == "alt":
        return "alt_text"
    if tag.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return "heading"
    if tag.name in {"a", "button"}:
        return "cta_or_nav"
    return "body"


def extract_segments(fetched_pages, root: Path):
    segments = []
    prepared_pages = []
    for page in fetched_pages:
        soup = BeautifulSoup(page["html"], "lxml")
        page_id = page["id"]
        for node_index, tag in enumerate(soup.find_all(True)):
            if tag.name in {"script", "style", "noscript"}:
                continue
            if tag.name in TEXT_TAGS:
                direct_text = "".join(str(child) for child in tag.children if isinstance(child, str)).strip()
                if direct_text:
                    segment_id = f"{page_id}:text:{node_index}"
                    tag["data-segment-id"] = segment_id
                    segments.append(
                        {
                            "id": segment_id,
                            "page_id": page_id,
                            "field": "text",
                            "tag": tag.name,
                            "type": _segment_type(tag),
                            "text": direct_text,
                        }
                    )
            if tag.has_attr("alt") and tag["alt"].strip():
                segment_id = f"{page_id}:alt:{node_index}"
                tag["data-alt-segment-id"] = segment_id
                segments.append(
                    {
                        "id": segment_id,
                        "page_id": page_id,
                        "field": "alt",
                        "tag": tag.name,
                        "type": "alt_text",
                        "text": tag["alt"].strip(),
                    }
                )
        prepared_pages.append({**page, "html": str(soup)})
    (root / "extracted_segments.json").write_text(
        json.dumps(segments, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return segments, prepared_pages
