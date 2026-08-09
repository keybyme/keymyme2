"""Geocoding + turn-by-turn routing for Rutas' "Directions" view
(RouteDirectionsView) and schools' "Lefts & Rights" view (LeftsRightsView).
Geocoding is via LocationIQ (free tier, API key required — see
settings.LOCATIONIQ_API_KEY); routing is via OSRM's public demo server (free,
no key). Both started out on OpenStreetMap's own public Nominatim (also
free, no key), but that was dropped for geocoding on 2026-08-09 after it
turned out to blanket-429 every request from prod's EC2 IP (confirmed: the
identical query succeeds from a residential/office IP, fails from the EC2
box) — an IP/ASN-level throttle on Nominatim's end, not something fixable by
respecting their documented 1 req/sec policy more carefully. LocationIQ is
Nominatim-compatible (same OSM data, same response shape) and unaffected.
OSRM's public demo server was never affected, so routing stayed as-is."""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

USER_AGENT = "KeyByMe/1.0 (personal app; contact: me@20874.com)"

# No \b before the digits: a typo/OCR glitch can run the zip straight into
# the street type with no space ("...Cir20874"), and \b wouldn't fire there
# since letters and digits are both "word" characters — only look-arounds on
# the digits themselves (not preceded/followed by another digit, so we don't
# grab a partial zip+4) catch that case too.
ZIP_RE = re.compile(r"(?<!\d)\d{5}(?!\d)")
INTERSECTION_RE = re.compile(r"^(.+?)\s*&\s*(.+)$")

LOCATIONIQ_URL = "https://us1.locationiq.com/v1/search"
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/"

# OSRM maneuver "modifier" -> human label. Only left/right/uturn maneuvers
# are surfaced (see get_route_legs) — a driver doesn't need "go straight"
# spelled out.
MODIFIER_LABELS = {
    "slight left": "Slight left",
    "left": "Turn left",
    "sharp left": "Sharp left",
    "slight right": "Slight right",
    "right": "Turn right",
    "sharp right": "Sharp right",
    "uturn": "U-turn",
}


class GeocodingRateLimited(Exception):
    """Raised when LocationIQ/OSRM answer with HTTP 429 — LocationIQ's free
    tier caps at 2 req/sec and 5,000/day; OSRM's demo server has its own
    unpublished limits. Distinct from a plain None result (address genuinely
    not found) so callers can tell the user the truth: the provider is
    throttling right now, not that the address doesn't exist."""


def _fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise GeocodingRateLimited from exc
        return None
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, ValueError):
        return None


def _geocode_query(query, viewbox=None):
    params = {
        "key": settings.LOCATIONIQ_API_KEY,
        "q": query, "format": "json", "limit": 1, "countrycodes": "us",
    }
    if viewbox:
        # Restricts results to this "lon1,lat1,lon2,lat2" box server-side
        # (bounded=1), rather than trusting the geocoder to guess the right
        # region for an ambiguous/malformed street name and filtering after
        # the fact — the latter can't recover a correct in-region match that
        # bounded search would have found instead. See callers for why:
        # a street name shared with somewhere far away (e.g. "Dunstable
        # Cir" also exists near Orlando, FL) can otherwise win outright.
        params["viewbox"] = viewbox
        params["bounded"] = 1
    results = _fetch_json(f"{LOCATIONIQ_URL}?{urllib.parse.urlencode(params)}")
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


def geocode_address(address, viewbox=None):
    """Returns (latitude, longitude) as floats, or None if the address
    couldn't be resolved. Callers looping over several addresses must space
    calls out themselves (LocationIQ free tier: max 2 req/sec) — see
    RouteDirectionsView.

    `viewbox` (optional "lon1,lat1,lon2,lat2") constrains every attempt to
    that region — worth passing when the caller knows results outside it are
    never correct (e.g. MCPS routes are always in Montgomery County, MD; see
    schools.views.MCPS_VIEWBOX). Real example that motivated this: without
    it, "20049 Dunstable Cir 20878" (an MCPS stop in Montgomery County)
    geocoded to a "Dunstable Cir" near Orlando, FL instead — same street
    name, wrong state, silently accepted because nothing said it couldn't be.

    Tries the address as typed, then two fallbacks (in order) once a zip code
    can be found in it:
    1. Everything up through the zip, dropping anything after it — OCR'd
       addresses (see route_sheet_ocr.py) sometimes carry trailing noise
       past the zip (misread table columns) that breaks the query outright.
    2. Just "street + zip", dropping any city/state too — the underlying OSM
       data frequently fails on "street, city, state zip" when the
       mailing/USPS city doesn't exactly match OSM's canonical locality name
       for that zip (common in MD, e.g. "Rockville" on an envelope vs.
       "Aspen Hill" in OSM), even though the zip itself is correct."""
    coords = _geocode_query(address, viewbox)
    if coords is not None:
        return coords

    zip_match = ZIP_RE.search(address)
    if not zip_match:
        return None

    candidates = []
    trimmed = address[:zip_match.end()].strip()
    if trimmed and trimmed != address:
        candidates.append(trimmed)
    street_zip = f"{address.split(',')[0].strip()} {zip_match.group()}"
    if street_zip not in candidates and street_zip != address:
        candidates.append(street_zip)

    for candidate in candidates:
        time.sleep(1)  # each retry is a new request for the same address — stay well under the rate limit
        coords = _geocode_query(candidate, viewbox)
        if coords is not None:
            return coords
    return None


def geocode_intersection(address, default_location, viewbox=None):
    """Approximates the coordinates of a "Street A & Street B[, City, State]"
    corner by geocoding each street separately and averaging the two points.

    Plain free-text search (geocode_address() above) doesn't parse "&" as an
    intersection — it just fails outright — but MCPS bus-stop addresses
    (schools.AmMidPmEntry) are routinely given as a corner rather than a
    mailing address, often with no city/state at all (e.g. "Skylark Rd &
    Walnut Haven Dr"). `default_location` (e.g. "Montgomery County, MD") is
    used when the address itself has no city/state after the streets.
    `viewbox` — see geocode_address() — constrains both sub-queries.

    Not exact — each street's geocode is the provider's best match for that
    street name within the area, not the literal point where the two cross —
    but close enough for a turn-by-turn driving cheat-sheet between stops.
    Returns (latitude, longitude) or None if either street couldn't be
    resolved, or the address isn't in "A & B" form at all."""
    match = INTERSECTION_RE.match(address)
    if not match:
        return None
    street_a, rest = match.group(1).strip(), match.group(2).strip()
    if "," in rest:
        street_b, location = (part.strip() for part in rest.split(",", 1))
    else:
        street_b, location = rest, default_location
    if not street_a or not street_b or not location:
        return None

    coords_a = _geocode_query(f"{street_a}, {location}", viewbox)
    time.sleep(1)  # stay well under the rate limit between the two sub-queries
    coords_b = _geocode_query(f"{street_b}, {location}", viewbox)
    if coords_a is None or coords_b is None:
        return None
    return (coords_a[0] + coords_b[0]) / 2, (coords_a[1] + coords_b[1]) / 2


def get_route_legs(coords):
    """coords: ordered list of (latitude, longitude) tuples (one per stop).
    Returns a list with one entry per consecutive pair of stops, each a list
    of {"label", "street", "distance_mi"} dicts for left/right/uturn
    maneuvers along that leg — or None if OSRM couldn't compute a route."""
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
    params = urllib.parse.urlencode({"steps": "true", "geometries": "geojson", "overview": "false"})
    data = _fetch_json(f"{OSRM_ROUTE_URL}{coord_str}?{params}")
    if not data or data.get("code") != "Ok" or not data.get("routes"):
        return None

    legs = []
    for leg in data["routes"][0]["legs"]:
        turns = []
        for step in leg.get("steps", []):
            modifier = (step.get("maneuver") or {}).get("modifier", "")
            label = MODIFIER_LABELS.get(modifier)
            if not label:
                continue
            turns.append({
                "label": label,
                "street": step.get("name") or "unnamed road",
                "distance_mi": round(step.get("distance", 0) / 1609.34, 2),
            })
        legs.append(turns)
    return legs
