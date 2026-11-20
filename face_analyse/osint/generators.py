"""Générateurs de données de TEST et décodeurs (utilitaires hors ligne).

Tout est calculé localement, sans réseau. Les valeurs produites sont des
**données de test** : un IBAN généré a une clé de contrôle valide (format) mais
ne correspond à AUCUN compte bancaire réel ; une IP aléatoire ne désigne aucune
machine en particulier. À utiliser pour tester des formulaires, des parseurs ou
comprendre un format — jamais pour usurper une identité ou frauder.

Le décodeur d'ID Discord n'interroge pas Discord : l'horodatage de création est
directement encodé dans l'identifiant (« snowflake »), information publique et
documentée. Il ne révèle ni le nom ni le propriétaire du compte.
"""

from __future__ import annotations

import ipaddress
import random
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

# --------------------------------------------------------------------------- IP


def random_ipv4(count: int = 10, *, public_only: bool = True) -> list[str]:
    """IPv4 aléatoires (données de test). `public_only` écarte privé/réservé."""
    count = max(1, min(count, 1000))
    out: list[str] = []
    tries = 0
    while len(out) < count and tries < count * 40:
        tries += 1
        addr = ipaddress.IPv4Address(secrets.randbits(32))
        if public_only and (addr.is_private or addr.is_reserved or addr.is_multicast
                            or addr.is_loopback or addr.is_link_local or not addr.is_global):
            continue
        out.append(str(addr))
    return out


def random_ipv6(count: int = 10, *, public_only: bool = True) -> list[str]:
    """IPv6 aléatoires (données de test)."""
    count = max(1, min(count, 1000))
    out: list[str] = []
    tries = 0
    while len(out) < count and tries < count * 40:
        tries += 1
        addr = ipaddress.IPv6Address(secrets.randbits(128))
        if public_only and not addr.is_global:
            continue
        out.append(str(addr))
    return out


def random_ipv4_in(cidr: str, count: int = 10) -> list[str]:
    """IPv4 aléatoires DANS un réseau donné (ex. 192.168.0.0/16) — utile en test."""
    net = ipaddress.ip_network(cidr, strict=False)
    size = net.num_addresses
    count = max(1, min(count, 1000))
    out = []
    for _ in range(count):
        out.append(str(net.network_address + random.randrange(size)))
    return out


# ------------------------------------------------------------------------- IBAN

#: longueur totale d'un IBAN par pays (BBAN = total - 4).
IBAN_LENGTHS: dict[str, int] = {
    "FR": 27, "DE": 22, "ES": 24, "BE": 16, "PT": 25, "LU": 20,
    "CH": 21, "IT": 27, "NL": 18, "GB": 22, "IE": 22, "AT": 20,
}


def _iban_check_digits(country: str, bban: str) -> str:
    rearranged = bban + country + "00"
    num = "".join(str(int(c, 36)) for c in rearranged)  # A→10 … Z→35, chiffres inchangés
    check = 98 - (int(num) % 97)
    return f"{check:02d}"


def fake_iban(country: str = "FR", count: int = 5) -> list[str]:
    """IBAN factices à clé de contrôle valide (DONNÉES DE TEST, aucun compte réel)."""
    country = country.upper()
    total = IBAN_LENGTHS.get(country)
    if total is None:
        raise ValueError(f"Pays IBAN non pris en charge : {country}")
    count = max(1, min(count, 500))
    out = []
    for _ in range(count):
        bban = "".join(str(secrets.randbelow(10)) for _ in range(total - 4))
        iban = country + _iban_check_digits(country, bban) + bban
        out.append(" ".join(iban[i:i + 4] for i in range(0, len(iban), 4)))
    return out


def iban_is_valid(iban: str) -> bool:
    """Vérifie la clé de contrôle mod-97 d'un IBAN (format uniquement)."""
    s = iban.replace(" ", "").upper()
    if len(s) < 5 or not s[:2].isalpha() or not s[2:4].isdigit():
        return False
    rearranged = s[4:] + s[:4]
    try:
        num = "".join(str(int(c, 36)) for c in rearranged)
    except ValueError:
        return False
    return int(num) % 97 == 1


# -------------------------------------------------------------------- Discord ID

DISCORD_EPOCH_MS = 1_420_070_400_000  # 2015-01-01T00:00:00Z


@dataclass(frozen=True)
class SnowflakeInfo:
    snowflake: int
    created_at: datetime
    worker_id: int
    process_id: int
    increment: int

    @property
    def age_days(self) -> int:
        return (datetime.now(timezone.utc) - self.created_at).days


def decode_discord_id(snowflake: str | int) -> SnowflakeInfo:
    """Décode un ID Discord (utilisateur/serveur/message) → date de création.

    L'horodatage est encodé dans l'identifiant (bits de poids fort). N'interroge
    pas Discord, ne révèle pas l'identité du titulaire.
    """
    sf = int(str(snowflake).strip())
    if sf <= 0:
        raise ValueError("Identifiant invalide")
    ms = (sf >> 22) + DISCORD_EPOCH_MS
    created = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return SnowflakeInfo(sf, created, (sf & 0x3E0000) >> 17, (sf & 0x1F000) >> 12, sf & 0xFFF)


def snowflake_for(dt: datetime) -> int:
    """Snowflake Discord minimal correspondant à une date (pour filtrer par date)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ms = int(dt.timestamp() * 1000)
    return max(0, ms - DISCORD_EPOCH_MS) << 22


# ------------------------------------------------------------------ divers tests


def random_uuid(count: int = 5) -> list[str]:
    return [str(uuid.uuid4()) for _ in range(max(1, min(count, 500)))]


def random_mac(count: int = 5, *, local: bool = True) -> list[str]:
    """Adresses MAC aléatoires (bit 'localement administré' posé par défaut)."""
    out = []
    for _ in range(max(1, min(count, 500))):
        first = (secrets.randbits(8) & 0xFE) | (0x02 if local else 0x00)
        rest = [secrets.randbits(8) for _ in range(5)]
        out.append(":".join(f"{b:02X}" for b in [first, *rest]))
    return out
