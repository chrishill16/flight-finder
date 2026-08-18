# flight-watch

SYD → UK Christmas trip search. Same pattern as ai-digest: scheduled GitHub Actions
job, no always-on machine needed.

## Status: core logic built, tested, and fixed once already

`config.py` has every parameter agreed on. `search.py` talks to Duffel's REST API
directly (not their Python SDK — see below for why), tested against realistic mock
offers covering the cases that actually matter:

- ✅ Excludes itineraries transiting Doha/Dubai/Abu Dhabi/Sharjah
- ✅ Excludes mainland Chinese carriers **even as the operating carrier on a
  QF-marketed codeshare**
- ✅ Applies the 25% Qantas discount only when every segment is genuinely
  QF-*operated* — a QF-marketed/Cathay-operated itinerary correctly stays allowed
  but does NOT get the discount
- ✅ Istanbul/Turkish Airlines confirmed NOT excluded
- ✅ Shows whatever currency Duffel actually returns rather than assuming AUD

Not yet done: email/notification delivery, the return-leg fallback fare.
Scheduling is already built (`.github/workflows/flight-watch.yml`).

## Why raw `requests`, not the `duffel-api` SDK

First attempt used the `duffel-api` PyPI package. It failed on the real GitHub
Actions run with `Unsupported version: v1` — Duffel moved their API to v2, and the
SDK (last published a while back) still hardcodes v1 and parses responses using
v1's field names. Rather than depend on someone else's library staying current,
`search.py` now calls `api.duffel.com` directly with `requests` and a
`Duffel-Version: v2` header, parsing the JSON as plain dicts. Fewer moving parts,
and this can't silently break again the same way.

## Why Duffel at all, not Amadeus

Amadeus's self-service portal was decommissioned 17 July 2026 — existing keys are
dead, and the only path left is their Enterprise tier, which needs IATA/ARC
accreditation. Duffel is the direct self-service replacement: real signup, no
accreditation, structured fare data.

**Cost:** search is free up to a 1,500:1 search-to-book ratio. This project never
books through the API (booking is manual, or via staff travel), so it stays free
in practice.

**Sandbox vs live:** whichever key you generate in the Duffel dashboard determines
sandbox (fake data, safe for testing) or live (real fares). Same code either way —
just swap the `DUFFEL_API_KEY` secret value in the repo.

## Setup checklist

- [x] Duffel account + test API key, added as the `DUFFEL_API_KEY` repo secret
- [x] GitHub Actions workflow — daily cron, manual trigger available
- [x] Fixed the v1/v2 version mismatch
- [ ] Re-run the workflow manually and confirm it returns real sandbox offers
- [ ] Swap to a live key once happy — same code, real fares
- [ ] Small separate script for the return-leg fallback fare (standby backup)
- [ ] Decide notification channel — email, same as ai-digest, or something else

## Why every result shows full routing, not just price

An itinerary that silently transits through an excluded hub, or gets a discount
it shouldn't via a codeshare, is the failure mode worth guarding against by
design — so the report always shows the actual routing and operating carriers,
not just "passed the filter."


