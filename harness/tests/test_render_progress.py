"""`render_progress.py` が PROGRESS.md / STATE.machine.yaml に出す要約の検証。

検証受領書（14節）と独立レビュー（16節）の結果は、最終的に人間が `PROGRESS.md` で
確認できることを担保としているため、その要約が壊れていないことを固定する。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import render_progress  # noqa: E402

HARNESS_ROOT = pathlib.Path(__file__).resolve().parent.parent


def receipt(**slots) -> dict:
    return {"verification_receipt": {"commit": "a1b2c3d4e5f6" + "0" * 28, **slots}}


def test_no_receipt_is_reported_as_not_run() -> None:
    assert render_progress._verification_summary({}) == "未実行"
    assert render_progress._verification_summary({"verification_receipt": {}}) == "未実行"


def test_passing_receipt_shows_counts_and_commit() -> None:
    summary = render_progress._verification_summary(
        receipt(test={"exit_code": 0, "tests": 42, "skipped": 0})
    )
    assert summary == "OK 42件 @a1b2c3d"


def test_skipped_tests_are_surfaced() -> None:
    summary = render_progress._verification_summary(
        receipt(test={"exit_code": 0, "tests": 10, "skipped": 2})
    )
    assert "skip 2" in summary


def test_failing_slots_are_named() -> None:
    summary = render_progress._verification_summary(
        receipt(test={"exit_code": 0, "tests": 1}, lint={"exit_code": 1})
    )
    assert summary == "失敗 (lint)"


def test_receipt_without_junit_counts() -> None:
    assert render_progress._verification_summary(receipt(test={"exit_code": 0})) == "OK @a1b2c3d"


@pytest.mark.parametrize(
    "review,expected",
    [
        ({}, "未実施"),
        ({"verdict": "GO", "rounds": 1}, "GO（1R）"),
        ({"verdict": "NO-GO", "rounds": 2, "blockers": 3}, "NO-GO（2R / Blocker 3）"),
        ({"verdict": "ESCALATED", "rounds": 3}, "ESCALATED（3R）"),
    ],
)
def test_review_summary(review, expected) -> None:
    assert render_progress._review_summary({"review": review} if review else {}) == expected


# --------------------------------------------------------------------------------------
# 生成される Markdown の体裁（F-013）
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("statuses", [[], [{"feature_id": "a", "state": "IN_PROGRESS"}]])
def test_every_heading_is_preceded_by_a_blank_line(tmp_path, statuses) -> None:
    """F-013: 機能が 1 件も無いとき、見出しの直前の空行が抜けていた。"""
    render_progress._write_progress_md(tmp_path, "demo", "APPROVED", "APPROVED", "SUPERVISED", statuses)
    lines = (tmp_path / "PROGRESS.md").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if i and line.startswith("#"):
            assert lines[i - 1] == "", f"{line!r} の直前に空行がありません"


# --------------------------------------------------------------------------------------
# main / worktree の優先順位（F-056）
# --------------------------------------------------------------------------------------

def _write_status(path: pathlib.Path, state: str, last_updated_at: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"feature_id: demo\nstate: {state}\nlast_updated_at: '{last_updated_at}'\n",
        encoding="utf-8",
    )


def test_worktree_wins_when_worktree_is_newer(tmp_path) -> None:
    """実装中は main 側にまだ状態が無い/古いので、worktree 側（作業中の最新）を採用する。"""
    app_dir = tmp_path / "demo-app"
    _write_status(app_dir / "03-features" / "demo" / "status.yaml", "IMPLEMENTED", "2026-08-22T09:00:00Z")
    _write_status(
        app_dir / ".worktrees" / "demo" / "apps" / "demo-app" / "03-features" / "demo" / "status.yaml",
        "TESTED",
        "2026-08-22T11:00:00Z",
    )
    paths = render_progress._collect_status_paths(app_dir)
    assert len(paths) == 1
    assert render_progress._common.load_yaml(paths[0])["state"] == "TESTED"


def test_main_wins_when_main_is_newer_after_integration(tmp_path) -> None:
    """F-056: 統合直後、main 側は INTEGRATED に進んでいるのに worktree 側がまだ削除されておらず
    古い TESTED のままだと、無条件の worktree 優先では統合完了が反映されなくなっていた。"""
    app_dir = tmp_path / "demo-app"
    _write_status(app_dir / "03-features" / "demo" / "status.yaml", "INTEGRATED", "2026-08-22T12:00:00Z")
    _write_status(
        app_dir / ".worktrees" / "demo" / "apps" / "demo-app" / "03-features" / "demo" / "status.yaml",
        "TESTED",
        "2026-08-22T11:00:00Z",
    )
    paths = render_progress._collect_status_paths(app_dir)
    assert len(paths) == 1
    assert render_progress._common.load_yaml(paths[0])["state"] == "INTEGRATED"


# --------------------------------------------------------------------------------------
# 非エンジニア向け HTML 面（T-030 / F-A8）
#
# 新しい skill は増やさず、既にある決定論的レンダラの出力形式を 1 つ足す（NG-3）。
# **AI に作文させない**ことが要点なので、入力が status.yaml / contract.yaml / VERSION /
# 強制レイヤの診断だけであることと、同じ入力から同じ出力が出ることを固定する。
# --------------------------------------------------------------------------------------

HTML_STATUS_A = """feature_id: "feat-a"
app_id: "demo"
state: INTEGRATED
blockers: []
last_updated_at: "2026-08-24T00:00:00Z"
review:
  verdict: GO
  rounds: 2
  blockers: 0
verification_receipt:
  commit: "0123456789abcdef0123456789abcdef01234567"
  test:
    exit_code: 0
    tests: 42
    skipped: 1
"""

HTML_STATUS_B = """feature_id: "feat-b"
app_id: "demo"
state: BLOCKED
blockers: ["依存する外部 API の仕様が未確定"]
last_updated_at: "2026-08-24T01:00:00Z"
"""

HTML_CONTRACT_A = """feature_id: "feat-a"
open_issues:
- id: "OI-1"
  summary: "エラー時の終了コードが契約に書かれていない"
  found_at: "2026-08-24T00:00:00Z"
  found_by: "feature-builder"
"""


def _html_app(tmp_path):
    """テンプレートを読ませるため、本物の harness を指す一時リポジトリを作る。"""
    import os

    root = tmp_path / "repo"
    app_dir = root / "apps" / "demo"
    (app_dir / "03-features" / "feat-a").mkdir(parents=True)
    (app_dir / "03-features" / "feat-b").mkdir(parents=True)
    (app_dir / "03-features" / "feat-a" / "status.yaml").write_text(HTML_STATUS_A, encoding="utf-8")
    (app_dir / "03-features" / "feat-a" / "contract.yaml").write_text(HTML_CONTRACT_A, encoding="utf-8")
    (app_dir / "03-features" / "feat-b" / "status.yaml").write_text(HTML_STATUS_B, encoding="utf-8")
    os.symlink(HARNESS_ROOT, root / "harness")
    return app_dir


def _render_html(tmp_path) -> str:
    app_dir = _html_app(tmp_path)
    render_progress.render_app(app_dir, as_html=True)
    return (app_dir / "PROGRESS.html").read_text(encoding="utf-8")


def test_html_is_generated_as_a_single_self_contained_file(tmp_path) -> None:
    page = _render_html(tmp_path)
    assert page.startswith("<!doctype html>")
    assert 'src="http' not in page and 'href="http' not in page  # 外部リソースに依存しない
    assert "<style>" in page  # CSS はインライン


def test_html_shows_each_feature_with_its_state(tmp_path) -> None:
    page = _render_html(tmp_path)
    assert "feat-a" in page and "統合済み" in page
    assert "feat-b" in page and "ブロック中" in page
    assert "依存する外部 API の仕様が未確定" in page


def test_html_shows_the_verification_receipt_result(tmp_path) -> None:
    """受領書の有無と結果は、非エンジニアが見るべき最重要の情報。"""
    page = _render_html(tmp_path)
    assert "OK 42件" in page and "0123456" in page


def test_html_shows_the_gate_reviewer_verdict(tmp_path) -> None:
    assert "GO（2R）" in _render_html(tmp_path)


def test_html_shows_unresolved_open_issues(tmp_path) -> None:
    page = _render_html(tmp_path)
    assert "OI-1" in page and "エラー時の終了コードが契約に書かれていない" in page


def test_html_shows_the_enforcement_layer_state(tmp_path) -> None:
    assert "強制レイヤ" in _render_html(tmp_path)


def test_html_has_no_markdown_bold_left_over(tmp_path) -> None:
    assert "**" not in _render_html(tmp_path)


def test_html_escapes_values_from_yaml(tmp_path) -> None:
    """`status.yaml` の内容がそのまま HTML に埋まると、壊れた表示や注入になる。"""
    app_dir = _html_app(tmp_path)
    (app_dir / "03-features" / "feat-b" / "status.yaml").write_text(
        'feature_id: "feat-b"\napp_id: "demo"\nstate: BLOCKED\n'
        'blockers: ["<script>alert(1)</script>"]\n',
        encoding="utf-8",
    )
    render_progress.render_app(app_dir, as_html=True)
    page = (app_dir / "PROGRESS.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_html_is_deterministic_for_the_same_input(tmp_path) -> None:
    """同じ入力からは同じ出力（タイムスタンプ以外）。AI が作文していないことの担保。"""
    app_dir = _html_app(tmp_path)
    render_progress.render_app(app_dir, as_html=True)
    first = (app_dir / "PROGRESS.html").read_text(encoding="utf-8")
    render_progress.render_app(app_dir, as_html=True)
    second = (app_dir / "PROGRESS.html").read_text(encoding="utf-8")
    assert first == second


def test_html_is_not_generated_without_the_flag(tmp_path) -> None:
    app_dir = _html_app(tmp_path)
    render_progress.render_app(app_dir)
    assert not (app_dir / "PROGRESS.html").exists()


def test_the_html_output_is_gitignored() -> None:
    """派生物は判断の根拠にしない（生成物をコミットさせない）。"""
    gitignore = (HARNESS_ROOT.parent / ".gitignore").read_text(encoding="utf-8")
    assert "apps/*/PROGRESS.html" in gitignore


def test_no_new_skill_or_subagent_was_added() -> None:
    """NG-3。HTML 面のために skill / subagent を増やしていないこと。"""
    root = HARNESS_ROOT.parent
    assert len(list((root / ".claude" / "agents").glob("*.md"))) == 5
    assert len(list((root / ".claude" / "skills").glob("*/SKILL.md"))) == 4
