"""Génération de rapports OSINT (HTML autonome + JSON)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from html import escape
from pathlib import Path

from face_analyse import __app_name__, __author__, __version__
from face_analyse.core.paths import reports_dir
from face_analyse.osint.models import OsintReport

DISCLAIMER = (
    "Ce rapport recense des pages publiques mentionnant le nom recherché. Une correspondance de nom "
    "ne prouve pas qu'il s'agit de la même personne (homonymes). Les informations doivent être "
    "vérifiées et leur usage doit respecter le RGPD et la vie privée des personnes concernées."
)

_CSS = """
:root{--bg:#050505;--fg:#e8e8e8;--muted:#8a8a8a;--line:#1e1e1e;--accent:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.5 "Segoe UI",system-ui,sans-serif;padding:40px 16px}
main{max-width:960px;margin:auto}h1{font-weight:200;letter-spacing:.35em;margin:0}
.sig{color:var(--muted);font-size:11px;letter-spacing:.3em}h2{font-weight:300;letter-spacing:.2em;
border-bottom:1px solid var(--line);padding-bottom:6px;margin-top:36px;font-size:15px;text-transform:uppercase}
table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid var(--line);padding:8px 6px;
text-align:left;vertical-align:top}th{color:var(--muted);font-weight:400;font-size:12px}
a{color:var(--accent)}.muted{color:var(--muted);font-size:12px}.warn{border:1px solid #333;padding:12px;
color:#cfcfcf;margin:18px 0}.pill{display:inline-block;border:1px solid #333;padding:0 6px;font-size:11px}
pre{white-space:pre-wrap;font:inherit}
"""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "recherche"


def render_html(rep: OsintReport) -> str:
    q = rep.query
    rows = []
    for r in rep.results:
        dup = f"<div class='muted'>aussi : {escape(', '.join(r.duplicates))}</div>" if r.duplicates else ""
        rows.append(
            f"<tr><td><span class='pill'>{escape(r.category)}</span><div class='muted'>{escape(r.source)}</div></td>"
            f"<td><a href='{escape(r.url)}' rel='noopener noreferrer'>{escape(r.title or r.url)}</a>"
            f"<div class='muted'>{escape(r.snippet)}</div>{dup}<div class='muted'>{escape(r.url)}</div></td>"
            f"<td>{r.relevance:.2f}</td><td class='muted'>{escape(r.retrieved_at)}</td></tr>"
        )
    status_rows = "".join(
        f"<tr><td>{escape(s.source)}</td><td>{'OK' if s.ok else 'ERREUR'}</td><td>{s.count}</td>"
        f"<td>{s.elapsed_ms:.0f} ms</td><td class='muted'>{escape(s.error)}</td></tr>" for s in rep.statuses
    )
    link_rows = "".join(
        f"<tr><td>{escape(link.category)}</td><td><a href='{escape(link.url)}' rel='noopener noreferrer'>{escape(link.platform)}</a>"
        f"<div class='muted'>{escape(link.note)}</div></td></tr>" for link in rep.links
    )
    ai = f"<h2>Synthèse IA</h2><div class='warn'><pre>{escape(rep.ai_summary)}</pre></div>" if rep.ai_summary else ""
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Rapport OSINT — {escape(q.full_name)}</title>
<style>{_CSS}</style></head><body><main>
<h1>{escape(__app_name__)}</h1><div class="sig">FAIT PAR {escape(__author__.upper())} · v{__version__}</div>
<h2>Rapport OSINT</h2>
<p>Recherche : <b>{escape(q.full_name)}</b>{(' · ' + escape(q.city)) if q.city else ''}
{(' · mots-clés : ' + escape(q.extra_keywords)) if q.extra_keywords else ''}<br>
<span class="muted">Début {escape(rep.started_at)} · fin {escape(rep.finished_at)} (UTC) · {len(rep.results)} résultat(s),
{rep.duplicates_removed} doublon(s) fusionné(s)</span></p>
<div class="warn">{escape(DISCLAIMER)}</div>{ai}
<h2>Résultats ({len(rep.results)})</h2>
<table><tr><th>Source</th><th>Résultat</th><th>Nom</th><th>Horodatage</th></tr>{''.join(rows) or '<tr><td colspan=4>Aucun résultat.</td></tr>'}</table>
<p class="muted">« Nom » = proportion du nom recherché retrouvée dans le résultat (1.00 = prénom et nom). Ce n'est pas une probabilité d'identité.</p>
<h2>Sources interrogées</h2><table><tr><th>Source</th><th>État</th><th>Résultats</th><th>Durée</th><th>Détail</th></tr>{status_rows}</table>
<h2>Recherches manuelles (navigateur)</h2>
<p class="muted">Plateformes sans API publique : non interrogées automatiquement.</p><table>{link_rows}</table>
</main></body></html>"""


def save_report(rep: OsintReport, folder: Path | None = None) -> tuple[Path, Path]:
    folder = folder or reports_dir()
    stamp = rep.started_at.replace(":", "").replace("-", "").replace("+0000", "")[:15]
    base = folder / f"osint_{_slug(rep.query.full_name)}_{stamp}"
    html_path, json_path = base.with_suffix(".html"), base.with_suffix(".json")
    html_path.write_text(render_html(rep), encoding="utf-8")
    json_path.write_text(json.dumps(asdict(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    return html_path, json_path
