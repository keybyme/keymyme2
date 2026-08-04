"""OCR + best-effort parsing of MCPS "Bus Detail Report" route sheet photos
(RouteSheetUpload). Free/offline via Tesseract (see settings.TESSERACT_CMD) —
no cloud OCR API/billing.

This is a draft extractor, not a reliable one: tested against a real photo,
Tesseract reads clean/well-spaced sections quite well but garbles cramped
sections and occasionally misreads individual digits (e.g. in a phone
number) even in otherwise-good output. RouteSheetUploadDetailView's review
screen — where every field stays editable before Import — is what makes
this safe to use, not the parser's accuracy.
"""

import datetime as dt
import re

import pytesseract
from django.conf import settings
from PIL import Image

if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

TIME_PATTERN = r"\d{1,2}:\d{2}\s*[AP]\.?M\.?"
STOP_LINE_RE = re.compile(rf"^(\d{{1,3}})\s+({TIME_PATTERN})\s+(.+)$", re.IGNORECASE)
PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
RATIO_RE = re.compile(r"\bC[/I]R\b\s*\d+\s*/\s*\d+", re.IGNORECASE)
# Strips the trailing "Load  Next" columns (e.g. "... 20882 1 10.39") off the
# end of a main stop line, once the address itself has been pulled out.
TRAILING_LOAD_NEXT_RE = re.compile(r"\s+\d+\s+[\d,.]+\s*$")
ROUTE_TRIP_RE = re.compile(r"Trip:\s*([A-Z0-9-]+)\s*-\s*(AM|PM|MID\s*DAY)", re.IGNORECASE)

# How many lines after a stop's main row to scan for its name/phone detail
# line(s) — MCPS sheets put those on the next 1-2 lines (name+C/R+EXT+phone,
# sometimes a further "WINDOW PAD..." note line).
DETAIL_LINE_LOOKAHEAD = 3


def extract_text(image_file):
    """image_file: any file-like object Pillow can open (e.g. an uploaded
    Django File). Returns the raw OCR text."""
    image = Image.open(image_file)
    return pytesseract.image_to_string(image)


def parse_route_sheet_text(text):
    """Best-effort line-by-line parse into draft stops. Returns
    {"route_number": str|None, "route_type": str|None, "stops": [dict, ...]}
    — each stop dict has seq/planned_time/remarks/address/phone_number,
    matching RouteSheetStopDraft's fields."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    route_number = None
    route_type = None
    stops = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if route_number is None:
            trip_match = ROUTE_TRIP_RE.search(line)
            if trip_match:
                route_number = trip_match.group(1).upper()
                route_type = trip_match.group(2).upper()

        stop_match = STOP_LINE_RE.match(line)
        if not stop_match:
            i += 1
            continue

        seq = int(stop_match.group(1))
        planned_time = _parse_time(stop_match.group(2))
        address = TRAILING_LOAD_NEXT_RE.sub("", stop_match.group(3)).strip()

        remarks = ""
        phone_number = ""
        j = i + 1
        while j < len(lines) and j < i + 1 + DETAIL_LINE_LOOKAHEAD and not STOP_LINE_RE.match(lines[j]):
            detail = lines[j]
            if not phone_number:
                phone_match = PHONE_RE.search(detail)
                if phone_match:
                    phone_number = phone_match.group()
            if not remarks:
                ratio_match = RATIO_RE.search(detail)
                if ratio_match:
                    remarks = detail[:ratio_match.start()].strip()
                elif "EXT" in detail.upper():
                    remarks = detail.split("EXT")[0].strip()
            j += 1

        stops.append({
            "seq": seq,
            "planned_time": planned_time,
            "remarks": remarks,
            "address": address,
            "phone_number": phone_number,
        })
        i = j

    return {"route_number": route_number, "route_type": route_type, "stops": stops}


def _parse_time(text):
    cleaned = text.upper().replace(".", "").replace(" ", "")
    try:
        return dt.datetime.strptime(cleaned, "%I:%M%p").time()
    except ValueError:
        return None
