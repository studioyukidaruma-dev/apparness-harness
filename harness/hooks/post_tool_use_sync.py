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

# 進捗ダッシュボードの内容を左右するファイル。
# `status.yaml` だけを見ていると、要件・設計が APPROVED になってもダッシュボードが
# DRAFT のまま腐る。CONVENTIONS.md 9節は「PROGRESS.md の表示で人間が随時状況を確認できること」を
# 自動化モードの**最終的な担保**と位置づけているため、承認という最重要の節目こそ反映が要る。
STATUS_PATH_RE = re.compile(
    r"^apps/([^/]+)/(?:"
    r"03-features/[^/]+/status\.yaml"
    r"|00-requirements/requirements\.machine\.yaml"
    r"|02-design/architecture\.machine\.yaml"
    r")$"
)


def main() -> int:
    payload = path_utils.read_hook_input()
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd") or os.getcwd()

    toplevel = path_utils.get_worktree_toplevel(cwd)
    if not toplevel:
        return 0

    # Rule 1・2・3・5・6 は Bash 経由の書き込みも対象にしているのに、Rule 4 だけ
    # 構造化ツールしか見ていなかった。`sed -i` 等で status.yaml を進めても
    # ダッシュボードが更新されない穴を塞ぐ（検知範囲は他の Rule と同じ静的抽出）。
    if tool_name == "Bash":
        edited_paths = path_utils.extract_bash_candidate_paths(tool_input.get("command", ""))
    else:
        edited_paths = path_utils.extract_structured_edit_paths(tool_name, tool_input)

    seen_apps: set[str] = set()
    for abs_path in edited_paths:
        rel_path, _scope_top = path_utils.resolve_worktree_scope(
            path_utils.to_worktree_relative(abs_path, toplevel), toplevel
        )
        m = STATUS_PATH_RE.match(rel_path)
        if not m:
            continue
        app_id = m.group(1)
        if app_id in seen_apps:
            continue  # 同じアプリを何度も再生成しない
        seen_apps.add(app_id)
        # worktree はリポジトリのメインルート配下の apps/<app_id>/ を編集対象と共有しているが、
        # render_progress.py はメインリポジトリの harness/scripts を使うため、まずメインルートを探す。
        main_root = path_utils.find_main_repo_root(toplevel)
        script = os.path.join(main_root, "harness", "scripts", "render_progress.py")
        if not os.path.exists(script):
            print(f"警告: {script} が見つかりません。進捗の自動再生成をスキップします", file=sys.stderr)
            continue
        # メイン側だけを再生成していたため、worktree の担当者が自分の作業ツリーで進捗を見ても
        # scaffold 直後のまま（`features: []`）だった（ドッグフーディング F-038）。
        # `render_progress.py` は cwd の git ルートを基準にするので、worktree でも同じ
        # スクリプト（メイン側の最新版）を cwd を変えて実行する。
        roots = [main_root]
        if os.path.realpath(toplevel) != os.path.realpath(main_root):
            roots.append(toplevel)
        for root in roots:
            if not os.path.isdir(os.path.join(root, "apps", app_id)):
                continue
            result = subprocess.run(
                [sys.executable, script, "--app", app_id],
                cwd=root,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print(
                    f"警告: render_progress.py --app {app_id} が失敗しました（{root}）:\n{result.stderr}",
                    file=sys.stderr,
                )

    return 0


if __name__ == "__main__":
    sys.exit(main())
