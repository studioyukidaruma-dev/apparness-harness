"""`path_utils.validate_status_transition`（Rule 9 / ci_check 項目 F の判定ロジック）を
`CONVENTIONS.md` 5 節の状態機械に対して網羅的に検証する。

直線状態 7 つ ＋ `BLOCKED` ＋ `SUPERSEDED` の全 81 組み合わせを、期待される許可/拒否と
突き合わせる。状態機械を変更するときは `CONVENTIONS.md` 5 節 → この期待値 → 実装、の順で
揃えること。
"""
from __future__ import annotations

import itertools

import pytest

import path_utils

LINEAR = path_utils.STATUS_LINEAR_ORDER
ALL_STATES = LINEAR + ["BLOCKED", "SUPERSEDED"]
TERMINAL = path_utils.STATUS_TERMINAL_STATES


def expected_allowed(old: str, new: str) -> bool:
    """`CONVENTIONS.md` 5 節の定義をテスト側で独立に再実装したもの（実装の写しではない）。"""
    if old == new:
        return True
    if old in TERMINAL:
        return False
    if new in ("BLOCKED", "SUPERSEDED"):
        return True
    if old == "BLOCKED":
        return True  # 履歴を渡さない場合は判定不能として許可（履歴ありの挙動は別テスト）
    return LINEAR.index(new) == LINEAR.index(old) + 1


@pytest.mark.parametrize("old,new", list(itertools.product(ALL_STATES, ALL_STATES)))
def test_transition_matrix(old: str, new: str) -> None:
    reason = path_utils.validate_status_transition(old, new)
    assert (reason is None) is expected_allowed(old, new), f"{old} -> {new}: {reason}"


def test_new_file_without_old_state_is_allowed() -> None:
    assert path_utils.validate_status_transition(None, "IN_PROGRESS") is None


def test_unknown_state_is_left_to_the_schema() -> None:
    assert path_utils.validate_status_transition("NOT_STARTED", "WHATEVER") is None
    assert path_utils.validate_status_transition("WHATEVER", "TESTED") is None


def test_backward_transition_message_mentions_direction() -> None:
    reason = path_utils.validate_status_transition("TESTED", "IN_PROGRESS")
    assert reason is not None and "後退" in reason


def test_skip_transition_message_lists_skipped_states() -> None:
    reason = path_utils.validate_status_transition("NOT_STARTED", "TESTED")
    assert reason is not None
    for skipped in ("CONTRACT_DRAFTED", "CONTRACT_APPROVED", "IN_PROGRESS", "IMPLEMENTED"):
        assert skipped in reason


def test_terminal_states_are_frozen() -> None:
    for terminal in sorted(TERMINAL):
        reason = path_utils.validate_status_transition(terminal, "IN_PROGRESS")
        assert reason is not None and "終端状態" in reason


def test_linear_order_matches_the_schema_enum() -> None:
    """`STATUS_LINEAR_ORDER` と `status.schema.json` の enum のズレを検出する。"""
    import json
    import pathlib

    schema_path = pathlib.Path(__file__).resolve().parent.parent / "schemas" / "status.schema.json"
    enum = json.loads(schema_path.read_text(encoding="utf-8"))["properties"]["state"]["enum"]
    assert enum == LINEAR + ["BLOCKED", "SUPERSEDED"]


# --------------------------------------------------------------------------------------
# BLOCKED を経由した飛び越しの遮断（改善提案⑦）
# --------------------------------------------------------------------------------------

def history(*states) -> list:
    """`state_history[]` を組み立てる（`at` は記載順に単調増加させる）。"""
    return [
        {"state": s, "at": f"2026-08-21T10:{i:02d}:00Z", "by": "tester"}
        for i, s in enumerate(states)
    ]


def test_blocked_without_history_is_still_undecidable() -> None:
    """履歴を渡さない場合は従来どおり判定不能として通す（既存の呼び出しを壊さない）。"""
    assert path_utils.validate_status_transition("BLOCKED", "TESTED") is None


def test_blocked_resume_uses_the_last_non_blocked_state() -> None:
    h = history("NOT_STARTED", "CONTRACT_DRAFTED", "BLOCKED")
    assert path_utils.validate_status_transition("BLOCKED", "CONTRACT_APPROVED", h) is None


def test_blocked_cannot_be_used_to_skip_states() -> None:
    h = history("NOT_STARTED", "BLOCKED")
    reason = path_utils.validate_status_transition("BLOCKED", "TESTED", h)
    assert reason is not None
    assert "飛ばしています" in reason
    assert "NOT_STARTED" in reason


def test_blocked_cannot_be_used_to_go_backwards() -> None:
    h = history("NOT_STARTED", "CONTRACT_DRAFTED", "CONTRACT_APPROVED", "BLOCKED")
    reason = path_utils.validate_status_transition("BLOCKED", "NOT_STARTED", h)
    assert reason is not None and "後退" in reason


def test_resuming_to_the_same_state_is_allowed() -> None:
    h = history("NOT_STARTED", "IN_PROGRESS", "BLOCKED")
    assert path_utils.validate_status_transition("BLOCKED", "IN_PROGRESS", h) is None


def test_repeated_blocking_still_resolves_the_real_previous_state() -> None:
    h = history("NOT_STARTED", "CONTRACT_DRAFTED", "BLOCKED", "CONTRACT_DRAFTED", "BLOCKED")
    assert path_utils.validate_status_transition("BLOCKED", "CONTRACT_APPROVED", h) is None
    assert path_utils.validate_status_transition("BLOCKED", "IMPLEMENTED", h) is not None


def test_history_without_any_non_blocked_entry_is_undecidable() -> None:
    assert path_utils.validate_status_transition("BLOCKED", "TESTED", history("BLOCKED")) is None
    assert path_utils.validate_status_transition("BLOCKED", "TESTED", []) is None


def test_blocked_to_superseded_is_always_allowed() -> None:
    h = history("NOT_STARTED", "BLOCKED")
    assert path_utils.validate_status_transition("BLOCKED", "SUPERSEDED", h) is None


def test_history_is_ordered_by_timestamp_not_file_order() -> None:
    unordered = [
        {"state": "IN_PROGRESS", "at": "2026-08-21T12:00:00Z"},
        {"state": "CONTRACT_APPROVED", "at": "2026-08-21T11:00:00Z"},
        {"state": "BLOCKED", "at": "2026-08-21T13:00:00Z"},
    ]
    assert path_utils.resolve_effective_previous_state(unordered) == "IN_PROGRESS"


def test_entries_without_timestamps_keep_their_file_order() -> None:
    assert path_utils.resolve_effective_previous_state(
        [{"state": "CONTRACT_DRAFTED"}, {"state": "CONTRACT_APPROVED"}, {"state": "BLOCKED"}]
    ) == "CONTRACT_APPROVED"


def test_extract_state_history_from_status_yaml() -> None:
    content = (
        "feature_id: a\n"
        "state: BLOCKED\n"
        "state_history:\n"
        "- state: NOT_STARTED\n"
        '  at: "2026-08-21T10:00:00Z"\n'
        "- state: BLOCKED\n"
        '  at: "2026-08-21T11:00:00Z"\n'
        '  note: "外部APIの仕様待ち"\n'
    )
    entries = path_utils.extract_state_history(content)
    assert [e["state"] for e in entries] == ["NOT_STARTED", "BLOCKED"]
    assert path_utils.resolve_effective_previous_state(entries) == "NOT_STARTED"


def test_extract_state_history_without_the_field() -> None:
    assert path_utils.extract_state_history("state: TESTED\n") == []
