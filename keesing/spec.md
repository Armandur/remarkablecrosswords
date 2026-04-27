# Keesing Content API - spec

Dokumenterar vad vi lärt oss om Keesing-APIet som används av
`playpuzzlesonline.com` (och sannolikt andra licensierade utgivare).

## Bakgrund

`playpuzzlesonline.com` är en tunn wrapper som laddar Keesing-spelaren
(`web.keesing.com/pub/player/v2.25.6/dist/main-bundle.js`) via en `<div
id="puzzle-portal" data-customerid="dnmag">`. All pussel-logik och alla
API-anrop sker inuti bundlen. **Ingen JS-rendering behövs** för att hämta
bilderna - de är tillgängliga direkt via HTTP.

## Klient-ID:n

| Utgivare | client_id | Gametype |
|----------|-----------|----------|
| Dagens Nyheter | `dnmag` | `arrowword_plus` |
| Söndagskrysset (DN) | `dnmag` | `arrowword_plus` (slot x9) |

Andra utgivare på playpuzzlesonline.com har egna `client_id`:n.

## API-endpoints

Bas-URL: `https://web.keesing.com`

### GetPuzzleInfo (metadata)
```
GET /Content/GetPuzzleInfo?clientid={clientid}&puzzleid={puzzleid}&epochtime={ts}
```
Returnerar JSON:
```json
{
  "puzzleID": "KSE-11360886",
  "puzzleType": "Arrowword_Plus",
  "date": "2026-04-27T00:00:00+02:00",
  "title": "",       ← alltid tom, hämta från getxml istället
  ...
}
```
- `puzzleID: null` om pusslet inte finns/inte är tillgängligt.
- `epochtime` kan sättas till `1` (ignoreras i praktiken).

### getxml (puzzle-data inkl. titel)
```
GET /content/getxml?clientid={clientid}&puzzleid={puzzleid}
```
Returnerar UTF-8 XML med BOM. Relevant data:
```xml
<puzzle id="KSE-..." variation="Arrowword DPG" ...>
  <title>Måndagskrysset</title>
  <byline>Lina Otterdahl</byline>
  ...
</puzzle>
```
- `title` ger publik rubrik (t.ex. "Måndagskrysset").
- `variation` ger pussel-typ (t.ex. "Arrowword DPG", "PuzzleConstruction Arrowword").
- Vissa pussel saknar titel (bildkorsord, Kulturbilagan) - fall back på variation.

### getimage (PNG-bild)
```
GET /content/getimage?clientid={clientid}&puzzleid={puzzleid}
```
Returnerar `image/png`. Storlek varierar: 300 KB - 1,7 MB.

### getsecondimage (kompletterande bild, används av Skillnad-pussel)
```
GET /content/getsecondimage?clientid={clientid}&puzzleid={puzzleid}
```

### getpreviewimage (miniatyrbild)
```
GET /content/getpreviewimage?clientid={clientid}&puzzleid={puzzleid}
```

### Övriga (ej relevanta för hämtning)
- `GET /content/getxml` - full XML inkl. lösning
- `POST /Content/setpuzzlestate` - spara spelläge
- `GET /Content/GetPuzzleState` - hämta spelläge
- `GET /Content/FinishedPuzzle` - markera klart
- `GET /Content/StartedPuzzle` - markera påbörjat
- `GET /content/isvalidword` - ordvalidering
- `GET /Content/GetClientCssJSON?clientid={id}` - CSS-konfig (tom för dnmag)
- `POST https://appservices.keesing.com/hsc` - high scores
- `GET https://appservices.keesing.com/highscores/List` - lista high scores

## Pussel-ID:n och slots

### Slot-format (alias)
```
{gametype}_x{N}_today_
```
Notera det avslutande understrecket - bundlen lägger på det automatiskt.
Utan understrecket fungerar inte API-anropen.

För `dnmag`/`arrowword_plus` finns 9 aktiva slots (2026-04-27, måndag):

| Slot | KSE-ID | Datum | Titel | Variation |
|------|--------|-------|-------|-----------|
| x1 | KSE-11360886 | 2026-04-27 | Måndagskrysset | Arrowword DPG |
| x2 | KSE-11361416 | 2026-04-28 | Tisdagskrysset | Arrowword DPG |
| x3 | KSE-11358388 | 2026-04-22 | Onsdagskrysset | Arrowword DPG |
| x4 | KSE-11365087 | 2026-04-23 | Torsdagskrysset | PuzzleConstruction Arrowword |
| x5 | KSE-11366008 | 2026-04-24 | Nutidskrysset | PuzzleConstruction Arrowword |
| x6 | KSE-11356612 | 2026-04-25 | (tom) | Arrowword Pictorial |
| x7 | KSE-11361364 | 2026-04-25 | Lördagskrysset | PuzzleConstruction Arrowword |
| x8 | KSE-11356338 | 2026-04-26 | (tom) | Arrowword DPG |
| x9 | KSE-11374193 | 2026-04-26 | Söndagskrysset | PuzzleConstruction Arrowword |
| x10+ | - | - | inte tillgänglig | - |

**Rullande fönster:** `_today_`-aliasen ger alltid det senast tillgängliga
pusslet per slot. På en måndag:
- Innevarande veckas måndag (x1), tisdag (x2) är tillgängliga
- Föregående veckas onsdag-söndag (x3-x9) finns kvar
- Ungefär 7-9 dagars bakåtrullning, men inte exakt

**Duplikat-kontroll:** x6 och x7 delade datum (2026-04-25) men hade olika
KSE-ID och varierande titlar - kontrollera alltid KSE-ID för att undvika
dubbellagring.

### Direkta KSE-ID:n
`GetPuzzleInfo` och `getimage` accepterar `puzzleid=KSE-XXXXXXXX` direkt.
Om ett ogiltigt KSE-ID anges returneras ett tomt svar utan puzzleType.

## Backfill

Backfill är **begränsad**. `_today_`-aliasen rör sig framåt i takt med
publiceringen och ger ca 7 dagars bakåtrullning. Det finns ingen känd publik
endpoint för att lista historiska pussel-ID:n.

Strategi för ongoing-insamling:
- Kör dagligen, hämta alla 9 slots
- Kontrollera KSE-ID mot redan sparade - spara bara nya
- Pusslet för "idag" finns alltid under sin respektive dag-slot

## PDF-konvertering

### Variation: Arrowword DPG (x1, x2, x3, x8)

XML-data räcker - ingen bild behövs. Renderaren `render_keesing.py` bygger SVG
från XML och konverterar till PDF via `cairosvg`:

```python
from render_keesing import render_pdf, supports_xml

xml_bytes = requests.get(f"https://web.keesing.com/content/getxml?clientid={cid}&puzzleid={kid}").content
if supports_xml(xml_bytes):
    render_pdf(xml_bytes, output_path)
    # render_pdf(xml_bytes, output_path, debug=True)  # lägger till (x,y)-koordinater i varje ruta
```

Cellstorlek anpassas automatiskt för A4 (~50px för 15-kolumns-grid, ~44px för 17-kolumns).

#### Pilrendering

Pilindikatorerna ritas **inte** i ledtrådsrutan utan i den angränsande svarscellen
(den cell som pilens första riktning pekar mot). Pilen är liten och sitter i hörnet
närmast ledtrådsrutan så att svarsrutan fortfarande är läsbar.

Piltyper och deras semantik:

| Arrow-namn | Första led | Andra led | Placering |
|------------|-----------|-----------|-----------|
| `arrowdownright` | ↓ | → | cellen nedanför |
| `arrowrightdown` | → | ↓ | cellen till höger |
| `arrowupright` | ↑ | → | cellen ovanför |
| `arrow4590rightdown` | ↘ (diagonal) | ↓ | diagonalt nedre-höger |
| `arrow4590downright` | ↘ (diagonal) | → | diagonalt nedre-höger |
| `arrow4590upright` | ↗ (diagonal) | → | diagonalt övre-höger |

Enkla riktningspilar (`arrowdown`, `arrowright` m.fl.) ritas inte - de ger ingen
information utöver vad rutornas layout redan visar.

Första ledets linje börjar halvvägs in i ledtrådsrutan och böjer av inne i svarscellen,
med pilspetsen vid slutet av andra ledet.

### Variation: PuzzleConstruction Arrowword, Arrowword Pictorial (x4, x5, x6, x7, x9)

Saknar ledtrådstexter i XML - kräver getimage:

```python
import img2pdf, requests

png = requests.get(f"https://web.keesing.com/content/getimage?clientid={cid}&puzzleid={kid}").content
pdf = img2pdf.convert(png)
```

`img2pdf` bevarar originalupplösningen utan komprimering. PNG på ~1 MB
ger PDF på liknande storlek (lossless).

## Filnamnskonvention

```
{datum} - {titel}.pdf
```
Exempel: `2026-04-27 - Måndagskrysset.pdf`

Om titel saknas (x6, x8): fall back på variation eller slot-nr.

## Implementationsnoter

- Inget cookie/session-krav för läsoperationer
- Ingen autentisering krävs (publik API)
- `User-Agent`-header rekommenderas men inte obligatorisk
- BOM (`﻿`) i XML-svaret - strip innan parse
- `epochtime`-parametern i GetPuzzleInfo kan sättas till `1` (ignoreras)
