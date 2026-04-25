"""Rendera korsord.io-data som SVG eller PDF.

Public API:
    render_svg(data: dict, debug: bool = False) -> str
    render_pdf(data: dict, output: Path, debug: bool = False) -> Path

Bakgrund och datamodell finns i `spec.md` i samma katalog.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Iterable

CELL = 36
PADDING = 20
STROKE = 1.0
TITLE_FONT_PX = 14
SOLUTION_INDEX_FONT = 8

SMS_BG = "#b8e6e6"      # ljust turkos — smsIndex-rutor (SMS-svar)
CAPTION_BG = "#fff4a0"  # ljust gul   — color:"caption" (lösningsmening)

DEBUG_COORD_FONT = 3.5
DEBUG_COORD_COLOR = "#999"

# Per-tecken-vikter för auto-skalning av ledtrådstexter (sans-serif vid
# font-size 1). Bättre än global ratio: rader med M/W skalas ner mer.
CHAR_WIDTHS = {
    "M": 1.00, "W": 1.05, "m": 0.92, "w": 0.92,
    "I": 0.34, "i": 0.34, "l": 0.34, "j": 0.36, "t": 0.44, "f": 0.44,
    "J": 0.58, "L": 0.66, " ": 0.34, "-": 0.42, ".": 0.32, ",": 0.32,
    "!": 0.32, "?": 0.58,
}
CHAR_WIDTH_DEFAULT = 0.70
TEXT_PADDING_X = 3      # horisontell padding i ledtrådsruta
TEXT_PADDING_Y = 1.5    # vertikal — låg så att split-leads (h=0.28) får plats
MIN_FONT = 4.0
MAX_FONT = 10
FIT_SAFETY = 0.92  # marginal mot fontvariationer i cairosvg


# ---------------------------------------------------------------------------
# Public API


def render_svg(data: dict, debug: bool = False) -> str:
    """Returnerar en SVG-sträng för korsordet.

    `data` är parsed `.crossword`-JSON. När `debug=True` ritas
    cell-koordinater (x,y) i grått i övre högra hörnet av varje
    bokstavs- och ledtrådsruta — användbart för felsökning.
    """
    return _build_svg(data, debug=debug)


def render_pdf(data: dict, output: Path | str, debug: bool = False) -> Path:
    """Rendera och skriv PDF till `output`. Kräver `cairosvg`."""
    import cairosvg  # type: ignore

    out_path = Path(output)
    svg = render_svg(data, debug=debug)
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=str(out_path))
    return out_path


# ---------------------------------------------------------------------------
# Text-fitting


def _text_width_units(text: str) -> float:
    return sum(CHAR_WIDTHS.get(c, CHAR_WIDTH_DEFAULT) for c in text)


def _fit_font_size(lines: list[str], box_w: float, box_h: float) -> float:
    if not lines:
        return MIN_FONT
    widest = max(_text_width_units(l) for l in lines) or 1
    by_w = (box_w - TEXT_PADDING_X * 2) / widest * FIT_SAFETY
    by_h = (box_h - TEXT_PADDING_Y * 2) / (len(lines) * 1.15)
    return max(MIN_FONT, min(MAX_FONT, by_w, by_h))


def _fit_text_to_box(text: str, box_w: float, box_h: float) -> tuple[float, list[str]]:
    """Provar radbrytningar vid blanksteg och behåller den som ger
    störst font-size. Lämnar texten orörd om inget byte förbättrar.
    """
    lines = text.split("\n")
    while True:
        current = _fit_font_size(lines, box_w, box_h)
        best = current
        best_lines: list[str] | None = None
        for i, line in enumerate(lines):
            spaces = [j for j, c in enumerate(line) if c == " "]
            if not spaces:
                continue
            for s in spaces:
                trial = (
                    lines[:i]
                    + [line[:s].rstrip(), line[s + 1:].lstrip()]
                    + lines[i + 1:]
                )
                size = _fit_font_size(trial, box_w, box_h)
                if size > best + 0.01:
                    best = size
                    best_lines = trial
        if best_lines is None:
            return current, lines
        lines = best_lines


# ---------------------------------------------------------------------------
# SVG-builder


def _build_svg(data: dict, debug: bool) -> str:
    rows, cols = data["rows"], data["cols"]
    width = cols * CELL + 2 * PADDING
    title_h = 30
    height = rows * CELL + 2 * PADDING + title_h

    def cx(x: float) -> float: return PADDING + x * CELL
    def cy(y: float) -> float: return PADDING + title_h + y * CELL

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="white"/>')
    parts.append(
        f'<text x="{PADDING}" y="{PADDING + 18}" '
        f'font-family="sans-serif" font-size="{TITLE_FONT_PX}" '
        f'font-weight="bold">{escape(data.get("name", ""))}</text>'
    )

    parts.extend(_render_nodes(data.get("nodes", []), cx, cy, debug))
    parts.extend(_render_leads(data.get("leads", []), cx, cy, debug))
    parts.extend(_render_arrows(data.get("arrows", []), data.get("leads", []), cx, cy))

    parts.append("</svg>")
    return "\n".join(parts)


def _render_nodes(nodes: list[dict], cx, cy, debug: bool) -> Iterable[str]:
    for node in nodes:
        x, y = node["position"]["x"], node["position"]["y"]
        is_sms = node.get("smsIndex") is not None
        is_caption = node.get("color") == "caption"
        # smsIndex tar prioritet visuellt
        fill = SMS_BG if is_sms else CAPTION_BG if is_caption else "white"
        yield (
            f'<rect x="{cx(x)}" y="{cy(y)}" width="{CELL}" height="{CELL}" '
            f'fill="{fill}" stroke="black" stroke-width="{STROKE}"/>'
        )
        if is_sms:
            yield (
                f'<text x="{cx(x) + 2}" y="{cy(y) + SOLUTION_INDEX_FONT + 1}" '
                f'font-family="sans-serif" font-size="{SOLUTION_INDEX_FONT}" '
                f'font-weight="bold">{node["smsIndex"]}</text>'
            )
        if debug:
            yield (
                f'<text x="{cx(x) + CELL - 1.5}" y="{cy(y) + 4.5}" '
                f'font-family="sans-serif" font-size="{DEBUG_COORD_FONT}" '
                f'fill="{DEBUG_COORD_COLOR}" text-anchor="end">{x},{y}</text>'
            )


def _render_leads(leads: list[dict], cx, cy, debug: bool) -> Iterable[str]:
    for lead in leads:
        pos = lead["position"]
        size = lead.get("size", {"width": 1, "height": 1})
        x, y = cx(pos["x"]), cy(pos["y"])
        w, h = size["width"] * CELL, size["height"] * CELL
        ltype = lead["type"]

        if ltype == "string":
            yield (
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                f'fill="white" stroke="black" stroke-width="{STROKE}"/>'
            )
            if debug:
                py = pos["y"]
                label = (
                    f"{pos['x']},{py:g}"
                    if isinstance(py, float) and py != int(py)
                    else f"{pos['x']},{int(py)}"
                )
                yield (
                    f'<text x="{x + w - 1.5}" y="{y + 4.5}" '
                    f'font-family="sans-serif" font-size="{DEBUG_COORD_FONT}" '
                    f'fill="{DEBUG_COORD_COLOR}" text-anchor="end">{label}</text>'
                )
            text = lead.get("clue", {}).get("text", "")
            font_size, lines = _fit_text_to_box(text, w, h)
            line_h = font_size * 1.15
            total = len(lines) * line_h
            start_y = y + (h - total) / 2 + font_size
            for i, line in enumerate(lines):
                yield (
                    f'<text x="{x + w / 2}" y="{start_y + i * line_h}" '
                    f'font-family="sans-serif" font-size="{font_size:.1f}" '
                    f'text-anchor="middle">{escape(line)}</text>'
                )
        elif ltype == "image":
            img = lead.get("image", {})
            data_uri = img.get("data", "")
            if data_uri:
                yield (
                    f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
                    f'preserveAspectRatio="xMidYMid slice" '
                    f'xlink:href="{escape(data_uri, quote=True)}"/>'
                )
                if img.get("border"):
                    yield (
                        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                        f'fill="none" stroke="black" stroke-width="{STROKE}"/>'
                    )
        elif ltype == "overlay":
            ov = lead.get("overlay", {})
            text = ov.get("text", "")
            if text:
                ox = ov.get("offset", {}).get("x", 0) * CELL
                oy = ov.get("offset", {}).get("y", 0) * CELL
                yield (
                    f'<text x="{x + w / 2 + ox}" y="{y + h / 2 + oy + 4}" '
                    f'font-family="sans-serif" font-size="12" '
                    f'text-anchor="middle" font-weight="bold">'
                    f'{escape(text)}</text>'
                )


# ---------------------------------------------------------------------------
# Pilrendering


def _render_arrows(arrows: list[dict], leads: list[dict], cx, cy) -> Iterable[str]:
    """Pilarna ligger på ledtrådsrutornas kant och pekar UT mot
    intilliggande bokstavsruta. Trailing-pilar är ord-separator i
    lösningsmeningen — placeras i cellen `arrow.x + 1` med en hög
    triangel som bas hela vänsterkanten av cellen.
    """
    stroke = 1.4
    triangle = CELL * 0.18
    arm_out = CELL * 0.18
    arm_perp = CELL * 0.30
    head = CELL * 0.11

    for a in arrows:
        pos = a["position"]
        atype = a["type"]
        edge = a.get("edge", "left")
        anchor = a.get("anchor")
        offset = a.get("offset")

        if atype == "trailing":
            rx = cx(pos["x"] + 1)
            ry = cy(pos["y"])
            tip_x = rx + CELL * 0.25
            tip_y = ry + CELL / 2
            yield (
                f'<polygon points="{rx:.2f},{ry:.2f} '
                f'{rx:.2f},{ry + CELL:.2f} '
                f'{tip_x:.2f},{tip_y:.2f}" fill="black"/>'
            )
            continue

        x0, y0 = cx(pos["x"]), cy(pos["y"])
        frac = _arrow_frac(offset, anchor, edge, pos, leads)
        anchor_pt = _edge_point(x0, y0, edge, frac)
        out_dir = _outward_direction(edge)

        if atype in ("horizontal-left", "horizontal-right", "vertical-down"):
            tip_dir = {
                "horizontal-left": (-1, 0),
                "horizontal-right": (1, 0),
                "vertical-down": (0, 1),
            }[atype]
            tip = (
                anchor_pt[0] + tip_dir[0] * triangle,
                anchor_pt[1] + tip_dir[1] * triangle,
            )
            yield _triangle_filled(anchor_pt, tip, triangle)
            continue

        bend_dir = _bend_direction(atype)
        if bend_dir is None:
            continue
        bx = anchor_pt[0] + out_dir[0] * arm_out
        by = anchor_pt[1] + out_dir[1] * arm_out
        line_end_x = bx + bend_dir[0] * (arm_perp - head)
        line_end_y = by + bend_dir[1] * (arm_perp - head)
        tip_x = bx + bend_dir[0] * arm_perp
        tip_y = by + bend_dir[1] * arm_perp
        yield (
            f'<path d="M{anchor_pt[0]:.2f},{anchor_pt[1]:.2f} '
            f'L{bx:.2f},{by:.2f} L{line_end_x:.2f},{line_end_y:.2f}" '
            f'fill="none" stroke="black" stroke-width="{stroke}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
        )
        yield _triangle(tip_x, tip_y, bend_dir, head)


def _arrow_frac(offset, anchor, edge, pos, leads):
    cx_, cy_top = pos["x"], int(pos["y"])
    if edge in ("left", "right"):
        candidates = sorted(
            [
                ld for ld in leads
                if ld["position"]["x"] == cx_
                and cy_top <= ld["position"]["y"] < cy_top + 1
            ],
            key=lambda ld: ld["position"]["y"],
        )
        axis_key, size_key, top = "y", "height", cy_top
    else:
        cx_left, cy_int = int(pos["x"]), pos["y"]
        candidates = sorted(
            [
                ld for ld in leads
                if ld["position"]["y"] == cy_int
                and cx_left <= ld["position"]["x"] < cx_left + 1
            ],
            key=lambda ld: ld["position"]["x"],
        )
        axis_key, size_key, top = "x", "width", cx_left

    # Lead-matching gäller bara split-celler (2+ leads). I icke-splittade
    # celler tolkas anchor leading/trailing som "nära kant" istället för
    # leadens mitt — för att L-pilarnas slutarm ska kunna nå in i
    # intilliggande cell när det behövs.
    if len(candidates) >= 2:
        target = None
        if anchor == "leading":
            target = candidates[0]
        elif anchor == "trailing":
            target = candidates[-1]
        elif offset is not None:
            for ld in candidates:
                local = ld["position"][axis_key] - top
                if local <= float(offset) < local + ld["size"][size_key]:
                    target = ld
                    break
            if target is None:
                target = candidates[0]
        elif anchor == "middle":
            for ld in candidates:
                local = ld["position"][axis_key] - top
                if local <= 0.5 < local + ld["size"][size_key]:
                    target = ld
                    break
        if target is not None:
            local = target["position"][axis_key] - top
            return local + target["size"][size_key] / 2

    if offset is not None:
        return float(offset)
    if anchor in ("leading", "middle", "trailing"):
        return {"leading": 0.20, "middle": 0.5, "trailing": 0.80}[anchor]
    return 0.5


def _edge_point(x0, y0, edge, frac):
    if edge == "left":
        return (x0, y0 + CELL * frac)
    if edge == "right":
        return (x0 + CELL, y0 + CELL * frac)
    if edge == "top":
        return (x0 + CELL * frac, y0)
    if edge == "bottom":
        return (x0 + CELL * frac, y0 + CELL)
    return (x0 + CELL / 2, y0 + CELL / 2)


def _outward_direction(edge):
    return {
        "left": (-1, 0),
        "right": (1, 0),
        "top": (0, -1),
        "bottom": (0, 1),
    }.get(edge, (0, 0))


def _bend_direction(atype):
    return {
        "horizontal-down-right": (1, 0),
        "horizontal-up-right": (1, 0),
        "vertical-right-down": (0, 1),
        "vertical-left-down": (0, 1),
    }.get(atype)


def _triangle_filled(base_pt, tip, size):
    bx, by = base_pt
    tx, ty = tip
    if tx - bx != 0:
        a = (bx, by - size * 0.5)
        b = (bx, by + size * 0.5)
    else:
        a = (bx - size * 0.5, by)
        b = (bx + size * 0.5, by)
    return (
        f'<polygon points="{tx:.2f},{ty:.2f} '
        f'{a[0]:.2f},{a[1]:.2f} {b[0]:.2f},{b[1]:.2f}" fill="black"/>'
    )


def _triangle(tip_x, tip_y, direction, size):
    dx, dy = direction
    bx = tip_x - dx * size
    by = tip_y - dy * size
    if dx != 0:
        a = (bx, by - size * 0.6)
        b = (bx, by + size * 0.6)
    else:
        a = (bx - size * 0.6, by)
        b = (bx + size * 0.6, by)
    return (
        f'<polygon points="{tip_x:.2f},{tip_y:.2f} '
        f'{a[0]:.2f},{a[1]:.2f} {b[0]:.2f},{b[1]:.2f}" fill="black"/>'
    )
