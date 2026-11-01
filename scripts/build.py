#!/usr/bin/env python3
"""ビルドスクリプト (build.py)

PyInstaller を使用して、デスクトップアプリケーションの実行ファイルを生成します。
- エントリポイント (src/backend/main.py) とフロントエンド資産 (src/frontend/) を自動パッケージング
- 出力先: dist/<プロジェクト名>.exe (または --name で指定)
- 仮想環境内の PyInstaller を自動検出して実行

標準ライブラリのみで動作し、特定アプリケーションに依存しません。
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def get_project_root() -> Path:
    """スクリプトの配置場所からプロジェクトルートパスを取得する"""
    return Path(__file__).resolve().parent.parent


def get_venv_python(project_root: Path) -> Path:
    """仮想環境内の Python 実行パスを取得する"""
    venv_dir = project_root / ".venv"
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
    return venv_python


def main() -> int:
    # Windows コンソールでの文字化け防止
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    project_root = get_project_root()
    default_name = project_root.name

    parser = argparse.ArgumentParser(description="デスクトップアプリケーションのビルドスクリプト")
    parser.add_argument(
        "--name",
        type=str,
        default=default_name,
        help=f"生成する実行ファイル名 (デフォルト: {default_name})",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="コンソールウィンドウを表示した状態でビルドする (デバッグ用)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=True,
        help="ビルド前に以前のビルド成果物・一時ファイルをクリーンアップする (デフォルト: True)",
    )
    args = parser.parse_args()

    venv_python = get_venv_python(project_root)
    if not venv_python.exists():
        print(
            f"エラー: 仮想環境の Python が見つかりません: {venv_python}\n"
            "先に ./scripts/setup.py を実行して開発環境を整備してください。",
            file=sys.stderr,
        )
        return 1

    entry_point = project_root / "src" / "backend" / "main.py"
    if not entry_point.exists():
        print(
            f"エラー: エントリポイントが見つかりません: {entry_point}\n"
            "アプリケーションのエントリポイント (src/backend/main.py) を作成した後に実行してください。",
            file=sys.stderr,
        )
        return 1

    frontend_dir = project_root / "src" / "frontend"
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"

    # クリーンアップ
    if args.clean:
        print("[1/3] 以前のビルド成果物をクリーンアップしています...")
        target_exe = dist_dir / (f"{args.name}.exe" if sys.platform == "win32" else args.name)
        if target_exe.exists():
            try:
                target_exe.unlink()
            except Exception:
                pass

    print(f"[2/3] PyInstaller によるビルドを実行しています (アプリ名: {args.name})...")

    # PyInstaller コマンドの構築
    cmd = [
        str(venv_python),
        "-m",
        "PyInstaller",
        "--name",
        args.name,
        "--onefile",
        "--clean",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        "--specpath",
        str(build_dir),
    ]

    # ウィンドウモード設定 (GUIアプリのためデフォルトはコンソール非表示)
    if not args.console:
        cmd.append("--noconsole")

    # フロントエンド静的ファイルの同梱設定
    if frontend_dir.exists():
        sep = ";" if sys.platform == "win32" else ":"
        cmd.extend(["--add-data", f"{frontend_dir}{sep}frontend"])

    # エントリポイントの追加
    cmd.append(str(entry_point))

    print(f"-> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_root)
    if result.returncode != 0:
        print(f"\nエラー: ビルドに失敗しました (終了コード: {result.returncode})", file=sys.stderr)
        return result.returncode

    # 成果物の確認
    expected_exe = dist_dir / (f"{args.name}.exe" if sys.platform == "win32" else args.name)
    print("\n[3/3] ビルド結果の確認...")
    if expected_exe.exists():
        file_size_mb = expected_exe.stat().st_size / (1024 * 1024)
        print(f"OK: 実行ファイルが正常に生成されました: {expected_exe} ({file_size_mb:.2f} MB)")
        return 0
    else:
        print(f"エラー: 期待される実行ファイルが生成されませんでした: {expected_exe}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
