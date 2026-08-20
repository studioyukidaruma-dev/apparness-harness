#!/usr/bin/env python3
"""PreToolUse hook: harness/CONVENTIONS.md 7節の Rule 1〜3, 5〜7, 9 を強制する（Rule 4/8 は別 hook）。
**依存ゼロ**（標準ライブラリのみ）。Edit/Write/MultiEdit/NotebookEdit は確実にブロックする。
Bash 経由の間接書き込み（`sed -i`/`cp`/`mv`/`tee`/リダイレクト等、`path_utils.extract_bash_candidate_paths`
で検知できる範囲）も同様にブロックする。検知は shlex によるクォート考慮トークン化に基づくため、
クォート内の文字列（例: `echo "a >> b"` の `>>`）を演算子と誤認識することはない。トークン化前に
クォート・行継続・ヒアドキュメント本体を考慮して改行をコマンド区切りへ正規化するため、複数行の
Bash コマンド（Claude Code が渡す典型的な形）でも `cp`/`mv`/`tee`/`sed -i` が先頭行以外にある場合を
検知できる（`path_utils._normalize_bash_newlines`）。ただし変数展開されたパス等の検知漏れ
（false negative）は起こりうる。これは「完全な防御ではなく、意図しない/不注意な間接書き込みを
止める」という目的上許容する。**バイパス用の環境変数は意図的に用意しない**
（AIがブロックされた際に自ら解除して実行できてしまい、決定論的強制が意味を失うため）。

exit 0 = 許可, exit 2 = 拒否（stderr に理由）。
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
import path_utils  # noqa: E402

HARNESS_PATH_RE = re.compile(r"^(harness/|\.claude/|\.github/)")
# 個人のローカル設定（gitignore 対象、チームに共有されない）はハーネス非侵襲性の対象外。
# 例: `/plugin install <name> --scope local` は .claude/settings.local.json に書き込む。
HARNESS_PATH_EXEMPT_RE = re.compile(r"^\.claude/settings\.local\.json$")
FEATURE_SCOPE_RE = re.compile(r"^apps/([^/]+)/03-features/([^/]+)/(.*)$")
FEATURE_CONTRACT_RE = re.compile(r"^apps/([^/]+)/03-features/([^/]+)/contract\.yaml$")
DESIGN_CONTRACT_RE = re.compile(r"^apps/([^/]+)/02-design/features/([^/]+)\.contract\.yaml$")
FEATURE_SRC_RE = re.compile(r"^apps/([^/]+)/03-features/([^/]+)/src/")
APP_UPSTREAM_DOC_RE = re.compile(r"^apps/([^/]+)/(00-requirements|01-foundation|02-design)/")
ARCHITECTURE_RE = re.compile(r"^apps/([^/]+)/02-design/architecture\.machine\.yaml$")
STATUS_YAML_RE = re.compile(r"^apps/([^/]+)/03-features/([^/]+)/status\.yaml$")


def check_rule1_harness_immutability(rel_path: str, cwd: str) -> str | None:
    if not HARNESS_PATH_RE.match(rel_path):
        return None
    if HARNESS_PATH_EXEMPT_RE.match(rel_path):
        return None
    if os.environ.get("HARNESS_UNLOCK") == "1":
        print(f"警告: HARNESS_UNLOCK=1 により {rel_path} への書き込みガードを解除しています", file=sys.stderr)
        return None
    branch = path_utils.get_current_branch(cwd) or ""
    if branch.startswith("harness/"):
        return None
    return (
        f"拒否: {rel_path} はハーネス本体です。アプリ作成中は書き込みが保護されています。\n"
        f"意図的な変更なら `harness/<topic>` ブランチで作業するか、"
        f"一時的に環境変数 HARNESS_UNLOCK=1 を設定してください。"
    )


def check_rule2_feature_scope(rel_path: str, cwd: str) -> str | None:
    m = FEATURE_SCOPE_RE.match(rel_path)
    if not m:
        return None
    _app_id, feature_id, rest = m.groups()
    if rest == "status.yaml":
        return None  # 状態遷移は担当者・integrator 双方が正当に更新するため対象外
    toplevel = path_utils.get_worktree_toplevel(cwd)
    if not toplevel:
        return None  # git 情報が取れない場合は判定不能としてブロックしない
    current_scope = os.path.basename(toplevel)
    if current_scope == feature_id:
        return None
    return (
        f"拒否: {rel_path} はこのセッションの担当範囲外です（このセッションは {current_scope!r} 用）。\n"
        f"{feature_id!r} を編集するには、対応する worktree "
        f"(`apps/<app>/.worktrees/{feature_id}/...`) でセッションを開始してください。"
    )


def check_rule6_foundation_scope(rel_path: str, toplevel: str) -> str | None:
    m = APP_UPSTREAM_DOC_RE.match(rel_path)
    if not m:
        return None
    if "/.worktrees/" not in toplevel.replace(os.sep, "/") + "/":
        return None  # feature 用 worktree 以外（メインリポジトリ）からの書き込みは対象外
    return (
        f"拒否: {rel_path} は feature-builder の担当範囲外です（要件・共有基盤・設計文書は編集できません）。\n"
        f"実装中に設計変更が必要だと気づいた場合は、実装を止めてユーザーに報告し、"
        f"`diff-design` skill での再設計に回してください。"
    )


def check_rule5_required_skills(rel_path: str, toplevel: str) -> str | None:
    m = FEATURE_SRC_RE.match(rel_path)
    if not m:
        return None
    app_id, _feature_id = m.groups()
    shared_kernel_path = os.path.join(toplevel, f"apps/{app_id}/01-foundation/shared-kernel.yaml")
    try:
        with open(shared_kernel_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None  # shared-kernel.yaml が無ければ判定不能、ブロックしない
    skills = path_utils.extract_required_skills(content)
    if not skills:
        return None
    enabled = path_utils.get_enabled_plugins(toplevel)
    missing = [s for s in skills if s.get("plugin_ref") and s["plugin_ref"] not in enabled]
    if not missing:
        return None
    lines = [
        "拒否: この機能の実装には、設計で必須と定められた Skill が不足しています。"
        "実装を始める前にインストールしてください:"
    ]
    for s in missing:
        lines.append(f"  - {s.get('name')}: `/plugin install {s['plugin_ref']} --scope local`")
    lines.append(
        "インストール後、セッションを再開してから実装を再開してください"
        "（設計で決めた Skill を使わずに実装を進めることはできません）。"
    )
    return "\n".join(lines)


def check_rule7_requirements_consistency(rel_path: str, tool_name: str, tool_input: dict, toplevel: str) -> str | None:
    m = ARCHITECTURE_RE.match(rel_path)
    if not m:
        return None
    app_id = m.group(1)
    arch_path = os.path.join(toplevel, rel_path)
    try:
        with open(arch_path, "r", encoding="utf-8") as f:
            current_content = f.read()
    except OSError:
        current_content = ""
    new_content = path_utils.simulate_write_result(tool_name, tool_input, current_content)
    new_status = path_utils.extract_scalar_field(new_content, "status")
    if new_status != "APPROVED":
        return None
    based_on = path_utils.extract_scalar_field(new_content, "based_on_requirements_version")
    requirements_path = os.path.join(toplevel, f"apps/{app_id}/00-requirements/requirements.machine.yaml")
    req_version = None
    try:
        with open(requirements_path, "r", encoding="utf-8") as f:
            req_version = path_utils.extract_scalar_field(f.read(), "version")
    except OSError:
        pass
    if req_version is None or based_on is None:
        return None  # 判定不能ならブロックしない
    if based_on != req_version:
        return (
            f"拒否: architecture.machine.yaml を status: APPROVED にしようとしていますが、\n"
            f"based_on_requirements_version ({based_on}) が requirements.machine.yaml の"
            f"現在の version ({req_version}) と一致しません。要件が変更されている可能性があります。\n"
            f"based_on_requirements_version を最新の version に更新するか、要件との食い違いを"
            f"解消してから再度 APPROVED にしてください。"
        )
    return None


def check_rule9_status_transition(rel_path: str, tool_name: str, tool_input: dict, toplevel: str) -> str | None:
    m = STATUS_YAML_RE.match(rel_path)
    if not m:
        return None
    status_path = os.path.join(toplevel, rel_path)
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            current_content = f.read()
    except OSError:
        return None  # 新規作成（旧状態なし）は判定不能として許可する
    old_state = path_utils.extract_scalar_field(current_content, "state")
    new_content = path_utils.simulate_write_result(tool_name, tool_input, current_content)
    new_state = path_utils.extract_scalar_field(new_content, "state")
    if new_state is None:
        return None
    return path_utils.validate_status_transition(old_state, new_state)


def check_rule3_contract_freeze(rel_path: str, toplevel: str) -> str | None:
    m = FEATURE_CONTRACT_RE.match(rel_path)
    if m:
        status_path = os.path.join(toplevel, os.path.dirname(rel_path), "status.yaml")
        state = path_utils.read_state_field(status_path)
        if state is None or state in ("NOT_STARTED", "CONTRACT_DRAFTED"):
            return None
        return (
            f"拒否: {rel_path} は state={state} のため凍結されています（CONTRACT_DRAFTED までのみ変更可）。\n"
            f"仕様変更が必要な場合は `diff-design` skill で新しい機能バージョンとして起票してください。"
        )

    m = DESIGN_CONTRACT_RE.match(rel_path)
    if m:
        app_id, _feature_id = m.groups()
        architecture_path = os.path.join(toplevel, f"apps/{app_id}/02-design/architecture.machine.yaml")
        status = path_utils.read_state_field(architecture_path)
        if status is None or status == "DRAFT":
            return None
        return (
            f"拒否: {rel_path} は architecture.machine.yaml が status={status} のため凍結されています"
            f"（DRAFT の間のみ変更可）。"
        )
    return None


def run_checks(
    rel_path: str, cwd: str, toplevel: str, tool_name: str = "", tool_input: dict | None = None
) -> str | None:
    tool_input = tool_input or {}
    for check in (check_rule1_harness_immutability, check_rule2_feature_scope):
        reason = check(rel_path, cwd)
        if reason:
            return reason
    for check in (check_rule6_foundation_scope, check_rule5_required_skills):
        reason = check(rel_path, toplevel)
        if reason:
            return reason
    reason = check_rule3_contract_freeze(rel_path, toplevel)
    if reason:
        return reason
    if tool_name in ("Edit", "Write", "MultiEdit"):
        reason = check_rule7_requirements_consistency(rel_path, tool_name, tool_input, toplevel)
        if reason:
            return reason
        reason = check_rule9_status_transition(rel_path, tool_name, tool_input, toplevel)
        if reason:
            return reason
    return None


def main() -> int:
    payload = path_utils.read_hook_input()
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd") or os.getcwd()

    toplevel = path_utils.get_worktree_toplevel(cwd) or cwd

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        candidates = path_utils.extract_bash_candidate_paths(command)
        violations = []
        for candidate in candidates:
            rel_path = path_utils.to_worktree_relative(candidate, toplevel)
            reason = run_checks(rel_path, cwd, toplevel)
            if reason:
                violations.append(reason)
        if violations:
            print(
                "拒否: Bash コマンドがガード対象パスへの間接的な書き込みを含んでいます"
                "（sed -i / cp / mv / tee / リダイレクト等をコマンド文字列から検知）。"
                "Edit/Write/MultiEdit などの構造化ツールを使ってください:",
                file=sys.stderr,
            )
            for v in violations:
                print(f"  - {v}", file=sys.stderr)
            return 2
        return 0

    for abs_path in path_utils.extract_structured_edit_paths(tool_name, tool_input):
        rel_path = path_utils.to_worktree_relative(abs_path, toplevel)
        reason = run_checks(rel_path, cwd, toplevel, tool_name, tool_input)
        if reason:
            print(reason, file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
