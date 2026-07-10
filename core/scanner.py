"""
scanner.py – Periksa setiap file PDF dan catat objek berbahaya yang ditemukan.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pikepdf

from core.logger import logger


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ─────────────────────────────────────────────────────────────────────────────
# PDFScanner
# ─────────────────────────────────────────────────────────────────────────────

class PDFScanner:
    """
    Scan satu file PDF dan kembalikan dict dengan informasi berikut:
      path, filename, size, size_fmt, pages,
      has_uri, has_js, has_annot, has_embedded, has_open_action,
      safe, issues (list[str]), error
    """

    @staticmethod
    def scan_file(file_path: str) -> dict[str, Any]:
        p = Path(file_path)
        result: dict[str, Any] = {
            "path": file_path,
            "filename": p.name,
            "size": p.stat().st_size,
            "size_fmt": _fmt_size(p.stat().st_size),
            "pages": 0,
            "has_uri": False,
            "has_js": False,
            "has_annot": False,
            "has_embedded": False,
            "has_open_action": False,
            "safe": True,
            "issues": [],
            "error": None,
        }

        try:
            with pikepdf.Pdf.open(file_path, suppress_warnings=True) as pdf:
                result["pages"] = len(pdf.pages)

                # ── Periksa setiap halaman ──────────────────────────────────
                for page in pdf.pages:
                    if "/Annots" in page:
                        annots = page.get("/Annots")
                        if annots:
                            result["has_annot"] = True
                            for annot_ref in annots:
                                try:
                                    annot = annot_ref
                                    action = annot.get("/A")
                                    if action is None:
                                        continue
                                    s = action.get("/S")
                                    if s is None:
                                        continue
                                    s_name = str(s)
                                    if s_name == "/URI":
                                        result["has_uri"] = True
                                    elif s_name in ("/JavaScript", "/JS"):
                                        result["has_js"] = True
                                except Exception:
                                    pass

                # ── Periksa root catalog ───────────────────────────────────
                root = pdf.Root

                # OpenAction
                if "/OpenAction" in root:
                    result["has_open_action"] = True

                # JavaScript / Names
                names = root.get("/Names")
                if names is not None:
                    if "/JavaScript" in names:
                        result["has_js"] = True
                    if "/EmbeddedFiles" in names:
                        result["has_embedded"] = True

                # AcroForm dengan JS
                acro = root.get("/AcroForm")
                if acro is not None:
                    aa = acro.get("/AA")
                    if aa is not None:
                        result["has_js"] = True

            # ── Rangkum issues ─────────────────────────────────────────────
            if result["has_uri"]:
                result["issues"].append("URI")
            if result["has_js"]:
                result["issues"].append("JavaScript")
            if result["has_embedded"]:
                result["issues"].append("EmbeddedFile")
            if result["has_open_action"]:
                result["issues"].append("OpenAction")

            if result["issues"]:
                result["safe"] = False

        except pikepdf.PdfError as e:
            result["error"] = f"PDF Error: {e}"
            result["safe"] = False
            logger.error("Scan error %s: %s", file_path, e)
        except Exception as e:
            result["error"] = f"Error: {e}"
            result["safe"] = False
            logger.error("Scan error %s: %s", file_path, e)

        return result
