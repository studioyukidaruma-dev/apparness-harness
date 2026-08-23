"""JUnit XML の解析（アプリ非依存の共通インターフェース）。

JUnit XML は pytest（`--junitxml`）/ jest（`jest-junit`）/ vitest / go-test（`go-junit-report`）/
cargo（`cargo2junit`）/ JUnit / RSpec / PHPUnit がいずれも出力できる**事実上のクロススタック
標準**である。ハーネスはアプリの言語を一切知らないまま、この XML を読むだけで

  - 空振りの検出（`tests="0"` を成功と呼んでいないか）
  - スキップ率の閾値超過
  - 特定テスト ID が実際に実行され成功したか（要件トレーサビリティ）

を機械判定できる。**JUnit XML を出せない技術を選んだ場合は `verification.junit_xml` を
宣言しなければよい**（その場合これらの判定だけが無効になり、終了コードによるゲートは
そのまま効き続ける）。非依存性を段階的に degrade させる設計。

標準ライブラリのみを使う（`xml.etree.ElementTree`）。
"""
from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET

PASSED = "passed"
FAILED = "failed"
ERRORED = "errored"
SKIPPED = "skipped"


def _int_attr(elem, name: str) -> int:
    try:
        return int(elem.get(name) or 0)
    except (TypeError, ValueError):
        return 0


def _testcase_status(case) -> str:
    for child in case:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "failure":
            return FAILED
        if tag == "error":
            return ERRORED
        if tag == "skipped":
            return SKIPPED
    return PASSED


def parse_junit_xml(path: pathlib.Path) -> dict:
    """JUnit XML を集計する。

    返り値: {"tests", "failures", "errors", "skipped", "testcases": [...]}。
    `testcases` の各要素は {"classname", "name", "file", "status"}。

    件数は `<testsuite>` の属性を合計するが、属性が無い実装（一部のレポータ）でも動くよう、
    属性の合計が 0 で `<testcase>` が存在する場合は要素を数え直す。
    """
    tree = ET.parse(str(path))
    root = tree.getroot()
    root_tag = root.tag.rsplit("}", 1)[-1]
    suites = [root] if root_tag == "testsuite" else list(root.iter())

    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for elem in suites:
        if elem.tag.rsplit("}", 1)[-1] != "testsuite":
            continue
        totals["tests"] += _int_attr(elem, "tests")
        totals["failures"] += _int_attr(elem, "failures")
        totals["errors"] += _int_attr(elem, "errors")
        totals["skipped"] += _int_attr(elem, "skipped") + _int_attr(elem, "skip")

    testcases = []
    for case in root.iter():
        if case.tag.rsplit("}", 1)[-1] != "testcase":
            continue
        testcases.append(
            {
                "classname": case.get("classname") or "",
                "name": case.get("name") or "",
                "file": case.get("file") or "",
                "status": _testcase_status(case),
            }
        )

    if totals["tests"] == 0 and testcases:
        totals["tests"] = len(testcases)
        totals["failures"] = sum(1 for c in testcases if c["status"] == FAILED)
        totals["errors"] = sum(1 for c in testcases if c["status"] == ERRORED)
        totals["skipped"] = sum(1 for c in testcases if c["status"] == SKIPPED)

    totals["testcases"] = testcases
    return totals


def _strip_param_suffix(name: str) -> str:
    """`@pytest.mark.parametrize` が付ける `test_x[None]` の末尾 `[...]` を落とす。

    契約には非パラメータ化の名前（`test_x`）で書かれるのが通例だが、実行結果の
    JUnit XML にはパラメータ値付きの名前しか出ないため、素の名前も候補に加える。
    """
    if name.endswith("]") and "[" in name:
        return name[: name.index("[")]
    return name


def testcase_identifiers(case: dict) -> set[str]:
    """1 つの `<testcase>` を指しうる識別子の候補を返す。

    テスト ID の書き方は言語・レポータごとに異なる（pytest は `tests/test_x.py::test_y`、
    jest は `describe > it`、JUnit は `com.example.FooTest.bar` など）。ハーネスは特定の
    書式を規定せず、代表的な組み立て方をすべて候補として持ち、契約に書かれた ID がその
    いずれかと一致する（または末尾一致する）かどうかで照合する。
    """
    name, classname, file = case["name"], case["classname"], case["file"]
    names = {name, _strip_param_suffix(name)}
    candidates = set(names)
    if classname:
        for n in names:
            candidates.update({classname, f"{classname}.{n}", f"{classname}::{n}", f"{classname} {n}"})
        # pytest の `--junitxml` は `file` 属性を出さず、classname にドット区切りのモジュールパス
        # （`tests.test_todo`）を入れる。一方で人間が契約に書くのは pytest の node id
        # （`tests/test_todo.py::test_empty_title`）である。両者を機械的に橋渡しするため、
        # ドット区切りを「どこまでがファイルパスか」の各可能性で分解した形も候補に加える。
        parts = classname.split(".")
        for i in range(1, len(parts) + 1):
            path = "/".join(parts[:i]) + ".py"
            for n in names:
                candidates.add("::".join([path, *parts[i:], n]))
    if file:
        for n in names:
            candidates.update({file, f"{file}::{n}"})
        if classname:
            for n in names:
                candidates.add(f"{file}::{classname}::{n}")
    return {c for c in candidates if c}


def find_matching_testcases(testcases: list[dict], identifier: str) -> list[dict]:
    """契約に書かれたテスト識別子に一致する `<testcase>` を返す（完全一致 → 末尾一致の順）。"""
    identifier = identifier.strip()
    if not identifier:
        return []
    exact = [c for c in testcases if identifier in testcase_identifiers(c)]
    if exact:
        return exact
    return [
        c for c in testcases
        if any(cand.endswith(identifier) for cand in testcase_identifiers(c))
    ]
