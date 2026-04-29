# Todo

Aktuella uppgifter. Färdiga uppgifter flyttas till `TODO_DONE.md`.

## Källor

- [ ] **Tvinga omsynk per källa** - "Tvinga omsynk"-knapp på källdetaljsidan öppnar en modal med två val: (1) hämta om alla utgåvor enligt aktuell config (rensar cache = sätter state till pending), (2) skriv över befintliga filer på reMarkable. Knappen ska fungera som en kombinerad "rensa cache + kör + overwrite" utan att användaren behöver pilla i inställningar.


## Keesing-modulen - nya speltyper

Alla renderare ska ligga i `keesing/`-modulen och **inte** i webapp:en.
API-åtkomst sker via befintliga fetch-funktioner (GetPuzzleInfo + getxml).

- [ ] **Vanligt korsord (`crossword`)** - PRIORITET
  Rendera till PDF från XML: grid med svarsceller och svarta rutor,
  cellnumrering för ordstart, separat kluelist (vågrätt/lodrätt) under grid.
  Se spec.md för XML-struktur.

- [ ] **Sudoku** - efter korsord
  Rendera 9x9-grid till PDF: tjocka kanter runt 3x3-boxar, tunna inre linjer,
  förifyllda siffror i fetstil. Giveaway-celler med `giveaway="1"`.

- [ ] **Tectonic** - efter korsord
  Rendera grid till PDF: regionfärgad bakgrund (ARGB från `<color>`),
  tjocka kanter mellan regioner, tunna inom region.
  Förifyllda siffror i fetstil.

## Design och arkitektur


- [ ] **Bryt ut keesing-modulen som eget repo** - likt korsordio är `keesing/` avsedd att
  på sikt bli ett fristående paket. Flytta till eget repo, publicera på PyPI eller
  installera via git-URL i pyproject.toml.

## Infrastruktur

- [ ] **Test-suite** — pytest med unit-tester för sources, remarkable, notifier

- [ ] **CI** — GitHub Actions-workflow är borttagen tillfälligt (kräver workflow-scope).
  Lägg tillbaka när `gh auth refresh -s workflow --hostname github.com` är gjort.
