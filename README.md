# remarkablecrosswords

Hämtar korsord automatiskt och synkar dem till din reMarkable-läsplatta som PDF. Konfigureras via ett webbaserat gränssnitt.

## Stödda källor

| Källa | Typ | Cron-förslag |
|---|---|---|
| **korsord.io** | Sverigekrysset, Miljonkrysset m.fl. — hämtar `.crossword`-JSON och renderar PDF lokalt | `30 6 * * 1` |
| **SR Melodikryss** | Sveriges Radio P4:s veckokryss — direktnedladdning av färdig PDF | `30 8 * * 6` |
| **Keesing (Arrowword DPG)** | Pilkorsord via Keesing Content API — hämtar XML + bild och renderar PDF lokalt. Täcker bl.a. Dagens Nyheter, Söndagskrysset och Bonnier News-poolen (Expressen, Sydsvenskan m.fl.) | `0 7 * * *` |

## Funktioner

- Webbaserat UI: lägg till/redigera källor, bläddra reMarkable-mappar, se jobbloggar
- Schemalagda hämtningar per källa (APScheduler + cron-uttryck)
- Synkstatus uppdateras asynkront i korsordslistans — klicka på utfall för att se logg
- Rendera om enstaka källas alla korsord (t.ex. efter ändrad inställning)
- Tvinga omhämtning med valfri kombination av cache-rensning och overwrite på reMarkable
- Notifieringar via [ntfy](https://ntfy.sh) när nya korsord synkats
- Fallback: `LocalQueueClient` kopierar PDF:er till en lokal mapp om rmapi inte är tillgänglig

## Deployment (TERVO2 / produktion)

```bash
cp .env.example .env
# Redigera .env — sätt SESSION_SECRET_KEY och ADMIN_INITIAL_PASSWORD
docker compose up -d
```

Öppna webgränssnittet, logga in och gå till **Inställningar** för att autentisera mot reMarkable (engångskod från [my.remarkable.com/device/desktop/connect](https://my.remarkable.com/device/desktop/connect)).

## Utvecklingsmiljö

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up
```

Eller direkt med uv (utan Docker):

```bash
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Sätt `ENABLE_SCHEDULER=false` i `.env` under utveckling för att undvika oväntade bakgrundsjobb.

## Miljövariabler

Kopiera `.env.example` och justera:

| Variabel | Standardvärde | Beskrivning |
|---|---|---|
| `SESSION_SECRET_KEY` | — | Lång slumpmässig sträng, krävs |
| `ADMIN_INITIAL_PASSWORD` | — | Sätts vid första start om inga användare finns |
| `DATA_DIR` | `/app/data` | SQLite-databas och PDF-arkiv |
| `REMARKABLE_FOLDER` | `/Korsord` | Basmapp på reMarkable (kan åsidosättas i UI) |
| `REMARKABLE_CLIENT` | `rmapi` | `rmapi` eller `local` (lokal kö-fallback) |
| `QUEUE_DIR` | `/app/queue` | Används av `local`-klienten |
| `NTFY_URL` | — | Valfri, t.ex. `https://ntfy.sh/min-hemliga-topic` |
| `ENABLE_SCHEDULER` | `true` | Sätt `false` under utveckling |
| `RMAPI_CONFIG_PATH` | `~/.config/rmapi/rmapi.conf` | Sökväg till rmapi-tokens |

## Arkitektur

```
korsordio/              fristående modul — hämtar och renderar korsord.io-kryss
keesing/                fristående modul — hämtar och renderar Keesing-pussel
  fetch.py              GetPuzzleInfo + getxml + getimage mot web.keesing.com
  render.py             SVG/PDF-rendering av Arrowword DPG (pilkorsord)
  spec.md               API-dokumentation och XML-format
app/
  main.py               FastAPI-app, lifespan, router-registrering
  config.py             miljövariabler och sökvägar
  database.py           SQLAlchemy-modeller + init_db()
  scheduler.py          APScheduler + pipeline-funktioner
  csrf.py               CSRF-skydd (itsdangerous)
  routes/               en fil per domän (sources, crosswords, jobs, settings, …)
  services/
    remarkable.py       RmapiClient / LocalQueueClient
    notifier.py         NtfyNotifier (utbyggbar)
    sources/
      korsordio/        KorsordioFetcher + spec.md
      sr_melodikryss/   SRMelodikryssFetcher + spec.md
      keesing/          KeesingFetcher (Arrowword DPG) + spec.md
  templates/            Jinja2 + Bootstrap 5
```

Nya källtyper läggs till i `app/services/sources/` — implementera `SourceFetcher`-protokollet (`list_available` + `download`) och registrera i `SOURCE_KINDS`.

`keesing/`-modulen är fristående och avsedd att på sikt brytas ut som eget paket, likt `korsordio/`. Den innehåller även spec och renderare för Keesing-speltyperna crossword, sudoku och tectonic (inte implementerade ännu).

## Krav

- Python 3.12
- [`rmapi`](https://github.com/ddvk/rmapi) v0.0.32 (ingår i Docker-imagen)
- `cairosvg` + systembibliotek för CairoSVG (ingår i Docker-imagen)
- `pyphen` för stavelseavstavning i Keesing-renderaren
