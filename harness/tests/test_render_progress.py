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
