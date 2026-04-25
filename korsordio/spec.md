# korsord.io – reverse-engineered spec

Löpande anteckningar baserat på inspektion av nätverkstrafik och
`.crossword`-filer för Sverigekrysset. Allt nedan är observerat genom
faktiska anrop, inte officiellt dokumenterat. Påståenden markerade
**(antagande)** är inte verifierade och kan vara fel.

## URL-struktur

| Resurs                        | URL                                                          |
| ----------------------------- | ------------------------------------------------------------ |
| Översikt per titel            | `https://app.korsord.io/g/<slug>/`                           |
| Enskilt kryss (HTML-klient)   | `https://app.korsord.io/c/<slug>-<vecka>-<år>/`              |
| Korsordsdata (JSON)           | `https://app.korsord.io/media/<uuid>.crossword`              |
| Bilder (preview/illustration) | `https://app.korsord.io/media/<uuid>.jpg`                    |

`<år>` är tvåsiffrigt (`26` = 2026). `<vecka>` har inget zero-padding.
`<slug>` är `sverigekrysset` eller `miljonkrysset` — det är de enda
titlar som publiceras på korsord.io idag.

### Hitta UUID från en kryss-URL

UUID:t bäddas in direkt i HTML:en på `/c/<slug>-<v>-<år>/` i
`WX.FetchCrossword(...)`-anropet:

```html
WX.FetchCrossword("https://app.korsord.io/media/<uuid>.crossword").then(...)
```

Regex: `WX\.FetchCrossword\("([^"]+\.crossword)"\)`.

### Översiktssidan

`/g/<slug>/` är en HTML-lista med länkar `/c/<slug>-<v>-<år>/` för
publicerade kryss. Just nu syns vecka 1–17 från 2026 och vecka 17–52
från 2025.

### Inloggning

Ingen autentisering krävs för att nå HTML eller `.crossword`-JSON.
Inga cookies, ingen session, ingen API-nyckel.

## .crossword-fil

Filändelsen är `.crossword` men innehållet är `application/json`.
Storlek ~2 MB för Sverigekrysset (drivs upp av base64-inbäddade
illustrationer).

### Top-level

```json
{
  "identifier": "<UUID i versaler>",
  "name": "SK_260420$5067",
  "type": "crossword",
  "locale": {"current": 0, "identifier": "sv_SE"},
  "rows": 25,
  "cols": 25,
  "difficulty": "unknown",
  "copyright": {"corner": "bottom-right", "offset": {...}, "text": ""},
  "colors": {...},
  "nodes":  [...],
  "leads":  [...],
  "arrows": [...]
}
```

`name`-format **(antagande):** `SK_<YYMMDD>$<intern-id>` där
`<YYMMDD>` är publiceringsdatum.

### `colors`

Färger angivna i CMYK för tryck. Web-klienten verkar ignorera dem
(allt visas vitt) — i de flesta render-scenarier kan de ignoreras
till förmån för en vit grund.

```json
"colors": {
  "caption":    {"cmyk": {"key": 0, "cyan": 0, "magenta": 0, "yellow": 50}},
  "sms":        {"cmyk": {"key": 0, "cyan": 20, "magenta": 0, "yellow": 0}},
  "empty-lead": {"cmyk": {"key": 0, "cyan": 0, "magenta": 10, "yellow": 0}},
  "solution":   {"cmyk": {"key": 100, "cyan": 0, "magenta": 0, "yellow": 0}},
  "border":     {...}
}
```

- `sms` är färgen för lösningsrutorna (i tryck), webb-klienten visar
  dem ljust turkosa **(antagande)**.

### `nodes`

En post per **bokstavsruta** (där användaren skriver). Alla har
`type: "letter"`. Genererad lista i Sverigekrysset 17–26: 306 noder.

```json
{
  "position": {"x": 11, "y": 0},
  "type": "letter",
  "character": "",     // tom; fylls av användarens lösning
  "smsIndex": 1,       // OPTIONAL: lösningsruta nr 1 (1..N), läses i ordning
  "color": "caption"   // OPTIONAL: kosmetisk markering, "caption" eller liknande
}
```

- `smsIndex` (1-indexerad, 6 st i sverigekrysset 17-26) markerar
  **SMS-svarsrutorna** — kortvarianten av lösningskoden som man
  skickar in via SMS för att vinna lotter. Webb-klienten har en
  separat svarsruta nederst där bokstäverna samlas i ordning.
  Renderas med ljust turkos bakgrund (`#b8e6e6`) + index-siffra i
  hörnet.
- `color: "caption"` markerar **lösningsmeningens rutor** — den
  längre meningen som bildas av bokstäver i grid:et i läsordning,
  uppdelad i ord av `trailing`-pilar (ord-separatorer). 51 noder i
  sverigekrysset 17-26. Renderas med ljust gul bakgrund (`#fff4a0`),
  matchar webb-klientens utseende.
- Övriga `color`-värden förekommer ej i exempel-data.

### `leads`

Ledtrådar: textledtrådar, bildledtrådar och overlays.

#### Gemensamma fält

```json
{
  "identifier": "<UUID>",
  "type": "string" | "image" | "overlay",
  "position": {"x": <int>, "y": <int|float>},
  "size":     {"width": <int|float>, "height": <int|float>}
}
```

`position.y` kan vara fraktionerad (t.ex. `15.28`) när en cell delas
mellan flera leads. `size.width`/`height` mäts i celler.

#### `type: "string"` (textledtråd)

```json
{
  "type": "string",
  "position": {...},
  "size": {...},
  "clue": {
    "text": "FART-\nMÄTARE\nTILL\nSJÖSS",
    "start": {"x": 21, "y": 1},   // OPTIONAL: var ordet börjar
    "direction": "horizontal"     // OPTIONAL: ordets riktning
  }
}
```

- `clue.text` använder `\n` för radbrytning. **Web-klienten kan
  bryta ytterligare vid blanksteg om en rad inte får plats vid
  rimlig fontstorlek.** Exempel (miljonkrysset 17-26 cell 20,9):
  data har `"BLIR\nHALVNAK-\nEN MED LESS"`, men renderaren bryter
  "EN MED LESS" → "EN MED" + "LESS" för att slippa krympa fonten.
  Renderingsstrategin bör därför ha en soft-wrap som bryter vid
  blanksteg när font_size annars hamnar under en threshold.
- `clue.start` och `clue.direction` saknas på vissa leads, t.ex.
  enskilda bokstavsledtrådar typ "SYRE → O".

#### Split-celler (delade ledtrådar)

Två leads kan dela samma cell vertikalt. Exempel — cell (24, 15):

```json
[
  {"position": {"x": 24, "y": 15},    "size": {"height": 0.28, "width": 1}, "clue": {"text": "SYRE"}},
  {"position": {"x": 24, "y": 15.28}, "size": {"height": 0.72, "width": 1}, "clue": {"text": "MYCKET\nLÅNG\nTID", ...}}
]
```

Höjderna summerar alltid till 1. Vanliga split-höjder: 0.5/0.5,
0.28/0.72.

#### `type: "image"` (bildledtråd)

```json
{
  "type": "image",
  "size": {"height": 8, "width": 11},
  "position": {"x": 0, "y": 17},
  "image": {
    "border": true,
    "name": "QFWYVQVCVIKC.jpg",
    "data": "data:image/jpeg;base64,/9j/4AAQ..."
  }
}
```

Bilder ligger som **base64-inbäddade JPEG:er direkt i JSON:en**. Det
förklarar filstorlekar runt 2 MB. Inga separata `media/<uuid>.jpg`-
anrop behövs för rendering. (Den lågupplösta `.jpg`-resursen som
syns i devtools är troligen en thumbnail för översiktssidan.)

#### `type: "overlay"` (markering)

```json
{
  "type": "overlay",
  "position": {...},
  "size": {...},
  "overlay": {
    "type": "character",
    "offset": {"x": 0, "y": 0},
    "text": ""
  }
}
```

Sällsynt — bara 1 förekomst i Sverigekrysset 17–26. Funktion
oklar **(antagande:** för förifyllda bokstäver eller manuella
markeringar).

### `arrows`

Pilar är **kosmetiska** indikatorer som visar var ord börjar och hur
de löper. Knyts inte explicit till en `lead.identifier` — placeringen
bestämmer relationen.

```json
{
  "position": {"x": <int>, "y": <int>},
  "type":   "horizontal-left" | "horizontal-right" | "vertical-down"
          | "horizontal-down-right" | "horizontal-up-right"
          | "vertical-right-down"   | "vertical-left-down"
          | "trailing",
  "edge":   "left" | "right" | "top" | "bottom",
  "anchor": "leading" | "middle" | "trailing" | null,
  "offset": <float i [0,1]> | null
}
```

#### Position och placering

- **`position`** är cell-koordinater. För alla typer **utom**
  `trailing` ligger `position` på en **ledtrådsruta** (en cell som
  innehåller minst ett `string`-lead). `trailing`-pilar ligger på
  **bokstavsrutor** (en cell med en `node`).
- **`edge`** anger vilken cellkant pilen ankras på. För pilar på
  ledtrådsrutor är detta kanten som *vetter mot bokstavsrutan* dit
  pilen pekar.
- **`anchor`** styr position längs kanten. **Korrekt tolkning:**
  matcha pilen mot dess associerade lead i cellen — `leading` =
  *första* leaden (lägst y eller x), `trailing` = *sista*. Pilens
  position blir mitten av matched leadens egen rektangel, vilket
  fungerar för både 0.5/0.5- och 0.28/0.72-splits.

  Förenklad fallback (när cellen inte är splittad eller leads inte
  hittas):

  | anchor   | fraktion |
  | -------- | -------- |
  | leading  | 0.25     |
  | middle   | 0.5      |
  | trailing | 0.75     |

  Men dessa konstanter är fel för 0.28/0.72-splits — då hamnar
  `leading=0.25` *under* den övre leadens nedre kant. Använd
  alltid lead-matching först.

- **`offset`** (0..1) förekommer sällan — bara 1 i exempelkrysset.
  Tolkas **inte** som direkt y-position (det blev fel för SYRE-fallet
  där offset=0.06 men leadens mittpunkt är 0.14). I stället används
  offset för att identifiera *vilken* lead i en split-cell pilen
  refererar till — vi tar leadens egen mittpunkt som pilposition.

#### Form (tolkning av `type`)

| type                      | form                                             |
| ------------------------- | ------------------------------------------------ |
| `horizontal-left`         | rak triangel som pekar vänster (utåt från kant)  |
| `horizontal-right`        | rak triangel som pekar höger                     |
| `vertical-down`           | rak triangel som pekar ner                       |
| `horizontal-down-right`   | L-form: kort arm ner från kanten, böj höger     |
| `horizontal-up-right`     | L-form: kort arm upp från kanten, böj höger     |
| `vertical-right-down`     | L-form: kort arm höger från kanten, böj ner     |
| `vertical-left-down`      | L-form: kort arm vänster från kanten, böj ner   |
| `trailing`                | hög smal triangel (se nedan) — ord-separator    |

**(antagande)** Type-prefixet ("horizontal" / "vertical") indikerar
första armens orientering, suffixet ("X-down/up/right/left") slut-
riktningen. Inte fullt verifierat för alla kombinationer.

Raka pilar ska ritas så små att de inte sträcker sig in i bokstavs-
rutan (anv:s krav: man måste kunna skriva utan att pilen är ivägen).
L-pilar ska hållas så nära ledtrådens kant som möjligt av samma
anledning.

#### `trailing`-pilen i detalj

- Verifierad funktion: **ord-separator i lösningsmeningen**.
  Lösningsmeningen bildas av `color: "caption"`-noderna lästa i
  rad-/kolumnordning. När meningen består av flera ord placeras
  en `trailing`-pil mellan grupperna för att markera mellanslag.
  Pilen själv ligger på en bokstavsruta (caption- eller vanlig nod)
  i meningen.
- Detta gäller **inte** SMS-svaret (`smsIndex`-noderna) som är ett
  separat och kortare svar.
- Position: `arrow.position` är på node N med `edge: "right"`, men
  pilen ska **renderas i cell N+1** — alltså en kolumn till höger.
- Form: hög smal triangel, basen = hela vänsterkanten av render-
  cellen, spetsen sticker in 1/4 av cellbredden, vertikalt centrerad,
  pekar höger.
- `anchor` och `offset` är `null` för dessa pilar i exempelkrysset.

#### Anchor-fraktion: split vs hel cell

För **split-celler** (2+ leads i samma cell) matchas pilen mot
specifik lead via anchor (leading/trailing) eller offset → leadens
egen mittpunkt blir pilens position längs kanten.

För **icke-splittade celler** (1 lead) tolkas anchor som fast
fraktion av kanten:

| anchor   | fraktion |
| -------- | -------- |
| leading  | 0.20     |
| middle   | 0.50     |
| trailing | 0.80     |

`leading=0.20` placerar pilen nära kantens topp/vänster, `trailing=0.80`
nära dess botten/höger — vilket gör att L-pilarnas slutarm hamnar i
hörn (och kan överlappa intilliggande cell, vilket korsord.io's
egen renderare också gör).

#### Olösta detaljer

- Om `vertical-up` finns (har inte sett i exempel-data).
- Hur `overlay`-leads med `text != ""` ska renderas.

## `name`-fältet

Format: `<PREFIX>_<YYMMDD>$<intern-id>` där prefixet identifierar
titeln:

- `SK_` — Sverigekrysset (`SK_260420$5067` för v17 2026,
  publicerad 2026-04-20)
- `MK_` — Miljonkrysset (`MK_260420$1631` för v17 2026)

Sverigekrysset och Miljonkrysset är de enda titlar som publiceras
på korsord.io idag.

## CMYK → RGB-konvertering

Standardformel utan ICC-profil:

```
R = 255 * (1 - C) * (1 - K)
G = 255 * (1 - M) * (1 - K)
B = 255 * (1 - Y) * (1 - K)
```

CMYK→RGB-konverteringen är sällan relevant i praktiken — webb-
klienten ignorerar dem och renderar med fasta accent-färger.
Standardval som matchar webb-klientens utseende:

- SMS-svarsrutor (`smsIndex` ≠ null): ljust turkos `#b8e6e6`
- Lösningsmenings-rutor (`color: "caption"`): ljust gul `#fff4a0`
- Övrigt: vit bakgrund, svart 1 px-border
