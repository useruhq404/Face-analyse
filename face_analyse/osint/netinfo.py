"""Recon réseau par services publics — DNS, RDAP (WHOIS), certificats, en-têtes.

Tout passe par des API/protocoles publics officiels (DNS-over-HTTPS de Google,
RDAP des registres, journaux de transparence des certificats crt.sh). Aucune
collecte interdite, aucun contournement. Le scan de ports est volontairement
limité aux hôtes locaux/privés ou à une cible explicitement autorisée.
"""

from __future__ import annotations

import socket
import ssl
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from urllib.parse import urlparse

from face_analyse.osint.http import PoliteSession

DOH_URL = "https://dns.google/resolve"
RDAP_URL = "https://rdap.org/domain/{domain}"
CRT_URL = "https://crt.sh/?q=%25.{domain}&output=json"

DNS_TYPES = ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "CAA")

#: en-têtes de sécurité à vérifier (présence = bonne pratique)
SECURITY_HEADERS = ("strict-transport-security", "content-security-policy", "x-frame-options",
                    "x-content-type-options", "referrer-policy", "permissions-policy")

#: ports courants pour un scan léger (services usuels)
COMMON_PORTS = {21: "ftp", 22: "ssh", 25: "smtp", 53: "dns", 80: "http", 110: "pop3",
                143: "imap", 443: "https", 445: "smb", 3306: "mysql", 3389: "rdp",
                5432: "postgres", 6379: "redis", 8080: "http-alt", 8443: "https-alt"}


def dns_query(http: PoliteSession, domain: str, rtype: str = "A") -> list[str]:
    """Résolution DNS via DNS-over-HTTPS (dns.google). Renvoie les réponses texte."""
    rtype = rtype.upper()
    data = http.get_json(DOH_URL, params={"name": domain, "type": rtype},
                         headers={"Accept": "application/dns-json"})
    return [a.get("data", "") for a in data.get("Answer", []) if a.get("data")]


def dns_overview(http: PoliteSession, domain: str) -> dict[str, list[str]]:
    """Interroge les types DNS courants. Une panne sur un type n'arrête pas les autres."""
    out: dict[str, list[str]] = {}
    for t in ("A", "AAAA", "MX", "NS", "TXT"):
        try:
            out[t] = dns_query(http, domain, t)
        except Exception:  # noqa: BLE001
            out[t] = []
    return out


@dataclass
class DomainInfo:
    domain: str
    handle: str = ""
    registrar: str = ""
    statuses: list[str] = field(default_factory=list)
    nameservers: list[str] = field(default_factory=list)
    events: dict[str, str] = field(default_factory=dict)  # registration/expiration/last changed


def rdap_domain(http: PoliteSession, domain: str) -> DomainInfo:
    """WHOIS moderne via RDAP (rdap.org redirige vers le bon registre)."""
    data = http.get_json(RDAP_URL.format(domain=domain.strip().lower()))
    info = DomainInfo(domain=domain, handle=data.get("handle", ""))
    for ev in data.get("events", []):
        act = ev.get("eventAction", "")
        if act:
            info.events[act] = ev.get("eventDate", "")
    info.statuses = data.get("status", []) or []
    for ns in data.get("nameservers", []):
        name = ns.get("ldhName") or ns.get("unicodeName")
        if name:
            info.nameservers.append(name.lower())
    for ent in data.get("entities", []):
        if "registrar" in (ent.get("roles") or []):
            for item in ent.get("vcardArray", [[], []])[1]:
                if item and item[0] == "fn":
                    info.registrar = item[3]
    return info


def crt_subdomains(http: PoliteSession, domain: str, limit: int = 200) -> list[str]:
    """Sous-domaines connus via les journaux de transparence des certificats (crt.sh)."""
    data = http.get_json(CRT_URL.format(domain=domain.strip().lower()))
    seen: set[str] = set()
    for row in data:
        for name in str(row.get("name_value", "")).splitlines():
            name = name.strip().lstrip("*.").lower()
            if name and "@" not in name:
                seen.add(name)
    return sorted(seen)[:limit]


@dataclass
class HeadersInfo:
    url: str
    status: int = 0
    server: str = ""
    present: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    all_headers: dict[str, str] = field(default_factory=dict)


def http_headers(http: PoliteSession, url: str) -> HeadersInfo:
    """Récupère les en-têtes HTTP et évalue les en-têtes de sécurité présents/absents."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    r = http.get(url, allow_redirects=True, headers={"Accept": "*/*"})
    headers = {k.lower(): v for k, v in r.headers.items()}
    present = [h for h in SECURITY_HEADERS if h in headers]
    missing = [h for h in SECURITY_HEADERS if h not in headers]
    return HeadersInfo(url=r.url, status=r.status_code, server=headers.get("server", ""),
                       present=present, missing=missing, all_headers=dict(r.headers))


def is_private_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    import ipaddress
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if not (addr.is_private or addr.is_loopback or addr.is_link_local):
            return False
    return True


@dataclass
class PortResult:
    host: str
    open_ports: list[tuple[int, str]] = field(default_factory=list)
    scanned: int = 0


def scan_ports(host: str, ports: dict[int, str] | None = None, timeout: float = 0.6,
               authorized: bool = False, workers: int = 40) -> PortResult:
    """Scan TCP léger. Refuse une cible non locale sans autorisation explicite.

    Scanner les ports d'un système tiers sans permission est intrusif et souvent
    illégal : par défaut on n'autorise que localhost / réseau privé.
    """
    host = urlparse(host).hostname or host.strip()
    if not is_private_host(host) and not authorized:
        raise PermissionError("cible non locale : cochez « j'y suis autorisé » (sinon intrusion illégale)")
    ports = ports or COMMON_PORTS
    res = PortResult(host=host, scanned=len(ports))

    def probe(port: int) -> tuple[int, str] | None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            if s.connect_ex((host, port)) == 0:
                return port, ports[port]
        return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(probe, ports):
            if r:
                res.open_ports.append(r)
    res.open_ports.sort()
    return res


def tls_cert_info(host: str, port: int = 443, timeout: float = 5.0) -> dict[str, str]:
    """Infos publiques du certificat TLS présenté par un hôte (sujet, émetteur, validité)."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
    subj = dict(x[0] for x in cert.get("subject", []))
    issuer = dict(x[0] for x in cert.get("issuer", []))
    return {"sujet": subj.get("commonName", ""), "émetteur": issuer.get("organizationName", ""),
            "valide_du": cert.get("notBefore", ""), "valide_au": cert.get("notAfter", "")}
