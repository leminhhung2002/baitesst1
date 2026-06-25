"""Trình khởi động backend KOC Data System.

Chỉ cần chạy:  python server.py

File này sẽ:
  1. Tự chuyển về đúng thư mục backend (để tìm thấy app/ và .env).
  2. Kiểm tra thư viện cần thiết, nếu THIẾU thì tự cài từ requirements.txt.
  3. Khởi động FastAPI bằng uvicorn ở http://localhost:8000 (docs: /docs).

Đổi host/port bằng biến môi trường HOST / PORT nếu muốn.
"""
import os
import subprocess
import sys
from pathlib import Path

# --- 1) Luôn chạy từ thư mục chứa file này (backend/) ---
BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))


def ensure_dependencies():
    """Cài requirements nếu môi trường còn thiếu thư viện cốt lõi."""
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import sqlalchemy  # noqa: F401
        import pydantic_settings  # noqa: F401
        return
    except ImportError:
        pass

    req = BASE_DIR / "requirements.txt"
    print("Thiếu thư viện -> đang cài từ requirements.txt ...\n")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(req)]
    )
    print("\nĐã cài xong thư viện.\n")


def main():
    ensure_dependencies()

    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))

    print(f"Backend chạy tại  http://{host}:{port}")
    print(f"API docs (Swagger) http://{host}:{port}/docs\n")

    uvicorn.run("app.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
