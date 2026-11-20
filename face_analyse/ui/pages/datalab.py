"""DATA LAB — exploration de jeux de données (CSV, JSON, TXT).

Import réel, aperçu tabulaire, statistiques par colonne, histogrammes,
détection de doublons et de valeurs manquantes. Aucune conclusion inventée :
sous l'échantillon minimal, la non-fiabilité est signalée.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
                               QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from face_analyse.dataset import analysis as A
from face_analyse.dataset.loader import Dataset, load
from face_analyse.ui.context import AppContext
from face_analyse.ui.pages.common import Page, card, muted, section_label
from face_analyse.ui.widgets.charts import BarList, Histogram
from face_analyse.ui.workers import run_async

PREVIEW_ROWS = 500


class DataLabPage(Page):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__("DATA LAB",
                         "Importez un jeu de données (CSV, TSV, JSON, TXT) : aperçu, statistiques, "
                         "histogrammes, doublons et valeurs manquantes — sur vos données réelles.", parent)
        self.ctx = ctx
        self.dataset: Dataset | None = None

        bar = QHBoxLayout()
        self.import_btn = QPushButton("IMPORTER UN JEU DE DONNÉES")
        self.import_btn.setObjectName("Primary")
        self.import_btn.clicked.connect(self._choose)
        self.info = muted("Aucun jeu de données chargé.")
        self.filter = QLineEdit(placeholderText="Filtrer les lignes…")
        self.filter.setMaximumWidth(240)
        self.filter.textChanged.connect(self._apply_filter)
        bar.addWidget(self.import_btn)
        bar.addWidget(self.info, 1)
        bar.addWidget(self.filter)
        self.root.addLayout(bar)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget()
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        split.addWidget(self.table)

        panel = QWidget()
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(10)
        ov, ol = card()
        ol.addWidget(section_label("Aperçu du jeu"))
        self.ov_rows = QLabel("—")
        self.ov_rows.setObjectName("Mono")
        self.ov_missing = QLabel("—")
        self.ov_missing.setObjectName("Mono")
        self.ov_dup = QLabel("—")
        self.ov_dup.setObjectName("Mono")
        for w in (self.ov_rows, self.ov_missing, self.ov_dup):
            ol.addWidget(w)
        pl.addWidget(ov)

        col_row = QHBoxLayout()
        col_row.addWidget(QLabel("Colonne :"))
        self.col_combo = QComboBox()
        self.col_combo.currentTextChanged.connect(self._show_column)
        col_row.addWidget(self.col_combo, 1)
        pl.addLayout(col_row)
        self.col_stats = QLabel("")
        self.col_stats.setObjectName("Mono")
        self.col_stats.setWordWrap(True)
        pl.addWidget(self.col_stats)
        self.reliability = QLabel("")
        self.reliability.setObjectName("Warn")
        self.reliability.setWordWrap(True)
        pl.addWidget(self.reliability)
        self.hist = Histogram()
        self.bars = BarList(max_rows=8)
        pl.addWidget(self.hist)
        pl.addWidget(self.bars)
        pl.addStretch(1)
        panel.setMinimumWidth(320)
        split.addWidget(panel)
        split.setSizes([720, 360])
        self.root.addWidget(split, 1)
        self._clear_panel()

    # ------------------------------------------------------------ import
    def _choose(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importer un jeu de données", "",
                                             "Données (*.csv *.tsv *.json *.txt)")
        if path:
            self.load_path(path)

    def load_path(self, path: str):
        self.import_btn.setEnabled(False)
        self.info.setText(f"Chargement de {Path(path).name}…")
        run_async(load, path, on_done=self._loaded, on_error=self._error)

    def _error(self, msg: str):
        self.import_btn.setEnabled(True)
        self.info.setText(msg)
        self.ctx.notify.emit(msg, "error")

    def _loaded(self, ds: Dataset):
        self.import_btn.setEnabled(True)
        self.dataset = ds
        trunc = f" · aperçu {PREVIEW_ROWS} lignes" if ds.n_rows > PREVIEW_ROWS else ""
        extra = " · tronqué à 100 000 lignes" if ds.truncated else ""
        self.info.setText(f"{ds.name} — {ds.source_format} · {ds.n_rows} lignes × {ds.n_cols} colonnes{trunc}{extra}")
        self._fill_table()
        ov = A.overview(ds)
        self.ov_rows.setText(f"{ov['rows']} lignes · {ov['cols']} colonnes")
        self.ov_missing.setText(f"valeurs manquantes : {ov['missing_cells']} ({ov['missing_ratio']*100:.1f} %)")
        self.ov_dup.setText(f"lignes en double : {ov['duplicates']}")
        self.col_combo.blockSignals(True)
        self.col_combo.clear()
        self.col_combo.addItems(ds.columns)
        self.col_combo.blockSignals(False)
        if ds.columns:
            self._show_column(ds.columns[0])
        self.ctx.repo.log_history("datalab", "import",
                                  f"Data Lab : {ds.name} ({ds.n_rows}×{ds.n_cols})",
                                  {"format": ds.source_format, "rows": ds.n_rows, "cols": ds.n_cols})
        self.ctx.log_event("datalab", "import", {"rows": ds.n_rows, "cols": ds.n_cols})

    def _fill_table(self):
        ds = self.dataset
        assert ds is not None
        self.table.setSortingEnabled(False)
        rows = ds.rows[:PREVIEW_ROWS]
        self.table.setColumnCount(ds.n_cols)
        self.table.setRowCount(len(rows))
        self.table.setHorizontalHeaderLabels(ds.columns)
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

    def _apply_filter(self, text: str):
        text = text.strip().lower()
        for r in range(self.table.rowCount()):
            visible = not text or any(
                text in (self.table.item(r, c).text().lower() if self.table.item(r, c) else "")
                for c in range(self.table.columnCount()))
            self.table.setRowHidden(r, not visible)

    # ------------------------------------------------------------ colonne
    def _clear_panel(self):
        self.col_stats.setText("Importez un jeu de données pour l'explorer.")
        self.reliability.setText("")
        self.hist.set_data([])
        self.bars.set_data([])

    def _show_column(self, name: str):
        if self.dataset is None or not name:
            return
        s = A.column_stats(self.dataset, name)
        lines = [f"type : {s.kind}", f"valeurs : {s.count}   manquantes : {s.missing}   distinctes : {s.distinct}"]
        if s.kind == "numérique" and s.numeric:
            lines.append(f"min {s.minimum:g}   max {s.maximum:g}   moyenne {s.mean:.3g}")
            lines.append(f"médiane {s.median:g}" + (f"   écart-type {s.std:.3g}" if s.std is not None else ""))
            self.hist.set_data(A.histogram(s.numeric, bins=12))
            self.bars.set_data([])
            self.hist.show()
            self.bars.hide()
        else:
            self.hist.set_data([])
            self.bars.set_data([(k, v) for k, v in s.top])
            self.hist.hide()
            self.bars.show()
            lines.append("valeurs les plus fréquentes :")
        self.col_stats.setText("\n".join(lines))
        if not s.reliable:
            self.reliability.setText(f"⚠ Échantillon insuffisant ({s.count} valeurs) : statistiques peu fiables.")
        else:
            self.reliability.setText("")
