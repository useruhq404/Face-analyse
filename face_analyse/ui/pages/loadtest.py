"""STRESS TEST — test de charge de TES propres cibles (mesure de performance).

Envoie des requêtes concurrentes vers une URL que tu possèdes / es autorisé à
tester, et affiche des métriques réelles (débit, latence p50/p90/p99, codes,
erreurs) + un histogramme de latence. Garde-fou : toute cible non locale exige
la confirmation « cette cible m'appartient ».

Ce n'est pas un outil d'attaque : viser un système tiers pour le saturer est un
déni de service, illégal (France : art. 323-2).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from face_analyse.loadtest.engine import LoadConfig, combined_latencies, is_local_target, run_many
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import Page, card, muted, section_label
from face_analyse.ui.widgets.charts import Histogram
from face_analyse.ui.workers import run_async


class LoadTestPage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("STRESS TEST",
                         "Test de charge de tes propres services : débit, latence (p50/p90/p99), point de "
                         "rupture. Cible non locale → confirmation d'autorisation requise.", parent)
        self.ctx = ctx

        body = QHBoxLayout()
        body.setSpacing(16)

        # ---- panneau de configuration
        cfg_card, cfg = card()
        cfg.addWidget(section_label("Configuration"))
        form = QFormLayout()
        self.urls = QPlainTextEdit()
        self.urls.setPlaceholderText("une URL par ligne — testées en même temps\nhttp://127.0.0.1:8090/\nhttp://127.0.0.1:8091/")
        self.urls.setFixedHeight(84)
        form.addRow("Cibles", self.urls)
        self.method = QComboBox()
        self.method.addItems(["GET", "POST", "HEAD", "PUT"])
        form.addRow("Méthode", self.method)
        self.concurrency = QSpinBox(minimum=1, maximum=500, value=50)
        form.addRow("Concurrence", self.concurrency)
        self.mode = QComboBox()
        self.mode.addItems(["Durée (s)", "Nombre de requêtes"])
        self.mode.currentIndexChanged.connect(self._mode_changed)
        form.addRow("Mode", self.mode)
        self.duration = QSpinBox(minimum=1, maximum=120, value=10)
        form.addRow("Durée (s)", self.duration)
        self.requests = QSpinBox(minimum=1, maximum=200000, value=2000, singleStep=500)
        self.requests.setEnabled(False)
        form.addRow("Requêtes", self.requests)
        self.ramp = QSpinBox(minimum=0, maximum=60, value=0)
        form.addRow("Montée en charge (s)", self.ramp)
        self.rps = QSpinBox(minimum=0, maximum=100000, value=0, singleStep=100)
        form.addRow("Plafond débit (req/s, 0=aucun)", self.rps)
        self.timeout = QSpinBox(minimum=1, maximum=60, value=10)
        form.addRow("Timeout (s)", self.timeout)
        cfg.addLayout(form)
        self.authorized = QCheckBox("Je possède cette cible ou suis autorisé à la tester")
        cfg.addWidget(self.authorized)
        self.run_btn = QPushButton("LANCER LE TEST")
        self.run_btn.setObjectName("Primary")
        self.run_btn.clicked.connect(self.run_test)
        cfg.addWidget(self.run_btn)
        cfg.addStretch(1)
        cfg_card.setFixedWidth(340)
        body.addWidget(cfg_card)

        # ---- résultats
        right = QVBoxLayout()
        right.setSpacing(10)
        res_card, rl = card()
        rl.addWidget(section_label("Résultats"))
        self.summary = QLabel("Aucun test lancé.")
        self.summary.setObjectName("Mono")
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        rl.addWidget(self.summary)
        right.addWidget(res_card)
        hist_card, hl = card()
        hl.addWidget(section_label("Distribution de latence (ms)"))
        self.hist = Histogram()
        hl.addWidget(self.hist)
        right.addWidget(hist_card)
        right.addStretch(1)
        right.addWidget(muted("Outil de mesure, à but éducatif. Ne vise que tes propres systèmes. "
                              "Saturer un système tiers est un déni de service (illégal)."))
        body.addLayout(right, 1)
        self.root.addLayout(body, 1)

    def _mode_changed(self, idx: int):
        by_duration = idx == 0
        self.duration.setEnabled(by_duration)
        self.requests.setEnabled(not by_duration)

    def run_test(self):
        urls = [u.strip() for u in self.urls.toPlainText().splitlines() if u.strip()]
        if not urls:
            self.ctx.notify.emit("Saisissez au moins une URL (une par ligne).", "warning")
            return
        bad = [u for u in urls if not u.startswith(("http://", "https://"))]
        if bad:
            self.ctx.notify.emit(f"URL invalide : {bad[0]} (doit commencer par http:// ou https://).", "warning")
            return
        non_local = [u for u in urls if not is_local_target(u)]
        if non_local and not self.authorized.isChecked():
            self.ctx.notify.emit(f"{len(non_local)} cible(s) non locale(s) : cochez « je possède / suis autorisé » "
                                 "— sinon c'est un déni de service illégal.", "warning")
            return

        cfgs = []
        for u in urls:
            cfg = LoadConfig(url=u, method=self.method.currentText(), concurrency=self.concurrency.value(),
                             timeout=float(self.timeout.value()), ramp=float(self.ramp.value()), rps=self.rps.value())
            if self.mode.currentIndex() == 0:
                cfg.duration = float(self.duration.value())
            else:
                cfg.requests = self.requests.value()
            cfgs.append(cfg)

        self.run_btn.setEnabled(False)
        self.summary.setText(f"Test de {len(cfgs)} cible(s) en cours…")
        self.ctx.busy.emit("Test de charge…", 0, 0)
        run_async(run_many, cfgs, on_done=self._done, on_error=self._error)
        self.ctx.log_event("loadtest", "run", {"targets": len(cfgs), "concurrency": self.concurrency.value()})

    def _error(self, msg: str):
        self.run_btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        self.summary.setText(msg)
        self.ctx.notify.emit(msg, "error")

    def _done(self, pairs):
        self.run_btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        blocks = []
        for cfg, res in pairs:
            lines = [f"▸ {cfg.url}",
                     f"    débit {res.rps:,.1f} req/s · requêtes {res.total} (ok {res.ok}, err {res.failed})"]
            if res.latencies:
                lines.append(f"    latence ms  p50 {res.pct(50):.1f} · p90 {res.pct(90):.1f} · "
                             f"p99 {res.pct(99):.1f} · max {max(res.latencies):.1f}")
            if res.status:
                lines.append("    codes  " + "  ".join(f"{c}:{n}" for c, n in sorted(res.status.items())))
            if res.errors:
                lines.append("    erreurs  " + "  ".join(f"{k}:{v}" for k, v in res.errors.items()))
            if res.failed and res.failed / max(res.total, 1) > 0.05:
                lines.append("    ⚠ saturation / ralentissement / limite de débit")
            blocks.append("\n".join(lines))
        agg = combined_latencies(pairs)
        header = f"{len(pairs)} cible(s) · {agg.total} requêtes au total\n"
        self.summary.setText(header + "\n\n".join(blocks))
        self.hist.set_data(agg.latency_histogram(12))
        self.ctx.repo.log_history("loadtest", "run",
                                  f"Stress test : {len(pairs)} cible(s), {agg.total} requêtes au total",
                                  {"targets": len(pairs), "total": agg.total})
