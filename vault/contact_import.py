"""Parseo de archivos .vcf (vCard) y .csv para la importación masiva de Contact.

No se usa ninguna librería externa de vCard: el formato que exportan iCloud/iPhone
es simple (RFC 6350 con "line folding") y así evitamos una dependencia nueva.
"""
import csv
import io
import re

CONTACT_FIELDS = ("name", "phone", "email", "address", "notes")

CSV_FIELD_ALIASES = {
    "name": {"nombre", "name", "fullname", "full name", "nombre completo"},
    "phone": {"telefono", "teléfono", "phone", "phone number", "celular", "movil", "móvil"},
    "email": {"correo", "email", "e-mail", "correo electronico", "correo electrónico"},
    "address": {"direccion", "dirección", "address"},
    "notes": {"notas", "notes", "nota", "comentarios"},
}

# Exportadores tipo Covve/iOS Contacts no traen una sola columna "name"/"phone"/etc.:
# separan el nombre en columnas y numeran teléfono/email/dirección
# ("Phone - 1", "Phone - 2", ...). Se detectan aparte y se usa el primer valor no
# vacío de cada grupo numerado.
GIVEN_NAME_ALIASES = {"given name", "first name"}
FAMILY_NAME_ALIASES = {"family name", "last name"}
ADDRESS_PART_ORDER = (
    "address street", "address city", "address state", "address postal code", "address country",
)
_NUMBER_SUFFIX = re.compile(r"\s*-\s*\d+$")


def _strip_index(header):
    return _NUMBER_SUFFIX.sub("", (header or "")).strip().lower()


def _empty_contact():
    return {field: "" for field in CONTACT_FIELDS}


def _unfold_vcard_lines(text):
    """RFC 6350: una línea que empieza con espacio/tab es continuación de la anterior."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def _unescape_vcard_value(value):
    return (
        value.replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\\\", "\\")
    )


def parse_vcard(text):
    """Regresa una lista de dicts (name/phone/email/address/notes) a partir de un .vcf
    que puede traer uno o varios BEGIN:VCARD...END:VCARD concatenados."""
    contacts = []
    current = None

    for raw_line in _unfold_vcard_lines(text):
        line = raw_line.strip()
        if not line:
            continue

        upper = line.upper()
        if upper == "BEGIN:VCARD":
            current = _empty_contact()
            continue
        if upper == "END:VCARD":
            if current is not None and current["name"]:
                contacts.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue

        prop, _, value = line.partition(":")
        prop_name = prop.split(";")[0].upper()
        value = _unescape_vcard_value(value).strip()
        if not value:
            continue

        if prop_name == "FN" and not current["name"]:
            current["name"] = value
        elif prop_name == "N" and not current["name"]:
            # N es "Apellidos;Nombre;Segundo nombre;Prefijo;Sufijo"
            parts = [p for p in value.split(";") if p]
            current["name"] = " ".join(reversed(parts))
        elif prop_name == "TEL" and not current["phone"]:
            current["phone"] = value
        elif prop_name == "EMAIL" and not current["email"]:
            current["email"] = value
        elif prop_name == "ADR" and not current["address"]:
            parts = [p.strip() for p in value.split(";") if p.strip()]
            current["address"] = ", ".join(parts)
        elif prop_name == "NOTE":
            current["notes"] = value

    return contacts


def parse_csv(text):
    """Regresa una lista de dicts a partir de un .csv, aceptando encabezados
    en español o inglés (ver CSV_FIELD_ALIASES), o el formato numerado tipo
    Covve/iOS Contacts (Given Name/Family Name, Phone - 1, Email - 1, ...)."""
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []

    column_map = {}
    given_name_col = family_name_col = None
    phone_cols, email_cols = [], []
    address_cols = {}

    for field in reader.fieldnames:
        key = (field or "").strip().lower()
        matched = False
        for target, aliases in CSV_FIELD_ALIASES.items():
            if key in aliases:
                column_map[field] = target
                matched = True
                break
        if matched:
            continue

        base_key = _strip_index(field)
        if base_key in GIVEN_NAME_ALIASES:
            given_name_col = field
        elif base_key in FAMILY_NAME_ALIASES:
            family_name_col = field
        elif base_key == "phone":
            phone_cols.append(field)
        elif base_key == "email":
            email_cols.append(field)
        elif base_key in ADDRESS_PART_ORDER:
            address_cols.setdefault(base_key, []).append(field)

    contacts = []
    for row in reader:
        data = _empty_contact()
        for field, value in row.items():
            target = column_map.get(field)
            if target and value:
                data[target] = value.strip()

        if not data["name"] and (given_name_col or family_name_col):
            given = (row.get(given_name_col) or "").strip() if given_name_col else ""
            family = (row.get(family_name_col) or "").strip() if family_name_col else ""
            data["name"] = " ".join(part for part in (given, family) if part)

        if not data["phone"]:
            for field in phone_cols:
                value = (row.get(field) or "").strip()
                if value:
                    data["phone"] = value
                    break

        if not data["email"]:
            for field in email_cols:
                value = (row.get(field) or "").strip()
                if value:
                    data["email"] = value
                    break

        if not data["address"] and address_cols:
            # Junta el primer grupo de dirección (calle/ciudad/edo/cp/país - 1).
            parts = []
            for part_key in ADDRESS_PART_ORDER:
                fields = address_cols.get(part_key)
                if not fields:
                    continue
                value = (row.get(fields[0]) or "").strip()
                if value:
                    parts.append(value.replace("\n", " "))
            data["address"] = ", ".join(parts)

        if data["name"]:
            contacts.append(data)

    return contacts
