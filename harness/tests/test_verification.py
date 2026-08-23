"""検証コマンドの宣言解決・JUnit XML 解析・受領書の妥当性判定（改善提案②③ / Rule 10）。

ハーネスがアプリの技術スタックを知らないまま「テストを実際に走らせて通したこと」を強制できる、
という主張の中核なので、宣言の解決規則と受領書の判定条件を網羅的に固定する。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

import path_utils

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import junit_utils  # noqa: E402
import run_verification  # noqa: E402

HEAD = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"


def receipt(**slots) -> dict:
    base = {"commit": HEAD}
    base.update(slots)
    return base


def ok(**extra) -> dict:
    entry = {"exit_code": 0, "at": "2026-08-21T10:00:00Z"}
    entry.update(extra)
    return entry


# --------------------------------------------------------------------------------------
# ② 宣言の解決（shared-kernel = 全機能共通、contract = 機能個別の上書き）
# --------------------------------------------------------------------------------------

SHARED = 'verification:\n  test_command: "pytest -q"\n  lint_command: "ruff check ."\n'


def test_declaration_comes_from_shared_kernel() -> None:
    declaration = path_utils.merge_verification_declaration(SHARED, "")
    assert declaration["test_command"] == "pytest -q"
    assert declaration["lint_command"] == "ruff check ."


def test_contract_overrides_per_key() -> None:
    contract = 'verification:\n  test_command: "pytest -q tests/"\n'
    declaration = path_utils.merge_verification_declaration(SHARED, contract)
    assert declaration["test_command"] == "pytest -q tests/"
    assert declaration["lint_command"] == "ruff check ."  # 上書きされていないキーは残る


def test_empty_values_are_not_declarations() -> None:
    declaration = path_utils.merge_verification_declaration(
        'verification:\n  test_command: ""\n  build_command: null\n', ""
    )
    assert declaration == {}


def test_missing_block_yields_empty_declaration() -> None:
    assert path_utils.merge_verification_declaration("app_id: x\n", "") == {}
    assert path_utils.merge_verification_declaration("", "") == {}


# --------------------------------------------------------------------------------------
# ② 受領書の判定
# --------------------------------------------------------------------------------------

def test_receipt_accepted_when_everything_passes() -> None:
    declaration = {"test_command": "pytest", "lint_command": "ruff check ."}
    assert path_utils.validate_verification_receipt(
        declaration, receipt(test=ok(), lint=ok()), HEAD
    ) is None


def test_test_command_must_be_declared() -> None:
    reason = path_utils.validate_verification_receipt({}, receipt(test=ok()), HEAD)
    assert reason is not None and "test_command" in reason


def test_missing_receipt_is_rejected() -> None:
    reason = path_utils.validate_verification_receipt({"test_command": "pytest"}, None, HEAD)
    assert reason is not None and "verification_receipt" in reason


@pytest.mark.parametrize(
    "receipt_commit",
    ["b" * 40, "", None, "abc"],  # 別コミット / 空 / 未記録 / 短すぎる
)
def test_commit_must_match_head(receipt_commit) -> None:
    reason = path_utils.validate_verification_receipt(
        {"test_command": "pytest"}, {"commit": receipt_commit, "test": ok()}, HEAD
    )
    assert reason is not None and "HEAD" in reason


def test_short_commit_prefix_matches() -> None:
    """受領書に短縮 SHA が入っていても同一コミットなら通す。"""
    assert path_utils.commits_match(HEAD[:7], HEAD) is True
    assert path_utils.commits_match(HEAD, HEAD[:7]) is True
    assert path_utils.commits_match("b" * 7, HEAD) is False


def test_declared_command_without_record_is_rejected() -> None:
    reason = path_utils.validate_verification_receipt(
        {"test_command": "pytest", "build_command": "make"}, receipt(test=ok()), HEAD
    )
    assert reason is not None and "build" in reason


def test_nonzero_exit_code_is_rejected() -> None:
    reason = path_utils.validate_verification_receipt(
        {"test_command": "pytest"}, receipt(test=ok(exit_code=1)), HEAD
    )
    assert reason is not None and "失敗" in reason


def test_undeclared_command_is_not_required() -> None:
    """宣言していないコマンドの記録が無くても構わない（ハーネスは何も規定しない）。"""
    assert path_utils.validate_verification_receipt(
        {"test_command": "pytest"}, receipt(test=ok()), HEAD
    ) is None


# --------------------------------------------------------------------------------------
# ③ JUnit XML の集計値による判定（空振り・失敗・スキップ率）
# --------------------------------------------------------------------------------------

DECL_WITH_JUNIT = {"test_command": "pytest", "junit_xml": ".verify/junit.xml"}


def test_zero_tests_is_rejected_as_empty_run() -> None:
    reason = path_utils.validate_verification_receipt(
        DECL_WITH_JUNIT, receipt(test=ok(tests=0, skipped=0)), HEAD
    )
    assert reason is not None and "1 件も実行されていません" in reason


def test_missing_test_count_is_rejected_when_junit_declared() -> None:
    reason = path_utils.validate_verification_receipt(DECL_WITH_JUNIT, receipt(test=ok()), HEAD)
    assert reason is not None and "テスト件数" in reason


def test_failures_are_rejected() -> None:
    reason = path_utils.validate_verification_receipt(
        DECL_WITH_JUNIT, receipt(test=ok(tests=10, failures=1)), HEAD
    )
    assert reason is not None and "失敗しているテスト" in reason


def test_skip_ratio_over_the_threshold_is_rejected() -> None:
    reason = path_utils.validate_verification_receipt(
        DECL_WITH_JUNIT, receipt(test=ok(tests=10, skipped=3)), HEAD
    )
    assert reason is not None and "スキップ" in reason


def test_skip_ratio_within_the_threshold_is_accepted() -> None:
    assert path_utils.validate_verification_receipt(
        DECL_WITH_JUNIT, receipt(test=ok(tests=10, skipped=2)), HEAD
    ) is None


def test_skip_ratio_threshold_is_overridable() -> None:
    declaration = dict(DECL_WITH_JUNIT, max_skip_ratio=0.5)
    assert path_utils.validate_verification_receipt(
        declaration, receipt(test=ok(tests=10, skipped=4)), HEAD
    ) is None


def test_junit_checks_are_skipped_when_not_declared() -> None:
    """JUnit XML を出せない技術を選んだ場合は、終了コードによるゲートだけが効く（段階的 degrade）。"""
    assert path_utils.validate_verification_receipt(
        {"test_command": "go test ./..."}, receipt(test=ok()), HEAD
    ) is None


# --------------------------------------------------------------------------------------
# ③ JUnit XML の解析（クロススタック標準）
# --------------------------------------------------------------------------------------

PYTEST_STYLE = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="1" tests="4" time="0.1">
    <testcase classname="tests.test_a" name="test_ok" file="tests/test_a.py" time="0.01"/>
    <testcase classname="tests.test_a" name="test_bad" file="tests/test_a.py">
      <failure message="boom">trace</failure>
    </testcase>
    <testcase classname="tests.test_a" name="test_skipped" file="tests/test_a.py">
      <skipped message="later"/>
    </testcase>
    <testcase classname="tests.test_b" name="test_ok2" file="tests/test_b.py"/>
  </testsuite>
</testsuites>
"""

SINGLE_SUITE = """<testsuite name="jest" tests="2" failures="0" errors="0" skipped="0">
  <testcase classname="Button" name="renders"/>
  <testcase classname="Button" name="handles clicks"/>
</testsuite>
"""

NO_ATTRIBUTES = """<testsuites>
  <testsuite name="custom">
    <testcase classname="X" name="a"/>
    <testcase classname="X" name="b"><error message="e"/></testcase>
  </testsuite>
</testsuites>
"""


def write(tmp_path: pathlib.Path, text: str) -> pathlib.Path:
    p = tmp_path / "junit.xml"
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_testsuites_root(tmp_path) -> None:
    summary = junit_utils.parse_junit_xml(write(tmp_path, PYTEST_STYLE))
    assert (summary["tests"], summary["failures"], summary["errors"], summary["skipped"]) == (4, 1, 0, 1)
    assert len(summary["testcases"]) == 4
    assert summary["testcases"][0]["status"] == junit_utils.PASSED
    assert summary["testcases"][1]["status"] == junit_utils.FAILED
    assert summary["testcases"][2]["status"] == junit_utils.SKIPPED


def test_parse_testsuite_root(tmp_path) -> None:
    summary = junit_utils.parse_junit_xml(write(tmp_path, SINGLE_SUITE))
    assert summary["tests"] == 2 and summary["failures"] == 0


def test_counts_are_recomputed_when_attributes_are_missing(tmp_path) -> None:
    summary = junit_utils.parse_junit_xml(write(tmp_path, NO_ATTRIBUTES))
    assert summary["tests"] == 2 and summary["errors"] == 1


@pytest.mark.parametrize(
    "identifier",
    [
        "test_ok",
        "tests.test_a.test_ok",
        "tests.test_a::test_ok",
        "tests/test_a.py::test_ok",
    ],
)
def test_testcase_identifier_forms(tmp_path, identifier: str) -> None:
    """テスト ID の書き方は言語・レポータごとに違うため、代表的な形をすべて受け付ける。"""
    summary = junit_utils.parse_junit_xml(write(tmp_path, PYTEST_STYLE))
    matched = junit_utils.find_matching_testcases(summary["testcases"], identifier)
    assert [c["name"] for c in matched] == ["test_ok"]


def test_unknown_identifier_matches_nothing(tmp_path) -> None:
    summary = junit_utils.parse_junit_xml(write(tmp_path, PYTEST_STYLE))
    assert junit_utils.find_matching_testcases(summary["testcases"], "test_nope") == []


# pytest の `--junitxml` は `file` 属性を出さず classname にドット区切りのモジュールパスを入れる。
# 人間が契約に書くのは pytest の node id（`tests/test_todo.py::test_x`）なので、ここが噛み合わないと
# トレーサビリティが実運用で使えない（実地の通し確認で発見）。
PYTEST_REAL_OUTPUT = """<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests">\
<testsuite name="pytest" errors="0" failures="0" skipped="0" tests="2">\
<testcase classname="tests.test_todo" name="test_empty_title" time="0.0" />\
<testcase classname="tests.test_todo.TestNested" name="test_inner" time="0.0" />\
</testsuite></testsuites>
"""


@pytest.mark.parametrize(
    "identifier,expected",
    [
        ("tests/test_todo.py::test_empty_title", "test_empty_title"),
        ("tests.test_todo::test_empty_title", "test_empty_title"),
        ("test_empty_title", "test_empty_title"),
        ("tests/test_todo.py::TestNested::test_inner", "test_inner"),
    ],
)
def test_pytest_node_id_forms_match(tmp_path, identifier: str, expected: str) -> None:
    summary = junit_utils.parse_junit_xml(write(tmp_path, PYTEST_REAL_OUTPUT))
    matched = junit_utils.find_matching_testcases(summary["testcases"], identifier)
    assert [c["name"] for c in matched] == [expected]


# F-051: `@pytest.mark.parametrize` は JUnit XML 上の name に `test_x[None]` のように末尾の
# `[...]` を付ける。契約側はパラメータなしの名前（`test_x`）で書くのが通例なので、
# 素の名前でも一致しなければならない（実地の通しで「見つかりません」と誤判定された）。
PYTEST_PARAMETRIZE_OUTPUT = """<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests">\
<testsuite name="pytest" errors="0" failures="0" skipped="0" tests="2">\
<testcase classname="tests.test_todo" name="test_priority[None]" time="0.0" />\
<testcase classname="tests.test_todo" name="test_priority[high]" time="0.0" />\
</testsuite></testsuites>
"""


@pytest.mark.parametrize(
    "identifier",
    [
        "test_priority",
        "tests/test_todo.py::test_priority",
        "tests.test_todo::test_priority",
    ],
)
def test_parametrized_testcase_matches_unparametrized_identifier(tmp_path, identifier: str) -> None:
    summary = junit_utils.parse_junit_xml(write(tmp_path, PYTEST_PARAMETRIZE_OUTPUT))
    matched = junit_utils.find_matching_testcases(summary["testcases"], identifier)
    assert {c["name"] for c in matched} == {"test_priority[None]", "test_priority[high]"}


def test_parametrized_testcase_still_matches_its_own_full_name(tmp_path) -> None:
    summary = junit_utils.parse_junit_xml(write(tmp_path, PYTEST_PARAMETRIZE_OUTPUT))
    matched = junit_utils.find_matching_testcases(summary["testcases"], "test_priority[None]")
    assert [c["name"] for c in matched] == ["test_priority[None]"]


# --------------------------------------------------------------------------------------
# F-023: 設計フェーズで `verification:` 宣言を試せる入口（--check-only）
# --------------------------------------------------------------------------------------

def _design_phase_app(tmp_path, shared_kernel: str) -> pathlib.Path:
    """worktree を作る前（03-features/ がまだ無い）状態のアプリを組み立てる。"""
    app = tmp_path / "apps" / "demo"
    (app / "01-foundation").mkdir(parents=True)
    (app / "01-foundation" / "shared-kernel.yaml").write_text(shared_kernel, encoding="utf-8")
    (app / "02-design" / "features").mkdir(parents=True)
    (app / "02-design" / "architecture.machine.yaml").write_text(
        'app_id: "demo"\nfeatures:\n  - id: "alpha"\n  - id: "beta"\n', encoding="utf-8"
    )
    return tmp_path


def test_check_only_passes_without_a_worktree(tmp_path, capsys) -> None:
    """F-023: --dry-run は status.yaml を要求するため、宣言する場所では使えなかった。"""
    root = _design_phase_app(tmp_path, 'verification:\n  test_command: "pytest -q"\n')
    assert run_verification.check_only(root, "demo", None) == 0
    assert "alpha" in capsys.readouterr().out


def test_check_only_detects_a_missing_test_command(tmp_path, capsys) -> None:
    root = _design_phase_app(tmp_path, 'verification:\n  lint_command: "ruff check ."\n')
    assert run_verification.check_only(root, "demo", None) == 1
    assert "test_command" in capsys.readouterr().err


def test_check_only_detects_a_missing_declaration(tmp_path, capsys) -> None:
    root = _design_phase_app(tmp_path, 'app_id: "demo"\n')
    assert run_verification.check_only(root, "demo", None) == 1
    assert "宣言されていません" in capsys.readouterr().err


def test_check_only_uses_the_design_draft_contract(tmp_path, capsys) -> None:
    """機能個別の上書きは、worktree 前でも設計時ドラフトから解決できる。"""
    root = _design_phase_app(tmp_path, 'verification:\n  test_command: "pytest -q"\n')
    (root / "apps/demo/02-design/features/alpha.contract.yaml").write_text(
        'feature_id: "alpha"\nverification:\n  test_command: "go test ./..."\n', encoding="utf-8"
    )
    assert run_verification.check_only(root, "demo", "alpha") == 0
    assert "go test ./..." in capsys.readouterr().out
