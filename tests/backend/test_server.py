"""サーバーモジュールの基盤検証テスト"""

from server import AppRequestHandler


def test_request_handler_frontend_dir():
    """AppRequestHandler の frontend_dir が正しく設定されていることを検証"""
    assert AppRequestHandler.frontend_dir.exists()
    assert (AppRequestHandler.frontend_dir / "index.html").exists()
