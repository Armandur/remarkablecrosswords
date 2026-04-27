# Todo

Aktuella uppgifter. Färdiga uppgifter flyttas till `TODO_DONE.md`.

## Källor

- [ ] **Regelbaserad sidurvalsmotor för Prenly**  
  Lägg till `page_rules` i `config_json` som ett alternativ till `extraction_pages` och
  `crossword_marker_text`. En sida inkluderas om den matchar definierade villkor.  
  Regeltyper: `text_contains`, `min_images`, `min_image_pixels`, `max_image_pixels`.  
  Match-läge: `any` (valfritt villkor matchar) eller `all` (alla villkor måste matcha).  
  Testat mot DN kulturbilaga (title 2359) - sida med korsord identifieras via `text_contains("korsord")`.

- [ ] **playpuzzlesonline.com som egen källtyp**  
  DN och Söndagskrysset tillgängliga via `https://playpuzzlesonline.com/dn/` med URL-parametrarna
  `gametype=arrowword_plus` och `puzzleid=arrowword_plus_x1_today` (vardag) resp. `x9_today` (söndag).
  Gamla utgåvor har unika ID:n (t.ex. `KSE-11361364`) - `_today`-länkarna är inte permanenta.
  Kräver JS-rendering (obscura) likt korsord.io. Implementera som ny `SourceFetcher`-klass.

## Design och arkitektur

## Infrastruktur

- [ ] **Test-suite** — pytest med unit-tester för sources, remarkable, notifier

- [ ] **CI** — GitHub Actions-workflow är borttagen tillfälligt (kräver workflow-scope).
  Lägg tillbaka när `gh auth refresh -s workflow --hostname github.com` är gjort.
