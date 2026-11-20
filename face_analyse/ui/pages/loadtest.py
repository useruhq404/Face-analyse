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
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from face_analyse.loadtest.engine import LoadConfig, Results, is_local_target, run
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
        self.url = QLineEdit(placeholderText="http://127.0.0.1:8090/")
        form.addRow("Cible (URL)", self.url)
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
        url = self.url.text().strip()
        if not url.startswith(("http://", "https://")):
            self.ctx.notify.emit("Saisissez une URL http(s) valide.", "warning")
            return
        if not is_local_target(url) and not self.authorized.isChecked():
            self.ctx.notify.emit("Cible non locale : cochez « Je possède cette cible / suis autorisé » "
                                 "— sinon c'est un déni de service illégal.", "warning")
            return
        cfg = LoadConfig(
            url=url, method=self.method.currentText(), concurrency=self.concurrency.value(),
            timeout=float(self.timeout.value()), ramp=float(self.ramp.value()), rps=self.rps.value(),
        )
        if self.mode.currentIndex() == 0:
            cfg.duration = float(self.duration.value())
        else:
            cfg.requests = self.requests.value()
        self.run_btn.setEnabled(False)
        self.summary.setText("Test en cours…")
        self.ctx.busy.emit("Test de charge…", 0, 0)
        run_async(run, cfg, on_done=self._done, on_error=self._error)
        self.ctx.log_event("loadtest", "run", {"concurrency": cfg.concurrency, "local": is_local_target(url)})

    def _error(self, msg: str):
        self.run_btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        self.summary.setText(msg)
        self.ctx.notify.emit(msg, "error")

    def _done(self, res: Results):
        self.run_btn.setEnabled(True)
        self.ctx.busy.emit("", -1, -1)
        lines = [
            f"débit        {res.rps:,.1f} req/s",
            f"requêtes     {res.total}   (ok {res.ok}, erreurs {res.failed})",
            f"durée        {res.duration:.1f} s",
        ]
        if res.latencies:
            lines.append(f"latence ms   moy {res.mean_latency:.1f} · p50 {res.pct(50):.1f} · "
                         f"p90 {res.pct(90):.1f} · p99 {res.pct(99):.1f} · max {max(res.latencies):.1f}")
        if res.status:
            lines.append("codes        " + "  ".join(f"{c}:{n}" for c, n in sorted(res.status.items())))
        if res.errors:
            lines.append("erreurs      " + "  ".join(f"{k}:{v}" for k, v in res.errors.items()))
        if res.failed and res.failed / max(res.total, 1) > 0.05:
            lines.append("⚠ beaucoup d'erreurs : la cible sature, ralentit ou limite le débit.")
        self.summary.setText("\n".join(lines))
        self.hist.set_data(res.latency_histogram(12))
        self.ctx.repo.log_history("loadtest", "run",
                                  f"Stress test : {res.total} req, {res.rps:.0f} req/s, p99 {res.pct(99):.0f} ms",
                                  {"rps": round(res.rps, 1), "total": res.total})
