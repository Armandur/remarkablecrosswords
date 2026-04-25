# Källa: Yippie Härnösand [Prenly]

Hämtar korsordet ur Yippie Härnösands lokaltidning via Prenly-plattformen.
Bygger på [`prenly`-källan](../prenly/spec.md) — se den för API-detaljer och autentiseringsflöde.

## Korsordets placering

Korsordsidan identifieras via texten `SE KRYSSET` i sidans extraherade text (pypdf).
Sidnumret varierar mellan nummer.

## Layoutvarianter

Tre olika layouttyper förekommer. `YippieHarnosandFetcher` detekterar dem automatiskt.

### Gammal layout (höjdkvot 40–65 %)

Korsordets bild är inbäddad som en XObject-bild i den övre halvan av en
redaktionssida. Identifieras genom att `_find_crossword_image` hittar en bild
vars höjd är 40–65 % av sidans höjd med bildcentrum i övre halvan (y > sidmitten).

**Hantering:**
1. Korsordsbilden extraheras ur innehållsströmmen — all annan grafik och text tas bort.
2. Nästa sida i numret hämtas och behandlas på samma sätt.
3. De två bilderna slås ihop sida vid sida till en enda PDF-sida med `_merge_side_by_side`.

### Ny layout, bild-korsord (höjdkvot > 65 %)

Korsordet täcker nästan hela sidan som en eller flera XObject-bilder.
Sidan har ett synligt overlay med texten "SE KRYSSET I PAPPERSTIDNINGEN!".

**Hantering** (tvåstegsprocess):
1. **Steg 1 – GS-overlay:** `_find_overlay_gs_names` detekterar GS-tillstånd med
   `/ca < 1.0` (fyllningsopacitet) **eller** `/CA < 1.0` (strokopacitet). Dessa
   GS-tillstånd används i `q...Q`-block som ritar helsidestäckande transparenta
   bilder (t.ex. `Im9`, `Im11`). `_remove_overlay_from_page` tar bort dessa block.
2. **Steg 2 – SE KRYSSET-text:** Om "SE KRYSSET" fortfarande finns i sidan efter
   steg 1 (texten kan ligga i ett separat BT-block utanför GS-blocket), hittas och
   tas det exakta BT-blocket bort via `_remove_marker_text_block` (trial-removal).

### Kampanjsida / placeholder

Hela sidan är inlindad i ett GS-overlay som täcker >80 % av alla instruktioner.
Detekteras av `_is_full_page_overlay`. Kastar `NoCrosswordError` — numret hoppa.

## Overlay-detektionslogik

`_find_overlay_gs_names` (Yippie-specifik) skiljer sig från den globala
`_find_semi_transparent_gs_names` genom att även kontrollera `/CA` (strok-opacity).
Detta fångar overlay-bilder som ritas med `Do` i ett `q gs/GS_x cm Do Q`-block
där GS-tillståndet markerar bilden som ett overlay via stroke-opacity (observerat
värde: 0.960007).

## `_remove_marker_text_block`

Tar bort exakt de BT/ET-block vars borttagning gör att "SE KRYSSET" försvinner.
Testar varje BT-block individuellt (trial-removal): skapar ett temporärt PDF,
kontrollerar med pypdf om markören fortfarande finns — om inte, markeras blocket
för borttagning. Alla övriga block (bilder, banor, övrig text) bevaras oförändrade.

## `config_json`-fält

| Fält | Typ | Beskrivning |
|---|---|---|
| `site` | string | `https://tidning.yippieharnosand.se` |
| `textalk_auth` | string | API-nyckel (`X-Textalk-Content-Client-Authorize`) |
| `auth` | string | Bearer-token |
| `title_id` | string | `3217` |
| `cdn` | string | (valfri) CDN-URL, default `https://mediacdn.prenly.com` |
| `backfill_limit` | int | Antal nummer att hämta vid listning (ärvs från Prenly) |

## `external_id`-format

Prenlys `uid` för numret (heltalssträng), t.ex. `2049410`.

## Publiceringscykel

Månadsvis (lokalpress). Rekommenderat cron-schema: `0 9 26 * *` (kl 09:00 den 26:e varje månad).
