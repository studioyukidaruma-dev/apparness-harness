"""CONVENTIONS.md 凍結（ci_check 項目 O）の検証。

ユーザーの明示的な許可を得て 2026-08-23 に凍結した（ROADMAP⑩ 3本完走が条件）。
機械的な強制は「節の新設を拒否する」ことだけ——既存の節の中身を直すこと・節を削ることは妨げない
（「新しい節を立てるべきか」という最も主観の入る判断そのものを消すのが目的のため）。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import ci_check  # noqa: E402


def _write_conventions(tmp_path: pathlib.Path, section_count: int) -> pathlib.Path:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir()
    body = "\n".join(f"## {i}. 節タイトル\n本文。" for i in range(1, section_count + 1))
    (harness_dir / "CONVENTIONS.md").write_text(body, encoding="utf-8")
    return tmp_path


def test_exactly_frozen_count_passes(tmp_path):
    root = _write_conventions(tmp_path, ci_check.CONVENTIONS_FROZEN_SECTION_COUNT)
    assert ci_check.check_conventions_frozen_section_count(root) == []


def test_fewer_than_frozen_count_passes(tmp_path):
    """節を削る・まとめることは凍結が禁じる対象ではない。"""
    root = _write_conventions(tmp_path, ci_check.CONVENTIONS_FROZEN_SECTION_COUNT - 2)
    assert ci_check.check_conventions_frozen_section_count(root) == []


def test_new_section_is_rejected(tmp_path):
    root = _write_conventions(tmp_path, ci_check.CONVENTIONS_FROZEN_SECTION_COUNT + 1)
    violations = ci_check.check_conventions_frozen_section_count(root)
    assert len(violations) == 1
    assert "16" in violations[0]


def test_multiple_new_sections_are_all_named(tmp_path):
    root = _write_conventions(tmp_path, ci_check.CONVENTIONS_FROZEN_SECTION_COUNT + 3)
    violations = ci_check.check_conventions_frozen_section_count(root)
    assert len(violations) == 1
    assert "16" in violations[0] and "17" in violations[0] and "18" in violations[0]


def test_missing_conventions_file_is_not_a_violation(tmp_path):
    (tmp_path / "harness").mkdir()
    assert ci_check.check_conventions_frozen_section_count(tmp_path) == []


def test_the_actual_repository_conventions_is_at_the_frozen_count():
    """現在のリポジトリの CONVENTIONS.md が実際に15節ちょうどであることの確認
    （空振りでないことの確認。凍結後にこの数を変える場合はユーザーの明示的な許可が要る）。
    """
    repo_root = pathlib.Path(__file__).resolve().parent.parent.parent
    assert ci_check.check_conventions_frozen_section_count(repo_root) == []
