#!/usr/bin/env python3
"""Batch PDF sanitizer for removing dangerous PDF constructs."""

from __future__ import annotations

import argparse
from pathlib import Path

DANGEROUS_TOKENS = {
    b"/URI": b"/_RI",
    b"/JS": b"/_S",
    b"/JavaScript": b"/NoJavaScrp",
    b"/OpenAction": b"/OpenActi0n",
    b"/EmbeddedFile": b"/Embedd3dFile",
    b"/EmbeddedFiles": b"/Embedd3dFiles",
}


def sanitize_pdf_bytes(data: bytes) -> tuple[bytes, int]:
    """Sanitize dangerous tokens in PDF content while preserving file length."""
    sanitized = data
    total_replacements = 0

    for bad, safe in DANGEROUS_TOKENS.items():
        count = sanitized.count(bad)
        if count:
            sanitized = sanitized.replace(bad, safe)
            total_replacements += count

    return sanitized, total_replacements


def sanitize_pdf_file(input_file: Path, output_file: Path) -> int:
    data = input_file.read_bytes()
    sanitized, replacements = sanitize_pdf_bytes(data)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(sanitized)
    return replacements


def iter_pdf_files(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Batch sanitize PDF files by neutralizing URI, JavaScript, "
            "OpenAction, and embedded-file constructs."
        )
    )
    parser.add_argument("input_dir", type=Path, help="Directory containing PDF files")
    parser.add_argument("output_dir", type=Path, help="Directory for sanitized PDFs")
    args = parser.parse_args()

    if not args.input_dir.exists() or not args.input_dir.is_dir():
        parser.error(f"Input directory does not exist or is not a directory: {args.input_dir}")

    pdf_files = iter_pdf_files(args.input_dir)
    sanitized_files = 0
    replacement_count = 0

    for src in pdf_files:
        dst = args.output_dir / src.relative_to(args.input_dir)
        replacements = sanitize_pdf_file(src, dst)
        sanitized_files += 1
        replacement_count += replacements

    print(
        f"Sanitized {sanitized_files} PDF file(s); neutralized {replacement_count} dangerous token(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
