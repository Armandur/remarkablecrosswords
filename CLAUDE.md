# CLAUDE.md - reMarkable Crosswords

## Stack
- **Backend:** FastAPI (Python 3.12)
- **Databas:** SQLite + SQLAlchemy
- **Schemaläggning:** APScheduler
- **PDF-rendering:** CairoSVG (via `korsordio`)
- **reMarkable-integration:** `rmapi` (extern binär)
- **Pakethantering:** `uv`

## Filstruktur
- `app/`: Huvudapplikation
  - `main.py`: Entrypoint och FastAPI-initiering
  - `config.py`: Miljövariabler och Pydantic Settings
  - `database.py`: SQLAlchemy setup
  - `auth.py`: Autentiseringslogik (bcrypt)
  - `scheduler.py`: APScheduler konfiguration
  - `routes/`: API och web-endpoints (crosswords, sources, settings, etc.)
  - `services/`: Affärslogik (remarkable integration, notifieringar)
  - `templates/`: Jinja2 templates för webbgränssnittet
- `korsordio/`: Fristående modul för hämtning och rendering av korsord (rör ej).
- `keesing/`: Fristående modul för hämtning och rendering av Keesing Arrowword DPG-korsord (playpuzzlesonline.com). Avsedd att på sikt brytas ut som eget repo, likt korsordio.
- `static/`: Statiska filer (CSS, JS)
- `data/`: Databas och lokal lagring (gitignored)

## Viktiga designbeslut
1. **korsordio-modulen:** Denna modul är självständig och fungerar som ett bibliotek. Modifiera inte dess interna logik såvida det inte är absolut nödvändigt.
2. **keesing-modulen:** Självständig modul, samma princip som korsordio. Modifiera inte dess interna logik. Avsedd att på sikt bli ett eget paket.
3. **SOURCE_KINDS:** Registreras i `app/services/sources/__init__.py`. För att lägga till en ny källa, implementera `SourceFetcher`-protokollet och lägg till den i mappen `app/services/sources/`.
4. **RemarkableClient:** Ett interface (`Protocol`) som tillåter olika implementations (t.ex. `RmapiClient` för cloud-sync eller `LocalQueueClient` för lokal filflytt).
5. **ENABLE_SCHEDULER:** Bör vara `false` under aktiv utveckling för att undvika oväntade bakgrundsjobb.

## rmapi-quirks

**Version:** v0.0.32 installerad i `/usr/local/bin/rmapi`.

**Autentisering:** `rmapi` lagrar tokens i `~/.config/rmapi/rmapi.conf` (JSON med `devicetoken` och `usertoken`). Appen registrerar enheter direkt mot reMarkable cloud API (`webapp.cloud.remarkable.com`) utan att använda `rmapi register` — konfigfilen skrivs av `register_remarkable()` i `app/services/remarkable.py`.

**Schema v4 / skrivoperationer:** rmapi v0.0.32 använder sync-protokoll 1.5, men reMarkable cloud kräver numera schema v4 för alla skrivoperationer (mkdir, put, rm). Utan miljövariabeln `RMAPI_FORCE_SCHEMA_VERSION=4` misslyckas alla skrivoperationer med HTTP 400. `RmapiClient._run()` sätter denna variabel automatiskt. Läsoperationer (ls) fungerar utan variabeln. Fix följs av ddvk/rmapi PR #55.

**rm är inte rekursivt:** `rmapi rm /mapp` misslyckas om mappen inte är tom. Ta bort innehållet först.

## Vanliga uppgifter
- **Lägga till ny Notifier:** Skapa en ny klass i `app/services/notifier.py` och registrera den i `get_notifiers()`.
- **Lägga till ny SourceFetcher:** Implementera klassen i `app/services/sources/` och uppdatera `SOURCE_KINDS` i `__init__.py`.

## Keesing-renderaren - testning och visuell granskning

Testfiler för `keesing/`-modulen synkas till `/mnt/vmworkspace/keesing/<timestamp>/` så att
renderingar kan granskas från hosten. Varje testkörning läggs i en ny datumstämplad mapp -
gallring sköts manuellt.

Varje testkörning ska innehålla **fem filer per slot**:
1. `<slot>.svg` - renderad SVG utan debug
2. `<slot>.pdf` - renderad PDF utan debug
3. `<slot>_debug.svg` - renderad SVG med `debug=True` (koordinater i varje ruta)
4. `<slot>_debug.pdf` - renderad PDF med `debug=True`
5. `<slot>_original.png` - råbilden från `getimage`-API:et (jämförelsebild)

Skript för att köra en testkörning och synka:

```bash
uv run python - <<'EOF'
import pathlib
from datetime import datetime
from keesing.fetch import fetch_puzzle, SESSION
from keesing.render import render_svg, render_pdf

outdir = pathlib.Path(f"/mnt/vmworkspace/keesing/{datetime.now().strftime('%Y%m%d_%H%M%S')}")
outdir.mkdir(parents=True, exist_ok=True)

for slot in ["x1", "x3", "x8"]:
    r = fetch_puzzle("dnmag", "arrowword_plus", slot)
    if not r:
        print(f"{slot}: inte tillgänglig")
        continue
    info = SESSION.get(
        f"https://web.keesing.com/Content/GetPuzzleInfo?clientid=dnmag&puzzleid=arrowword_plus_{slot}_today_&epochtime=1",
        timeout=15,
    ).json()
    kse_id = info["puzzleID"]
    xml_bytes = SESSION.get(f"https://web.keesing.com/content/getxml?clientid=dnmag&puzzleid={kse_id}", timeout=15).content
    png_bytes = SESSION.get(f"https://web.keesing.com/content/getimage?clientid=dnmag&puzzleid={kse_id}", timeout=30).content

    (outdir / f"{slot}_original.png").write_bytes(png_bytes)
    (outdir / f"{slot}.svg").write_text(render_svg(xml_bytes, image_bytes=png_bytes, date_str=str(r.published_at)))
    (outdir / f"{slot}_debug.svg").write_text(render_svg(xml_bytes, image_bytes=png_bytes, date_str=str(r.published_at), debug=True))
    render_pdf(xml_bytes, outdir / f"{slot}.pdf", image_bytes=png_bytes, date_str=str(r.published_at))
    render_pdf(xml_bytes, outdir / f"{slot}_debug.pdf", image_bytes=png_bytes, date_str=str(r.published_at), debug=True)
    print(f"{slot}: {r.published_at}  {r.title}  -> {outdir.name}/")

print("Klar:", outdir)
EOF
```

## Verifiering
Kör följande för att snabbt verifiera att applikationen kan starta:
```bash
uv run python -c 'from app.main import app; print("OK")'
```
eller
```bash
uv run pytest
```
