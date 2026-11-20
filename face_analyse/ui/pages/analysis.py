"""FACE ANALYSIS : analyse d'une photo (tous les visages) et comparaison 1:1."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSplitter, QTabWidget, QTextBrowser, QVBoxLayout,
                               QWidget)

from face_analyse.engine.pipeline import ComparisonResult
from face_analyse.engine.preprocessing import SUPPORTED_EXTENSIONS, load_image
from face_analyse.engine.types import FaceAnalysis, MatchStatus
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import SIMILARITY_NOTICE, Page, muted, pick_images
from face_analyse.ui.widgets.image_view import ImageView, Overlay
from face_analyse.ui.workers import run_async


def _decision_html(i: int, a: FaceAnalysis) -> str:
    q = a.quality
    parts = [f"<h3 style='font-weight:300;letter-spacing:2px'>VISAGE #{i}</h3>"]
    parts.append(f"<span style='color:#888'>taille {q.face_size:.0f}px · netteté {q.sharpness:.0f} · "
                 f"luminosité {q.brightness:.0f} · rotation {q.yaw_ratio:.2f} · détection {q.detection_score:.2f} · "
                 f"qualité {q.score:.2f}</span>")
    for w in q.warnings:
        parts.append(f"<div style='color:#ffe9b0'>⚠ {w}</div>")
    d = a.decision
    if a.embedding is None:
        parts.append("<div style='color:#ff9a9a'>Empreinte non calculable pour ce visage.</div>")
    elif d is None:
        parts.append("<div>Recherche non effectuée.</div>")
    else:
        color = {"MATCH": "#ffffff", "AMBIGUOUS": "#ffe9b0", "UNKNOWN": "#ffb4b4"}[d.status.value]
        parts.append(f"<p style='color:{color};font-size:14pt;letter-spacing:2px'>{d.label}</p>")
        parts.append(f"<div style='color:#aaa'>{d.note}</div>")
        if d.candidates:
            rows = "".join(
                f"<tr><td>{c.display_name}</td><td style='font-family:monospace'>{c.similarity:+.3f}</td>"
                f"<td>{'≥ seuil' if c.similarity >= d.threshold else '< seuil'}</td></tr>"
                for c in d.candidates
            )
            title = ("Correspondances potentielles" if d.status != MatchStatus.UNKNOWN
                     else "Plus proches dans la base (toutes sous le seuil, aucune identité retenue)")
            parts.append(f"<div style='color:#888;margin-top:6px'>{title} — seuil {d.threshold:.3f}</div>"
                         f"<table cellpadding=3>{rows}</table>")
    return "".join(parts)


class AnalyzeTab(QWidget):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.open_btn = QPushButton("IMPORTER UNE PHOTO")
        self.open_btn.setObjectName("Primary")
        self.open_btn.clicked.connect(self._choose)
        self.info = QLabel("Glissez une photo ici ou importez-la.")
        self.info.setObjectName("Muted")
        bar.addWidget(self.open_btn)
        bar.addWidget(self.info, 1)
        lay.addLayout(bar)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.view = ImageView(placeholder="Aucune photo")
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(False)
        split.addWidget(self.view)
        split.addWidget(self.details)
        split.setSizes([640, 360])
        lay.addWidget(split, 1)
        lay.addWidget(muted(SIMILARITY_NOTICE))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in SUPPORTED_EXTENSIONS:
                self.analyze(path)
                break

    def _choose(self):
        files = pick_images(self)
        if files:
            self.analyze(files[0])

    def analyze(self, path: str):
        if self.ctx.engine is None:
            self.ctx.notify.emit("Moteur non chargé : " + (self.ctx.engine_error or "patientez…"), "warning")
            return
        self.open_btn.setEnabled(False)
        self.info.setText(f"Analyse de {Path(path).name}…")
        self.ctx.busy.emit("Analyse faciale…", 0, 0)

        engine = self.ctx.engine
        top_k = self.ctx.settings.engine.top_k

        def job():
            img = load_image(path)
            return img, engine.analyze(img, identify=True, top_k=top_k), engine.last_timings

        run_async(job, on_done=lambda r: self._done(path, r), on_error=self._error)

    def _error(self, msg: str):
        self.open_btn.setEnabled(True)
        self.info.setText(msg)
        self.ctx.busy.emit("", -1, -1)
        self.ctx.notify.emit(msg, "error")

    def _done(self, path: str, result):
        img, analyses, t = result
        analyses = sorted(analyses, key=lambda a: (a.face.x, a.face.y))  # numérotation de gauche à droite
        self.open_btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        self.view.set_image(img)
        overlays = []
        for i, a in enumerate(analyses, start=1):
            d = a.decision
            label = d.label if d else "?"
            sub = f"sim {d.candidates[0].similarity:+.3f}" if d and d.candidates else ""
            overlays.append(Overlay(a.face.box, label, sub, known=bool(d and d.identity), index=i))
        self.view.set_overlays(overlays)
        n = len(analyses)
        known = sum(1 for a in analyses if a.decision and a.decision.identity)
        self.info.setText(f"{Path(path).name} — {n} visage(s) détecté(s), {known} correspondance(s) "
                          f"· détection {t.detection_ms:.0f} ms · empreintes {t.embedding_ms:.0f} ms · recherche {t.search_ms:.1f} ms")
        if not analyses:
            self.details.setHtml("<p>Aucun visage détecté.</p><p style='color:#888'>Essayez une photo plus nette, "
                                 "mieux éclairée ou où le visage est plus grand.</p>")
        else:
            gal = self.ctx.engine.matcher.person_count if self.ctx.engine else 0
            head = f"<p style='color:#888'>Base consentante : {gal} personne(s).</p>"
            self.details.setHtml(head + "<hr>".join(_decision_html(i, a) for i, a in enumerate(analyses, start=1)))
        self.ctx.repo.log_history("analysis", "photo_analyzed", f"{Path(path).name} : {n} visage(s), {known} correspondance(s)",
                                  {"file": Path(path).name, "faces": n,
                                   "labels": [a.decision.label if a.decision else None for a in analyses]})
        self.ctx.log_event("analysis", "photo_analyzed", {"faces": n, "known": known})


class CompareTab(QWidget):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.paths: list[str | None] = [None, None]
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.views = [ImageView(placeholder="Photo A"), ImageView(placeholder="Photo B")]
        for i, v in enumerate(self.views):
            col = QVBoxLayout()
            btn = QPushButton(f"CHOISIR PHOTO {'AB'[i]}")
            btn.clicked.connect(lambda _=False, idx=i: self._choose(idx))
            col.addWidget(btn)
            col.addWidget(v, 1)
            row.addLayout(col, 1)
        lay.addLayout(row, 1)
        self.compare_btn = QPushButton("COMPARER")
        self.compare_btn.setObjectName("Primary")
        self.compare_btn.clicked.connect(self._compare)
        self.result = QLabel("Choisissez deux photos contenant chacune un visage.")
        self.result.setWordWrap(True)
        self.result.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.compare_btn, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self.result)
        lay.addWidget(muted(SIMILARITY_NOTICE))

    def _choose(self, idx: int):
        files = pick_images(self)
        if not files:
            return
        try:
            self.views[idx].set_image(load_image(files[0]))
            self.views[idx].set_overlays([])
            self.paths[idx] = files[0]
        except Exception as exc:  # noqa: BLE001
            self.ctx.notify.emit(str(exc), "error")

    def _compare(self):
        if self.ctx.engine is None:
            self.ctx.notify.emit("Moteur non chargé.", "warning")
            return
        if not all(self.paths):
            self.ctx.notify.emit("Choisissez deux photos.", "warning")
            return
        engine = self.ctx.engine
        a, b = self.paths
        self.compare_btn.setEnabled(False)
        self.ctx.busy.emit("Comparaison…", 0, 0)
        run_async(lambda: engine.compare(load_image(a), load_image(b)), on_done=self._done, on_error=self._error)

    def _error(self, msg):
        self.compare_btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        self.result.setText(f"<span style='color:#ff9a9a'>{msg}</span>")

    def _done(self, r: ComparisonResult):
        self.compare_btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        for v, fa in zip(self.views, (r.face_a, r.face_b)):
            v.set_overlays([Overlay(fa.face.box, "visage comparé", known=r.above_threshold)])
        warn = "".join(f"<br><span style='color:#ffe9b0'>⚠ {w}</span>"
                       for w in r.face_a.quality.warnings + r.face_b.quality.warnings)
        self.result.setText(
            f"<span style='font-size:20pt;font-weight:200;letter-spacing:3px'>{r.similarity:+.3f}</span>"
            f"&nbsp;&nbsp;<span style='color:#888'>seuil {r.threshold:.3f}</span><br>{r.verdict}{warn}"
        )
        self.ctx.repo.log_history("analysis", "compare", f"Comparaison 1:1 — similarité {r.similarity:+.3f}",
                                  {"similarity": r.similarity, "threshold": r.threshold})


class AnalysisPage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("FACE ANALYSIS",
                         "Détection de tous les visages d'une photo, empreinte faciale et recherche dans la base locale "
                         "consentante. Un visage absent de la base est toujours affiché UNKNOWN.", parent, help_key="analysis")
        tabs = QTabWidget()
        tabs.addTab(AnalyzeTab(ctx), "ANALYSER")
        tabs.addTab(CompareTab(ctx), "COMPARER DEUX VISAGES")
        self.root.addWidget(tabs, 1)
