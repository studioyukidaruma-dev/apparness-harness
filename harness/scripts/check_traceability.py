#!/usr/bin/env python3
"""要件 → 機能 → テスト のトレーサビリティを機械検証する。

`requirements.machine.yaml` の `functional_requirements[].id` は `^FR-[0-9]+$` で既に固定されて
おり、`architecture.machine.yaml` の `features[].covers_requirements` と
`contract.yaml` の `test_strategy.coverage[].requirement` が同じ ID 体系を参照する。
この 3 者を突き合わせるだけで、**要件の取りこぼし**と**受入基準に対応するテストの不在**を
スタック非依存に検出できる。

判定内容:
  1. `priority: MUST` の要件がどの機能にも覆われていない（要件の取りこぼし）
  2. `covers_requirements` に、要件定義に存在しない ID が書かれている
  3. 機能が覆うと宣言した要件が、その機能の `contract.yaml` の
     `test_strategy.coverage[]` に対応づけられていない

「対応づけたテストが実在し、実際に成功したか」は `run_verification.py` が JUnit XML と
突合し、受領書の `traceability` に記録する（Rule 10 が検証する。CONVENTIONS.md 14節）。

使い方:
    python3 harness/scripts/check_traceability.py [--app <app-id>]

exit code: 0 = 問題なし, 1 = 不整合あり, 2 = 実行エラー
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402


def check_traceability(requirements: dict, architecture: dict, contracts: dict) -> list[str]:
    """要件・設計・各機能の契約を突き合わせる。`contracts` は feature_id → contract の dict。"""
    frs = {
        fr.get("id"): fr
        for fr in (requirements or {}).get("functional_requirements") or []
        if isinstance(fr, dict) and fr.get("id")
    }
    if not frs:
        return []

    violations: list[str] = []
    covered: dict[str, list[str]] = {}
    for feature in (architecture or {}).get("features") or []:
        if not isinstance(feature, dict):
            continue
        fid = feature.get("id")
        for fr_id in feature.get("covers_requirements") or []:
            if fr_id not in frs:
                violations.append(
                    f"features[{fid}].covers_requirements: {fr_id!r} は requirements.machine.yaml に"
                    f"存在しません"
                )
                continue
            covered.setdefault(fr_id, []).append(fid)

            contract = contracts.get(fid)
            if contract is None:
                continue  # まだ contract.yaml が作られていない段階（scaffold 前）は判定しない
            strategy = contract.get("test_strategy")
            if not isinstance(strategy, dict):
                violations.append(
                    f"{fid}/contract.yaml: test_strategy が構造化されていません"
                    f"（approach と coverage[] を持つオブジェクトにしてください）"
                )
                continue
            requirements_in_tests = {
                entry.get("requirement")
                for entry in strategy.get("coverage") or []
                if isinstance(entry, dict)
            }
            if fr_id not in requirements_in_tests:
                violations.append(
                    f"{fid}/contract.yaml: この機能が覆うと宣言した {fr_id} に対応するテストが"
                    f"test_strategy.coverage[] にありません（受入基準ごとにテスト識別子を"
                    f"対応づけてください）"
                )

    violations += check_acceptance_criteria(frs, covered, contracts)

    for fr_id, fr in frs.items():
        if fr.get("priority") == "MUST" and fr_id not in covered:
            violations.append(
                f"{fr_id}（priority: MUST, {fr.get('title')!r}）: どの機能の"
                f"covers_requirements にも含まれていません（要件の取りこぼし）"
            )
    return violations


def _coverage_entries(contract) -> list:
    strategy = (contract or {}).get("test_strategy")
    if not isinstance(strategy, dict):
        return []
    return [e for e in strategy.get("coverage") or [] if isinstance(e, dict)]


def check_acceptance_criteria(frs: dict, covered: dict, contracts: dict) -> list[str]:
    """受入基準の単位で、テストへの対応づけの取りこぼしを検出する（F-019）。

    受入基準は end-to-end の文であることが多く、1 つの基準が複数機能にまたがる。一方
    `coverage[]` は機能ごとに書くため、**どの機能がどの基準を引き受けるかの分担ルール**が
    必要になる。ここでは「その FR を覆うと宣言した全機能の `coverage[]` を合算して、
    `acceptance_criteria` を全て覆うこと」を分担ルールとして機械検証する。

    FR 単位で 1 件でも対応づけがあれば通していた頃は、基準 4 件のうち 1 件しか
    テストが無くても「トレーサビリティは成立しています」と出ていた。
    """
    violations: list[str] = []
    for fr_id, fids in sorted(covered.items()):
        criteria = [c for c in (frs.get(fr_id) or {}).get("acceptance_criteria") or [] if str(c).strip()]
        if not criteria:
            continue
        if any(contracts.get(fid) is None for fid in fids):
            continue  # 契約が未作成の機能が混ざっている間は判定しない（分担が確定していない）

        entries = {fid: _coverage_entries(contracts.get(fid)) for fid in fids}
        if any(
            not any(e.get("requirement") == fr_id for e in entries[fid]) for fid in fids
        ):
            continue  # その FR の対応づけを一切持たない機能がある＝上の判定で既に報告済み

        declared: dict[str, list[str]] = {}
        for fid in fids:
            for entry in entries[fid]:
                if entry.get("requirement") != fr_id:
                    continue
                key = str(entry.get("acceptance_criterion") or "").strip()
                if key:
                    declared.setdefault(key, []).append(fid)

        known = {str(c).strip() for c in criteria}
        for criterion in criteria:
            if str(criterion).strip() not in declared:
                violations.append(
                    f"{fr_id} の受入基準にテストが対応づけられていません（{'/'.join(fids)} の"
                    f" coverage[] を合算しても覆われていない）: {str(criterion)[:60]!r}"
                )
        for key, fids_with_key in sorted(declared.items()):
            if key not in known:
                violations.append(
                    f"{'/'.join(fids_with_key)}/contract.yaml: coverage[] の acceptance_criterion が"
                    f" {fr_id} の受入基準と一致しません（原文のまま書いてください）: {key[:60]!r}"
                )
    return violations


def load_contracts(root: pathlib.Path, app_id: str) -> dict:
    """機能ごとの契約を読む。実装中の `03-features/` を優先し、無ければ設計時のドラフトを使う。

    `03-features/` だけを見ていると、worktree を作る前——つまり `solution-architect` が
    `check_traceability.py` を実行するよう指示されている設計フェーズ——では契約が 1 件も
    見つからず、`coverage[]` が空でも「OK: トレーサビリティは成立しています」と出ていた。
    **指示どおりに実行すると偽の安心を得る**状態だったので、`check_interfaces.py` と同じく
    設計時ドラフトも読む（並行実装に入る前に取りこぼしを潰せることがこの検査の主目的）。
    """
    contracts: dict = {}
    design_dir = root / "apps" / app_id / "02-design" / "features"
    if design_dir.is_dir():
        for path in sorted(design_dir.glob("*.contract.yaml")):
            try:
                contracts[path.name[: -len(".contract.yaml")]] = _common.load_yaml(path) or {}
            except Exception:  # noqa: BLE001
                continue
    for path in sorted((root / "apps" / app_id / "03-features").glob("*/contract.yaml")):
        try:
            contracts[path.parent.name] = _common.load_yaml(path) or {}
        except Exception:  # noqa: BLE001
            continue
    return contracts


def check_app(root: pathlib.Path, app_id: str) -> list[str]:
    app_dir = root / "apps" / app_id
    req_path = app_dir / "00-requirements" / "requirements.machine.yaml"
    arch_path = app_dir / "02-design" / "architecture.machine.yaml"
    if not req_path.exists() or not arch_path.exists():
        return []
    try:
        requirements = _common.load_yaml(req_path) or {}
        architecture = _common.load_yaml(arch_path) or {}
    except Exception as e:  # noqa: BLE001
        return [f"apps/{app_id}: YAML の読み込みに失敗しました: {e}"]
    return [
        f"apps/{app_id}: {v}"
        for v in check_traceability(requirements, architecture, load_contracts(root, app_id))
    ]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", help="app-id（省略時は apps/ 配下の全アプリ）")
    args = parser.parse_args(argv[1:])

    root = _common.repo_root()
    apps_dir = root / "apps"
    if not apps_dir.exists():
        print("apps/ がまだ存在しません。チェックをスキップします")
        return 0
    app_ids = [args.app] if args.app else [d.name for d in sorted(apps_dir.iterdir()) if d.is_dir()]

    violations: list[str] = []
    for app_id in app_ids:
        violations += check_app(root, app_id)

    if violations:
        print(f"NG: {len(violations)} 件の不整合が見つかりました:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("OK: 要件 → 機能 → テストのトレーサビリティは成立しています")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
