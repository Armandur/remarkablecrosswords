# korsordio

Self-contained Python-modul för att hämta och rendera kryss från
[app.korsord.io](https://app.korsord.io) (Sverigekrysset, Miljonkrysset
och liknande) som SVG eller PDF.

Bygger via `cairosvg` på en strukturerad SVG-mall som tar fram
korsordsrutor, ledtrådar (text + bild + overlay), pilar och
färgkodade lösningsrutor utifrån korsord.io:s `.crossword`-JSON.

Datamodellen är dokumenterad i `../korsord.io-spec.md`.

## Installation

```bash
pip install cairosvg   # enda externa beroendet
```

Stdlib räcker för fetch (`urllib`).

## Användning som bibliotek

```python
from korsordio import fetch_crossword, render_pdf, render_svg

data = fetch_crossword("sverigekrysset", week=17, year=26)
render_pdf(data, "krysset.pdf")          # produktionsmässig
svg_text = render_svg(data, debug=True)  # med cell-koordinater
```

## CLI

```bash
# Hämta från korsord.io och skriv PDF:
python -m korsordio sverigekrysset 17 26 --pdf krysset.pdf

# Båda formaten i samma körning + debug-koordinater:
python -m korsordio miljonkrysset 17 26 --pdf out.pdf --svg out.svg --debug

# Renderera en lokal .crossword-fil:
python -m korsordio --file ./sverigekrysset-17-26.crossword --svg out.svg
```

Minst en av `--pdf` och `--svg` måste anges. När båda används
återanvänds SVG-strängen (en rendering, två format).

`--debug` ritar koordinater (`x,y`) i grått i varje rutas övre högra
hörn — användbart för att referera till specifika rutor när man
felsöker layouten.

## Public API

| Funktion                                 | Beskrivning                                          |
| ---------------------------------------- | ---------------------------------------------------- |
| `fetch_crossword(slug, week, year)`      | Hämta `.crossword`-JSON från app.korsord.io.         |
| `render_svg(data, debug=False)`          | Returnera SVG som sträng.                            |
| `render_pdf(data, output, debug=False)`  | Skriv PDF till `output`. Kräver `cairosvg`.          |

## Modulstruktur

```
korsordio/
  __init__.py    # public API
  fetch.py       # urllib-baserad hämtning från app.korsord.io
  render.py      # SVG-byggare, text-fitting, pilrendering
  __main__.py    # CLI (argparse)
  README.md
```

## Designval

- **Inga externa Python-beroenden för fetch** (urllib istället för
  requests) — gör modulen lättviktig och driftsäker.
- **`cairosvg` är valfritt** — bara nödvändigt för `render_pdf`. Om du
  bara behöver SVG kan du undvika det.
- **Ingen statisk konfig** — allt läses från `.crossword`-data.

## TODO / framtida features

- **Bildextraktion**: image-leads bäddar in JPEG som base64 (~2 MB
  per kryss). En `extract_images(data) -> list[(name, bytes)]` skulle
  låta oss spara bilderna separat och länka eller komprimera dem
  innan SVG/PDF-rendering. Kan halvera utdatastorleken.
- **PDF-storleksoptimering**: `cairosvg` re-encodar base64-JPEG:er
  ineffektivt (12 MB PDF för 2 MB SVG). En direkt PDF-väg via
  `reportlab` eller post-process via `pikepdf`/`ghostscript` skulle
  ge ~2 MB output.
- **Faktisk text-mätning**: `Pillow.ImageDraw.textlength()` istället
  för per-tecken-vikter — mer exakt fit utan justering.
- **`vertical-up`-pil**: inte sett i exempel-data, men kan förekomma
  i andra kryss-titlar.
- **Brytas ut till eget repo**: när modulen är stabil, flytta till
  egen GitHub-repo + publicera på PyPI. Kräver bara ett
  `pyproject.toml`, allt annat är redan självständigt.
- **Verifiera fler titlar**: just nu testat mot Sverigekrysset (v17
  och v10 av 2026) och Miljonkrysset (v17 av 2026). Andra kryss-typer
  (knepiga, kryptiska, korsrim) kan ha ytterligare type-värden.
