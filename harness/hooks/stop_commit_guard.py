#!/usr/bin/env python3
"""Stop/SubagentStop hook: harness/CONVENTIONS.md 7節 Rule 8 を強制する。

各フェーズの節目を表すファイル（`status.yaml` / `requirements.machine.yaml` /
`architecture.machine.yaml`）に未コミットの変更が残ったまま応答を終えようとした場合、
停止をブロックしてコミットを促す。各 subagent のプロンプトは「状態を進めるたびに
git commit する」と指示しているが、過去の実地テストでコミット漏れが実際に発生したため、
決定論的に強制する。

**依存ゼロ**（標準ライブラリのみ）。exit 0 = 停止を許可, exit 2 = 停止を拒否（stderr に理由）。
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
import path_utils  # noqa: E402

PHASE_MARKER_RE = re.compile(
    r"apps/[^/]+/(?:"
    r"00-requirements/requirements\.machine\.yaml"
    r"|02-design/architecture\.machine\.yaml"
    r"|03-features/[^/]+/status\.yaml"
    r")$"
)


def find_uncommitted_phase_markers(toplevel: str) -> list[str]:
    status = path_utils.get_status_porcelain(toplevel)
    if not status:
        return []
    markers = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        # porcelain v1: "XY PATH" または rename 時 "XY OLD -> NEW"
        path_part = line[3:]
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        path_part = path_part.strip().strip('"').replace("\\", "/")
        if PHASE_MARKER_RE.search(path_part):
            markers.append(path_part)
    return markers


def main() -> int:
    payload = path_utils.read_hook_input()
    if payload.get("stop_hook_active"):
        # 既にこの Hook でブロックした後の継続応答。無限ループを避けるため通す。
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    toplevel = path_utils.get_worktree_toplevel(cwd)
    if not toplevel:
        return 0

    markers = find_uncommitted_phase_markers(toplevel)
    if not markers:
        return 0

    lines = [
        "拒否: フェーズの節目を表すファイルに未コミットの変更が残っています。"
        "応答を終える前に `git add -A && git commit` で記録してください"
        "（CONVENTIONS.md 7節 Rule 8）:",
    ]
    for m in markers:
        lines.append(f"  - {m}")
    print("\n".join(lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
