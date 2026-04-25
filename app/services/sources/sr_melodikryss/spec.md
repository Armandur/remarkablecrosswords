# Källa: SR Melodikryss

Laddar ned SR:s Melodikryss som publiceras veckovis av Sveriges Radio P4.

## URL-struktur

```
https://sr.korsord.se/images/kryss/kryss{YYYY}w{W}.pdf
```

- `YYYY` — fyrsiffrigt år (t.ex. `2026`)
- `W` — veckonummer utan ledande nolla (t.ex. `17`, inte `017`)

Exempel: `https://sr.korsord.se/images/kryss/kryss2026w17.pdf`

Äldsta kända nummer: `kryss2006w1.pdf`.

## Autentisering

Ingen. Direkt HTTP-nedladdning utan cookies.

## PDF-format

Färdig PDF, genererad av iTextSharp 5.5.13. Ingen lokal rendering behövs.

| Egenskap | Värde |
|---|---|
| Sidstorlek | 490 × 540 pts (~17 × 19 cm) |
| Filstorlek | ~1,8–2,2 KB |
| Sidor | 1 |
| Innehåll | Vektorgrafik + text (digitalt, ingen skanning) |

## `config_json`-fält

Inga källspecifika fält. Konfigureras bara med gemensamma fält
(undermapp, overwrite, cron-schema).

## `external_id`-format

`{year}w{week}`, t.ex. `2026w17`.

## Publiceringscykel

Veckovis, lördagar (sänds i P4 lördag kl. 10:03). Inlämning senast
onsdag efterföljande vecka. Rekommenderat cron-schema: `30 8 * * 6`.

## Tillgänglighetsdetektering

`list_available` kontrollerar de 8 senaste veckorna med HEAD-anrop och
returnerar de 4 senaste som svarar med HTTP 200 och `Content-Type: application/pdf`.
Ingen katalog-API finns — probing är enda sättet att hitta tillgängliga nummer.
