"""
sanitizer.py – Orkestrasi scan + convert untuk satu file PDF.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from core.scanner import PDFScanner
from core.renderer import PDFRenderer
from core.logger import logger


# ─────────────────────────────────────────────────────────────────────────────
# Konstanta mode output
# ─────────────────────────────────────────────────────────────────────────────

OUTPUT_NEW_FOLDER = "new_folder"   # Simpan ke folder output (mirror struktur)
OUTPUT_REPLACE    = "replace"      # Ganti file asli (in-place)
OUTPUT_BACKUP     = "backup"       # Backup file asli, lalu replace


class SanitizerOrchestrator:
    """
    Kumpulkan daftar PDF dari input_dir, lalu proses satu per satu.

    Parameters
    ----------
    input_dir      : folder sumber
    output_dir     : folder tujuan (diabaikan jika mode = replace)
    recursive      : cari subfolder secara rekursif
    output_mode    : OUTPUT_NEW_FOLDER | OUTPUT_REPLACE | OUTPUT_BACKUP
    dpi            : resolusi render (default 150)
    skip_safe      : lewati file yang sudah aman (tidak perlu dikonversi)
    """

    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        recursive: bool = True,
        output_mode: str = OUTPUT_NEW_FOLDER,
        dpi: int = 150,
        skip_safe: bool = False,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir) if output_dir else self.input_dir
        self.recursive = recursive
        self.output_mode = output_mode
        self.dpi = dpi
        self.skip_safe = skip_safe

    # ── Kumpulkan file ──────────────────────────────────────────────────────

    def collect_files(self) -> list[Path]:
        pattern = "**/*.pdf" if self.recursive else "*.pdf"
        return sorted(self.input_dir.glob(pattern))

    # ── Tentukan path output ────────────────────────────────────────────────

    def _resolve_output(self, src: Path) -> Path:
        if self.output_mode in (OUTPUT_REPLACE, OUTPUT_BACKUP):
            return src
        # OUTPUT_NEW_FOLDER: mirror struktur folder
        rel = src.relative_to(self.input_dir)
        return self.output_dir / rel

    # ── Proses satu file ────────────────────────────────────────────────────

    def process_file(self, file_path: Path) -> dict[str, Any]:
        result = {
            "file": file_path.name,
            "path": str(file_path),
            "status": "failed",
            "message": "",
        }

        # ── Scan ────────────────────────────────────────────────────────────
        scan = PDFScanner.scan_file(str(file_path))

        if scan.get("error"):
            result["message"] = scan["error"]
            return result

        # ── Lewati jika aman dan skip_safe aktif ────────────────────────────
        if self.skip_safe and scan["safe"]:
            result["status"] = "skipped"
            result["message"] = "Aman, dilewati"
            # Jika mode new_folder, tetap salin file asli supaya folder output
            # tetap lengkap.
            if self.output_mode == OUTPUT_NEW_FOLDER:
                out = self._resolve_output(file_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                if not out.exists() or out != file_path:
                    shutil.copy2(file_path, out)
            return result

        out_path = self._resolve_output(file_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # ── Backup jika diminta ──────────────────────────────────────────────
        if self.output_mode == OUTPUT_BACKUP:
            backup = file_path.with_suffix(".bak.pdf")
            try:
                shutil.copy2(file_path, backup)
            except Exception as e:
                result["message"] = f"Gagal backup: {e}"
                return result

        # ── Render ke file sementara lalu pindahkan ─────────────────────────
        # Untuk mode replace/backup, kita render ke .tmp agar atomik.
        if out_path == file_path:
            tmp_path = file_path.with_suffix(".sanitizing.pdf")
            success = PDFRenderer.render_and_rebuild(
                str(file_path), str(tmp_path), dpi=self.dpi
            )
            if success:
                try:
                    tmp_path.replace(file_path)
                except Exception as e:
                    tmp_path.unlink(missing_ok=True)
                    result["message"] = f"Gagal replace: {e}"
                    return result
        else:
            success = PDFRenderer.render_and_rebuild(
                str(file_path), str(out_path), dpi=self.dpi
            )

        if success:
            result["status"] = "success"
            issues = scan.get("issues") or []
            if issues:
                result["message"] = f"Dibersihkan: {', '.join(issues)}"
            else:
                result["message"] = "Dikonversi"
        else:
            result["message"] = "Gagal render"

        return result
