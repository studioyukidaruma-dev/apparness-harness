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
import render_progress  # noqa: E402

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# worktree に必ず入っていなければならない上位文書（CONVENTIONS.md 11節）。
# ここに挙げたものが分岐元のコミットに含まれていなければ、feature-builder は
# 要件・設計・検証コマンドの宣言を読めないまま実装することになる。
REQUIRED_IN_TREE = (
    "00-requirements/requirements.machine.yaml",
    "01-foundation/shared-kernel.yaml",
    "02-design/architecture.machine.yaml",
)


def tracked_in_head(root: pathlib.Path, rel_path: str) -> bool:
    """`rel_path` が現在の HEAD のツリーに含まれているかを git に問い合わせる。"""
    result = subprocess.run(
        ["git", "ls-tree", "--name-only", "HEAD", "--", rel_path],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


_APPROVAL_EMPTY = {"", "null", "~", "none"}


def _is_empty_approval(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip().strip("\"'").lower() in _APPROVAL_EMPTY)


def inherit_contract_approval(contract_text: str, approved_by, approved_at) -> str:
    """契約ドラフトの承認欄が空なら、設計（architecture）の承認記録を引き継ぐ。

    契約ドラフトは `architecture.machine.yaml` と同じ設計フェーズの成果物で、設計が APPROVED に
    なった時点で凍結される（Rule 3）。にもかかわらず契約側には承認者の記録が無く、
    `status.yaml` が `CONTRACT_APPROVED` になっても凍結の根拠を機械的に確かめられなかった
    （ドッグフーディング F-039）。承認の出所は設計承認そのものなので、そこから継承する。

    行単位の置換で行う（YAML を読み書きし直すとコメントが失われるため）。
    """
    if _is_empty_approval(approved_by) and _is_empty_approval(approved_at):
        return contract_text
    lines = contract_text.splitlines(keepends=True)
    for key, value in (("approved_by", approved_by), ("approved_at", approved_at)):
        if _is_empty_approval(value):
            continue
        rendered = f'{key}: "{value}"\n'
        for i, line in enumerate(lines):
            m = re.match(rf"^{key}\s*:\s*(.*?)\s*$", line)
            if m is None:
                continue
            if _is_empty_approval(m.group(1)):
                lines[i] = rendered
            break
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] = lines[-1] + "\n"
            lines.append(rendered)
    return "".join(lines)


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
        # 分岐元は `main` 固定ではなく現在の HEAD。アプリ作成は `app/<app-id>/bootstrap`
        # ブランチで行う（CONVENTIONS.md 3節）ため、`main` から切ると要件・設計・
        # shared-kernel が一切入っていない worktree ができ、feature-builder は上位文書を
        # 読めず、run_verification.py も `verification:` 宣言を解決できないため
        # **どの機能も TESTED にできない**（ドッグフーディングで実証。F-014）。
        missing = [
            rel for rel in REQUIRED_IN_TREE if not tracked_in_head(root, f"apps/{app_id}/{rel}")
        ]
        if missing:
            print(
                "エラー: 現在の HEAD に上位文書が含まれていないため worktree を作成できません。\n"
                "  未コミット、または別のブランチにあります:\n"
                + "".join(f"    - apps/{app_id}/{rel}\n" for rel in missing)
                + "  先に `git add -A && git commit` するか、成果物のあるブランチに切り替えてください。",
                file=sys.stderr,
            )
            return 2
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", branch, "HEAD"],
            cwd=root,
            check=True,
        )

    feature_dir = worktree_path / "apps" / app_id / "03-features" / feature_id
    tmpl_dir = _common.harness_root(root) / "templates"
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
            contract_text = inherit_contract_approval(
                design_contract.read_text(encoding="utf-8"),
                architecture.get("approved_by"),
                architecture.get("approved_at"),
            )
            contract_dest.write_text(contract_text, encoding="utf-8")
        else:
            write_from_template("feature-contract.yaml.tmpl", contract_dest)

    status_dest = feature_dir / "status.yaml"
    if not status_dest.exists():
        write_from_template("status.yaml.tmpl", status_dest)
        status = _common.load_yaml(status_dest)
        status["state"] = "CONTRACT_APPROVED"
        status["branch"] = branch
        status["worktree_path"] = str(worktree_path.relative_to(root))
        # 誰がいつ埋めるのか決まっておらず、実装者が自己判断で埋めていた（F-040）。
        # 契約を引き継いだこの時点が唯一の確実な機会なので、ここで固定する。
        try:
            contract_version = (_common.load_yaml(contract_dest) or {}).get("version")
        except Exception:  # noqa: BLE001
            contract_version = None
        if isinstance(contract_version, int):
            status["contract_version"] = contract_version
        # 状態機械（CONVENTIONS.md 5節）は 1 段階ずつの前進しか認めない。
        # `CONTRACT_DRAFTED` を飛ばして履歴を書くと、`validate_status_transition.py` が
        # 拒否する遷移をハーネス自身が記録することになり、BLOCKED からの復帰判定
        # （履歴を遡って直前の状態を復元する）の前提も崩れる。
        for state, note in (
            ("CONTRACT_DRAFTED", "contract draft carried over from 02-design"),
            ("CONTRACT_APPROVED", "worktree scaffold created"),
        ):
            status["state_history"].append(
                {
                    "state": state,
                    "at": values["TIMESTAMP"],
                    "by": values["ACTOR"],
                    "note": note,
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

    # Rule 4（進捗自動再生成）は Edit/Write でしか発火しないため、スクリプトからの
    # status.yaml 生成では PROGRESS.md が更新されない。new_app_scaffold.py と同じく明示的に呼ぶ。
    render_progress.render_app(app_dir)

    launch_dir = feature_dir.relative_to(root)
    print(f"作成しました: {worktree_path} (branch: {branch})")
    print("担当者はこのディレクトリでセッションを開始してください:")
    print(f"  cd {launch_dir} && claude")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
