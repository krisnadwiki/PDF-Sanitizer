"""
renderer.py – Render ulang setiap halaman PDF menjadi gambar lalu
              kemas kembali sebagai PDF bersih (tanpa /URI, JS, dll.).

Pendekatan ini meniru hasil "Print as PDF": semua elemen interaktif
hilang, konten visual tetap utuh.
"""
from __future__ import annotations

import io
from pathlib import Path

import fitz  # PyMuPDF

from core.logger import logger


class PDFRenderer:
    """
    Render setiap halaman PDF sumber sebagai pixmap, lalu buat PDF baru
    dengan setiap halaman berisi gambar hasil render tersebut.

    Catatan kompatibilitas PyMuPDF:
      - fitz.open("pdf", bytes) bekerja di semua versi >= 1.18.
      - Kita TIDAK menggunakan pdfocr_tobytes() karena membutuhkan Tesseract.
    """

    @staticmethod
    def render_and_rebuild(
        input_path: str,
        output_path: str,
        dpi: int = 150,
    ) -> bool:
        """
        Baca *input_path*, render ulang tiap halaman, simpan ke *output_path*.

        Parameters
        ----------
        input_path:  path file PDF sumber
        output_path: path file PDF hasil
        dpi:         resolusi render (150 = hemat ukuran, 200-300 = lebih tajam)

        Returns
        -------
        True  – berhasil
        False – gagal (error sudah di-log)
        """
        try:
            src = fitz.open(input_path)
        except Exception as e:
            logger.error("Gagal membuka %s: %s", input_path, e)
            return False

        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        new_doc = fitz.open()

        try:
            for page_num in range(len(src)):
                page = src[page_num]
                # Render halaman → pixmap (RGB, tanpa alpha)
                pix = page.get_pixmap(matrix=mat, alpha=False)

                # ── Buat satu halaman PDF mini dari pixmap ─────────────────
                # Gunakan fitz.open("pdf", pix.tobytes("png")) agar kompatibel
                # dengan semua versi PyMuPDF yang masih aktif.
                img_bytes = pix.tobytes("png")
                tmp = fitz.open("pdf", fitz.open("png", img_bytes).convert_to_pdf())

                # ── Insert ke dokumen baru dengan ukuran halaman asli ──────
                # (tmp halaman 0 sudah berukuran sesuai pixel; kita pakai
                #  ukuran asli supaya dimensi dokumen tidak berubah)
                new_page = new_doc.new_page(
                    width=page.rect.width,
                    height=page.rect.height,
                )
                new_page.show_pdf_page(new_page.rect, tmp, 0)
                tmp.close()

            # ── Simpan ─────────────────────────────────────────────────────
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            new_doc.save(
                output_path,
                garbage=4,      # hapus objek tidak terpakai
                deflate=True,   # kompresi stream
                clean=True,     # normalise content streams
            )
            return True

        except Exception as e:
            logger.error("Gagal render %s: %s", input_path, e)
            return False

        finally:
            new_doc.close()
            src.close()
