"""Hämta korsordsdata från app.korsord.io.

Strategi:
  1. GET /c/<slug>-<week>-<year>/ → HTML
  2. Regex ut WX.FetchCrossword(".../media/<uuid>.crossword")
  3. GET den URL:en → JSON med korsordsdata
"""
from __future__ import annotations

import json
import re
import urllib.request

BASE = "https://app.korsord.io"
UA = "Mozilla/5.0 (compatible; korsordio-render)"
_FETCH_RE = re.compile(r'WX\.FetchCrossword\("([^"]+\.crossword)"\)')


def _http_get(url: str, accept: str = "*/*") -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def crossword_data_url(slug: str, week: int, year: int) -> str:
    """Hitta `.crossword`-URL:en för ett givet kryss genom att skrapa
    HTML-sidan. Returnerar absolut URL.
    """
    html = _http_get(
        f"{BASE}/c/{slug}-{week}-{year:02d}/", accept="text/html"
    ).decode("utf-8", errors="replace")
    match = _FETCH_RE.search(html)
    if not match:
        raise RuntimeError(
            f"Could not find WX.FetchCrossword reference in HTML for "
            f"{slug} v{week}-{year}"
        )
    return match.group(1)


def fetch_crossword(slug: str, week: int, year: int) -> dict:
    """Hämta korsordsdata som parsed dict.

    `year` är två-siffrigt (26 = 2026). Sverigekrysset/Miljonkrysset
    publiceras med URL-mönstret `/c/<slug>-<week>-<yy>/`.
    """
    url = crossword_data_url(slug, week, year)
    return json.loads(_http_get(url, accept="application/json"))
