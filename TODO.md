# Todo

Aktuella uppgifter. Färdiga uppgifter flyttas till `TODO_DONE.md`.

## Källor

## Keesing-modulen - nya speltyper

Alla renderare ska ligga i `keesing/`-modulen och **inte** i webapp:en.
API-åtkomst sker via befintliga fetch-funktioner (GetPuzzleInfo + getxml).

- [ ] **Sudoku** - PRIORITET

- [ ] **Sudoku** - PRIORITET
  Rendera 9x9-grid till PDF: tjocka kanter runt 3x3-boxar, tunna inre linjer,
  förifyllda siffror i fetstil. Giveaway-celler med `giveaway="1"`.

- [ ] **Tectonic** - efter korsord
  Rendera grid till PDF: regionfärgad bakgrund (ARGB från `<color>`),
  tjocka kanter mellan regioner, tunna inom region.
  Förifyllda siffror i fetstil.

## Rikare metadata i filnamnsättaren

- [ ] **Generellt extra-fält-system för filnamnsmallar** - Medel prio

  Varje källtyp ska kunna exponera källspecifika metadatafält som användaren kan
  använda i filnamnsmallen via syntaxen `{extra:FÄLTNAMN}`.

  Design:
  - `ExternalIssue` får ett `extra: dict[str, str]`-fält (default tom dict)
  - `render_filename` i `base.py` parsar `{extra:FÄLTNAMN}` och slår upp i `extra`
  - `SourceFetcher`-protokollet utökas med en valfri metod `extra_fields() -> list[dict]`
    som returnerar en lista med metadata om tillgängliga fält, t.ex.:
    `[{"key": "series", "label": "Serie", "example": "Klassikern"}, ...]`
  - UI:t anropar detta vid redigering av filnamnsmall och visar tillgängliga fält
    som klickbara chips (infogar `{extra:FÄLTNAMN}` i templatefältet)

  Keesing-specifika fält att exponera (hämtas ur getxml `<puzzle>`-attribut):
  - `series` - parsad ur `ipsrecipe` (t.ex. "Klassikern" ur `DN_CW1313_Klassikern_Intern_NoRW`)
  - `difficulty` - svårighetsgrad som siffra (1-7), relevant för sudoku/tectonic
  - `slot` - slot-identifierare (t.ex. "x6")
  - `byline` - upphovsmannens namn

  Potentiellt värde: Keesing-korsord kan automatnamnas "Klassikern 2026-04-29" eller
  "Söndagskrysset 2026-04-27" utan manuell konfiguration. Mönstret är generellt och
  funkar för framtida källtyper med egna metadatafält.

## Design och arkitektur


- [ ] **Bryt ut keesing-modulen som eget repo** - likt korsordio är `keesing/` avsedd att
  på sikt bli ett fristående paket. Flytta till eget repo, publicera på PyPI eller
  installera via git-URL i pyproject.toml.

## Infrastruktur

- [ ] **Test-suite** — pytest med unit-tester för sources, remarkable, notifier

- [ ] **CI** — GitHub Actions-workflow är borttagen tillfälligt (kräver workflow-scope).
  Lägg tillbaka när `gh auth refresh -s workflow --hostname github.com` är gjort.
