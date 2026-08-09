"""Free, no-API-key geocoding + turn-by-turn routing for Rutas' "Directions"
view (RouteDirectionsView). Uses OpenStreetMap's public Nominatim (geocoding)
and OSRM (routing) demo servers — no billing/API key setup, but both have
usage policies (Nominatim: max 1 request/second) and can occasionally be
slow/unavailable, unlike a paid provider such as Google Directions."""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "KeyByMe/1.0 (personal app; contact: me@20874.com)"

ZIP_RE = re.compile(r"\b\d{5}\b")
INTERSECTION_RE = re.compile(r"^(.+?)\s*&\s*(.+)$")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
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


def _fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, ValueError):
        return None


def _geocode_query(query):
    params = urllib.parse.urlencode({
        "q": query, "format": "json", "limit": 1, "countrycodes": "us",
    })
    results = _fetch_json(f"{NOMINATIM_URL}?{params}")
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


def geocode_address(address):
    """Returns (latitude, longitude) as floats, or None if the address
    couldn't be resolved. Callers looping over several addresses must space
    calls out themselves (Nominatim: max 1 req/sec) — see RouteDirectionsView.

    Tries the address as typed, then two fallbacks (in order) once a zip code
    can be found in it:
    1. Everything up through the zip, dropping anything after it — OCR'd
       addresses (see route_sheet_ocr.py) sometimes carry trailing noise
       past the zip (misread table columns) that breaks the query outright.
    2. Just "street + zip", dropping any city/state too — Nominatim
       frequently fails on "street, city, state zip" when the mailing/USPS
       city doesn't exactly match OSM's canonical locality name for that zip
       (common in MD, e.g. "Rockville" on an envelope vs. "Aspen Hill" in
       OSM), even though the zip itself is correct."""
    coords = _geocode_query(address)
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
        time.sleep(1)  # each retry is a new request for the same address — respect 1 req/sec
        coords = _geocode_query(candidate)
        if coords is not None:
            return coords
    return None


def geocode_intersection(address, default_location):
    """Approximates the coordinates of a "Street A & Street B[, City, State]"
    corner by geocoding each street separately and averaging the two points.

    Nominatim's free-text search (geocode_address() above) doesn't parse "&"
    as an intersection — it just fails outright — but MCPS bus-stop
    addresses (schools.AmMidPmEntry) are routinely given as a corner rather
    than a mailing address, often with no city/state at all (e.g. "Skylark
    Rd & Walnut Haven Dr"). `default_location` (e.g. "Montgomery County, MD")
    is used when the address itself has no city/state after the streets.

    Not exact — each street's geocode is Nominatim's best match for that
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

    coords_a = _geocode_query(f"{street_a}, {location}")
    time.sleep(1)  # Nominatim usage policy: max 1 request/second
    coords_b = _geocode_query(f"{street_b}, {location}")
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
