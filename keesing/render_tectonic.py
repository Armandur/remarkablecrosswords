"""Rendera Keesing Tectonic från XML till SVG/PDF.

Stöder: variation "Tectonic"

Innehållsstorlad SVG/PDF. Regionfärgad bakgrund, tjocka kanter mellan
regioner, tunna inre kanter. Förifyllda siffror (giveaway=1) i fetstil.

Public API:
    supports_tectonic_xml(xml_bytes: bytes) -> bool
    render_tectonic_svg(xml_bytes: bytes, date_str: str | None = None) -> str
    render_tectonic_pdf(xml_bytes: bytes, output: Path, date_str: str | None = None) -> Path
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

PADDING = 20
STROKE_INNER = 0.5   # kant inom region
STROKE_REGION = 2.5  # kant mellan regioner
STROKE_OUTER = 2.5   # yttre kant
TITLE_FONT = 12
CELL_MAX = 70
CELL_MIN = 34
_TARGET_GRID_PX = 754  # A4-bredd minus padding


# ---------------------------------------------------------------------------
# Public API


def supports_tectonic_xml(xml_bytes: bytes) -> bool:
    """Returnerar True om variationen är ett Tectonic-pussel."""
    try:
        root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
        return root.get("variation", "").startswith("Tectonic")
    except ET.ParseError:
        return False


def render_tectonic_svg(xml_bytes: bytes, date_str: str | None = None) -> str:
    """Renderar till innehållsstorlad SVG-sträng."""
    root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
    if not supports_tectonic_xml(xml_bytes):
        raise ValueError(
            f"Variation '{root.get('variation')}' stöds inte av render_tectonic"
        )
    return _build_svg(root, date_str=date_str)


def render_tectonic_pdf(
    xml_bytes: bytes,
    output: Path | str,
    date_str: str | None = None,
) -> Path:
    """Kräver cairosvg."""
    import cairosvg  # type: ignore

    out_path = Path(output)
    svg = render_tectonic_svg(xml_bytes, date_str=date_str)
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=str(out_path))
    return out_path


# ---------------------------------------------------------------------------
# Helpers


_WHITE_BLEND = 0.55  # blandningsfaktor mot vitt (0=original, 1=helt vitt)

def _argb_to_hex(argb: str) -> str:
    """Konverterar '0xffRRGGBB' → '#RRGGBB', blekad mot vitt för läsbarhet."""
    try:
        val = int(argb, 16)
        r = (val >> 16) & 0xFF
        g = (val >> 8) & 0xFF
        b = val & 0xFF
        r = int(r + (255 - r) * _WHITE_BLEND)
        g = int(g + (255 - g) * _WHITE_BLEND)
        b = int(b + (255 - b) * _WHITE_BLEND)
        return f"#{r:02x}{g:02x}{b:02x}"
    except (ValueError, TypeError):
        return "#ececec"


def _cell_size(cols: int) -> int:
    return max(CELL_MIN, min(CELL_MAX, _TARGET_GRID_PX // cols))


def _build_svg(root: ET.Element, date_str: str | None = None) -> str:
    cols = int(root.get("width", 9))
    rows = int(root.get("height", 9))
    cell = _cell_size(cols)

    # Färgkarta: color_id → hex
    color_map: dict[str, str] = {}
    for c in root.findall("grid/colors/color"):
        color_map[c.get("id", "")] = _argb_to_hex(c.get("ARGB", ""))

    # Celler: (x,y) → element
    cells = {
        (int(c.get("x")), int(c.get("y"))): c
        for c in (root.find("grid/cells") or [])
    }

    # Region-karta: (x,y) → (region_idx, color_hex)
    cell_region: dict[tuple[int, int], int] = {}
    cell_color: dict[tuple[int, int], str] = {}
    for idx, region in enumerate(root.findall("grid/regions/region")):
        color_id = region.get("colorid", "")
        hex_color = color_map.get(color_id, "#e0e0e0")
        for rc in region.findall("cells/cell"):
            xy = (int(rc.get("x")), int(rc.get("y")))
            cell_region[xy] = idx
            cell_color[xy] = hex_color

    # Vilka interna kanter är regionsgränser?
    # h_borders[(x,y)] = True om kanten UNDER cell (x,y) är regionsgräns
    # v_borders[(x,y)] = True om kanten TILL HÖGER om cell (x,y) är regionsgräns
    h_borders: set[tuple[int, int]] = set()
    v_borders: set[tuple[int, int]] = set()
    for x in range(cols):
        for y in range(rows):
            if y + 1 < rows:
                if cell_region.get((x, y), -1) != cell_region.get((x, y + 1), -2):
                    h_borders.add((x, y))
            if x + 1 < cols:
                if cell_region.get((x, y), -1) != cell_region.get((x + 1, y), -2):
                    v_borders.add((x, y))

    # Header
    header_text = date_str or ""
    header_h = (TITLE_FONT + 8) if header_text else 0

    grid_w = cols * cell
    grid_h = rows * cell
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

    if header_text:
        parts.append(
            f'<text x="{total_w / 2:.1f}" y="{PADDING + TITLE_FONT:.1f}" '
            f'text-anchor="middle" font-family="sans-serif" '
            f'font-size="{TITLE_FONT}" font-weight="bold">'
            f'{escape(header_text)}</text>'
        )

    # 1. Regionsfärgade cellbakgrunder
    for (cx, cy) in cells:
        x = grid_x + cx * cell
        y = grid_y + cy * cell
        bg = cell_color.get((cx, cy), "#ffffff")
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
            f'fill="{bg}" stroke="none"/>'
        )

    # 2. Tunna inre linjer (hela gridet)
    for i in range(1, cols):
        lx = grid_x + i * cell
        parts.append(
            f'<line x1="{lx}" y1="{grid_y}" x2="{lx}" y2="{grid_y + grid_h}" '
            f'stroke="#888" stroke-width="{STROKE_INNER}"/>'
        )
    for i in range(1, rows):
        ly = grid_y + i * cell
        parts.append(
            f'<line x1="{grid_x}" y1="{ly}" x2="{grid_x + grid_w}" y2="{ly}" '
            f'stroke="#888" stroke-width="{STROKE_INNER}"/>'
        )

    # 3. Tjocka regionsgränser
    for (cx, cy) in h_borders:
        ly = grid_y + (cy + 1) * cell
        x0 = grid_x + cx * cell
        parts.append(
            f'<line x1="{x0}" y1="{ly}" x2="{x0 + cell}" y2="{ly}" '
            f'stroke="black" stroke-width="{STROKE_REGION}"/>'
        )
    for (cx, cy) in v_borders:
        lx = grid_x + (cx + 1) * cell
        y0 = grid_y + cy * cell
        parts.append(
            f'<line x1="{lx}" y1="{y0}" x2="{lx}" y2="{y0 + cell}" '
            f'stroke="black" stroke-width="{STROKE_REGION}"/>'
        )

    # 4. Förifyllda siffror
    giveaway_font = int(cell * 0.5)
    for (cx, cy), c in cells.items():
        if c.get("giveaway") == "1":
            content = c.get("content", "")
            if content:
                tx = grid_x + cx * cell + cell / 2
                ty = grid_y + cy * cell + cell * 0.67
                parts.append(
                    f'<text x="{tx:.1f}" y="{ty:.1f}" '
                    f'text-anchor="middle" font-family="sans-serif" '
                    f'font-size="{giveaway_font}" font-weight="bold">'
                    f'{escape(content)}</text>'
                )

    # 5. Yttre kant
    parts.append(
        f'<rect x="{grid_x}" y="{grid_y}" '
        f'width="{grid_w}" height="{grid_h}" '
        f'fill="none" stroke="black" stroke-width="{STROKE_OUTER}"/>'
    )

    parts.append("</svg>")
    return "\n".join(parts)
