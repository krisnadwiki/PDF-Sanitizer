"""
web_app.py – Entry point untuk menjalankan web server PDF Sanitizer.

Jalankan:
  python web_app.py
  uvicorn web_app:app --host 0.0.0.0 --port 8000 --reload

Lalu buka: http://localhost:8000
"""
import uvicorn
from web.server import app  # noqa: F401 – re-export untuk uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "web.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
