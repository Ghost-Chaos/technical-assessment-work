from pathlib import Path

import requests


SAMPLE_HTML = """<!doctype html>
<html lang="en">
<head><title>Deriv sample</title></head>
<body>
  <nav><a href="/markets/">Markets</a><a href="/trading-platforms/">Platforms</a></nav>
  <main>
    <h1>Trade Forex, Synthetic Indices, and CFDs with Deriv</h1>
    <p>Explore Deriv Bot, Deriv MT5, Deriv X, SmartTrader, and Multipliers.</p>
    <a href="https://deriv.com/signup/?platform=mt5" class="button">Create free account</a>
    <img src="/images/deriv-mt5.png" alt="Deriv MT5 trading platform">
    <p>Start with {{currency}} and keep your account_id token unchanged.</p>
  </main>
</body>
</html>"""


def fetch_pages(pages, root: Path, limit: int = 2):
    fetched = []
    raw_dir = root / "outputs" / "fetched_pages"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for page in pages[:limit]:
        page_id = page.get("id") or f"page_{len(fetched) + 1}"
        source = "network"
        try:
            response = requests.get(page["url"], timeout=12, headers={"User-Agent": "assessment-translator/1.0"})
            response.raise_for_status()
            html = response.text
        except Exception as exc:
            source = "sample_fallback"
            html = SAMPLE_HTML.replace("Deriv sample", page.get("title", "Deriv sample"))
            page = {**page, "fetch_error": str(exc)}
        path = raw_dir / f"{page_id}.html"
        path.write_text(html, encoding="utf-8")
        fetched.append({**page, "id": page_id, "html": html, "source": source, "raw_path": str(path)})
    return fetched
