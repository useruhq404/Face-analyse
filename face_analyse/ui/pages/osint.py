"""OSINT SEARCH : recherche par nom dans des sources publiques autorisées."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QGridLayout, QHBoxLayout, QHeaderView, QLineEdit, QPushButton, QSplitter,
                               QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from face_analyse.osint.aggregator import OsintEngine
from face_analyse.osint.assistant import ResearchAssistant, Suggestions
from face_analyse.osint.links import build_links
from face_analyse.osint.models import OsintQuery, OsintReport
from face_analyse.osint.report import DISCLAIMER, save_report
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import Page, muted
from face_analyse.ui.workers import run_async


class OsintPage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("OSINT SEARCH",
                         "Recherche à partir d'un nom et d'un prénom dans des sources publiques officielles. "
                         "Aucune recherche par visage. Les réseaux sociaux sans API publique sont proposés en liens "
                         "à ouvrir vous-même.", parent, help_key="osint")
        self.ctx = ctx
        self.report: OsintReport | None = None

        grid = QGridLayout()
        self.first = QLineEdit(placeholderText="Prénom")
        self.last = QLineEdit(placeholderText="Nom")
        self.city = QLineEdit(placeholderText="Ville (facultatif)")
        self.keywords = QLineEdit(placeholderText="Mots-clés (facultatif : métier, entreprise…)")
        self.handles = QLineEdit(placeholderText="Pseudonymes connus, séparés par des virgules (facultatif)")
        grid.addWidget(self.first, 0, 0)
        grid.addWidget(self.last, 0, 1)
        grid.addWidget(self.city, 0, 2)
        grid.addWidget(self.keywords, 1, 0, 1, 2)
        grid.addWidget(self.handles, 1, 2)
        self.root.addLayout(grid)

        bar = QHBoxLayout()
        self.search_btn = QPushButton("RECHERCHER")
        self.search_btn.setObjectName("Primary")
        self.search_btn.clicked.connect(self.search)
        self.check_handles = QCheckBox("Vérifier les pseudonymes")
        self.check_handles.setChecked(ctx.settings.osint.username_check)
        self.ai_suggest_btn = QPushButton("IA · SUGGÉRER DES PISTES")
        self.ai_suggest_btn.clicked.connect(self.ai_suggest)
        self.ai_summary_btn = QPushButton("IA · SYNTHÈSE")
        self.ai_summary_btn.clicked.connect(self.ai_summarize)
        self.export_btn = QPushButton("EXPORTER (HTML/JSON)")
        self.export_btn.clicked.connect(self.export)
        self.pdf_btn = QPushButton("EXPORTER PDF")
        self.pdf_btn.clicked.connect(self.export_pdf)
        for w in (self.search_btn, self.check_handles, self.ai_suggest_btn, self.ai_summary_btn,
                  self.export_btn, self.pdf_btn):
            bar.addWidget(w)
        bar.addStretch(1)
        self.root.addLayout(bar)
        for w in (self.first, self.last, self.city, self.keywords, self.handles):
            w.returnPressed.connect(self.search)

        tabs = QTabWidget()
        # Résultats
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Catégorie", "Source", "Résultat", "Nom", "URL"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(self._open_row)
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(True)
        self.detail.document().setDefaultStyleSheet('a{color:#ffffff;text-decoration:underline}')
        self.detail.setMaximumHeight(130)
        self.table.currentCellChanged.connect(lambda r, *_: self._show_detail(r))
        res = QWidget()
        rl = QVBoxLayout(res)
        rl.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.table)
        split.addWidget(self.detail)
        rl.addWidget(split)
        tabs.addTab(res, "RÉSULTATS")
        # Liens navigateur
        self.links = QTreeWidget()
        self.links.setHeaderLabels(["Plateforme", "Remarque"])
        self.links.itemDoubleClicked.connect(lambda it, _c: self._open_url(it.data(0, Qt.ItemDataRole.UserRole)))
        lw = QWidget()
        ll = QVBoxLayout(lw)
        ll.addWidget(muted("Double-cliquez pour ouvrir la recherche dans votre navigateur. Ces plateformes ne sont "
                           "jamais interrogées automatiquement par l'application."))
        ll.addWidget(self.links)
        tabs.addTab(lw, "RÉSEAUX SOCIAUX · ANNUAIRES")
        # Sources
        self.sources = QTableWidget(0, 4)
        self.sources.setHorizontalHeaderLabels(["Source", "État", "Résultats", "Détail"])
        self.sources.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.sources.verticalHeader().setVisible(False)
        self.sources.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabs.addTab(self.sources, "SOURCES")
        # IA
        self.ai = QTextBrowser()
        self.ai.setOpenExternalLinks(True)
        tabs.addTab(self.ai, "ASSISTANT IA")
        self.tabs = tabs
        self.root.addWidget(tabs, 1)
        self.root.addWidget(muted(DISCLAIMER))
        self._set_enabled(True)

    # ------------------------------------------------------------ utilitaires
    def _query(self) -> OsintQuery:
        handles = tuple(h.strip().lstrip("@") for h in self.handles.text().split(",") if h.strip())
        return OsintQuery(self.first.text().strip(), self.last.text().strip(), self.city.text().strip(),
                          self.keywords.text().strip(), handles)

    def _set_enabled(self, on: bool):
        self.search_btn.setEnabled(on)
        self.ai_suggest_btn.setEnabled(on)
        self.ai_summary_btn.setEnabled(on and self.report is not None)
        self.export_btn.setEnabled(on and self.report is not None)
        self.pdf_btn.setEnabled(on and self.report is not None)

    def _secrets(self) -> dict[str, str]:
        return {"openalex_api_key": self.ctx.repo.get_secret("openalex_api_key")}

    @staticmethod
    def _open_url(url: str | None):
        if url and url.startswith("https://"):
            QDesktopServices.openUrl(QUrl(url))

    # ------------------------------------------------------------ recherche
    def search(self):
        q = self._query()
        try:
            q.validate()
        except Exception as exc:  # noqa: BLE001
            self.ctx.notify.emit(str(exc), "warning")
            return
        self._set_enabled(False)
        self._fill_links(q)
        s = self.ctx.settings.osint
        engine = OsintEngine(timeout_s=s.timeout_s, secrets=self._secrets(), enabled_sources=s.enabled_sources or None)
        check = self.check_handles.isChecked()
        run_async(lambda progress: engine.run(q, check_handles=check, progress=progress),
                  on_done=self._done, on_error=self._error, on_progress=lambda l, d, n: self.ctx.busy.emit(l, d, n))
        self.ctx.busy.emit("Recherche OSINT…", 0, 0)

    def _error(self, msg):
        self._set_enabled(True)
        self.ctx.busy.emit("", -1, -1)
        self.ctx.notify.emit(msg, "error")

    def _done(self, rep: OsintReport):
        self.report = rep
        self._set_enabled(True)
        self.ctx.busy.emit("", -1, -1)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rep.results))
        for i, r in enumerate(rep.results):
            cells = [r.category, r.source + (f" (+{len(r.duplicates)})" if r.duplicates else ""), r.title,
                     f"{r.relevance:.2f}", r.url]
            for j, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, i)
                self.table.setItem(i, j, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.sources.setRowCount(len(rep.statuses))
        for i, s in enumerate(rep.statuses):
            for j, text in enumerate([s.source, "OK" if s.ok else "ERREUR", str(s.count), s.error or f"{s.elapsed_ms:.0f} ms"]):
                self.sources.setItem(i, j, QTableWidgetItem(text))
        errors = sum(1 for s in rep.statuses if not s.ok)
        self.ctx.notify.emit(f"{len(rep.results)} résultat(s), {rep.duplicates_removed} doublon(s) fusionné(s)"
                             + (f", {errors} source(s) en erreur" if errors else ""), "warning" if errors else "success")
        self.ctx.repo.log_history("osint", "search", f"Recherche « {rep.query.full_name} » : {len(rep.results)} résultat(s)",
                                  {"query": rep.query.full_name, "city": rep.query.city, "results": len(rep.results),
                                   "started_at": rep.started_at, "errors": errors})
        self.ctx.log_event("osint", "search", {"results": len(rep.results), "errors": errors})

    def _fill_links(self, q: OsintQuery):
        self.links.clear()
        groups: dict[str, QTreeWidgetItem] = {}
        for link in build_links(q):
            parent = groups.get(link.category)
            if parent is None:
                parent = QTreeWidgetItem([link.category.upper(), ""])
                self.links.addTopLevelItem(parent)
                groups[link.category] = parent
            child = QTreeWidgetItem([link.platform, link.note])
            child.setData(0, Qt.ItemDataRole.UserRole, link.url)
            child.setToolTip(0, link.url)
            parent.addChild(child)
        self.links.expandAll()
        self.links.resizeColumnToContents(0)

    def _row_result(self, row: int):
        if self.report is None or row < 0:
            return None
        item = self.table.item(row, 0)
        return self.report.results[item.data(Qt.ItemDataRole.UserRole)] if item else None

    def _show_detail(self, row: int):
        r = self._row_result(row)
        if r is None:
            return
        extra = " · ".join(f"{k} : {v}" for k, v in r.extra.items())
        dup = f"<br>Également trouvé via : {', '.join(r.duplicates)}" if r.duplicates else ""
        self.detail.setHtml(f"<b>{r.title}</b><br>{r.snippet}<br><a href='{r.url}'>{r.url}</a><br>"
                            f"<span style='color:#888'>{r.source} · récupéré le {r.retrieved_at} · {extra}{dup}</span>")

    def _open_row(self, row: int, _col: int):
        r = self._row_result(row)
        if r:
            self._open_url(r.url)

    # ------------------------------------------------------------ IA
    def _assistant(self) -> ResearchAssistant | None:
        key = self.ctx.repo.get_secret("anthropic_api_key")
        if not key:
            self.ctx.notify.emit("Ajoutez votre clé API Claude dans SETTINGS pour utiliser l'assistant IA.", "warning")
            return None
        return ResearchAssistant(key, self.ctx.settings.osint.ai_model)

    def ai_suggest(self):
        q = self._query()
        try:
            q.validate()
        except Exception as exc:  # noqa: BLE001
            self.ctx.notify.emit(str(exc), "warning")
            return
        assistant = self._assistant()
        if assistant is None:
            return
        self._set_enabled(False)
        self.ctx.busy.emit("Assistant IA : suggestions…", 0, 0)
        run_async(assistant.suggest, q, on_done=self._suggested, on_error=self._error)

    def _suggested(self, s: Suggestions):
        self._set_enabled(True)
        self.ctx.busy.emit("", -1, -1)
        li = lambda xs: "".join(f"<li>{x}</li>" for x in xs) or "<li>—</li>"  # noqa: E731
        self.ai.setHtml(f"<h3>Variantes du nom</h3><ul>{li(s.name_variants)}</ul>"
                        f"<h3>Pseudonymes plausibles</h3><ul>{li(s.usernames)}</ul>"
                        f"<h3>Pistes de recherche</h3><ul>{li(s.search_ideas)}</ul>"
                        f"<p style='color:#ffe9b0'>{s.caution}</p>"
                        "<p style='color:#888'>Suggestions générées par IA : hypothèses à vérifier, pas des faits.</p>")
        if s.usernames:
            existing = [h.strip() for h in self.handles.text().split(",") if h.strip()]
            merged = list(dict.fromkeys(existing + s.usernames[:5]))
            self.handles.setText(", ".join(merged))
        self.tabs.setCurrentIndex(3)

    def ai_summarize(self):
        if self.report is None:
            return
        assistant = self._assistant()
        if assistant is None:
            return
        self._set_enabled(False)
        self.ctx.busy.emit("Assistant IA : synthèse…", 0, 0)
        run_async(assistant.summarize, self.report, on_done=self._summarized, on_error=self._error)

    def _summarized(self, text: str):
        self._set_enabled(True)
        self.ctx.busy.emit("", -1, -1)
        if self.report is not None:
            self.report.ai_summary = text
        self.ai.setMarkdown(text + "\n\n---\n*Synthèse générée par IA à partir des seuls résultats collectés : à vérifier.*")
        self.tabs.setCurrentIndex(3)

    # ------------------------------------------------------------ export
    def export(self):
        if self.report is None:
            return
        try:
            html_path, json_path = save_report(self.report)
        except OSError as exc:
            self.ctx.notify.emit(f"Export impossible : {exc}", "error")
            return
        self.ctx.repo.log_history("osint", "report", f"Rapport exporté : {html_path.name}", {"html": str(html_path), "json": str(json_path)})
        self.ctx.notify.emit(f"Rapport enregistré : {html_path}", "success")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(html_path)))

    def export_pdf(self):
        if self.report is None:
            return
        from face_analyse.core.paths import reports_dir
        from face_analyse.osint.pdf import save_pdf
        from face_analyse.osint.report import _slug

        stamp = self.report.started_at.replace(":", "").replace("-", "").replace("+0000", "")[:15]
        path = reports_dir() / f"osint_{_slug(self.report.query.full_name)}_{stamp}.pdf"
        try:
            save_pdf(self.report, path)
        except Exception as exc:  # noqa: BLE001 - l'export ne doit pas planter l'app
            self.ctx.notify.emit(f"Export PDF impossible : {exc}", "error")
            return
        self.ctx.repo.log_history("osint", "report_pdf", f"Rapport PDF exporté : {path.name}", {"pdf": str(path)})
        self.ctx.notify.emit(f"PDF enregistré : {path}", "success")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
