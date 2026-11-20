"""OSINT téléphone : analyse HORS LIGNE d'un numéro (bibliothèque phonenumbers).

Validation, pays/région, opérateur probable, type de ligne, fuseaux horaires et
formats normalisés. Aucune base inversée scrapée, aucun appel passé : uniquement
les métadonnées publiques du plan de numérotation + des liens de recherche.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote_plus

from face_analyse.core.errors import OsintError

_TYPES = {
    0: "fixe", 1: "mobile", 2: "fixe ou mobile", 3: "numéro gratuit", 4: "surtaxé",
    5: "coût partagé", 6: "VoIP", 7: "numéro personnel", 8: "messagerie vocale",
    9: "radiocom", 10: "inconnu", 27: "urgence", 28: "court",
}


@dataclass
class PhoneInfo:
    raw: str
    valid: bool
    possible: bool
    country: str = ""
    country_code: int | None = None
    region: str = ""
    carrier: str = ""
    line_type: str = ""
    timezones: list[str] = field(default_factory=list)
    e164: str = ""
    international: str = ""
    national: str = ""
    links: list[tuple[str, str]] = field(default_factory=list)
    note: str = ""


def _links(e164: str, international: str) -> list[tuple[str, str]]:
    q = quote_plus(f'"{international}"')
    qe = quote_plus(f'"{e164}"')
    return [
        ("Google", f"https://www.google.com/search?q={q}+OR+{qe}"),
        ("Bing", f"https://www.bing.com/search?q={q}"),
        ("DuckDuckGo", f"https://duckduckgo.com/?q={q}"),
    ]


def investigate(number: str, default_region: str = "FR") -> PhoneInfo:
    import phonenumbers
    from phonenumbers import carrier, geocoder, timezone

    number = number.strip()
    if not number:
        raise OsintError("Saisissez un numéro de téléphone.")
    try:
        parsed = phonenumbers.parse(number, None if number.startswith("+") else default_region)
    except phonenumbers.NumberParseException as exc:
        raise OsintError(f"Numéro illisible : {exc}") from exc

    valid = phonenumbers.is_valid_number(parsed)
    possible = phonenumbers.is_possible_number(parsed)
    info = PhoneInfo(
        raw=number, valid=valid, possible=possible,
        country_code=parsed.country_code,
        country=geocoder.region_code_for_number(parsed) or "",
        region=geocoder.description_for_number(parsed, "fr"),
        carrier=carrier.name_for_number(parsed, "fr"),
        line_type=_TYPES.get(phonenumbers.number_type(parsed), "inconnu"),
        timezones=list(timezone.time_zones_for_number(parsed)),
        e164=phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
        international=phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
        national=phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
    )
    info.links = _links(info.e164, info.international)
    if not valid:
        info.note = ("Numéro non valide pour ce plan de numérotation. "
                     "Précisez l'indicatif international (ex. +33…).") if not possible else \
                    "Numéro possible mais non attribué/valide selon les règles du pays."
    return info
