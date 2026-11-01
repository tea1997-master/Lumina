"""デスクトップエントリポイント (pywebview)
"""

import os
from pathlib import Path
import sys
import webview

from server import LocalServer, AppRequestHandler


def resolve_frontend_dir() -> Path:
    """実行環境（PyInstaller バンドル環境または開発環境）に応じたフロントエンドパスを取得"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "frontend"
    return Path(__file__).resolve().parent.parent / "frontend"


def main() -> None:
    frontend_dir = resolve_frontend_dir()
    AppRequestHandler.frontend_dir = frontend_dir

    server = LocalServer(host="127.0.0.1", port=0)
    server.start()

    url = f"http://127.0.0.1:{server.port}/index.html"
    window = webview.create_window("Lumina", url=url, width=1024, height=768)

    try:
        webview.start()
    finally:
        server.stop()


if __name__ == "__main__":
    main()
