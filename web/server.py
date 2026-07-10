"""
web/server.py – FastAPI server untuk PDF Sanitizer.

Endpoint:
  POST /api/upload          – upload satu atau lebih PDF, simpan ke session folder
  POST /api/scan            – scan semua file di session, kembalikan hasil JSON
  GET  /api/jobs            – daftar semua job aktif/selesai
  POST /api/sanitize        – mulai batch sanitize (file_ids[])
  WS   /ws/{job_id}         – stream progress sanitize via WebSocket
  GET  /api/download/{job_id} – download hasil sebagai ZIP
  DELETE /api/session/{sid} – bersihkan file sesi
"""
from __future__ import annotations

import asyncio
import io
import json
import shutil
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from core.renderer import PDFRenderer
from core.scanner import PDFScanner

# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = Path("/tmp/pdf_sanitizer_uploads")   # di Docker → /tmp; lokal menyesuaikan
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="PDF Sanitizer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Thread pool untuk operasi CPU-bound (render PDF)
_executor = ThreadPoolExecutor(max_workers=8)

# ─────────────────────────────────────────────────────────────────────────────
# In-memory state (cukup untuk single-server, ganti Redis untuk multi-instance)
# ─────────────────────────────────────────────────────────────────────────────

# sessions[sid] = {"files": {fid: {"name", "path", "scan": dict|None}}}
sessions: dict[str, dict] = {}

# jobs[job_id] = {"status", "total", "done", "results": [], "output_zip": Path|None}
jobs: dict[str, dict[str, Any]] = {}

# WebSocket connections per job
ws_connections: dict[str, list[WebSocket]] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _new_sid() -> str:
    return uuid.uuid4().hex

def _session_dir(sid: str) -> Path:
    d = UPLOAD_DIR / sid
    d.mkdir(parents=True, exist_ok=True)
    return d

def _output_dir(job_id: str) -> Path:
    d = UPLOAD_DIR / "out" / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d

async def _broadcast(job_id: str, msg: dict):
    """Kirim pesan JSON ke semua WS listener job ini."""
    dead = []
    for ws in ws_connections.get(job_id, []):
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            dead.append(ws)
    for d in dead:
        ws_connections[job_id].remove(d)


# ─────────────────────────────────────────────────────────────────────────────
# Routes – halaman utama
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# Routes – upload
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    sid: str = "",
):
    """Terima satu atau lebih PDF, simpan ke folder sesi."""
    if not sid:
        sid = _new_sid()
    s_dir = _session_dir(sid)
    sessions.setdefault(sid, {"files": {}})

    uploaded = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            continue
        fid  = uuid.uuid4().hex
        dest = s_dir / f"{fid}_{f.filename}"
        content = await f.read()
        dest.write_bytes(content)
        sessions[sid]["files"][fid] = {
            "name": f.filename,
            "path": str(dest),
            "size": len(content),
            "scan": None,
        }
        uploaded.append({"fid": fid, "name": f.filename, "size": len(content)})

    return {"sid": sid, "uploaded": uploaded}


# ─────────────────────────────────────────────────────────────────────────────
# Routes – scan
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/scan")
async def scan_files(body: dict):
    """
    Scan semua file di sesi (atau subset via fids[]).
    Body: {"sid": "...", "fids": [...]}   fids opsional
    """
    sid  = body.get("sid", "")
    fids = body.get("fids")   # None = semua

    sess = sessions.get(sid)
    if not sess:
        return {"error": "Sesi tidak ditemukan"}

    loop = asyncio.get_event_loop()
    results = []

    target = fids if fids else list(sess["files"].keys())

    async def _scan_one(fid: str):
        info = sess["files"].get(fid)
        if not info:
            return
        res = await loop.run_in_executor(_executor, PDFScanner.scan_file, info["path"])
        # Simpan hasil scan ke state
        info["scan"] = res
        results.append({
            "fid":          fid,
            "name":         info["name"],
            "size_fmt":     res["size_fmt"],
            "pages":        res["pages"],
            "has_uri":      res["has_uri"],
            "has_js":       res["has_js"],
            "has_annot":    res["has_annot"],
            "has_embedded": res["has_embedded"],
            "safe":         res["safe"],
            "issues":       res.get("issues", []),
            "error":        res.get("error"),
        })

    await asyncio.gather(*[_scan_one(fid) for fid in target])
    return {"sid": sid, "results": results}


# ─────────────────────────────────────────────────────────────────────────────
# Routes – sanitize (batch)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/sanitize")
async def start_sanitize(body: dict):
    """
    Mulai batch sanitize.
    Body: {"sid": "...", "fids": [...], "dpi": 150}
    """
    sid  = body.get("sid", "")
    fids = body.get("fids", [])
    dpi  = int(body.get("dpi", 150))

    sess = sessions.get(sid)
    if not sess:
        return {"error": "Sesi tidak ditemukan"}

    if not fids:
        fids = list(sess["files"].keys())

    job_id = uuid.uuid4().hex
    out_dir = _output_dir(job_id)

    jobs[job_id] = {
        "status":      "running",
        "total":       len(fids),
        "done":        0,
        "success":     0,
        "failed":      0,
        "results":     [],
        "output_zip":  None,
        "created_at":  time.time(),
    }
    ws_connections[job_id] = []

    # Jalankan di background task
    asyncio.create_task(_run_sanitize(job_id, sid, fids, dpi, out_dir))

    return {"job_id": job_id}


async def _run_sanitize(job_id: str, sid: str, fids: list, dpi: int, out_dir: Path):
    loop    = asyncio.get_event_loop()
    sess    = sessions.get(sid, {"files": {}})
    job     = jobs[job_id]
    total   = len(fids)
    t_start = time.monotonic()

    for i, fid in enumerate(fids):
        info = sess["files"].get(fid)
        if not info:
            continue

        src_path = Path(info["path"])
        dst_path = out_dir / info["name"]
        # Hindari nama duplikat
        if dst_path.exists():
            stem = dst_path.stem
            dst_path = out_dir / f"{stem}_{fid[:6]}.pdf"

        # Jalankan render di thread pool (CPU-bound)
        success = await loop.run_in_executor(
            _executor, PDFRenderer.render_and_rebuild, str(src_path), str(dst_path), dpi
        )

        scan  = info.get("scan") or {}
        issues = scan.get("issues", [])

        entry = {
            "fid":      fid,
            "name":     info["name"],
            "status":   "success" if success else "failed",
            "message":  ("Dibersihkan: " + ", ".join(issues)) if (success and issues)
                        else ("Dikonversi" if success else "Gagal render"),
            "out_name": dst_path.name if success else None,
        }
        job["results"].append(entry)
        job["done"]    = i + 1
        if success:
            job["success"] += 1
        else:
            job["failed"] += 1

        # Hitung ETA
        elapsed   = time.monotonic() - t_start
        rate      = (i + 1) / elapsed if elapsed > 0 else 0
        remaining = (total - (i + 1)) / rate if rate > 0 else 0

        await _broadcast(job_id, {
            "type":      "progress",
            "done":      i + 1,
            "total":     total,
            "pct":       round((i + 1) / total * 100),
            "eta":       _fmt_eta(remaining),
            "entry":     entry,
        })

    # Zip semua hasil
    zip_path = out_dir.parent / f"{job_id}.zip"
    try:
        _make_zip(out_dir, zip_path)
        job["output_zip"] = str(zip_path)
    except Exception as e:
        job["output_zip"] = None

    job["status"] = "done"
    await _broadcast(job_id, {
        "type":    "done",
        "total":   total,
        "success": job["success"],
        "failed":  job["failed"],
        "job_id":  job_id,
    })


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

def _make_zip(src_dir: Path, dest: Path):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in src_dir.iterdir():
            if f.is_file():
                zf.write(f, f.name)


# ─────────────────────────────────────────────────────────────────────────────
# Routes – WebSocket progress
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws/{job_id}")
async def ws_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()
    if job_id not in ws_connections:
        ws_connections[job_id] = []
    ws_connections[job_id].append(websocket)

    # Kalau job sudah selesai saat connect, kirim state terakhir langsung
    job = jobs.get(job_id)
    if job and job["status"] == "done":
        await websocket.send_text(json.dumps({
            "type":    "done",
            "total":   job["total"],
            "success": job["success"],
            "failed":  job["failed"],
            "job_id":  job_id,
        }))

    try:
        while True:
            await websocket.receive_text()   # keep-alive ping dari client
    except WebSocketDisconnect:
        if job_id in ws_connections:
            try:
                ws_connections[job_id].remove(websocket)
            except ValueError:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Routes – download
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/download/{job_id}")
async def download_result(job_id: str):
    job = jobs.get(job_id)
    if not job or not job.get("output_zip"):
        return {"error": "File tidak tersedia"}
    zip_path = Path(job["output_zip"])
    if not zip_path.exists():
        return {"error": "File sudah dihapus"}
    return FileResponse(
        path=str(zip_path),
        filename=f"sanitized_{job_id[:8]}.zip",
        media_type="application/zip",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Routes – status job
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"error": "Job tidak ditemukan"}
    return job


# ─────────────────────────────────────────────────────────────────────────────
# Routes – bersihkan sesi
# ─────────────────────────────────────────────────────────────────────────────

@app.delete("/api/session/{sid}")
async def delete_session(sid: str):
    s_dir = UPLOAD_DIR / sid
    if s_dir.exists():
        shutil.rmtree(s_dir, ignore_errors=True)
    sessions.pop(sid, None)
    return {"ok": True}
