"""IP Lookup : géolocalisation, ASN/opérateur, DNS inverse, indices proxy/hébergeur.

Sources publiques gratuites (ipwho.is, ipinfo.io). Données approximatives : la
géolocalisation IP donne la zone de l'opérateur, pas l'adresse d'une personne.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field

import requests

from face_analyse.core.errors import OsintError

_UA = {"User-Agent": "FaceAnalyse-OSINT/1.0"}


@dataclass
class IpInfo:
    query: str
    ip: str
    ip_type: str = ""
    hostname: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    postal: str = ""
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = ""
    asn: str = ""
    org: str = ""
    isp: str = ""
    domain: str = ""
    is_proxy: bool | None = None
    is_hosting: bool | None = None
    is_mobile: bool | None = None
    is_anycast: bool | None = None
    sources: list[str] = field(default_factory=list)
    map_url: str = ""


def resolve_to_ip(value: str) -> tuple[str, str]:
    """Accepte une IP ou un nom de domaine ; retourne (ip, nom_original)."""
    value = value.strip()
    if not value:
        raise OsintError("Saisissez une adresse IP ou un domaine.")
    try:
        ipaddress.ip_address(value)
        return value, value
    except ValueError:
        pass
    host = value.split("//")[-1].split("/")[0].split(":")[0]
    try:
        ip = socket.gethostbyname(host)
    except OSError as exc:
        raise OsintError(f"Domaine irrésolu : {host}") from exc
    return ip, host


def reverse_dns(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except (OSError, socket.herror):
        return ""


def lookup(value: str, timeout: float = 12.0) -> IpInfo:
    ip, original = resolve_to_ip(value)
    try:
        if not ipaddress.ip_address(ip).is_global:
            raise OsintError("Adresse IP privée ou réservée : pas de géolocalisation publique.")
    except ValueError:
        pass

    info = IpInfo(query=original, ip=ip)
    info.hostname = reverse_dns(ip)

    # Source principale : ipwho.is (riche).
    try:
        r = requests.get(f"https://ipwho.is/{ip}", headers=_UA, timeout=timeout)
        d = r.json()
        if d.get("success"):
            conn = d.get("connection", {}) or {}
            tz = d.get("timezone", {}) or {}
            info.ip_type = d.get("type", "")
            info.country = d.get("country", "")
            info.region = d.get("region", "")
            info.city = d.get("city", "")
            info.postal = d.get("postal", "")
            info.latitude = d.get("latitude")
            info.longitude = d.get("longitude")
            info.timezone = tz.get("id", "")
            info.asn = f"AS{conn.get('asn')}" if conn.get("asn") else ""
            info.org = conn.get("org", "")
            info.isp = conn.get("isp", "")
            info.domain = conn.get("domain", "")
            info.sources.append("ipwho.is")
    except (requests.RequestException, ValueError):
        pass

    # Complément : ipinfo.io (hostname, anycast).
    try:
        r = requests.get(f"https://ipinfo.io/{ip}/json", headers=_UA, timeout=timeout)
        d = r.json()
        if not d.get("error"):
            info.hostname = info.hostname or d.get("hostname", "")
            info.city = info.city or d.get("city", "")
            info.region = info.region or d.get("region", "")
            info.country = info.country or d.get("country", "")
            info.org = info.org or d.get("org", "")
            info.timezone = info.timezone or d.get("timezone", "")
            if d.get("anycast") is not None:
                info.is_anycast = bool(d.get("anycast"))
            info.sources.append("ipinfo.io")
    except (requests.RequestException, ValueError):
        pass

    if not info.sources:
        raise OsintError("Services de géolocalisation injoignables. Réessayez plus tard.")
    # Heuristiques « hébergeur / datacenter » sur le nom d'organisation.
    org = f"{info.org} {info.isp}".lower()
    info.is_hosting = any(k in org for k in ("hosting", "cloud", "datacenter", "data center", "server",
                                             "ovh", "digitalocean", "amazon", "google", "azure", "hetzner", "vps"))
    if info.latitude is not None and info.longitude is not None:
        info.map_url = f"https://www.openstreetmap.org/?mlat={info.latitude}&mlon={info.longitude}#map=11/{info.latitude}/{info.longitude}"
    return info
