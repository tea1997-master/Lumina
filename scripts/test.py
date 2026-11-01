#!/usr/bin/env python3
"""テスト実行スクリプト (test.py)

pytest をラップし、機能別・種別 (backend / ui) の絞り込み実行を支援します。
- `-f <機能名>`: 指定機能のテストに絞り込む
- `--backend`: バックエンドテスト (tests/backend/) のみに絞る
- `--ui`: UI テスト (tests/ui/) のみに絞る
- その他の引数はすべて pytest へ透過的に転送
- `--import-mode=importlib` を自動付与

標準ライブラリのみで動作し、特定アプリケーションに依存しません。
"""

import argparse
from pathlib import Path
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


def find_feature_test_files(tests_dir: Path, feature: str, target_kind: str | None) -> list[Path]:
    """機能名に対応するテストファイルを検索する (ハイフン/アンダースコア両対応)"""
    feature_variants = {
        feature,
        feature.replace("-", "_"),
        feature.replace("_", "-"),
    }

    subdirs: list[str] = []
    if target_kind == "backend":
        subdirs = ["backend"]
    elif target_kind == "ui":
        subdirs = ["ui"]
    else:
        subdirs = ["backend", "ui"]

    matched_files: list[Path] = []
    for subdir in subdirs:
        dir_path = tests_dir / subdir
        if not dir_path.exists():
            continue
        for variant in feature_variants:
            candidate = dir_path / f"test_{variant}.py"
            if candidate.exists() and candidate not in matched_files:
                matched_files.append(candidate)

    return matched_files


def main() -> int:
    # Windows コンソールでの文字化け防止
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    parser = argparse.ArgumentParser(
        description="テスト実行スクリプト (pytest ラッパー)",
        add_help=False,  # -h / --help は pytest にも渡せるように独自処理
    )
    parser.add_argument(
        "-f",
        "--feature",
        type=str,
        default=None,
        help="テスト対象の機能名 (例: -f auth)",
    )
    parser.add_argument(
        "--backend",
        action="store_true",
        help="バックエンドテスト (tests/backend/) のみに絞り込む",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="UI テスト (tests/ui/) のみに絞り込む",
    )
    parser.add_argument(
        "--help-script",
        action="store_true",
        help="このラッパースクリプト自体のヘルプを表示する",
    )

    args, pytest_extra_args = parser.parse_known_args()

    if args.help_script:
        parser.print_help()
        print("\nその他の引数はすべて直接 pytest に渡されます (例: -v, -s, -k, --lf, -h 等)")
        return 0

    project_root = get_project_root()
    venv_python = get_venv_python(project_root)

    # 仮想環境の存在チェック
    if not venv_python.exists():
        print(
            f"エラー: 仮想環境の Python が見つかりません: {venv_python}\n"
            "先に ./scripts/setup.py を実行して開発環境を整備してください。",
            file=sys.stderr,
        )
        return 1

    tests_dir = project_root / "tests"

    # テスト対象パスの解決
    target_kind = "backend" if args.backend and not args.ui else ("ui" if args.ui and not args.backend else None)
    target_paths: list[str] = []

    if args.feature:
        matched = find_feature_test_files(tests_dir, args.feature, target_kind)
        if not matched:
            kind_str = f" ({target_kind})" if target_kind else ""
            print(
                f"警告: 機能 '{args.feature}'{kind_str} に対応するテストファイルが見つかりません。\n"
                f"検索対象: tests/backend/test_{args.feature}.py または tests/ui/test_{args.feature}.py",
                file=sys.stderr,
            )
            # 該当がなくても pytest にパスを渡して明示的に結果を出力させる
            if target_kind:
                target_paths.append(str(tests_dir / target_kind / f"test_{args.feature.replace('-', '_')}.py"))
            else:
                target_paths.append(str(tests_dir / "backend" / f"test_{args.feature.replace('-', '_')}.py"))
        else:
            target_paths.extend(str(p) for p in matched)
    elif target_kind == "backend":
        backend_dir = tests_dir / "backend"
        target_paths.append(str(backend_dir if backend_dir.exists() else tests_dir))
    elif target_kind == "ui":
        ui_dir = tests_dir / "ui"
        target_paths.append(str(ui_dir if ui_dir.exists() else tests_dir))
    else:
        # 引数なし: 全テスト実行
        target_paths.append(str(tests_dir if tests_dir.exists() else project_root))

    # pytest コマンドの構築
    # AGENTS.md 規約: --import-mode=importlib を常に指定
    # サンドボックス環境下でのワークスペース内ファイルロック競合を防ぐため cache_dir を一時ディレクトリに設定
    import tempfile
    default_cache_dir = Path(tempfile.gettempdir()) / ".pytest_cache"

    cmd = [
        str(venv_python),
        "-m",
        "pytest",
        "--import-mode=importlib",
        f"-o",
        f"cache_dir={default_cache_dir}",
    ]

    # 追加引数と対象パスの統合
    cmd.extend(target_paths)
    cmd.extend(pytest_extra_args)

    print(f"=== テスト実行スクリプト (test.py) ===")
    print(f"実行コマンド: {' '.join(cmd)}\n")

    # pytest の実行
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
