"""Rendera Keesing Crossword General från XML till SVG/PDF.

Stöder: variation "Crossword General" (och andra "Crossword*"-variationer)

Producerar innehållsstorlad SVG/PDF - ingen A4-tvingning. Cellstorlek
kalibreras mot A4-bredd (max ~58px) för rimlig läsbarhet på reMarkable.

Public API:
    supports_crossword_xml(xml_bytes: bytes) -> bool
    render_crossword_svg(xml_bytes: bytes, date_str: str | None = None) -> str
    render_crossword_pdf(xml_bytes: bytes, output: Path, date_str: str | None = None) -> Path
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

PADDING = 20
STROKE_INNER = 0.5
STROKE_OUTER = 1.5
TITLE_FONT_PX = 11
NUM_FONT_PX = 7
CLUE_HEADER_FONT = 10
CLUE_FONT_MAX = 9.0
CLUE_FONT_MIN = 6.5
CLUE_LINE_SPACING = 1.4
COL_GAP = 16

# Cellstorlek kalibreras mot A4-bredd (794 - 2*20 = 754px)
_TARGET_GRID_PX = 754


# ---------------------------------------------------------------------------
# Public API


def supports_crossword_xml(xml_bytes: bytes) -> bool:
    """Returnerar True om variationen är ett Crossword-pussel."""
    try:
        root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
        return root.get("variation", "").startswith("Crossword")
    except ET.ParseError:
        return False


def render_crossword_svg(xml_bytes: bytes, date_str: str | None = None) -> str:
    """Renderar till innehållsstorlad SVG-sträng."""
    root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
    if not supports_crossword_xml(xml_bytes):
        raise ValueError(
            f"Variation '{root.get('variation')}' stöds inte av render_crossword"
        )
    return _build_svg(root, date_str=date_str)


def render_crossword_pdf(
    xml_bytes: bytes,
    output: Path | str,
    date_str: str | None = None,
) -> Path:
    """Kräver cairosvg."""
    import cairosvg  # type: ignore

    out_path = Path(output)
    svg = render_crossword_svg(xml_bytes, date_str=date_str)
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=str(out_path))
    return out_path


# ---------------------------------------------------------------------------
# Text-utilities


def _cw(c: str) -> float:
    """Proportionell teckenbredd i em-enheter."""
    if c in "IiljtfJ1 .,!:;'\"":
        return 0.35
    if c in "mwMW":
        return 0.95
    return 0.62


def _tw(text: str) -> float:
    return sum(_cw(c) for c in text)


def _wrap(text: str, max_em: float) -> list[str]:
    """Bryt text till rader som ryms inom max_em em."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _tw(candidate) <= max_em:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# Parsing


def _cell_size(cols: int) -> int:
    return max(34, min(58, _TARGET_GRID_PX // cols))


def _parse_groups(root: ET.Element) -> tuple[str, list[tuple[int, str]], str, list[tuple[int, str]]]:
    """Returnerar (h_header, h_clues, v_header, v_clues)."""
    h_header = "Vågrätt"
    v_header = "Lodrätt"
    horizontal: list[tuple[int, str]] = []
    vertical: list[tuple[int, str]] = []
    for wg in root.findall("wordgroups/wordgroup"):
        kind = wg.get("kind", "")
        header = (wg.findtext("header") or "").strip()
        if kind == "horizontal":
            h_header = header or h_header
            for word in wg.findall("words/word"):
                horizontal.append((int(word.get("number", 0)), (word.findtext("clue") or "").strip()))
        elif kind == "vertical":
            v_header = header or v_header
            for word in wg.findall("words/word"):
                vertical.append((int(word.get("number", 0)), (word.findtext("clue") or "").strip()))
    horizontal.sort()
    vertical.sort()
    return h_header, horizontal, v_header, vertical


def _word_starts(root: ET.Element) -> dict[tuple[int, int], int]:
    """Returnerar {(x,y): nummer} för varje ordstart (deduplicerat per cell)."""
    starts: dict[tuple[int, int], int] = {}
    for wg in root.findall("wordgroups/wordgroup"):
        for word in wg.findall("words/word"):
            num = int(word.get("number", 0))
            first = word.find("cells/cell")
            if first is not None:
                xy = (int(first.get("x")), int(first.get("y")))
                starts.setdefault(xy, num)
    return starts


# ---------------------------------------------------------------------------
# SVG builder


def _build_svg(root: ET.Element, date_str: str | None = None) -> str:
    cols = int(root.get("width", 10))
    rows = int(root.get("height", 10))
    cell = _cell_size(cols)

    cells = {
        (int(c.get("x")), int(c.get("y"))): c
        for c in (root.find("grid/cells") or [])
    }
    starts = _word_starts(root)
    h_header, h_clues, v_header, v_clues = _parse_groups(root)

    header_text = date_str or ""
    header_h = (TITLE_FONT_PX + 8) if header_text else 0

    grid_w = cols * cell
    grid_h = rows * cell
    total_w = grid_w + 2 * PADDING
    grid_x = PADDING
    grid_y = PADDING + header_h

    # Kluelista i två kolumner under gridet
    col_w = (total_w - 2 * PADDING - COL_GAP) / 2

    font_size = CLUE_FONT_MAX
    clue_h = 0.0
    while True:
        line_h = font_size * CLUE_LINE_SPACING
        max_em = col_w / font_size

        def _ch(clues: list[tuple[int, str]]) -> float:
            h = CLUE_HEADER_FONT + 6.0
            for num, clue in clues:
                h += len(_wrap(f"{num}. {clue}", max_em)) * line_h + 2
            return h

        clue_h = max(_ch(h_clues), _ch(v_clues)) + PADDING
        if font_size <= CLUE_FONT_MIN:
            break
        font_size = round(font_size - 0.5, 1)
        # Kluelist skalas ner bara om den är osannolikt lång (>3x grid-höjd)
        if clue_h <= grid_h * 3:
            break

    max_em = col_w / font_size
    total_h = grid_y + grid_h + PADDING + clue_h

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{total_w}" height="{int(total_h)}" '
        f'viewBox="0 0 {total_w} {int(total_h)}">',
        f'<rect width="{total_w}" height="{int(total_h)}" fill="white"/>',
    ]

    if header_text:
        parts.append(
            f'<text x="{total_w / 2:.1f}" y="{PADDING + TITLE_FONT_PX:.1f}" '
            f'text-anchor="middle" font-family="sans-serif" '
            f'font-size="{TITLE_FONT_PX}" font-weight="bold">'
            f'{escape(header_text)}</text>'
        )

    # Grid: bakgrund
    parts.append(
        f'<rect x="{grid_x}" y="{grid_y}" '
        f'width="{grid_w}" height="{grid_h}" fill="white" stroke="none"/>'
    )

    # Inre gridlinjer (ritade innan celler så svarta celler täcker dem)
    for i in range(1, cols):
        lx = grid_x + i * cell
        parts.append(
            f'<line x1="{lx}" y1="{grid_y}" x2="{lx}" y2="{grid_y + grid_h}" '
            f'stroke="#999" stroke-width="{STROKE_INNER}"/>'
        )
    for i in range(1, rows):
        ly = grid_y + i * cell
        parts.append(
            f'<line x1="{grid_x}" y1="{ly}" x2="{grid_x + grid_w}" y2="{ly}" '
            f'stroke="#999" stroke-width="{STROKE_INNER}"/>'
        )

    # Celler
    for (cx, cy), c in cells.items():
        x = grid_x + cx * cell
        y = grid_y + cy * cell
        if c.get("fillable") == "0":
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'fill="black" stroke="none"/>'
            )
        elif c.get("giveaway") == "1":
            content = c.get("content", "")
            if content:
                fs = cell * 0.45
                parts.append(
                    f'<text x="{x + cell / 2:.1f}" y="{y + cell * 0.68:.1f}" '
                    f'text-anchor="middle" font-family="sans-serif" '
                    f'font-size="{fs:.1f}" font-weight="bold">'
                    f'{escape(content)}</text>'
                )

    # Ordnummer i cellhörn
    for (cx, cy), num in starts.items():
        parts.append(
            f'<text x="{grid_x + cx * cell + 1.5:.1f}" '
            f'y="{grid_y + cy * cell + NUM_FONT_PX + 0.5:.1f}" '
            f'font-family="sans-serif" font-size="{NUM_FONT_PX}">'
            f'{num}</text>'
        )

    # Yttre kant
    parts.append(
        f'<rect x="{grid_x}" y="{grid_y}" '
        f'width="{grid_w}" height="{grid_h}" '
        f'fill="none" stroke="black" stroke-width="{STROKE_OUTER}"/>'
    )

    # Kluelista
    clue_y = float(grid_y + grid_h + PADDING)
    line_h = font_size * CLUE_LINE_SPACING

    def _render_col(clues: list[tuple[int, str]], x0: float, label: str) -> None:
        y = clue_y
        parts.append(
            f'<text x="{x0:.1f}" y="{y + CLUE_HEADER_FONT:.1f}" '
            f'font-family="sans-serif" font-size="{CLUE_HEADER_FONT}" '
            f'font-weight="bold">{escape(label)}</text>'
        )
        y += CLUE_HEADER_FONT + 6
        for num, clue in clues:
            for line in _wrap(f"{num}. {clue}", max_em):
                parts.append(
                    f'<text x="{x0:.1f}" y="{y + font_size:.1f}" '
                    f'font-family="sans-serif" font-size="{font_size}">'
                    f'{escape(line)}</text>'
                )
                y += line_h
            y += 2

    _render_col(h_clues, float(PADDING), h_header)
    _render_col(v_clues, PADDING + col_w + COL_GAP, v_header)

    parts.append("</svg>")
    return "\n".join(parts)
