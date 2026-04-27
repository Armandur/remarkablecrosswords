# Todo

Aktuella uppgifter. Färdiga uppgifter flyttas till `TODO_DONE.md`.

## Buggar

- [ ] **Schemaläggaren uppdateras inte vid källändringar**  
  `setup_scheduler` körs bara vid appstart. Sparar man ett nytt schema eller
  lägger till en källa krävs omstart för att ändringen ska aktiveras.
  APScheduler stödjer att lägga till/uppdatera jobb dynamiskt.

## Datamodell

- [ ] **DB-reset och ren datamodell före produktion**  
  Vi är inte i produktion än. Istället för att ackumulera ALTER TABLE-guards:
  nollställ databasen, skriv om `init_db()` med korrekta constraints och
  cascade-regler från start. Komplettera med ett seed-skript som lägger in
  reMarkable-koppling, befintliga ntfy-tjänster och nuvarande källor.  
  Inkluderar: cascade delete (`Source -> Issue -> Crossword`, `Source -> Job`)
  och unique constraint på `(source_id, external_id)` i `issues`-tabellen.

## Design och arkitektur

- [ ] **Modulärt notifieringssystem**  
  Nuvarande ntfy-implementation är hårdkodad i settings-UI. Bygg ett
  register-baserat system likt `SOURCE_KINDS`:
  - Varje notistjänst deklarerar `KIND`, `LABEL` och `CONFIG_FIELDS`
  - Settings-UI renderar formulärfält generiskt från `CONFIG_FIELDS`
  - Ny tjänst = ny fil + rad i registret, inga template-ändringar
  - Gör detta i kombination med DB-rensningen ovan
  
  Planerade implementationer: Discord-webhook (trivial), SMTP, 
  Web Push (kräver VAPID + service worker — eget flöde), Home Assistant.

- [ ] **Blocking subprocess i async-router** *(låg prioritet)*  
  `remarkable_api.py` är `async def` men anropar synkron `subprocess.run`
  via `RmapiClient`. Blockerar FastAPI-händelseloopen under rmapi-anrop.
  Rätta med `asyncio.to_thread(...)` eller `run_in_executor`. Låg praktisk
  påverkan för single-user self-hosted men principiellt fel.

## Infrastruktur

- [ ] **Test-suite** — pytest med unit-tester för sources, remarkable, notifier

- [ ] **CI** — GitHub Actions-workflow är borttagen tillfälligt (kräver workflow-scope).
  Lägg tillbaka när `gh auth refresh -s workflow --hostname github.com` är gjort.
