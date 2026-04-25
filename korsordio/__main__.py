"""CLI för korsordio.

Användning:
    # Hämta från korsord.io och skriv PDF:
    python -m korsordio sverigekrysset 17 26 --pdf krysset.pdf

    # Båda formaten i samma körning + debug-koordinater:
    python -m korsordio miljonkrysset 17 26 --pdf out.pdf --svg out.svg --debug

    # Renderera lokal .crossword-fil:
    python -m korsordio --file path/to.crossword --svg out.svg

`--debug` ritar cell-koordinater i grått så man kan referera till
specifika rutor under felsökning.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .fetch import fetch_competition_info, fetch_crossword
from .render import render_pdf, render_svg


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="korsordio",
        description="Render Sverigekrysset/Miljonkrysset från korsord.io",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--file",
        type=Path,
        help="Lokal .crossword-fil att rendera (skippa fetch).",
    )
    g.add_argument(
        "spec",
        nargs="?",
        help="Slug, t.ex. sverigekrysset eller miljonkrysset.",
    )
    p.add_argument("week", nargs="?", type=int, help="Veckonummer (1-52).")
    p.add_argument("year", nargs="?", type=int, help="Två-siffrigt år (26 = 2026).")
    p.add_argument(
        "--pdf",
        type=Path,
        help="Skriv PDF till denna fil (kräver cairosvg).",
    )
    p.add_argument(
        "--svg",
        type=Path,
        help="Skriv SVG till denna fil.",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Skriv ut cell-koordinater (x,y) i varje ruta.",
    )
    p.add_argument(
        "--sms-boxes",
        action="store_true",
        help="Lägg en rad tomma SMS-svarsrutor (turkos) under krysset "
        "för manuell sammanställning av lösningskoden.",
    )
    p.add_argument(
        "--competition-info",
        action="store_true",
        help="Hämta tävlingsinfo från korsord.io och rita under krysset. "
        "Kräver slug+week+year (inte --file).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.file:
        data = json.loads(args.file.read_text())
    else:
        if args.spec is None or args.week is None or args.year is None:
            print("error: spec, week och year krävs när --file inte används", file=sys.stderr)
            return 2
        data = fetch_crossword(args.spec, args.week, args.year)

    if not (args.svg or args.pdf):
        print("error: minst en av --svg och --pdf måste anges", file=sys.stderr)
        return 2

    competition_info = None
    if args.competition_info:
        if args.file:
            print(
                "error: --competition-info kräver slug+week+year, inte --file",
                file=sys.stderr,
            )
            return 2
        competition_info = fetch_competition_info(args.spec, args.week, args.year)

    render_kwargs = dict(
        debug=args.debug,
        sms_boxes=args.sms_boxes,
        competition_info=competition_info,
    )

    if args.svg:
        args.svg.write_text(render_svg(data, **render_kwargs))
        print(f"Wrote {args.svg} ({args.svg.stat().st_size} bytes)")
    if args.pdf:
        render_pdf(data, args.pdf, **render_kwargs)
        print(f"Wrote {args.pdf} ({args.pdf.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
