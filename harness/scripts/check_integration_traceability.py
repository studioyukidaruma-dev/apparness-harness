#!/usr/bin/env python3
"""`architecture.machine.yaml` の `interfaces[]` を `04-integration/integration.machine.yaml` の
`interface_coverage[]` と突合し、全エッジに結合テストが対応づけられているかを機械検証する。

`check_interfaces.py` は producer/consumer 両端の contract.yaml が宣言する JSON Schema 同士を
比較する（型・必須項目・enum の整合）。これは静的な宣言同士の比較なので、機能が実装内部で
定義する DI インターフェース（Ports 等）のように **どの契約にも現れない形** や、HTTP クエリ
文字列のエンコーディングのように **JSON Schema で表現できない約束事** はすり抜ける
（ドッグフーディング F-065/F-066）。

このチェックは「静的な形の整合」ではなく「実際に実装同士を繋いで動かした結合テストが
存在し、宣言されているか」を見る。テストが実際に成功したかどうかは
`run_integration_verification.py` が JUnit XML と突合し、受領書に記録する（Rule 11）。
ここでの判定は宣言レベル（テストの存在の宣言漏れ）にとどまる——実行結果の真偽は
CI では検証できないため（run_verification.py と同じ設計上の理由。CONVENTIONS.md 12節）。

判定内容:
  1. `interfaces[]` の各エッジが `interface_coverage[]` に 1 件以上の `test_ids` 付きで
     宣言されているか（取りこぼしの検出）
  2. `interface_coverage[]` に、`interfaces[]` に存在しないエッジが宣言されていないか

使い方:
    python3 harness/scripts/check_integration_traceability.py [--app <app-id>]

exit code: 0 = 問題なし, 1 = 不整合あり, 2 = 実行エラー
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "hooks" / "lib"))
import path_utils  # noqa: E402


def check_app(root: pathlib.Path, app_id: str) -> list[str]:
    arch_path = root / "apps" / app_id / "02-design" / "architecture.machine.yaml"
    integration_path = root / "apps" / app_id / "04-integration" / "integration.machine.yaml"
    if not arch_path.exists():
        return []
    try:
        architecture = _common.load_yaml(arch_path) or {}
    except Exception as e:  # noqa: BLE001
        return [f"apps/{app_id}: {arch_path.name} の読み込みに失敗しました: {e}"]
    interfaces = architecture.get("interfaces") or []
    if not interfaces:
        return []  # interfaces[] が無いアプリ（単一機能等）は対象外

    if not integration_path.exists():
        # 統合前（まだどの機能も TESTED に到達していない等）は判定不能として許可する。
        # integrator が実際に `state: INTEGRATED` へ進めようとする際は Rule 11 が別途強制する。
        return []

    try:
        integration_content = integration_path.read_text(encoding="utf-8")
        architecture_content = arch_path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"apps/{app_id}: 読み込みに失敗しました: {e}"]

    # `new_app_scaffold.py` が `integration.machine.yaml` を空テンプレート
    # （`interface_coverage: []`）として作成時点から生成するため、ファイルの存在だけでは
    # 「統合に未着手」を判定できない（F-074）。integrator がまだ1件も interface_coverage[]
    # を書いていない状態は、ファイル不存在時と同じく「判定不能として許可する」を維持する。
    record = path_utils.parse_simple_yaml(integration_content) if integration_content else {}
    coverage = (record.get("interface_coverage") if isinstance(record, dict) else None) or []
    if not coverage:
        return []

    gaps = path_utils.interface_coverage_gaps(architecture_content, integration_content)
    return [f"apps/{app_id}: {g}" for g in gaps]


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
    print("OK: interfaces[] の全エッジが結合テストに対応づけられています")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
