#!/usr/bin/env python3
"""環境整備スクリプト (setup.py)

プロジェクト用の仮想環境 (.venv) を作成し、必要な依存関係をインストール・検証します。
標準ライブラリのみで動作します。
"""

import argparse
import importlib.metadata
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def get_project_root() -> Path:
    """スクリプトの配置場所からプロジェクトルートパスを取得する"""
    return Path(__file__).resolve().parent.parent


def get_venv_paths(project_root: Path) -> tuple[Path, Path]:
    """仮想環境ディレクトリと Python 実行可能ファイルのパスを取得する"""
    venv_dir = project_root / ".venv"
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
    return venv_dir, venv_python


def run_command(cmd: list[str], cwd: Path | None = None) -> None:
    """コマンドを実行し、失敗時は例外を発生させる"""
    print(f"-> {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"コマンドが失敗しました (終了コード: {result.returncode}): {' '.join(cmd)}")


def setup_venv(venv_dir: Path, recreate: bool = False) -> None:
    """仮想環境を作成する"""
    if venv_dir.exists():
        if recreate:
            print(f"[1/4] 既存の仮想環境を削除しています: {venv_dir}")
            shutil.rmtree(venv_dir)
        else:
            print(f"[1/4] 仮想環境は既に存在します: {venv_dir}")
            return

    print(f"[1/4] 仮想環境を作成しています: {venv_dir}")
    run_command([sys.executable, "-m", "venv", str(venv_dir)])


def upgrade_pip(venv_python: Path) -> None:
    """仮想環境内の pip を最新化する"""
    print("[2/4] pip を最新化しています...")
    run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])


def install_requirements(venv_python: Path, project_root: Path) -> list[str]:
    """requirements.txt に基づいて依存パッケージをインストールし、パッケージ名一覧を返す"""
    req_file = project_root / "requirements.txt"
    if not req_file.exists():
        print(f"[3/4] {req_file.name} が見つかりません。スキップします。")
        return []

    print(f"[3/4] 依存パッケージをインストールしています ({req_file.name})...")
    run_command([str(venv_python), "-m", "pip", "install", "-r", str(req_file)], cwd=project_root)

    packages: list[str] = []
    with open(req_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # パッケージ名のみ抽出 (例: pywebview>=5.0 -> pywebview)
            pkg_name = re.split(r"[=<>!~;@\s]", line)[0].strip()
            if pkg_name:
                packages.append(pkg_name)
    return packages


def verify_installation(venv_python: Path, packages: list[str]) -> None:
    """pip check による依存整合性検証および各パッケージのインストール確認を行う"""
    print("[4/4] 環境の整合性を検証しています...")
    # pip check で依存関係の不整合がないか確認
    run_command([str(venv_python), "-m", "pip", "check"])

    # requirements.txt に記載されたパッケージのインストール確認
    if packages:
        test_script = (
            "import sys, importlib.metadata; "
            f"pkgs = {packages!r}; "
            "missing = [p for p in pkgs if not any(dist.metadata['Name'].lower() == p.lower() for dist in importlib.metadata.distributions())]; "
            "assert not missing, f'未インストールのパッケージがあります: {missing}'; "
            "print(f'-> インストール確認完了 ({len(pkgs)} パッケージ): {', '.join(pkgs)}')"
        )
        run_command([str(venv_python), "-c", test_script])


def main() -> int:
    parser = argparse.ArgumentParser(description="プロジェクト用仮想環境のセットアップスクリプト")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="既存の .venv を削除して新しく作成し直す",
    )
    args = parser.parse_args()

    project_root = get_project_root()
    venv_dir, venv_python = get_venv_paths(project_root)

    print(f"=== 開発環境整備スクリプト ({project_root.name}) ===")
    print(f"プロジェクトルート: {project_root}")
    print(f"Python バージョン: {sys.version.split()[0]}")
    print()

    try:
        setup_venv(venv_dir, recreate=args.recreate)
        upgrade_pip(venv_python)
        packages = install_requirements(venv_python, project_root)
        verify_installation(venv_python, packages)
        print()
        print("=== セットアップが正常に完了しました ===")
        print(f"仮想環境の Python: {venv_python}")
        return 0
    except Exception as e:
        print()
        print(f"エラー: セットアップ中に問題が発生しました: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
