import tempfile
import unittest
from pathlib import Path

from sanitizer import iter_pdf_files, sanitize_pdf_bytes, sanitize_pdf_file


class SanitizerTests(unittest.TestCase):
    def test_sanitize_pdf_bytes_replaces_dangerous_tokens(self):
        payload = (
            b"%PDF-1.7\n"
            b"<< /URI (https://example.com) /JS (app.alert('x')) /JavaScript 1 "
            b"/OpenAction 2 0 R /EmbeddedFile true /EmbeddedFiles 3 0 R >>"
        )

        result, replacements = sanitize_pdf_bytes(payload)

        self.assertEqual(replacements, 6)
        self.assertNotIn(b"/URI", result)
        self.assertNotIn(b"/JS", result)
        self.assertNotIn(b"/JavaScript", result)
        self.assertNotIn(b"/OpenAction", result)
        self.assertNotIn(b"/EmbeddedFile", result)
        self.assertNotIn(b"/EmbeddedFiles", result)
        self.assertEqual(len(result), len(payload))

    def test_sanitize_pdf_file_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.pdf"
            dst = Path(tmp) / "out.pdf"
            src.write_bytes(b"%PDF-1.4\n<< /URI (https://example.com) >>")

            replacements = sanitize_pdf_file(src, dst)

            self.assertEqual(replacements, 1)
            self.assertTrue(dst.exists())
            self.assertNotIn(b"/URI", dst.read_bytes())

    def test_iter_pdf_files_is_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.pdf").write_bytes(b"x")
            (root / "b.PDF").write_bytes(b"x")
            (root / "c.txt").write_text("x")

            pdfs = iter_pdf_files(root)

            self.assertEqual([p.name for p in pdfs], ["a.pdf", "b.PDF"])


if __name__ == "__main__":
    unittest.main()
