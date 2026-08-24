"""`ci_check.py` の各項目が、違反する入力を与えたら実際に不合格を返すことの実証。

CI はサーバーサイドの二重チェックであり、Hook をすり抜けた変更（人間の直接コミット、
Claude Code を経由しない編集）に対する最後の砦である。ところが項目 A・B・E・F・G・I は
どのテストからも呼ばれておらず、**丸ごと空振りしていても誰も気付けない**状態だった（F-A5）。

ここでは「その項目が拒否すると主張しているものを与えたら本当に拒否するか」と、
「正常な入力を誤って拒否しないか」を対で固定する。項目 C・D・J・K・L・M・N・O は
別ファイルが押さえている（対応は `harness/CLAIMS.md`）。
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import ci_check  # noqa: E402

HARNESS_ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = "demo"
FEATURE = "feat-a"


def _git(repo: pathlib.Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return out.stdout.strip()


@pytest.fixture()
def root(tmp_path: pathlib.Path) -> pathlib.Path:
    """ハーネス資源（schemas/scripts）を持つ、git 管理下の一時リポジトリ。

    `ci_check` は `_common.harness_root()` 経由でスキーマとスクリプトを読むため、実体を
    コピーする（スタブに差し替えると、判定に使う定義が本物と食い違っても気付けない）。
    """
    repo = tmp_path / "repo"
    (repo / "harness").mkdir(parents=True)
    for name in ("schemas", "scripts"):
        shutil.copytree(HARNESS_ROOT / name, repo / "harness" / name)
    (repo / "harness" / "CONVENTIONS.md").write_text(
        (HARNESS_ROOT / "CONVENTIONS.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo / ".claude" / "agents").mkdir(parents=True)
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "tester"],
    ):
        _git(repo, *args)
    return repo


def commit_all(repo: pathlib.Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def write(repo: pathlib.Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


STATUS_TMPL = """feature_id: "{feature}"
app_id: "{app}"
state: {state}
state_history:
- state: {state}
  at: "2026-08-24T00:00:00Z"
  by: "tester"
blockers: []
last_updated_at: "2026-08-24T00:00:00Z"
"""


# --------------------------------------------------------------------------------------
# 項目 A: machine-readable YAML の JSON Schema 検証
# --------------------------------------------------------------------------------------

def test_item_a_rejects_a_status_yaml_violating_its_schema(root: pathlib.Path) -> None:
    write(root, f"apps/{APP}/03-features/{FEATURE}/status.yaml", 'state: "NOT_A_STATE"\n')
    violations = ci_check.check_schema(root)
    assert violations, "スキーマ違反の status.yaml が素通りしている"
    assert "status.schema.json" in violations[0]


def test_item_a_accepts_a_valid_status_yaml(root: pathlib.Path) -> None:
    write(
        root,
        f"apps/{APP}/03-features/{FEATURE}/status.yaml",
        STATUS_TMPL.format(app=APP, feature=FEATURE, state="NOT_STARTED"),
    )
    assert ci_check.check_schema(root) == []


# --------------------------------------------------------------------------------------
# 項目 B: Rule 1 相当（harness/.claude/.github は harness/<topic> ブランチでのみ変更可）
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["harness/CONVENTIONS.md", ".claude/settings.json", ".github/x.yml"])
def test_item_b_rejects_harness_changes_from_a_feature_branch(path: str) -> None:
    violations = ci_check.check_harness_immutability(f"feature/{APP}/{FEATURE}", [("M", path)])
    assert len(violations) == 1 and path in violations[0]


def test_item_b_allows_harness_changes_on_a_harness_branch() -> None:
    assert ci_check.check_harness_immutability("harness/topic", [("M", "harness/CONVENTIONS.md")]) == []


def test_item_b_exempts_the_personal_local_settings() -> None:
    violations = ci_check.check_harness_immutability(
        f"feature/{APP}/{FEATURE}", [("M", ".claude/settings.local.json")]
    )
    assert violations == []


def test_item_b_is_skipped_on_the_default_branch() -> None:
    """fast-forward マージ後の main では「元々どのブランチで作られたか」が git 上に残らない。"""
    assert ci_check.check_harness_immutability("main", [("M", "harness/CONVENTIONS.md")]) == []


# --------------------------------------------------------------------------------------
# 項目 E: Rule 7 相当（APPROVED な設計は要件の現在の version を参照していること）
# --------------------------------------------------------------------------------------

def _requirements(version: int) -> str:
    return f"""app_id: "{APP}"
version: {version}
status: APPROVED
summary: "x"
goals: []
functional_requirements: []
approved_by: "human"
approved_at: "2026-08-24T00:00:00Z"
"""


def _architecture(based_on: int, status: str = "APPROVED") -> str:
    return f"""app_id: "{APP}"
version: 1
status: {status}
based_on_requirements_version: {based_on}
features: []
interfaces: []
approved_by: "human"
approved_at: "2026-08-24T00:00:00Z"
"""


def test_item_e_rejects_an_approved_design_pinned_to_an_old_requirements_version(root) -> None:
    write(root, f"apps/{APP}/00-requirements/requirements.machine.yaml", _requirements(2))
    write(root, f"apps/{APP}/02-design/architecture.machine.yaml", _architecture(1))
    violations = ci_check.check_requirements_architecture_consistency(root)
    assert len(violations) == 1 and "不一致" in violations[0]


def test_item_e_accepts_a_design_that_follows_the_current_requirements(root) -> None:
    write(root, f"apps/{APP}/00-requirements/requirements.machine.yaml", _requirements(2))
    write(root, f"apps/{APP}/02-design/architecture.machine.yaml", _architecture(2))
    assert ci_check.check_requirements_architecture_consistency(root) == []


def test_item_e_ignores_a_design_that_is_still_a_draft(root) -> None:
    write(root, f"apps/{APP}/00-requirements/requirements.machine.yaml", _requirements(2))
    write(root, f"apps/{APP}/02-design/architecture.machine.yaml", _architecture(1, status="DRAFT"))
    assert ci_check.check_requirements_architecture_consistency(root) == []


# --------------------------------------------------------------------------------------
# 項目 F: Rule 9 相当（コミット間の state 遷移が妥当であること）
# --------------------------------------------------------------------------------------

def test_item_f_rejects_a_multi_step_jump_between_commits(root: pathlib.Path) -> None:
    rel = f"apps/{APP}/03-features/{FEATURE}/status.yaml"
    write(root, rel, STATUS_TMPL.format(app=APP, feature=FEATURE, state="NOT_STARTED"))
    base = commit_all(root, "init")
    write(root, rel, STATUS_TMPL.format(app=APP, feature=FEATURE, state="TESTED"))
    commit_all(root, "jump")
    violations = ci_check.check_status_transitions(base, [("M", rel)], root)
    assert len(violations) == 1 and "飛ばしています" in violations[0]


def test_item_f_accepts_a_single_step_forward(root: pathlib.Path) -> None:
    rel = f"apps/{APP}/03-features/{FEATURE}/status.yaml"
    write(root, rel, STATUS_TMPL.format(app=APP, feature=FEATURE, state="NOT_STARTED"))
    base = commit_all(root, "init")
    write(root, rel, STATUS_TMPL.format(app=APP, feature=FEATURE, state="CONTRACT_DRAFTED"))
    commit_all(root, "forward")
    assert ci_check.check_status_transitions(base, [("M", rel)], root) == []


def test_item_f_ignores_newly_added_status_files(root: pathlib.Path) -> None:
    """旧状態が無いので判定不能。ここを拒否にすると新規機能が作れなくなる。"""
    rel = f"apps/{APP}/03-features/{FEATURE}/status.yaml"
    write(root, rel, STATUS_TMPL.format(app=APP, feature=FEATURE, state="TESTED"))
    base = commit_all(root, "init")
    assert ci_check.check_status_transitions(base, [("A", rel)], root) == []


# --------------------------------------------------------------------------------------
# 項目 I: Rule 10 相当（TESTED/INTEGRATED には有効な受領書が要る）
# --------------------------------------------------------------------------------------

SHARED_KERNEL = """app_id: "demo"
version: 1
required_skills: []
verification:
  test_command: "true"
notes: ""
"""


def _tested_status(receipt_commit: str | None) -> str:
    body = STATUS_TMPL.format(app=APP, feature=FEATURE, state="TESTED")
    if receipt_commit is None:
        return body
    return body + f"""verification_receipt:
  commit: "{receipt_commit}"
  test:
    exit_code: 0
    at: "2026-08-24T00:00:00Z"
"""


def test_item_i_rejects_tested_without_a_receipt(root: pathlib.Path) -> None:
    write(root, f"apps/{APP}/01-foundation/shared-kernel.yaml", SHARED_KERNEL)
    write(root, f"apps/{APP}/03-features/{FEATURE}/status.yaml", _tested_status(None))
    head = commit_all(root, "init")
    violations = ci_check.check_verification_receipts(root, head)
    assert len(violations) == 1 and "verification_receipt" in violations[0]


def test_item_i_rejects_a_receipt_that_is_not_in_the_history(root: pathlib.Path) -> None:
    write(root, f"apps/{APP}/01-foundation/shared-kernel.yaml", SHARED_KERNEL)
    write(root, f"apps/{APP}/03-features/{FEATURE}/status.yaml", _tested_status("0" * 40))
    head = commit_all(root, "init")
    violations = ci_check.check_verification_receipts(root, head)
    assert len(violations) == 1 and "履歴に存在しません" in violations[0]


def test_item_i_rejects_an_implementation_changed_after_verification(root: pathlib.Path) -> None:
    """項目 I の本質。検証したあとに実装を書き換えていないことを、履歴の差分で確かめる。"""
    write(root, f"apps/{APP}/01-foundation/shared-kernel.yaml", SHARED_KERNEL)
    write(root, f"apps/{APP}/03-features/{FEATURE}/src/x.py", "x = 1\n")
    verified = commit_all(root, "implementation")
    write(root, f"apps/{APP}/03-features/{FEATURE}/status.yaml", _tested_status(verified))
    write(root, f"apps/{APP}/03-features/{FEATURE}/src/x.py", "x = 2\n")  # 検証後の書き換え
    head = commit_all(root, "tested with a stale receipt")
    violations = ci_check.check_verification_receipts(root, head)
    assert len(violations) == 1 and "後に実装が変更されています" in violations[0]


def test_item_i_accepts_a_receipt_taken_at_the_verified_commit(root: pathlib.Path) -> None:
    write(root, f"apps/{APP}/01-foundation/shared-kernel.yaml", SHARED_KERNEL)
    write(root, f"apps/{APP}/03-features/{FEATURE}/src/x.py", "x = 1\n")
    verified = commit_all(root, "implementation")
    write(root, f"apps/{APP}/03-features/{FEATURE}/status.yaml", _tested_status(verified))
    head = commit_all(root, "tested")
    assert ci_check.check_verification_receipts(root, head) == []


def test_item_i_rejects_tested_without_a_declared_test_command(root: pathlib.Path) -> None:
    write(root, f"apps/{APP}/03-features/{FEATURE}/status.yaml", _tested_status(None))
    head = commit_all(root, "init")
    violations = ci_check.check_verification_receipts(root, head)
    assert len(violations) == 1 and "test_command" in violations[0]


# --------------------------------------------------------------------------------------
# 項目 G: PROGRESS.md / STATE.machine.yaml の鮮度
# --------------------------------------------------------------------------------------

def test_item_g_rejects_a_stale_dashboard(root: pathlib.Path) -> None:
    write(
        root,
        f"apps/{APP}/03-features/{FEATURE}/status.yaml",
        STATUS_TMPL.format(app=APP, feature=FEATURE, state="IMPLEMENTED"),
    )
    write(root, f"apps/{APP}/PROGRESS.md", "# 古いダッシュボード\n")
    violations = ci_check.check_progress_freshness(root, "main")
    assert violations and "PROGRESS.md" in violations[0]


def test_item_g_accepts_a_freshly_rendered_dashboard(root: pathlib.Path) -> None:
    write(
        root,
        f"apps/{APP}/03-features/{FEATURE}/status.yaml",
        STATUS_TMPL.format(app=APP, feature=FEATURE, state="IMPLEMENTED"),
    )
    subprocess.run(
        [sys.executable, str(root / "harness" / "scripts" / "render_progress.py"), "--app", APP],
        cwd=root, check=True, capture_output=True,
    )
    assert ci_check.check_progress_freshness(root, "main") == []


def test_item_g_does_not_leave_the_worktree_dirty(root: pathlib.Path) -> None:
    """判定のための再生成の副作用を必ず戻すこと（戻さないと項目 C に引っかかる）。"""
    write(
        root,
        f"apps/{APP}/03-features/{FEATURE}/status.yaml",
        STATUS_TMPL.format(app=APP, feature=FEATURE, state="IMPLEMENTED"),
    )
    write(root, f"apps/{APP}/PROGRESS.md", "# 古いダッシュボード\n")
    ci_check.check_progress_freshness(root, "main")
    assert (root / f"apps/{APP}/PROGRESS.md").read_text(encoding="utf-8") == "# 古いダッシュボード\n"
