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
- `static/`: Statiska filer (CSS, JS)
- `data/`: Databas och lokal lagring (gitignored)

## Viktiga designbeslut
1. **korsordio-modulen:** Denna modul är självständig och fungerar som ett bibliotek. Modifiera inte dess interna logik såvida det inte är absolut nödvändigt.
2. **SOURCE_KINDS:** Registreras i `app/services/sources/__init__.py`. För att lägga till en ny källa, implementera `SourceFetcher`-protokollet och lägg till den i mappen `app/services/sources/`.
3. **RemarkableClient:** Ett interface (`Protocol`) som tillåter olika implementations (t.ex. `RmapiClient` för cloud-sync eller `LocalQueueClient` för lokal filflytt).
4. **ENABLE_SCHEDULER:** Bör vara `false` under aktiv utveckling för att undvika oväntade bakgrundsjobb.

## Vanliga uppgifter
- **Lägga till ny Notifier:** Skapa en ny klass i `app/services/notifier.py` och registrera den i `get_notifiers()`.
- **Lägga till ny SourceFetcher:** Implementera klassen i `app/services/sources/` och uppdatera `SOURCE_KINDS` i `__init__.py`.

## Verifiering
Kör följande för att snabbt verifiera att applikationen kan starta:
```bash
uv run python -c 'from app.main import app; print("OK")'
```
eller
```bash
uv run pytest
```
