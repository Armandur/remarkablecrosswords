"""keesing — hämta och rendera Keesing Arrowword-korsord.

Self-contained module for fetching and rendering crosswords via the
Keesing Content API (web.keesing.com). Designed to be liftable to its
own repository (no imports outside this package).

Public API:
    fetch.fetch_puzzle(client_id, gametype, slot) -> PuzzleResult | None
    fetch.fetch_all(client_id, gametype, slots) -> list[PuzzleResult]
    render.render_svg(xml_bytes, debug=False) -> str
    render.render_pdf(xml_bytes, output, debug=False) -> Path
    render.supports_xml(xml_bytes) -> bool
"""
