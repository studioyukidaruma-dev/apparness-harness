"""版管理（CI 項目 Q・T-021 / F-A7）の検証。

VERSION も CHANGELOG も無いと、導入されたハーネスの版を機械的に特定できない。
版が分からなければ「どの版で起きた不具合か」が言えず、報告と改修の対応が取れない。

`VERSION` を置くだけでは腐るので、**ハーネス本体を触ったコミットでは CHANGELOG の
Unreleased セクションが更新されていること**まで機械的に要求する。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import ci_check  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

CHANGELOG_WITH_ENTRY = """# CHANGELOG

## [Unreleased]

### Added

- 何かを足した

## [1.0.0] - 2026-08-23

- 初版
"""

CHANGELOG_EMPTY_UNRELEASED = """# CHANGELOG

## [Unreleased]

## [1.0.0] - 2026-08-23

- 初版
"""


def build(tmp_path: pathlib.Path, version: str | None = "1.0.0", changelog: str | None = CHANGELOG_WITH_ENTRY):
    if version is not None:
        (tmp_path / "VERSION").write_text(version + "\n", encoding="utf-8")
    if changelog is not None:
        (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return tmp_path


HARNESS_CHANGE = [("M", "harness/hooks/pre_tool_use_guard.py")]
APP_CHANGE = [("M", "apps/demo/03-features/feat-a/src/x.py")]


# --------------------------------------------------------------------------------------
# VERSION
# --------------------------------------------------------------------------------------

def test_missing_version_file_is_rejected(tmp_path) -> None:
    violations = ci_check.check_versioning([], build(tmp_path, version=None))
    assert any("VERSION" in v for v in violations)


@pytest.mark.parametrize("value", ["v1.0.0", "1.0", "latest", "1.0.0-rc1"])
def test_non_semver_version_is_rejected(tmp_path, value: str) -> None:
    violations = ci_check.check_versioning([], build(tmp_path, version=value))
    assert any("VERSION" in v for v in violations)


def test_a_valid_version_passes(tmp_path) -> None:
    assert ci_check.check_versioning([], build(tmp_path)) == []


# --------------------------------------------------------------------------------------
# CHANGELOG の追随
# --------------------------------------------------------------------------------------

def test_missing_changelog_is_rejected(tmp_path) -> None:
    violations = ci_check.check_versioning([], build(tmp_path, changelog=None))
    assert any("CHANGELOG.md" in v for v in violations)


def test_harness_change_without_a_changelog_entry_is_rejected(tmp_path) -> None:
    """ハーネス本体を触ったのに CHANGELOG を更新していないコミットを拒否する。"""
    violations = ci_check.check_versioning(HARNESS_CHANGE, build(tmp_path))
    assert len(violations) == 1 and "CHANGELOG.md" in violations[0]


def test_harness_change_with_a_changelog_entry_passes(tmp_path) -> None:
    changed = HARNESS_CHANGE + [("M", "CHANGELOG.md")]
    assert ci_check.check_versioning(changed, build(tmp_path)) == []


def test_an_empty_unreleased_section_is_rejected(tmp_path) -> None:
    """見出しだけ足しても、何が変わったのかは導入側から分からない。"""
    changed = HARNESS_CHANGE + [("M", "CHANGELOG.md")]
    root = build(tmp_path, changelog=CHANGELOG_EMPTY_UNRELEASED)
    violations = ci_check.check_versioning(changed, root)
    assert len(violations) == 1 and "Unreleased" in violations[0]


def test_app_only_changes_do_not_require_a_changelog_entry(tmp_path) -> None:
    """アプリ側の作業まで CHANGELOG を要求すると、毎コミットが二度手間になる。"""
    assert ci_check.check_versioning(APP_CHANGE, build(tmp_path)) == []


def test_the_personal_local_settings_do_not_require_a_changelog_entry(tmp_path) -> None:
    changed = [("M", ".claude/settings.local.json")]
    assert ci_check.check_versioning(changed, build(tmp_path)) == []


@pytest.mark.parametrize(
    "path",
    ["harness/CONVENTIONS.md", ".claude/agents/feature-builder.md", ".github/workflows/x.yml"],
)
def test_all_harness_prefixes_require_a_changelog_entry(tmp_path, path: str) -> None:
    violations = ci_check.check_versioning([("M", path)], build(tmp_path))
    assert len(violations) == 1 and "CHANGELOG.md" in violations[0]


# --------------------------------------------------------------------------------------
# Unreleased セクションの読み取り
# --------------------------------------------------------------------------------------

def test_unreleased_entries_ignores_the_next_section() -> None:
    entries = ci_check.unreleased_entries(CHANGELOG_WITH_ENTRY)
    assert entries == ["- 何かを足した"]


def test_unreleased_entries_is_empty_without_the_section() -> None:
    assert ci_check.unreleased_entries("# CHANGELOG\n\n## [1.0.0]\n\n- 初版\n") == []


# --------------------------------------------------------------------------------------
# 実リポジトリ
# --------------------------------------------------------------------------------------

def test_this_repository_has_a_version_and_a_changelog() -> None:
    assert ci_check.read_harness_version(REPO_ROOT) is not None
    assert (REPO_ROOT / "CHANGELOG.md").exists()


def test_the_dashboard_shows_the_harness_version() -> None:
    """`PROGRESS.md` から、そのアプリを作ったハーネスの版が辿れること。"""
    import render_progress

    line = render_progress._harness_version_line(REPO_ROOT)
    assert line.startswith("- ハーネス版: **v")
