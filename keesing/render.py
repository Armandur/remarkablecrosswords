"""Rendera Keesing Arrowword DPG-korsord från XML till SVG/PDF.

Stöder: variation "Arrowword DPG"
Ej stödd: PuzzleConstruction Arrowword (saknar ledtrådstexter i XML)

Public API:
    render_svg(xml_bytes: bytes) -> str
    render_pdf(xml_bytes: bytes, output: Path) -> Path
    supports_xml(xml_bytes: bytes) -> bool
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

PADDING = 20
STROKE = 1.0
TITLE_FONT_PX = 14
BYLINE_FONT_PX = 10
CLUE_BG = "#c0c0c0"
QUIZ_BG = "#e8e8e8"

# Anpassa cellstorlek till A4 bredd (794px vid 96 DPI, ~210mm)
_TARGET_GRID_PX = 754  # 794 - 2*PADDING

CHAR_WIDTHS = {
    "M": 1.00, "W": 1.05, "m": 0.92, "w": 0.92,
    "I": 0.34, "i": 0.34, "l": 0.34, "j": 0.36, "t": 0.44, "f": 0.44,
    "J": 0.58, "L": 0.66, " ": 0.34, "-": 0.42, ".": 0.32, ",": 0.32,
    "!": 0.32, "?": 0.58,
    "Å": 0.85, "Ä": 0.85, "Ö": 0.85, "å": 0.72, "ä": 0.72, "ö": 0.72,
}
CHAR_WIDTH_DEFAULT = 0.70
FIT_SAFETY = 0.90
MIN_FONT = 3.0

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
        self.pad_x = max(2.0, cell * 0.07)
        self.pad_y = max(1.5, cell * 0.04)
        self.max_font = cell * 0.24
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


def render_svg(xml_bytes: bytes, debug: bool = False) -> str:
    root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
    if not supports_xml(xml_bytes):
        raise ValueError(
            f"Variation '{root.get('variation')}' stöds inte av render_keesing"
        )
    cols = int(root.get("width", 15))
    cell = max(36, min(54, _TARGET_GRID_PX // cols))
    ctx = _Ctx(cell)
    return _build_svg(root, ctx, debug=debug)


def render_pdf(xml_bytes: bytes, output: Path | str, debug: bool = False) -> Path:
    """Kräver cairosvg."""
    import cairosvg  # type: ignore

    out_path = Path(output)
    svg = render_svg(xml_bytes, debug=debug)
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
    by_w = (box_w - ctx.pad_x * 2) / widest * FIT_SAFETY
    by_h = (box_h - ctx.pad_y * 2) / (len(lines) * 1.15)
    return max(MIN_FONT, min(ctx.max_font, by_w, by_h))


def _fit_text(
    text: str, box_w: float, box_h: float, ctx: _Ctx
) -> tuple[float, list[str]]:
    """Exploderar '\\' till radbrytningar, optimerar sedan vid mellanslag."""
    lines = text.split("\\")
    while True:
        current = _fit_font(lines, box_w, box_h, ctx)
        best = current
        best_lines: list[str] | None = None
        for i, line in enumerate(lines):
            spaces = [j for j, c in enumerate(line) if c == " "]
            for s in spaces:
                trial = (
                    lines[:i]
                    + [line[:s].rstrip(), line[s + 1:].lstrip()]
                    + lines[i + 1:]
                )
                size = _fit_font(trial, box_w, box_h, ctx)
                if size > best + 0.01:
                    best = size
                    best_lines = trial
        if best_lines is None:
            return current, lines
        lines = best_lines


# ---------------------------------------------------------------------------
# SVG builder


def _build_svg(root: ET.Element, ctx: _Ctx, debug: bool = False) -> str:
    cell = ctx.cell
    cols = int(root.get("width", 0))
    rows = int(root.get("height", 0))

    title_text = (root.findtext("title") or "").strip()
    byline_text = (root.findtext("byline") or "").strip()

    header_h = TITLE_FONT_PX + 4 + ((BYLINE_FONT_PX + 4) if byline_text else 0) + 6
    total_w = cols * cell + 2 * PADDING
    total_h = header_h + rows * cell + 2 * PADDING

    def px(x: int) -> float:
        return PADDING + x * cell

    def py(y: int) -> float:
        return PADDING + header_h + y * cell

    cells = {
        (int(c.get("x")), int(c.get("y"))): c
        for c in (root.find("grid/cells") or [])
    }

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

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{total_w}" height="{total_h}" '
        f'viewBox="0 0 {total_w} {total_h}">'
    )
    parts.append(f'<rect width="{total_w}" height="{total_h}" fill="white"/>')

    title_y = PADDING + TITLE_FONT_PX + 2
    parts.append(
        f'<text x="{PADDING}" y="{title_y}" '
        f'font-family="sans-serif" font-size="{TITLE_FONT_PX}" '
        f'font-weight="bold">{escape(title_text)}</text>'
    )
    if byline_text:
        byline_y = title_y + BYLINE_FONT_PX + 4
        parts.append(
            f'<text x="{PADDING}" y="{byline_y}" '
            f'font-family="sans-serif" font-size="{BYLINE_FONT_PX}" '
            f'fill="#555">{escape(byline_text)}</text>'
        )

    for y in range(rows):
        for x in range(cols):
            c = cells.get((x, y))
            if c is None or c.get("visible") == "0":
                continue

            cx = px(x)
            cy = py(y)
            fillable = c.get("fillable") == "1"
            iscluecell = c.get("iscluecell") == "1"
            clues = c.findall("clue")
            is_quiz = (
                not fillable and not iscluecell and c.get("arrownumber") is not None
            )

            if fillable:
                parts.append(
                    f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" '
                    f'fill="white" stroke="black" stroke-width="{STROKE}"/>'
                )
            elif is_quiz:
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


def _render_clue_cell(
    cx: float, cy: float, clues: list[ET.Element], cell: int, ctx: _Ctx
) -> list[str]:
    parts: list[str] = []
    if len(clues) == 2:
        half = cell / 2
        parts.extend(_clue_area(cx, cy, cell, half, clues[0], ctx))
        parts.extend(_clue_area(cx, cy + half, cell, half, clues[1], ctx))
        mid = cy + half
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

    raw_text = (clue.text or "").strip()

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
                f'<path d="M {lx:.2f},{sy:.2f} L {lx:.2f},{by_:.2f} L {tx:.2f},{by_:.2f}" '
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
                f'<path d="M {sx:.2f},{ly:.2f} L {bx:.2f},{ly:.2f} L {bx:.2f},{ey:.2f}" '
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
            f'<path d="M {lx:.2f},{sy:.2f} L {lx:.2f},{by_:.2f} L {tx:.2f},{by_:.2f}" '
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
                f'<path d="M {sx:.2f},{sy:.2f} L {bx:.2f},{by_:.2f} L {tx:.2f},{by_:.2f}" '
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
                f'<path d="M {sx:.2f},{sy:.2f} L {bx:.2f},{by_:.2f} L {bx:.2f},{ty:.2f}" '
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
                f'<path d="M {sx:.2f},{sy:.2f} L {bx:.2f},{by_:.2f} L {tx:.2f},{by_:.2f}" '
                f'fill="none" stroke="black" stroke-width="{sw}" '
                f'stroke-linejoin="round" stroke-linecap="round"/>'
            )
            parts.append(
                f'<polygon points="{tx:.2f},{by_:.2f} '
                f'{tx - s:.2f},{by_ - s/2:.2f} '
                f'{tx - s:.2f},{by_ + s/2:.2f}" fill="black"/>'
            )

    return parts
