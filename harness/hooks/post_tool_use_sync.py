#!/usr/bin/env python3
"""PostToolUse hook: harness/CONVENTIONS.md 7節の Rule 4 を実行する。
status.yaml が更新されたら render_progress.py を呼び、PROGRESS.md / STATE.machine.yaml を再生成する。
**非ブロッキング**: 何が起きても常に exit 0（書き込み自体は既に完了しているため、後からブロックできない）。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
import path_utils  # noqa: E402

STATUS_PATH_RE = re.compile(r"^apps/([^/]+)/03-features/[^/]+/status\.yaml$")


def main() -> int:
    payload = path_utils.read_hook_input()
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd") or os.getcwd()

    toplevel = path_utils.get_worktree_toplevel(cwd)
    if not toplevel:
        return 0

    for abs_path in path_utils.extract_structured_edit_paths(tool_name, tool_input):
        rel_path = path_utils.to_worktree_relative(abs_path, toplevel)
        m = STATUS_PATH_RE.match(rel_path)
        if not m:
            continue
        app_id = m.group(1)
        # worktree はリポジトリのメインルート配下の apps/<app_id>/ を編集対象と共有しているが、
        # render_progress.py はメインリポジトリの harness/scripts を使うため、まずメインルートを探す。
        main_root = path_utils.find_main_repo_root(toplevel)
        script = os.path.join(main_root, "harness", "scripts", "render_progress.py")
        if not os.path.exists(script):
            print(f"警告: {script} が見つかりません。進捗の自動再生成をスキップします", file=sys.stderr)
            continue
        result = subprocess.run(
            [sys.executable, script, "--app", app_id],
            cwd=main_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"警告: render_progress.py --app {app_id} が失敗しました:\n{result.stderr}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
