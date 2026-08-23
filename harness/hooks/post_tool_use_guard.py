#!/usr/bin/env python3
"""PostToolUse hook: Bash 実行の**結果**を検証し、ガード対象パスへの書き込みを巻き戻す。

`pre_tool_use_guard.py` の Bash 検知は、シェルを実行せずコマンド文字列を静的に解析している。
そのため変数展開されたパス（例: `>> "$VAR"`）・`xargs`・`find -exec`・スクリプト経由の書き込みは
**原理的に検知できない**（`CONVENTIONS.md` 7節末尾）。

発想を変えれば構造的に解決する。**Bash の実行後に `git status` を取れば、実際に何が変更されたかが
パースの精度に依存せず確実に分かる。** この Hook は次を行う:

  1. `pre_tool_use_guard.py` が Bash 実行の直前に保存したスナップショット（`git status --porcelain
     --untracked-files=all`）を読む
  2. 実行後の `git status` と比較し、**この Bash コマンドによって新たに変わったパス**を求める
  3. それらを Rule 1・2・3・5・6 で判定し、違反があれば巻き戻して報告する

スナップショットとの差分だけを見るのが要点である。実行前から dirty だったパス（人間が
Claude Code の外で編集していた等）を巻き戻してしまうと、ユーザーの作業を破壊しかねない。

静的検知（未然防止）と事後検証（確実な検知）の**二段構え**とし、前者は削除しない。
未然に止めるほうが AI にとって学習可能なフィードバックになるためである。

**非ブロッキングにはしない**: exit 2 で Claude にフィードバックを返す（書き込み自体は既に
起きているため「阻止」はできないが、巻き戻したことと理由を伝える必要がある）。
**依存ゼロ**（標準ライブラリのみ）。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
import path_utils  # noqa: E402
import pre_tool_use_guard  # noqa: E402


def main() -> int:
    payload = path_utils.read_hook_input()
    if payload.get("tool_name") != "Bash":
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    toplevel = path_utils.get_worktree_toplevel(cwd)
    if not toplevel:
        return 0

    snapshot_file = pre_tool_use_guard.snapshot_file_path(cwd, payload.get("session_id"))
    if not snapshot_file or not os.path.exists(snapshot_file):
        return 0  # 比較対象が無ければ何もしない（既存の変更を誤って巻き戻さないため）
    try:
        with open(snapshot_file, "r", encoding="utf-8") as f:
            before = json.load(f)
    except (OSError, ValueError):
        return 0
    finally:
        try:
            os.remove(snapshot_file)
        except OSError:
            pass
    if not isinstance(before, dict):
        return 0

    after = path_utils.capture_worktree_state(toplevel)
    if after is None:
        return 0
    changed = path_utils.diff_worktree_state(before, after)
    if not changed:
        return 0

    violations: list[tuple[str, str]] = []
    for rel_path in changed:
        # 判定は worktree を基準に読み替えたパスで行い、巻き戻しは元のパスで行う
        scope_rel, scope_top = path_utils.resolve_worktree_scope(rel_path, toplevel)
        reason = pre_tool_use_guard.run_checks(scope_rel, cwd, scope_top)
        if reason:
            violations.append((rel_path, reason))
    if not violations:
        return 0

    lines = [
        "拒否（事後検証）: 直前の Bash コマンドが、ガード対象のパスを実際に変更しました。",
        "静的解析では検知できない形（変数展開・スクリプト経由等）の書き込みを、"
        "実行後の `git status` との比較で検出しています。**変更は巻き戻しました。**",
    ]
    for rel_path, reason in violations:
        # HEAD ではなく Bash 実行直前の内容へ戻す（実行前からの未コミット変更を巻き添えにしない）
        reverted = path_utils.restore_from_snapshot(rel_path, toplevel, before.get(rel_path))
        state = "巻き戻し済み" if reverted else "**巻き戻しに失敗（手動で戻してください）**"
        lines.append(f"  - {rel_path}（{state}）: {reason.splitlines()[0]}")
    lines.append("担当範囲内のパスに対して、Edit/Write などの構造化ツールで作業し直してください。")
    print("\n".join(lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
