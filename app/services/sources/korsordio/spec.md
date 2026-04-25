# Källa: korsord.io

Hämtar och renderar korsord från [app.korsord.io](https://app.korsord.io) —
primärt Sverigekrysset och Miljonkrysset.

## URL-struktur

| Syfte | URL |
|---|---|
| Lista tillgängliga nummer | `https://app.korsord.io/g/{slug}/` |
| Hämta korsords-JSON | `https://app.korsord.io/api/crossword/{slug}-{week}-{year}` (internt i korsordio-modulen) |

Länkarna `/c/{slug}-{week}-{year}/` extraheras ur HTML-sidan med regex.

## Autentisering

Ingen. Allt publikt tillgängligt utan cookies.

## Datakälla

Hämtar `.crossword`-JSON (proprietärt format dokumenterat i `korsordio/spec.md`).
PDF:en renderas lokalt av `korsordio`-modulen via CairoSVG — ingen headless-webbläsare behövs.

## `config_json`-fält

| Fält | Typ | Default | Beskrivning |
|---|---|---|---|
| `slug` | string | — | Korsordets identifierare, t.ex. `sverigekrysset` eller `miljonkrysset` |
| `sms_boxes` | bool | `true` | Rad med SMS-svarsrutor (lösningskod) under krysset |
| `fetch_competition` | bool | `true` | Hämta och rendera tävlingsinfo (Tävla-modal) |
| `overwrite` | bool | `false` | Skriv över befintlig fil på reMarkable vid omsynk (`rmapi put --force`) |

## `external_id`-format

`{week}-{year}` med kortår, t.ex. `17-26` för vecka 17 år 2026.
Matchar länkstrukturen på korsord.io.

## Publiceringscykel

Veckovis, måndagar. Rekommenderat cron-schema: `30 6 * * 1`.

## Kända begränsningar

- `list_available` hämtar max 4 senaste nummer genom att scrapa listan av `/c/`-länkar.
- `fetch_competition_info` kan misslyckas tyst om tävlingsinformationen inte finns (t.ex. utanför tävlingsperiod) — hanteras med `try/except`.
