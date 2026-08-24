#!/usr/bin/env python3
"""PreToolUse hook: harness/CONVENTIONS.md 7節の Rule 1〜3, 5〜7, 9, 10〜12 を強制する（Rule 4/8 は別 hook）。
Rule 3・7・9・10・11 は書き込み前後の内容比較に依存するため、書き込み後の内容を再現できない手段
（Bash・NotebookEdit 等）による該当ファイルへの書き込みは `check_requires_simulatable_tool` が一律拒否する。
**依存ゼロ**（標準ライブラリのみ）。Edit/Write/MultiEdit/NotebookEdit は確実にブロックする。
Bash 経由の間接書き込み（`sed -i`/`cp`/`mv`/`tee`/リダイレクト等、`path_utils.extract_bash_candidate_paths`
で検知できる範囲）も同様にブロックする。検知は shlex によるクォート考慮トークン化に基づくため、
クォート内の文字列（例: `echo "a >> b"` の `>>`）を演算子と誤認識することはない。トークン化前に
クォート・行継続・ヒアドキュメント本体を考慮して改行をコマンド区切りへ正規化するため、複数行の
Bash コマンド（Claude Code が渡す典型的な形）でも `cp`/`mv`/`tee`/`sed -i` が先頭行以外にある場合を
検知できる（`path_utils._normalize_bash_newlines`）。ただし変数展開されたパス等の検知漏れ
（false negative）は起こりうる。これは「完全な防御ではなく、意図しない/不注意な間接書き込みを
止める」という目的上許容する。**この Bash 間接書き込み検知には、解除用の環境変数を意図的に
用意しない**（AIがブロックされた際に自ら解除して実行できてしまい、決定論的強制が意味を失うため）。

解除路があるのは Rule 1 だけである（`HARNESS_UNLOCK=1`。ハーネス本体を `harness/` ブランチ以外
から直す必要がある場合の緊急避難路で、使うと警告を stderr に出す。`CONVENTIONS.md` 8節・
`CLAIMS.md` の Rule 1 行にも明記してある）。Rule 2〜12 には解除路が無く、とりわけ Rule 12
（危険操作フロア）に環境変数を足さないことは INV-4 であり、
`test_dangerous_ops.py::test_rule12_has_no_bypass_environment_variable` が固定している。

exit 0 = 許可, exit 2 = 拒否（stderr に理由）。
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

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
REQUIREMENTS_RE = re.compile(r"^apps/([^/]+)/00-requirements/requirements\.machine\.yaml$")
STATUS_YAML_RE = re.compile(r"^apps/([^/]+)/03-features/([^/]+)/status\.yaml$")
INTEGRATION_RECORD_RE = re.compile(r"^apps/([^/]+)/04-integration/integration\.machine\.yaml$")


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
    feature_id, rest = m.group(2), m.group(3)
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


def check_rule6_foundation_scope(rel_path: str, cwd: str) -> str | None:
    """判定は**セッションがどこで動いているか**で行う（書き込み先のツリーではない）。

    書き込み先を基準にすると、feature 用 worktree のセッションが**メインリポジトリ側の**
    上位文書を書く場合に素通りする（そちらのルートには `.worktrees/` が現れないため。F-055）。
    """
    m = APP_UPSTREAM_DOC_RE.match(rel_path)
    if not m:
        return None
    session_top = path_utils.get_worktree_toplevel(cwd) or cwd
    if "/.worktrees/" not in session_top.replace(os.sep, "/") + "/":
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
    app_id, feature_id = m.groups()
    shared_kernel_path = os.path.join(toplevel, f"apps/{app_id}/01-foundation/shared-kernel.yaml")
    try:
        with open(shared_kernel_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None  # shared-kernel.yaml が無ければ判定不能、ブロックしない
    all_skills = path_utils.extract_required_skills(content)
    # applies_to が省略・空なら全機能に適用（従来どおり）。指定されていればこの feature_id を
    # 含むものだけを要求する（無関係な機能にまで不要な Skill の有効化を強制しないため）。
    skills = [s for s in all_skills if not s.get("applies_to") or feature_id in s["applies_to"]]
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


def check_rule7_requirements_consistency(rel_path: str, tool_name: str, tool_input: dict[str, Any], toplevel: str) -> str | None:
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


def check_rule7_approval_record(rel_path: str, tool_name: str, tool_input: dict[str, Any], toplevel: str) -> str | None:
    """Rule 7（承認ゲート）の要件側・同時性の強制（CONVENTIONS.md 9節）。

    `requirements.machine.yaml` / `architecture.machine.yaml` を `status: APPROVED` にする
    書き込みは、同じ書き込みで `approved_by` / `approved_at` が埋まっていなければ拒否する。
    要件側には従来ゲートが無く（F-011）、設計側も `status` だけを先に APPROVED にした
    中間状態が素通りしていた（F-020）。
    """
    m = REQUIREMENTS_RE.match(rel_path) or ARCHITECTURE_RE.match(rel_path)
    if not m:
        return None
    target = os.path.join(toplevel, rel_path)
    try:
        with open(target, "r", encoding="utf-8") as f:
            current_content = f.read()
    except OSError:
        current_content = ""
    new_content = path_utils.simulate_write_result(tool_name, tool_input, current_content)
    return path_utils.validate_approval_record(new_content, os.path.basename(rel_path))


def check_rule3_contract_approval_record(
    rel_path: str, tool_name: str, tool_input: dict[str, Any], toplevel: str
) -> str | None:
    """Rule 3（契約凍結）の前提を機械的に確かめる（CONVENTIONS.md 9節・F-039）。

    `status.yaml` を `CONTRACT_APPROVED` にする書き込みは、その機能の `contract.yaml` に
    `approved_by` / `approved_at` が記録されていなければ拒否する。
    `CONTRACT_APPROVED` 以降は契約が凍結されるため、凍結の根拠となる承認の記録を
    凍結の時点で要求する（要件・設計はスキーマで同じ条件を課しているが、feature 契約には
    その強制が無く、承認者不明のまま凍結されていた）。
    """
    m = STATUS_YAML_RE.match(rel_path)
    if not m:
        return None
    status_path = os.path.join(toplevel, rel_path)
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            current_content = f.read()
    except OSError:
        current_content = ""
    old_state = path_utils.extract_scalar_field(current_content, "state")
    new_content = path_utils.simulate_write_result(tool_name, tool_input, current_content)
    new_state = path_utils.extract_scalar_field(new_content, "state")
    if new_state != "CONTRACT_APPROVED" or old_state == "CONTRACT_APPROVED":
        return None
    contract_path = os.path.join(toplevel, os.path.dirname(rel_path), "contract.yaml")
    try:
        with open(contract_path, "r", encoding="utf-8") as f:
            contract_content = f.read()
    except OSError:
        return None  # 契約がまだ無ければ判定不能（別 Rule の領分）
    try:
        contract = path_utils.parse_simple_yaml(contract_content)
    except Exception:
        return None
    missing = path_utils.find_empty_approval_fields(contract)
    if not missing:
        return None
    return (
        f"拒否: status.yaml を state: CONTRACT_APPROVED にしようとしていますが、"
        f"contract.yaml の {' と '.join(missing)} が空のままです。\n"
        "CONTRACT_APPROVED 以降は契約が凍結される（Rule 3）ため、凍結の根拠となる承認者と"
        "承認日時を contract.yaml に記録してから状態を進めてください（CONVENTIONS.md 9節）。"
    )


def check_rule9_status_transition(rel_path: str, tool_name: str, tool_input: dict[str, Any], toplevel: str) -> str | None:
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
    # `BLOCKED` からの復帰は、書き込み**前**の履歴から直前の実質的な状態を復元して判定する
    history = path_utils.extract_state_history(current_content)
    return path_utils.validate_status_transition(old_state, new_state, history)


def check_rule10_verification_receipt(
    rel_path: str, tool_name: str, tool_input: dict[str, Any], toplevel: str
) -> str | None:
    """Rule 10: 検証受領書ゲート（CONVENTIONS.md 12節）。

    2 つを強制する:
      (a) `verification_receipt` を Edit/Write で書き換えることを拒否する
          （受領書は `run_verification.py` が実際にコマンドを実行して生成するものであり、
          手書きできてしまえば「実行した」という主張の裏付けにならない）。
      (b) `state: TESTED` への書き込みは、受領書が存在し、宣言された全コマンドが
          `exit_code: 0` であり、`commit` が現在の HEAD と一致する場合のみ許可する。

    (b) の `commit` 一致条件が本質である。これが無ければ、実装を書き換えた後も過去の成功記録を
    使い回して TESTED を宣言できてしまう。
    """
    m = STATUS_YAML_RE.match(rel_path)
    if not m:
        return None
    app_id, feature_id = m.groups()
    status_path = os.path.join(toplevel, rel_path)
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            current_content = f.read()
    except OSError:
        current_content = ""
    new_content = path_utils.simulate_write_result(tool_name, tool_input, current_content)

    def receipt_of(content: str):
        data = path_utils.parse_simple_yaml(content) if content else {}
        return data.get("verification_receipt") if isinstance(data, dict) else None

    old_receipt = receipt_of(current_content)
    new_receipt = receipt_of(new_content)
    if new_receipt != old_receipt:
        return (
            "拒否: `verification_receipt` は手書きできません（検証を実際に実行した記録であるため）。\n"
            "`python3 harness/scripts/run_verification.py "
            f"--app {app_id} --feature {feature_id}` を実行してください。"
        )

    old_state = path_utils.extract_scalar_field(current_content, "state")
    new_state = path_utils.extract_scalar_field(new_content, "state")
    if new_state != "TESTED" or old_state == "TESTED":
        return None

    shared_kernel_path = os.path.join(toplevel, f"apps/{app_id}/01-foundation/shared-kernel.yaml")
    contract_path = os.path.join(toplevel, os.path.dirname(rel_path), "contract.yaml")

    def read_or_empty(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    shared_kernel_content = read_or_empty(shared_kernel_path)
    contract_content = read_or_empty(contract_path)
    if not shared_kernel_content and not contract_content:
        return None  # 宣言元が両方とも無ければ判定不能。ブロックしない

    declaration = path_utils.merge_verification_declaration(shared_kernel_content, contract_content)
    head = path_utils.get_head_commit(toplevel)
    if head is None:
        return None  # git 情報が取れない場合は判定不能
    declared_test_ids = path_utils.extract_declared_test_ids(contract_content)
    return path_utils.validate_verification_receipt(
        declaration, new_receipt, head, declared_test_ids
    )


def check_rule11_integration_receipt_immutable(
    rel_path: str, tool_name: str, tool_input: dict[str, Any], toplevel: str
) -> str | None:
    """Rule 11(a): `integration.machine.yaml` の `verification_receipt` は手書きできない
    （Rule 10(a) の統合版。`run_integration_verification.py` だけが書き込める）。
    """
    m = INTEGRATION_RECORD_RE.match(rel_path)
    if not m:
        return None
    app_id = m.group(1)
    path = os.path.join(toplevel, rel_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            current_content = f.read()
    except OSError:
        current_content = ""
    new_content = path_utils.simulate_write_result(tool_name, tool_input, current_content)

    def receipt_of(content: str):
        data = path_utils.parse_simple_yaml(content) if content else {}
        return data.get("verification_receipt") if isinstance(data, dict) else None

    if receipt_of(new_content) != receipt_of(current_content):
        return (
            "拒否: `verification_receipt` は手書きできません（検証を実際に実行した記録であるため）。\n"
            f"`python3 harness/scripts/run_integration_verification.py --app {app_id}` を実行してください。"
        )
    return None


def check_rule11_integration_receipt(
    rel_path: str, tool_name: str, tool_input: dict[str, Any], toplevel: str
) -> str | None:
    """Rule 11: 統合の受領書ゲート（CONVENTIONS.md 12/13節。Rule 10 の統合版）。

    `state: INTEGRATED` への書き込みは、`04-integration/integration.machine.yaml` に
    `run_integration_verification.py` が生成した受領書があり、宣言された検証コマンドが
    すべて成功し、`architecture.machine.yaml` の `interfaces[]` の全エッジが
    `interface_coverage[]` で結合テストに対応づけられている場合のみ許可する。

    `check_interfaces.py`（契約同士の静的な JSON Schema 比較）はすり抜けるが実地には壊れている
    差異（機能内部の DI インターフェースの形状差、HTTP エンコーディングの不一致など。
    ドッグフーディング F-065/F-066）を、AI の目視ではなく実行結果で機械的に塞ぐためのゲート。
    """
    m = STATUS_YAML_RE.match(rel_path)
    if not m:
        return None
    app_id = m.group(1)
    status_path = os.path.join(toplevel, rel_path)
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            current_content = f.read()
    except OSError:
        current_content = ""
    new_content = path_utils.simulate_write_result(tool_name, tool_input, current_content)
    old_state = path_utils.extract_scalar_field(current_content, "state")
    new_state = path_utils.extract_scalar_field(new_content, "state")
    if new_state != "INTEGRATED" or old_state == "INTEGRATED":
        return None

    rerun_hint = f"`python3 harness/scripts/run_integration_verification.py --app {app_id}` を実行してください。"
    integration_path = os.path.join(toplevel, f"apps/{app_id}/04-integration/integration.machine.yaml")
    try:
        with open(integration_path, "r", encoding="utf-8") as f:
            integration_content = f.read()
    except OSError:
        return (
            f"拒否: apps/{app_id}/04-integration/integration.machine.yaml が見つからないため "
            "INTEGRATED にできません。\n"
            "interfaces[] の各エッジを実地に検証する結合テストの宣言（interface_coverage[]）と "
            f"assembly の verification 宣言をこのファイルに書いてから、\n{rerun_hint}"
        )

    data = path_utils.parse_simple_yaml(integration_content) if integration_content else {}
    declaration = data.get("verification") if isinstance(data, dict) else None
    declaration = declaration if isinstance(declaration, dict) else {}
    receipt = data.get("verification_receipt") if isinstance(data, dict) else None

    head = path_utils.get_head_commit(toplevel)
    if head is None:
        return None  # git 情報が取れない場合は判定不能

    declared_test_ids = path_utils.extract_declared_interface_test_ids(integration_content)
    reason = path_utils.validate_verification_receipt(
        declaration, receipt, head, declared_test_ids,
        target_state="INTEGRATED",
        declaration_label="`04-integration/integration.machine.yaml` の `interface_coverage[]`",
        rerun_hint=rerun_hint,
    )
    if reason:
        return reason

    arch_path = os.path.join(toplevel, f"apps/{app_id}/02-design/architecture.machine.yaml")
    try:
        with open(arch_path, "r", encoding="utf-8") as f:
            architecture_content = f.read()
    except OSError:
        architecture_content = ""
    gaps = path_utils.interface_coverage_gaps(architecture_content, integration_content)
    if gaps:
        return (
            "拒否: interfaces[] の一部が interface_coverage[] でカバーされていません:\n"
            + "\n".join(f"  - {g}" for g in gaps)
            + f"\n{rerun_hint}"
        )
    return None


def is_open_issue_append(current_content: str, new_content: str) -> bool:
    """凍結された契約への書き込みが `open_issues[]` への追記だけか判定する（F-044）。

    凍結後に見つかった契約の穴は、これまで `SPEC.md` にしか書けなかった。`SPEC.md` は
    機械検証の対象外なので統合時に拾われる保証がない。追記だけを許すことで、契約の
    同一性（Rule 3 が守るもの）を保ったまま申し送りを契約側に残せるようにする。

    既存の要素の書き換え・削除・並べ替えは許さない（末尾への追加のみ）。
    パースできない場合は False（＝従来どおり拒否）を返す。
    """
    try:
        old = path_utils.parse_simple_yaml(current_content) if current_content else None
        new = path_utils.parse_simple_yaml(new_content) if new_content else None
    except Exception:
        return False
    if not isinstance(old, dict) or not isinstance(new, dict):
        return False
    if {k: v for k, v in old.items() if k != "open_issues"} != {
        k: v for k, v in new.items() if k != "open_issues"
    }:
        return False
    old_issues = old.get("open_issues") or []
    new_issues = new.get("open_issues") or []
    if not isinstance(old_issues, list) or not isinstance(new_issues, list):
        return False
    # 追記が 1 件以上あるときだけ許す（何も足さない書き込みは凍結の対象のまま）
    return len(new_issues) > len(old_issues) and new_issues[: len(old_issues)] == old_issues


def check_rule3_contract_freeze(
    rel_path: str, toplevel: str, tool_name: str = "", tool_input: dict[str, Any] | None = None
) -> str | None:
    m = FEATURE_CONTRACT_RE.match(rel_path)
    if m:
        status_path = os.path.join(toplevel, os.path.dirname(rel_path), "status.yaml")
        state = path_utils.read_state_field(status_path)
        if state is None or state in ("NOT_STARTED", "CONTRACT_DRAFTED"):
            return None
        if tool_name in ("Edit", "Write", "MultiEdit"):
            try:
                with open(os.path.join(toplevel, rel_path), "r", encoding="utf-8") as f:
                    current_content = f.read()
            except OSError:
                current_content = ""
            new_content = path_utils.simulate_write_result(tool_name, tool_input or {}, current_content)
            if is_open_issue_append(current_content, new_content):
                return None
        return (
            f"拒否: {rel_path} は state={state} のため凍結されています（CONTRACT_DRAFTED までのみ変更可）。\n"
            f"仕様変更が必要な場合は `diff-design` skill で新しい機能バージョンとして起票してください。\n"
            f"契約の穴を申し送るだけなら `open_issues[]` への追記のみ許可されています"
            f"（既存の項目の書き換え・削除はできません）。"
        )

    m = DESIGN_CONTRACT_RE.match(rel_path)
    if m:
        app_id = m.group(1)
        architecture_path = os.path.join(toplevel, f"apps/{app_id}/02-design/architecture.machine.yaml")
        status = path_utils.read_state_field(architecture_path)
        if status is None or status == "DRAFT":
            return None
        return (
            f"拒否: {rel_path} は architecture.machine.yaml が status={status} のため凍結されています"
            f"（DRAFT の間のみ変更可）。"
        )
    return None


# Rule 3・7・9・10・11 が「書き込み前後の内容比較」で判定するファイル。
# 書き込み後の内容を予測できない手段では、これらのゲートが一度も走らないまま素通りする。
CONTENT_JUDGED_RES = (STATUS_YAML_RE, REQUIREMENTS_RE, ARCHITECTURE_RE, INTEGRATION_RECORD_RE)

# `path_utils.simulate_write_result()` が書き込み後の内容を再現できるツール。
# ここに無いツールは「判定できない手段」であり、CONTENT_JUDGED_RES への書き込みを拒否する。
CONTENT_SIMULATABLE_TOOLS = ("Edit", "Write", "MultiEdit")


def check_requires_simulatable_tool(rel_path: str, tool_name: str) -> str | None:
    """内容比較で判定するファイルを、結果を予測できない手段で書くことを拒否する（F-021）。

    `sed -i` で `status: APPROVED` や `state: TESTED` にすれば、内容比較に依存する
    Rule 3・7・9・10・11 は一度も走らなかった。決定論的強制を掲げる以上、**書き込み手段しだいで
    ゲートが消えるのは設計上の穴**なので、判定できない手段そのものを拒否する。

    当初は Bash だけを対象にしていたが、それでは不十分だった（実測で確認）:

    - `NotebookEdit` は `simulate_write_result()` が扱えず、書き込み後の内容として
      **変更前の内容がそのまま返る**。Rule 9・10 から見れば「何も変わっていない」ので
      受領書なしの `state: TESTED` が素通りした。
    - `integration.machine.yaml` は対象に入っておらず、Bash / NotebookEdit から
      **統合受領書を手書きできた**（INV-2 違反）。

    そこで判定を「Bash かどうか」ではなく「**書き込み後の内容を再現できる手段かどうか**」に
    変えた。将来ツールが増えても、`CONTENT_SIMULATABLE_TOOLS` に追加しない限り自動的に拒否側に入る。

    `tool_name` が空のときは判定しない。事後検証（`post_tool_use_guard.py`）は
    「実際に何が変わったか」を見る経路であり、そこにはハーネス自身のスクリプト
    （`run_verification.py` 等。受領書という実行の裏付けを伴う正規の書き込み経路）による
    変更も含まれるため、ここで拒否すると受領書そのものが巻き戻される。
    """
    if not tool_name or tool_name in CONTENT_SIMULATABLE_TOOLS:
        return None
    if not any(pattern.match(rel_path) for pattern in CONTENT_JUDGED_RES):
        return None
    return (
        f"拒否: {rel_path} への {tool_name} 経由の書き込みは受け付けません。\n"
        "Edit/Write/MultiEdit を使ってください（承認・状態遷移・検証受領書・統合受領書のゲート"
        "（Rule 3・7・9・10・11）は書き込み前後の内容を比較して判定するため、"
        f"{tool_name} では書き込み後の内容を再現できず、検証できないまま素通りしてしまいます）。"
    )


def check_rule12_dangerous_operation(
    tool_name: str, tool_input: dict[str, Any], cwd: str, toplevel: str
) -> str | None:
    """Rule 12: 危険操作フロア（CONVENTIONS.md 7節）。

    他の Rule と独立に判定し、**他 Rule が allow でも Rule 12 が deny なら deny が勝つ**。
    パスに紐づく工程の整合性ではなく「この操作自体をやらせない」という別軸の判定なので、
    `run_checks`（書き込み先ごとのループ）ではなく `main` から 1 回だけ呼ぶ。

    確認を求める（ask）のではなく拒否する（deny）。AUTONOMOUS モードでは AI 自身が確認に
    答えてしまうため、確認は歯止めにならない（NG-6）。
    """
    if tool_name == "Bash":
        return path_utils.detect_dangerous_bash_operation(
            tool_input.get("command", "") or "", cwd, toplevel
        )
    if tool_name in ("Read", "NotebookRead"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        return path_utils.detect_dangerous_read(path) if path else None
    return None


def run_checks(
    rel_path: str, cwd: str, toplevel: str, tool_name: str = "", tool_input: dict[str, Any] | None = None
) -> str | None:
    tool_input = tool_input or {}
    for check in (check_rule1_harness_immutability, check_rule2_feature_scope):
        reason = check(rel_path, cwd)
        if reason:
            return reason
    reason = check_rule6_foundation_scope(rel_path, cwd)
    if reason:
        return reason
    reason = check_rule5_required_skills(rel_path, toplevel)
    if reason:
        return reason
    reason = check_rule3_contract_freeze(rel_path, toplevel, tool_name, tool_input)
    if reason:
        return reason
    reason = check_requires_simulatable_tool(rel_path, tool_name)
    if reason:
        return reason
    if tool_name in CONTENT_SIMULATABLE_TOOLS:
        reason = check_rule11_integration_receipt_immutable(rel_path, tool_name, tool_input, toplevel)
        if reason:
            return reason
        reason = check_rule7_requirements_consistency(rel_path, tool_name, tool_input, toplevel)
        if reason:
            return reason
        reason = check_rule7_approval_record(rel_path, tool_name, tool_input, toplevel)
        if reason:
            return reason
        reason = check_rule3_contract_approval_record(rel_path, tool_name, tool_input, toplevel)
        if reason:
            return reason
        reason = check_rule9_status_transition(rel_path, tool_name, tool_input, toplevel)
        if reason:
            return reason
        reason = check_rule10_verification_receipt(rel_path, tool_name, tool_input, toplevel)
        if reason:
            return reason
        reason = check_rule11_integration_receipt(rel_path, tool_name, tool_input, toplevel)
        if reason:
            return reason
    return None


SNAPSHOT_PREFIX = "apparness-bash-guard-"


def snapshot_file_path(cwd: str, session_id: str | None) -> str | None:
    """Bash 実行前後の `git status` を比較するためのスナップショットの置き場所。

    `.git` ディレクトリ配下に置く（作業ツリーを汚さず、git の追跡対象にもならない）。
    `post_tool_use_guard.py` がこの関数を import して同じパスを求める。
    """
    git_dir = path_utils.get_git_dir(cwd)
    if not git_dir:
        return None
    safe = "".join(c for c in str(session_id or "default") if c.isalnum() or c in "-_")[:64]
    return os.path.join(git_dir, f"{SNAPSHOT_PREFIX}{safe or 'default'}.txt")


def save_bash_snapshot(cwd: str, toplevel: str, session_id: str | None) -> None:
    """Bash を許可する直前に作業ツリーの状態を保存する（事後検証の比較元。CONVENTIONS.md 7節末尾）。

    保存するのは状態コードではなく**内容のハッシュと本文**（`capture_worktree_state`）。
    """
    path = snapshot_file_path(cwd, session_id)
    if not path:
        return
    state = path_utils.capture_worktree_state(toplevel)
    if state is None:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except (OSError, TypeError, ValueError):
        pass  # スナップショットが取れなければ事後検証をスキップするだけ（Bash は止めない）


def main() -> int:
    # 寛容版（read_hook_input）だと壊れた入力が `{}` に潰れ、「ツール名なし＝判定対象外」として
    # 通過してしまう。ブロックする hook では判定できない入力は止める（F-R1）。
    payload = path_utils.read_hook_input_strict()
    tool_name = payload.get("tool_name", "")
    tool_input_raw = payload.get("tool_input", {})
    if tool_input_raw is None:
        tool_input_raw = {}
    if not isinstance(tool_input_raw, dict):
        raise path_utils.HookInputError(
            f"tool_input がオブジェクトではありません（{type(tool_input_raw).__name__}）"
        )
    tool_input: dict[str, Any] = tool_input_raw
    cwd = payload.get("cwd") or os.getcwd()

    # 構造化編集ツールなのに書き込み先が入っていない payload は、何に対する操作かを特定できない。
    # 「対象パスなし＝判定対象なし」として通すと、Rule 1〜11 がまとめて空振りする。
    field = path_utils.STRUCTURED_EDIT_PATH_FIELDS.get(tool_name)
    if field is not None and not path_utils.extract_structured_edit_paths(tool_name, tool_input):
        raise path_utils.HookInputError(
            f"{tool_name} の tool_input に書き込み先（{field}）が入っていません"
        )

    toplevel = path_utils.get_worktree_toplevel(cwd) or cwd

    # Rule 12 は他の Rule と独立に、書き込み先に関係なく判定する（deny が勝つ）
    reason = check_rule12_dangerous_operation(tool_name, tool_input, cwd, toplevel)
    if reason:
        print(reason, file=sys.stderr)
        return 2

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        candidates = path_utils.extract_bash_candidate_paths(command)
        violations: list[str] = []
        for candidate in candidates:
            target_rel, target_top = path_utils.resolve_write_target(candidate, cwd, toplevel)
            rel_path, scope_top = path_utils.resolve_worktree_scope(target_rel, target_top)
            reason = run_checks(rel_path, cwd, scope_top, "Bash", tool_input)
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
        # 静的解析ですり抜ける書き込み（変数展開されたパス等）を実行後に検出するため、
        # 直前の作業ツリーの状態を保存しておく（post_tool_use_guard.py が比較する）
        save_bash_snapshot(cwd, toplevel, payload.get("session_id"))
        return 0

    for abs_path in path_utils.extract_structured_edit_paths(tool_name, tool_input):
        target_rel, target_top = path_utils.resolve_write_target(abs_path, cwd, toplevel)
        rel_path, scope_top = path_utils.resolve_worktree_scope(target_rel, target_top)
        reason = run_checks(rel_path, cwd, scope_top, tool_name, tool_input)
        if reason:
            print(reason, file=sys.stderr)
            return 2

    return 0


def _fail_closed_main() -> int:
    """想定外の例外で **通過** させない（fail-closed）。

    Hook が exit != 2 で終わると Claude Code はそれを「判断なし＝通過」として扱う。
    例外を握りつぶすと、全ルールが黙って無効化された状態で作業が続いてしまう（F-A2）。
    判定できなかったのなら、通すのではなく止めて人間に見せるほうが安全側である。
    """
    try:
        return main()
    except path_utils.HookInputError as exc:
        print(
            "拒否: ハーネスの強制レイヤ（pre_tool_use_guard.py）が hook の入力を解釈できませんでした。\n"
            f"  {exc}\n"
            "何に対する操作かが分からない状態では Rule 1〜12 のどれも判定できません。"
            "通すのではなく止めます。\n"
            "PreToolUse に渡される payload（JSON）が壊れています。"
            "Hook の起動方法（`.claude/settings.json` の command）を確認してください。",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # noqa: BLE001
        print(
            "拒否: ハーネスの強制レイヤ（pre_tool_use_guard.py）が想定外の例外で判定できませんでした。\n"
            f"  {type(exc).__name__}: {exc}\n"
            "判定できない状態で書き込みを通すと、全ルールが黙って無効化された状態で作業が続きます。\n"
            "`python3 harness/hooks/session_start_healthcheck.py` で強制レイヤの状態を確認してください。",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(_fail_closed_main())
