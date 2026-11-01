#!/usr/bin/env python3
"""コード構造検証スクリプト (lint_code.py)

docs/app.md に定義されたコード規約・アーキテクチャ構造を検証します。
- ファイルサイズ制限 (目安 150〜300 行)
- レイヤ間の依存関係と一方向規則 (Frontend / Backend)
- Pure JS (DOM非依存) / Pure Python (HTTP非依存) の独立性
- data-testid の命名規約 (Frontend)

標準ライブラリのみで動作し、特定アプリケーションに依存しません。
"""

import argparse
import ast
from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys


@dataclass
class CodeLintError:
    file_path: Path
    line_number: int
    category: str
    message: str
    context: str = ""

    def __str__(self) -> str:
        loc = f"{self.file_path}:{self.line_number}" if self.line_number > 0 else str(self.file_path)
        ctx = f" -> {self.context.strip()}" if self.context else ""
        return f"[{self.category}] {loc}: {self.message}{ctx}"


def get_project_root() -> Path:
    """スクリプトの配置場所からプロジェクトルートパスを取得する"""
    return Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------------
# 1. ファイルサイズ検査
# ----------------------------------------------------------------------

def check_file_size(file_path: Path, max_lines: int) -> list[CodeLintError]:
    """1ファイルの行数が上限を超えていないか検査する"""
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [
            CodeLintError(
                file_path=file_path,
                line_number=0,
                category="ENCODING_ERROR",
                message="UTF-8 で読み込めません",
            )
        ]

    line_count = len(content.splitlines())
    if line_count > max_lines:
        return [
            CodeLintError(
                file_path=file_path,
                line_number=line_count,
                category="FILE_SIZE_LIMIT",
                message=f"ファイル行数 ({line_count} 行) が上限 ({max_lines} 行) を超えています",
            )
        ]
    return []


# ----------------------------------------------------------------------
# 2. Frontend 依存関係・規約検査
# ----------------------------------------------------------------------

JS_IMPORT_PATTERN = re.compile(
    r"""import\s+(?:(?:[\w*\s{},]*)\s+from\s+)?['"]([^'"]+)['"]"""
)
FORBIDDEN_DOM_IN_FEATURE = re.compile(r"\b(window|document|localStorage|sessionStorage)\b")


def check_frontend_file(file_path: Path, frontend_root: Path) -> list[CodeLintError]:
    """Frontend コード (screens, features, api, common) の依存と規約を検査する"""
    errors: list[CodeLintError] = []
    rel_path = file_path.relative_to(frontend_root)
    parts = rel_path.parts

    layer = parts[0] if parts else ""
    is_js = file_path.suffix == ".js"
    is_html = file_path.suffix == ".html"

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return errors

    lines = content.splitlines()

    # (A) HTML 画面層の data-testid 規約検査
    if is_html and layer == "screens" and len(parts) >= 2:
        screen_name = parts[1]
        testid_pattern = re.compile(r'data-testid=["\']([^"\']+)["\']')
        for idx, line in enumerate(lines, start=1):
            for match in testid_pattern.finditer(line):
                testid = match.group(1)
                expected_prefix = f"{screen_name}--"
                if not testid.startswith(expected_prefix):
                    errors.append(
                        CodeLintError(
                            file_path=file_path,
                            line_number=idx,
                            category="INVALID_TESTID",
                            message=f"data-testid '{testid}' は画面名プレフィックス '{expected_prefix}' で始まる必要があります",
                            context=match.group(0),
                        )
                    )

    if not is_js:
        return errors

    # (B) features/ の Pure JS 規則 (DOM 非依存)
    if layer == "features":
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            match = FORBIDDEN_DOM_IN_FEATURE.search(stripped)
            if match:
                errors.append(
                    CodeLintError(
                        file_path=file_path,
                        line_number=idx,
                        category="DOM_IN_FEATURE",
                        message=f"機能層 (features) で DOM オブジェクト '{match.group(1)}' にアクセスしています (Pure JS 規約違反)",
                        context=stripped,
                    )
                )

    # (C) レイヤ間依存関係検査 (import 文の解析)
    for idx, line in enumerate(lines, start=1):
        for match in JS_IMPORT_PATTERN.finditer(line):
            import_target = match.group(1)
            # 相対パスを解決
            if import_target.startswith("."):
                resolved_target = (file_path.parent / import_target).resolve()
                try:
                    target_rel = resolved_target.relative_to(frontend_root)
                    target_layer = target_rel.parts[0] if target_rel.parts else ""
                except ValueError:
                    continue  # frontend_root 外のインポート
            else:
                continue

            # レイヤ依存規則のチェック
            # 許可される依存:
            # - screens -> features, common
            # - features -> api, common
            # - api -> common
            # - common -> common
            if layer == "screens" and target_layer == "api":
                errors.append(
                    CodeLintError(
                        file_path=file_path,
                        line_number=idx,
                        category="FORBIDDEN_DEPENDENCY",
                        message="画面層 (screens) から通信層 (api) への直接参照は禁止されています (features 経由にしてください)",
                        context=line.strip(),
                    )
                )
            elif layer == "features" and target_layer == "screens":
                errors.append(
                    CodeLintError(
                        file_path=file_path,
                        line_number=idx,
                        category="FORBIDDEN_DEPENDENCY",
                        message="機能層 (features) から画面層 (screens) への逆方向参照は禁止されています",
                        context=line.strip(),
                    )
                )
            elif layer == "api" and target_layer in ("screens", "features"):
                errors.append(
                    CodeLintError(
                        file_path=file_path,
                        line_number=idx,
                        category="FORBIDDEN_DEPENDENCY",
                        message=f"通信層 (api) から上位層 ({target_layer}) への逆方向参照は禁止されています",
                        context=line.strip(),
                    )
                )
            elif layer == "common" and target_layer in ("screens", "features", "api"):
                errors.append(
                    CodeLintError(
                        file_path=file_path,
                        line_number=idx,
                        category="FORBIDDEN_DEPENDENCY",
                        message=f"共通基盤層 (common) から上位層 ({target_layer}) への参照は禁止されています",
                        context=line.strip(),
                    )
                )

    return errors


# ----------------------------------------------------------------------
# 3. Backend 依存関係・規約検査
# ----------------------------------------------------------------------

class PythonImportVisitor(ast.NodeVisitor):
    def __init__(self, current_file: Path, backend_root: Path):
        self.current_file = current_file
        self.backend_root = backend_root
        self.imports: list[tuple[int, str]] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append((node.lineno, alias.name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        self.imports.append((node.lineno, module))
        self.generic_visit(node)


def check_backend_file(file_path: Path, backend_root: Path) -> list[CodeLintError]:
    """Backend コード (api, services, storage, common, server/main) の依存と規約を検査する"""
    errors: list[CodeLintError] = []
    rel_path = file_path.relative_to(backend_root)
    parts = rel_path.parts

    layer = parts[0] if len(parts) > 1 else "root"
    if file_path.suffix != ".py":
        return errors

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        return [
            CodeLintError(
                file_path=file_path,
                line_number=e.lineno or 0,
                category="SYNTAX_ERROR",
                message=f"Python 構文エラー: {e.msg}",
            )
        ]
    except Exception:
        return errors

    visitor = PythonImportVisitor(file_path, backend_root)
    visitor.visit(tree)

    # サービス層の Pure Python 規則 (HTTP サーバー非依存)
    if layer == "services":
        for lineno, mod_name in visitor.imports:
            if mod_name.startswith(("http.server", "urllib", "requests")):
                errors.append(
                    CodeLintError(
                        file_path=file_path,
                        line_number=lineno,
                        category="HTTP_IN_SERVICE",
                        message=f"サービス層 (services) で HTTP 関連モジュール '{mod_name}' を直接参照しています (Pure Python 規約違反)",
                    )
                )

    # レイヤ依存関係の検査
    # 許可される依存:
    # - server / main -> api, services, storage, common
    # - api -> services, common
    # - services -> storage, common
    # - storage -> common
    # - common -> common
    for lineno, mod_name in visitor.imports:
        # 相対インポートや backend パッケージ内のインポートを判定
        target_layer = None
        mod_parts = mod_name.split(".")
        for candidate in ("api", "services", "storage", "common"):
            if candidate in mod_parts:
                target_layer = candidate
                break

        if not target_layer:
            continue

        if layer == "api" and target_layer == "storage":
            errors.append(
                CodeLintError(
                    file_path=file_path,
                    line_number=lineno,
                    category="FORBIDDEN_DEPENDENCY",
                    message="API・ルーティング層 (api) からデータ層 (storage) への直接参照は禁止されています (services 経由にしてください)",
                )
            )
        elif layer == "services" and target_layer == "api":
            errors.append(
                CodeLintError(
                    file_path=file_path,
                    line_number=lineno,
                    category="FORBIDDEN_DEPENDENCY",
                    message="サービス層 (services) から API 層 (api) への逆方向参照は禁止されています",
                )
            )
        elif layer == "storage" and target_layer in ("services", "api"):
            errors.append(
                CodeLintError(
                    file_path=file_path,
                    line_number=lineno,
                    category="FORBIDDEN_DEPENDENCY",
                    message=f"データ層 (storage) から上位層 ({target_layer}) への逆方向参照は禁止されています",
                )
            )
        elif layer == "common" and target_layer in ("api", "services", "storage"):
            errors.append(
                CodeLintError(
                    file_path=file_path,
                    line_number=lineno,
                    category="FORBIDDEN_DEPENDENCY",
                    message=f"共通基盤層 (common) から上位層 ({target_layer}) への参照は禁止されています",
                )
            )

    return errors


# ----------------------------------------------------------------------
# メイン処理
# ----------------------------------------------------------------------

def run_lint_code(project_root: Path, max_lines: int = 300) -> list[CodeLintError]:
    """src/ 配下のすべてのコード構造を検証する"""
    all_errors: list[CodeLintError] = []
    src_dir = project_root / "src"

    if not src_dir.exists():
        # まだ src がない初期段階では正常終了
        return []

    frontend_root = src_dir / "frontend"
    backend_root = src_dir / "backend"

    # 全対象ファイルの走査 (.py, .js, .html, .css)
    valid_exts = {".py", ".js", ".html", ".css"}
    for file_path in src_dir.rglob("*"):
        if not file_path.is_file() or file_path.suffix not in valid_exts:
            continue

        # 1. ファイルサイズ検査
        all_errors.extend(check_file_size(file_path, max_lines))

        # 2. Frontend 規約検査
        if frontend_root.exists() and frontend_root in file_path.parents:
            all_errors.extend(check_frontend_file(file_path, frontend_root))

        # 3. Backend 規約検査
        if backend_root.exists() and backend_root in file_path.parents:
            all_errors.extend(check_backend_file(file_path, backend_root))

    return all_errors


def main() -> int:
    # Windows コンソールでの文字化け防止
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    parser = argparse.ArgumentParser(description="コード構造・アーキテクチャ規約検証スクリプト")
    parser.add_argument(
        "--max-lines",
        type=int,
        default=300,
        help="1ファイルあたりの最大行数制限 (デフォルト: 300)",
    )
    args = parser.parse_args()

    project_root = get_project_root()
    src_dir = project_root / "src"

    print(f"=== コード構造検証スクリプト (lint_code.py) ===")
    print(f"プロジェクトルート: {project_root}")
    print(f"行数制限: {args.max_lines} 行/ファイル")
    print()

    if not src_dir.exists():
        print("INFO: src/ ディレクトリが存在しないため、コード構造検査をスキップします。")
        return 0

    errors = run_lint_code(project_root, max_lines=args.max_lines)

    if not errors:
        print("OK: すべてのコード構造検査に合格しました。規約違反は見つかりませんでした。")
        return 0

    print(f"FAILED: {len(errors)} 件の規約違反が見つかりました:\n")
    for err in errors:
        print(f"  - {err}")

    print()
    print("修正後に再度 scripts/lint_code.py を実行してください。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
