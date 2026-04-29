"""Rendera Keesing Arrowword DPG-korsord från XML till SVG/PDF.

Stöder: variation "Arrowword DPG"
Ej stödd: PuzzleConstruction Arrowword (saknar ledtrådstexter i XML)

Public API:
    render_svg(xml_bytes: bytes, image_bytes: bytes | None = None) -> str
    render_pdf(xml_bytes: bytes, output: Path, image_bytes: bytes | None = None) -> Path
    supports_xml(xml_bytes: bytes) -> bool
"""
from __future__ import annotations

import base64
import itertools
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

PADDING = 20
STROKE = 1.0
TITLE_FONT_PX = 14
BYLINE_FONT_PX = 10
CLUE_BG = "#c0c0c0"
QUIZ_BG = "#e8e8e8"
SENTENCE_BG = "#fffacd"  # ljusgul bakgrund för quiz-svarsrutor

# Anpassa cellstorlek till A4 bredd (794px vid 96 DPI, ~210mm)
_TARGET_GRID_PX = 754  # 794 - 2*PADDING

_BREAK = "\x1f"    # osynlig brytningsmöjlighet (stavelsegräns); bredd 0
_HYPH_END = "\x1e" # markör: raden bröts vid stavelsegräns → visa bindestreck

CHAR_WIDTHS = {
    "M": 1.00, "W": 1.05, "m": 0.92, "w": 0.92,
    "I": 0.34, "i": 0.34, "l": 0.34, "j": 0.36, "t": 0.44, "f": 0.44,
    "J": 0.58, "L": 0.66, " ": 0.34, "-": 0.42, ".": 0.32, ",": 0.32,
    "!": 0.32, "?": 0.58,
    "Å": 0.85, "Ä": 0.85, "Ö": 0.85, "å": 0.72, "ä": 0.72, "ö": 0.72,
    _BREAK: 0.0,
    _HYPH_END: 0.42,  # tar plats som ett bindestreck vid radbredd-beräkning
}
CHAR_WIDTH_DEFAULT = 0.70
FIT_SAFETY = 0.95
MIN_LINE_TW = 1.2  # minimum visuell bredd (em) per rad; hindrar ensamma bokstäver/artikel
MIN_FONT = 3.0

try:
    import pyphen as _pyphen_mod
    _HYPHEN_DICT: _pyphen_mod.Pyphen | None = _pyphen_mod.Pyphen(lang="sv")
except ImportError:
    _HYPHEN_DICT = None
_HYPHEN_MIN_LEN = 8  # ord kortare än så avstavas inte

# arrow_name → (position, directions[])
# position: 'full' | 'top' | 'bottom'
# direction: 'down' | 'right' | 'up' | 'diag_se' | 'diag_ne'
ARROW_DEFS: dict[str, tuple[str, list[str]]] = {
    "arrowdown":                    ("full",   ["down"]),
    "arrowdownbottom":              ("bottom", ["down"]),
    "arrowdownright":               ("full",   ["down", "right"]),
    "arrowdownrightbottom":         ("bottom", ["down", "right"]),
    "arrowdownrighttop":            ("top",    ["down", "right"]),
    "arrowright":                   ("full",   ["right"]),
    "arrowrightdown":               ("full",   ["right", "down"]),
    "arrowrightdowntop":            ("top",    ["right", "down"]),
    "arrowrighttop":                ("top",    ["right"]),
    "arrowupright":                 ("full",   ["up", "right"]),
    "arrow4590downright":           ("full",   ["diag_se", "right"]),
    "arrow4590rightdown":           ("full",   ["diag_se", "down"]),
    "arrow4590upright":             ("full",   ["diag_ne", "right"]),
    "none":                         ("full",   []),
    "sentencearrowdoubledownright": ("full",   ["down", "right"]),
}


class _Ctx:
    """Skalningskonstanter för aktuell cellstorlek."""

    def __init__(self, cell: int) -> None:
        self.cell = cell
        self.arrow = cell * 0.18
        self.pad_x = max(1.5, cell * 0.04)
        self.pad_y = max(1.0, cell * 0.03)
        self.max_font = cell * 0.28
        self.stroke = STROKE


# ---------------------------------------------------------------------------
# Public API


def supports_xml(xml_bytes: bytes) -> bool:
    """Returnerar True om variationen stöds av denna renderare."""
    try:
        root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
        return root.get("variation", "").startswith("Arrowword DPG")
    except ET.ParseError:
        return False


def render_svg(
    xml_bytes: bytes,
    debug: bool = False,
    image_bytes: bytes | None = None,
    date_str: str | None = None,
    bare: bool = False,
) -> str:
    """Renderar till SVG.

    date_str  – om angivet visas titeln som "Titel - datum" (t.ex. "2026-04-28").
    bare      – om True renderas enbart rutnätet utan rubrik och padding.
    """
    root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
    if not supports_xml(xml_bytes):
        raise ValueError(
            f"Variation '{root.get('variation')}' stöds inte av render_keesing"
        )
    cols = int(root.get("width", 15))
    cell = max(36, min(54, _TARGET_GRID_PX // cols))
    ctx = _Ctx(cell)
    return _build_svg(root, ctx, debug=debug, image_bytes=image_bytes,
                      date_str=date_str, bare=bare)


def render_pdf(
    xml_bytes: bytes,
    output: Path | str,
    debug: bool = False,
    image_bytes: bytes | None = None,
    date_str: str | None = None,
    bare: bool = False,
) -> Path:
    """Kräver cairosvg."""
    import cairosvg  # type: ignore

    out_path = Path(output)
    svg = render_svg(xml_bytes, debug=debug, image_bytes=image_bytes,
                     date_str=date_str, bare=bare)
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=str(out_path))
    return out_path


# ---------------------------------------------------------------------------
# Text-fitting


def _tw(text: str) -> float:
    return sum(CHAR_WIDTHS.get(c, CHAR_WIDTH_DEFAULT) for c in text)


def _fit_font(lines: list[str], box_w: float, box_h: float, ctx: _Ctx) -> float:
    if not lines:
        return MIN_FONT
    widest = max(_tw(ln) for ln in lines) or 1.0
    by_w = box_w / widest * FIT_SAFETY
    by_h = box_h / (len(lines) * 1.15)
    return max(MIN_FONT, min(ctx.max_font, by_w, by_h))


def _apply_splits(
    text: str, splits: list[tuple[int, str]], combo: tuple[int, ...]
) -> list[str] | None:
    """Applicerar en kombination av delningspunkter; returnerar None om ogiltigt."""
    fragments: list[str] = []
    prev_end = 0
    for idx in combo:
        pos, kind = splits[idx]
        left = text[prev_end:pos] if kind == "space" else text[prev_end:pos] + _HYPH_END
        if not left or _tw(left) < MIN_LINE_TW:
            return None
        fragments.append(left)
        prev_end = pos + 1
    last = text[prev_end:]
    if not last or _tw(last) < MIN_LINE_TW:
        return None
    fragments.append(last)
    return fragments


def _optimize(
    text: str, box_w: float, box_h: float, ctx: _Ctx, use_break: bool
) -> tuple[float, list[str]]:
    """Uttömmande sökning efter bästa radindelning.

    Provar alla kombinationer av delningspunkter (mellanslag och, om
    use_break=True, _BREAK-markörer) och väljer den som ger störst fontstorlek.
    Returnerar råa rader (med _BREAK och _HYPH_END kvar); anroparen
    ansvarar för att kalla _finalize_lines().
    """
    splits: list[tuple[int, str]] = []
    for i, c in enumerate(text):
        if c == " ":
            splits.append((i, "space"))
        elif c == _BREAK and use_break:
            splits.append((i, "break"))

    best_size = _fit_font([text], box_w, box_h, ctx)
    best_lines: list[str] = [text]

    for num_splits in range(1, min(len(splits), 5) + 1):
        for combo in itertools.combinations(range(len(splits)), num_splits):
            lines = _apply_splits(text, splits, combo)
            if lines is None:
                continue
            size = _fit_font(lines, box_w, box_h, ctx)
            if size > best_size + 0.01:
                best_size = size
                best_lines = lines

    return best_size, best_lines


def _finalize_lines(raw: list[str]) -> list[str]:
    """Konverterar råa optimizer-rader till visningstext.

    Tar bort _BREAK-markörer. Rader med avslutande _HYPH_END (stavelsbrott)
    ersätts med bindestreck; övriga _HYPH_END (borde inte förekomma) tas bort.
    """
    result = []
    for line in raw:
        clean = line.replace(_BREAK, "")
        if clean.endswith(_HYPH_END):
            result.append(clean[:-1] + "-")
        else:
            result.append(clean.replace(_HYPH_END, ""))
    return result


# Minsta förhållande ord-font/stavelse-font för att föredra ordsplitsar.
# 0.95 = godkänn ord-layout (inga bindestreck) om den ger minst 95% av stavelse-layoutens storlek.
_WORD_PREF = 0.95


def _add_hyphen_breaks(text: str) -> str:
    """Infogar _BREAK vid stavelsegränser för långa ord som saknar XML-brytningstips."""
    if _HYPHEN_DICT is None:
        return text
    out: list[str] = []
    word: list[str] = []
    for ch in text:
        if ch in (" ", _BREAK):
            if word:
                w = "".join(word)
                if len(w) >= _HYPHEN_MIN_LEN:
                    out.append(_HYPHEN_DICT.inserted(w.lower(), hyphen=_BREAK).upper())
                else:
                    out.append(w)
                word = []
            out.append(ch)
        else:
            word.append(ch)
    if word:
        w = "".join(word)
        if len(w) >= _HYPHEN_MIN_LEN:
            out.append(_HYPHEN_DICT.inserted(w.lower(), hyphen=_BREAK).upper())
        else:
            out.append(w)
    return "".join(out)


def _fit_text(
    text: str, box_w: float, box_h: float, ctx: _Ctx
) -> tuple[float, list[str]]:
    """Optimerar radindelning för maximal fontstorlek.

    Försöker två strategier och väljer den som ger störst font — med ett
    undantag: om ord-nivå-strategin (enbart mellanslag) ger minst _WORD_PREF
    av stavelse-strategins storlek väljs den ändå, eftersom rena ord-rader
    är mer lättlästa än stavelsefragment.
    """
    pieces = [p for p in text.split("\\") if p.strip()]
    if not pieces:
        return MIN_FONT, []

    # Strategi A: rekonstruera hela texten (utan separator), bryt enbart vid mellanslag.
    word_text = "".join(pieces)
    size_a, raw_a = _optimize(word_text, box_w, box_h, ctx, use_break=False)
    lines_a = _finalize_lines(raw_a)

    # Strategi B: _BREAK vid XML-gränser + pyphen-avstavning för långa ord utan tips.
    syllable_text = _add_hyphen_breaks(_BREAK.join(pieces))
    size_b, raw_b = _optimize(syllable_text, box_w, box_h, ctx, use_break=True)
    lines_b = _finalize_lines(raw_b)

    b_has_fragments = any(l.endswith("-") for l in lines_b)
    if b_has_fragments:
        # Enradstext som ger tillräcklig font avstavas inte (t.ex. "PENGEN").
        # Lång enradstext med liten font tillåts brytas (t.ex. "DRUVSOCKER").
        # Annars: acceptera bara om B är klart bättre.
        one_line_ok = len(lines_a) == 1 and size_a >= ctx.max_font * 0.50
        if one_line_ok or size_a >= size_b * _WORD_PREF:
            return size_a, lines_a
        return size_b, lines_b
    else:
        # B har inga stavelsefragment → ta det som ger störst font
        return (size_a, lines_a) if size_a >= size_b else (size_b, lines_b)


def _quiz_number(clues: list[ET.Element]) -> int | None:
    """Returnerar quiz-numret om cellen är en Quiz_RedCircle-referens, annars None."""
    for cl in clues:
        t = cl.text or ""
        if t.startswith("Quiz_RedCircle_") and t.endswith(".ai"):
            try:
                return int(t[len("Quiz_RedCircle_"):-3])
            except ValueError:
                pass
    return None


# ---------------------------------------------------------------------------
# SVG builder


def _build_svg(
    root: ET.Element,
    ctx: _Ctx,
    debug: bool = False,
    image_bytes: bytes | None = None,
    date_str: str | None = None,
    bare: bool = False,
) -> str:
    cell = ctx.cell
    cols = int(root.get("width", 0))
    rows = int(root.get("height", 0))

    title_text = (root.findtext("title") or "").strip()
    if date_str:
        title_text = f"{title_text} - {date_str}" if title_text else date_str
    byline_text = (root.findtext("byline") or "").strip()

    if bare:
        header_h = 0
        pad = 0
    else:
        header_h = TITLE_FONT_PX + 4 + ((BYLINE_FONT_PX + 4) if byline_text else 0) + 6
        pad = PADDING

    total_w = cols * cell + 2 * pad
    total_h = header_h + rows * cell + 2 * pad

    def px(x: int) -> float:
        return pad + x * cell

    def py(y: int) -> float:
        return pad + header_h + y * cell

    cells = {
        (int(c.get("x")), int(c.get("y"))): c
        for c in (root.find("grid/cells") or [])
    }

    # Svarsrutor för quiz-ledtrådar (definieras i <sentences>, inte i <grid>)
    sentence_cells: set[tuple[int, int]] = set()
    for sent in (root.find("sentences") or []):
        for word in sent.findall("word"):
            for sc in word.findall("cell"):
                sentence_cells.add((int(sc.get("x")), int(sc.get("y"))))

    # Samla cellgränser där bindestreck ska ritas (från puzzleword-element)
    hyphen_borders: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for word in root.iter("word"):
        pw = word.findtext("puzzleword") or ""
        if "-" not in pw:
            continue
        wc = [(int(c.get("x")), int(c.get("y"))) for c in word.findall("cells/cell")]
        letter_idx = 0
        for ch in pw:
            if ch == "-":
                hyphen_borders.add((wc[letter_idx - 1], wc[letter_idx]))
            else:
                letter_idx += 1

    # Beräkna bildarea: osynliga cellers bounding box
    invis = [(x, y) for (x, y), c in cells.items() if c.get("visible") == "0"]
    img_clip: tuple[float, float, float, float] | None = None
    if image_bytes and invis and root.find("puzzleimage") is not None:
        ix0 = min(x for x, y in invis)
        iy0 = min(y for x, y in invis)
        ix1 = max(x for x, y in invis) + 1
        iy1 = max(y for x, y in invis) + 1
        img_clip = (px(ix0), py(iy0), (ix1 - ix0) * cell, (iy1 - iy0) * cell)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{total_w}" height="{total_h}" '
        f'viewBox="0 0 {total_w} {total_h}">'
    )
    parts.append(f'<rect width="{total_w}" height="{total_h}" fill="white"/>')

    if img_clip is not None:
        clip_x, clip_y, clip_w, clip_h = img_clip
        b64 = base64.b64encode(image_bytes).decode()  # type: ignore[arg-type]
        parts.append(
            f'<defs><clipPath id="imgclip">'
            f'<rect x="{clip_x:.2f}" y="{clip_y:.2f}" '
            f'width="{clip_w:.2f}" height="{clip_h:.2f}"/>'
            f'</clipPath></defs>'
        )
        parts.append(
            f'<image x="{px(0):.2f}" y="{py(0):.2f}" '
            f'width="{cols * cell:.2f}" height="{rows * cell:.2f}" '
            f'href="data:image/png;base64,{b64}" '
            f'preserveAspectRatio="none" clip-path="url(#imgclip)"/>'
        )

    if not bare and title_text:
        title_y = pad + TITLE_FONT_PX + 2
        parts.append(
            f'<text x="{pad}" y="{title_y}" '
            f'font-family="sans-serif" font-size="{TITLE_FONT_PX}" '
            f'font-weight="bold">{escape(title_text)}</text>'
        )
        if byline_text:
            byline_y = title_y + BYLINE_FONT_PX + 4
            parts.append(
                f'<text x="{pad}" y="{byline_y}" '
                f'font-family="sans-serif" font-size="{BYLINE_FONT_PX}" '
                f'fill="#555">{escape(byline_text)}</text>'
            )

    for y in range(rows):
        for x in range(cols):
            c = cells.get((x, y))
            is_sentence_cell = (x, y) in sentence_cells
            if c is None and not is_sentence_cell:
                continue
            if c is not None and c.get("visible") == "0":
                continue

            cx = px(x)
            cy = py(y)
            fillable = c is not None and c.get("fillable") == "1"
            iscluecell = c is not None and c.get("iscluecell") == "1"
            clues = c.findall("clue") if c is not None else []
            quiz_num = _quiz_number(clues)
            is_legacy_quiz = (
                c is not None and not fillable and not iscluecell
                and c.get("arrownumber") is not None
            )

            if is_sentence_cell:
                parts.append(
                    f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" '
                    f'fill="{SENTENCE_BG}" stroke="black" stroke-width="{STROKE}"/>'
                )
            elif fillable:
                parts.append(
                    f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" '
                    f'fill="white" stroke="black" stroke-width="{STROKE}"/>'
                )
            elif quiz_num is not None:
                cx_c = cx + cell / 2
                cy_c = cy + cell / 2
                r_circ = cell * 0.30
                fs = cell * 0.22
                parts.append(
                    f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" '
                    f'fill="{SENTENCE_BG}" stroke="black" stroke-width="{STROKE}"/>'
                )
                parts.append(
                    f'<circle cx="{cx_c:.2f}" cy="{cy_c:.2f}" r="{r_circ:.2f}" '
                    f'fill="#cc2200" stroke="none"/>'
                )
                parts.append(
                    f'<text x="{cx_c:.2f}" y="{cy_c + fs * 0.38:.2f}" '
                    f'font-family="sans-serif" font-size="{fs:.1f}" font-weight="bold" '
                    f'fill="white" text-anchor="middle">{quiz_num}</text>'
                )
            elif is_legacy_quiz:
                parts.append(
                    f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" '
                    f'fill="{QUIZ_BG}" stroke="black" stroke-width="{STROKE}"/>'
                )
                r = cell * 0.25
                parts.append(
                    f'<circle cx="{cx + cell / 2:.2f}" cy="{cy + cell / 2:.2f}" '
                    f'r="{r:.2f}" fill="none" stroke="#888" stroke-width="1.5"/>'
                )
            elif iscluecell:
                parts.extend(_render_clue_cell(cx, cy, clues, cell, ctx))
            else:
                parts.append(
                    f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" '
                    f'fill="#333" stroke="black" stroke-width="{STROKE}"/>'
                )

            if debug:
                parts.append(
                    f'<text x="{cx + cell - 1}" y="{cy + 5}" '
                    f'font-family="sans-serif" font-size="4" fill="#aaa" '
                    f'text-anchor="end">{x},{y}</text>'
                )

    # Andra passet: pilar i angränsande svarsceller
    for y in range(rows):
        for x in range(cols):
            c = cells.get((x, y))
            if c is None or c.get("iscluecell") != "1":
                continue
            for clue_elem in c.findall("clue"):
                arrow_name = (clue_elem.get("arrow") or "none").lower().strip()
                _, dirs = ARROW_DEFS.get(arrow_name, ("full", []))
                if not dirs:
                    continue
                ddx, ddy = _DIR_DELTA.get(dirs[0], (0, 0))
                adj_x, adj_y = x + ddx, y + ddy
                if not (0 <= adj_x < cols and 0 <= adj_y < rows):
                    continue
                parts.extend(_draw_arrow_corner(px(adj_x), py(adj_y), cell, dirs))

    # Tredje passet: bindestreck på cellgränser
    half = cell * 0.22
    for (x1, y1), (x2, y2) in hyphen_borders:
        if x1 == x2:
            # Lodrätt ord: vertikalt streck som korsar den horisontella cellgränsen
            bx = px(x1) + cell / 2
            by_ = py(y2)
            parts.append(
                f'<line x1="{bx:.2f}" y1="{by_ - half:.2f}" '
                f'x2="{bx:.2f}" y2="{by_ + half:.2f}" '
                f'stroke="black" stroke-width="3.0"/>'
            )
        else:
            # Vågrätt ord: horisontellt streck som korsar den vertikala cellgränsen
            bx = px(x2)
            by_ = py(y1) + cell / 2
            parts.append(
                f'<line x1="{bx - half:.2f}" y1="{by_:.2f}" '
                f'x2="{bx + half:.2f}" y2="{by_:.2f}" '
                f'stroke="black" stroke-width="3.0"/>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def _best_split(text0: str, text1: str, cell: int, ctx: _Ctx) -> float:
    """Hittar optimal höjdandel (0-1) för övre ledtråden i en delad cell.

    Provar ett antal kandidat-delningar och väljer den som maximerar
    min(font_övre, font_nedre).
    """
    text_w = float(cell) - ctx.pad_x * 2
    best_r, best_score = 0.5, -1.0
    for r in (0.20, 0.25, 0.30, 0.33, 0.40, 0.45, 0.50, 0.55, 0.60, 0.67, 0.70, 0.75, 0.80):
        h0 = cell * r - ctx.pad_y * 2
        h1 = cell * (1 - r) - ctx.pad_y * 2
        if h0 < MIN_FONT or h1 < MIN_FONT:
            continue
        f0, _ = _fit_text(text0, text_w, h0, ctx) if text0 else (ctx.max_font, [])
        f1, _ = _fit_text(text1, text_w, h1, ctx) if text1 else (ctx.max_font, [])
        score = min(f0, f1)
        if score > best_score:
            best_score = score
            best_r = r
    return best_r


def _render_clue_cell(
    cx: float, cy: float, clues: list[ET.Element], cell: int, ctx: _Ctx
) -> list[str]:
    parts: list[str] = []
    if len(clues) == 2:
        text0 = (clues[0].text or "").strip().upper()
        text1 = (clues[1].text or "").strip().upper()
        r = _best_split(text0, text1, cell, ctx)
        h0 = cell * r
        h1 = cell - h0
        parts.extend(_clue_area(cx, cy, cell, h0, clues[0], ctx))
        parts.extend(_clue_area(cx, cy + h0, cell, h1, clues[1], ctx))
        mid = cy + h0
        parts.append(
            f'<line x1="{cx}" y1="{mid}" x2="{cx + cell}" y2="{mid}" '
            f'stroke="black" stroke-width="{STROKE}"/>'
        )
    else:
        parts.extend(_clue_area(cx, cy, cell, float(cell), clues[0] if clues else None, ctx))
    return parts


def _clue_area(
    cx: float, cy: float,
    cell: int, ch: float,
    clue: ET.Element | None,
    ctx: _Ctx,
) -> list[str]:
    parts: list[str] = []
    parts.append(
        f'<rect x="{cx}" y="{cy}" width="{cell}" height="{ch:.2f}" '
        f'fill="{CLUE_BG}" stroke="black" stroke-width="{STROKE}"/>'
    )
    if clue is None:
        return parts

    raw_text = (clue.text or "").strip().upper()

    text_w = float(cell) - ctx.pad_x * 2
    text_h = ch - ctx.pad_y * 2

    if raw_text:
        font_size, lines = _fit_text(raw_text, text_w, text_h, ctx)
        line_h = font_size * 1.15
        total_text_h = len(lines) * line_h
        start_y = cy + ctx.pad_y + (text_h - total_text_h) / 2 + font_size
        center_x = cx + cell / 2
        for i, line in enumerate(lines):
            parts.append(
                f'<text x="{center_x:.2f}" y="{start_y + i * line_h:.2f}" '
                f'font-family="sans-serif" font-size="{font_size:.1f}" '
                f'text-anchor="middle">{escape(line)}</text>'
            )

    return parts


_DIR_DELTA: dict[str, tuple[int, int]] = {
    "down": (0, 1), "up": (0, -1),
    "right": (1, 0), "left": (-1, 0),
    "diag_se": (1, 1), "diag_ne": (1, -1),
}


def _draw_arrow_corner(adj_cx: float, adj_cy: float, cell: int, dirs: list[str]) -> list[str]:
    """Liten L-pil i övre vänstra hörnet av den angränsande svarscellen."""
    if not dirs:
        return []
    parts: list[str] = []
    d_set = set(dirs)
    arm = cell * 0.17
    m = 3.0
    sw = 1.2
    s = arm * 0.65

    ax = adj_cx + m
    ay = adj_cy + m

    if "down" in d_set and "right" in d_set:
        if dirs[0] == "down":
            # Första arm ↓: börjar arm/2 ovanför cellgränsen (i ledtrådsrutan)
            lx = adj_cx + m
            sy, by_ = adj_cy - arm / 2, adj_cy + arm / 2
            tx = lx + arm
            parts.append(
                f'<path d="M {lx:.2f},{sy:.2f} L {lx:.2f},{by_:.2f} L {tx - s:.2f},{by_:.2f}" '
                f'fill="none" stroke="black" stroke-width="{sw}" '
                f'stroke-linejoin="round" stroke-linecap="round"/>'
            )
            parts.append(
                f'<polygon points="{tx:.2f},{by_:.2f} '
                f'{tx - s:.2f},{by_ - s/2:.2f} '
                f'{tx - s:.2f},{by_ + s/2:.2f}" fill="black"/>'
            )
        else:
            # Första arm →: börjar arm/2 till vänster om cellgränsen (i ledtrådsrutan)
            ly = adj_cy + m
            sx, bx = adj_cx - arm / 2, adj_cx + arm / 2
            ey = ly + arm
            parts.append(
                f'<path d="M {sx:.2f},{ly:.2f} L {bx:.2f},{ly:.2f} L {bx:.2f},{ey - s:.2f}" '
                f'fill="none" stroke="black" stroke-width="{sw}" '
                f'stroke-linejoin="round" stroke-linecap="round"/>'
            )
            parts.append(
                f'<polygon points="{bx:.2f},{ey:.2f} '
                f'{bx - s/2:.2f},{ey - s:.2f} '
                f'{bx + s/2:.2f},{ey - s:.2f}" fill="black"/>'
            )

    elif "up" in d_set and "right" in d_set:
        # Första arm ↑: angränsande cell ovanför, börjar arm/2 nedanför cellgränsen
        lx = adj_cx + m
        sy, by_ = adj_cy + cell + arm / 2, adj_cy + cell - arm / 2
        tx = lx + arm
        parts.append(
            f'<path d="M {lx:.2f},{sy:.2f} L {lx:.2f},{by_:.2f} L {tx - s:.2f},{by_:.2f}" '
            f'fill="none" stroke="black" stroke-width="{sw}" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        parts.append(
            f'<polygon points="{tx:.2f},{by_:.2f} '
            f'{tx - s:.2f},{by_ - s/2:.2f} '
            f'{tx - s:.2f},{by_ + s/2:.2f}" fill="black"/>'
        )

    elif "diag_se" in d_set:
        # Diagonalarm ↘: halvvägs in i ledtrådsrutan, böjpunkt vid cellgränsen
        word_dir = dirs[1] if len(dirs) > 1 else None
        sx, sy = adj_cx - arm / 2, adj_cy - arm / 2   # start (i ledtrådsrutan)
        bx, by_ = adj_cx + arm / 2, adj_cy + arm / 2  # böjpunkt (i svarscellen)
        if word_dir == "right":
            tx = bx + arm
            parts.append(
                f'<path d="M {sx:.2f},{sy:.2f} L {bx:.2f},{by_:.2f} L {tx - s:.2f},{by_:.2f}" '
                f'fill="none" stroke="black" stroke-width="{sw}" '
                f'stroke-linejoin="round" stroke-linecap="round"/>'
            )
            parts.append(
                f'<polygon points="{tx:.2f},{by_:.2f} '
                f'{tx - s:.2f},{by_ - s/2:.2f} '
                f'{tx - s:.2f},{by_ + s/2:.2f}" fill="black"/>'
            )
        elif word_dir == "down":
            ty = by_ + arm
            parts.append(
                f'<path d="M {sx:.2f},{sy:.2f} L {bx:.2f},{by_:.2f} L {bx:.2f},{ty - s:.2f}" '
                f'fill="none" stroke="black" stroke-width="{sw}" '
                f'stroke-linejoin="round" stroke-linecap="round"/>'
            )
            parts.append(
                f'<polygon points="{bx:.2f},{ty:.2f} '
                f'{bx - s/2:.2f},{ty - s:.2f} '
                f'{bx + s/2:.2f},{ty - s:.2f}" fill="black"/>'
            )

    elif "diag_ne" in d_set:
        # Diagonalarm ↗: start i ledtrådsrutan (nedre-vänster), böjpunkt i svarscellens nedre-vänstra hörn
        word_dir = dirs[1] if len(dirs) > 1 else None
        sx, sy = adj_cx - arm / 2, adj_cy + cell + arm / 2   # start (i ledtrådsrutan)
        bx, by_ = adj_cx + arm / 2, adj_cy + cell - arm / 2  # böjpunkt (i svarscellen)
        if word_dir == "right":
            tx = bx + arm
            parts.append(
                f'<path d="M {sx:.2f},{sy:.2f} L {bx:.2f},{by_:.2f} L {tx - s:.2f},{by_:.2f}" '
                f'fill="none" stroke="black" stroke-width="{sw}" '
                f'stroke-linejoin="round" stroke-linecap="round"/>'
            )
            parts.append(
                f'<polygon points="{tx:.2f},{by_:.2f} '
                f'{tx - s:.2f},{by_ - s/2:.2f} '
                f'{tx - s:.2f},{by_ + s/2:.2f}" fill="black"/>'
            )

    return parts
