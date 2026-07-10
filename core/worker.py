"""
worker.py – QThread wrappers untuk scan dan convert agar GUI tetap responsif.
"""
from __future__ import annotations

import concurrent.futures
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from core.sanitizer import SanitizerOrchestrator
from core.scanner import PDFScanner


# ─────────────────────────────────────────────────────────────────────────────
# ScanWorker – scan folder tanpa memblokir UI
# ─────────────────────────────────────────────────────────────────────────────

class ScanWorker(QThread):
    """Scan seluruh PDF di folder dan emit hasilnya satu per satu."""

    file_scanned  = Signal(dict)   # hasil scan satu file
    progress      = Signal(int, int)  # (selesai, total)
    finished      = Signal(int, int)  # (total, bermasalah)
    error         = Signal(str)

    def __init__(
        self,
        input_dir: str,
        recursive: bool = True,
        workers: int = 4,
        parent=None,
    ):
        super().__init__(parent)
        self.input_dir = Path(input_dir)
        self.recursive = recursive
        self.workers = workers
        self._running = True

    def run(self):
        try:
            pattern = "**/*.pdf" if self.recursive else "*.pdf"
            files = sorted(self.input_dir.glob(pattern))
            total = len(files)
            done = 0
            bad = 0

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
                futures = {pool.submit(PDFScanner.scan_file, str(f)): f for f in files}
                for fut in concurrent.futures.as_completed(futures):
                    if not self._running:
                        pool.shutdown(wait=False, cancel_futures=True)
                        break
                    result = fut.result()
                    done += 1
                    if not result.get("safe"):
                        bad += 1
                    self.file_scanned.emit(result)
                    self.progress.emit(done, total)

            self.finished.emit(done, bad)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._running = False


# ─────────────────────────────────────────────────────────────────────────────
# ConvertWorker – convert batch dengan multi-thread
# ─────────────────────────────────────────────────────────────────────────────

class ConvertWorker(QThread):
    """Convert / sanitasi batch PDF dengan ThreadPoolExecutor."""

    progress_updated = Signal(int, int, str)  # (selesai, total, nama_file)
    log_entry        = Signal(str, str, str)  # (status, filename, message)
    eta_updated      = Signal(str)            # string ETA, mis. "2 mnt 30 dtk"
    finished         = Signal(dict)           # statistik akhir

    def __init__(
        self,
        orchestrator: SanitizerOrchestrator,
        files: list[Path],
        workers: int = 4,
        parent=None,
    ):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.files = files
        self.workers = workers
        self._running = True

    # ── ETA helper ──────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_eta(seconds: float) -> str:
        if seconds <= 0:
            return "–"
        s = int(seconds)
        if s < 60:
            return f"{s} dtk"
        m, s = divmod(s, 60)
        if m < 60:
            return f"{m} mnt {s:02d} dtk"
        h, m = divmod(m, 60)
        return f"{h} jam {m:02d} mnt"

    # ── Thread entry point ──────────────────────────────────────────────────

    def run(self):
        files = self.files
        total = len(files)

        if total == 0:
            self.finished.emit({"total": 0, "success": 0, "failed": 0, "skipped": 0})
            return

        done = success = failed = skipped = 0
        t_start = time.monotonic()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {
                pool.submit(self.orchestrator.process_file, f): f
                for f in files
            }
            for fut in concurrent.futures.as_completed(futures):
                if not self._running:
                    pool.shutdown(wait=False, cancel_futures=True)
                    break

                res: dict[str, Any] = fut.result()
                done += 1

                st = res["status"]
                if st == "success":
                    success += 1
                elif st == "failed":
                    failed += 1
                else:
                    skipped += 1

                self.log_entry.emit(st, res["file"], res["message"])
                self.progress_updated.emit(done, total, res["file"])

                # Hitung ETA
                elapsed = time.monotonic() - t_start
                rate = done / elapsed if elapsed > 0 else 0
                remaining = (total - done) / rate if rate > 0 else 0
                self.eta_updated.emit(self._fmt_eta(remaining))

        self.finished.emit({
            "total": total,
            "success": success,
            "failed": failed,
            "skipped": skipped,
        })

    def stop(self):
        self._running = False
