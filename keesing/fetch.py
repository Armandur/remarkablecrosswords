"""
Keesing puzzle fetcher - hämtar korsord via Keesing Content API.

API-flöde:
  1. GetPuzzleInfo?clientid=<id>&puzzleid=<slot>_ → KSE-ID + datum
  2. getxml?clientid=<id>&puzzleid=<KSE-ID>      → XML med titel, variation
  3a. Om variation=Arrowword DPG: render_keesing → PDF (ingen bild behövs)
  3b. Annars: getimage → PNG, img2pdf.convert    → PDF

Slot-format: <gametype>_x<N>_today_
  Exempel: arrowword_plus_x1_today_

_today_-aliaser ger alltid det senaste tillgängliga pusslet per slot,
ungefär ett rullande 7-dagarsfönster.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import img2pdf
import requests

try:
    from keesing.render import render_pdf as _keesing_render_pdf, supports_xml as _keesing_supports
    _HAS_KEESING_RENDERER = True
except ImportError:
    _HAS_KEESING_RENDERER = False

BASE_CONTENT = "https://web.keesing.com/content"
BASE_CONTENT_CAP = "https://web.keesing.com/Content"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; keesing-fetcher/1.0)"})


@dataclass
class PuzzleResult:
    slot: str           # t.ex. "x1"
    kse_id: str         # t.ex. "KSE-11360886"
    title: str          # t.ex. "Måndagskrysset"
    variation: str      # t.ex. "Arrowword DPG"
    byline: str
    published_at: date
    pdf_bytes: bytes


def _get_puzzle_info(client_id: str, puzzle_id: str) -> Optional[dict]:
    """Hämtar metadata. Returnerar None om pusslet inte finns."""
    url = f"{BASE_CONTENT_CAP}/GetPuzzleInfo?clientid={client_id}&puzzleid={puzzle_id}&epochtime=1"
    r = SESSION.get(url, timeout=15)
    r.raise_for_status()
    d = r.json()
    if not d.get("puzzleID") or not d.get("puzzleType"):
        return None
    return d


def _get_xml(client_id: str, kse_id: str) -> tuple[bytes, str, str, str]:
    """Returnerar (xml_bytes, title, variation, byline) från puzzle-XML."""
    url = f"{BASE_CONTENT}/getxml?clientid={client_id}&puzzleid={kse_id}"
    r = SESSION.get(url, timeout=15)
    r.raise_for_status()
    xml_bytes = r.content
    try:
        root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
        title = root.findtext("title") or ""
        variation = root.get("variation", "")
        byline = root.findtext("byline") or ""
        return xml_bytes, title, variation, byline
    except ET.ParseError:
        return xml_bytes, "", "", ""


def _get_image(client_id: str, kse_id: str) -> bytes:
    """Hämtar PNG-bilden för pusslet."""
    url = f"{BASE_CONTENT}/getimage?clientid={client_id}&puzzleid={kse_id}"
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    return r.content


def fetch_puzzle(client_id: str, gametype: str, slot: str) -> Optional[PuzzleResult]:
    """
    Hämtar ett pussel för angiven slot (t.ex. "x1").
    Returnerar None om pusslet inte är tillgängligt.
    """
    puzzle_id = f"{gametype}_{slot}_today_"

    info = _get_puzzle_info(client_id, puzzle_id)
    if info is None:
        return None

    kse_id = info["puzzleID"]
    raw_date = info.get("date", "")
    try:
        published_at = datetime.fromisoformat(raw_date).date()
    except (ValueError, TypeError):
        published_at = date.today()

    xml_bytes, title, variation, byline = _get_xml(client_id, kse_id)

    if _HAS_KEESING_RENDERER and _keesing_supports(xml_bytes):
        import tempfile, pathlib
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = pathlib.Path(tmp.name)
        try:
            _keesing_render_pdf(xml_bytes, tmp_path)
            pdf_bytes = tmp_path.read_bytes()
        finally:
            tmp_path.unlink(missing_ok=True)
    else:
        png_bytes = _get_image(client_id, kse_id)
        pdf_bytes = img2pdf.convert(png_bytes)

    return PuzzleResult(
        slot=slot,
        kse_id=kse_id,
        title=title,
        variation=variation,
        byline=byline,
        published_at=published_at,
        pdf_bytes=pdf_bytes,
    )


def fetch_all(client_id: str, gametype: str, slots: list[str]) -> list[PuzzleResult]:
    """Hämtar alla tillgängliga pussel för angiven lista av slots."""
    results = []
    for slot in slots:
        result = fetch_puzzle(client_id, gametype, slot)
        if result:
            results.append(result)
    return results

