"""Hämta korsordsdata från app.korsord.io.

Strategi:
  1. GET /c/<slug>-<week>-<year>/ → HTML
  2. Regex ut WX.FetchCrossword(".../media/<uuid>.crossword")
  3. GET den URL:en → JSON med korsordsdata

Tävlingsinfo (`fetch_competition_info`) skrapas från samma HTML-sidans
"Tävla"-modal — robust om koderna eller priserna ändras.
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass

BASE = "https://app.korsord.io"
UA = "Mozilla/5.0 (compatible; korsordio-render)"
_FETCH_RE = re.compile(r'WX\.FetchCrossword\("([^"]+\.crossword)"\)')

# Tävla-modalens block: <h4>Via X</h4> följt av <p ...>instruktioner</p>
_WAY_RE = re.compile(
    r'<h4 class="text-center text-danger">([^<]+)</h4>\s*'
    r'<p class="text-center minh-lg-96">(.+?)</p>',
    re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


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


@dataclass(frozen=True)
class CompetitionWay:
    name: str           # t.ex. "Via webben"
    instructions: str   # ren text utan HTML-taggar


@dataclass(frozen=True)
class CompetitionInfo:
    header: str = "Tävla med din lösning!"
    subheader: str = "Vi lottar ut trisslotter bland de rätta svaren."
    ways: tuple[CompetitionWay, ...] = ()


def fetch_competition_info(slug: str, week: int, year: int) -> CompetitionInfo:
    """Hämta strukturerad tävlingsinfo från Tävla-modalen.

    Skrapar från HTML-sidan så att texterna alltid är aktuella —
    om korsord.io ändrar priser, telefonnummer eller webbplats följer
    renderingen automatiskt med nästa hämtning.
    """
    html = _http_get(
        f"{BASE}/c/{slug}-{week}-{year:02d}/", accept="text/html"
    ).decode("utf-8", errors="replace")
    ways = []
    for title, raw in _WAY_RE.findall(html):
        clean = _WS_RE.sub(" ", _TAG_RE.sub("", raw)).strip()
        ways.append(CompetitionWay(name=title.strip(), instructions=clean))
    return CompetitionInfo(ways=tuple(ways))
