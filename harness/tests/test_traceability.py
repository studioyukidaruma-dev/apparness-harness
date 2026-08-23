"""要件 → 機能 → テスト のトレーサビリティ判定（改善提案⑤ / ci_check 項目 K）と、
受領書側のテスト識別子突合の検証。

要件 ID（`^FR-[0-9]+$`）は既にスキーマで固定されているため、この判定は追加の技術選定なしに
スタック非依存で成立する。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

import path_utils

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import check_traceability  # noqa: E402
import junit_utils  # noqa: E402
import run_verification  # noqa: E402


def requirements(*frs) -> dict:
    return {"functional_requirements": list(frs)}


def fr(fid: str, priority: str = "MUST") -> dict:
    return {"id": fid, "title": f"{fid} の要件", "priority": priority, "acceptance_criteria": ["ac"]}


def architecture(**features) -> dict:
    return {
        "features": [
            {"id": fid, "covers_requirements": covers} for fid, covers in features.items()
        ]
    }


def contract(*fr_ids, structured: bool = True) -> dict:
    if not structured:
        return {"test_strategy": "自由記述"}
    return {
        "test_strategy": {
            "approach": "単体テスト",
            "coverage": [
                {"requirement": fid, "acceptance_criterion": "ac", "test_ids": [f"test_{fid}"]}
                for fid in fr_ids
            ],
        }
    }


# --------------------------------------------------------------------------------------
# 要件の取りこぼし
# --------------------------------------------------------------------------------------

def test_fully_covered_passes() -> None:
    violations = check_traceability.check_traceability(
        requirements(fr("FR-1")), architecture(alpha=["FR-1"]), {"alpha": contract("FR-1")}
    )
    assert violations == []


def test_uncovered_must_requirement_is_detected() -> None:
    violations = check_traceability.check_traceability(
        requirements(fr("FR-1"), fr("FR-2")), architecture(alpha=["FR-1"]), {"alpha": contract("FR-1")}
    )
    assert len(violations) == 1 and "FR-2" in violations[0] and "取りこぼし" in violations[0]


@pytest.mark.parametrize("priority", ["SHOULD", "COULD"])
def test_uncovered_non_must_requirement_is_allowed(priority: str) -> None:
    violations = check_traceability.check_traceability(
        requirements(fr("FR-1"), fr("FR-2", priority)),
        architecture(alpha=["FR-1"]),
        {"alpha": contract("FR-1")},
    )
    assert violations == []


def test_unknown_requirement_id_is_detected() -> None:
    violations = check_traceability.check_traceability(
        requirements(fr("FR-1")), architecture(alpha=["FR-1", "FR-99"]), {"alpha": contract("FR-1")}
    )
    assert any("FR-99" in v and "存在しません" in v for v in violations)


def test_one_requirement_may_be_covered_by_several_features() -> None:
    violations = check_traceability.check_traceability(
        requirements(fr("FR-1")),
        architecture(alpha=["FR-1"], beta=["FR-1"]),
        {"alpha": contract("FR-1"), "beta": contract("FR-1")},
    )
    assert violations == []


# --------------------------------------------------------------------------------------
# 要件 → テストの対応づけ
# --------------------------------------------------------------------------------------

def test_requirement_without_a_matching_test_entry_is_detected() -> None:
    violations = check_traceability.check_traceability(
        requirements(fr("FR-1"), fr("FR-2")),
        architecture(alpha=["FR-1", "FR-2"]),
        {"alpha": contract("FR-1")},  # FR-2 に対応するテストが無い
    )
    assert len(violations) == 1 and "FR-2" in violations[0] and "coverage" in violations[0]


def test_unstructured_test_strategy_is_detected() -> None:
    violations = check_traceability.check_traceability(
        requirements(fr("FR-1")), architecture(alpha=["FR-1"]), {"alpha": contract(structured=False)}
    )
    assert violations and "構造化されていません" in violations[0]


def test_missing_contract_is_not_yet_judged() -> None:
    """scaffold 前（contract.yaml がまだ無い）の段階では判定しない。"""
    violations = check_traceability.check_traceability(
        requirements(fr("FR-1")), architecture(alpha=["FR-1"]), {}
    )
    assert violations == []


def test_no_requirements_means_nothing_to_check() -> None:
    assert check_traceability.check_traceability({}, architecture(alpha=["FR-1"]), {}) == []


# --------------------------------------------------------------------------------------
# 契約に書かれたテスト識別子の抽出
# --------------------------------------------------------------------------------------

CONTRACT_YAML = """feature_id: "alpha"
test_strategy:
  approach: "単体テスト"
  coverage:
  - requirement: "FR-1"
    acceptance_criterion: "空のタイトルは拒否される"
    test_ids:
    - "tests/test_todo.py::test_empty_title"
    - "tests/test_todo.py::test_blank_title"
  - requirement: "FR-2"
    acceptance_criterion: "一覧が取得できる"
    test_ids: ["tests/test_todo.py::test_list"]
"""


def test_extract_declared_test_ids() -> None:
    assert path_utils.extract_declared_test_ids(CONTRACT_YAML) == [
        "tests/test_todo.py::test_empty_title",
        "tests/test_todo.py::test_blank_title",
        "tests/test_todo.py::test_list",
    ]


def test_extract_declared_test_ids_without_strategy() -> None:
    assert path_utils.extract_declared_test_ids("feature_id: alpha\n") == []


# --------------------------------------------------------------------------------------
# JUnit XML との突合（run_verification.match_declared_tests）
# --------------------------------------------------------------------------------------

def cases(*specs) -> list[dict]:
    return [
        {"classname": "tests.test_todo", "name": name, "file": "tests/test_todo.py", "status": status}
        for name, status in specs
    ]


def test_all_declared_tests_present_and_passing() -> None:
    result = run_verification.match_declared_tests(
        ["tests/test_todo.py::test_a"], cases(("test_a", junit_utils.PASSED))
    )
    assert result == {"declared": 1, "matched": 1}


def test_missing_test_is_reported() -> None:
    result = run_verification.match_declared_tests(
        ["tests/test_todo.py::test_ghost"], cases(("test_a", junit_utils.PASSED))
    )
    assert result["missing"] == ["tests/test_todo.py::test_ghost"]


def test_failing_declared_test_is_reported() -> None:
    result = run_verification.match_declared_tests(
        ["tests/test_todo.py::test_a"], cases(("test_a", junit_utils.FAILED))
    )
    assert result["failed"] == ["tests/test_todo.py::test_a"]


def test_skipped_declared_test_counts_as_not_passing() -> None:
    result = run_verification.match_declared_tests(
        ["tests/test_todo.py::test_a"], cases(("test_a", junit_utils.SKIPPED))
    )
    assert result["failed"] == ["tests/test_todo.py::test_a"]


# --------------------------------------------------------------------------------------
# Rule 10 側の判定（validate_traceability）
# --------------------------------------------------------------------------------------

def test_traceability_is_optional_when_nothing_is_declared() -> None:
    assert path_utils.validate_traceability([], None) is None
    assert path_utils.validate_traceability(None, None) is None


def test_missing_traceability_record_is_rejected() -> None:
    reason = path_utils.validate_traceability(["t1"], None)
    assert reason is not None and "traceability" in reason


def test_missing_tests_are_rejected() -> None:
    reason = path_utils.validate_traceability(["t1"], {"declared": 1, "matched": 0, "missing": ["t1"]})
    assert reason is not None and "見つかりません" in reason


def test_failed_tests_are_rejected() -> None:
    reason = path_utils.validate_traceability(["t1"], {"declared": 1, "matched": 0, "failed": ["t1"]})
    assert reason is not None and "成功していません" in reason


def test_stale_declaration_count_is_rejected() -> None:
    """契約を変えたのに検証をやり直していない場合を検出する。"""
    reason = path_utils.validate_traceability(["t1", "t2"], {"declared": 1, "matched": 1})
    assert reason is not None and "一致しません" in reason


def test_complete_traceability_passes() -> None:
    assert path_utils.validate_traceability(["t1"], {"declared": 1, "matched": 1}) is None


# --------------------------------------------------------------------------------------
# 受入基準の単位での取りこぼし（F-019）
# --------------------------------------------------------------------------------------

def fr_with_criteria(fid: str, *criteria: str) -> dict:
    return {"id": fid, "title": f"{fid} の要件", "priority": "MUST", "acceptance_criteria": list(criteria)}


def contract_covering(fr_id: str, *criteria: str) -> dict:
    return {
        "test_strategy": {
            "approach": "単体テスト",
            "coverage": [
                {"requirement": fr_id, "acceptance_criterion": c, "test_ids": [f"test_{i}"]}
                for i, c in enumerate(criteria)
            ],
        }
    }


def test_missing_acceptance_criterion_is_detected() -> None:
    """F-019: FR 単位で 1 件でもあれば通していたため、4 件中 1 件でも「成立」と出ていた。"""
    violations = check_traceability.check_traceability(
        requirements(fr_with_criteria("FR-1", "基準A", "基準B")),
        architecture(alpha=["FR-1"]),
        {"alpha": contract_covering("FR-1", "基準A")},
    )
    assert len(violations) == 1
    assert "基準B" in violations[0]


def test_criteria_can_be_shared_across_features() -> None:
    """1 つの FR を複数機能で分担する場合、合算して全基準を覆っていれば通る。"""
    violations = check_traceability.check_traceability(
        requirements(fr_with_criteria("FR-1", "基準A", "基準B")),
        architecture(alpha=["FR-1"], beta=["FR-1"]),
        {"alpha": contract_covering("FR-1", "基準A"), "beta": contract_covering("FR-1", "基準B")},
    )
    assert violations == []


def test_unknown_acceptance_criterion_is_detected() -> None:
    """要件に無い文言（typo・改訂前の原文）で対応づけても通らない。"""
    violations = check_traceability.check_traceability(
        requirements(fr_with_criteria("FR-1", "基準A")),
        architecture(alpha=["FR-1"]),
        {"alpha": contract_covering("FR-1", "基準A", "存在しない基準")},
    )
    assert len(violations) == 1
    assert "存在しない基準" in violations[0]


def test_acceptance_criteria_are_not_judged_before_all_contracts_exist() -> None:
    """契約が未作成の機能が混ざっている設計途中では、分担が確定していないので判定しない。"""
    violations = check_traceability.check_traceability(
        requirements(fr_with_criteria("FR-1", "基準A", "基準B")),
        architecture(alpha=["FR-1"], beta=["FR-1"]),
        {"alpha": contract_covering("FR-1", "基準A")},
    )
    assert violations == []
