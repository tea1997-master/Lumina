"""HTTP サーバー起動・ルーティング登録 (server.py)

Python 標準ライブラリの http.server を用いたローカル HTTP サーバー。
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
from pathlib import Path
import threading
from typing import Callable, Optional


class AppRequestHandler(SimpleHTTPRequestHandler):
    """静的ファイルと API をルーティングするハンドラ"""

    frontend_dir: Path = Path(__file__).resolve().parent.parent / "frontend"
    api_router: Optional[Callable] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.frontend_dir), **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/"):
            if self.api_router:
                self.api_router(self, "GET")
            else:
                self.send_error(404, "API endpoint not found")
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            if self.api_router:
                self.api_router(self, "POST")
            else:
                self.send_error(404, "API endpoint not found")
            return
        self.send_error(405, "Method Not Allowed")


class LocalServer:
    """ローカル HTTP サーバー管理クラス"""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.server = HTTPServer((host, port), AppRequestHandler)
        self.port = self.server.server_port
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
