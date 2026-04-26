# Todo

Aktuella uppgifter. Färdiga uppgifter flyttas till `TODO_DONE.md`.

## Öppna uppgifter

- [ ] **Inställningen "Skriv över befintlig fil på reMarkable vid omsynk" ska vara generell**  
  Just nu finns den bara per korsord.io-källa. Flytta till global källinställning
  som gäller alla källtyper.

- [ ] **Fler notifierare** — Discord-webhook (trivial), Web Push, Home Assistant

- [ ] **Test-suite** — pytest med unit-tester för sources, remarkable, notifier

- [ ] **CI** — GitHub Actions-workflow är borttagen tillfälligt (kräver workflow-scope).
  Lägg tillbaka när `gh auth refresh -s workflow --hostname github.com` är gjort.
