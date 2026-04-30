import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import img2pdf

from keesing.fetch import _get_image, _get_puzzle_info, _get_xml
from keesing.render import render_pdf as keesing_render_pdf, supports_xml
from keesing.render_crossword import render_crossword_pdf, supports_crossword_xml
from keesing.render_sudoku import render_sudoku_pdf, supports_sudoku_xml
from keesing.render_tectonic import render_tectonic_pdf, supports_tectonic_xml
from app.config import PDF_CROSSWORDS_DIR
from app.services.sources.base import ExternalIssue, SourceFetcher, render_filename

if TYPE_CHECKING:
    from app.database import Source

logger = logging.getLogger(__name__)

DEFAULT_SLOTS = [f"x{n}" for n in range(1, 10)]


class KeesingFetcher(SourceFetcher):
    def list_available(self, source: "Source") -> list[ExternalIssue]:
        config = json.loads(source.config_json or "{}")
        client_id = config.get("client_id", "dnmag")
        gametype = config.get("gametype", "arrowword_plus")
        slots = config.get("slots", DEFAULT_SLOTS)

        issues = []
        seen_kse: set[str] = set()
        for slot in slots:
            puzzle_id = f"{gametype}_{slot}_today_"
            try:
                info = _get_puzzle_info(client_id, puzzle_id)
            except Exception:
                logger.exception("GetPuzzleInfo misslyckades för slot %s", slot)
                continue
            if info is None:
                continue
            kse_id = info["puzzleID"]
            if kse_id in seen_kse:
                continue
            seen_kse.add(kse_id)

            try:
                published_at: datetime | None = datetime.fromisoformat(info.get("date", ""))
            except (ValueError, TypeError):
                published_at = None

            try:
                xml_bytes, title, variation, byline = _get_xml(client_id, kse_id)
                root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
                ipsrecipe = root.get("ipsrecipe", "")
                difficulty = root.get("difficulty", "")

                series = ""
                if "_" in ipsrecipe:
                    parts = ipsrecipe.split("_")
                    if len(parts) > 2:
                        series = parts[2]

                extra = {
                    "series": series,
                    "difficulty": difficulty,
                    "slot": slot,
                    "byline": byline,
                }
            except Exception:
                logger.exception("getxml misslyckades för %s", kse_id)
                title, variation, byline = "", "", ""
                extra = {"slot": slot}

            issues.append(ExternalIssue(
                external_id=kse_id,
                name=extra.get("series") or title or variation or slot,
                published_at=published_at,
                extra=extra,
            ))

        return issues

    def download(self, source: "Source", ext_issue: ExternalIssue) -> tuple[Path, list[str]]:
        config = json.loads(source.config_json or "{}")
        client_id = config.get("client_id", "dnmag")

        kse_id = ext_issue.external_id
        date_str = ext_issue.published_at.strftime("%Y-%m-%d") if ext_issue.published_at else None

        xml_bytes, title, variation, _ = _get_xml(client_id, kse_id)

        PDF_CROSSWORDS_DIR.mkdir(parents=True, exist_ok=True)
        if source.filename_template:
            filename = render_filename(source.filename_template, ext_issue, source.name)
            out_path = PDF_CROSSWORDS_DIR / f"{filename}.pdf"
        else:
            label = ext_issue.name or kse_id
            prefix = f"{date_str} - " if date_str else ""
            out_path = PDF_CROSSWORDS_DIR / f"{prefix}{label}.pdf"

        if supports_xml(xml_bytes):
            png_bytes = _get_image(client_id, kse_id)
            keesing_render_pdf(xml_bytes, out_path, image_bytes=png_bytes, date_str=date_str)
        elif supports_crossword_xml(xml_bytes):
            render_crossword_pdf(xml_bytes, out_path, date_str=date_str)
        elif supports_sudoku_xml(xml_bytes):
            render_sudoku_pdf(xml_bytes, out_path, date_str=date_str)
        elif supports_tectonic_xml(xml_bytes):
            render_tectonic_pdf(xml_bytes, out_path, date_str=date_str)
        else:
            png_bytes = _get_image(client_id, kse_id)
            out_path.write_bytes(img2pdf.convert(png_bytes))

        return out_path, []

    def extra_fields(self) -> list[dict]:
        return [
            {"key": "series", "label": "Serie", "example": "Klassikern"},
            {"key": "slot", "label": "Slot", "example": "x6"},
            {"key": "difficulty", "label": "Svårighetsgrad", "example": "5"},
            {"key": "byline", "label": "Upphovsman", "example": "Lina Otterdahl"},
        ]
