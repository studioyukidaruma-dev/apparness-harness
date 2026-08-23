#!/usr/bin/env python3
"""`CONVENTIONS.md` から指定した節だけを抜き出して表示する。

agent/skill 定義が `harness/CONVENTIONS.md`（35KB 前後）を毎回まるごと読み込むのは、
その節のほとんどが自分のフェーズと無関係なエージェントにとって無駄が大きい
（`requirements-analyst` は 15 節中せいぜい 1 節しか使わない、等）。
`CONVENTIONS.md` は「単一情報源」（1節冒頭の注意書き）として複製はせず、
消費側だけを絞ることでコンテキスト予算（15節・DOGFOODING-LOG.md F-047）を守る。

使い方:
    python3 harness/scripts/print_conventions.py --sections 6,9,13
    python3 harness/scripts/print_conventions.py --list   # 節番号と見出し一覧だけを表示

exit code: 0 = 成功, 2 = 引数エラー・存在しない節番号
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402

SECTION_RE = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)


def parse_sections(text: str) -> list[tuple[int, str, str]]:
    """`(節番号, 見出し行, 本文全体)` のリストを返す。本文は次の節の直前まで（見出し込み）。"""
    matches = list(SECTION_RE.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        number = int(m.group(1))
        heading = m.group(0)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((number, heading, text[start:end].rstrip("\n")))
    return sections


def load_sections(root: pathlib.Path) -> list[tuple[int, str, str]]:
    path = _common.harness_root(root) / "CONVENTIONS.md"
    return parse_sections(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sections", help="カンマ区切りの節番号（例: 6,9,13）")
    parser.add_argument("--list", action="store_true", help="節番号と見出し一覧だけを表示する")
    args = parser.parse_args(argv[1:])

    if not args.sections and not args.list:
        parser.error("--sections か --list のどちらかを指定してください")

    root = _common.repo_root()
    sections = load_sections(root)

    if args.list:
        for number, heading, _body in sections:
            print(f"{number}: {heading[len('## ') + len(str(number)) + 2:]}")
        return 0

    wanted: list[int] = []
    for token in args.sections.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            wanted.append(int(token))
        except ValueError:
            print(f"エラー: 節番号ではありません: {token!r}", file=sys.stderr)
            return 2

    by_number = {number: body for number, _heading, body in sections}
    missing = [n for n in wanted if n not in by_number]
    if missing:
        print(
            f"エラー: 存在しない節番号です: {missing}（--list で一覧を確認してください）",
            file=sys.stderr,
        )
        return 2

    for n in wanted:
        print(by_number[n])
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
