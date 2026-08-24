"""`harness/CLAIMS.md`（主張と証跡の対応表）と実体の drift を検出する項目 P の検証。

表が実体から drift すれば索引としての価値が消える。「テストを書いたつもりで名前だけ書いた」
「テストをリネームして表を直し忘れた」のどちらも、機械的に検出できなければ必ず起きる。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import ci_check  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

HEADER = """| 規則 | 何をブロックすると主張するか | 実証テスト | 最終実証日 | 未実証の残余 |
|---|---|---|---|---|
"""


def build(tmp_path: pathlib.Path, table: str, tests: dict[str, str] | None = None) -> pathlib.Path:
    harness = tmp_path / "harness"
    (harness / "tests").mkdir(parents=True)
    (harness / "CLAIMS.md").write_text(HEADER + table, encoding="utf-8")
    for name, source in (tests or {}).items():
        (harness / "tests" / name).write_text(source, encoding="utf-8")
    return tmp_path


def test_existing_test_name_passes(tmp_path) -> None:
    root = build(
        tmp_path,
        "| Rule 1 | x を拒否する | `test_a.py::test_x` | 2026-08-24 | — |\n",
        {"test_a.py": "def test_x() -> None:\n    pass\n"},
    )
    assert ci_check.check_claims_coverage(root) == []


def test_unknown_test_name_is_rejected(tmp_path) -> None:
    """表にあるのに実体に無いテスト名（リネーム後の直し忘れ、書いたつもり）を検出する。"""
    root = build(
        tmp_path,
        "| Rule 1 | x を拒否する | `test_a.py::test_ghost` | 2026-08-24 | — |\n",
        {"test_a.py": "def test_x() -> None:\n    pass\n"},
    )
    violations = ci_check.check_claims_coverage(root)
    assert len(violations) == 1 and "test_ghost" in violations[0]


def test_unknown_test_file_is_rejected(tmp_path) -> None:
    root = build(tmp_path, "| Rule 1 | x | `test_missing.py::test_x` | 2026-08-24 | — |\n")
    violations = ci_check.check_claims_coverage(root)
    assert len(violations) == 1 and "test_missing.py" in violations[0]


def test_missing_evidence_without_a_reason_is_rejected(tmp_path) -> None:
    """実証テストが無い行は、なぜ実証できないかを書かせる（空欄のまま置かせない）。"""
    root = build(tmp_path, "| Rule 1 | x を拒否する | — | — | — |\n")
    violations = ci_check.check_claims_coverage(root)
    assert len(violations) == 1 and "未実証の残余" in violations[0]


def test_missing_evidence_with_a_reason_passes(tmp_path) -> None:
    root = build(
        tmp_path,
        "| Rule 1 | x を拒否する | — | — | Claude Code 側の責務で外から確かめられない |\n",
    )
    assert ci_check.check_claims_coverage(root) == []


def test_multiple_tests_in_one_cell_are_all_checked(tmp_path) -> None:
    root = build(
        tmp_path,
        "| Rule 1 | x | `test_a.py::test_x` / `test_a.py::test_ghost` | 2026-08-24 | — |\n",
        {"test_a.py": "def test_x() -> None:\n    pass\n"},
    )
    violations = ci_check.check_claims_coverage(root)
    assert len(violations) == 1 and "test_ghost" in violations[0]


def test_missing_claims_file_does_not_crash(tmp_path) -> None:
    (tmp_path / "harness").mkdir()
    assert ci_check.check_claims_coverage(tmp_path) == []


# --------------------------------------------------------------------------------------
# 実リポジトリの表が実体と一致していること（このテスト自体が見張り番）
# --------------------------------------------------------------------------------------

def test_this_repository_claims_table_matches_reality() -> None:
    violations = ci_check.check_claims_coverage(REPO_ROOT)
    assert violations == [], "\n".join(violations)


def test_every_hook_rule_has_a_row() -> None:
    """`CONVENTIONS.md` 7節の各 Rule が、表に 1 行ずつあること（行の足し忘れの検出）。"""
    import re

    conventions = (REPO_ROOT / "harness" / "CONVENTIONS.md").read_text(encoding="utf-8")
    section7 = conventions.split("## 7. ")[1].split("\n## ")[0]
    rule_numbers = {int(n) for n in re.findall(r"^\s*(\d+)\. \*\*", section7, re.MULTILINE)}
    assert rule_numbers, "7節から Rule 番号を読み取れませんでした"

    claims = (REPO_ROOT / "harness" / "CLAIMS.md").read_text(encoding="utf-8")
    documented = {int(n) for n in re.findall(r"\|\s*Rule (\d+)\s*\|", claims)}
    assert rule_numbers <= documented, f"CLAIMS.md に行が無い Rule: {sorted(rule_numbers - documented)}"
