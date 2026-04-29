import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import img2pdf

from keesing.fetch import _get_image, _get_puzzle_info, _get_xml
from keesing.render import render_pdf as keesing_render_pdf, supports_xml
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
                _, title, variation, _ = _get_xml(client_id, kse_id)
            except Exception:
                logger.exception("getxml misslyckades för %s", kse_id)
                title, variation = "", ""

            issues.append(ExternalIssue(
                external_id=kse_id,
                name=title or variation or slot,
                published_at=published_at,
            ))

        return issues

    def download(self, source: "Source", ext_issue: ExternalIssue) -> tuple[Path, list[str]]:
        config = json.loads(source.config_json or "{}")
        client_id = config.get("client_id", "dnmag")

        kse_id = ext_issue.external_id
        date_str = ext_issue.published_at.strftime("%Y-%m-%d") if ext_issue.published_at else None

        xml_bytes, title, variation, _ = _get_xml(client_id, kse_id)
        png_bytes = _get_image(client_id, kse_id)

        PDF_CROSSWORDS_DIR.mkdir(parents=True, exist_ok=True)
        if source.filename_template:
            filename = render_filename(source.filename_template, ext_issue, source.name)
            out_path = PDF_CROSSWORDS_DIR / f"{filename}.pdf"
        else:
            label = title or variation or kse_id
            prefix = f"{date_str} - " if date_str else ""
            out_path = PDF_CROSSWORDS_DIR / f"{prefix}{label}.pdf"

        if supports_xml(xml_bytes):
            keesing_render_pdf(xml_bytes, out_path, image_bytes=png_bytes, date_str=date_str)
        else:
            out_path.write_bytes(img2pdf.convert(png_bytes))

        return out_path, []
