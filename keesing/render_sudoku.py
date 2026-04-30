"""Rendera Keesing Sudoku från XML till SVG/PDF.

Stöder: variation "Sudoku 9x9" (och andra "Sudoku*"-variationer)

Innehållsstorlad SVG/PDF. Tjocka kanter runt 3x3-boxar, tunna inre linjer.
Förifyllda siffror (giveaway=1) visas i fetstil.

Public API:
    supports_sudoku_xml(xml_bytes: bytes) -> bool
    render_sudoku_svg(xml_bytes: bytes, date_str: str | None = None) -> str
    render_sudoku_pdf(xml_bytes: bytes, output: Path, date_str: str | None = None) -> Path
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

PADDING = 20
CELL = 56              # px per cell (9x9 → 504px grid)
BOX = 3                # celler per 3x3-box
STROKE_THIN = 0.5      # inre linjer inom box
STROKE_BOX = 2.0       # kanter mellan boxar
STROKE_OUTER = 2.5     # yttre kant
TITLE_FONT = 12
DIFF_FONT = 10
GIVEAWAY_FONT = int(CELL * 0.55)


# ---------------------------------------------------------------------------
# Public API


def supports_sudoku_xml(xml_bytes: bytes) -> bool:
    """Returnerar True om variationen är ett Sudoku-pussel."""
    try:
        root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
        return root.get("variation", "").startswith("Sudoku")
    except ET.ParseError:
        return False


def render_sudoku_svg(xml_bytes: bytes, date_str: str | None = None) -> str:
    """Renderar till innehållsstorlad SVG-sträng."""
    root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
    if not supports_sudoku_xml(xml_bytes):
        raise ValueError(
            f"Variation '{root.get('variation')}' stöds inte av render_sudoku"
        )
    return _build_svg(root, date_str=date_str)


def render_sudoku_pdf(
    xml_bytes: bytes,
    output: Path | str,
    date_str: str | None = None,
) -> Path:
    """Kräver cairosvg."""
    import cairosvg  # type: ignore

    out_path = Path(output)
    svg = render_sudoku_svg(xml_bytes, date_str=date_str)
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=str(out_path))
    return out_path


# ---------------------------------------------------------------------------
# Helpers


def _difficulty_stars(difficulty: int) -> str:
    """Returnerar t.ex. '★★★☆☆☆☆' för difficulty=3 av 7."""
    d = max(1, min(7, difficulty))
    return "★" * d + "☆" * (7 - d)


def _build_svg(root: ET.Element, date_str: str | None = None) -> str:
    cols = int(root.get("width", 9))
    rows = int(root.get("height", 9))
    difficulty = int(root.get("difficulty", 1))

    cells = {
        (int(c.get("x")), int(c.get("y"))): c
        for c in (root.find("grid/cells") or [])
    }

    # Header: datum + svårighetsgrad
    header_parts: list[str] = []
    if date_str:
        header_parts.append(date_str)
    header_parts.append(_difficulty_stars(difficulty))
    header_text = "  ".join(header_parts)
    header_h = TITLE_FONT + DIFF_FONT + 10 if header_text else 0

    grid_w = cols * CELL
    grid_h = rows * CELL
    total_w = grid_w + 2 * PADDING
    total_h = PADDING + header_h + grid_h + PADDING

    grid_x = PADDING
    grid_y = PADDING + header_h

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{total_w}" height="{total_h}" '
        f'viewBox="0 0 {total_w} {total_h}">',
        f'<rect width="{total_w}" height="{total_h}" fill="white"/>',
    ]

    # Header
    if header_text:
        cx = total_w / 2
        parts.append(
            f'<text x="{cx:.1f}" y="{PADDING + TITLE_FONT:.1f}" '
            f'text-anchor="middle" font-family="sans-serif" '
            f'font-size="{TITLE_FONT}" font-weight="bold">'
            f'{escape(header_text)}</text>'
        )

    # Gridbakgrund (vit)
    parts.append(
        f'<rect x="{grid_x}" y="{grid_y}" '
        f'width="{grid_w}" height="{grid_h}" fill="white"/>'
    )

    # Tunna inre linjer (hela gridet)
    for i in range(1, cols):
        lx = grid_x + i * CELL
        parts.append(
            f'<line x1="{lx}" y1="{grid_y}" x2="{lx}" y2="{grid_y + grid_h}" '
            f'stroke="#bbb" stroke-width="{STROKE_THIN}"/>'
        )
    for i in range(1, rows):
        ly = grid_y + i * CELL
        parts.append(
            f'<line x1="{grid_x}" y1="{ly}" x2="{grid_x + grid_w}" y2="{ly}" '
            f'stroke="#bbb" stroke-width="{STROKE_THIN}"/>'
        )

    # Tjocka boxkanter (vid multipelr av BOX)
    for i in range(BOX, cols, BOX):
        lx = grid_x + i * CELL
        parts.append(
            f'<line x1="{lx}" y1="{grid_y}" x2="{lx}" y2="{grid_y + grid_h}" '
            f'stroke="black" stroke-width="{STROKE_BOX}"/>'
        )
    for i in range(BOX, rows, BOX):
        ly = grid_y + i * CELL
        parts.append(
            f'<line x1="{grid_x}" y1="{ly}" x2="{grid_x + grid_w}" y2="{ly}" '
            f'stroke="black" stroke-width="{STROKE_BOX}"/>'
        )

    # Siffror (giveaway=1 → fetstil svart, giveaway=0 → tom cell)
    for (cx, cy), c in cells.items():
        if c.get("giveaway") == "1":
            content = c.get("content", "")
            if content:
                tx = grid_x + cx * CELL + CELL / 2
                ty = grid_y + cy * CELL + CELL * 0.68
                parts.append(
                    f'<text x="{tx:.1f}" y="{ty:.1f}" '
                    f'text-anchor="middle" font-family="sans-serif" '
                    f'font-size="{GIVEAWAY_FONT}" font-weight="bold">'
                    f'{escape(content)}</text>'
                )

    # Yttre kant
    parts.append(
        f'<rect x="{grid_x}" y="{grid_y}" '
        f'width="{grid_w}" height="{grid_h}" '
        f'fill="none" stroke="black" stroke-width="{STROKE_OUTER}"/>'
    )

    parts.append("</svg>")
    return "\n".join(parts)
