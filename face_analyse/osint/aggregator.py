"""Exécution parallèle des sources, dédoublonnage et tri."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable

from face_analyse.osint.http import PoliteSession
from face_analyse.osint.links import build_links
from face_analyse.osint.models import OsintQuery, OsintReport, OsintResult, SourceStatus
from face_analyse.osint.sources import Source, all_sources
from face_analyse.osint.usernames import Presence, candidate_usernames, check_usernames

log = logging.getLogger(__name__)

ProgressFn = Callable[[str, int, int], None]


def deduplicate(results: list[OsintResult]) -> tuple[list[OsintResult], int]:
    by_key: dict[str, OsintResult] = {}
    removed = 0
    for r in results:
        existing = by_key.get(r.key)
        if existing is None:
            by_key[r.key] = r
            continue
        removed += 1
        keep, drop = (existing, r) if existing.relevance >= r.relevance else (r, existing)
        if drop.source not in keep.duplicates and drop.source != keep.source:
            keep.duplicates.append(drop.source)
        by_key[r.key] = keep
    return list(by_key.values()), removed


class OsintEngine:
    def __init__(self, timeout_s: float = 10.0, secrets: dict[str, str] | None = None,
                 enabled_sources: list[str] | None = None, sources: list[Source] | None = None):
        self.http = PoliteSession(timeout=timeout_s)
        self.sources = sources or all_sources(self.http, secrets)
        if enabled_sources:
            self.sources = [s for s in self.sources if s.key in enabled_sources]

    def run(self, q: OsintQuery, check_handles: bool = True, progress: ProgressFn | None = None,
            min_relevance: float = 0.15) -> OsintReport:
        q.validate()
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        results: list[OsintResult] = []
        statuses: list[SourceStatus] = []
        total = len(self.sources)

        def run_source(src: Source):
            t0 = time.perf_counter()
            try:
                found = src.search(q)
                return src, found, None, (time.perf_counter() - t0) * 1000
            except Exception as exc:  # noqa: BLE001 - une source en panne ne bloque pas les autres
                log.warning("Source %s en erreur : %s", src.label, exc)
                return src, [], str(exc)[:200], (time.perf_counter() - t0) * 1000

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(run_source, s) for s in self.sources]
            for i, fut in enumerate(as_completed(futures)):
                src, found, err, ms = fut.result()
                kept = [r for r in found if r.relevance >= min_relevance]
                results.extend(kept)
                statuses.append(SourceStatus(src.label, err is None, len(kept), ms, err or ""))
                if progress:
                    progress(f"Source : {src.label}", i + 1, total)

        if check_handles:
            handles = list(dict.fromkeys(list(q.usernames) + candidate_usernames(q.first_name, q.last_name)[:4]))
            t0 = time.perf_counter()
            hits = check_usernames(self.http, handles,
                                   progress=(lambda d, n: progress("Pseudonymes", d, n)) if progress else None)
            found = [h for h in hits if h.presence == Presence.FOUND]
            for h in found:
                results.append(OsintResult(
                    source=h.platform, category="Pseudonyme", title=f"@{h.username} sur {h.platform}", url=h.url,
                    snippet="Un compte porte ce pseudo. Rien n'indique qu'il appartienne à la personne recherchée.",
                    relevance=0.3 if h.username not in q.usernames else 0.6, extra={"username": h.username},
                ))
            unknown = sum(h.presence == Presence.UNKNOWN for h in hits)
            statuses.append(SourceStatus("Pseudonymes", True, len(found), (time.perf_counter() - t0) * 1000,
                                         f"{unknown} vérification(s) indéterminée(s)" if unknown else ""))

        deduped, removed = deduplicate(results)
        deduped.sort(key=lambda r: (-r.relevance, r.category, r.source))
        return OsintReport(
            query=q, started_at=started, finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            results=deduped, statuses=sorted(statuses, key=lambda s: s.source), links=build_links(q),
            duplicates_removed=removed,
        )
