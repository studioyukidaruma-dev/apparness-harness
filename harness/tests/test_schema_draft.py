"""要件・設計のスキーマが、DRAFT の空欄を許し、承認後は空欄を許さないことの検証。

雛形（`new_app_scaffold.py`）は要件・設計を空の DRAFT として生成し、`init-app` はそれを
コミットする。以前はスキーマが DRAFT でも「空でないこと」を要求していたため、雛形を
コミットしたブランチを push しただけで CI 項目 A が不合格になっていた。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

import pytest

import _common
import ci_check

HARNESS_ROOT = pathlib.Path(__file__).resolve().parent.parent


def schema(name: str) -> dict:
    return json.loads((HARNESS_ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))


def requirements(status: str, **fields) -> dict:
    doc = {
        "app_id": "demo-app",
        "app_name": "デモ",
        "version": 1,
        "status": status,
        "summary": "",
        "goals": [],
        "functional_requirements": [],
        "approved_by": "tester" if status != "DRAFT" else None,
        "approved_at": "2026-09-13T00:00:00Z" if status != "DRAFT" else None,
    }
    doc.update(fields)
    return doc


def architecture(status: str, **fields) -> dict:
    doc = {
        "app_id": "demo-app",
        "design_version": 1,
        "based_on_requirements_version": 1,
        "status": status,
        "features": [],
        "interfaces": [],
        "approved_by": "tester" if status != "DRAFT" else None,
        "approved_at": "2026-09-13T00:00:00Z" if status != "DRAFT" else None,
    }
    doc.update(fields)
    return doc


FR = {
    "id": "FR-1",
    "title": "貸出を記録する",
    "description": "備品の貸出を記録できる",
    "priority": "MUST",
    "acceptance_criteria": ["貸出を登録すると一覧に出る"],
}


# --------------------------------------------------------------------------------------
# 雛形そのもの（回帰テスト）
# --------------------------------------------------------------------------------------

@pytest.fixture()
def scaffolded(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "repo"
    (root / "harness").mkdir(parents=True)
    for name in ("schemas", "scripts", "templates"):
        shutil.copytree(HARNESS_ROOT / name, root / "harness" / name)
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "tester"],
    ):
        subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)
    result = subprocess.run(
        [sys.executable, "harness/scripts/new_app_scaffold.py", "demo-app", "デモアプリ"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return root


def test_the_generated_app_scaffold_satisfies_ci_item_a(scaffolded: pathlib.Path) -> None:
    """雛形を生成した直後の状態で、CI 項目 A（スキーマ検証）が通る。"""
    assert ci_check.check_schema(scaffolded) == []


# --------------------------------------------------------------------------------------
# 要件
# --------------------------------------------------------------------------------------

def test_a_blank_draft_requirements_is_valid() -> None:
    assert _common.validate_against_schema(requirements("DRAFT"), schema("requirements")) == []


@pytest.mark.parametrize("status", ["APPROVED", "SUPERSEDED"])
@pytest.mark.parametrize("field", ["summary", "goals", "functional_requirements"])
def test_non_draft_requirements_must_not_be_blank(status: str, field: str) -> None:
    filled = requirements(status, summary="備品の貸出を管理する", goals=["紛失を減らす"], functional_requirements=[FR])
    blank = {**filled, field: requirements(status)[field]}
    assert _common.validate_against_schema(filled, schema("requirements")) == []
    errors = _common.validate_against_schema(blank, schema("requirements"))
    assert errors and any(field in e or "<root>" in e for e in errors)


def test_a_malformed_requirement_is_rejected_even_in_draft() -> None:
    """空欄は許しても、書いた機能要件の書式は DRAFT でも検証する。"""
    broken = {k: v for k, v in FR.items() if k != "acceptance_criteria"}
    doc = requirements("DRAFT", functional_requirements=[broken])
    assert _common.validate_against_schema(doc, schema("requirements")) != []


# --------------------------------------------------------------------------------------
# 設計
# --------------------------------------------------------------------------------------

def test_a_blank_draft_architecture_is_valid() -> None:
    assert _common.validate_against_schema(architecture("DRAFT"), schema("architecture")) == []


@pytest.mark.parametrize("status", ["APPROVED", "SUPERSEDED"])
def test_non_draft_architecture_must_have_features(status: str) -> None:
    errors = _common.validate_against_schema(architecture(status), schema("architecture"))
    assert errors and any("features" in e for e in errors)
