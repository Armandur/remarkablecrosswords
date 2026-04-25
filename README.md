# reMarkable Crosswords

Automatisera leveransen av korsord till din reMarkable-läsplatta. Projektet integrerar med korsord.io för att hämta, rendera och skicka korsord direkt till din enhet.

## Funktioner
- Hämtar korsord från korsord.io.
- Renderar PDF-filer anpassade för reMarkable.
- Automatisk uppladdning via `rmapi`.
- Webbaserat dashboard för inställningar och hantering av källor.
- Stöd för schemalagda jobb.

## Deployment (TERVO2)

Använd `docker-compose.yml` för att köra applikationen på din server.

```bash
docker compose up -d
```

### Förstagångs-autentisering med rmapi

För att applikationen ska kunna skicka filer till din reMarkable måste du autentisera `rmapi` en gång manuellt:

```bash
docker run -it --rm \
  -v /mnt/user/appdata/remarkablecrosswords/rmapi:/root/.config/rmapi \
  ghcr.io/armandur/remarkablecrosswords:latest \
  rmapi
```
Följ instruktionerna på skärmen (besök https://my.remarkable.com/device/desktop/connect för att få en kod).

## Utvecklingsmiljö

### Med Docker Compose
```bash
docker compose -f docker-compose.dev.yml up
```

### Lokalt med uv
```bash
uv sync
uv run uvicorn app.main:app --reload
```

## Miljövariabler

Följande variabler kan konfigureras i din `.env`-fil:

| Variabel | Beskrivning | Standardvärde |
|----------|-------------|---------------|
| `SESSION_SECRET_KEY` | Hemlig nyckel för sessioner | (Krävs) |
| `ADMIN_INITIAL_PASSWORD` | Initialt lösenord för admin | (Krävs) |
| `DATA_DIR` | Sökväg till SQLite-databas och data | `/app/data` |
| `REMARKABLE_FOLDER` | Mapp på reMarkable där korsord hamnar | `/Korsord` |
| `REMARKABLE_CLIENT` | Vilken klient som ska användas (`rmapi` eller `local`) | `rmapi` |
| `QUEUE_DIR` | Sökväg för lokal kö (om `local` klient används) | `/app/queue` |
| `NTFY_URL` | URL för notifieringar via ntfy.sh | (Valfri) |
| `ENABLE_SCHEDULER` | Aktivera/inaktivera schemaläggaren | `true` |

## Arkitektur
Projektet är byggt med FastAPI och SQLite. Den använder `rmapi` för att kommunicera med reMarkable Cloud.
Korsordshämtning sker via den fristående modulen `korsordio`.
