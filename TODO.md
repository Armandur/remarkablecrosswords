# Todo

Aktuella uppgifter. Färdiga uppgifter flyttas till `TODO_DONE.md`.

## Källor

- [ ] **Tvinga omsynk per källa** - "Tvinga omsynk"-knapp på källdetaljsidan öppnar en modal med två val: (1) hämta om alla utgåvor enligt aktuell config (rensar cache = sätter state till pending), (2) skriv över befintliga filer på reMarkable. Knappen ska fungera som en kombinerad "rensa cache + kör + overwrite" utan att användaren behöver pilla i inställningar.


## Design och arkitektur


- [ ] **Bryt ut keesing-modulen som eget repo** - likt korsordio är `keesing/` avsedd att
  på sikt bli ett fristående paket. Flytta till eget repo, publicera på PyPI eller
  installera via git-URL i pyproject.toml.

## Infrastruktur

- [ ] **Test-suite** — pytest med unit-tester för sources, remarkable, notifier

- [ ] **CI** — GitHub Actions-workflow är borttagen tillfälligt (kräver workflow-scope).
  Lägg tillbaka när `gh auth refresh -s workflow --hostname github.com` är gjort.
