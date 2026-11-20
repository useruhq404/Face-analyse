"""Export PDF d'un rapport OSINT (Qt, sans dépendance externe).

Rendu lisible à l'impression (fond clair, monochrome) via ``QTextDocument`` +
``QPdfWriter``. Import Qt différé pour garder le module OSINT utilisable sans
interface.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from face_analyse import __app_name__, __signature__, __version__
from face_analyse.osint.models import OsintReport
from face_analyse.osint.report import DISCLAIMER

_PDF_CSS = """
body { font-family: sans-serif; color: #111; }
h1 { letter-spacing: 3px; font-weight: normal; }
h2 { border-bottom: 1px solid #999; padding-bottom: 3px; margin-top: 18px; font-size: 13pt; }
.muted { color: #666; }
table { width: 100%; border-collapse: collapse; }
td, th { border-bottom: 1px solid #ccc; padding: 4px 6px; text-align: left; font-size: 9pt; }
.warn { border: 1px solid #bbb; padding: 8px; color: #333; }
"""


def render_pdf_html(rep: OsintReport) -> str:
    q = rep.query
    rows = "".join(
        f"<tr><td>{escape(r.category)}<br><span class='muted'>{escape(r.source)}</span></td>"
        f"<td>{escape(r.title or r.url)}<br><span class='muted'>{escape(r.snippet)}</span><br>"
        f"<span class='muted'>{escape(r.url)}</span></td><td>{r.relevance:.2f}</td></tr>"
        for r in rep.results
    )
    ai = f"<h2>Synthèse IA</h2><div class='warn'>{escape(rep.ai_summary)}</div>" if rep.ai_summary else ""
    return f"""<html><head><style>{_PDF_CSS}</style></head><body>
    <h1>{escape(__app_name__)}</h1>
    <div class='muted'>{escape(__signature__)} · v{__version__} · Rapport OSINT</div>
    <p>Recherche : <b>{escape(q.full_name)}</b>{(' · ' + escape(q.city)) if q.city else ''}<br>
    <span class='muted'>Début {escape(rep.started_at)} · fin {escape(rep.finished_at)} (UTC) ·
    {len(rep.results)} résultat(s)</span></p>
    <div class='warn'>{escape(DISCLAIMER)}</div>{ai}
    <h2>Résultats ({len(rep.results)})</h2>
    <table><tr><th>Source</th><th>Résultat</th><th>Nom</th></tr>{rows or '<tr><td colspan=3>Aucun résultat.</td></tr>'}</table>
    <p class='muted'>« Nom » = proportion du nom recherché retrouvée (1.00 = prénom et nom). Pas une probabilité d'identité.</p>
    </body></html>"""


def save_pdf(rep: OsintReport, path: str | Path) -> Path:
    from PySide6.QtGui import QPageSize, QTextDocument
    from PySide6.QtPrintSupport import QPrinter

    path = Path(path)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setOutputFileName(str(path))
    doc = QTextDocument()
    doc.setHtml(render_pdf_html(rep))
    doc.print_(printer)
    return path
