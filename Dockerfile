# ─────────────────────────────────────────────────────────────────────────────
# PDF Sanitizer – Dockerfile
#
# Tersedia tiga target build:
#   web  (default) – FastAPI web interface, buka di browser
#   cli            – batch convert headless via terminal
#   gui            – desktop GUI via X11 (Linux/WSL2)
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage base ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
VOLUME ["/tmp/pdf_sanitizer_uploads"]


# ── Stage web (default) ──────────────────────────────────────────────────────
FROM base AS web

COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", "8000"]


# ── Stage cli ────────────────────────────────────────────────────────────────
FROM base AS cli

COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

COPY . .
VOLUME ["/input", "/output"]

ENV PYTHONUNBUFFERED=1
CMD ["python", "cli.py", "--input", "/input", "--output", "/output", "--recursive"]


# ── Stage gui (X11) ──────────────────────────────────────────────────────────
FROM base AS gui

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libxcb1 libx11-xcb1 libxrender1 libxext6 \
    libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 \
    libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
    libxcb-shape0 libxcb-shm0 libxcb-sync1 libxcb-xfixes0 \
    libxcb-xinerama0 libxcb-xkb1 libfontconfig1 libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV QT_QPA_PLATFORM=xcb
CMD ["python", "app.py"]
