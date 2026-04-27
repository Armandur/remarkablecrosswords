# Källa: Prenly

Hämtar tidningsnummer från Prenly-plattformen (Textalk). Använder `prenly-dl`-biblioteket
(`github.com/Armandur/prenly-dl`) för autentisering och sidnedladdning.

## API-endpoints

| Syfte | URL |
|---|---|
| Context token | `POST https://content.textalk.se/api/web-reader/v1/context-token` |
| Lista nummer | `GET https://apicdn.prenly.com/api/web-reader/v1/issues` |
| Nummermetadata (JSON-RPC) | `POST https://content.textalk.se/api/v2/` (method `Issue.get`) |
| Sidmedia | `{cdn}/api/v2/media/get/{title_id}/{checksum}?h=abc` |

## Autentiseringsflöde

1. Hämta context token med `textalk_auth` + `auth` (Bearer).
2. Använd token för att lista tillgängliga nummer.
3. Hämta nummermetadata via JSON-RPC för att få sidhashar.
4. Ladda ned varje sida (PDF eller bild) från CDN med `Origin`/`Referer`.

## `config_json`-fält

| Fält | Typ | Default | Beskrivning |
|---|---|---|---|
| `site` | string | — | Publikationens webbadress, t.ex. `https://etidning.sydsvenskan.se` |
| `textalk_auth` | string | — | API-nyckel (`X-Textalk-Content-Client-Authorize`-header) |
| `auth` | string | — | Bearer-token för autentisering |
| `title_id` | string | — | Publikationens ID i Prenly |
| `cdn` | string | `https://mediacdn.prenly.com` | CDN-URL (valfri) |
| `extraction_pages` | list[int] | `[]` | 1-indexerade sidnummer att extrahera till separat PDF. Tomt = hela numret. |
| `crossword_marker_text` | string | — | Text som identifierar korsordsidan (t.ex. `"SE KRYSSET"`). När satt: sidor skannas med pypdf tills texten hittas, sedan tas overlayen bort ur innehållsströmmen (q...Q-block med `/GS2 gs` filtreras bort). Mer exakt än `extraction_pages` och bevarar sidlayouten. |

## `external_id`-format

Prenlys `uid` för numret (heltalssträng).

## Publiceringscykel

Beror på publikationen, ofta dagligen. Konfigurera cron-schema efter utgivningsdag.

## Kända begränsningar

- Tokens kan löpa ut och behöva uppdateras manuellt i källans config.
- `prenly_dl.get_issue_json` och `download_pdf` anropar `sys.exit(1)` vid API-fel —
  `PrenlyFetcher.download` fångar `SystemExit` och konverterar till `RuntimeError`.
- Sidor som levereras som bilder (inte PDF) konverteras automatiskt via `img2pdf`.
