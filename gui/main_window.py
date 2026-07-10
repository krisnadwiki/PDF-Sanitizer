"""
main_window.py – Jendela utama aplikasi PDF Sanitizer.

Tab:
  1. Convert  – pilih folder, atur opsi, jalankan batch convert
  2. Scan     – scan folder dan lihat tabel hasil analisa PDF
  3. Log      – riwayat proses lengkap (bisa di-export)
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.sanitizer import (
    OUTPUT_BACKUP,
    OUTPUT_NEW_FOLDER,
    OUTPUT_REPLACE,
    SanitizerOrchestrator,
)
from core.worker import ConvertWorker, ScanWorker


# ─────────────────────────────────────────────────────────────────────────────
# Stylesheet
# ─────────────────────────────────────────────────────────────────────────────

STYLE = """
QMainWindow, QWidget#central {
    background: #f0f2f5;
}
QTabWidget::pane {
    border: 1px solid #d0d3da;
    border-radius: 6px;
    background: #ffffff;
}
QTabBar::tab {
    background: #e4e6eb;
    border: 1px solid #d0d3da;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 20px;
    font-weight: 600;
    color: #555;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #1a73e8;
    border-bottom: 2px solid #1a73e8;
}
QGroupBox {
    font-weight: 700;
    font-size: 11px;
    color: #444;
    border: 1px solid #d0d3da;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px 10px 8px 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    background: #ffffff;
}
QLineEdit {
    border: 1px solid #c4c8d4;
    border-radius: 6px;
    padding: 7px 10px;
    background: #fff;
    font-size: 12px;
}
QLineEdit:focus { border-color: #1a73e8; }
QPushButton {
    background: #1a73e8;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 12px;
}
QPushButton:hover  { background: #1558b0; }
QPushButton:pressed{ background: #0d47a1; }
QPushButton:disabled { background: #b0bec5; color: #eceff1; }
QPushButton#btn_stop {
    background: #e53935;
}
QPushButton#btn_stop:hover  { background: #b71c1c; }
QPushButton#btn_secondary {
    background: #546e7a;
}
QPushButton#btn_secondary:hover { background: #37474f; }
QPushButton#btn_export {
    background: #2e7d32;
}
QPushButton#btn_export:hover { background: #1b5e20; }
QProgressBar {
    border: 1px solid #d0d3da;
    border-radius: 6px;
    background: #e8eaf6;
    height: 18px;
    text-align: center;
    font-weight: 700;
    font-size: 11px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #1a73e8, stop:1 #26c6da);
    border-radius: 6px;
}
QTextEdit {
    border: 1px solid #d0d3da;
    border-radius: 6px;
    background: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    padding: 6px;
}
QTableWidget {
    border: 1px solid #d0d3da;
    border-radius: 6px;
    gridline-color: #e8eaf6;
    font-size: 11px;
}
QTableWidget::item { padding: 4px 8px; }
QTableWidget::item:selected { background: #e3f2fd; color: #000; }
QHeaderView::section {
    background: #e8eaf6;
    border: none;
    border-right: 1px solid #d0d3da;
    border-bottom: 1px solid #d0d3da;
    padding: 6px 8px;
    font-weight: 700;
    font-size: 11px;
}
QComboBox {
    border: 1px solid #c4c8d4;
    border-radius: 6px;
    padding: 6px 10px;
    background: #fff;
}
QSpinBox {
    border: 1px solid #c4c8d4;
    border-radius: 6px;
    padding: 6px 8px;
    background: #fff;
}
QCheckBox { font-size: 12px; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 2px solid #c4c8d4;
    border-radius: 4px;
    background: #fff;
}
QCheckBox::indicator:checked {
    background: #1a73e8;
    border-color: #1a73e8;
    image: none;
}
QStatusBar { font-size: 11px; color: #555; }
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helper widget: DragDropLineEdit
# ─────────────────────────────────────────────────────────────────────────────

class DragDropLineEdit(QLineEdit):
    """QLineEdit yang menerima drag-and-drop folder."""

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_dir():
                self.setText(path)
            elif Path(path).is_file():
                self.setText(str(Path(path).parent))


# ─────────────────────────────────────────────────────────────────────────────
# Stat Card – kotak statistik ringkas
# ─────────────────────────────────────────────────────────────────────────────

class StatCard(QWidget):
    def __init__(self, label: str, value: str = "0", color: str = "#1a73e8", parent=None):
        super().__init__(parent)
        self.setFixedHeight(72)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(2)

        self.val_lbl = QLabel(value)
        font = self.val_lbl.font()
        font.setPointSize(22)
        font.setBold(True)
        self.val_lbl.setFont(font)
        self.val_lbl.setStyleSheet(f"color: {color};")
        self.val_lbl.setAlignment(Qt.AlignCenter)

        self.txt_lbl = QLabel(label)
        self.txt_lbl.setAlignment(Qt.AlignCenter)
        self.txt_lbl.setStyleSheet("color: #777; font-size: 11px;")

        layout.addWidget(self.val_lbl)
        layout.addWidget(self.txt_lbl)
        self.setStyleSheet("background:#fff; border:1px solid #e0e0e0; border-radius:8px;")

    def set_value(self, v):
        self.val_lbl.setText(str(v))



# ─────────────────────────────────────────────────────────────────────────────
# ConvertTab
# ─────────────────────────────────────────────────────────────────────────────

class ConvertTab(QWidget):
    def __init__(self, log_callback, parent=None):
        super().__init__(parent)
        self._log = log_callback
        self._worker: ConvertWorker | None = None
        self._files: list[Path] = []
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # ── Input / Output ────────────────────────────────────────────────
        io_box = QGroupBox("Folder")
        io_lay = QVBoxLayout(io_box)
        io_lay.setSpacing(8)

        # Input row
        in_row = QHBoxLayout()
        lbl_in = QLabel("Input :")
        lbl_in.setFixedWidth(52)
        self.edit_input = DragDropLineEdit("Pilih atau drag-drop folder sumber…")
        btn_in = QPushButton("Browse")
        btn_in.setFixedWidth(80)
        btn_in.clicked.connect(self._browse_input)
        in_row.addWidget(lbl_in)
        in_row.addWidget(self.edit_input)
        in_row.addWidget(btn_in)
        io_lay.addLayout(in_row)

        # Output row
        out_row = QHBoxLayout()
        lbl_out = QLabel("Output :")
        lbl_out.setFixedWidth(52)
        self.edit_output = DragDropLineEdit("Pilih atau drag-drop folder tujuan…")
        btn_out = QPushButton("Browse")
        btn_out.setFixedWidth(80)
        btn_out.clicked.connect(self._browse_output)
        out_row.addWidget(lbl_out)
        out_row.addWidget(self.edit_output)
        out_row.addWidget(btn_out)
        io_lay.addLayout(out_row)

        root.addWidget(io_box)

        # ── Opsi ──────────────────────────────────────────────────────────
        opt_box = QGroupBox("Opsi")
        opt_lay = QHBoxLayout(opt_box)
        opt_lay.setSpacing(16)

        self.cb_recursive = QCheckBox("Rekursif (subfolder)")
        self.cb_recursive.setChecked(True)
        opt_lay.addWidget(self.cb_recursive)

        self.cb_skip_safe = QCheckBox("Lewati file aman")
        self.cb_skip_safe.setChecked(False)
        self.cb_skip_safe.setToolTip("File tanpa /URI atau JS hanya disalin tanpa render ulang")
        opt_lay.addWidget(self.cb_skip_safe)

        opt_lay.addStretch()

        opt_lay.addWidget(QLabel("Mode output :"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Folder baru", "Replace file asli", "Backup lalu replace"])
        self.combo_mode.setFixedWidth(160)
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        opt_lay.addWidget(self.combo_mode)

        opt_lay.addWidget(QLabel("DPI :"))
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(72, 300)
        self.spin_dpi.setValue(150)
        self.spin_dpi.setFixedWidth(60)
        self.spin_dpi.setToolTip("150 = file kecil, 200-300 = lebih tajam")
        opt_lay.addWidget(self.spin_dpi)

        opt_lay.addWidget(QLabel("Workers :"))
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, 32)
        self.spin_workers.setValue(max(1, (os.cpu_count() or 4) // 2))
        self.spin_workers.setFixedWidth(55)
        opt_lay.addWidget(self.spin_workers)

        root.addWidget(opt_box)

        # ── Statistik cards ───────────────────────────────────────────────
        card_row = QHBoxLayout()
        card_row.setSpacing(8)
        self.card_total   = StatCard("Total File",  "0", "#455a64")
        self.card_success = StatCard("Sukses",       "0", "#2e7d32")
        self.card_failed  = StatCard("Gagal",        "0", "#c62828")
        self.card_skipped = StatCard("Dilewati",     "0", "#f57c00")
        self.card_eta     = StatCard("Sisa Waktu",   "–", "#1a73e8")
        for c in (self.card_total, self.card_success, self.card_failed,
                  self.card_skipped, self.card_eta):
            card_row.addWidget(c)
        root.addLayout(card_row)

        # ── Progress ──────────────────────────────────────────────────────
        prog_box = QGroupBox("Progress")
        prog_lay = QVBoxLayout(prog_box)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        prog_lay.addWidget(self.progress_bar)

        self.lbl_current = QLabel("Siap.")
        self.lbl_current.setStyleSheet("color:#555; font-size:11px;")
        prog_lay.addWidget(self.lbl_current)

        root.addWidget(prog_box)

        # ── Tombol kontrol ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_stop = QPushButton("⏹  Stop")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        btn_row.addWidget(self.btn_stop)

        self.btn_start = QPushButton("▶  Mulai Convert")
        self.btn_start.clicked.connect(self._start)
        btn_row.addWidget(self.btn_start)

        root.addLayout(btn_row)

    # ── Slot UI ───────────────────────────────────────────────────────────

    def _browse_input(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih Folder Input")
        if d:
            self.edit_input.setText(d)
            # Auto-isi output jika belum ada
            if not self.edit_output.text():
                self.edit_output.setText(str(Path(d).parent / (Path(d).name + "_sanitized")))

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih Folder Output")
        if d:
            self.edit_output.setText(d)

    def _on_mode_changed(self, idx: int):
        # Mode replace / backup → output folder tidak relevan
        in_place = idx in (1, 2)
        self.edit_output.setEnabled(not in_place)

    def _mode_str(self) -> str:
        idx = self.combo_mode.currentIndex()
        return [OUTPUT_NEW_FOLDER, OUTPUT_REPLACE, OUTPUT_BACKUP][idx]

    def _validate(self) -> bool:
        in_dir = self.edit_input.text().strip()
        if not in_dir or not Path(in_dir).is_dir():
            QMessageBox.warning(self, "Input tidak valid", "Pilih folder input yang valid.")
            return False
        mode = self._mode_str()
        if mode == OUTPUT_NEW_FOLDER:
            out_dir = self.edit_output.text().strip()
            if not out_dir:
                QMessageBox.warning(self, "Output tidak valid", "Pilih folder output.")
                return False
            if Path(in_dir) == Path(out_dir):
                QMessageBox.warning(self, "Konflik folder",
                    "Folder input dan output tidak boleh sama\n"
                    "saat menggunakan mode 'Folder baru'.\n"
                    "Gunakan mode 'Replace' jika ingin menimpa file asli.")
                return False
        return True

    def _reset_stats(self):
        for c in (self.card_total, self.card_success, self.card_failed,
                  self.card_skipped):
            c.set_value("0")
        self.card_eta.set_value("–")
        self.progress_bar.setValue(0)

    def _set_busy(self, busy: bool):
        self.btn_start.setEnabled(not busy)
        self.btn_stop.setEnabled(busy)
        self.edit_input.setEnabled(not busy)
        self.edit_output.setEnabled(not busy and self.combo_mode.currentIndex() == 0)
        self.combo_mode.setEnabled(not busy)
        self.cb_recursive.setEnabled(not busy)
        self.cb_skip_safe.setEnabled(not busy)
        self.spin_dpi.setEnabled(not busy)
        self.spin_workers.setEnabled(not busy)


    def _start(self):
        if not self._validate():
            return

        in_dir  = self.edit_input.text().strip()
        out_dir = self.edit_output.text().strip()
        mode    = self._mode_str()

        orch = SanitizerOrchestrator(
            input_dir   = in_dir,
            output_dir  = out_dir if mode == OUTPUT_NEW_FOLDER else in_dir,
            recursive   = self.cb_recursive.isChecked(),
            output_mode = mode,
            dpi         = self.spin_dpi.value(),
            skip_safe   = self.cb_skip_safe.isChecked(),
        )
        files = orch.collect_files()

        if not files:
            QMessageBox.information(self, "Kosong", "Tidak ada file PDF ditemukan di folder input.")
            return

        self._reset_stats()
        self.card_total.set_value(len(files))
        self._set_busy(True)
        self.lbl_current.setText("Memulai…")

        self._worker = ConvertWorker(
            orchestrator = orch,
            files        = files,
            workers      = self.spin_workers.value(),
        )
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.log_entry.connect(self._on_log)
        self._worker.eta_updated.connect(lambda s: self.card_eta.set_value(s))
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _stop(self):
        if self._worker:
            self._worker.stop()
            self.btn_stop.setEnabled(False)
            self.lbl_current.setText("Menghentikan…")

    def _on_progress(self, done: int, total: int, filename: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)
        self.progress_bar.setFormat(f"{done} / {total}  ({int(done/total*100)}%)")
        self.lbl_current.setText(f"Memproses: {filename}")

    def _on_log(self, status: str, filename: str, message: str):
        if status == "success":
            self.card_success.set_value(int(self.card_success.val_lbl.text()) + 1)
        elif status == "failed":
            self.card_failed.set_value(int(self.card_failed.val_lbl.text()) + 1)
        else:
            self.card_skipped.set_value(int(self.card_skipped.val_lbl.text()) + 1)
        self._log(status, filename, message)

    def _on_finished(self, stats: dict):
        self._set_busy(False)
        self.card_eta.set_value("–")
        self.lbl_current.setText(
            f"Selesai — Sukses: {stats['success']} | "
            f"Gagal: {stats['failed']} | Dilewati: {stats['skipped']}"
        )
        QMessageBox.information(
            self,
            "Proses Selesai",
            f"Total   : {stats['total']} file\n"
            f"Sukses  : {stats['success']}\n"
            f"Gagal   : {stats['failed']}\n"
            f"Dilewati: {stats['skipped']}",
        )



# ─────────────────────────────────────────────────────────────────────────────
# ScanTab
# ─────────────────────────────────────────────────────────────────────────────

# Kolom tabel
_COLS = ["Nama File", "Halaman", "Ukuran", "URI", "JS", "Annot", "Embedded", "Status"]
_COL_IDX = {c: i for i, c in enumerate(_COLS)}


class ScanTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: ScanWorker | None = None
        self._results: list[dict] = []
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # ── Input ─────────────────────────────────────────────────────────
        in_box = QGroupBox("Folder")
        in_lay = QHBoxLayout(in_box)
        self.edit_folder = DragDropLineEdit("Pilih atau drag-drop folder untuk discan…")
        btn_br = QPushButton("Browse")
        btn_br.setFixedWidth(80)
        btn_br.clicked.connect(self._browse)
        self.cb_rec = QCheckBox("Rekursif")
        self.cb_rec.setChecked(True)
        in_lay.addWidget(QLabel("Folder :"))
        in_lay.addWidget(self.edit_folder)
        in_lay.addWidget(btn_br)
        in_lay.addWidget(self.cb_rec)
        root.addWidget(in_box)

        # ── Progress bar scan ─────────────────────────────────────────────
        self.scan_progress = QProgressBar()
        self.scan_progress.setTextVisible(True)
        self.scan_progress.setVisible(False)
        root.addWidget(self.scan_progress)

        # ── Filter baris ──────────────────────────────────────────────────
        filter_row = QHBoxLayout()
        self.cb_show_all      = QCheckBox("Semua")
        self.cb_show_all.setChecked(True)
        self.cb_show_problem  = QCheckBox("Bermasalah saja")
        self.cb_show_all.toggled.connect(lambda: self._apply_filter())
        self.cb_show_problem.toggled.connect(lambda: self._apply_filter())
        filter_row.addWidget(QLabel("Tampilkan:"))
        filter_row.addWidget(self.cb_show_all)
        filter_row.addWidget(self.cb_show_problem)
        filter_row.addStretch()
        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet("color:#555; font-size:11px;")
        filter_row.addWidget(self.lbl_summary)
        root.addLayout(filter_row)

        # ── Tabel hasil ───────────────────────────────────────────────────
        self.table = QTableWidget(0, len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, len(_COLS)):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        root.addWidget(self.table)

        # ── Tombol ────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.btn_export = QPushButton("💾  Export CSV")
        self.btn_export.setObjectName("btn_export")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_csv)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch()

        self.btn_stop_scan = QPushButton("⏹  Stop")
        self.btn_stop_scan.setObjectName("btn_stop")
        self.btn_stop_scan.setEnabled(False)
        self.btn_stop_scan.clicked.connect(self._stop)
        btn_row.addWidget(self.btn_stop_scan)

        self.btn_scan = QPushButton("🔍  Scan")
        self.btn_scan.clicked.connect(self._start_scan)
        btn_row.addWidget(self.btn_scan)
        root.addLayout(btn_row)

    # ── Slot ──────────────────────────────────────────────────────────────

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih Folder")
        if d:
            self.edit_folder.setText(d)

    def _start_scan(self):
        folder = self.edit_folder.text().strip()
        if not folder or not Path(folder).is_dir():
            QMessageBox.warning(self, "Folder tidak valid", "Pilih folder yang valid.")
            return

        self._results.clear()
        self.table.setRowCount(0)
        self.lbl_summary.setText("")
        self.scan_progress.setValue(0)
        self.scan_progress.setVisible(True)
        self.btn_scan.setEnabled(False)
        self.btn_stop_scan.setEnabled(True)
        self.btn_export.setEnabled(False)

        self._worker = ScanWorker(
            input_dir = folder,
            recursive = self.cb_rec.isChecked(),
            workers   = max(1, (os.cpu_count() or 4) // 2),
        )
        self._worker.file_scanned.connect(self._on_file_scanned)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
        self._worker.start()

    def _stop(self):
        if self._worker:
            self._worker.stop()
            self.btn_stop_scan.setEnabled(False)

    def _on_scan_progress(self, done: int, total: int):
        self.scan_progress.setMaximum(total)
        self.scan_progress.setValue(done)
        self.scan_progress.setFormat(f"Scan {done} / {total}")

    def _on_file_scanned(self, res: dict):
        self._results.append(res)
        self._add_table_row(res)

    def _on_scan_finished(self, total: int, bad: int):
        self.btn_scan.setEnabled(True)
        self.btn_stop_scan.setEnabled(False)
        self.scan_progress.setVisible(False)
        self.btn_export.setEnabled(bool(self._results))
        self.lbl_summary.setText(
            f"Total: {total} file  |  Bermasalah: {bad}  |  Aman: {total - bad}"
        )

    def _add_table_row(self, res: dict):
        if self.cb_show_problem.isChecked() and res.get("safe"):
            return
        row = self.table.rowCount()
        self.table.insertRow(row)

        def cell(txt, align=Qt.AlignLeft):
            item = QTableWidgetItem(str(txt))
            item.setTextAlignment(align | Qt.AlignVCenter)
            return item

        def bool_cell(val: bool):
            item = QTableWidgetItem("✔" if val else "–")
            item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            if val:
                item.setForeground(QColor("#c62828"))
            return item

        self.table.setItem(row, 0, cell(res["filename"]))
        self.table.setItem(row, 1, cell(res["pages"], Qt.AlignCenter))
        self.table.setItem(row, 2, cell(res["size_fmt"], Qt.AlignRight))
        self.table.setItem(row, 3, bool_cell(res["has_uri"]))
        self.table.setItem(row, 4, bool_cell(res["has_js"]))
        self.table.setItem(row, 5, bool_cell(res["has_annot"]))
        self.table.setItem(row, 6, bool_cell(res["has_embedded"]))

        status_text = "⚠ Bermasalah" if not res.get("safe") else "✔ Aman"
        status_item = cell(status_text, Qt.AlignCenter)
        if res.get("error"):
            status_item.setText("✖ Error")
            status_item.setForeground(QColor("#b71c1c"))
        elif not res.get("safe"):
            status_item.setForeground(QColor("#e65100"))
        else:
            status_item.setForeground(QColor("#2e7d32"))
        self.table.setItem(row, 7, status_item)

        # Warna baris
        if not res.get("safe"):
            for c in range(len(_COLS)):
                item = self.table.item(row, c)
                if item:
                    item.setBackground(QColor("#fff3e0"))

    def _apply_filter(self):
        self.table.setRowCount(0)
        show_problem_only = self.cb_show_problem.isChecked()
        for res in self._results:
            if show_problem_only and res.get("safe"):
                continue
            self._add_table_row(res)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan CSV", "scan_result.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["path", "filename", "pages", "size", "has_uri",
                             "has_js", "has_annot", "has_embedded", "safe", "issues", "error"])
                for r in self._results:
                    w.writerow([
                        r["path"], r["filename"], r["pages"], r["size_fmt"],
                        r["has_uri"], r["has_js"], r["has_annot"], r["has_embedded"],
                        r["safe"], ", ".join(r.get("issues") or []), r.get("error") or "",
                    ])
            QMessageBox.information(self, "Ekspor Selesai", f"Tersimpan di:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Gagal Ekspor", str(e))



# ─────────────────────────────────────────────────────────────────────────────
# LogTab
# ─────────────────────────────────────────────────────────────────────────────

class LogTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[tuple[str, str, str]] = []  # (status, filename, message)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        root.addWidget(self.log_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_clear = QPushButton("🗑  Bersihkan")
        btn_clear.setObjectName("btn_secondary")
        btn_clear.clicked.connect(self._clear)
        btn_row.addWidget(btn_clear)

        btn_export = QPushButton("💾  Export Log")
        btn_export.setObjectName("btn_export")
        btn_export.clicked.connect(self._export)
        btn_row.addWidget(btn_export)

        root.addLayout(btn_row)

    def append(self, status: str, filename: str, message: str):
        self._entries.append((status, filename, message))
        ts = datetime.now().strftime("%H:%M:%S")

        if status == "success":
            color, icon = "#a5d6a7", "✔"
        elif status == "failed":
            color, icon = "#ef9a9a", "✖"
        elif status == "skipped":
            color, icon = "#b0bec5", "⏭"
        else:
            color, icon = "#cdd6f4", "ℹ"

        line = (
            f'<span style="color:#888">[{ts}]</span> '
            f'<span style="color:{color}">{icon} {filename}</span>'
            f'<span style="color:#888"> — {message}</span>'
        )
        self.log_edit.append(line)
        sb = self.log_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear(self):
        self.log_edit.clear()
        self._entries.clear()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Log", f"log_{datetime.now():%Y%m%d_%H%M%S}.txt", "Text (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for status, fname, msg in self._entries:
                    f.write(f"[{status.upper()}] {fname} — {msg}\n")
            QMessageBox.information(self, "Ekspor Selesai", f"Tersimpan di:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Gagal Ekspor", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# MainWindow
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Sanitizer — v1.0")
        self.setMinimumSize(860, 640)
        self.resize(960, 700)
        self.setAcceptDrops(True)

        self._setup_ui()
        self.setStyleSheet(STYLE)
        self._update_status("Siap.")

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 6)
        root.setSpacing(6)

        # ── Header ────────────────────────────────────────────────────────
        header = QLabel("🛡  PDF Sanitizer")
        header.setStyleSheet(
            "font-size: 18px; font-weight: 800; color: #1a237e; padding: 4px 0;"
        )
        root.addWidget(header)

        sub = QLabel(
            "Bersihkan /URI, JavaScript, dan objek berbahaya dari PDF secara batch "
            "agar lolos validasi JKN Drive."
        )
        sub.setStyleSheet("color: #607d8b; font-size: 11px;")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # ── Tabs ──────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.log_tab  = LogTab()
        self.conv_tab = ConvertTab(log_callback=self.log_tab.append)
        self.scan_tab = ScanTab()

        self.tabs.addTab(self.conv_tab, "⚙  Convert")
        self.tabs.addTab(self.scan_tab, "🔍  Scan")
        self.tabs.addTab(self.log_tab,  "📋  Log")

        root.addWidget(self.tabs)

        # ── Status bar ────────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _update_status(self, msg: str):
        self.status_bar.showMessage(msg)

    # Drag-drop ke window utama → isi folder di tab aktif
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if not Path(path).is_dir():
            path = str(Path(path).parent)

        idx = self.tabs.currentIndex()
        if idx == 0:
            self.conv_tab.edit_input.setText(path)
        elif idx == 1:
            self.scan_tab.edit_folder.setText(path)
 