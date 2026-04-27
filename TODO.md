# Todo

Aktuella uppgifter. Färdiga uppgifter flyttas till `TODO_DONE.md`.

## Buggar

- [ ] **Notifieringshändelser ignoreras i pipeline**  
  `run_pipeline_for_source` anropar `get_notifiers(db)` utan `event=`-argument.
  Alla aktiva notifierare triggas oavsett konfigurerade händelser — bryter
  händelsefiltret vi byggt. Ska använda t.ex. `get_notifiers(db, event="sync_ok")`.

- [ ] **Schemaläggaren uppdateras inte vid källändringar**  
  `setup_scheduler` körs bara vid appstart. Sparar man ett nytt schema eller
  lägger till en källa krävs omstart för att ändringen ska aktiveras.
  APScheduler stödjer att lägga till/uppdatera jobb dynamiskt.

- [ ] **`datetime.utcnow()` föråldrad**  
  Används på flera ställen i `scheduler.py` och `database.py`. Ersätt med
  `datetime.datetime.now(datetime.UTC)` (Python 3.12+).

## Datamodell

- [ ] **Saknad cascade delete**  
  `Source → Issue → Crossword` och `Source → Job` saknar `ondelete="CASCADE"`.
  Raderar man en Source lämnas föräldralösa rader i databasen. Hanteras
  enklast som en del av DB-rensningen nedan.

- [ ] **Saknad unique constraint på `(source_id, external_id)`**  
  `issues`-tabellen kan få dubbletter vid dubbla körningar. Lägg till
  `UniqueConstraint("source_id", "external_id")` på `Issue`-modellen.

- [ ] **DB-reset och ren datamodell före produktion**  
  Vi är inte i produktion än. Istället för att ackumulera ALTER TABLE-guards:
  nollställ databasen, skriv om `init_db()` med korrekta constraints och
  cascade-regler från start. Komplettera med ett seed-skript som lägger in
  reMarkable-koppling, befintliga ntfy-tjänster och nuvarande källor.

## Prestanda

- [ ] **N+1-query i `clear_source_cache`**  
  `app/routes/sources.py` gör ett extra DB-anrop per issue för att hämta
  dess crosswords. Optimera med en join eller `IN`-klausul.

## Säkerhet

- [ ] **CSRF saknas på `/crosswords/{id}/sync` och `/crosswords/{id}/delete`**  
  Dessa POST-endpoints saknar `CsrfProtect`-beroendet. Lägre praktisk risk
  (AJAX-anrop, ingen CORS konfigurerad) men bör åtgärdas för konsekvens.

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
