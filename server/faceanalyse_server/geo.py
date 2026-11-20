"""Géolocalisation d'IP (ip-api.com, gratuit, usage non commercial).

Utilisé pour enrichir les sessions dans le panel admin. Échoue silencieusement
pour les IP privées ou si le service est injoignable : la session reste valide.
"""

from __future__ import annotations

import ipaddress

import httpx

_FIELDS = "status,country,regionName,city,isp,org,as,query,proxy,hosting"


def is_public_ip(ip: str) -> bool:
    try:
        return not ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def lookup(ip: str, timeout: float = 4.0) -> dict:
    if not is_public_ip(ip):
        return {}
    try:
        r = httpx.get(f"http://ip-api.com/json/{ip}", params={"fields": _FIELDS}, timeout=timeout)
        data = r.json()
    except (httpx.HTTPError, ValueError):
        return {}
    if data.get("status") != "success":
        return {}
    return {
        "country": data.get("country", ""),
        "region": data.get("regionName", ""),
        "city": data.get("city", ""),
        "isp": data.get("isp", ""),
        "org": data.get("org", ""),
        "asn": data.get("as", ""),
        "proxy": bool(data.get("proxy")),
        "hosting": bool(data.get("hosting")),
    }
