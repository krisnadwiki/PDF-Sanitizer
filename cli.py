"""
cli.py – Antarmuka command-line untuk PDF Sanitizer.

Contoh pemakaian:
  python cli.py --input ./pdfs --output ./out --recursive --workers 4
  python cli.py --input ./pdfs --mode replace --skip-safe
  python cli.py --input ./pdfs --mode backup --dpi 200 --scan-only
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from core.sanitizer import (
    OUTPUT_BACKUP,
    OUTPUT_NEW_FOLDER,
    OUTPUT_REPLACE,
    SanitizerOrchestrator,
)
from core.scanner import PDFScanner
from core.logger import logger

# ── ANSI warna (dinonaktifkan jika bukan TTY) ─────────────────────────────

def _color(text: str, code: str) -> str:
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text

green  = lambda t: _color(t, "32")
red    = lambda t: _color(t, "31")
yellow = lambda t: _color(t, "33")
cyan   = lambda t: _color(t, "36")
bold   = lambda t: _color(t, "1")


# ── CLI argument parser ───────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdf-sanitizer",
        description="Batch sanitasi PDF untuk JKN Drive BPJS — hapus /URI, JS, dll.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python cli.py --input ./pdfs --output ./clean
  python cli.py --input ./pdfs --mode replace --skip-safe
  python cli.py --input ./pdfs --scan-only
        """,
    )

    p.add_argument("--input",  "-i", required=True, metavar="DIR",
                   help="Folder sumber PDF")
    p.add_argument("--output", "-o", default="", metavar="DIR",
                   help="Folder tujuan (wajib untuk mode new_folder)")
    p.add_argument("--mode", choices=["new_folder", "replace", "backup"],
                   default="new_folder",
                   help="Mode output: new_folder | replace | backup (default: new_folder)")
    p.add_argument("--recursive", "-r", action="store_true",
                   help="Cari PDF secara rekursif ke subfolder")
    p.add_argument("--workers", "-w", type=int, default=4, metavar="N",
                   help="Jumlah thread paralel (default: 4)")
    p.add_argument("--dpi", type=int, default=150, metavar="N",
                   help="Resolusi render (default: 150)")
    p.add_argument("--skip-safe", action="store_true",
                   help="Lewati file PDF yang sudah bersih (tidak perlu dikonversi)")
    p.add_argument("--scan-only", action="store_true",
                   help="Hanya scan dan laporkan, tanpa melakukan convert")
    return p


# ── Mode scan-only ────────────────────────────────────────────────────────

def run_scan(input_dir: Path, recursive: bool, workers: int):
    import concurrent.futures

    pattern = "**/*.pdf" if recursive else "*.pdf"
    files = sorted(input_dir.glob(pattern))
    total = len(files)

    if total == 0:
        print(yellow("Tidak ada file PDF ditemukan."))
        return

    print(bold(f"\nScan {total} file PDF di: {input_dir}\n"))
    print(f"{'Nama File':<40} {'Hal':>4}  {'Ukuran':>8}  {'Masalah'}")
    print("─" * 80)

    bad = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(PDFScanner.scan_file, [str(f) for f in files]):
            issues = res.get("issues") or []
            status = red(f"⚠ {', '.join(issues)}") if issues else green("✔ Aman")
            if res.get("error"):
                status = red(f"✖ {res['error']}")
            if not res.get("safe"):
                bad += 1
            print(f"{res['filename']:<40} {res['pages']:>4}  {res['size_fmt']:>8}  {status}")

    print("─" * 80)
    print(bold(f"\nTotal: {total}  |  Bermasalah: {red(str(bad))}  |  Aman: {green(str(total - bad))}\n"))


# ── Mode convert ──────────────────────────────────────────────────────────

def run_convert(
    input_dir: Path,
    output_dir: str,
    mode: str,
    recursive: bool,
    workers: int,
    dpi: int,
    skip_safe: bool,
):
    import concurrent.futures

    orch = SanitizerOrchestrator(
        input_dir   = str(input_dir),
        output_dir  = output_dir or str(input_dir),
        recursive   = recursive,
        output_mode = mode,
        dpi         = dpi,
        skip_safe   = skip_safe,
    )
    files = orch.collect_files()
    total = len(files)

    if total == 0:
        print(yellow("Tidak ada file PDF ditemukan."))
        return

    print(bold(f"\nConvert {total} file PDF"))
    print(f"  Input  : {input_dir}")
    if mode == "new_folder":
        print(f"  Output : {output_dir}")
    print(f"  Mode   : {mode}  |  DPI: {dpi}  |  Workers: {workers}")
    print(f"  Skip safe: {'Ya' if skip_safe else 'Tidak'}\n")

    done = success = failed = skipped = 0
    t0 = time.monotonic()

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(orch.process_file, f): f for f in files}
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            done += 1
            st = res["status"]
            if st == "success":
                success += 1
                icon = green("✔")
            elif st == "failed":
                failed += 1
                icon = red("✖")
            else:
                skipped += 1
                icon = yellow("⏭")

            elapsed = time.monotonic() - t0
            rate = done / elapsed if elapsed > 0 else 0
            remaining = (total - done) / rate if rate > 0 else 0
            eta = f"{int(remaining)}s" if remaining < 60 else f"{int(remaining/60)}m{int(remaining%60):02d}s"

            bar_w = 30
            filled = int(bar_w * done / total)
            bar = "█" * filled + "░" * (bar_w - filled)
            pct = int(done / total * 100)

            sys.stdout.write(
                f"\r{icon} [{bar}] {pct:3d}% ({done}/{total})  ETA:{eta}  {res['file'][:35]:<35}"
            )
            sys.stdout.flush()

    elapsed = time.monotonic() - t0
    print(f"\n\n{'─'*60}")
    print(bold("Selesai!"))
    print(f"  Total    : {total}")
    print(f"  {green('Sukses')}   : {success}")
    print(f"  {red('Gagal')}    : {failed}")
    print(f"  {yellow('Dilewati')} : {skipped}")
    print(f"  Waktu    : {elapsed:.1f} detik")
    print()


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = build_parser()
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        print(red(f"Error: folder input tidak ditemukan: {input_dir}"))
        sys.exit(1)

    if args.scan_only:
        run_scan(input_dir, args.recursive, args.workers)
    else:
        if args.mode == "new_folder" and not args.output:
            print(red("Error: --output wajib diisi untuk mode 'new_folder'"))
            sys.exit(1)
        run_convert(
            input_dir  = input_dir,
            output_dir = args.output,
            mode       = args.mode,
            recursive  = args.recursive,
            workers    = args.workers,
            dpi        = args.dpi,
            skip_safe  = args.skip_safe,
        )


if __name__ == "__main__":
    main()
