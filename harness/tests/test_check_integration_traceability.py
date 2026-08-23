"""`check_integration_traceability.check_app` の回帰テスト。

ドッグフーディング F-074: `new_app_scaffold.py` が `04-integration/integration.machine.yaml`
を `interface_coverage: []` の空テンプレートとしてアプリ作成時点から生成するため、
「統合前（`integration.machine.yaml` が存在しない）は判定不能として許可する」という
`check_app` の元々の免除ロジックが、ファイルの存在チェックでは実際には機能していなかった
（ファイルは常に存在する）。結果、`interfaces[]` を持つアプリがどれか1つでも作成されて以降、
まだ1機能もTESTEDになっていない設計直後の段階から `ci_check.py` の項目Nが常時 NG になり、
そのアプリと無関係な harness/ ブランチのマージまで巻き込まれてブロックされていた。
"""
from __future__ import annotations

import check_integration_traceability


ARCHITECTURE = """
interfaces:
  - producer_feature: a
    producer_output: out
    consumer_feature: b
    consumer_input: in
"""


def _write(tmp_path, app_id: str, integration_body: str | None):
    app_dir = tmp_path / "apps" / app_id
    design_dir = app_dir / "02-design"
    design_dir.mkdir(parents=True)
    (design_dir / "architecture.machine.yaml").write_text(ARCHITECTURE, encoding="utf-8")
    if integration_body is not None:
        integ_dir = app_dir / "04-integration"
        integ_dir.mkdir(parents=True)
        (integ_dir / "integration.machine.yaml").write_text(integration_body, encoding="utf-8")
    return tmp_path


def test_scaffolded_empty_template_is_treated_as_not_started(tmp_path):
    """F-074 本体: scaffold直後の空テンプレート（interface_coverage: []）はNGにならない。"""
    root = _write(tmp_path, "demo", "interface_coverage: []\n")
    assert check_integration_traceability.check_app(root, "demo") == []


def test_missing_integration_file_is_still_treated_as_not_started(tmp_path):
    """既存の挙動（ファイル不存在）が壊れていないことの確認。"""
    root = _write(tmp_path, "demo", None)
    assert check_integration_traceability.check_app(root, "demo") == []


def test_partial_coverage_still_reports_gaps(tmp_path):
    """統合が実際に始まった後（1件でも interface_coverage[] があるが不足）は検出を維持する。"""
    root = _write(
        tmp_path,
        "demo",
        "interface_coverage:\n"
        "  - producer_feature: other\n"
        "    producer_output: out\n"
        "    consumer_feature: other2\n"
        "    consumer_input: in\n"
        "    test_ids: [x]\n",
    )
    violations = check_integration_traceability.check_app(root, "demo")
    assert len(violations) == 1
    assert "a.out -> b.in" in violations[0]


def test_fully_covered_reports_nothing(tmp_path):
    root = _write(
        tmp_path,
        "demo",
        "interface_coverage:\n"
        "  - producer_feature: a\n"
        "    producer_output: out\n"
        "    consumer_feature: b\n"
        "    consumer_input: in\n"
        "    test_ids: [x]\n",
    )
    assert check_integration_traceability.check_app(root, "demo") == []
