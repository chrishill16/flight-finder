"""
Flight watch config — Sydney to UK, Christmas trip.
Edit this file to tweak the search without touching the script logic.
"""

# --- Route ---
ORIGIN = "SYD"

# Candidate UK destinations, weighted north of England first.
# NOTE: checked manually — Leeds Bradford (LBA) has NO flights from SYD at all
# (confirmed via Skyscanner, Aug 2026), so it's left out. Add it back if that changes.
DESTINATIONS = [
    "MAN",  # Manchester — north, good connectivity
    "NCL",  # Newcastle — north
    "LPL",  # Liverpool — north
    "EDI",  # Edinburgh — technically Scotland, not "north of England", but in scope
            # since Chris said "any UK city"
    "LON",  # London (all airports) — benchmark / fallback, not prioritised
]

# --- Dates ---
# Outbound: flexible departure window, must ARRIVE in the UK by 24 Dec.
DEPART_WINDOW_START = "2026-12-18"
DEPART_WINDOW_END = "2026-12-22"   # latest sensible departure to land by the 24th
ARRIVE_BY = "2026-12-24"

# Return leg: Chris is planning standby (staff travel) for this leg.
# This script does NOT search the return — it's here as a fallback price-check only,
# in case standby doesn't clear. See fallback_return.py (tomorrow).
RETURN_FALLBACK_ENABLED = True

# --- Passengers ---
ADULTS = 2
INFANTS_ON_LAP = 1  # under 2, no seat — MUST be passed as infant, not child, in the API call

# --- Cabin ---
CABIN_DEFAULT = "ECONOMY"
FLAG_BUSINESS_IF_GAP_UNDER_PCT = 40  # if business is within 40% of economy price, flag it

# --- Trip shape ---
# "RETURN"     = standard round trip
# "OPEN_JAW"   = fly into one city, out of another (fits "happy to break up the trip")
# "BEST_OF"    = price all shapes, report the winner with savings shown
TRIP_SHAPE = "BEST_OF"

# --- Exclusions ---
# Mainland Chinese carriers only — Cathay Pacific (CX, Hong Kong) is explicitly OK.
EXCLUDED_AIRLINES = [
    "CA",  # Air China
    "MU",  # China Eastern
    "CZ",  # China Southern
    "HU",  # Hainan Airlines
    "3U",  # Sichuan Airlines
    "MF",  # Xiamen Airlines
]

# Transit/connection airports to avoid — Middle East hubs only.
# CONFIRMED: Istanbul (IST) / Turkish Airlines is fine — not treated as Middle East.
EXCLUDED_TRANSIT_AIRPORTS = [
    "DOH",  # Doha
    "DXB",  # Dubai
    "AUH",  # Abu Dhabi
    "SHJ",  # Sharjah (catch-all for UAE)
]

# --- Qantas staff discount ---
QANTAS_STAFF_DISCOUNT_PCT = 25
# CONFIRMED: applies to Qantas-OPERATED sectors only (QF flight number AND QF as the
# operating carrier — a QF-marketed codeshare actually flown by a partner does NOT
# get the discount).
QANTAS_DISCOUNT_QF_OPERATED_ONLY = True

# Blackout dates for the staff discount over peak Christmas period are still unconfirmed.
# Flagged in the report output rather than blocking the build — worth checking with
# Chris's staff travel portal before relying on a discounted price near Dec 18-24.
QANTAS_DISCOUNT_BLACKOUT_CHECK_NEEDED = True
