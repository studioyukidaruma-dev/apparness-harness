"""Rule 13（人間向け文書の読み取り拒否・CONVENTIONS.md 7節）の実証。

AI は実行物と規約から動作を判断し、人間向けの説明を根拠に作業しない。説明と実装が
食い違ったとき、説明を読んだ AI はその食い違いをそのまま作業に持ち込むため。

Hook を実際にサブプロセスとして起動し、payload → 終了コードという契約そのものを見る。
「拒否されること」と「正当な読み取りが通ること」を対にしてある。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import ci_check
import pytest

HOOK = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "pre_tool_use_guard.py"


def _git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """配布元と同じ配置（直下の `docs/` と `harness/docs/`）を持つ一時リポジトリ。"""
    root = tmp_path / "repo"
    for rel in (
        "docs/DESIGN.md",
        "harness/docs/GUIDE.md",
        "harness/scripts/tool.py",
        "apps/demo/docs/notes.md",
        "README.md",
    ):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x\n", encoding="utf-8")
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "tester"],
        ["add", "-A"],
        ["commit", "-q", "-m", "init"],
    ):
        _git(root, *args)
    return root


def run(repo: pathlib.Path, tool_name: str, tool_input: dict, cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    payload = {"tool_name": tool_name, "tool_input": tool_input, "cwd": str(cwd or repo)}
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True, cwd=str(cwd or repo)
    )


def assert_denied(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 2, result.stderr
    assert "Rule 13" in result.stderr


def assert_allowed(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------------------
# 構造化ツール
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("rel", ["docs/DESIGN.md", "harness/docs/GUIDE.md"])
def test_rule13_blocks_reading_human_docs(repo: pathlib.Path, rel: str) -> None:
    assert_denied(run(repo, "Read", {"file_path": str(repo / rel)}))


def test_rule13_blocks_notebook_read(repo: pathlib.Path) -> None:
    assert_denied(run(repo, "NotebookRead", {"notebook_path": str(repo / "docs" / "x.ipynb")}))


@pytest.mark.parametrize("rel", ["README.md", "harness/scripts/tool.py", "apps/demo/docs/notes.md"])
def test_rule13_allows_reading_other_files(repo: pathlib.Path, rel: str) -> None:
    """アプリ側の `docs/` は人間向け文書ではない（ハーネスの文書だけが対象）。"""
    assert_allowed(run(repo, "Read", {"file_path": str(repo / rel)}))


def test_rule13_blocks_grep_into_human_docs(repo: pathlib.Path) -> None:
    assert_denied(run(repo, "Grep", {"pattern": "x", "path": str(repo / "harness" / "docs")}))
    assert_denied(run(repo, "Grep", {"pattern": "x", "path": str(repo), "glob": "docs/**/*.md"}))


def test_rule13_does_not_block_a_repository_wide_grep(repo: pathlib.Path) -> None:
    """検索全般を止めると作業にならない。範囲を絞らない検索は対象外（既知の限界）。"""
    assert_allowed(run(repo, "Grep", {"pattern": "x", "path": str(repo)}))
    assert_allowed(run(repo, "Grep", {"pattern": "x", "path": str(repo), "glob": "*.md"}))


# --------------------------------------------------------------------------------------
# Bash
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        "cat docs/DESIGN.md",
        "head -n 20 harness/docs/GUIDE.md",
        "grep -rn Rule docs/",
        "rg Rule harness/docs",
        "sed -n 1,5p docs/DESIGN.md",
        "grep -e docs docs/DESIGN.md",
        "ls && cat ./docs/DESIGN.md",
    ],
)
def test_rule13_blocks_bash_reads_of_human_docs(repo: pathlib.Path, command: str) -> None:
    assert_denied(run(repo, "Bash", {"command": command}))


def test_rule13_resolves_relative_paths_from_the_session_cwd(repo: pathlib.Path) -> None:
    assert_denied(run(repo, "Bash", {"command": "cat ../docs/DESIGN.md"}, cwd=repo / "harness"))


@pytest.mark.parametrize(
    "command",
    [
        "ls docs",                         # 名前の一覧は内容の読み取りではない
        "grep -rn 'docs/' harness",        # 最初の位置引数はパターンでありパスではない
        "cat README.md",
        "git mv docs/DESIGN.md docs/X.md",
    ],
)
def test_rule13_allows_bash_commands_that_do_not_read_human_docs(repo: pathlib.Path, command: str) -> None:
    assert_allowed(run(repo, "Bash", {"command": command}))


# --------------------------------------------------------------------------------------
# 例外と導入先
# --------------------------------------------------------------------------------------

def test_rule13_allows_reading_on_a_harness_maintenance_branch(repo: pathlib.Path) -> None:
    """文書の保守には Edit の前の Read が要る。ハーネス保守ブランチでは読める。"""
    _git(repo, "switch", "-q", "-c", "harness/docs-fix")
    assert_allowed(run(repo, "Read", {"file_path": str(repo / "docs" / "DESIGN.md")}))
    assert_allowed(run(repo, "Bash", {"command": "cat harness/docs/GUIDE.md"}))


def test_rule13_in_an_installed_project_protects_only_harness_docs(repo: pathlib.Path) -> None:
    """導入先の直下の `docs/` は導入先プロジェクト自身の文書なので、読み取りを妨げない。"""
    (repo / "harness" / "install-manifest.json").write_text("{}", encoding="utf-8")
    assert_allowed(run(repo, "Read", {"file_path": str(repo / "docs" / "DESIGN.md")}))
    assert_denied(run(repo, "Read", {"file_path": str(repo / "harness" / "docs" / "GUIDE.md")}))


def test_rule13_applies_through_a_worktree_path(repo: pathlib.Path) -> None:
    """メインのセッションから worktree 内の人間向け文書を指しても、同じ Rule が効く。"""
    path = repo / "apps" / "demo" / ".worktrees" / "feat-a" / "harness" / "docs" / "GUIDE.md"
    assert_denied(run(repo, "Read", {"file_path": str(path)}))


def test_rule13_has_no_bypass_environment_variable() -> None:
    source = HOOK.read_text(encoding="utf-8")
    start = source.index("def check_rule13_human_docs")
    body = source[start:source.index("\ndef ", start + 1)]
    assert "environ" not in body


# --------------------------------------------------------------------------------------
# CI 項目 R: AI が読む文書から人間向け文書への参照
# --------------------------------------------------------------------------------------


def _write(root: pathlib.Path, rel: str, text: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    "rel",
    [
        ".claude/agents/builder.md",
        ".claude/skills/init-app/SKILL.md",
        "harness/procedures/feature-build.md",
        "harness/CONVENTIONS.md",
        "harness/quality/security-baseline.md",
        "harness/STACK_PACK.md",
    ],
)
def test_item_r_rejects_a_reference_to_human_docs(tmp_path: pathlib.Path, rel: str) -> None:
    _write(tmp_path, rel, "# 手順\n\n詳しくは `harness/docs/GUIDE.md` を読むこと。\n")
    violations = ci_check.check_human_doc_references(tmp_path)
    assert len(violations) == 1 and f"{rel}:3" in violations[0]


def test_item_r_rejects_a_root_docs_reference(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, ".claude/agents/builder.md", "背景は docs/DESIGN.md 参照\n")
    assert len(ci_check.check_human_doc_references(tmp_path)) == 1


def test_item_r_allows_a_policy_line_marked_for_humans(tmp_path: pathlib.Path) -> None:
    """人間向け文書の扱いを定める規範は、対象を名指しできないと書けない。"""
    _write(tmp_path, "harness/CONVENTIONS.md", "- 人間向け文書 `docs/` と `harness/docs/` は AI が読まない\n")
    assert ci_check.check_human_doc_references(tmp_path) == []


@pytest.mark.parametrize(
    "line",
    [
        "アプリの資料は `apps/<app-id>/docs/` に置く",   # アプリ側の docs/ はハーネスの文書ではない
        '#     url: "./docs/genkou-daichou.xlsx"',
        "mydocs/ は対象外",
    ],
)
def test_item_r_ignores_paths_that_are_not_harness_human_docs(tmp_path: pathlib.Path, line: str) -> None:
    _write(tmp_path, ".claude/agents/builder.md", line + "\n")
    assert ci_check.check_human_doc_references(tmp_path) == []


def test_item_r_does_not_scan_human_docs_themselves(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, "harness/docs/GUIDE.md", "詳しくは docs/DESIGN.md\n")
    _write(tmp_path, "docs/DESIGN.md", "利用者は harness/docs/GUIDE.md\n")
    assert ci_check.check_human_doc_references(tmp_path) == []


def test_item_r_passes_on_this_repository() -> None:
    repo_root = pathlib.Path(__file__).resolve().parent.parent.parent
    assert ci_check.check_human_doc_references(repo_root) == []
