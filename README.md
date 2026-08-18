# flight-watch

SYD → UK Christmas trip search. Same pattern as ai-digest: scheduled GitHub Actions
job, no always-on machine needed.

## Status: core logic built and tested

`config.py` has every parameter agreed on. `search.py` has real Duffel API calls,
tested against realistic mock offers covering the cases that actually matter:

- ✅ Excludes itineraries transiting Doha/Dubai/Abu Dhabi/Sharjah
- ✅ Excludes mainland Chinese carriers **even as the operating carrier on a
  QF-marketed codeshare** — this was the main risk called out earlier in the
  build, and it's now covered by a passing test
- ✅ Applies the 25% Qantas discount only when every segment is genuinely
  QF-*operated* — a QF-marketed/Cathay-operated itinerary correctly stays allowed
  but does NOT get the discount
- ✅ Istanbul/Turkish Airlines confirmed NOT excluded

Not yet done: email/notification delivery, the return-leg fallback fare, GitHub
Actions scheduling.

## Why Duffel, not Amadeus

Amadeus's self-service portal was decommissioned 17 July 2026 — existing keys are
dead, and the only path left is their Enterprise tier, which needs IATA/ARC
accreditation. Duffel is the direct self-service replacement: real signup, no
accreditation, structured fare data.

**Cost:** search is free up to a 1,500:1 search-to-book ratio. This project never
books through the API (booking is manual, or via staff travel), so it stays free
in practice. Booking would cost $3/order if that ever changed.

**Sandbox vs live:** whichever key you generate in the Duffel dashboard determines
sandbox (fake data, safe for testing) or live (real fares). Same code either way —
just swap the `DUFFEL_API_KEY` value.

## Setup checklist

- [ ] Duffel account — duffel.com, generate a test (sandbox) API key first
- [ ] `pip install duffel-api` (already in requirements.txt)
- [ ] `export DUFFEL_API_KEY=...` locally, run `python search.py`, confirm it
      returns sandbox offers without crashing
- [ ] Swap to a live key once happy — same code, real fares
- [ ] Small separate script for the return-leg fallback fare (standby backup)
- [ ] GitHub Actions workflow — daily cron, DUFFEL_API_KEY as a repo secret,
      same pattern as ai-digest
- [ ] Decide notification channel — email, same as ai-digest, or something else

## Why every result shows full routing, not just price

An itinerary that silently transits through an excluded hub, or gets a discount
it shouldn't via a codeshare, is the failure mode worth guarding against by
design — so the report always shows the actual routing and operating carriers,
not just "passed the filter."

