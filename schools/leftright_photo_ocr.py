"""OCR + best-effort line classification for LeftRightPhotoUpload -- a
photo of an already-existing Left & Right turn-by-turn sheet. Reuses the
same Tesseract setup as vault/route_sheet_ocr.py (free/offline, see
settings.TESSERACT_CMD via that module's import-time configuration); the
parsing here is much simpler than that module's since a Left & Right sheet
has no fixed table layout to match against -- just turn-by-turn text and
the occasional standalone address.

Like route_sheet_ocr.py, this is a draft-only classifier, not a reliable
one: every line lands on the Edit page as an ordinary, already-editable
LeftRightRow (see LeftRightRowSaveView / leftright_form.html's autosave
editing), which is what makes a wrong guess here harmless rather than a
reliability requirement on the classifier itself.
"""

import re

from vault.route_sheet_ocr import extract_text  # noqa: F401 -- re-exported for callers

from .models import LeftRightRow

# A line that OPENS with a house number ("123 Main St, City, MD 20874") is
# almost always a standalone address on the sheet, not a turn instruction
# -- "Turn left onto Main St" never starts with digits -- so this is what
# tells the two apart, not the presence of a street-suffix word alone
# (turn instructions name streets too).
ADDRESS_START_RE = re.compile(r"^\d{1,6}\s+\S")
# A short, fully-uppercase line ("AM ROUTE", "SCHOOL STOP") reads as a
# section heading rather than an instruction or address.
HEADING_RE = re.compile(r"^[A-Z0-9 .,'&/-]+$")
HEADING_MAX_WORDS = 6


def classify_line(line):
    """Returns (row_type, text, address) for one OCR'd line of text, per
    LeftRightRow's fields -- LINK rows carry the address in `address`
    since LeftRightDetailView turns that into a GPS link, not `text`."""
    if ADDRESS_START_RE.match(line):
        return LeftRightRow.RowType.LINK, "STOP @", line
    if HEADING_RE.match(line) and len(line.split()) <= HEADING_MAX_WORDS:
        return LeftRightRow.RowType.BOLD, line, ""
    return LeftRightRow.RowType.NORMAL, line, ""


def parse_photo_text(text):
    """Splits raw OCR text into non-blank lines and classifies each one.
    Returns a list of (row_type, text, address) tuples, in reading order."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return [classify_line(line) for line in lines]
