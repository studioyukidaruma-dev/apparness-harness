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
    # 寛容版（read_hook_input）だと壊れた入力が `{}` に潰れ、`stop_hook_active` も
    # 作業ツリーの位置も分からないまま「未コミットなし」として通過する（F-R1）。
    payload = path_utils.read_hook_input_strict()
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


def _fail_closed_main() -> int:
    """入力を解釈できないとき、通過ではなく拒否（exit 2）で止める（fail-closed）。

    `pre_tool_use_guard.py` の `_fail_closed_main()` と同じ規範。Stop hook が exit != 2 で
    終わると「未コミットなし」と同じ扱いになり、Rule 8 が黙って無効化される。

    ここで止める対象は**入力の破損だけ**に限り、判定に入ったあとの想定外の例外は拒否側へ倒さない。
    Stop hook は「拒否 → 応答継続 → 再び Stop」を繰り返す構造で、無限ループを止める唯一の手がかりが
    payload の `stop_hook_active` だからである。判定が例外で落ち続ける状態を拒否側に倒すと、
    その手がかり（正常に読めている）を使ってもループが止まらない。破損入力の場合は、そもそも
    ホスト側が payload を出せていない異常であり、応答を終わらせるより可視化を優先する。
    """
    try:
        return main()
    except path_utils.HookInputError as exc:
        print(
            "拒否: ハーネスの強制レイヤ（stop_commit_guard.py）が hook の入力を解釈できませんでした。\n"
            f"  {exc}\n"
            "入力を読めない状態では、フェーズ節目ファイルの未コミット（Rule 8）を判定できません。\n"
            "Stop/SubagentStop に渡される payload（JSON）が壊れています。"
            "Hook の起動方法（`.claude/settings.json` の command）を確認してください。",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(_fail_closed_main())
