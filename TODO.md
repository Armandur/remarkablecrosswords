# Todo

Aktuella uppgifter. Färdiga uppgifter flyttas till `TODO_DONE.md`.

## Källor

## Design och arkitektur

- [ ] **Automatisk PDF-rotation** - korsord som passar bättre i liggande format (t.ex. bredare än höga) bör roteras 90° innan synk till reMarkable, eftersom det inte går att rotera filer på enheten. Lägg till valfritt `rotate` i Source-config eller identifiera automatiskt baserat på sidmått.

- [ ] **Bryt ut keesing-modulen som eget repo** - likt korsordio är `keesing/` avsedd att
  på sikt bli ett fristående paket. Flytta till eget repo, publicera på PyPI eller
  installera via git-URL i pyproject.toml.

## Infrastruktur

- [ ] **Test-suite** — pytest med unit-tester för sources, remarkable, notifier

- [ ] **CI** — GitHub Actions-workflow är borttagen tillfälligt (kräver workflow-scope).
  Lägg tillbaka när `gh auth refresh -s workflow --hostname github.com` är gjort.
