"""`harness/CLAIMS.md` が主張する「Rule N は今も本当にブロックする」を Rule 単位で実証する。

既存のテスト群は Rule 1・2・3・5・7・9・10・11 を個別に押さえているが、Rule 4・6・8 と、
worktree 経由での Rule 1・3・5 の発火は、どのファイルにも実証が無かった（F-A5）。
F-029/F-030 は「中核ルール群が丸ごと空振りしていても気付ける経路が無かった」ことを示しており、
主張と証跡の対応が取れていない箇所は、その空振りが起きても誰も気付けない箇所である。

このファイルはその欠けを埋める。各テストは `CLAIMS.md` の「実証テスト」列から参照される。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

import path_utils
import pre_tool_use_guard
import pytest

HOOKS_DIR = pathlib.Path(__file__).resolve().parent.parent / "hooks"
PRE_HOOK = HOOKS_DIR / "pre_tool_use_guard.py"
STOP_HOOK = HOOKS_DIR / "stop_commit_guard.py"
SYNC_HOOK = HOOKS_DIR / "post_tool_use_sync.py"

APP = "demo"
FEATURE = "feat-a"
WT = f"apps/{APP}/.worktrees/{FEATURE}/"


def _git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """フェーズ節目ファイルを 1 つ持つ、コミット済みの一時 git リポジトリ。"""
    root = tmp_path / "repo"
    (root / f"apps/{APP}/03-features/{FEATURE}").mkdir(parents=True)
    (root / f"apps/{APP}/03-features/{FEATURE}/status.yaml").write_text(
        f"feature_id: {FEATURE}\napp_id: {APP}\nstate: IN_PROGRESS\n", encoding="utf-8"
    )
    # Rule 4 は `<repo>/harness/scripts/render_progress.py` を起動する。本物を参照させる
    # （テスト用のスタブに差し替えると「本当に走ったか」を確かめたことにならない）。
    os.symlink(HOOKS_DIR.parent, root / "harness")
    (root / ".gitignore").write_text("harness\n", encoding="utf-8")
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "tester"],
        ["add", "-A"],
        ["commit", "-q", "-m", "init"],
    ):
        _git(root, *args)
    return root


def run_hook(hook: pathlib.Path, repo: pathlib.Path, payload: dict) -> subprocess.CompletedProcess:
    # hooks 自体は依存ゼロだが、Rule 4 が起動する render_progress.py は PyYAML を使う。
    # hook は `sys.executable` で子プロセスを起動するので、テストからも同じ実行系で呼ぶ。
    return subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps({**payload, "cwd": str(repo)}),
        capture_output=True,
        text=True,
        cwd=repo,
    )


def _reason(rel_path: str, cwd: str, toplevel: str, monkeypatch, session_top: str | None = None, **kwargs):
    """`.worktrees/` の読み替えを通してから `run_checks` に掛ける（実運用と同じ経路）。

    `session_top` は「セッションがどの worktree で動いているか」（Rule 2・6 が見る値）。
    省略時は `toplevel` と同じ。Rule 3・5 の worktree 経由の発火を見たいときは、
    担当 worktree で動いているセッションを再現するためにこちらを指定する
    （そうしないと Rule 2 が先に発火して、確かめたい Rule まで到達しない）。
    """
    monkeypatch.setattr(path_utils, "get_worktree_toplevel", lambda _cwd: session_top or toplevel)
    scope_rel, scope_top = path_utils.resolve_worktree_scope(rel_path, toplevel)
    return pre_tool_use_guard.run_checks(scope_rel, cwd, scope_top, **kwargs)


# --------------------------------------------------------------------------------------
# Rule 4: status.yaml の更新でダッシュボードが再生成される（非ブロッキング）
# --------------------------------------------------------------------------------------

def test_rule4_regenerates_the_dashboard_when_status_changes(repo: pathlib.Path) -> None:
    """Rule 4 は「ブロックする」ルールではなく「必ず走る」ルール。走ったことを成果物で確かめる。"""
    status = repo / f"apps/{APP}/03-features/{FEATURE}/status.yaml"
    result = run_hook(
        SYNC_HOOK,
        repo,
        {"tool_name": "Write", "tool_input": {"file_path": str(status), "content": ""}},
    )
    assert result.returncode == 0  # 非ブロッキング
    assert (repo / f"apps/{APP}/PROGRESS.md").exists(), result.stderr
    assert (repo / f"apps/{APP}/STATE.machine.yaml").exists(), result.stderr


def test_rule4_ignores_paths_that_do_not_affect_the_dashboard(repo: pathlib.Path) -> None:
    result = run_hook(
        SYNC_HOOK,
        repo,
        {"tool_name": "Write", "tool_input": {"file_path": str(repo / "README.md"), "content": ""}},
    )
    assert result.returncode == 0
    assert not (repo / f"apps/{APP}/PROGRESS.md").exists()


# --------------------------------------------------------------------------------------
# Rule 6: feature 用 worktree から上位文書への書き込みを拒否する
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rel_path",
    [
        f"apps/{APP}/00-requirements/requirements.machine.yaml",
        f"apps/{APP}/01-foundation/shared-kernel.yaml",
        f"apps/{APP}/02-design/design.md",
    ],
)
def test_rule6_blocks_upstream_documents_from_a_feature_worktree(rel_path: str, monkeypatch) -> None:
    top = f"/repo/apps/{APP}/.worktrees/{FEATURE}"
    reason = _reason(rel_path, top, top, monkeypatch)
    assert reason is not None
    assert "担当範囲外" in reason


def test_rule6_allows_upstream_documents_from_the_main_worktree(monkeypatch) -> None:
    """メインの worktree（solution-architect / diff-design）からの書き込みは通ること。"""
    reason = _reason(f"apps/{APP}/02-design/design.md", "/repo", "/repo", monkeypatch)
    assert reason is None


def test_rule6_judges_by_the_session_not_by_the_target_tree(monkeypatch) -> None:
    """F-055 の再発防止。feature worktree のセッションがメイン側の上位文書を書く場合も拒否する。"""
    top = f"/repo/apps/{APP}/.worktrees/{FEATURE}"
    reason = _reason(f"apps/{APP}/02-design/design.md", top, top, monkeypatch)
    assert reason is not None


# --------------------------------------------------------------------------------------
# Rule 8: フェーズ節目ファイルの未コミットを残したまま停止できない
# --------------------------------------------------------------------------------------

def test_rule8_blocks_stopping_with_an_uncommitted_status_yaml(repo: pathlib.Path) -> None:
    status = repo / f"apps/{APP}/03-features/{FEATURE}/status.yaml"
    status.write_text(status.read_text(encoding="utf-8") + "blockers: []\n", encoding="utf-8")
    result = run_hook(STOP_HOOK, repo, {})
    assert result.returncode == 2
    assert "status.yaml" in result.stderr


def test_rule8_blocks_stopping_with_an_untracked_phase_marker(repo: pathlib.Path) -> None:
    """新規追加（未追跡）もコミット漏れの対象に含める。"""
    design = repo / f"apps/{APP}/02-design"
    design.mkdir(parents=True)
    (design / "architecture.machine.yaml").write_text("status: DRAFT\n", encoding="utf-8")
    result = run_hook(STOP_HOOK, repo, {})
    assert result.returncode == 2
    assert "architecture.machine.yaml" in result.stderr


def test_rule8_allows_stopping_when_everything_is_committed(repo: pathlib.Path) -> None:
    assert run_hook(STOP_HOOK, repo, {}).returncode == 0


def test_rule8_does_not_loop_when_stop_hook_is_already_active(repo: pathlib.Path) -> None:
    status = repo / f"apps/{APP}/03-features/{FEATURE}/status.yaml"
    status.write_text("state: IMPLEMENTED\n", encoding="utf-8")
    assert run_hook(STOP_HOOK, repo, {"stop_hook_active": True}).returncode == 0


# --------------------------------------------------------------------------------------
# worktree 経由での発火（F-029/F-030 の再発防止を Rule 1・3・5 にも広げる）
#
# Rule 2・9・10 は test_worktree_scope.py が押さえている。ここは残りの 3 本。
# --------------------------------------------------------------------------------------

def test_rule1_blocks_harness_writes_through_a_worktree_path(monkeypatch) -> None:
    monkeypatch.setattr(path_utils, "get_current_branch", lambda _cwd: "feature/demo/feat-a")
    monkeypatch.delenv("HARNESS_UNLOCK", raising=False)
    reason = _reason(WT + "harness/CONVENTIONS.md", "/repo", "/repo", monkeypatch)
    assert reason is not None
    assert "ハーネス本体" in reason


def test_rule1_allows_harness_writes_through_a_worktree_path_on_a_harness_branch(monkeypatch) -> None:
    monkeypatch.setattr(path_utils, "get_current_branch", lambda _cwd: "harness/topic")
    reason = _reason(WT + "harness/CONVENTIONS.md", "/repo", "/repo", monkeypatch)
    assert reason is None


def _worktree_feature_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    d = tmp_path / f"apps/{APP}/.worktrees/{FEATURE}/apps/{APP}/03-features/{FEATURE}"
    d.mkdir(parents=True)
    return d


def test_rule3_blocks_a_frozen_contract_through_a_worktree_path(tmp_path, monkeypatch) -> None:
    feature_dir = _worktree_feature_dir(tmp_path)
    (feature_dir / "status.yaml").write_text("state: IN_PROGRESS\n", encoding="utf-8")
    (feature_dir / "contract.yaml").write_text("feature_id: feat-a\nversion: 1\n", encoding="utf-8")
    reason = _reason(
        WT + f"apps/{APP}/03-features/{FEATURE}/contract.yaml",
        str(tmp_path),
        str(tmp_path),
        monkeypatch,
        session_top=str(tmp_path / f"apps/{APP}/.worktrees/{FEATURE}"),
        tool_name="Write",
        tool_input={"content": "feature_id: feat-a\nversion: 2\n"},
    )
    assert reason is not None
    assert "凍結" in reason


def test_rule3_allows_a_draft_contract_through_a_worktree_path(tmp_path, monkeypatch) -> None:
    feature_dir = _worktree_feature_dir(tmp_path)
    (feature_dir / "status.yaml").write_text("state: CONTRACT_DRAFTED\n", encoding="utf-8")
    (feature_dir / "contract.yaml").write_text("feature_id: feat-a\nversion: 1\n", encoding="utf-8")
    reason = _reason(
        WT + f"apps/{APP}/03-features/{FEATURE}/contract.yaml",
        str(tmp_path),
        str(tmp_path),
        monkeypatch,
        session_top=str(tmp_path / f"apps/{APP}/.worktrees/{FEATURE}"),
        tool_name="Write",
        tool_input={"content": "feature_id: feat-a\nversion: 2\n"},
    )
    assert reason is None


def test_rule5_blocks_missing_required_skills_through_a_worktree_path(tmp_path, monkeypatch) -> None:
    worktree_root = tmp_path / f"apps/{APP}/.worktrees/{FEATURE}"
    feature_dir = _worktree_feature_dir(tmp_path)
    (feature_dir / "src").mkdir()
    kernel = worktree_root / f"apps/{APP}/01-foundation"
    kernel.mkdir(parents=True)
    (kernel / "shared-kernel.yaml").write_text(
        'required_skills:\n- name: "x"\n  plugin_ref: "x@market"\n  purpose: "y"\n', encoding="utf-8"
    )
    reason = _reason(
        WT + f"apps/{APP}/03-features/{FEATURE}/src/x.py",
        str(tmp_path),
        str(tmp_path),
        monkeypatch,
        session_top=str(tmp_path / f"apps/{APP}/.worktrees/{FEATURE}"),
        tool_name="Write",
        tool_input={"content": ""},
    )
    assert reason is not None
    assert "Skill が不足" in reason


def test_rule5_allows_when_the_required_skill_is_enabled_through_a_worktree_path(
    tmp_path, monkeypatch
) -> None:
    worktree_root = tmp_path / f"apps/{APP}/.worktrees/{FEATURE}"
    feature_dir = _worktree_feature_dir(tmp_path)
    (feature_dir / "src").mkdir()
    kernel = worktree_root / f"apps/{APP}/01-foundation"
    kernel.mkdir(parents=True)
    (kernel / "shared-kernel.yaml").write_text(
        'required_skills:\n- name: "x"\n  plugin_ref: "x@market"\n  purpose: "y"\n', encoding="utf-8"
    )
    settings = worktree_root / ".claude"
    settings.mkdir(parents=True)
    (settings / "settings.json").write_text(
        json.dumps({"enabledPlugins": {"x@market": True}}), encoding="utf-8"
    )
    reason = _reason(
        WT + f"apps/{APP}/03-features/{FEATURE}/src/x.py",
        str(tmp_path),
        str(tmp_path),
        monkeypatch,
        session_top=str(tmp_path / f"apps/{APP}/.worktrees/{FEATURE}"),
        tool_name="Write",
        tool_input={"content": ""},
    )
    assert reason is None


# --------------------------------------------------------------------------------------
# Rule 1 の緊急避難路（8節）が今も 1 本だけであること
# --------------------------------------------------------------------------------------

def test_only_rule1_has_an_escape_hatch() -> None:
    """INV-4: Bash 検知にバイパス用の環境変数を足していないこと。

    `HARNESS_UNLOCK` 以外の環境変数で判定を緩めるコードが増えていたら、決定論的強制の
    前提が崩れているサイン。ソースを直接見て固定する。
    """
    source = (HOOKS_DIR / "pre_tool_use_guard.py").read_text(encoding="utf-8")
    env_reads = set(re.findall(r"os\.environ(?:\.get)?\(\s*[\"']([A-Z_]+)[\"']", source))
    assert env_reads <= {"HARNESS_UNLOCK"}, f"新しいバイパス用環境変数: {env_reads}"
