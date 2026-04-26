# remarkablecrosswords — implementationsplan (utkast)

## Context

Du vill ha korsord på din reMarkable Pro utan manuellt PDF-pyssel.
Korsorden kommer från två olika typer av källor:

- **app.korsord.io** — interaktiv webbklient som publicerar
  **Sverigekrysset** och **Miljonkrysset** veckovis. URL-strukturen
  är förutsägbar (`/c/sverigekrysset-<vecka>-<år>/`), ingen
  inloggning krävs. Dessa två kryss syndikeras i flera dagstidningar
  — att hämta dem direkt här undviker dubbletter och slipper hela
  Prenly-flödet.
- **Prenly-tidningar** (DN, SvD, lokaltidningar m.fl.) för
  *tidningsspecifika* korsord (dagskrysset, kryptokrysset, lokala
  kryss). Mitt eget `prenly-dl`-repo visar API-flödet:
  hela tidnings-PDF:er hämtas och korsordssidor måste extraheras.

`zotero2remarkable_bridge` (separat repo) visar mönstret för
reMarkable-sync via `rmapi`-binären (ddvk/rmapi) snarare än ett eget
cloud-API-bygge.

`remarkablecrosswords` blir en tjänst som binder ihop fyra steg, alla
styrbara från ett webb-UI:

1. **Hämta** — beroende på källtyp:
   - korsord.io → använd egna `korsordio`-modulen (i samma repo) som
     hämtar `.crossword`-JSON och renderar SVG/PDF helt själv. Ingen
     Chromium, ingen Playwright. Modulen är self-contained och kan
     brytas ut till eget repo senare.
   - Prenly → ladda ner tidnings-PDF (logik från prenly-dl)
2. **Extrahera** — bara för Prenly-källor: plocka ut
   korsordssidorna ur tidnings-PDF:en. Hoppas över för korsord.io.
3. **Synka** — skicka korsords-PDF till reMarkable Pro via
   cloud (rmapi).
4. **Notifiera** — pinga mig när nya korsord ligger på plattan.

Mål: kör som en alltid-på tjänst på TERVO2 (Docker-container under
befintlig nginx-stack). Dev sker på ubuntu-ai. Schemalagd att hämta
nya kryss veckovis (korsord.io) respektive dagligen (Prenly), med
självsynk. Webb-UI för konfiguration, manuell körning, historik och
felsökning.

## Stack

Standard enligt globala defaulter:

- Python 3.12 + FastAPI (uvicorn, lifespan)
- SQLite via SQLAlchemy ORM (init_db med ALTER TABLE-guards, ingen Alembic)
- Jinja2 + vanilla JS/HTML/CSS, ingen bundler
- `itsdangerous` session-cookies, bcrypt, CSRF på POST
- APScheduler för cron-liknande jobb i samma process
- Docker + docker-compose (prod), Caddy som reverse proxy
- GitHub Actions → `ghcr.io/armandur/remarkablecrosswords`

Externa beroenden i container:
- `rmapi` (**ddvk/rmapi** — den enda fork som aktivt underhålls och har
  experimentellt stöd för reMarkables nya sync-protokoll, vilket
  reMarkable Pro använder). Statiskt linkad Go-binär kopieras in i
  imagen från release-artefakt.
- `cairosvg` för PDF-export från `korsordio`-modulen. Fetch sker via
  stdlib (`urllib`) — ingen `requests`-dep behövs för korsord.io-
  flödet. Ingen Playwright, ingen Chromium (~300 MB sparat).
- `pypdf` + `pdfplumber` för textextraktion ur Prenly-tidnings-
  PDF:er (Prenly-flödet, fas 2).
- `requests`, `img2pdf` (Prenly-flödet).

**Ingen OCR/tesseract** — både Prenly och korsord.io ger digitala
(textbaserade eller vector-baserade) PDF:er, så textextraktion
räcker. Skippar pdf2image/tesseract-beroenden helt.

## Arkitektur

```
korsordio/             # self-contained modul (KLAR — kan brytas ut till eget repo)
  __init__.py          # public API
  fetch.py             # urllib-baserad fetch + Tävla-modal-skrapning
  metadata.py          # parse_name → CrosswordMeta (titel, datum, vecka, tävlingsnr)
  render.py            # SVG-byggare, text-fitting, pilrendering, footer-zoner
  __main__.py          # CLI (argparse)
  spec.md              # reverse-engineered datamodell
  README.md
app/                   # tjänsten — INTE byggt än
  main.py              # FastAPI-app, lifespan, scheduler-start, router-reg
  config.py            # konstanter, env, paths
  database.py          # SQLAlchemy-modeller + init_db()
  schemas.py           # Pydantic
  auth.py              # session, bcrypt
  deps.py              # FastAPI-dependencies
  scheduler.py         # APScheduler-konfig + jobs
  routes/
    __init__.py
    auth.py            # login/logout
    sources.py         # CRUD: källor (slug eller prenly-config)
    issues.py          # lista/visa nedladdade nummer + extraherade korsord
    extraction.py      # regler för korsordsextrahering per källa (Prenly)
    sync.py            # status reMarkable, manuell trigger
    notifications.py   # konfig av notif-target, testskick
    jobs.py            # historik och loggar
  services/
    sources/
      __init__.py      # SOURCE_KINDS = {"korsordio": ..., "prenly": ...}
      base.py          # SourceFetcher-protokoll: list_available, download
      korsordio.py     # tunn adapter runt ../korsordio-paketet
      prenly.py        # refaktorerad prenly-dl: getContextToken, getCatalogueIssues,
                       # getIssueJSON, getHashes, getPDF, download_issue()
    crossword.py       # extract_pages_by_rule(pdf, rule) -> Path (bara Prenly-flödet)
    remarkable.py      # wrapper kring rmapi: upload, ls, mkdir, ensure_folder
    notifier.py        # abstrakt Notifier + implementation (ntfy/Pushover/...)
  utils/
    pdf.py             # pypdf-helpers (split, merge) — för Prenly-flödet
  templates/
  static/
data/                  # gitignored
  pdfs/incoming/       # hela tidnings-PDF:er (Prenly)
  pdfs/crosswords/     # renderade korsords-PDF:er, väntar på sync
  pdfs/synced/         # arkiv efter lyckad sync
  app.db
```

## Datamodell (SQLite)

- **users** — admin-användare (jag är ensam, men lösen ska skyddas)
- **sources** — en rad per källa, gemensam tabell för båda källtyper:
  - `name`, `kind` (`korsordio` | `prenly`), `enabled`,
    `schedule_cron`, `prefix`
  - `config_json` — kindspecifik konfiguration:
    - `korsordio`: `{"slug": "sverigekrysset"}` (URL byggs som
      `/c/<slug>-<vecka>-<år>/`)
    - `prenly`: `{"title_id", "site", "textalk_auth", "auth",
      "cdn"}` (tokens lagras maskerade i UI)
- **extraction_rules** — regel per `source_id`: `kind`
  (`pages` | `pages_per_weekday` | `text_match` | `manual`),
  `params_json`. Exempel: `{"weekday":"sat","pages":[28,29]}` eller
  `{"keywords":["korsord","kryss"]}`.
- **issues** — `source_id`, `prenly_uid`, `name`, `published_at`,
  `pdf_path`, `downloaded_at`, `state`
- **crosswords** — `issue_id`, `pdf_path`, `pages_json`, `extracted_at`,
  `synced_at`, `remarkable_path`
- **jobs** — `kind` (download | extract | sync | notify), `started_at`,
  `finished_at`, `state`, `log`, `source_id?`, `issue_id?`
- **notification_target** — `kind` (ntfy | pushover | gotify | email),
  `config_json`, `enabled`

## Modulansvar

### 1. Hämtning (`services/sources/`)

Gemensamt protokoll i `services/sources/base.py`:

```python
class SourceFetcher(Protocol):
    def list_available(self, source: Source) -> list[ExternalIssue]: ...
    def download(self, source: Source, ext_issue: ExternalIssue) -> Path: ...
```

`ExternalIssue` är en lättviktig dataklass med `external_id`, `name`,
`published_at`. `external_id` används för att slå mot `issues`-tabellen
och avgöra om något redan är hämtat.

#### `services/sources/korsordio.py`

Tunn adapter runt `korsordio`-paketet (samma repo, men brytbart):

- `list_available(source)` — GET mot `/g/<slug>/`, parsa
  `/c/<slug>-<v>-<yy>/`-länkar. Returnerar lista med
  `external_id="<v>-<yy>"`.
- `download(source, ext_issue)` — anropar
  `korsordio.fetch_crossword(slug, week, year)` + valfritt
  `fetch_competition_info(...)` + `render_pdf(data, path,
  sms_boxes=True, competition_info=info)`. PDF:en blir vector-
  baserad och självgenererad — inget headless-browser-steg.
- Filnamn använder `korsordio.parse_name(data["name"]).slug()`
  för naturlig sortering: `sverigekrysset-2026-w17.pdf`.
- Inget extraktionssteg — `render_pdf` ger ett färdigt korsord.

#### `services/sources/prenly.py`

Bryt isär `prenly-dl.py` (279 rader) i återanvändbara funktioner:

- `get_context_token(session, creds)`
- `list_catalogue_issues(session, creds, title_id, limit)` →
  återanvänds som `list_available()`
- `get_issue(session, creds, title_id, uid)` → JSON
- `extract_page_hashes(issue_json)` → `dict[str, str]`
- `download_pages(session, creds, title_id, hashes, out_dir)`
- `merge_pages(out_dir, target_pdf)`
- `download(source, ext_issue) -> Path` (orchestrator)

Output: hela tidnings-PDF:en i `data/pdfs/incoming/` — extraktionssteget
nedan plockar ut korsordssidorna.

Båda fetchers körs synkront i background-tasks. Skippa om
`issues.external_id` redan finns för källan.

### 2. Extrahering (`services/crossword.py`)

**Bara för Prenly-källor.** Korsord.io-flödet hoppar över detta steg
helt — `korsordio.render_pdf` ger redan ett färdigt korsord.

Eftersom Prenly-PDF:erna är digitala (textbaserade) räcker
`pdfplumber.extract_text()` per sida — ingen OCR.

Två sammansatta lager:

1. **Auto-detektering via textmatch** — sök per sida efter
   konfigurerbara mönster (default: regex
   `\b(korsord|krysset|kryss[äo]rd|sudoku)\b`, case-insensitive).
   Returnerar matchade sidnummer.
2. **Inlärd regel per källa** — när auto hittat sidor lyckat ett par
   gånger, spara `pages_per_weekday`-regel i DB. Vid framtida
   nedladdningar används regeln direkt och text-matchen blir bara en
   sanity-check (varnar i UI om regelns sidor inte längre innehåller
   nyckelord — layout kan ha ändrats).

Manuell override: om varken regel eller textmatch ger tydligt svar
markeras numret som `pending_review` och webb-UI visar
sid-thumbnails (renderade via `pypdfium2`) så jag kan klicka i sidor.
Det valet sparas både som extrahering *och* som ny/uppdaterad regel.

Output: en PDF per identifierat korsord (eller en sammanslagen) i
`data/pdfs/crosswords/`.

### 3. reMarkable-sync (`services/remarkable.py`)

Abstrakt `RemarkableClient`-interface med två implementationer:

- **`RmapiClient`** (default) — tunt skal kring ddvk/rmapi-binären.
  Mönster lånat från `zotero2remarkable_bridge/zrm/rmapi_shim.py`:
  `check`, `ensure_folder`, `upload`, `list_folder`, `delete`.
- **`LocalQueueClient`** (fallback) — kopierar PDF:er till en
  monterad mapp på TERVO2 (t.ex.
  `/mnt/user/remarkablecrosswords/queue/`) och loggar att manuell
  uppladdning krävs. Användbart om rmapi går sönder vid en
  protokollförändring från reMarkables sida — då kan jag dra över
  filerna via reMarkables USB Web Interface
  (`http://10.11.99.1`) på 30 sekunder.

UI och scheduler vet inte vilken klient som används; valet styrs av
`config.yml`/env. Webb-UI visar tydligt aktivt läge och tillåter
manuell omkörning av kö när rmapi åter funkar.

Förstagångs-auth: `rmapi`-binären skapar `~/.config/rmapi/rmapi.conf`
efter en interaktiv prompt. Setup på TERVO2:
1. `docker run -it --rm -v /mnt/user/appdata/remarkablecrosswords/rmapi:/root/.config/rmapi ghcr.io/armandur/remarkablecrosswords rmapi`
2. Klistra in koden från `my.remarkable.com/device/desktop/connect`
3. Configfilen ligger sen kvar i appdata-mappen och mountas av
   tjänstecontainern.

### 4. Notifiering (`services/notifier.py`)

Abstrakt `Notifier`-bas. Implementationer registreras i en dict
(`NOTIFIER_KINDS = {"ntfy": NtfyNotifier, ...}`) så det är trivialt
att lägga till nya senare.

**V1 (nu):** `NtfyNotifier` — POST till en ntfy-topic (publika
ntfy.sh i första hand, men URL:en är konfigurerbar för senare
självhost). Title, message, click-URL till webb-UI.

**Stubs/förberedda för senare** (interface klart men inte
implementerat förrän behov uppstår):
- `WebPushNotifier` — Web Push API + VAPID-nycklar, kräver service
  worker i webb-UI:t. Bygger vidare på samma admin-session.
- `DiscordWebhookNotifier` — POST till en Discord-webhook-URL.
  Trivial, kan göras samtidigt som ntfy om du vill.
- `HomeAssistantNotifier` — POST till HA `notify`-service via
  long-lived access token. Kan funka mot din OptiPlex-HA på
  192.168.1.64.

Multi-target: `notification_target`-tabellen tillåter flera aktiva
samtidigt — ett event pingar alla aktiverade.

Skickas vid: lyckad sync av minst ett nytt korsord. Inkludera tidning,
datum, antal sidor, deeplink till webb-UI.

## Webb-UI

Skydd: en admin-användare, login via `/login`, session-cookie.

Sidor:
- **Dashboard** (`/`) — senaste 10 jobb, antal korsord väntande sync,
  senaste notifiering, knappar "kör nu" per källa.
- **Källor** (`/sources`) — CRUD-formulär. Ny källa kräver
  `title_id`, site, auth-tokens. Kommentar i UI:t som förklarar var
  tokens hittas (Prenlys reader, devtools).
- **Källa-detalj** (`/sources/{id}`) — utdragna nummer, regler,
  dry-run-knapp som hämtar nyaste utan att synka, manuell
  sidavmarkering om regel saknas.
- **Korsord** (`/crosswords`) — lista med filtrer, möjlighet att
  manuellt trigga sync, ladda ner PDF, ta bort.
- **Inställningar** (`/settings`) — notifieringstarget,
  reMarkable-mapp, schemaläggning per källa.
- **Loggar** (`/jobs`) — paginerad jobblista, klick → loggdetalj.

## Schemaläggning

APScheduler i FastAPI-lifespan. Per källa: enligt `schedule_cron`.

Default-cron per källtyp:
- `korsordio`: `30 6 * * 1` — måndagar 06:30 (nya kryss läggs ut
  varje måndag).
- `prenly`: `30 6 * * *` — varje morgon (dagstidningar).

Pipeline per körning:
1. `fetcher = SOURCE_KINDS[source.kind]`
2. `available = fetcher.list_available(source)` — vilka externa
   issues finns för källan?
3. För varje `ext_issue` som inte redan finns i `issues`-tabellen:
   - `pdf = fetcher.download(source, ext_issue)`
   - Om `source.kind == "prenly"`: kör `extract_crosswords(pdf)` →
     en eller flera korsords-PDF:er i `data/pdfs/crosswords/`.
   - Om `source.kind == "korsordio"`: registrera PDF:en direkt som
     korsord (ingen extraktion).
4. `sync_pending_crosswords()` — pusha allt med `synced_at IS NULL`.
5. Om något synkades: `notify(...)`.

Manuell trigger via webb-UI startar samma pipeline för en specifik källa
eller ett specifikt nummer.

## Säkerhet & GDPR

- Prenly- och Textalk-tokens lagras i SQLite. Acceptabelt här (egen VM,
  egen instans), men markera fält som "secret" i UI och visa maskerat.
- Notifieringar innehåller bara tidningsnamn och datum, inga
  personuppgifter.
- Hämtade tidnings-PDF:er ska inte delas externt — `data/`-mappen är
  gitignored, ingen public route exponerar dem utan auth.
- `rmapi.conf` innehåller reMarkable cloud-token — mountas som
  read-only volym, finns inte i image.

## Deployment

**Mål-host: TERVO2 (Unraid).** Ej ubuntu-ai. Eftersom TERVO2 redan
har en nginx-stack för dina containrar går vi via den, inte Caddy.

`docker-compose.yml` (prod, körs på TERVO2 via Unraid Compose Manager
eller direkt i en docker-stack):
- service: `app` (FastAPI + APScheduler, samma process,
  `uvicorn --workers 1` så scheduler inte dubblerar)
- volumes:
  - `/mnt/user/appdata/remarkablecrosswords/data:/app/data` — DB +
    PDF-arkiv
  - `/mnt/user/appdata/remarkablecrosswords/rmapi:/root/.config/rmapi:ro`
    — reMarkable-token
  - `/mnt/user/remarkablecrosswords/queue:/app/queue` — fallback-mapp
    åtkomstbar från Unraid-shares (LocalQueueClient skriver hit)
- network: anslut till samma docker-nät som befintlig nginx
- exponering: ingen direkt port-mapping — nginx-containern proxar
  internt

Nginx-konfig läggs till i din befintliga nginx-stack: subdomän eller
subpath under en redan certifierad domän. Tailscale-only access som
default; om du vill ha publik åtkomst räcker nginx + befintlig
auth-stack (basic auth eller IP-allowlist).

`docker-compose.dev.yml` (dev på ubuntu-ai under utveckling):
- bind-mount `./` på `/app` med `--reload`
- exponera 8000 lokalt
- `dev.log` skrivs av uvicorn för Gemini-felsökning enligt globala
  riktlinjer

GitHub Actions bygger image till `ghcr.io/armandur/remarkablecrosswords`
med `:latest`, SHA, branch, semver. TERVO2 drar nya imagen via
Watchtower eller manuellt.

### Säkerhetsöverväganden för TERVO2-deployment

- TERVO2 är hemnätet, men `data/`-volymen kan innehålla hela
  tidnings-PDF:er (upphovsrättsskyddat material — bara för eget
  bruk). Ingen route exponerar dessa publikt utan login.
- `rmapi`-config-volymen är `:ro` för app-containern. Skrivs bara av
  setup-körningen.
- Nginx-stacken framför ger TLS; app-containern lyssnar bara på
  internt docker-nät.

## Kritiska filer som påverkas / skapas

`korsordio/` — **redan klar och commitad**. Modulen är self-contained
(bara `cairosvg` som extern dep, urllib för fetch) och kan brytas ut
till eget repo + PyPI-publicering när som helst.

Resten är fortfarande nytt. Förebilder att återanvända kod-mönster
från (inte importera direkt):

- `/tmp/prenly-dl/prenly-dl.py:13-156` — Prenly-API-funktioner
- `/tmp/zotero2remarkable_bridge/zrm/rmapi_shim.py:1-114` — rmapi-shim
- `/tmp/zotero2remarkable_bridge/zrm/adapters/ReMarkableAPI.py:1-113` —
  upload/exists/download-mönster
- `Armandur/svk-had-gravregister/app/auth.py` + `routes/auth.py` —
  auth-mönster (bcrypt + Starlette SessionMiddleware)

Förebilderna ska inte vendors:as utan portas in i `services/` med
SQLite-konfiguration istället för JSON/YAML, och med async-vänliga
signaturer (eller `run_in_threadpool` runt subprocess-anropen).

## Verifiering

End-to-end på ubuntu-ai:
1. `docker compose -f docker-compose.dev.yml up --build` startar app +
   uvicorn med reload.
2. `dev.log` (uvicorn-output) ska vara fri från fel.
3. Skapa admin-user i webb-UI, logga in.
4. Lägg till en testkälla med kända Prenly-tokens. Klicka "kör nu" →
   jobblistan ska visa download → extract → sync.
5. Verifiera att PDF dyker upp under `Korsord/<tidning>/` på
   reMarkable (rmapi ls).
6. Verifiera att ntfy-push når mobilen.

Test-suite (pytest):
- Unit: `services/prenly.py` med mockad `requests.Session`.
- Unit: `services/crossword.py` med en samplad PDF i `tests/fixtures/`.
- Unit: `services/remarkable.py` med mockad `subprocess.run` (samma
  mönster som zrm:s `tests/test_sync_mock.py`).
- Smoke: `from app.main import app; print("OK")`.

## Beslutade vägval (efter dialog)

- **Notifiering:** ntfy i V1, men `Notifier`-abstraktionen byggs
  generisk så Web Push, Discord-webhook och Home Assistant kan
  pluggas in senare utan refaktor.
- **Korsordsextrahering:** textmatchning på digitala PDF:er (ingen
  OCR), kompletterat med inlärd regel per källa och manuell
  override i UI.
- **Hosting:** TERVO2 som docker-container, bakom befintlig
  nginx-stack. Dev-miljö på ubuntu-ai under utveckling.
- **rmapi-klient:** ddvk/rmapi (mest aktivt underhållen), isolerad
  bakom `RemarkableClient`-interface med `LocalQueueClient` som
  fallback om cloud-protokollet pajar.

## Slutgiltiga vägval

- **Nginx-routing:** egen subdomän (t.ex. `crosswords.<din-domän>`)
  med eget cert-block i befintlig nginx-stack på TERVO2.
- **Åtkomst:** publik exponering med inlogg. Mönster lånat rakt från
  `svk-had-gravregister/app/auth.py` + `routes/auth.py`:
  - Starlette `SessionMiddleware` med `SESSION_SECRET_KEY` från env
  - bcrypt password hash, `User`-modell (`username`, `password_hash`,
    `is_admin`)
  - `ensure_first_admin()` i lifespan: om inga users finns och
    `ADMIN_INITIAL_PASSWORD` är satt → skapa `admin`
  - `get_current_user` och `require_admin` som FastAPI-dependencies
  - `POST /api/login` (JSON), `POST /api/logout`, `GET /api/me`,
    `PUT /api/me/password` — exakt samma signaturer som svk-had
  - Vanilla JS-formulär på `/login`-sidan postar JSON och redirectar
    vid framgång (samma frontend-mönster)
  - rate limiting (`slowapi`) på `/api/login` mot brute-force
  - HSTS via nginx, inga `data/`-PDF:er nås utan auth-check
  - **Ingen e-post, ingen magic-link** — räcker med
    username/password eftersom du är ensam användare
- **Källor:** ingen seed-data. Webb-UI:t för tillägg av källor byggs
  som första-class-flöde. Formuläret har två lägen efter `kind`-val:
  - **korsord.io** — bara `slug` (default-val: `sverigekrysset`,
    `miljonkrysset`). "Test connection" hämtar senaste veckans URL
    och verifierar att sidan finns.
  - **prenly** — `title_id`, `site`, `textalk_auth`, `auth`, ev.
    `cdn`. Tokens visas maskerade. "Test connection" hämtar
    katalogmetadata utan att ladda ned hela PDF:en.

## V1-prioritering (första iteration att bygga)

**Fas 0 — KLAR:** `korsordio`-modulen. Hämtar och renderar
Sverigekrysset/Miljonkrysset till SVG/PDF. Verifierad mot 87 kryss
(44 sverigekrysset + 43 miljonkrysset, v17 2025 – v17 2026).
Inkluderar `--sms-boxes` och `--competition-info`-flaggor för fullt
självservice-kryss på reMarkable.

**Fas 1 — korsord.io end-to-end via tjänsten:**
1. ✅ FastAPI-skelett, SQLite, lifespan, auth-mönster från svk-had.
2. ✅ `services/sources/base.py` + `services/sources/korsordio.py`
   (tunn adapter runt `korsordio`-paketet).
3. ✅ `services/remarkable.py` med både `RmapiClient` och
   `LocalQueueClient`.
4. ✅ `services/notifier.py` med `NtfyNotifier`.
5. ✅ Scheduler som kör pipelinen för korsord.io-källor.
6. ✅ Webb-UI: login, Bootstrap-styling, källista, korsordslista med
   inline PDF-visning, jobblogg med paginering, inställningar.
7. ✅ korsordio-flaggor (`sms_boxes`, `fetch_competition`) konfigurerbara
   per källa via `config_json`.
8. **rmapi-autentisering via webb-UI** — istället för `docker run -it`:
   - Inställningssidan visar autentiseringsstatus (config-fil finns/saknas).
   - Formulär för engångskod från `my.remarkable.com/device/desktop/connect`.
   - Anropar reMarkable device-registration-API direkt (ingen interaktiv
     rmapi-process) och skriver `rmapi.conf`.
   - `RMAPI_CONFIG_PATH` konfigurerbar via env (default `~/.config/rmapi/rmapi.conf`).
9. **CSRF-skydd på alla POST-formulär** — `itsdangerous`-signerat token
   i hidden input, valideras i middleware eller per route.
10. **"Test connection" per källtyp** — knapp i källformuläret som verifierar
    slug/tokens utan att spara eller ladda ned.
11. Deploy mot TERVO2 (efter att grund är solid).

Vid fas-1-slut ska du kunna lägga till en korsord.io-källa och få
Sverigekrysset på reMarkable varje måndag morgon med ntfy-ping och
tävlingsinfo direkt på sidan.

**Fas 2 — Prenly-källor + extraktion:**
8. `services/sources/prenly.py` (port av prenly-dl).
9. `services/crossword.py` (textmatch + inlärd regel).
10. UI för regelhantering och manuell sidavmarkering.

**Fas 3 — polish:**
11. Fler notifierare (Discord-webhook är trivial att lägga till).
12. Web Push om/när du vill ha det.
13. Tests + CI.
14. Bryt ut `korsordio` till eget repo + PyPI om modulen mognar.
