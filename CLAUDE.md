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

## rmapi-quirks

**Version:** v0.0.32 installerad i `/usr/local/bin/rmapi`.

**Autentisering:** `rmapi` lagrar tokens i `~/.config/rmapi/rmapi.conf` (JSON med `devicetoken` och `usertoken`). Appen registrerar enheter direkt mot reMarkable cloud API (`webapp.cloud.remarkable.com`) utan att använda `rmapi register` — konfigfilen skrivs av `register_remarkable()` i `app/services/remarkable.py`.

**Schema v4 / skrivoperationer:** rmapi v0.0.32 använder sync-protokoll 1.5, men reMarkable cloud kräver numera schema v4 för alla skrivoperationer (mkdir, put, rm). Utan miljövariabeln `RMAPI_FORCE_SCHEMA_VERSION=4` misslyckas alla skrivoperationer med HTTP 400. `RmapiClient._run()` sätter denna variabel automatiskt. Läsoperationer (ls) fungerar utan variabeln. Fix följs av ddvk/rmapi PR #55.

**rm är inte rekursivt:** `rmapi rm /mapp` misslyckas om mappen inte är tom. Ta bort innehållet först.

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
