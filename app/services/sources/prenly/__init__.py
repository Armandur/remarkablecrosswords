import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import requests
from pypdf import PdfReader, PdfWriter
from prenly_dl import download_pdf, get_context_token, get_hashes, get_issue_json

from app.config import PDF_CROSSWORDS_DIR
from app.services.sources.base import ExternalIssue, SourceFetcher, render_filename

if TYPE_CHECKING:
    from app.database import Source

logger = logging.getLogger(__name__)

_ISSUES_URL = "https://apicdn.prenly.com/api/web-reader/v1/issues"


def _make_conf(cfg: dict) -> dict:
    return {
        "credentials": {
            "textalk-auth": cfg["textalk_auth"],
            "auth": cfg["auth"],
            "site": cfg["site"],
        },
        "publication": {"title": cfg["title_id"]},
    }


def _page_contains_text(pdf_bytes: bytes, needle: str) -> bool:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    for page in reader.pages:
        if needle.lower() in page.extract_text().lower():
            return True
    return False


def _find_semi_transparent_gs_names(page) -> set[str]:
    """Returnerar namnen på alla grafiktillstånd med fill-opacity < 1 i sidans resurser."""
    try:
        ext_g_state = page["/Resources"].get("/ExtGState", {})
        names = set()
        for name, gs in ext_g_state.items():
            ca = gs.get("/ca")
            if ca is not None:
                try:
                    if float(ca) < 1.0:
                        names.add(str(name))
                except (ValueError, TypeError):
                    pass
        return names
    except Exception:
        return {"/GS2"}  # fallback till känt värde


def _filter_instructions(instructions: list, gs_names: set[str]) -> list:
    """Tar rekursivt bort q...Q-block där ett semi-transparent gs är direkt barn (ej nästlat)."""
    output = []
    instr = list(instructions)
    i = 0
    while i < len(instr):
        operands, operator = instr[i]
        if str(operator) == "q":
            # Hitta matchande Q
            depth, j = 1, i + 1
            while j < len(instr) and depth > 0:
                s = str(instr[j][1])
                if s == "q":
                    depth += 1
                elif s == "Q":
                    depth -= 1
                j += 1
            inner = instr[i + 1 : j - 1]

            # Kolla om ett semi-transparent gs är ett DIREKT barn (inte inne i nästlat q...Q)
            direct_has_overlay_gs = False
            inner_depth = 0
            for ops, op2 in inner:
                s = str(op2)
                if s == "q":
                    inner_depth += 1
                elif s == "Q":
                    inner_depth -= 1
                elif s == "gs" and inner_depth == 0 and ops and str(ops[0]) in gs_names:
                    direct_has_overlay_gs = True
                    break

            if direct_has_overlay_gs:
                i = j  # kasta detta block
            else:
                output.append(instr[i])        # q
                output.extend(_filter_instructions(inner, gs_names))
                output.append(instr[j - 1])    # Q
                i = j
        else:
            output.append((operands, operator))
            i += 1
    return output


def _is_full_page_overlay(page, gs_names: set[str]) -> bool:
    """Returnerar True om >80% av sidans instruktioner ligger i semi-transparenta block.

    Indikerar att hela sidan är inlindad i en overlay (kampanjsida utan korsord),
    till skillnad från ett litet overlay-block ovanpå ett verkligt korsord.
    """
    instrs = list(pikepdf.parse_content_stream(page))
    if not instrs:
        return False
    inside = 0
    i = 0
    while i < len(instrs):
        ops, op = instrs[i]
        if str(op) == "q":
            depth, j = 1, i + 1
            while j < len(instrs) and depth > 0:
                s = str(instrs[j][1])
                depth += (s == "q") - (s == "Q")
                j += 1
            inner = instrs[i + 1 : j - 1]
            inner_depth = 0
            has_overlay = False
            for o2, op2 in inner:
                s = str(op2)
                if s == "q":
                    inner_depth += 1
                elif s == "Q":
                    inner_depth -= 1
                elif s == "gs" and inner_depth == 0 and o2 and str(o2[0]) in gs_names:
                    has_overlay = True
                    break
            if has_overlay:
                inside += len(inner)
            i = j
        else:
            i += 1
    return inside / len(instrs) > 0.8


def _find_crossword_image(
    page,
    min_pixels: int = 500_000,
    min_stream_bytes: int = 10_000,
) -> tuple[str, tuple[float, float, float, float, float, float], tuple[float, float, float, float], int] | None:
    """Hittar korsordsbilden på en redaktionssida med gammal Yippie-layout.

    Algoritm:
    1. Uteslut bilder vars komprimerade ström är < min_stream_bytes (solida fylfärger).
    2. Uteslut bilder med färre pixlar än min_pixels.
    3. Bland kvarvarande: välj den SISTA i ritordningen vars center_y > page_height/2
       (övre halvan av sidan i PDF-koordinater, y=0 nere).

    Returnerar (img_name, cm_matrix, bbox, pixel_count) eller None.
    img_name inkluderar slash, t.ex. '/Im28'.
    cm_matrix = (a, b, c, d, e, f) från cm-instruktionen.
    bbox = (x1, y1, x2, y2) i sidans koordinatsystem.
    """
    media_box = page.get("/MediaBox")
    page_height = float(str(media_box[3])) if media_box and len(media_box) >= 4 else 841.0

    xobjs = page["/Resources"].get("/XObject", {})
    eligible: dict[str, int] = {}
    for name, xobj in xobjs.items():
        if xobj.get("/Subtype") != "/Image":
            continue
        w = int(xobj.get("/Width", 0))
        h = int(xobj.get("/Height", 0))
        if w * h < min_pixels:
            continue
        try:
            stream_len = len(xobj.read_raw_bytes())
        except Exception:
            stream_len = min_stream_bytes + 1
        if stream_len < min_stream_bytes:
            continue
        eligible[str(name)] = w * h

    if not eligible:
        return None

    instrs = list(pikepdf.parse_content_stream(page))
    best: tuple[str, tuple[float, float, float, float, float, float], tuple[float, float, float, float], int] | None = None

    for i, (ops, op) in enumerate(instrs):
        if str(op) != "Do" or not ops:
            continue
        name = str(ops[0])
        if name not in eligible:
            continue
        for j in range(i - 1, max(0, i - 6), -1):
            o2, op2 = instrs[j]
            if str(op2) == "cm" and len(o2) == 6:
                a, b, c, d, e, f = [float(str(x)) for x in o2]
                x1, y1 = e, f
                x2, y2 = e + a, f + d
                bbox = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                center_y = (bbox[1] + bbox[3]) / 2
                if center_y > page_height / 2:
                    best = (name, (a, b, c, d, e, f), bbox, eligible[name])
                break

    return best


def _extract_image_to_bytes(
    pdf_bytes: bytes,
    min_pixels: int = 500_000,
    min_stream_bytes: int = 10_000,
) -> bytes | None:
    """Skapar en ren ensides-PDF med bara korsordsbilden – ingen text eller grafik.

    Ersätter hela innehållsströmmen med enbart bildritningsinstruktionen
    så att eventuell SE KRYSSET-text och annan overlay försvinner.
    Returnerar None om ingen kvalificerad bild hittas i övre halvan.
    """
    src = pikepdf.Pdf.open(io.BytesIO(pdf_bytes))
    page = src.pages[0]
    result = _find_crossword_image(page, min_pixels, min_stream_bytes)
    if result is None:
        return None

    img_name, (a, b, c, d, e, f), bbox, _ = result
    x1, y1, x2, y2 = bbox

    new_content = f"q {a} {b} {c} {d} {e} {f} cm {img_name} Do Q\n".encode()

    page["/MediaBox"] = pikepdf.Array([round(x1, 4), round(y1, 4), round(x2, 4), round(y2, 4)])
    if "/CropBox" in page:
        del page["/CropBox"]

    contents = page.get("/Contents")
    if isinstance(contents, pikepdf.Array):
        page["/Contents"] = pikepdf.Stream(src, new_content)
    else:
        contents.write(new_content)

    buf = io.BytesIO()
    src.save(buf)
    return buf.getvalue()


def _crop_page(pdf_bytes: bytes, bbox: tuple[float, float, float, float], out_path: Path) -> Path:
    """Beskär sidan till angiven bounding box via MediaBox och sparar."""
    src = pikepdf.Pdf.open(io.BytesIO(pdf_bytes))
    page = src.pages[0]
    x1, y1, x2, y2 = bbox
    page["/MediaBox"] = pikepdf.Array([
        round(x1, 4), round(y1, 4), round(x2, 4), round(y2, 4),
    ])
    if "/CropBox" in page:
        del page["/CropBox"]
    src.save(str(out_path))
    return out_path


def _remove_overlay_from_page(
    pdf_bytes: bytes,
    out_path: Path,
    crop_bbox: tuple[float, float, float, float] | None = None,
    gs_names: set[str] | None = None,
) -> Path:
    """Tar bort overlay-blocket ur innehållsströmmen och sparar ren PDF."""
    src = pikepdf.Pdf.open(io.BytesIO(pdf_bytes))
    page = src.pages[0]

    if gs_names is None:
        gs_names = _find_semi_transparent_gs_names(page)
    logger.debug("Semi-transparenta grafiktillstånd att ta bort: %s", gs_names)

    instructions = list(pikepdf.parse_content_stream(page))
    filtered = _filter_instructions(instructions, gs_names)
    new_stream = pikepdf.unparse_content_stream(filtered)

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


class PrenlyFetcher(SourceFetcher):
    def list_available(self, source: "Source") -> list[ExternalIssue]:
        cfg = json.loads(source.config_json or "{}")
        try:
            session = requests.Session()
            conf = _make_conf(cfg)
            token = get_context_token(session, conf)
            limit = int(cfg.get("backfill_limit", 5))
            url = f"{_ISSUES_URL}?title_ids[]={cfg['title_id']}&limit={limit}&context_token={token}"
            resp = session.get(url, headers={"Origin": cfg["site"], "Referer": f"{cfg['site']}/"})
            resp.raise_for_status()
            issues = []
            for item in resp.json():
                pub = None
                for date_field in ("published_at", "publication_date", "released_at", "activation_date", "valid_from", "date"):
                    val = item.get(date_field)
                    if val:
                        try:
                            pub = datetime.fromisoformat(str(val).replace(" ", "T"))
                            break
                        except ValueError:
                            pass
                issues.append(ExternalIssue(
                    external_id=str(item["uid"]),
                    name=item.get("name") or str(item["uid"]),
                    published_at=pub,
                ))
            return issues
        except Exception as e:
            logger.error("Prenly list_available misslyckades: %s", e)
            return []

    def download(self, source: "Source", ext_issue: ExternalIssue) -> Path:
        cfg = json.loads(source.config_json or "{}")
        cdn = cfg.get("cdn", "https://mediacdn.prenly.com")
        marker: str | None = cfg.get("crossword_marker_text")
        extraction_pages: list[int] = cfg.get("extraction_pages") or []

        session = requests.Session()
        conf = _make_conf(cfg)

        issue_dict = {"title": cfg["title_id"], "uid": ext_issue.external_id}
        try:
            data = get_issue_json(session, issue_dict, conf)
        except SystemExit as e:
            raise RuntimeError(f"Prenly get_issue_json misslyckades (kod {e.code})") from e

        hashes = get_hashes(data)
        PDF_CROSSWORDS_DIR.mkdir(parents=True, exist_ok=True)
        
        if source.filename_template:
            base = render_filename(source.filename_template, ext_issue, source.name)
        else:
            base = render_filename("{name}", ext_issue, source.name)

        if marker:
            # Hitta sidan med markertexten och extrahera dess inbäddade bild
            for page_num, checksum in hashes.items():
                try:
                    resp = download_pdf(session, conf, checksum, cdn=cdn)
                except SystemExit as e:
                    raise RuntimeError(f"Prenly download_pdf misslyckades (kod {e.code})") from e
                if "pdf" not in resp.headers.get("Content-Type", "").lower():
                    continue
                if _page_contains_text(resp.content, marker):
                    logger.info("Hittade korsordssida (sid %s) via marker '%s'", page_num, marker)
                    return _remove_overlay_from_page(resp.content, PDF_CROSSWORDS_DIR / f"{base}-crossword.pdf")
            raise RuntimeError(f"Hittade ingen sida med texten '{marker}'")

        # Ladda ned alla sidor och slå ihop
        writer = PdfWriter()
        for _page_num, checksum in hashes.items():
            try:
                resp = download_pdf(session, conf, checksum, cdn=cdn)
            except SystemExit as e:
                raise RuntimeError(f"Prenly download_pdf misslyckades (kod {e.code})") from e
            ct = resp.headers.get("Content-Type", "").lower()
            if "pdf" in ct:
                writer.append(PdfReader(io.BytesIO(resp.content)))
            else:
                import img2pdf
                writer.append(PdfReader(io.BytesIO(img2pdf.convert(resp.content))))

        if extraction_pages:
            out_path = PDF_CROSSWORDS_DIR / f"{base}-crossword.pdf"
            xw = PdfWriter()
            for p in extraction_pages:
                if 1 <= p <= len(writer.pages):
                    xw.add_page(writer.pages[p - 1])
            with open(out_path, "wb") as f:
                xw.write(f)
        else:
            out_path = PDF_CROSSWORDS_DIR / f"{base}.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)

        return out_path
