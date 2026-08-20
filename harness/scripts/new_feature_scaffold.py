#!/usr/bin/env python3
"""機能用の git worktree を作成し、03-features/<feature_id>/ の雛形を生成する。
`new-feature-worktree` skill から呼ばれる。

前提: apps/<app_id>/02-design/architecture.machine.yaml が status: APPROVED で、
      features[] に対象 feature_id が存在すること。

使い方:
    python3 harness/scripts/new_feature_scaffold.py <app_id> <feature_id>
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"使い方: {argv[0]} <app_id> <feature_id>", file=sys.stderr)
        return 2

    app_id, feature_id = argv[1], argv[2]
    if not ID_RE.match(feature_id):
        print(f"エラー: feature_id は kebab-case にしてください: {feature_id!r}", file=sys.stderr)
        return 2

    root = _common.repo_root()
    app_dir = root / "apps" / app_id
    if not app_dir.exists():
        print(f"エラー: {app_dir} が存在しません。先に init-app を実行してください", file=sys.stderr)
        return 2

    architecture_path = app_dir / "02-design" / "architecture.machine.yaml"
    if not architecture_path.exists():
        print(f"エラー: {architecture_path} が存在しません", file=sys.stderr)
        return 2
    architecture = _common.load_yaml(architecture_path)
    if architecture.get("status") != "APPROVED":
        print(
            f"エラー: architecture.machine.yaml は status: APPROVED である必要があります"
            f"（現在: {architecture.get('status')}）",
            file=sys.stderr,
        )
        return 2
    feature_entries = [f for f in architecture.get("features", []) if f.get("id") == feature_id]
    if not feature_entries:
        print(f"エラー: architecture.machine.yaml の features[] に {feature_id!r} が見つかりません", file=sys.stderr)
        return 2
    feature_entry = feature_entries[0]

    worktree_path = app_dir / ".worktrees" / feature_id
    branch = f"feature/{app_id}/{feature_id}"

    if worktree_path.exists():
        print(f"既に存在します（冪等スキップ）: {worktree_path}")
    else:
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", branch, "main"],
            cwd=root,
            check=True,
        )

    feature_dir = worktree_path / "apps" / app_id / "03-features" / feature_id
    tmpl_dir = root / "harness" / "templates"
    values = {
        "APP_ID": app_id,
        "FEATURE_ID": feature_id,
        "FEATURE_NAME": feature_entry.get("name", feature_id),
        "TIMESTAMP": _common.now_iso(),
        "ACTOR": "new-feature-worktree",
    }

    def write_from_template(tmpl_name: str, dest: pathlib.Path) -> None:
        if dest.exists():
            return
        text = (tmpl_dir / tmpl_name).read_text(encoding="utf-8")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_common.render_template(text, values), encoding="utf-8")

    write_from_template("feature-spec.md.tmpl", feature_dir / "SPEC.md")

    # 設計時点のドラフト契約があればそれを引き継ぐ。なければテンプレートから新規作成。
    design_contract = app_dir / "02-design" / "features" / f"{feature_id}.contract.yaml"
    contract_dest = feature_dir / "contract.yaml"
    if not contract_dest.exists():
        feature_dir.mkdir(parents=True, exist_ok=True)
        if design_contract.exists():
            contract_dest.write_text(design_contract.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            write_from_template("feature-contract.yaml.tmpl", contract_dest)

    status_dest = feature_dir / "status.yaml"
    if not status_dest.exists():
        write_from_template("status.yaml.tmpl", status_dest)
        status = _common.load_yaml(status_dest)
        status["state"] = "CONTRACT_APPROVED"
        status["branch"] = branch
        status["worktree_path"] = str(worktree_path.relative_to(root))
        status["state_history"].append(
            {
                "state": "CONTRACT_APPROVED",
                "at": values["TIMESTAMP"],
                "by": values["ACTOR"],
                "note": "worktree scaffold created",
            }
        )
        _common.dump_yaml(status, status_dest)

    (feature_dir / "src").mkdir(parents=True, exist_ok=True)
    (feature_dir / "src" / ".gitkeep").touch()
    (feature_dir / "tests").mkdir(parents=True, exist_ok=True)
    (feature_dir / "tests" / ".gitkeep").touch()
    (feature_dir / ".claude").mkdir(parents=True, exist_ok=True)
    (feature_dir / ".claude" / ".gitkeep").touch()

    subprocess.run(["git", "add", "-A"], cwd=worktree_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"scaffold: {feature_id} の機能雛形を作成"],
        cwd=worktree_path,
        check=True,
    )

    launch_dir = feature_dir.relative_to(root)
    print(f"作成しました: {worktree_path} (branch: {branch})")
    print("担当者はこのディレクトリでセッションを開始してください:")
    print(f"  cd {launch_dir} && claude")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
