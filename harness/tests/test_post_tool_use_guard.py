"""`post_tool_use_guard.py`（Bash の事後検証）の end-to-end 検証。

静的解析（`pre_tool_use_guard.py` の Bash 検知）では**原理的に**検知できない書き込み
——変数展開されたパス、スクリプト経由の書き込みなど——を、実行後の `git status` との比較で
確実に検出して巻き戻せることを確かめる。

同時に、**実行前から dirty だったパスは巻き戻さない**ことも固定する。ここを間違えると、
Claude Code の外で人間が編集していた内容を無関係な Bash コマンドが破壊してしまう。
"""
from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

HOOKS_DIR = pathlib.Path(__file__).resolve().parent.parent / "hooks"
PRE_HOOK = HOOKS_DIR / "pre_tool_use_guard.py"
POST_HOOK = HOOKS_DIR / "post_tool_use_guard.py"

SESSION = "test-session"


@pytest.fixture()
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """`harness/` を持つ一時 git リポジトリ（`main` ブランチなので Rule 1 が効く）。"""
    root = tmp_path / "repo"
    (root / "harness").mkdir(parents=True)
    (root / "harness" / "CONVENTIONS.md").write_text("original\n", encoding="utf-8")
    (root / "work.txt").write_text("free\n", encoding="utf-8")
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "tester"],
        ["add", "-A"],
        ["commit", "-q", "-m", "init"],
    ):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    return root


def run_hook(hook: pathlib.Path, repo: pathlib.Path, command: str) -> subprocess.CompletedProcess:
    payload = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": str(repo),
            "session_id": SESSION,
        }
    )
    return subprocess.run(
        ["python3", str(hook)], input=payload, capture_output=True, text=True, cwd=repo
    )


def bash(repo: pathlib.Path, command: str) -> None:
    subprocess.run(["bash", "-c", command], cwd=repo, check=True, capture_output=True)


def cycle(repo: pathlib.Path, command: str) -> subprocess.CompletedProcess:
    """PreToolUse（スナップショット保存）→ 実際のコマンド実行 → PostToolUse（事後検証）。"""
    pre = run_hook(PRE_HOOK, repo, command)
    assert pre.returncode == 0, f"静的検知で止まった: {pre.stderr}"
    bash(repo, command)
    return run_hook(POST_HOOK, repo, command)


# --------------------------------------------------------------------------------------
# 静的解析では検知できない書き込みの検出と巻き戻し
# --------------------------------------------------------------------------------------

def test_variable_expanded_path_is_detected_and_reverted(repo) -> None:
    """`>> "$VAR"` は静的解析では検知できない（ガイド 11 節の既知の検知漏れ）。"""
    result = cycle(repo, 'TARGET=harness/CONVENTIONS.md; echo tampered >> "$TARGET"')
    assert result.returncode == 2
    assert "harness/CONVENTIONS.md" in result.stderr
    assert "巻き戻し済み" in result.stderr
    assert (repo / "harness" / "CONVENTIONS.md").read_text(encoding="utf-8") == "original\n"


def test_write_through_a_script_is_detected_and_reverted(repo) -> None:
    result = cycle(
        repo,
        "printf 'echo x > harness/CONVENTIONS.md\\n' > gen.sh; bash gen.sh",
    )
    assert result.returncode == 2
    assert (repo / "harness" / "CONVENTIONS.md").read_text(encoding="utf-8") == "original\n"


def test_newly_created_guarded_file_is_removed(repo) -> None:
    result = cycle(repo, 'D=harness; echo x > "$D/new_file.py"')
    assert result.returncode == 2
    assert not (repo / "harness" / "new_file.py").exists()


# --------------------------------------------------------------------------------------
# 誤検知の回避
# --------------------------------------------------------------------------------------

def test_writes_outside_guarded_paths_are_left_alone(repo) -> None:
    result = cycle(repo, 'T=work.txt; echo appended >> "$T"')
    assert result.returncode == 0
    assert "appended" in (repo / "work.txt").read_text(encoding="utf-8")


def test_read_only_command_changes_nothing(repo) -> None:
    result = cycle(repo, "cat harness/CONVENTIONS.md > /dev/null")
    assert result.returncode == 0


def test_preexisting_dirty_guarded_path_is_not_reverted(repo) -> None:
    """Claude Code の外で行われていた編集を、無関係な Bash コマンドが破壊しないこと。"""
    (repo / "harness" / "CONVENTIONS.md").write_text("edited by a human\n", encoding="utf-8")
    result = cycle(repo, "echo hello > /dev/null")
    assert result.returncode == 0
    assert (repo / "harness" / "CONVENTIONS.md").read_text(encoding="utf-8") == "edited by a human\n"


def test_harness_branch_may_write_to_harness(repo) -> None:
    subprocess.run(["git", "checkout", "-q", "-b", "harness/topic"], cwd=repo, check=True)
    result = cycle(repo, 'T=harness/CONVENTIONS.md; echo legit >> "$T"')
    assert result.returncode == 0
    assert "legit" in (repo / "harness" / "CONVENTIONS.md").read_text(encoding="utf-8")


def test_without_a_snapshot_nothing_is_reverted(repo) -> None:
    """スナップショットが無ければ（比較不能なら）何もしない。"""
    bash(repo, "echo tampered >> harness/CONVENTIONS.md")
    result = run_hook(POST_HOOK, repo, "echo tampered >> harness/CONVENTIONS.md")
    assert result.returncode == 0
    assert "tampered" in (repo / "harness" / "CONVENTIONS.md").read_text(encoding="utf-8")


def test_non_bash_tools_are_ignored(repo) -> None:
    payload = json.dumps({"tool_name": "Edit", "tool_input": {}, "cwd": str(repo)})
    result = subprocess.run(
        ["python3", str(POST_HOOK)], input=payload, capture_output=True, text=True, cwd=repo
    )
    assert result.returncode == 0


def test_snapshot_is_stored_inside_the_git_directory(repo) -> None:
    run_hook(PRE_HOOK, repo, "echo hi")
    snapshots = list((repo / ".git").glob("apparness-bash-guard-*.txt"))
    assert len(snapshots) == 1


# --------------------------------------------------------------------------------------
# 比較の基準は「状態コード」ではなく「内容」 — ドッグフーディング F-050
# --------------------------------------------------------------------------------------

def test_git_add_alone_does_not_trigger_a_revert(repo) -> None:
    """`git add` はファイルの内容を変えないので、事後検証は発火してはいけない。

    F-050: 比較を `git status` の状態コードで行っていたため、`git add` による
    ` M` → `M ` の変化を「Bash がファイルを変更した」と誤検知し、**正当な編集を巻き戻していた**。
    実際に `contract.yaml` への `open_issues[]` 追記（Rule 3 が許可した書き込み）が消えた。
    """
    (repo / "harness" / "CONVENTIONS.md").write_text("legitimately edited\n", encoding="utf-8")
    result = cycle(repo, "git add -A")
    assert result.returncode == 0, result.stderr
    assert (repo / "harness" / "CONVENTIONS.md").read_text(encoding="utf-8") == "legitimately edited\n"


def test_further_change_to_an_already_dirty_path_is_detected(repo) -> None:
    """実行前から dirty なファイルをさらに書き換えた場合も検知する（旧実装の取りこぼし）。

    状態コードでの比較では ` M` のままなので変化が見えず、素通りしていた。
    """
    (repo / "harness" / "CONVENTIONS.md").write_text("human edit\n", encoding="utf-8")
    result = cycle(repo, 'T=harness/CONVENTIONS.md; echo tampered >> "$T"')
    assert result.returncode == 2
    assert "tampered" not in (repo / "harness" / "CONVENTIONS.md").read_text(encoding="utf-8")


def test_revert_restores_the_pre_bash_content_not_head(repo) -> None:
    """巻き戻し先は HEAD ではなく **Bash 実行直前の内容**。人間の編集を巻き添えにしない。"""
    (repo / "harness" / "CONVENTIONS.md").write_text("human edit\n", encoding="utf-8")
    result = cycle(repo, 'T=harness/CONVENTIONS.md; echo tampered >> "$T"')
    assert result.returncode == 2
    assert (repo / "harness" / "CONVENTIONS.md").read_text(encoding="utf-8") == "human edit\n"


def test_unmodified_dirty_paths_keep_their_content_when_another_path_is_reverted(repo) -> None:
    """違反したパスだけを戻し、同時に dirty だった無関係なパスには触れない。"""
    (repo / "work.txt").write_text("in progress\n", encoding="utf-8")
    result = cycle(repo, 'T=harness/CONVENTIONS.md; echo tampered >> "$T"')
    assert result.returncode == 2
    assert (repo / "work.txt").read_text(encoding="utf-8") == "in progress\n"
