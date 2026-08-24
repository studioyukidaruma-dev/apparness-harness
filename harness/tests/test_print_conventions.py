"""`print_conventions.py`（agent/skill が CONVENTIONS.md の必要な節だけを読み込む入口）の検証。

コンテキスト予算（`CONVENTIONS.md` 15節）を守るために追加したツール。担当外の節まで
読み込ませていたことが常時コストを押し上げていた（摩擦点 F-047）。
節の切り出しが取りこぼし・重複なく行われることと、CLI の異常系を固定する。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import print_conventions  # noqa: E402

FIXTURE = """# タイトル

前文。

## 1. 最初の節

本文1行目。
本文2行目。

## 2. 次の節（記号を含む見出し）

本文A。

## 10. 二桁の節

本文B。
"""


def test_parse_sections_splits_by_number_in_order() -> None:
    sections = print_conventions.parse_sections(FIXTURE)
    assert [n for n, _h, _b in sections] == [1, 2, 10]


def test_each_section_body_stops_before_the_next_heading() -> None:
    sections = print_conventions.parse_sections(FIXTURE)
    body = dict((n, b) for n, _h, b in sections)
    assert "本文1行目" in body[1]
    assert "本文A" not in body[1]  # 次の節の本文を巻き込まない
    assert "## 2." not in body[1]  # 次の節の見出しも含まない


def test_section_body_includes_its_own_heading() -> None:
    sections = print_conventions.parse_sections(FIXTURE)
    body = dict((n, b) for n, _h, b in sections)
    assert body[2].startswith("## 2. 次の節")


def test_two_digit_section_numbers_are_not_confused_with_one_digit() -> None:
    """`## 1.` への正規表現マッチが `## 10.` を誤って拾わないこと。"""
    sections = print_conventions.parse_sections(FIXTURE)
    body = dict((n, b) for n, _h, b in sections)
    assert "本文B" in body[10]
    assert "本文B" not in body[1]


@pytest.fixture()
def repo(tmp_path: pathlib.Path, monkeypatch) -> pathlib.Path:
    (tmp_path / "harness").mkdir()
    (tmp_path / "harness" / "CONVENTIONS.md").write_text(FIXTURE, encoding="utf-8")
    monkeypatch.setattr(print_conventions._common, "repo_root", lambda: tmp_path)
    return tmp_path


def test_main_list_shows_every_section_number_and_title(repo, capsys) -> None:
    assert print_conventions.main(["print_conventions.py", "--list"]) == 0
    out = capsys.readouterr().out
    assert "1: 最初の節" in out
    assert "10: 二桁の節" in out


def test_main_sections_prints_only_the_requested_ones(repo, capsys) -> None:
    assert print_conventions.main(["print_conventions.py", "--sections", "2"]) == 0
    out = capsys.readouterr().out
    assert "次の節" in out
    assert "最初の節" not in out
    assert "二桁の節" not in out


def test_main_sections_accepts_a_comma_separated_list(repo, capsys) -> None:
    assert print_conventions.main(["print_conventions.py", "--sections", "1, 10"]) == 0
    out = capsys.readouterr().out
    assert "最初の節" in out and "二桁の節" in out


def test_main_rejects_an_unknown_section_number(repo, capsys) -> None:
    assert print_conventions.main(["print_conventions.py", "--sections", "99"]) == 2
    assert "存在しない節番号" in capsys.readouterr().err


def test_main_requires_either_sections_or_list(repo) -> None:
    with pytest.raises(SystemExit):
        print_conventions.main(["print_conventions.py"])
