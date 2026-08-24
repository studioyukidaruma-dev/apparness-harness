"""実地でアプリを作りながら見つかった穴の再発防止テスト。

いずれも「実運用で 1 度起きたこと」を固定するためのもので、各テストの docstring に
対応する摩擦点 ID を書いてある。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

import path_utils
import post_tool_use_sync

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import _common  # noqa: E402
import ci_check  # noqa: E402
import new_feature_scaffold  # noqa: E402
import run_verification  # noqa: E402


# --------------------------------------------------------------------------------------
# F-008 / F-009: Rule 4（進捗自動再生成）のトリガ範囲
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rel_path,expected_app",
    [
        ("apps/demo/03-features/feat-a/status.yaml", "demo"),
        ("apps/demo/00-requirements/requirements.machine.yaml", "demo"),
        ("apps/demo/02-design/architecture.machine.yaml", "demo"),
    ],
)
def test_progress_sync_triggers_on_approval_documents(rel_path, expected_app):
    """F-008: 要件・設計が APPROVED になってもダッシュボードが再生成されず DRAFT のまま腐っていた。"""
    m = post_tool_use_sync.STATUS_PATH_RE.match(rel_path)
    assert m is not None, rel_path
    assert m.group(1) == expected_app


@pytest.mark.parametrize(
    "rel_path",
    [
        "apps/demo/00-requirements/requirements.md",       # 人間向け文書は対象外
        "apps/demo/02-design/design.md",
        "apps/demo/03-features/feat-a/contract.yaml",
        "apps/demo/01-foundation/shared-kernel.yaml",
        "harness/scripts/render_progress.py",
    ],
)
def test_progress_sync_does_not_trigger_on_unrelated_paths(rel_path):
    assert post_tool_use_sync.STATUS_PATH_RE.match(rel_path) is None


# --------------------------------------------------------------------------------------
# F-002: 受領書の見出しコメントが実行のたびに増殖しない
# --------------------------------------------------------------------------------------

def test_receipt_header_is_not_duplicated_across_runs(tmp_path):
    """F-002: 3 回実行してもヘッダは 1 組。無関係なコメントは巻き込まない。"""
    status = tmp_path / "status.yaml"
    status.write_text(
        "feature_id: x\n# 無関係なコメント\nstate: IMPLEMENTED\n", encoding="utf-8"
    )
    for i in range(3):
        run_verification.write_receipt(status, {"commit": f"c{i}", "test": {"exit_code": 0}})

    text = status.read_text(encoding="utf-8")
    assert text.count("手書き禁止") == 1
    assert "# 無関係なコメント" in text
    assert text.count("verification_receipt:") == 1
    assert "commit: c2" in text


# --------------------------------------------------------------------------------------
# F-036: 項目 G は feature ブランチでは判定しない
# --------------------------------------------------------------------------------------

def test_progress_freshness_is_skipped_on_feature_branch(tmp_path):
    """F-036: 項目 G と項目 C（担当範囲外）は feature ブランチ上で構造的に両立しない。"""
    assert ci_check.check_progress_freshness(tmp_path, "feature/demo/feat-a") == []


def test_progress_freshness_still_runs_on_other_branches(tmp_path, capsys):
    """スキップ条件が広すぎないこと（main / harness ブランチでは判定に入る）。"""
    for branch in ("main", "harness/some-topic", "app/demo/bootstrap", None):
        ci_check.check_progress_freshness(tmp_path, branch)
        assert "スキップ" not in capsys.readouterr().out

    ci_check.check_progress_freshness(tmp_path, "feature/demo/feat-a")
    assert "スキップ" in capsys.readouterr().out


# --------------------------------------------------------------------------------------
# F-016: 項目 D はベース時点の architecture の status で判定する
# --------------------------------------------------------------------------------------

def test_contract_freeze_allows_draft_then_approve_in_one_branch(tmp_path, monkeypatch):
    """F-016: 「契約を書く → 設計を承認する」を同一ブランチで行う正常フローを不合格にしない。"""
    monkeypatch.setattr(ci_check, "_status_field_at", lambda rev, rel, root: "DRAFT")
    changed = [("A", "apps/demo/02-design/features/feat-a.contract.yaml")]
    assert ci_check.check_contract_freeze("base", changed, tmp_path) == []


def test_contract_freeze_still_blocks_edit_after_approval(tmp_path, monkeypatch):
    """ベース時点で既に APPROVED だった設計への追記は、従来どおり拒否されること。"""
    monkeypatch.setattr(ci_check, "_status_field_at", lambda rev, rel, root: "APPROVED")
    changed = [("M", "apps/demo/02-design/features/feat-a.contract.yaml")]
    violations = ci_check.check_contract_freeze("base", changed, tmp_path)
    assert len(violations) == 1
    assert "凍結" in violations[0]


# --------------------------------------------------------------------------------------
# F-014: worktree の分岐元に上位文書が含まれているかの事前検査
# --------------------------------------------------------------------------------------

def _init_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    import subprocess

    root = tmp_path / "repo"
    root.mkdir()
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "t"],
    ):
        subprocess.run(["git", *args], cwd=root, check=True)
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=root, check=True)
    return root


def test_tracked_in_head_detects_documents_on_another_branch(tmp_path):
    """F-014: 別ブランチにコミットされた上位文書は「HEAD に無い」と判定されること。

    worktree の分岐元を `main` 固定にしていたために、`app/<app-id>/bootstrap` に
    コミットされた要件・設計・shared-kernel が worktree に入らず、feature-builder が
    上位文書を読めないまま実装することになっていた（`verification:` 宣言も解決できず、
    どの機能も TESTED にできなかった）。**コミット済みでも別ブランチなら入らない**という
    のが本質なので、ブランチ違いを検出できることを固定する。
    """
    import subprocess

    import new_feature_scaffold

    root = _init_repo(tmp_path)
    rel = "apps/demo/02-design/architecture.machine.yaml"

    # main には無い
    assert new_feature_scaffold.tracked_in_head(root, rel) is False

    # 別ブランチにコミットしても、main の HEAD からは見えない
    subprocess.run(["git", "checkout", "-q", "-b", "app/demo/bootstrap"], cwd=root, check=True)
    (root / rel).parent.mkdir(parents=True)
    (root / rel).write_text("status: APPROVED\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "design"], cwd=root, check=True)
    assert new_feature_scaffold.tracked_in_head(root, rel) is True

    subprocess.run(["git", "checkout", "-q", "main"], cwd=root, check=True)
    assert new_feature_scaffold.tracked_in_head(root, rel) is False


def test_tracked_in_head_is_false_for_uncommitted_file(tmp_path):
    """未コミットの上位文書も「HEAD に無い」と判定されること。"""
    import new_feature_scaffold

    root = _init_repo(tmp_path)
    rel = "apps/demo/01-foundation/shared-kernel.yaml"
    (root / rel).parent.mkdir(parents=True)
    (root / rel).write_text("verification:\n  test_command: \"pytest\"\n", encoding="utf-8")
    assert new_feature_scaffold.tracked_in_head(root, rel) is False


# --------------------------------------------------------------------------------------
# F-011 / F-020: 承認記録の同時性（判定ロジック単体）
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "approved_by,approved_at",
    [
        ("null", "null"),
        ('"せのび！"', "null"),
        ("null", '"2026-08-21T09:00:00Z"'),
        ('""', '"2026-08-21T09:00:00Z"'),
        ("TBD", '"2026-08-21T09:00:00Z"'),
    ],
)
def test_approval_record_requires_both_fields(approved_by, approved_at):
    """F-020: `status` だけ先に APPROVED にした中間状態を書き込み時点で塞ぐ。"""
    content = f"status: APPROVED\napproved_by: {approved_by}\napproved_at: {approved_at}\n"
    assert path_utils.validate_approval_record(content, "requirements.machine.yaml") is not None


def test_approval_record_accepts_a_complete_record():
    content = 'status: APPROVED\napproved_by: "せのび！"\napproved_at: "2026-08-21T09:00:00Z"\n'
    assert path_utils.validate_approval_record(content, "requirements.machine.yaml") is None


def test_approval_record_ignores_documents_that_are_not_approved():
    """DRAFT のうちは承認欄が空でも当然通す（起草を妨げない）。"""
    assert path_utils.validate_approval_record("status: DRAFT\napproved_by: null\n", "x") is None


# --------------------------------------------------------------------------------------
# F-039: 契約ドラフトの承認記録を設計承認から引き継ぐ
# --------------------------------------------------------------------------------------

def test_contract_approval_is_inherited_from_the_design_approval():
    contract = 'feature_id: "a"\n# 末尾のコメント\napproved_at: null\napproved_by: null\n'
    result = new_feature_scaffold.inherit_contract_approval(
        contract, "solution-architect (AUTONOMOUS)", "2026-08-21T11:45:00Z"
    )
    assert 'approved_by: "solution-architect (AUTONOMOUS)"' in result
    assert 'approved_at: "2026-08-21T11:45:00Z"' in result
    assert "# 末尾のコメント" in result  # コメントを巻き込まない


def test_contract_approval_does_not_overwrite_an_existing_record():
    contract = 'approved_by: "だれか"\napproved_at: "2026-01-01T00:00:00Z"\n'
    assert new_feature_scaffold.inherit_contract_approval(contract, "別人", "2026-08-21T11:45:00Z") == contract


def test_contract_approval_is_appended_when_the_field_is_absent():
    result = new_feature_scaffold.inherit_contract_approval(
        'feature_id: "a"', "solution-architect", "2026-08-21T11:45:00Z"
    )
    assert result == (
        'feature_id: "a"\n'
        'approved_by: "solution-architect"\n'
        'approved_at: "2026-08-21T11:45:00Z"\n'
    )


def test_contract_approval_is_left_alone_when_the_design_has_no_approver():
    contract = "approved_by: null\napproved_at: null\n"
    assert new_feature_scaffold.inherit_contract_approval(contract, None, None) == contract


# --------------------------------------------------------------------------------------
# F-038: worktree 側でも進捗が再生成され、feature ブランチがそれをコミットできる
# --------------------------------------------------------------------------------------

def test_feature_branch_may_carry_regenerated_progress_files():
    """F-038: Rule 4 の再生成物は担当者が書いたものではないので、担当範囲外にしない。"""
    changed = [
        ("M", "apps/demo/PROGRESS.md"),
        ("M", "apps/demo/STATE.machine.yaml"),
        ("M", "apps/demo/03-features/feat-a/src/main.py"),
    ]
    assert ci_check.check_feature_branch_scope("feature/demo/feat-a", changed) == []


def test_feature_branch_scope_still_blocks_other_features():
    changed = [("M", "apps/demo/03-features/feat-b/src/main.py")]
    violations = ci_check.check_feature_branch_scope("feature/demo/feat-a", changed)
    assert len(violations) == 1 and "担当範囲外" in violations[0]


# --------------------------------------------------------------------------------------
# F-049: worktree 側の `harness/` は作成時点のスナップショットであり、Hook が使う定義とずれる
# --------------------------------------------------------------------------------------

def _git(repo: pathlib.Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def repo_with_worktree(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """`harness/schemas/demo.json` を持つリポジトリと、そこから切った worktree を返す。"""
    main = tmp_path / "main"
    (main / "harness" / "schemas").mkdir(parents=True)
    (main / "harness" / "schemas" / "demo.json").write_text('{"old": true}', encoding="utf-8")
    _git(main, "init", "-q", "-b", "main")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "tester")
    _git(main, "add", "-A")
    _git(main, "commit", "-q", "-m", "init")
    worktree = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(worktree), "-b", "feature/x")
    # worktree を切ったあとにメイン側だけを改修する（実際に起きた食い違いの再現）
    (main / "harness" / "schemas" / "demo.json").write_text('{"new": true}', encoding="utf-8")
    return main, worktree


def test_harness_root_from_a_worktree_points_at_the_main_repo(repo_with_worktree) -> None:
    """worktree の中から呼んでも、ハーネス資源はメインリポジトリ側を指すこと。

    F-049: worktree 側の `feature-contract.schema.json` が古く、Hook が許可した
    `open_issues[]` 追記をローカル検証だけが不合格にしていた。
    """
    main, worktree = repo_with_worktree
    assert _common.harness_root(worktree) == main / "harness"
    assert (_common.harness_root(worktree) / "schemas" / "demo.json").read_text() == '{"new": true}'


def test_repo_root_still_resolves_to_the_worktree(repo_with_worktree) -> None:
    """**コードはメイン側、データは worktree 側**。アプリの生成物の基準は変えない。"""
    import subprocess

    _main, worktree = repo_with_worktree
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=worktree, capture_output=True, text=True, check=True
    )
    assert pathlib.Path(out.stdout.strip()).resolve() == worktree.resolve()


def test_resolve_harness_path_remaps_a_stale_worktree_copy(repo_with_worktree) -> None:
    """引数で渡された `harness/...` も、メインリポジトリ側の同じ相対位置へ読み替える。"""
    import os

    main, worktree = repo_with_worktree
    stale = worktree / "harness" / "schemas" / "demo.json"
    assert stale.read_text() == '{"old": true}'  # worktree 側は古いまま
    cwd = os.getcwd()
    try:
        os.chdir(worktree)
        assert _common.resolve_harness_path(stale) == main / "harness" / "schemas" / "demo.json"
    finally:
        os.chdir(cwd)


def test_harness_root_falls_back_outside_a_git_repository(tmp_path: pathlib.Path) -> None:
    """git 情報が取れない場所では判定不能として退避する（テストの一時ディレクトリ等）。"""
    assert _common.harness_root(tmp_path) == tmp_path / "harness"


# --------------------------------------------------------------------------------------
# F-055: worktree の外へ出る書き込みが、どの Rule にも掛からなかった
# --------------------------------------------------------------------------------------

@pytest.fixture()
def app_repo_with_worktree(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """アプリ 1 つ・機能 2 つ分の構成を持つリポジトリと、`feat-a` 用の worktree を返す。"""
    main = tmp_path / "main"
    for rel in (
        "harness",
        ".github/workflows",
        "apps/demo/00-requirements",
        "apps/demo/02-design",
        "apps/demo/03-features/feat-a",
        "apps/demo/03-features/feat-b/src",
    ):
        (main / rel).mkdir(parents=True)
    (main / "harness" / "CONVENTIONS.md").write_text("v1\n", encoding="utf-8")
    (main / "apps/demo/02-design/design.md").write_text("d\n", encoding="utf-8")
    _git(main, "init", "-q", "-b", "main")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "tester")
    _git(main, "add", "-A")
    _git(main, "commit", "-q", "-m", "init")
    worktree = main / "apps/demo/.worktrees/feat-a"
    _git(main, "worktree", "add", "-q", str(worktree), "-b", "feature/demo/feat-a")
    return main, worktree


def _guard(cwd: pathlib.Path, tool_name: str, tool_input: dict) -> int:
    import json
    import subprocess

    hook = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "pre_tool_use_guard.py"
    payload = json.dumps(
        {"tool_name": tool_name, "tool_input": tool_input, "cwd": str(cwd), "session_id": "s"}
    )
    return subprocess.run(
        ["python3", str(hook)], input=payload, capture_output=True, text=True, cwd=cwd
    ).returncode


@pytest.mark.parametrize(
    "rel_target",
    [
        "harness/CONVENTIONS.md",                       # Rule 1
        ".github/workflows/ci.yml",                     # Rule 1
        "apps/demo/03-features/feat-b/src/x.py",        # Rule 2
        "apps/demo/02-design/design.md",                # Rule 6
        "apps/demo/00-requirements/requirements.md",    # Rule 6
    ],
)
def test_writing_outside_the_worktree_is_blocked(app_repo_with_worktree, rel_target) -> None:
    """F-055: メインリポジトリ側を直接指す書き込みが素通りしていた。

    Hook はセッションの worktree ルートからの相対パスだけを見ていたため、外を指すパスは
    `../..` で始まり `^harness/` 等にマッチしなかった。判定の基準点をパスの所属先に移した。
    """
    main, worktree = app_repo_with_worktree
    assert _guard(worktree, "Write", {"file_path": str(main / rel_target), "content": "x"}) == 2


def test_writing_outside_the_worktree_through_a_relative_path_is_blocked(
    app_repo_with_worktree,
) -> None:
    """`../../../../harness/...` のような相対パスも、cwd を基準に解決してから判定する。"""
    _main, worktree = app_repo_with_worktree
    command = "echo x >> ../../../../harness/CONVENTIONS.md"
    assert _guard(worktree, "Bash", {"command": command}) == 2


def test_relative_paths_are_resolved_against_cwd_not_the_worktree_root(
    app_repo_with_worktree,
) -> None:
    """セッションの cwd は worktree ルートとは限らない（機能ディレクトリで動くことが多い）。"""
    _main, worktree = app_repo_with_worktree
    feature_dir = worktree / "apps/demo/03-features/feat-a"
    feature_dir.mkdir(parents=True, exist_ok=True)
    command = "echo x >> ../../../../../../../../harness/CONVENTIONS.md"
    assert _guard(feature_dir, "Bash", {"command": command}) == 2


def test_paths_outside_the_repository_are_still_allowed(app_repo_with_worktree, tmp_path) -> None:
    """リポジトリの外（スクラッチ領域等）は対象外のまま。過剰にブロックしない。"""
    _main, worktree = app_repo_with_worktree
    outside = tmp_path / "scratch.txt"
    assert _guard(worktree, "Write", {"file_path": str(outside), "content": "x"}) == 0


def test_own_feature_directory_is_still_writable(app_repo_with_worktree) -> None:
    """担当範囲は従来どおり通る。"""
    _main, worktree = app_repo_with_worktree
    target = worktree / "apps/demo/03-features/feat-a/src/ok.py"
    assert _guard(worktree, "Write", {"file_path": str(target), "content": "x"}) == 0


# --------------------------------------------------------------------------------------
# F-R4: 雛形生成の git 失敗を、traceback ではなく「エラー: … ＋ 次の一手」で返す
# --------------------------------------------------------------------------------------

def _scaffold_repo_without_git_identity(tmp_path: pathlib.Path, monkeypatch) -> pathlib.Path:
    """`new_feature_scaffold.py` が走る条件は満たすが、git の identity が無いリポジトリ。

    identity を持たせずに seed コミットを作るため、永続しない `-c` 指定で 1 回だけ名乗る。
    global / system の設定を読み込まないよう空ファイルへ向ける（実行環境の git 設定に
    結果が左右されないようにする）。
    """
    import shutil
    import subprocess

    empty_config = tmp_path / "empty-gitconfig"
    empty_config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_config))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(empty_config))
    for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.delenv(var, raising=False)

    root = tmp_path / "repo"
    (root / "apps" / "demo" / "00-requirements").mkdir(parents=True)
    (root / "apps" / "demo" / "01-foundation").mkdir(parents=True)
    (root / "apps" / "demo" / "02-design").mkdir(parents=True)
    harness_root = pathlib.Path(__file__).resolve().parents[1]
    shutil.copytree(harness_root / "templates", root / "harness" / "templates")

    (root / "apps" / "demo" / "00-requirements" / "requirements.machine.yaml").write_text(
        "version: 1\n", encoding="utf-8"
    )
    (root / "apps" / "demo" / "01-foundation" / "shared-kernel.yaml").write_text(
        "required_skills: []\n", encoding="utf-8"
    )
    (root / "apps" / "demo" / "02-design" / "architecture.machine.yaml").write_text(
        'status: APPROVED\napproved_by: "人間"\napproved_at: "2026-08-24T00:00:00Z"\n'
        'features:\n  - id: sample\n    name: "サンプル"\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
         "commit", "-q", "-m", "seed"],
        cwd=root, check=True,
    )
    return root


def test_run_git_reports_the_reason_instead_of_raising(tmp_path) -> None:
    """`check=True` の traceback は「ハーネスのバグ」に見え、本当の原因に到達できない。"""
    import subprocess

    import new_feature_scaffold

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    message = new_feature_scaffold.run_git(
        ["checkout", "no-such-branch"], root, "存在しないブランチへの切り替え", hint="  次の一手"
    )
    assert message is not None
    assert message.startswith("エラー: ")
    assert "  git: " in message
    assert message.endswith("  次の一手")


def test_run_git_returns_none_on_success(tmp_path) -> None:
    import subprocess

    import new_feature_scaffold

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    assert new_feature_scaffold.run_git(["status", "--porcelain"], root, "状態の確認") is None


def test_scaffold_without_git_identity_fails_cleanly(tmp_path, monkeypatch, capsys) -> None:
    """git identity 未設定でも traceback を出さず、`エラー: ` と設定コマンドを返すこと。"""
    import new_feature_scaffold

    root = _scaffold_repo_without_git_identity(tmp_path, monkeypatch)
    monkeypatch.chdir(root)

    assert new_feature_scaffold.main(["new_feature_scaffold.py", "demo", "sample"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("エラー: "), err
    assert "Traceback" not in err
    assert "user.email" in err  # 環境側の原因と、その直し方に到達できる
