import re

from django import template

register = template.Library()

# A LeftRightRow's `text` sometimes starts with a single direction letter
# followed by a wide gap of spaces before the street name -- e.g.
# "R     SHAWNEE LANE" or "L     RIDGE RD (MD-27)" -- typed that way by
# whoever transcribed the route sheet, purely for print alignment. Matched
# strictly (one of R/L/S/U, then 2+ spaces) so this never fires on a real
# word that merely starts with the same letter, like "ROUTE: 2304 AM",
# "RIGHT INTO QUINCE ORCHARD HS", or "STOP @" (single space, or no space
# at all right after the letter, in every case that isn't actually one of
# these direction markers).
_DIRECTION_RE = re.compile(r"^([RLSU])[ \t]{2,}(.*)$")

_DIRECTION_ICONS = {
    "R": "icons/turn-right.html",
    "L": "icons/turn-left.html",
    "S": "icons/straight.html",
    "U": "icons/u-turn-left.html",
}


@register.filter
def leftright_direction(text):
    """Splits a LeftRightRow.text into its leading direction letter (if
    any) and the rest, so leftright_detail.html can render a Material
    Symbols turn icon (fonts.google.com/icons -- see config/templates/
    icons/turn-right.html and friends) in place of the bare letter instead
    of just printing "R"/"L"/"S"/"U". Returns a dict: {"icon": <icon
    template path, or None if this row has no leading direction letter>,
    "rest": <text with the letter+gap stripped, or the original text
    unchanged when there's no match>}."""
    match = _DIRECTION_RE.match(text)
    if not match:
        return {"icon": None, "rest": text}
    letter, rest = match.groups()
    return {"icon": _DIRECTION_ICONS[letter], "rest": rest}
