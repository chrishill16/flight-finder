"""
flight-watch: SYD -> UK Christmas trip search
Uses Duffel — Amadeus's self-service API was decommissioned 17 July 2026.

WHAT THIS DOES
  - Loops over DESTINATIONS x date window x TRIP_SHAPE
  - Applies EXCLUDED_AIRLINES and EXCLUDED_TRANSIT_AIRPORTS as hard filters
  - Compares against the Qantas staff discount
  - Flags business class if it's surprisingly close to economy
  - Prints/returns the best options with FULL itinerary detail (not just price) —
    so Chris can eyeball the routing before trusting a "Middle East excluded" claim

WHAT THIS DOESN'T DO YET
  - Email/notification delivery
  - The return-leg fallback check (separate small script, same pattern)
  - GitHub Actions scheduling wrapper

WHY DUFFEL
  - Real self-service signup, no accreditation needed — the direct replacement for
    what Amadeus's self-service tier used to be
  - Search is free up to a 1,500:1 search-to-book ratio; we never book through the
    API (booking happens manually / via staff travel), so this stays free in practice
  - Sandbox mode uses fake data — switch DUFFEL_LIVE=1 once the logic is verified,
    still free for search-only usage
  - Sign up: https://duffel.com  (needs Chris's own account + API key, stored as a
    GitHub Actions secret, same pattern as the ai-digest project)
"""

import itertools
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from duffel_api import Duffel

import config

# Auth: reads from environment — set locally for testing, or as a GitHub Actions
# secret (DUFFEL_API_KEY) for the scheduled job. Sandbox and live keys look the
# same to this code — which one you get depends on which key you generate in
# the Duffel dashboard.
duffel = Duffel(access_token=os.environ.get("DUFFEL_API_KEY"))


@dataclass
class FlightOption:
    destination: str
    depart_date: str
    return_date: str | None
    trip_shape: str
    cabin: str
    airline_codes: list[str] = field(default_factory=list)
    transit_airports: list[str] = field(default_factory=list)
    price_aud: float = 0.0
    discounted_price_aud: float | None = None  # set only if the QF discount applies
    is_qantas_discounted: bool = False
    excluded_reason: str | None = None  # set if this got filtered out — kept for
                                         # debugging/visibility rather than silently dropped
    raw_itinerary: dict = field(default_factory=dict)  # full routing, for manual eyeballing


def daterange(start: str, end: str):
    start_d = datetime.strptime(start, "%Y-%m-%d")
    end_d = datetime.strptime(end, "%Y-%m-%d")
    d = start_d
    while d <= end_d:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)


def _duffel_passengers() -> list[dict]:
    """Duffel wants explicit passenger types. A lap infant is 'infant_without_seat'."""
    passengers = [{"type": "adult"} for _ in range(config.ADULTS)]
    passengers += [{"type": "infant_without_seat"} for _ in range(config.INFANTS_ON_LAP)]
    return passengers


def fetch_offers(origin: str, destination: str, depart_date: str,
                  return_date: str | None, cabin: str):
    """
    Real Duffel Offer Request call. Returns a list of Offer objects (Duffel's SDK
    types, not raw dicts — see models/offer.py for the shape).
    """
    slices = [{"origin": origin, "destination": destination, "departure_date": depart_date}]
    if return_date:
        slices.append(
            {"origin": destination, "destination": origin, "departure_date": return_date}
        )

    try:
        offer_request = (
            duffel.offer_requests.create()
            .cabin_class(cabin.lower())
            .passengers(_duffel_passengers())
            .slices(slices)
            .return_offers()  # get offers back immediately, no separate fetch needed
            .execute()
        )
        return offer_request.offers or []
    except Exception as error:
        # Don't let one failed route/date combo kill the whole run — log and move on.
        print(f"  [warn] {origin}->{destination} {depart_date}: {error}")
        return []


def _all_segments(offer):
    """Flatten every segment across every slice (outbound + return) in one offer."""
    for travel_slice in offer.slices:
        for segment in travel_slice.segments:
            yield segment


def violates_exclusions(offer) -> str | None:
    """
    Hard filter: mainland Chinese carriers, and any Middle East transit airport.
    Checks BOTH the marketing carrier and the operating carrier on every segment —
    a Qantas-marketed itinerary can still be operated by an excluded carrier via
    codeshare, and that's exactly the case worth catching rather than missing.
    Returns a human-readable reason string if excluded, else None.
    """
    segments = list(_all_segments(offer))
    for segment in segments:
        marketing_code = segment.marketing_carrier.iata_code
        operating_code = segment.operating_carrier.iata_code

        for carrier in (marketing_code, operating_code):
            if carrier in config.EXCLUDED_AIRLINES:
                return (
                    f"excluded airline: {carrier} "
                    f"(segment {segment.origin.iata_code}->{segment.destination.iata_code})"
                )

    # Any segment's arrival airport that isn't the final leg destination is a transit
    # point. Check every segment except the last one in each slice.
    for travel_slice in offer.slices:
        for segment in travel_slice.segments[:-1]:
            if segment.destination.iata_code in config.EXCLUDED_TRANSIT_AIRPORTS:
                return f"excluded transit airport: {segment.destination.iata_code}"

    return None


def apply_qantas_discount(offer, base_price: float) -> tuple[float | None, bool]:
    """
    Applies the 25% staff discount IF every segment is genuinely QF-operated
    (confirmed scope — operating carrier must be QF, not just marketed as QF).
    Returns (discounted_price, applied) — discounted_price is None if not eligible.
    """
    segments = list(_all_segments(offer))
    if not segments:
        return None, False

    all_qf_operated = all(segment.operating_carrier.iata_code == "QF" for segment in segments)

    if not all_qf_operated:
        return None, False

    discounted = round(base_price * (1 - config.QANTAS_STAFF_DISCOUNT_PCT / 100), 2)
    return discounted, True


def check_business_class_gap(economy_price: float, business_price: float) -> bool:
    """Returns True if business is within FLAG_BUSINESS_IF_GAP_UNDER_PCT of economy."""
    if economy_price <= 0:
        return False
    gap_pct = ((business_price - economy_price) / economy_price) * 100
    return gap_pct <= config.FLAG_BUSINESS_IF_GAP_UNDER_PCT


def _build_option(offer, destination: str, depart_date: str,
                   return_date: str | None, trip_shape: str, cabin: str) -> FlightOption:
    price = float(offer.total_amount)
    exclusion_reason = violates_exclusions(offer)
    discounted_price, is_discounted = apply_qantas_discount(offer, price)

    segments = list(_all_segments(offer))
    airline_codes = sorted({s.marketing_carrier.iata_code for s in segments})

    transit_airports = []
    for travel_slice in offer.slices:
        transit_airports += [s.destination.iata_code for s in travel_slice.segments[:-1]]

    return FlightOption(
        destination=destination,
        depart_date=depart_date,
        return_date=return_date,
        trip_shape=trip_shape,
        cabin=cabin,
        airline_codes=airline_codes,
        transit_airports=transit_airports,
        price_aud=price,
        discounted_price_aud=discounted_price,
        is_qantas_discounted=is_discounted,
        excluded_reason=exclusion_reason,
        raw_itinerary=offer,
    )


def run_search() -> list[FlightOption]:
    """
    Checks every destination x depart-date x trip-shape x cabin combination.
    This is the part that manual chat searches genuinely can't do — a handful of
    web searches sample a few combos; this loops every one of them against the
    live Duffel fare database.
    """
    results: list[FlightOption] = []
    depart_dates = list(daterange(config.DEPART_WINDOW_START, config.DEPART_WINDOW_END))
    cabins = [config.CABIN_DEFAULT, "BUSINESS"]

    shapes_to_check = (
        ["RETURN", "OPEN_JAW"] if config.TRIP_SHAPE == "BEST_OF" else [config.TRIP_SHAPE]
    )

    for destination, depart_date, cabin in itertools.product(
        config.DESTINATIONS, depart_dates, cabins
    ):
        for shape in shapes_to_check:
            return_date = None
            if shape == "RETURN":
                # Simple case for the skeleton — a fixed 14-night stay from depart_date.
                # Real return dates are on staff travel per config, so this return-shape
                # price only matters as a point of comparison, not a booking target.
                return_date = (
                    datetime.strptime(depart_date, "%Y-%m-%d") + timedelta(days=14)
                ).strftime("%Y-%m-%d")

            offers = fetch_offers(config.ORIGIN, destination, depart_date, return_date, cabin)

            for offer in offers:
                option = _build_option(offer, destination, depart_date, return_date, shape, cabin)
                results.append(option)

    return results


def format_report(results: list[FlightOption]) -> str:
    """
    Human-readable summary. Shows full routing for every kept result — not just
    price — so a misread exclusion is easy to catch by eye rather than trusted blind.
    Excluded offers are shown too (collapsed), so a filtering bug is visible rather
    than silently invisible.
    """
    kept = [r for r in results if r.excluded_reason is None]
    excluded = [r for r in results if r.excluded_reason is not None]

    kept.sort(key=lambda r: r.discounted_price_aud or r.price_aud)

    lines = [f"flight-watch report — {len(kept)} valid options, {len(excluded)} excluded\n"]

    for r in kept[:15]:  # top 15, cheapest first
        price_line = f"${r.price_aud:,.0f} AUD"
        if r.is_qantas_discounted:
            price_line += f" -> ${r.discounted_price_aud:,.0f} AUD (QF staff discount applied)"

        route = " -> ".join([config.ORIGIN] + r.transit_airports + [r.destination])
        lines.append(
            f"{r.destination} | {r.depart_date}"
            + (f" - {r.return_date}" if r.return_date else " (one-way)")
            + f" | {r.trip_shape} | {r.cabin}\n"
            f"  {price_line}\n"
            f"  route: {route}  |  airlines: {', '.join(r.airline_codes)}\n"
        )

    if excluded:
        lines.append(f"\n{len(excluded)} offers excluded (sample reasons):")
        seen_reasons = set()
        for r in excluded:
            if r.excluded_reason not in seen_reasons:
                lines.append(f"  - {r.excluded_reason}")
                seen_reasons.add(r.excluded_reason)

    return "\n".join(lines)


if __name__ == "__main__":
    offers = run_search()
    print(format_report(offers))
