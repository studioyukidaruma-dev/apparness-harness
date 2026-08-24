"""`pre_tool_use_guard.py` を**実際にサブプロセスとして起動**して、Hook が課すルールが
end-to-end で効いていることを検証する。

`path_utils` の単体テストは判定ロジックの正しさを見るが、こちらは「Claude Code から渡される
payload → 終了コード」という Hook の契約そのものを見る（exit 0 = 許可 / exit 2 = 拒否）。
一時的な git リポジトリを作って本物の `git` に対して判定させるため、worktree 解決や HEAD の
照合といった git 依存の部分も含めて検証できる。
"""
from __future__ import annotations

import json
import pathlib
import subprocess

import path_utils
import pre_tool_use_guard
import pytest

HOOK = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "pre_tool_use_guard.py"

APP = "demo-app"
FEATURE = "todo-list-api"
FEATURE_DIR = f"apps/{APP}/03-features/{FEATURE}"

SHARED_KERNEL = f"""app_id: "{APP}"
version: 1
required_skills: []
verification:
  test_command: "true"
notes: ""
"""

CONTRACT = f"""feature_id: "{FEATURE}"
feature_name: "TODO 一覧 API"
version: 1
description: "x"
inputs: []
outputs: []
tech_stack:
  language: "python"
  libraries: []
approved_by: "solution-architect (AUTONOMOUS)"
approved_at: "2026-08-21T09:00:00Z"
"""

# 承認者が記録されていない契約（Rule 3 の承認記録ゲート用）
CONTRACT_WITHOUT_APPROVAL = CONTRACT.replace(
    'approved_by: "solution-architect (AUTONOMOUS)"', "approved_by: null"
).replace('approved_at: "2026-08-21T09:00:00Z"', "approved_at: null")


def requirements_yaml(status: str = "APPROVED", approved_by: str = '"せのび！"') -> str:
    return f"""app_id: "{APP}"
version: 2
status: {status}
summary: "x"
goals: []
functional_requirements: []
approved_by: {approved_by}
approved_at: "2026-08-21T09:00:00Z"
"""


def architecture_yaml(status: str = "DRAFT", approved_by: str = "null") -> str:
    return f"""app_id: "{APP}"
version: 1
status: {status}
based_on_requirements_version: 2
features: []
interfaces: []
approved_by: {approved_by}
approved_at: "2026-08-21T09:30:00Z"
"""


def status_yaml(state: str, receipt: str = "", history: list | None = None) -> str:
    entries = history if history is not None else [state]
    history_block = "".join(
        f'- state: {s}\n  at: "2026-08-21T10:{i:02d}:00Z"\n  by: "tester"\n'
        for i, s in enumerate(entries)
    )
    return f"""feature_id: "{FEATURE}"
app_id: "{APP}"
state: {state}
state_history:
{history_block}blockers: []
last_updated_at: "2026-08-21T10:00:00Z"
{receipt}"""


def receipt_block(commit: str, exit_code: int = 0) -> str:
    return f"""verification_receipt:
  commit: "{commit}"
  test:
    exit_code: {exit_code}
    at: "2026-08-21T10:00:00Z"
"""


@pytest.fixture()
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """機能 1 つ分の最小構成を持つ一時 git リポジトリ。"""
    # ディレクトリ名を feature-id に合わせる（Rule 2 の担当範囲判定は worktree ルートの
    # basename を見るため、これで「その機能の worktree の中」を再現できる）
    root = tmp_path / FEATURE
    (root / FEATURE_DIR).mkdir(parents=True)
    (root / f"apps/{APP}/01-foundation").mkdir(parents=True)
    (root / f"apps/{APP}/01-foundation/shared-kernel.yaml").write_text(SHARED_KERNEL, encoding="utf-8")
    (root / f"apps/{APP}/00-requirements").mkdir(parents=True)
    (root / f"apps/{APP}/00-requirements/requirements.machine.yaml").write_text(
        requirements_yaml(), encoding="utf-8"
    )
    (root / f"apps/{APP}/02-design").mkdir(parents=True)
    (root / f"apps/{APP}/02-design/architecture.machine.yaml").write_text(
        architecture_yaml(), encoding="utf-8"
    )
    (root / FEATURE_DIR / "contract.yaml").write_text(CONTRACT, encoding="utf-8")
    (root / FEATURE_DIR / "status.yaml").write_text(status_yaml("IMPLEMENTED"), encoding="utf-8")
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "tester"],
        ["add", "-A"],
        ["commit", "-q", "-m", "init"],
    ):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    return root


def head_of(repo: pathlib.Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def run_hook(repo: pathlib.Path, tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input, "cwd": str(repo)})
    return subprocess.run(
        ["python3", str(HOOK)], input=payload, capture_output=True, text=True, cwd=repo
    )


def write_status(repo: pathlib.Path, content: str) -> dict:
    return {"file_path": str(repo / FEATURE_DIR / "status.yaml"), "content": content}


# --------------------------------------------------------------------------------------
# Rule 9: 状態遷移
# --------------------------------------------------------------------------------------

def test_rule9_allows_one_step_forward(repo) -> None:
    """IMPLEMENTED → TESTED は Rule 9 的には妥当（Rule 10 で別途止まることは次のテストで見る）。"""
    result = run_hook(repo, "Write", write_status(repo, status_yaml("IN_PROGRESS")))
    assert result.returncode == 2  # IMPLEMENTED からの後退
    assert "後退" in result.stderr


def test_rule9_rejects_skipping_states(repo) -> None:
    (repo / FEATURE_DIR / "status.yaml").write_text(status_yaml("NOT_STARTED"), encoding="utf-8")
    result = run_hook(repo, "Write", write_status(repo, status_yaml("TESTED")))
    assert result.returncode == 2
    assert "飛ばしています" in result.stderr


def test_rule9_blocks_skipping_through_blocked(repo) -> None:
    """`BLOCKED` を一度経由して飛び越す抜け穴が塞がれていること（改善提案⑦）。"""
    blocked = status_yaml("BLOCKED", history=["NOT_STARTED", "BLOCKED"])
    (repo / FEATURE_DIR / "status.yaml").write_text(blocked, encoding="utf-8")
    result = run_hook(
        repo, "Write", write_status(repo, status_yaml("IMPLEMENTED", history=["NOT_STARTED", "BLOCKED"]))
    )
    assert result.returncode == 2
    assert "BLOCKED` の直前の状態" in result.stderr


def test_rule9_allows_a_legitimate_resume_from_blocked(repo) -> None:
    history = ["NOT_STARTED", "CONTRACT_DRAFTED", "BLOCKED"]
    (repo / FEATURE_DIR / "status.yaml").write_text(
        status_yaml("BLOCKED", history=history), encoding="utf-8"
    )
    result = run_hook(
        repo, "Write", write_status(repo, status_yaml("CONTRACT_APPROVED", history=history))
    )
    assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------------------
# Rule 10: 検証受領書ゲート
# --------------------------------------------------------------------------------------

def test_rule10_rejects_tested_without_receipt(repo) -> None:
    result = run_hook(repo, "Write", write_status(repo, status_yaml("TESTED")))
    assert result.returncode == 2
    assert "verification_receipt" in result.stderr


def test_rule10_accepts_tested_with_a_valid_receipt(repo) -> None:
    content = status_yaml("TESTED", receipt_block(head_of(repo)))
    (repo / FEATURE_DIR / "status.yaml").write_text(
        status_yaml("IMPLEMENTED", receipt_block(head_of(repo))), encoding="utf-8"
    )
    result = run_hook(repo, "Write", write_status(repo, content))
    assert result.returncode == 0, result.stderr


def test_rule10_rejects_a_receipt_from_another_commit(repo) -> None:
    stale = "0" * 40
    (repo / FEATURE_DIR / "status.yaml").write_text(
        status_yaml("IMPLEMENTED", receipt_block(stale)), encoding="utf-8"
    )
    result = run_hook(repo, "Write", write_status(repo, status_yaml("TESTED", receipt_block(stale))))
    assert result.returncode == 2
    assert "HEAD" in result.stderr


def test_rule10_rejects_a_failing_receipt(repo) -> None:
    head = head_of(repo)
    (repo / FEATURE_DIR / "status.yaml").write_text(
        status_yaml("IMPLEMENTED", receipt_block(head, exit_code=1)), encoding="utf-8"
    )
    result = run_hook(
        repo, "Write", write_status(repo, status_yaml("TESTED", receipt_block(head, exit_code=1)))
    )
    assert result.returncode == 2
    assert "exit_code" in result.stderr


def test_rule10_rejects_handwritten_receipts(repo) -> None:
    """受領書そのものの手書き（Edit/Write による改変）は state に関係なく拒否する。"""
    result = run_hook(
        repo, "Write", write_status(repo, status_yaml("IMPLEMENTED", receipt_block(head_of(repo))))
    )
    assert result.returncode == 2
    assert "手書き" in result.stderr


# --------------------------------------------------------------------------------------
# Rule 11: 統合の受領書ゲート（interfaces[] の実地カバレッジ）
# --------------------------------------------------------------------------------------

INTEGRATION_PATH = f"apps/{APP}/04-integration/integration.machine.yaml"
ARCH_ONE_EDGE = f"""app_id: "{APP}"
version: 1
status: APPROVED
based_on_requirements_version: 2
features: []
interfaces:
- producer_feature: "a"
  producer_output: "out1"
  consumer_feature: "b"
  consumer_input: "in1"
approved_by: "tester"
approved_at: "2026-08-21T09:30:00Z"
"""


def integration_yaml(coverage: str = "interface_coverage: []\n", receipt: str = "") -> str:
    return f'app_id: "{APP}"\n{coverage}verification:\n  test_command: "true"\n{receipt}'


def _promote_to_tested(repo: pathlib.Path) -> None:
    """Rule 9 の1段階前進を満たしつつ、Rule 11 のテスト対象である INTEGRATED への遷移だけを見る。"""
    (repo / FEATURE_DIR / "status.yaml").write_text(
        status_yaml("TESTED", receipt_block(head_of(repo)), history=["IMPLEMENTED", "TESTED"]),
        encoding="utf-8",
    )


def write_integration(repo: pathlib.Path, content: str) -> dict:
    return {"file_path": str(repo / INTEGRATION_PATH), "content": content}


def test_rule11_blocks_integrated_without_integration_record(repo) -> None:
    _promote_to_tested(repo)
    result = run_hook(
        repo, "Write",
        write_status(repo, status_yaml("INTEGRATED", receipt_block(head_of(repo)))),
    )
    assert result.returncode == 2
    assert "04-integration/integration.machine.yaml" in result.stderr


def test_rule11_blocks_integrated_without_a_receipt(repo) -> None:
    _promote_to_tested(repo)
    (repo / f"apps/{APP}/04-integration").mkdir(parents=True)
    (repo / INTEGRATION_PATH).write_text(integration_yaml(), encoding="utf-8")
    result = run_hook(
        repo, "Write",
        write_status(repo, status_yaml("INTEGRATED", receipt_block(head_of(repo)))),
    )
    assert result.returncode == 2
    assert "verification_receipt" in result.stderr


def test_rule11_blocks_integrated_with_a_coverage_gap(repo) -> None:
    """契約同士は整合していても、実地の結合テストが宣言されていないエッジがあれば拒否する。"""
    _promote_to_tested(repo)
    (repo / f"apps/{APP}/02-design/architecture.machine.yaml").write_text(ARCH_ONE_EDGE, encoding="utf-8")
    (repo / f"apps/{APP}/04-integration").mkdir(parents=True)
    head = head_of(repo)
    (repo / INTEGRATION_PATH).write_text(
        integration_yaml(receipt=receipt_block(head)), encoding="utf-8"
    )
    result = run_hook(
        repo, "Write",
        write_status(repo, status_yaml("INTEGRATED", receipt_block(head))),
    )
    assert result.returncode == 2
    assert "a.out1 -> b.in1" in result.stderr


def test_rule11_accepts_integrated_with_full_coverage_and_a_valid_receipt(repo) -> None:
    _promote_to_tested(repo)
    (repo / f"apps/{APP}/02-design/architecture.machine.yaml").write_text(ARCH_ONE_EDGE, encoding="utf-8")
    (repo / f"apps/{APP}/04-integration").mkdir(parents=True)
    head = head_of(repo)
    coverage = (
        "interface_coverage:\n"
        '- producer_feature: "a"\n'
        '  producer_output: "out1"\n'
        '  consumer_feature: "b"\n'
        '  consumer_input: "in1"\n'
        "  test_ids:\n"
        '  - "t1"\n'
    )
    (repo / INTEGRATION_PATH).write_text(
        integration_yaml(coverage=coverage, receipt=receipt_block(head)), encoding="utf-8"
    )
    result = run_hook(
        repo, "Write",
        write_status(repo, status_yaml("INTEGRATED", receipt_block(head))),
    )
    assert result.returncode == 0, result.stderr


def test_rule11_rejects_handwritten_integration_receipt(repo) -> None:
    (repo / f"apps/{APP}/04-integration").mkdir(parents=True)
    result = run_hook(
        repo, "Write",
        write_integration(repo, integration_yaml(receipt=receipt_block(head_of(repo)))),
    )
    assert result.returncode == 2
    assert "手書き" in result.stderr


def test_rule10_rejects_tested_when_no_test_command_is_declared(repo) -> None:
    (repo / f"apps/{APP}/01-foundation/shared-kernel.yaml").write_text(
        f'app_id: "{APP}"\nversion: 1\nrequired_skills: []\nverification: {{}}\n', encoding="utf-8"
    )
    result = run_hook(repo, "Write", write_status(repo, status_yaml("TESTED")))
    assert result.returncode == 2
    assert "test_command" in result.stderr


# --------------------------------------------------------------------------------------
# Rule 1 / Rule 3 / Bash 経由の間接書き込み
# --------------------------------------------------------------------------------------

def test_rule1_blocks_harness_writes_outside_harness_branches(repo) -> None:
    (repo / "harness").mkdir()
    result = run_hook(repo, "Write", {"file_path": str(repo / "harness" / "x.py"), "content": "x"})
    assert result.returncode == 2
    assert "ハーネス本体" in result.stderr


def test_rule1_allows_harness_writes_on_a_harness_branch(repo) -> None:
    subprocess.run(["git", "checkout", "-q", "-b", "harness/topic"], cwd=repo, check=True)
    (repo / "harness").mkdir()
    result = run_hook(repo, "Write", {"file_path": str(repo / "harness" / "x.py"), "content": "x"})
    assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------------------
# Rule 5: 必須 Skill の充足ゲート（applies_to による機能ごとの絞り込み）
# --------------------------------------------------------------------------------------

OTHER_FEATURE = "other-feature"
OTHER_FEATURE_DIR = f"apps/{APP}/03-features/{OTHER_FEATURE}"


def _repo_with_shared_kernel(tmp_path: pathlib.Path, feature: str, shared_kernel: str) -> pathlib.Path:
    """`repo` フィクスチャと同じ最小構成を、任意の feature_id / shared-kernel 内容で作る。"""
    feature_dir = f"apps/{APP}/03-features/{feature}"
    root = tmp_path / feature
    (root / feature_dir).mkdir(parents=True)
    (root / f"apps/{APP}/01-foundation").mkdir(parents=True)
    (root / f"apps/{APP}/01-foundation/shared-kernel.yaml").write_text(shared_kernel, encoding="utf-8")
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "tester"],
        ["add", "-A"],
        ["commit", "-q", "-m", "init"],
    ):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    return root


SHARED_KERNEL_WITH_SCOPED_SKILL = f"""app_id: "{APP}"
version: 1
required_skills:
- name: "frontend-design"
  plugin_ref: "frontend-design@claude-plugins-official"
  applies_to: ["{FEATURE}"]
verification:
  test_command: "true"
notes: ""
"""


def test_rule5_blocks_the_feature_named_in_applies_to(tmp_path: pathlib.Path) -> None:
    root = _repo_with_shared_kernel(tmp_path, FEATURE, SHARED_KERNEL_WITH_SCOPED_SKILL)
    result = run_hook(
        root, "Write", {"file_path": str(root / FEATURE_DIR / "src" / "a.ts"), "content": "x"}
    )
    assert result.returncode == 2
    assert "frontend-design" in result.stderr


def test_rule5_does_not_block_a_feature_not_named_in_applies_to(tmp_path: pathlib.Path) -> None:
    """他機能向けの Skill を、無関係な機能の実装にまで要求しない（F の per-feature scoping）。"""
    root = _repo_with_shared_kernel(tmp_path, OTHER_FEATURE, SHARED_KERNEL_WITH_SCOPED_SKILL)
    result = run_hook(
        root, "Write", {"file_path": str(root / OTHER_FEATURE_DIR / "src" / "a.ts"), "content": "x"}
    )
    assert result.returncode == 0, result.stderr


def test_rule3_freezes_the_contract_after_approval(repo) -> None:
    result = run_hook(
        repo, "Write", {"file_path": str(repo / FEATURE_DIR / "contract.yaml"), "content": CONTRACT}
    )
    assert result.returncode == 2
    assert "凍結" in result.stderr


def test_bash_indirect_write_to_a_guarded_path_is_blocked(repo) -> None:
    (repo / "harness").mkdir()
    result = run_hook(repo, "Bash", {"command": "echo x > harness/x.py"})
    assert result.returncode == 2
    assert "間接的な書き込み" in result.stderr


def test_bash_read_only_command_is_allowed(repo) -> None:
    result = run_hook(repo, "Bash", {"command": f"cat {FEATURE_DIR}/status.yaml"})
    assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------------------
# Rule 7: 承認ゲート（承認記録の同時性）— ドッグフーディング F-011 / F-020
# --------------------------------------------------------------------------------------

def write_requirements(repo: pathlib.Path, content: str) -> dict:
    return {
        "file_path": str(repo / f"apps/{APP}/00-requirements/requirements.machine.yaml"),
        "content": content,
    }


def write_architecture(repo: pathlib.Path, content: str) -> dict:
    return {
        "file_path": str(repo / f"apps/{APP}/02-design/architecture.machine.yaml"),
        "content": content,
    }


def test_rule7_rejects_requirements_approved_without_approver(repo) -> None:
    """F-011/F-020: `status` だけ先に APPROVED にした中間状態が素通りしていた。"""
    (repo / f"apps/{APP}/00-requirements/requirements.machine.yaml").write_text(
        requirements_yaml(status="DRAFT", approved_by="null"), encoding="utf-8"
    )
    result = run_hook(
        repo, "Edit",
        {
            "file_path": str(repo / f"apps/{APP}/00-requirements/requirements.machine.yaml"),
            "old_string": "status: DRAFT",
            "new_string": "status: APPROVED",
        },
    )
    assert result.returncode == 2
    assert "approved_by" in result.stderr


def test_rule7_allows_requirements_approved_with_approver(repo) -> None:
    result = run_hook(repo, "Write", write_requirements(repo, requirements_yaml()))
    assert result.returncode == 0, result.stderr


def test_rule7_rejects_architecture_approved_without_approver(repo) -> None:
    result = run_hook(
        repo, "Write", write_architecture(repo, architecture_yaml(status="APPROVED"))
    )
    assert result.returncode == 2
    assert "approved_by" in result.stderr


def test_rule7_allows_architecture_approved_with_approver(repo) -> None:
    result = run_hook(
        repo,
        "Write",
        write_architecture(repo, architecture_yaml(status="APPROVED", approved_by='"だれか"')),
    )
    assert result.returncode == 0, result.stderr


def test_rule7_still_checks_requirements_version_consistency(repo) -> None:
    """既存の要件↔設計の整合性ゲートが承認記録ゲートに埋もれていないこと。"""
    stale = architecture_yaml(status="APPROVED", approved_by='"だれか"').replace(
        "based_on_requirements_version: 2", "based_on_requirements_version: 1"
    )
    result = run_hook(repo, "Write", write_architecture(repo, stale))
    assert result.returncode == 2
    assert "based_on_requirements_version" in result.stderr


# --------------------------------------------------------------------------------------
# Rule 3: 契約凍結の根拠（CONTRACT_APPROVED の承認記録）— ドッグフーディング F-039
# --------------------------------------------------------------------------------------

def test_rule3_rejects_contract_approved_without_approver(repo) -> None:
    """F-039: 承認者不明の契約のまま CONTRACT_APPROVED になり、凍結の根拠が確かめられなかった。"""
    (repo / FEATURE_DIR / "contract.yaml").write_text(CONTRACT_WITHOUT_APPROVAL, encoding="utf-8")
    (repo / FEATURE_DIR / "status.yaml").write_text(
        status_yaml("CONTRACT_DRAFTED", history=["NOT_STARTED", "CONTRACT_DRAFTED"]),
        encoding="utf-8",
    )
    result = run_hook(
        repo, "Write",
        write_status(
            repo,
            status_yaml("CONTRACT_APPROVED", history=["NOT_STARTED", "CONTRACT_DRAFTED"]),
        ),
    )
    assert result.returncode == 2
    assert "contract.yaml" in result.stderr


def test_rule3_allows_contract_approved_with_approver(repo) -> None:
    (repo / FEATURE_DIR / "status.yaml").write_text(
        status_yaml("CONTRACT_DRAFTED", history=["NOT_STARTED", "CONTRACT_DRAFTED"]),
        encoding="utf-8",
    )
    result = run_hook(
        repo, "Write",
        write_status(
            repo,
            status_yaml("CONTRACT_APPROVED", history=["NOT_STARTED", "CONTRACT_DRAFTED"]),
        ),
    )
    assert result.returncode == 0, result.stderr


def test_rule3_approval_gate_does_not_fire_on_later_states(repo) -> None:
    """既に CONTRACT_APPROVED を過ぎた機能の状態更新まで巻き込まないこと。"""
    (repo / FEATURE_DIR / "contract.yaml").write_text(CONTRACT_WITHOUT_APPROVAL, encoding="utf-8")
    history = ["NOT_STARTED", "CONTRACT_DRAFTED", "CONTRACT_APPROVED", "IN_PROGRESS"]
    (repo / FEATURE_DIR / "status.yaml").write_text(
        status_yaml("IN_PROGRESS", history=history), encoding="utf-8"
    )
    result = run_hook(
        repo, "Write", write_status(repo, status_yaml("IMPLEMENTED", history=history))
    )
    assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------------------
# Bash 経由での Rule 7・9・10 迂回を塞ぐ — ドッグフーディング F-021
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        f"sed -i 's/state: IMPLEMENTED/state: TESTED/' {FEATURE_DIR}/status.yaml",
        f"echo 'state: TESTED' > {FEATURE_DIR}/status.yaml",
        f"sed -i 's/status: DRAFT/status: APPROVED/' apps/{APP}/00-requirements/requirements.machine.yaml",
        f"cp /tmp/x apps/{APP}/02-design/architecture.machine.yaml",
    ],
)
def test_bash_cannot_write_files_judged_by_content_comparison(repo, command) -> None:
    """F-021: `sed -i` で状態や承認を書き換えると Rule 7・9・10 が一度も走らなかった。"""
    result = run_hook(repo, "Bash", {"command": command})
    assert result.returncode == 2
    assert "Edit/Write/MultiEdit を使ってください" in result.stderr


def test_bash_can_still_read_those_files(repo) -> None:
    result = run_hook(repo, "Bash", {"command": f"grep state {FEATURE_DIR}/status.yaml"})
    assert result.returncode == 0, result.stderr


def test_harness_scripts_can_still_write_the_receipt_through_bash(repo) -> None:
    """受領書は `run_verification.py` が書く。コマンド文字列にパスが現れないため掛からない。"""
    result = run_hook(
        repo,
        "Bash",
        {"command": f"python3 harness/scripts/run_verification.py --app {APP} --feature {FEATURE}"},
    )
    assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------------------
# Rule 3: 凍結された契約への `open_issues[]` 追記 — ドッグフーディング F-044
# --------------------------------------------------------------------------------------

OPEN_ISSUE = """open_issues:
- id: "OI-1"
  summary: "エラー時の終了コードが契約に書かれていない"
  found_at: "2026-08-22T10:00:00Z"
  found_by: "feature-builder"
"""


def test_rule3_allows_appending_an_open_issue_to_a_frozen_contract(repo) -> None:
    """F-044: 凍結後に見つかった契約の穴の記録先が SPEC.md しかなく、統合時に拾われなかった。"""
    result = run_hook(
        repo, "Write",
        {"file_path": str(repo / FEATURE_DIR / "contract.yaml"), "content": CONTRACT + OPEN_ISSUE},
    )
    assert result.returncode == 0, result.stderr


def test_rule3_still_rejects_changing_the_frozen_part(repo) -> None:
    (repo / FEATURE_DIR / "contract.yaml").write_text(CONTRACT + OPEN_ISSUE, encoding="utf-8")
    tampered = (CONTRACT + OPEN_ISSUE).replace('description: "x"', 'description: "書き換え"')
    result = run_hook(
        repo, "Write", {"file_path": str(repo / FEATURE_DIR / "contract.yaml"), "content": tampered}
    )
    assert result.returncode == 2
    assert "凍結" in result.stderr


def test_rule3_rejects_rewriting_an_existing_open_issue(repo) -> None:
    """追記のみ。過去の申し送りをこっそり書き換えることはできない。"""
    (repo / FEATURE_DIR / "contract.yaml").write_text(CONTRACT + OPEN_ISSUE, encoding="utf-8")
    tampered = (CONTRACT + OPEN_ISSUE).replace("エラー時の終了コードが契約に書かれていない", "なんでもない")
    result = run_hook(
        repo, "Write", {"file_path": str(repo / FEATURE_DIR / "contract.yaml"), "content": tampered}
    )
    assert result.returncode == 2
    assert "凍結" in result.stderr


def test_rule3_rejects_open_issue_append_through_bash(repo) -> None:
    """Bash は書き込み後の内容を予測できないため、追記の許可は構造化ツールに限る。"""
    result = run_hook(
        repo, "Bash", {"command": f"echo 'open_issues: []' >> {FEATURE_DIR}/contract.yaml"}
    )
    assert result.returncode == 2


# --------------------------------------------------------------------------------------
# 内容比較で判定するファイルは「結果を予測できる手段」でしか書けない
#
# 当初この制限は Bash だけを対象にしていたが、実測で 3 つの素通りを確認した:
#   ① NotebookEdit で `state: TESTED` を書き込める（受領書ゲートが一度も走らない）
#      `simulate_write_result()` が NotebookEdit を扱えず、書き込み後の内容として
#      変更前の内容がそのまま返るため、Rule 9・10 から見れば「何も変わっていない」。
#   ② Bash で `integration.machine.yaml` を書き換えられる（統合受領書を手書きできる）
#   ③ NotebookEdit でも同じ（②③ は INV-2 違反）
# 判定を「Bash かどうか」ではなく「書き込み後の内容を再現できる手段かどうか」に変えて塞いだ。
# --------------------------------------------------------------------------------------

CONTENT_JUDGED_PATHS = {
    "status.yaml": f"{FEATURE_DIR}/status.yaml",
    "requirements.machine.yaml": f"apps/{APP}/00-requirements/requirements.machine.yaml",
    "architecture.machine.yaml": f"apps/{APP}/02-design/architecture.machine.yaml",
    "integration.machine.yaml": f"apps/{APP}/04-integration/integration.machine.yaml",
}


@pytest.mark.parametrize("label,rel", sorted(CONTENT_JUDGED_PATHS.items()))
def test_notebook_edit_cannot_write_content_judged_files(repo, label: str, rel: str) -> None:
    """NotebookEdit は書き込み後の内容を再現できないため、これらのファイルを書けない。"""
    result = run_hook(
        repo, "NotebookEdit", {"notebook_path": str(repo / rel), "new_source": "state: TESTED"}
    )
    assert result.returncode == 2, f"{label} が NotebookEdit で素通りした: {result.stdout}"
    assert "NotebookEdit" in result.stderr


@pytest.mark.parametrize("label,rel", sorted(CONTENT_JUDGED_PATHS.items()))
def test_bash_cannot_write_content_judged_files(repo, label: str, rel: str) -> None:
    result = run_hook(repo, "Bash", {"command": f"echo x >> {rel}"})
    assert result.returncode == 2, f"{label} が Bash で素通りした: {result.stdout}"


def test_notebook_edit_bypass_of_the_receipt_gate_is_closed(repo) -> None:
    """穴の本体: 受領書なしの `state: TESTED` を NotebookEdit で書き込めないこと。"""
    result = run_hook(
        repo,
        "NotebookEdit",
        {"notebook_path": str(repo / FEATURE_DIR / "status.yaml"),
         "new_source": status_yaml("TESTED")},
    )
    assert result.returncode == 2
    assert "Rule 3・7・9・10・11" in result.stderr


def test_integration_receipt_cannot_be_handwritten_through_bash(repo) -> None:
    """INV-2: 統合受領書を Bash で手書きできないこと。"""
    rel = f"apps/{APP}/04-integration/integration.machine.yaml"
    command = f"printf 'verification_receipt:\\n  commit: \"{head_of(repo)}\"\\n' > {rel}"
    result = run_hook(repo, "Bash", {"command": command})
    assert result.returncode == 2
    assert "integration.machine.yaml" in result.stderr


def test_notebook_edit_is_allowed_outside_content_judged_files(repo) -> None:
    """過剰ブロックしていないこと。本来の用途（ノートブックの編集）は通る。"""
    result = run_hook(
        repo,
        "NotebookEdit",
        {"notebook_path": str(repo / FEATURE_DIR / "src" / "analysis.ipynb"), "new_source": "print(1)"},
    )
    assert result.returncode == 0, result.stderr


def test_structured_tools_are_still_allowed_on_content_judged_files(repo) -> None:
    """Edit/Write/MultiEdit は従来どおり通る（内容は各 Rule が判定する）。"""
    result = run_hook(repo, "Write", write_status(repo, status_yaml("IMPLEMENTED")))
    assert result.returncode == 0, result.stderr


def test_the_simulatable_tool_set_matches_simulate_write_result() -> None:
    """許可する手段の集合が、実際に内容を再現できるツールと一致していること。

    ここがずれると「再現できないのに許可される」（＝ゲートが空振りする）か、
    「再現できるのに拒否される」（＝過剰ブロック）のどちらかが起きる。
    """
    current = "state: IMPLEMENTED\n"
    for tool in pre_tool_use_guard.CONTENT_SIMULATABLE_TOOLS:
        payload = {
            "Write": {"content": "state: TESTED\n"},
            "Edit": {"old_string": "IMPLEMENTED", "new_string": "TESTED"},
            "MultiEdit": {"edits": [{"old_string": "IMPLEMENTED", "new_string": "TESTED"}]},
        }[tool]
        assert path_utils.simulate_write_result(tool, payload, current) != current, tool
    for tool in ("Bash", "NotebookEdit"):
        assert path_utils.simulate_write_result(tool, {"new_source": "state: TESTED"}, current) == current
