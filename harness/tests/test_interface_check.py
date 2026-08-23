"""`interfaces[]` の JSON Schema 突合（改善提案④ / ci_check 項目 J）の検証。

機能を独立した worktree で並行実装する apparness では、producer の出力と consumer の入力の
食い違いが統合時まで露見しない。この判定はそれを統合前に機械検出するためのもので、
JSON Schema の構造比較なので完全にスタック非依存である。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import check_interfaces  # noqa: E402


def arch() -> dict:
    """producer.payload -> consumer.payload という 1 本の結線だけを持つ設計。"""
    return {
        "features": [{"id": "producer"}, {"id": "consumer"}],
        "interfaces": [{
            "producer_feature": "producer",
            "producer_output": "payload",
            "consumer_feature": "consumer",
            "consumer_input": "payload",
        }],
    }


def contracts(out_schema: dict, in_schema: dict) -> dict:
    return {
        "producer": {"outputs": [{"name": "payload", "json_schema": out_schema}]},
        "consumer": {"inputs": [{"name": "payload", "json_schema": in_schema, "required": True}]},
    }


def check(out_schema: dict, in_schema: dict) -> list[str]:
    return check_interfaces.check_interfaces(arch(), contracts(out_schema, in_schema))


# --------------------------------------------------------------------------------------
# 端点の実在
# --------------------------------------------------------------------------------------

def test_unknown_producer_feature() -> None:
    architecture = {
        "features": [{"id": "consumer"}],
        "interfaces": [{
            "producer_feature": "ghost", "producer_output": "x",
            "consumer_feature": "consumer", "consumer_input": "x",
        }],
    }
    violations = check_interfaces.check_interfaces(architecture, {"consumer": {}})
    assert violations and "features[] に存在しません" in violations[0]


def test_unknown_output_name() -> None:
    architecture = arch()
    c = contracts({"type": "object"}, {"type": "object"})
    c["producer"]["outputs"][0]["name"] = "other"
    violations = check_interfaces.check_interfaces(architecture, c)
    assert violations and "outputs[] に 'payload' がありません" in violations[0]


def test_unknown_input_name() -> None:
    architecture = arch()
    c = contracts({"type": "object"}, {"type": "object"})
    c["consumer"]["inputs"][0]["name"] = "other"
    violations = check_interfaces.check_interfaces(architecture, c)
    assert violations and "inputs[] に 'payload' がありません" in violations[0]


# --------------------------------------------------------------------------------------
# 型の一致
# --------------------------------------------------------------------------------------

def test_matching_types_pass() -> None:
    assert check({"type": "string"}, {"type": "string"}) == []


def test_type_mismatch_is_detected() -> None:
    violations = check({"type": "string"}, {"type": "integer"})
    assert violations and "型が一致しません" in violations[0]


def test_producer_type_may_be_a_subset_of_the_consumer_types() -> None:
    assert check({"type": "string"}, {"type": ["string", "null"]}) == []


def test_producer_wider_than_consumer_is_detected() -> None:
    violations = check({"type": ["string", "null"]}, {"type": "string"})
    assert violations and "型が一致しません" in violations[0]


def test_missing_type_is_undecidable() -> None:
    assert check({}, {"type": "string"}) == []
    assert check({"type": "string"}, {}) == []


# --------------------------------------------------------------------------------------
# 必須項目の包含関係
# --------------------------------------------------------------------------------------

OBJ_OUT = {
    "type": "object",
    "properties": {"id": {"type": "string"}, "title": {"type": "string"}},
    "required": ["id"],
}


def test_consumer_requiring_a_field_the_producer_never_emits() -> None:
    consumer = {"type": "object", "properties": {"owner": {"type": "string"}}, "required": ["owner"]}
    violations = check(OBJ_OUT, consumer)
    assert violations and "producer の出力に存在しません" in violations[0]


def test_consumer_requiring_an_optional_producer_field() -> None:
    consumer = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}
    violations = check(OBJ_OUT, consumer)
    assert violations and "必須ではない" in violations[0]


def test_consumer_requiring_a_required_producer_field_passes() -> None:
    consumer = {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}
    assert check(OBJ_OUT, consumer) == []


def test_nested_property_types_are_compared() -> None:
    producer = {"type": "object", "properties": {"count": {"type": "string"}}}
    consumer = {"type": "object", "properties": {"count": {"type": "integer"}}}
    violations = check(producer, consumer)
    assert violations and "count" in violations[0]


def test_array_items_are_compared() -> None:
    producer = {"type": "array", "items": {"type": "string"}}
    consumer = {"type": "array", "items": {"type": "integer"}}
    violations = check(producer, consumer)
    assert violations and "[]" in violations[0]


# --------------------------------------------------------------------------------------
# enum の包含関係
# --------------------------------------------------------------------------------------

def test_producer_enum_must_be_a_subset() -> None:
    violations = check({"enum": ["a", "b"]}, {"enum": ["a"]})
    assert violations and "enum の包含関係" in violations[0]


def test_producer_enum_subset_passes() -> None:
    assert check({"enum": ["a"]}, {"enum": ["a", "b"]}) == []


def test_enum_only_on_one_side_is_undecidable() -> None:
    assert check({"type": "string"}, {"enum": ["a"]}) == []


# --------------------------------------------------------------------------------------
# 実運用に近い形
# --------------------------------------------------------------------------------------

def test_realistic_compatible_pair() -> None:
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "status": {"enum": ["open", "done"]},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["id", "status"],
    }
    assert check(schema, schema) == []


def test_realistic_incompatible_pair_reports_every_problem() -> None:
    producer = {
        "type": "object",
        "properties": {"id": {"type": "string"}, "status": {"enum": ["open", "done", "archived"]}},
        "required": ["id"],
    }
    consumer = {
        "type": "object",
        "properties": {"id": {"type": "integer"}, "status": {"enum": ["open", "done"]}},
        "required": ["id", "status"],
    }
    violations = check(producer, consumer)
    assert len(violations) == 3  # status が必須でない / id の型不一致 / status の enum 超過


@pytest.mark.parametrize("empty", [{}, True, None])
def test_empty_schema_accepts_anything(empty) -> None:
    assert check({"type": "string"}, empty) == []
    assert check(empty, {"type": "string"}) == []
