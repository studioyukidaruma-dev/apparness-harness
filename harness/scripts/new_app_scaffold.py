#!/usr/bin/env python3
"""新規アプリの雛形を apps/<app_id>/ に生成する。`init-app` skill から呼ばれる。

使い方:
    python3 harness/scripts/new_app_scaffold.py <app_id> <app_name> [autonomy_mode]

autonomy_mode は MANUAL / SUPERVISED / AUTONOMOUS のいずれか。省略時は SUPERVISED。
"""
from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402
import render_progress  # noqa: E402

APP_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
AUTONOMY_MODES = ("MANUAL", "SUPERVISED", "AUTONOMOUS")


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print(f"使い方: {argv[0]} <app_id> <app_name> [autonomy_mode]", file=sys.stderr)
        return 2

    app_id, app_name = argv[1], argv[2]
    autonomy_mode = argv[3] if len(argv) == 4 else "SUPERVISED"
    if not APP_ID_RE.match(app_id):
        print(f"エラー: app_id は kebab-case にしてください（例: hello-world-todo）: {app_id!r}", file=sys.stderr)
        return 2
    if autonomy_mode not in AUTONOMY_MODES:
        print(f"エラー: autonomy_mode は {AUTONOMY_MODES} のいずれかにしてください: {autonomy_mode!r}", file=sys.stderr)
        return 2

    root = _common.repo_root()
    harness_dir = root / "harness"
    app_dir = root / "apps" / app_id

    if app_dir.exists():
        print(f"エラー: {app_dir} は既に存在します", file=sys.stderr)
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

    render_progress.render_app(app_dir)

    print(f"作成しました: {app_dir}")
    print(f"autonomy_mode: {autonomy_mode}（{app_dir / 'AUTONOMY.yaml'} に記録済み）")
    print("次のステップ: `requirements-analyst` subagent（または `init-app` skill の続き）で要件定義を進めてください。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
