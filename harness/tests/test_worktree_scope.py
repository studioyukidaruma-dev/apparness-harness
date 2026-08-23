"""`.worktrees/` を通るパスでも Rule が発火することの回帰テスト。

ドッグフーディング（`DOGFOODING-LOG.md` の F-029 / F-030）で、メインの worktree から
`apps/<app>/.worktrees/<feature-id>/apps/<app>/03-features/<feature-id>/...` を書き込むと
Rule 1・2・3・5・9・10 がまとめて素通りすることが実証された。原因は各 Rule の正規表現が
worktree 相対パスの先頭にアンカーされていて、ハーネス自身が規定する worktree の実体パスに
マッチしなかったこと。**受領書なしで `state: TESTED` を書き込めた**ため、ハーネスが最も強く
主張しているゲートが空振りしていた。

ここでは `resolve_worktree_scope` による読み替えと、それを使う各 Rule の発火を固定する。
"""
from __future__ import annotations

import os

import pre_tool_use_guard
import path_utils


WT = "apps/demo/.worktrees/feat-a/"


# --------------------------------------------------------------------------------------
# resolve_worktree_scope
# --------------------------------------------------------------------------------------

def test_worktree_prefix_is_stripped_and_root_is_rebased():
    rel, top = path_utils.resolve_worktree_scope(
        WT + "apps/demo/03-features/feat-a/src/x.py", "/repo"
    )
    assert rel == "apps/demo/03-features/feat-a/src/x.py"
    assert top == os.path.join("/repo", "apps", "demo", ".worktrees", "feat-a")


def test_path_without_worktree_prefix_is_unchanged():
    """worktree の中から書いている場合は恒等写像でなければならない（既存動作の保護）。"""
    rel, top = path_utils.resolve_worktree_scope(
        "apps/demo/03-features/feat-a/src/x.py", "/repo"
    )
    assert rel == "apps/demo/03-features/feat-a/src/x.py"
    assert top == "/repo"


def test_harness_path_inside_worktree_is_still_harness():
    rel, _top = path_utils.resolve_worktree_scope(WT + "harness/hooks/x.py", "/repo")
    assert rel == "harness/hooks/x.py"


def test_nested_worktree_prefixes_are_all_stripped():
    rel, _top = path_utils.resolve_worktree_scope(
        WT + "apps/demo/.worktrees/feat-b/apps/demo/03-features/feat-b/src/x.py", "/repo"
    )
    assert rel == "apps/demo/03-features/feat-b/src/x.py"


def test_unrelated_apps_path_is_unchanged():
    rel, top = path_utils.resolve_worktree_scope("apps/demo/02-design/design.md", "/repo")
    assert rel == "apps/demo/02-design/design.md"
    assert top == "/repo"


# --------------------------------------------------------------------------------------
# Rule 2 が `.worktrees/` 経由でも発火すること（F-029）
# --------------------------------------------------------------------------------------

def _reject_reason(rel_path: str, cwd: str, toplevel: str, monkeypatch, **kwargs):
    monkeypatch.setattr(path_utils, "get_worktree_toplevel", lambda _cwd: toplevel)
    scope_rel, scope_top = path_utils.resolve_worktree_scope(rel_path, toplevel)
    return pre_tool_use_guard.run_checks(scope_rel, cwd, scope_top, **kwargs)


def test_rule2_blocks_write_into_other_worktree_from_main(monkeypatch):
    reason = _reject_reason(
        WT + "apps/demo/03-features/feat-a/src/x.py", "/repo", "/repo", monkeypatch
    )
    assert reason is not None
    assert "担当範囲外" in reason


def test_rule2_allows_write_from_the_owning_worktree(monkeypatch):
    """その機能の worktree の中からなら通ること（過剰ブロックしていないことの確認）。"""
    top = "/repo/apps/demo/.worktrees/feat-a"
    reason = _reject_reason(
        "apps/demo/03-features/feat-a/src/x.py", top, top, monkeypatch
    )
    assert reason is None


def test_rule2_exempts_status_yaml(monkeypatch):
    reason = _reject_reason(
        WT + "apps/demo/03-features/feat-a/status.yaml", "/repo", "/repo", monkeypatch
    )
    assert reason is None


# --------------------------------------------------------------------------------------
# Rule 10 が `.worktrees/` 経由でも発火すること（F-030）
# --------------------------------------------------------------------------------------

def _write_status(tmp_path, state: str) -> str:
    """`<tmp>/apps/demo/.worktrees/feat-a/apps/demo/03-features/feat-a/status.yaml` を作る。"""
    feature_dir = tmp_path / "apps/demo/.worktrees/feat-a/apps/demo/03-features/feat-a"
    feature_dir.mkdir(parents=True)
    status = feature_dir / "status.yaml"
    status.write_text(f"feature_id: feat-a\napp_id: demo\nstate: {state}\n", encoding="utf-8")
    kernel_dir = tmp_path / "apps/demo/.worktrees/feat-a/apps/demo/01-foundation"
    kernel_dir.mkdir(parents=True)
    (kernel_dir / "shared-kernel.yaml").write_text(
        'verification:\n  test_command: "pytest -q"\n', encoding="utf-8"
    )
    return str(status)


def test_rule10_blocks_tested_without_receipt_via_worktree_path(tmp_path, monkeypatch):
    """F-030 の再発防止。受領書が無いのに TESTED にする書き込みは拒否されること。"""
    status_path = _write_status(tmp_path, "IMPLEMENTED")
    monkeypatch.setattr(path_utils, "get_worktree_toplevel", lambda _cwd: str(tmp_path))
    monkeypatch.setattr(path_utils, "get_head_commit", lambda _cwd: "a" * 40)

    rel_path = path_utils.to_worktree_relative(status_path, str(tmp_path))
    scope_rel, scope_top = path_utils.resolve_worktree_scope(rel_path, str(tmp_path))
    reason = pre_tool_use_guard.run_checks(
        scope_rel,
        str(tmp_path),
        scope_top,
        tool_name="Edit",
        tool_input={
            "file_path": status_path,
            "old_string": "state: IMPLEMENTED",
            "new_string": "state: TESTED",
        },
    )
    assert reason is not None
    assert "verification_receipt" in reason


def test_rule10_uses_worktree_head_not_session_cwd_head(tmp_path, monkeypatch):
    """F-073 の再発防止。

    feature-builder がオーケストレーターから起動され、実プロセスの cwd がメインリポジトリの
    ルート（＝対象 worktree とは別の git チェックアウト）のままでも、`state: TESTED` への
    遷移判定は対象 worktree（`resolve_worktree_scope` が返す `scope_top`）の HEAD で
    行われなければならない。修正前は `get_head_commit(cwd)` で判定しており、cwd がメイン
    リポジトリだと常にメインリポジトリの HEAD が返るため、worktree 側でどれだけ正しい
    受領書を作っても一致せず TESTED に進めなかった。
    """
    status_path = _write_status(tmp_path, "IMPLEMENTED")
    # run_verification.py が既に受領書を書き込んだ状態を再現する（このテストの主眼は
    # 受領書の有無ではなく commit 照合に使う HEAD の取得元なので、Edit では state だけを
    # 変え、verification_receipt は old/new で同一に保つ）。
    receipt_block = (
        "verification_receipt:\n"
        "  commit: " + "b" * 40 + "\n"
        "  test:\n"
        "    exit_code: 0\n"
    )
    with open(status_path, "a", encoding="utf-8") as f:
        f.write(receipt_block)
    monkeypatch.setattr(path_utils, "get_worktree_toplevel", lambda _cwd: str(tmp_path))

    worktree_top = str(tmp_path / "apps/demo/.worktrees/feat-a")
    main_repo_cwd = str(tmp_path)  # 対象 worktree とは異なる、物理的な cwd

    def fake_get_head_commit(path):
        # 呼び出し元が正しく worktree のルートを渡していれば worktree の HEAD、
        # 誤ってセッションの生 cwd（メインリポジトリ）を渡していれば別の HEAD が返る。
        if os.path.normpath(path) == os.path.normpath(worktree_top):
            return "b" * 40
        return "c" * 40  # メインリポジトリ側の無関係な HEAD

    monkeypatch.setattr(path_utils, "get_head_commit", fake_get_head_commit)

    old_string = "state: IMPLEMENTED"

    rel_path = path_utils.to_worktree_relative(status_path, str(tmp_path))
    scope_rel, scope_top = path_utils.resolve_worktree_scope(rel_path, str(tmp_path))
    assert scope_top == worktree_top

    reason = pre_tool_use_guard.run_checks(
        scope_rel,
        main_repo_cwd,
        scope_top,
        tool_name="Edit",
        tool_input={
            "file_path": status_path,
            "old_string": old_string,
            "new_string": "state: TESTED",
        },
    )
    assert reason is None, f"worktree の HEAD で一致するはずなのに拒否された: {reason}"


def test_rule9_blocks_multi_step_jump_via_worktree_path(tmp_path, monkeypatch):
    """F-030 と同時に確認された、3段飛ばし遷移の素通りの再発防止。"""
    status_path = _write_status(tmp_path, "CONTRACT_APPROVED")
    monkeypatch.setattr(path_utils, "get_worktree_toplevel", lambda _cwd: str(tmp_path))

    rel_path = path_utils.to_worktree_relative(status_path, str(tmp_path))
    scope_rel, scope_top = path_utils.resolve_worktree_scope(rel_path, str(tmp_path))
    reason = pre_tool_use_guard.run_checks(
        scope_rel,
        str(tmp_path),
        scope_top,
        tool_name="Edit",
        tool_input={
            "file_path": status_path,
            "old_string": "state: CONTRACT_APPROVED",
            "new_string": "state: TESTED",
        },
    )
    assert reason is not None
    assert "飛ばしています" in reason
