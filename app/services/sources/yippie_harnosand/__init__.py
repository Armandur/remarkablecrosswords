import io
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import requests
from pypdf import PageObject, PdfReader, PdfWriter, Transformation
from prenly_dl import download_pdf, get_hashes, get_issue_json

from app.config import PDF_CROSSWORDS_DIR
from app.services.sources.base import ExternalIssue, NoCrosswordError, render_filename
from app.services.sources.prenly import (
    PrenlyFetcher,
    _make_conf,
    _page_contains_text,
    _find_semi_transparent_gs_names,
    _filter_instructions,
    _is_full_page_overlay,
    _find_crossword_image,
    _extract_image_to_bytes,
    _remove_overlay_from_page,
)

if TYPE_CHECKING:
    from app.database import Source

logger = logging.getLogger(__name__)

def _merge_side_by_side(page1_bytes: bytes, page2_bytes: bytes) -> bytes:
    """Slår ihop två ensidiga PDF:er till en enda sida med sidorna bredvid varandra."""
    r1 = PdfReader(io.BytesIO(page1_bytes))
    r2 = PdfReader(io.BytesIO(page2_bytes))
    p1 = r1.pages[0]
    p2 = r2.pages[0]

    w1 = float(p1.mediabox.right) - float(p1.mediabox.left)
    h1 = float(p1.mediabox.top) - float(p1.mediabox.bottom)
    ox1 = float(p1.mediabox.left)
    oy1 = float(p1.mediabox.bottom)

    w2 = float(p2.mediabox.right) - float(p2.mediabox.left)
    h2 = float(p2.mediabox.top) - float(p2.mediabox.bottom)
    ox2 = float(p2.mediabox.left)
    oy2 = float(p2.mediabox.bottom)

    combined = PageObject.create_blank_page(width=w1 + w2, height=max(h1, h2))
    combined.merge_transformed_page(p1, Transformation().translate(-ox1, -oy1))
    combined.merge_transformed_page(p2, Transformation().translate(-ox2 + w1, -oy2))

    writer = PdfWriter()
    writer.add_page(combined)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


_CROSSWORD_MARKER = "SE KRYSSET"
_OLD_LAYOUT_MIN_HEIGHT_RATIO = 0.40  # under 40% = ej gammal layout (liten felaktig bild)
_OLD_LAYOUT_MAX_HEIGHT_RATIO = 0.65  # 40–65% = gammal layout; över 65% = ny layout


def _find_overlay_gs_names(page) -> set[str]:
    """Returnerar GS-namn med ca < 1.0 ELLER CA < 1.0 (inkl. stroke-opacity overlays)."""
    try:
        ext_g_state = page["/Resources"].get("/ExtGState", {})
        names = set()
        for name, gs in ext_g_state.items():
            for key in ("/ca", "/CA"):
                val = gs.get(key)
                if val is not None:
                    try:
                        if float(val) < 1.0:
                            names.add(str(name))
                            break
                    except (ValueError, TypeError):
                        pass
        return names
    except Exception:
        return {"/GS2"}


def _remove_marker_text_block(pdf_bytes: bytes, out_path: Path, marker: str) -> Path:
    """Tar bort exakt de BT/ET-block vars borttagning gör att marker försvinner från sidan.

    Alla övriga block (bilder, banor, övrig text) lämnas oförändrade.
    Varje BT-block testas individuellt via trial removal + pypdf-textsökning.
    """
    src = pikepdf.Pdf.open(io.BytesIO(pdf_bytes))
    page = src.pages[0]
    instrs = list(pikepdf.parse_content_stream(page))

    # Samla (bt_start, et_end) för alla BT/ET-block
    bt_ranges: list[tuple[int, int]] = []
    i = 0
    while i < len(instrs):
        if str(instrs[i][1]) == "BT":
            bt_start = i
            i += 1
            while i < len(instrs) and str(instrs[i][1]) != "ET":
                i += 1
            if i < len(instrs):
                bt_ranges.append((bt_start, i))
        i += 1

    remove_indices: set[int] = set()
    for bt_start, et_end in bt_ranges:
        skip = set(range(bt_start, et_end + 1))
        test_instrs = [instr for j, instr in enumerate(instrs) if j not in skip]
        test_stream = pikepdf.unparse_content_stream(test_instrs)

        test_src = pikepdf.Pdf.open(io.BytesIO(pdf_bytes))
        test_page = test_src.pages[0]
        test_contents = test_page.get("/Contents")
        if isinstance(test_contents, pikepdf.Array):
            test_page["/Contents"] = pikepdf.Stream(test_src, test_stream)
        else:
            test_contents.write(test_stream)
        buf = io.BytesIO()
        test_src.save(buf)

        if not _page_contains_text(buf.getvalue(), marker):
            logger.debug("BT-block idx %d–%d innehåller '%s', tas bort", bt_start, et_end, marker)
            remove_indices.update(skip)

    if not remove_indices:
        logger.warning("Hittade inget BT-block med texten '%s'", marker)
        src.save(str(out_path))
        return out_path

    result = [(ops, op) for j, (ops, op) in enumerate(instrs) if j not in remove_indices]
    new_stream = pikepdf.unparse_content_stream(result)
    contents = page.get("/Contents")
    if isinstance(contents, pikepdf.Array):
        page["/Contents"] = pikepdf.Stream(src, new_stream)
    else:
        contents.write(new_stream)

    src.save(str(out_path))
    return out_path


def _collect_q_block(
    instructions: list, start: int
) -> tuple[list | None, int]:
    """Returnerar (block_innehåll, index_efter_Q) för ett q...Q-block som börjar på start."""
    depth, j, block = 1, start, []
    while j < len(instructions) and depth > 0:
        ops, op = instructions[j]
        s = str(op)
        if s == "q":
            depth += 1
        elif s == "Q":
            depth -= 1
        if depth > 0:
            block.append((ops, op))
        j += 1
    return (block, j) if depth == 0 else (None, j)


def _clean_new_layout_page(
    pdf_bytes: bytes,
    out_path: Path,
    crop_bbox: tuple[float, float, float, float] | None = None,
) -> Path:
    """Rensar ny Yippie-layout: tar bort overlay och text men bevarar bilder på plats.

    Tar bort:
    - Semi-transparenta GS overlay-block (q...Q med gs ca<1)
    - Alla BT...ET text-block
    - Fyllda rektanglar (re f) – bakgrundsboxar bakom SE KRYSSET-texten
    - q...Q-block som bara innehåller bilder med liten komprimerad ström (<5 kB)
      – helsidestäckande overlay-bilder utan verkligt bildinnehåll
    """
    src = pikepdf.Pdf.open(io.BytesIO(pdf_bytes))
    page = src.pages[0]

    # Identifiera overlay-bilder med liten komprimerad ström
    xobjs = page["/Resources"].get("/XObject", {})
    tiny_image_names: set[str] = set()
    for name, xobj in xobjs.items():
        if xobj.get("/Subtype") == "/Image":
            try:
                if len(xobj.read_raw_bytes()) < 5_000:
                    tiny_image_names.add(str(name))
            except Exception:
                pass

    gs_names = _find_semi_transparent_gs_names(page)
    instrs = list(pikepdf.parse_content_stream(page))

    # Pass 1: ta bort semi-transparenta GS overlay-block
    after_gs = _filter_instructions(instrs, gs_names)

    # Pass 2: ta bort text, fyllfärgsrektanglar och tiny-bildblock
    result = []
    i = 0
    while i < len(after_gs):
        ops, op = after_gs[i]
        s = str(op)

        # Ta bort BT...ET text-block
        if s == "BT":
            i += 1
            while i < len(after_gs) and str(after_gs[i][1]) != "ET":
                i += 1
            i += 1  # hoppa över ET
            continue

        # Ta bort 're f' (fylld rektangel) men behåll 're W n' (klippning)
        if s == "re" and i + 1 < len(after_gs) and str(after_gs[i + 1][1]) in ("f", "F", "f*"):
            i += 2
            continue

        # Ta bort q...Q-block som enbart innehåller tiny-bildritning
        if s == "q":
            block, end = _collect_q_block(after_gs, i + 1)
            if block is not None:
                has_real = any(
                    str(op2) == "Do" and ops2 and str(ops2[0]) not in tiny_image_names
                    for ops2, op2 in block
                )
                has_tiny = any(
                    str(op2) == "Do" and ops2 and str(ops2[0]) in tiny_image_names
                    for ops2, op2 in block
                )
                if has_tiny and not has_real:
                    i = end
                    continue

        result.append((ops, op))
        i += 1

    new_stream = pikepdf.unparse_content_stream(result)
    contents = page.get("/Contents")
    if isinstance(contents, pikepdf.Array):
        page["/Contents"] = pikepdf.Stream(src, new_stream)
    else:
        contents.write(new_stream)

    if crop_bbox is not None:
        x1, y1, x2, y2 = crop_bbox
        page["/MediaBox"] = pikepdf.Array([round(x1, 4), round(y1, 4), round(x2, 4), round(y2, 4)])
        if "/CropBox" in page:
            del page["/CropBox"]

    src.save(str(out_path))
    return out_path


class YippieHarnosandFetcher(PrenlyFetcher):
    """Prenly-fetcher specifikt för Yippie Härnösand.

    Hanterar tre layoutvarianter:
    - Gammal layout: hel redaktionssida med korsord i övre halvan (<70% av sidans höjd)
      → extrahera korsordsbilden ren, kombinera med nästa sida
    - Ny layout: korsord på (nästan) hel sida (≥70% av sidans höjd), eventuellt med overlay
      → ta bort semi-transparent overlay-block och returnera hela sidan
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
        
        if source.filename_template:
            base = render_filename(source.filename_template, ext_issue, source.name)
        else:
            base = render_filename("{name}", ext_issue, source.name)
        out_path = PDF_CROSSWORDS_DIR / f"{base}.pdf"

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
            gs_names = _find_overlay_gs_names(page)

            if gs_names and _is_full_page_overlay(page, gs_names):
                raise NoCrosswordError(
                    f"Nummer {ext_issue.external_id} har helsidestäckande overlay "
                    f"(gs: {gs_names}) utan korsord"
                )

            result = _find_crossword_image(page)

            if result is not None:
                _img_name, _cm, bbox, _px = result
                x1, y1, x2, y2 = bbox
                media_box = page.get("/MediaBox")
                page_height = float(str(media_box[3])) if media_box and len(media_box) >= 4 else 921.0
                height_ratio = (y2 - y1) / page_height

                if _OLD_LAYOUT_MIN_HEIGHT_RATIO <= height_ratio < _OLD_LAYOUT_MAX_HEIGHT_RATIO:
                    # Gammal layout: korsord är en inbäddad bild i övre halvan
                    logger.info(
                        "Gammal layout (sid 1): korsordsbild extraherad (höjdkvot %.0f%%)",
                        height_ratio * 100,
                    )
                    page1_bytes = _extract_image_to_bytes(resp.content)

                    page2_bytes: bytes | None = None
                    if idx + 1 < len(page_nums):
                        next_num = page_nums[idx + 1]
                        next_checksum = hashes[next_num]
                        try:
                            resp2 = download_pdf(session, conf, next_checksum, cdn=cdn)
                            if "pdf" in resp2.headers.get("Content-Type", "").lower():
                                page2_bytes = _extract_image_to_bytes(resp2.content)
                                if page2_bytes:
                                    logger.info("Gammal layout (sid 2): korsordsbild extraherad")
                                else:
                                    logger.info("Nästa sida (sid %s) saknar korsordsbild", next_num)
                        except Exception as e:
                            logger.warning("Kunde inte hämta nästa sida (sid %s): %s", next_num, e)

                    if page2_bytes:
                        logger.info("Slår ihop sid 1 och sid 2 bredvid varandra")
                        combined = _merge_side_by_side(page1_bytes, page2_bytes)
                        with open(out_path, "wb") as f:
                            f.write(combined)
                    else:
                        with open(out_path, "wb") as f:
                            f.write(page1_bytes)
                    return out_path

                logger.info(
                    "Ny layout: bilden täcker %.0f%% av sidan (utanför gammal-layout-intervall)",
                    height_ratio * 100,
                )

            # Ny layout: steg 1 – ta bort GS-overlay q-block (helsidestäckande bilder m.m.)
            # Steg 2 – om SE KRYSSET-texten fortfarande finns, ta bort det BT-blocket separat
            logger.info("Ny layout: tar bort GS-overlay (gs: %s)", gs_names)
            _remove_overlay_from_page(resp.content, out_path, gs_names=gs_names)
            cleaned = out_path.read_bytes()
            if _page_contains_text(cleaned, _CROSSWORD_MARKER):
                logger.info("Ny layout: '%s' kvar efter overlay-borttagning, tar bort BT-block", _CROSSWORD_MARKER)
                _remove_marker_text_block(cleaned, out_path, _CROSSWORD_MARKER)
            return out_path

        raise NoCrosswordError(f"Inget korsord i nummer {ext_issue.external_id}")
