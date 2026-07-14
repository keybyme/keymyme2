"""Parseo de archivos .vcf (vCard) y .csv para la importación masiva de Contact.

No se usa ninguna librería externa de vCard: el formato que exportan iCloud/iPhone
es simple (RFC 6350 con "line folding") y así evitamos una dependencia nueva.
"""
import csv
import io

CONTACT_FIELDS = ("name", "phone", "email", "address", "notes")

CSV_FIELD_ALIASES = {
    "name": {"nombre", "name", "fullname", "full name", "nombre completo"},
    "phone": {"telefono", "teléfono", "phone", "phone number", "celular", "movil", "móvil"},
    "email": {"correo", "email", "e-mail", "correo electronico", "correo electrónico"},
    "address": {"direccion", "dirección", "address"},
    "notes": {"notas", "notes", "nota", "comentarios"},
}


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
    en español o inglés (ver CSV_FIELD_ALIASES)."""
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []

    column_map = {}
    for field in reader.fieldnames:
        key = (field or "").strip().lower()
        for target, aliases in CSV_FIELD_ALIASES.items():
            if key in aliases:
                column_map[field] = target
                break

    contacts = []
    for row in reader:
        data = _empty_contact()
        for field, value in row.items():
            target = column_map.get(field)
            if target and value:
                data[target] = value.strip()
        if data["name"]:
            contacts.append(data)

    return contacts
