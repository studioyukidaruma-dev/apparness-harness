"""`path_utils.parse_simple_yaml`（hooks 用の依存ゼロ YAML サブセットパーサ）の検証。

hooks は PyYAML に依存できないため自前のパーサを持つが、**ハーネスが規定する範囲の YAML に
限れば PyYAML と同じ結果を返す**ことがこのパーサの契約である。テストでは PyYAML
（開発用依存。`requirements-dev.txt`）を正解として突き合わせる。
"""
from __future__ import annotations

import pathlib

import pytest
import yaml

import path_utils

TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent.parent / "templates"

PLACEHOLDERS = {
    "{{APP_ID}}": "my-app",
    "{{APP_NAME}}": "My App",
    "{{FEATURE_ID}}": "my-feature",
    "{{FEATURE_NAME}}": "My Feature",
    "{{TIMESTAMP}}": "2026-08-21T10:00:00Z",
    "{{ACTOR}}": "tester",
    "{{REQUIREMENTS_VERSION}}": "1",
}


def fill(text: str) -> str:
    for key, value in PLACEHOLDERS.items():
        text = text.replace(key, value)
    return text


@pytest.mark.parametrize("template", sorted(TEMPLATE_DIR.glob("*.yaml.tmpl")), ids=lambda p: p.name)
def test_matches_pyyaml_on_every_template(template: pathlib.Path) -> None:
    text = fill(template.read_text(encoding="utf-8"))
    assert path_utils.parse_simple_yaml(text) == yaml.safe_load(text)


@pytest.mark.parametrize(
    "text",
    [
        "a: 1\nb: two\nc: null\nd: true\ne: 1.5\n",
        "outer:\n  inner:\n    leaf: 1\n",
        "items:\n- 1\n- 2\n",
        "items:\n  - 1\n  - 2\n",
        "items:\n- name: a\n  ref: b\n- name: c\n  ref: d\n",
        "flow: { a: 1, b: two }\n",
        'flow: { a: "x, y", b: [1, 2] }\n',
        "list: []\nmap: {}\n",
        'quoted: "a # not a comment"  # a comment\n',
        "nested:\n  items:\n  - name: a\n    sub: { x: 1 }\n",
        "empty_value:\nnext: 1\n",
        "deep:\n  a:\n  - b: 1\n    c:\n      d: 2\n",
        # 値の中にコロンを含む文字列をマッピングと誤認識しないこと（契約の test_ids で実際に踏んだ）
        'ids:\n- "tests/test_todo.py::test_a"\n- "tests/test_todo.py::test_b"\n',
        'cmd: "pytest -q --junitxml=x.xml"\n',
        "url: http://example.com/a\n",
        "nested:\n  ids:\n  - a::b\n  other: 1\n",
    ],
)
def test_matches_pyyaml_on_snippets(text: str) -> None:
    assert path_utils.parse_simple_yaml(text) == yaml.safe_load(text)


def test_empty_content() -> None:
    assert path_utils.parse_simple_yaml("") == {}
    assert path_utils.parse_simple_yaml("# comment only\n") == {}


def test_unsupported_construct_does_not_raise() -> None:
    """未対応の記法（ブロックスカラー等）に出会っても例外を投げない（Hook を止めない）。"""
    result = path_utils.parse_simple_yaml("a: |\n  line1\n  line2\nb: 1\n")
    assert isinstance(result, dict)
    assert result.get("b") == 1


def test_block_scalar_as_sequence_item_does_not_lose_following_keys() -> None:
    """F-061: `- >-`（シーケンス項目自体がブロックスカラー）を解釈できず、それ以降の
    トップレベルキーが丸ごと消える実害があった（`review.majors` にこの書式を使うと
    `verification_receipt` が読めなくなり、「受領書が無い」という誤ったブロックが起きた）。
    """
    text = (
        "review:\n"
        "  majors:\n"
        "  - >-\n"
        "    something long\n"
        "    continues here\n"
        "  minors: []\n"
        "verification_receipt:\n"
        "  commit: abc123\n"
    )
    result = path_utils.parse_simple_yaml(text)
    assert result["review"]["minors"] == []
    assert len(result["review"]["majors"]) == 1
    assert result["verification_receipt"] == {"commit": "abc123"}


def test_literal_block_scalar_as_sequence_item() -> None:
    """`- |`（リテラル）でも同様に読み飛ばせること。"""
    text = "items:\n- |\n  line1\n  line2\nnext: 1\n"
    result = path_utils.parse_simple_yaml(text)
    assert len(result["items"]) == 1
    assert result["next"] == 1


def test_unexpected_deep_indent_in_mapping_is_skipped_not_fatal() -> None:
    """F-061 の保険: マッピング内で想定より深いインデントの行に出会っても、
    その行だけ読み飛ばして後続キーの解析を継続する（丸ごと break しない）。
    """
    text = "a: 1\n    stray line\nb: 2\n"
    result = path_utils.parse_simple_yaml(text)
    assert result["a"] == 1
    assert result["b"] == 2
