#!/usr/bin/env python3
"""設計資料検証スクリプト (lint_docs.py)

docs/ 配下の設計資料（仕様書）の整合性を検証します。
- プレースホルダ・未選択テンプレートの残骸
- 相対リンク・参照アンカーの整合性
- docs/index.md と実在ファイルの一致
- Mermaid ダイアグラムの構文・描画エラー要因

標準ライブラリのみで動作し、特定アプリケーションに依存しません。
"""

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys
from typing import Iterator


@dataclass
class LintError:
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


def find_markdown_files(docs_dir: Path) -> list[Path]:
    """検証対象の Markdown ファイル一覧を取得する (docs/_template は除外)"""
    files: list[Path] = []
    if not docs_dir.exists():
        return files

    template_dir = docs_dir / "_template"
    for md_file in docs_dir.rglob("*.md"):
        # _template 配下はスキップ
        try:
            md_file.relative_to(template_dir)
            continue
        except ValueError:
            pass
        files.append(md_file)
    return sorted(files)


# ----------------------------------------------------------------------
# 1. プレースホルダ・テンプレート残骸検査
# ----------------------------------------------------------------------

# HTMLタグ等、除外すべき正当なタグパターン
ALLOWED_TAGS = {"<br>", "<br/>", "<hr>", "<hr/>", "<details>", "</details>", "<summary>", "</summary>"}
# テンプレートのプレースホルダパターン
PLACEHOLDER_PATTERN = re.compile(r"<([a-zA-Z0-9_\-ぁ-んァ-ヶー一-龠]+)>")
# インラインコード `...` パターン
INLINE_CODE_PATTERN = re.compile(r"`[^`]+`")
# 未選択のテンプレート選択肢パターン (例: "必須、任意", "未着手、進行中、完了")
TEMPLATE_CHOICES_PATTERNS = [
    re.compile(r"（(?:必須、任意|任意、必須)）"),
    re.compile(r"（(?:未着手、進行中、完了|未確認、確認済)）"),
    re.compile(r"\[(?:必須\|任意)\]"),
]
# HTMLコメント注釈パターン
HTML_COMMENT_PATTERN = re.compile(r"<!--(.*?)-->")


def check_placeholders(file_path: Path, content: str) -> list[LintError]:
    """未置換のプレースホルダやテンプレート注釈を検出する"""
    errors: list[LintError] = []
    lines = content.splitlines()
    in_code_block = False

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # HTMLコメントの検出 (<!-- 注釈 -->)
        for match in HTML_COMMENT_PATTERN.finditer(line):
            errors.append(
                LintError(
                    file_path=file_path,
                    line_number=idx,
                    category="TEMPLATE_COMMENT",
                    message="未解決のテンプレート注釈 (HTMLコメント) が残っています",
                    context=match.group(0),
                )
            )

        # インラインコードブロック (`...`) の中身はパス記法等の説明であるため除外してプレースホルダ判定
        line_without_inline_code = INLINE_CODE_PATTERN.sub("", line)

        # プレースホルダの検出 (<...>)
        for match in PLACEHOLDER_PATTERN.finditer(line_without_inline_code):
            tag = match.group(0)
            if tag.lower() in ALLOWED_TAGS:
                continue
            errors.append(
                LintError(
                    file_path=file_path,
                    line_number=idx,
                    category="PLACEHOLDER",
                    message=f"未置換のプレースホルダ '{tag}' が残っています",
                    context=stripped,
                )
            )

        # 選択肢の未選択残骸の検出
        for pattern in TEMPLATE_CHOICES_PATTERNS:
            match = pattern.search(line)
            if match:
                errors.append(
                    LintError(
                        file_path=file_path,
                        line_number=idx,
                        category="TEMPLATE_CHOICE",
                        message=f"テンプレート選択肢 '{match.group(0)}' が選択されずに残っています",
                        context=stripped,
                    )
                )

    return errors


# ----------------------------------------------------------------------
# 2. 相対リンク・参照整合性検査
# ----------------------------------------------------------------------

MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def check_links(file_path: Path, content: str, project_root: Path) -> list[LintError]:
    """Markdown リンクの相対パスが存在するか検証する"""
    errors: list[LintError] = []
    lines = content.splitlines()
    in_code_block = False

    for idx, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        for match in MARKDOWN_LINK_PATTERN.finditer(line):
            link_text = match.group(1)
            target = match.group(2).strip()

            # 外部 URL やメール、アンカーのみのリンクはスキップ
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue

            # アンカー(#)付きパスの分離 (例: "screens/foo.md#section")
            path_part, _, anchor_part = target.partition("#")
            if not path_part:
                continue

            # 相対パスの解決
            target_path = (file_path.parent / path_part).resolve()
            if not target_path.exists():
                errors.append(
                    LintError(
                        file_path=file_path,
                        line_number=idx,
                        category="BROKEN_LINK",
                        message=f"リンク先ファイルが存在しません: '{target}'",
                        context=match.group(0),
                    )
                )

    return errors


# ----------------------------------------------------------------------
# 3. docs/index.md 整合性検査
# ----------------------------------------------------------------------

def check_index_consistency(docs_dir: Path) -> list[LintError]:
    """docs/index.md に screens/ features/ の各仕様書が網羅されているか検査する"""
    index_file = docs_dir / "index.md"
    if not index_file.exists():
        return [
            LintError(
                file_path=index_file,
                line_number=0,
                category="INDEX_MISSING",
                message="docs/index.md が存在しません",
            )
        ]

    errors: list[LintError] = []
    index_content = index_file.read_text(encoding="utf-8")

    # 実在する screen / feature 仕様書
    screens_dir = docs_dir / "screens"
    features_dir = docs_dir / "features"

    actual_screens = {f.stem: f for f in screens_dir.glob("*.md")} if screens_dir.exists() else {}
    actual_features = {f.stem: f for f in features_dir.glob("*.md")} if features_dir.exists() else {}

    # index.md 内でのリンク収集
    # screens/... や features/... への参照
    screen_links = set(re.findall(r"screens/([a-zA-Z0-9_\-]+)\.md", index_content))
    feature_links = set(re.findall(r"features/([a-zA-Z0-9_\-]+)\.md", index_content))

    # 1. 実ファイルがあるのに index.md にリンクがない
    for screen_name, path in actual_screens.items():
        if screen_name not in screen_links:
            errors.append(
                LintError(
                    file_path=index_file,
                    line_number=0,
                    category="INDEX_UNREGISTERED",
                    message=f"画面仕様書 '{screen_name}' ({path.name}) が index.md に登録されていません",
                )
            )

    for feature_name, path in actual_features.items():
        if feature_name not in feature_links:
            errors.append(
                LintError(
                    file_path=index_file,
                    line_number=0,
                    category="INDEX_UNREGISTERED",
                    message=f"機能仕様書 '{feature_name}' ({path.name}) が index.md に登録されていません",
                )
            )

    # 2. index.md にリンクがあるのに実ファイルが存在しない
    for screen_name in screen_links:
        if screen_name not in actual_screens:
            errors.append(
                LintError(
                    file_path=index_file,
                    line_number=0,
                    category="INDEX_DEAD_LINK",
                    message=f"index.md に記載された画面仕様書 'screens/{screen_name}.md' が実在しません",
                )
            )

    for feature_name in feature_links:
        if feature_name not in actual_features:
            errors.append(
                LintError(
                    file_path=index_file,
                    line_number=0,
                    category="INDEX_DEAD_LINK",
                    message=f"index.md に記載された機能仕様書 'features/{feature_name}.md' が実在しません",
                )
            )

    return errors


# ----------------------------------------------------------------------
# 4. Mermaid 構文・描画エラー要因検査
# ----------------------------------------------------------------------

VALID_DIAGRAM_PREFIXES = (
    "graph",
    "flowchart",
    "sequencediagram",
    "classdiagram",
    "statediagram",
    "statediagram-v2",
    "erdiagram",
    "gantt",
    "pie",
    "xychart-beta",
    "gitgraph",
    "mindmap",
    "timeline",
    "quadrantchart",
    "c4context",
    "architecture-beta",
    "zenuml",
)

# ノード定義内の特殊文字を含むラベルの不正記法 (引用符で囲まれていないカッコ)
# 例: id[テキスト(補足)] -> 正しくは id["テキスト(補足)"]
UNQUOTED_PAREN_IN_LABEL = re.compile(r"(\w+)\s*\[([^\"\]\n]*[\(\)\{\}][^\"\]\n]*)\]")


def check_mermaid_blocks(file_path: Path, content: str) -> list[LintError]:
    """Markdown 内の Mermaid コードブロックを検査する"""
    errors: list[LintError] = []
    lines = content.splitlines()

    in_mermaid = False
    block_start_line = 0
    mermaid_lines: list[tuple[int, str]] = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```mermaid"):
            in_mermaid = True
            block_start_line = idx
            mermaid_lines = []
            continue
        elif in_mermaid and stripped.startswith("```"):
            in_mermaid = False
            # ブロック終了時に検証を実行
            errors.extend(_validate_mermaid_diagram(file_path, block_start_line, mermaid_lines))
            continue

        if in_mermaid:
            mermaid_lines.append((idx, line))

    if in_mermaid:
        errors.append(
            LintError(
                file_path=file_path,
                line_number=block_start_line,
                category="MERMAID_UNCLOSED",
                message="Mermaid ブロック (```mermaid) が閉じられていません",
            )
        )

    return errors


def _validate_mermaid_diagram(
    file_path: Path, start_line: int, lines: list[tuple[int, str]]
) -> list[LintError]:
    """Mermaid ブロック内の行を精査する"""
    errors: list[LintError] = []

    # 有効な行 (空行・コメント除外)
    active_lines: list[tuple[int, str]] = []
    for line_no, raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        active_lines.append((line_no, stripped))

    if not active_lines:
        errors.append(
            LintError(
                file_path=file_path,
                line_number=start_line,
                category="MERMAID_EMPTY",
                message="Mermaid ブロックが空です",
            )
        )
        return errors

    # 1. 先頭宣言の検証
    first_line_no, first_line = active_lines[0]
    first_token = first_line.split()[0].lower() if first_line.split() else ""
    if not any(first_token.startswith(prefix) for prefix in VALID_DIAGRAM_PREFIXES):
        errors.append(
            LintError(
                file_path=file_path,
                line_number=first_line_no,
                category="MERMAID_INVALID_TYPE",
                message=f"未知またはサポート外のダイアグラム宣言です: '{first_line}'",
                context=first_line,
            )
        )

    # 2. subgraph と end の対応関係の追跡
    subgraph_depth = 0
    for line_no, stripped in active_lines:
        tokens = stripped.split()
        if tokens and tokens[0] == "subgraph":
            subgraph_depth += 1
        elif tokens and tokens[0] == "end":
            subgraph_depth -= 1
            if subgraph_depth < 0:
                errors.append(
                    LintError(
                        file_path=file_path,
                        line_number=line_no,
                        category="MERMAID_MISMATCHED_END",
                        message="'end' に対応する 'subgraph' がありません",
                        context=stripped,
                    )
                )
                subgraph_depth = 0

    if subgraph_depth > 0:
        errors.append(
            LintError(
                file_path=file_path,
                line_number=start_line,
                category="MERMAID_UNCLOSED_SUBGRAPH",
                message=f"{subgraph_depth} 個の 'subgraph' が 'end' で閉じられていません",
            )
        )

    # 3. 描画エラーを招く特殊文字・カッコのクォート漏れ検知
    for line_no, stripped in active_lines:
        # ノードラベル内の特殊文字クォート漏れ: A[ラベル (補足)] -> A["ラベル (補足)"]
        match = UNQUOTED_PAREN_IN_LABEL.search(stripped)
        if match:
            errors.append(
                LintError(
                    file_path=file_path,
                    line_number=line_no,
                    category="MERMAID_UNQUOTED_LABEL",
                    message="ノードラベルにカッコ等の特殊記号が含まれていますが、二重引用符 '\"' で囲まれていません",
                    context=stripped,
                )
            )

        # 矢印記号のスペース混入タイポ (例: "-- >", "== >")
        if re.search(r"(--\s+>|==\s+>|-\.\s+>)", stripped):
            errors.append(
                LintError(
                    file_path=file_path,
                    line_number=line_no,
                    category="MERMAID_ARROW_SYNTAX",
                    message="接続矢印記号の中に不要な空白が含まれています",
                    context=stripped,
                )
            )

        # 括弧の対の不一致 (簡易検出: [ に対して ) で閉じるなど、クォート外を対象とする)
        # クォート文字列 "..." を一時的に除外してからチェック
        unquoted = re.sub(r'"[^"]*"', '""', stripped)
        if re.search(r"\w+\[[^\]]*\)", unquoted) or re.search(r"\w+\([^\)]*\]", unquoted):
            errors.append(
                LintError(
                    file_path=file_path,
                    line_number=line_no,
                    category="MERMAID_BRACKET_MISMATCH",
                    message="ノード定義の開きカッコと閉じカッコの形状が一致していません",
                    context=stripped,
                )
            )

    return errors


# ----------------------------------------------------------------------
# メイン処理
# ----------------------------------------------------------------------

def run_lint(docs_dir: Path, target_file: Path | None = None) -> list[LintError]:
    """すべての設計資料検査を実行する"""
    all_errors: list[LintError] = []
    project_root = docs_dir.parent

    # 単一ファイル指定または docs 全体走査
    if target_file:
        files = [target_file]
    else:
        files = find_markdown_files(docs_dir)
        # index.md 整合性検査は全走査時のみ実行
        all_errors.extend(check_index_consistency(docs_dir))

    for md_file in files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            all_errors.append(
                LintError(
                    file_path=md_file,
                    line_number=0,
                    category="ENCODING_ERROR",
                    message="UTF-8 でデコードできません",
                )
            )
            continue

        all_errors.extend(check_placeholders(md_file, content))
        all_errors.extend(check_links(md_file, content, project_root))
        all_errors.extend(check_mermaid_blocks(md_file, content))

    return all_errors


def main() -> int:
    # Windows コンソールでの文字化け防止
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    parser = argparse.ArgumentParser(description="設計資料（docs/）の品質・整合性検証スクリプト")
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        default=None,
        help="特定の Markdown ファイルのみを検証する",
    )
    args = parser.parse_args()

    project_root = get_project_root()
    docs_dir = project_root / "docs"

    target_file = None
    if args.file:
        target_file = args.file if args.file.is_absolute() else (project_root / args.file)
        if not target_file.exists():
            print(f"エラー: 指定されたファイルが存在しません: {target_file}", file=sys.stderr)
            return 1

    print(f"=== 設計資料検証スクリプト (lint_docs.py) ===")
    print(f"対象ディレクトリ: {docs_dir}")
    if target_file:
        print(f"対象ファイル: {target_file.name}")
    print()

    errors = run_lint(docs_dir, target_file)

    if not errors:
        print("OK: すべての設計資料検査に合格しました。問題は見つかりませんでした。")
        return 0

    print(f"FAILED: {len(errors)} 件の問題が見つかりました:\n")
    for err in errors:
        print(f"  - {err}")

    print()
    print("修正後に再度 scripts/lint_docs.py を実行してください。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
