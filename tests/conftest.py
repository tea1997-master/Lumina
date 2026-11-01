"""共通 pytest fixture 定義 (tests/conftest.py)

- sys.path への src/backend 追加
- テスト用インメモリストレージやモック基盤
"""

from pathlib import Path
import sys
import pytest

# src/backend を import パスに追加
backend_path = Path(__file__).resolve().parent.parent / "src" / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))
