"""CLI för keesing.

Användning:
    # Hämta alla slots och skriv PDF:er till en mapp:
    python -m keesing --outdir ./output

    # Specifika slots:
    python -m keesing --slots x1 x2 x9 --outdir ./output

    # Renderera lokal XML-fil:
    python -m keesing --file puzzle.xml --pdf out.pdf

    # Med debug-koordinater i renderingen:
    python -m keesing --file puzzle.xml --pdf out.pdf --debug

`--debug` ritar cell-koordinater (x,y) i grått i varje ruta.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .fetch import fetch_puzzle, PuzzleResult
from .render import render_pdf, render_svg, supports_xml

DEFAULT_CLIENT_ID = "dnmag"
DEFAULT_GAMETYPE = "arrowword_plus"
DEFAULT_SLOTS = [f"x{n}" for n in range(1, 10)]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="keesing",
        description="Hämta och rendera Keesing Arrowword-korsord",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--file",
        type=Path,
        help="Lokal XML-fil att rendera (skippa fetch).",
    )
    g.add_argument(
        "--outdir",
        type=Path,
        help="Mapp att skriva hämtade PDF:er till.",
    )
    p.add_argument(
        "--slots",
        nargs="+",
        default=DEFAULT_SLOTS,
        metavar="SLOT",
        help="Slots att hämta, t.ex. x1 x2 x9. Default: x1-x9.",
    )
    p.add_argument(
        "--client-id",
        default=DEFAULT_CLIENT_ID,
        help=f"Keesing client-ID. Default: {DEFAULT_CLIENT_ID}.",
    )
    p.add_argument(
        "--gametype",
        default=DEFAULT_GAMETYPE,
        help=f"Gametype. Default: {DEFAULT_GAMETYPE}.",
    )
    p.add_argument(
        "--pdf",
        type=Path,
        help="Skriv PDF till denna fil (används med --file).",
    )
    p.add_argument(
        "--svg",
        type=Path,
        help="Skriv SVG till denna fil (används med --file).",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Skriv ut cell-koordinater (x,y) i varje ruta.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.file:
        xml_bytes = args.file.read_bytes()
        if not (args.svg or args.pdf):
            print("error: minst en av --svg och --pdf måste anges med --file", file=sys.stderr)
            return 2
        if not supports_xml(xml_bytes):
            print("error: XML-filen är inte en Arrowword DPG-variation", file=sys.stderr)
            return 1
        if args.svg:
            svg = render_svg(xml_bytes, debug=args.debug)
            args.svg.write_text(svg)
            print(f"Wrote {args.svg} ({args.svg.stat().st_size:,} bytes)")
        if args.pdf:
            render_pdf(xml_bytes, args.pdf, debug=args.debug)
            print(f"Wrote {args.pdf} ({args.pdf.stat().st_size:,} bytes)")
        return 0

    # Fetch-läge
    args.outdir.mkdir(parents=True, exist_ok=True)
    print(f"Hämtar {len(args.slots)} slots för {args.client_id}/{args.gametype}...")
    print()

    seen_kse: set[str] = set()
    fetched = 0

    for slot in args.slots:
        result = fetch_puzzle(args.client_id, args.gametype, slot)
        if result is None:
            print(f"  {slot}: inte tillgänglig")
            continue
        if result.kse_id in seen_kse:
            print(f"  {slot}: {result.kse_id} redan hämtad (duplikat)")
            continue
        seen_kse.add(result.kse_id)

        label = result.title or result.variation or slot
        out_path = args.outdir / f"{result.published_at} - {label}.pdf"
        out_path.write_bytes(result.pdf_bytes)

        print(f"  {slot}: {result.kse_id}  {result.published_at}  '{result.title}'  ({len(result.pdf_bytes):,} bytes)")
        print(f"       -> {out_path.name}")
        fetched += 1

    print()
    print(f"Klar: {fetched} PDF:er sparade i {args.outdir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
