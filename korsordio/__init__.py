"""korsordio — render korsord.io crosswords as SVG/PDF.

Self-contained module for fetching and rendering Sverigekrysset/
Miljonkrysset and similar crosswords from app.korsord.io. Designed to
be liftable to its own repository (no imports outside this package).

Public API:
    fetch_crossword(slug, week, year) -> dict
    render_svg(data, debug=False) -> str
    render_pdf(data, output_path, debug=False) -> Path
"""
from .fetch import fetch_crossword
from .metadata import CrosswordMeta, parse_name
from .render import render_pdf, render_svg

__all__ = [
    "fetch_crossword",
    "render_svg",
    "render_pdf",
    "CrosswordMeta",
    "parse_name",
]
