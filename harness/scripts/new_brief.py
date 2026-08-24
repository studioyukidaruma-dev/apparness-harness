#!/usr/bin/env python3
"""企画ブリーフの記入用フォーマットを生成する。

ブリーフは `init-app` の**前**に人間が書くファイル。要件を対話で少しずつ引き出す代わりに、
目的・必要な機能・使ってほしい技術などを一度にまとめて渡すための固定フォーマットである。
空欄のままで構わない（未記入項目は要件定義の対話で確認される）。

使い方:
    python3 harness/scripts/new_brief.py <app_id> [app_name] [--out PATH] [--force]

既定の出力先は `briefs/<app_id>.brief.yaml`。`init-app` はこのパスを自動で探す。
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402

APP_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def default_brief_path(root: pathlib.Path, app_id: str) -> pathlib.Path:
    return root / "briefs" / f"{app_id}.brief.yaml"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="企画ブリーフの記入用フォーマットを生成する")
    parser.add_argument("app_id", help="アプリ ID（kebab-case。例: hello-world-todo）")
    parser.add_argument("app_name", nargs="?", default="", help="人間向けのアプリ名（省略可）")
    parser.add_argument("--out", help="出力先（省略時は briefs/<app_id>.brief.yaml）")
    parser.add_argument("--force", action="store_true", help="既存ファイルを上書きする")
    args = parser.parse_args(argv[1:])

    if not APP_ID_RE.match(args.app_id):
        print(
            f"エラー: app_id は kebab-case にしてください（例: hello-world-todo）: {args.app_id!r}",
            file=sys.stderr,
        )
        return 2

    try:
        root = _common.main_repo_root()
    except Exception:  # noqa: BLE001
        root = pathlib.Path.cwd()

    dest = pathlib.Path(args.out) if args.out else default_brief_path(root, args.app_id)
    if dest.exists() and not args.force:
        print(f"エラー: {dest} は既に存在します（上書きするなら --force）", file=sys.stderr)
        return 2

    tmpl_path = _common.harness_root(root) / "templates" / "brief.yaml.tmpl"
    try:
        template = tmpl_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"エラー: テンプレートを読み込めません ({tmpl_path}): {e}", file=sys.stderr)
        return 2

    try:
        shown_path = str(dest.relative_to(root))
    except ValueError:
        shown_path = str(dest)

    values = {
        "APP_ID": args.app_id,
        "APP_NAME": args.app_name,
        "TIMESTAMP": _common.now_iso(),
        "BRIEF_PATH": shown_path,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_common.render_template(template, values), encoding="utf-8")

    print(f"作成しました: {dest}")
    print("次のステップ:")
    print("  1. このファイルを編集する（分かるところだけでよい。空欄は対話で確認されます）")
    print(f"  2. python3 harness/scripts/check_brief.py {shown_path}")
    print(f"  3. `init-app` skill を起動する（{shown_path} は自動で読み込まれます）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
