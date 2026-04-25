import io
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import requests
from pypdf import PdfReader, PdfWriter
from prenly_dl import download_pdf, get_hashes, get_issue_json

from app.config import PDF_CROSSWORDS_DIR
from app.services.sources.base import ExternalIssue, NoCrosswordError
from app.services.sources.prenly import (
    PrenlyFetcher,
    _make_conf,
    _page_contains_text,
    _remove_overlay_from_page,
    _find_semi_transparent_gs_names,
    _is_full_page_overlay,
    _find_crossword_image,
    _crop_page,
)

if TYPE_CHECKING:
    from app.database import Source

logger = logging.getLogger(__name__)

_CROSSWORD_MARKER = "SE KRYSSET"
_MIN_IMAGE_PIXELS = 500_000


def _crop_to_bytes(pdf_bytes: bytes, bbox: tuple[float, float, float, float]) -> bytes:
    """Beskär sidan till bbox och returnerar PDF-bytes (sparar inte till disk)."""
    src = pikepdf.Pdf.open(io.BytesIO(pdf_bytes))
    page = src.pages[0]
    x1, y1, x2, y2 = bbox
    page["/MediaBox"] = pikepdf.Array([
        pikepdf.Decimal(str(round(x1, 4))),
        pikepdf.Decimal(str(round(y1, 4))),
        pikepdf.Decimal(str(round(x2, 4))),
        pikepdf.Decimal(str(round(y2, 4))),
    ])
    if "/CropBox" in page:
        del page["/CropBox"]
    buf = io.BytesIO()
    src.save(buf)
    return buf.getvalue()


class YippieHarnosandFetcher(PrenlyFetcher):
    """Prenly-fetcher specifikt för Yippie Härnösand.

    Hanterar tre layoutvarianter:
    - Ny layout: litet semi-transparent overlay-block ovanpå korsordet → ta bort overlay
    - Gammal layout utan overlay: hel redaktionssida med korsord i övre halvan → beskär
      och kombinera med nästa sida till en tvåsidig PDF
    - Kampanjsida (placeholder): hela sidan inlindad i overlay utan korsord → NoCrosswordError
    """

    def download(self, source: "Source", ext_issue: ExternalIssue) -> Path:
        cfg = json.loads(source.config_json or "{}")
        cdn = cfg.get("cdn", "https://mediacdn.prenly.com")

        session = requests.Session()
        conf = _make_conf(cfg)

        issue_dict = {"title": cfg["title_id"], "uid": ext_issue.external_id}
        try:
            data = get_issue_json(session, issue_dict, conf)
        except SystemExit as e:
            raise RuntimeError(f"get_issue_json misslyckades (kod {e.code})") from e

        hashes = get_hashes(data)
        page_nums = list(hashes.keys())
        PDF_CROSSWORDS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = PDF_CROSSWORDS_DIR / f"yippie-{source.id}-{ext_issue.external_id}-crossword.pdf"

        for idx, page_num in enumerate(page_nums):
            checksum = hashes[page_num]
            try:
                resp = download_pdf(session, conf, checksum, cdn=cdn)
            except SystemExit as e:
                raise RuntimeError(f"download_pdf misslyckades (kod {e.code})") from e
            if "pdf" not in resp.headers.get("Content-Type", "").lower():
                continue
            if not _page_contains_text(resp.content, _CROSSWORD_MARKER):
                continue

            logger.info("Korsordssida hittad (sid %s)", page_num)

            src_pdf = pikepdf.Pdf.open(io.BytesIO(resp.content))
            page = src_pdf.pages[0]
            gs_names = _find_semi_transparent_gs_names(page)

            if gs_names:
                if _is_full_page_overlay(page, gs_names):
                    raise NoCrosswordError(
                        f"Nummer {ext_issue.external_id} har helsidestäckande overlay "
                        f"(gs: {gs_names}) utan korsord"
                    )
                logger.info("Ny layout: tar bort overlay-block (gs: %s)", gs_names)
                return _remove_overlay_from_page(resp.content, out_path)

            # Gammal redaktionslayout utan overlay
            result = _find_crossword_image(page)
            if result is None:
                raise NoCrosswordError(
                    f"Nummer {ext_issue.external_id} har platshållarsida utan korsordsbild"
                )
            bbox1, largest_px = result
            if largest_px < _MIN_IMAGE_PIXELS:
                raise NoCrosswordError(
                    f"Nummer {ext_issue.external_id} har platshållarsida utan tillräckligt stort korsord"
                )

            logger.info("Gammal layout (sid 1): beskär till bbox %s", bbox1)
            page1_bytes = _crop_to_bytes(resp.content, bbox1)

            # Hämta nästa sida och kombinera
            page2_bytes: bytes | None = None
            if idx + 1 < len(page_nums):
                next_num = page_nums[idx + 1]
                next_checksum = hashes[next_num]
                try:
                    resp2 = download_pdf(session, conf, next_checksum, cdn=cdn)
                    if "pdf" in resp2.headers.get("Content-Type", "").lower():
                        src2 = pikepdf.Pdf.open(io.BytesIO(resp2.content))
                        page2 = src2.pages[0]
                        result2 = _find_crossword_image(page2)
                        if result2 is not None:
                            bbox2, _ = result2
                            logger.info("Gammal layout (sid 2): beskär till bbox %s", bbox2)
                            page2_bytes = _crop_to_bytes(resp2.content, bbox2)
                        else:
                            logger.info("Nästa sida (sid %s) saknar korsordsbild", next_num)
                except Exception as e:
                    logger.warning("Kunde inte hämta nästa sida (sid %s): %s", next_num, e)

            writer = PdfWriter()
            writer.append(PdfReader(io.BytesIO(page1_bytes)))
            if page2_bytes:
                writer.append(PdfReader(io.BytesIO(page2_bytes)))

            with open(out_path, "wb") as f:
                writer.write(f)
            return out_path

        raise NoCrosswordError(f"Inget korsord i nummer {ext_issue.external_id}")
