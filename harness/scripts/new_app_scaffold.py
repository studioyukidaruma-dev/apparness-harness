#!/usr/bin/env python3
"""新規アプリの雛形を apps/<app_id>/ に生成する。`init-app` skill から呼ばれる。

使い方:
    python3 harness/scripts/new_app_scaffold.py <app_id> <app_name> [autonomy_mode] [--brief PATH]

autonomy_mode は MANUAL / SUPERVISED / AUTONOMOUS のいずれか。省略時は SUPERVISED。

--brief を渡すと、企画ブリーフ（`new_brief.py` で作る記入用フォーマット）を
`apps/<app_id>/00-requirements/brief.yaml` に取り込む。要件定義の入力が何だったかを、
後から要件と突き合わせられるように生成物の中に残すため。
"""
from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402
import render_progress  # noqa: E402

APP_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
AUTONOMY_MODES = ("MANUAL", "SUPERVISED", "AUTONOMOUS")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="新規アプリの雛形を生成する")
    parser.add_argument("app_id", help="アプリ ID（kebab-case）")
    parser.add_argument("app_name", help="人間向けのアプリ名")
    parser.add_argument(
        "autonomy_mode", nargs="?", default="SUPERVISED", help="MANUAL / SUPERVISED / AUTONOMOUS"
    )
    parser.add_argument("--brief", help="企画ブリーフの YAML（00-requirements/brief.yaml に取り込む）")
    args = parser.parse_args(argv[1:])

    app_id, app_name, autonomy_mode = args.app_id, args.app_name, args.autonomy_mode
    if not APP_ID_RE.match(app_id):
        print(f"エラー: app_id は kebab-case にしてください（例: hello-world-todo）: {app_id!r}", file=sys.stderr)
        return 2
    if autonomy_mode not in AUTONOMY_MODES:
        print(f"エラー: autonomy_mode は {AUTONOMY_MODES} のいずれかにしてください: {autonomy_mode!r}", file=sys.stderr)
        return 2

    root = _common.repo_root()
    harness_dir = _common.harness_root(root)
    app_dir = root / "apps" / app_id

    if app_dir.exists():
        print(f"エラー: {app_dir} は既に存在します", file=sys.stderr)
        return 2

    brief_src = pathlib.Path(args.brief) if args.brief else None
    if brief_src is not None and not brief_src.is_file():
        print(f"エラー: ブリーフが見つかりません: {brief_src}", file=sys.stderr)
        return 2

    tmpl_dir = harness_dir / "templates"
    values = {
        "APP_ID": app_id,
        "APP_NAME": app_name,
        "VERSION": "1",
        "STATUS": "DRAFT",
        "DESIGN_VERSION": "1",
        "REQUIREMENTS_VERSION": "1",
        "AUTONOMY_MODE": autonomy_mode,
        "TIMESTAMP": _common.now_iso(),
        "ACTOR": "init-app",
    }

    def write_from_template(tmpl_name: str, dest: pathlib.Path) -> None:
        text = (tmpl_dir / tmpl_name).read_text(encoding="utf-8")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_common.render_template(text, values), encoding="utf-8")

    write_from_template("autonomy.yaml.tmpl", app_dir / "AUTONOMY.yaml")
    write_from_template("requirements.md.tmpl", app_dir / "00-requirements" / "requirements.md")
    write_from_template(
        "requirements.machine.yaml.tmpl", app_dir / "00-requirements" / "requirements.machine.yaml"
    )
    write_from_template("shared-kernel.yaml.tmpl", app_dir / "01-foundation" / "shared-kernel.yaml")
    write_from_template("design.md.tmpl", app_dir / "02-design" / "design.md")
    write_from_template(
        "architecture.machine.yaml.tmpl", app_dir / "02-design" / "architecture.machine.yaml"
    )
    write_from_template("integration.md.tmpl", app_dir / "04-integration" / "integration.md")
    write_from_template(
        "integration.machine.yaml.tmpl", app_dir / "04-integration" / "integration.machine.yaml"
    )

    (app_dir / "00-requirements" / "history").mkdir(parents=True, exist_ok=True)
    (app_dir / "00-requirements" / "history" / ".gitkeep").touch()
    (app_dir / "02-design" / "features").mkdir(parents=True, exist_ok=True)
    (app_dir / "02-design" / "features" / ".gitkeep").touch()
    (app_dir / "02-design" / "history").mkdir(parents=True, exist_ok=True)
    (app_dir / "02-design" / "history" / ".gitkeep").touch()
    (app_dir / "03-features").mkdir(parents=True, exist_ok=True)
    (app_dir / "03-features" / ".gitkeep").touch()
    (app_dir / "04-integration" / "assembly").mkdir(parents=True, exist_ok=True)
    (app_dir / "04-integration" / "assembly" / ".gitkeep").touch()
    (app_dir / ".worktrees").mkdir(parents=True, exist_ok=True)
    (app_dir / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")

    if brief_src is not None:
        brief_dest = app_dir / "00-requirements" / "brief.yaml"
        shutil.copyfile(brief_src, brief_dest)

    render_progress.render_app(app_dir)

    print(f"作成しました: {app_dir}")
    print(f"autonomy_mode: {autonomy_mode}（{app_dir / 'AUTONOMY.yaml'} に記録済み）")
    if brief_src is not None:
        print(f"ブリーフを取り込みました: {brief_src} → {app_dir / '00-requirements' / 'brief.yaml'}")
    print("次のステップ: `requirements-analyst` subagent（または `init-app` skill の続き）で要件定義を進めてください。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
