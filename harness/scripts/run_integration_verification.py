#!/usr/bin/env python3
"""宣言された `04-integration/assembly` の検証コマンドを実行し、結果を
`integration.machine.yaml` の `verification_receipt` に記録する（`run_verification.py` の
統合版。Rule 11、CONVENTIONS.md 12/13節）。

`03-features/<feature-id>/` は機能ごとに独立した契約と受領書を持つが、`04-integration/` は
複数機能を実際に繋ぐ integrator 自身の成果物であり、どの機能にも属さない。そのためこの
スクリプトは `status.yaml` ではなく `apps/<app-id>/04-integration/integration.machine.yaml` に
対して同じ「宣言 → 実行 → 受領書 → ゲート」の仕組みを適用する。**このスクリプトはアプリの
技術スタックを一切解釈しない**（`run_verification.py` と同じ設計原則）。

`interface_coverage[]` に宣言された `test_ids` は、`architecture.machine.yaml` の
`interfaces[]` の各エッジに対応する結合テストの識別子。JUnit XML と突合し、実在して
成功したことまで機械検証する（`check_interfaces.py` が静的な契約同士の整合を見るのに対し、
こちらは実際に実装同士を繋いで動かした結果を見る。F-065/F-066 対策）。

使い方:
    python3 harness/scripts/run_integration_verification.py --app <app-id>
    python3 harness/scripts/run_integration_verification.py --app <app-id> --dry-run

exit code: 0 = 受領書が Rule 11 を満たす, 1 = 満たさない, 2 = 実行エラー
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402
import junit_utils  # noqa: E402
import run_verification  # noqa: E402  実行・受領書生成の共通ロジックを再利用する

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "hooks" / "lib"))
import path_utils  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", required=True, help="app-id")
    parser.add_argument("--dry-run", action="store_true", help="コマンドを実行せず、解決された宣言だけを表示する")
    args = parser.parse_args(argv[1:])

    root = _common.repo_root()
    integration_dir = root / "apps" / args.app / "04-integration"
    integration_path = integration_dir / "integration.machine.yaml"
    arch_path = root / "apps" / args.app / "02-design" / "architecture.machine.yaml"

    if not integration_path.exists():
        print(f"エラー: {integration_path} が見つかりません", file=sys.stderr)
        return 2

    declaration = (_common.load_yaml(integration_path) or {}).get("verification") or {}
    if not declaration.get("test_command"):
        print(
            f"エラー: `verification.test_command` が {integration_path.relative_to(root)} に"
            "宣言されていません。", file=sys.stderr,
        )
        return 2

    print("解決された verification 宣言:")
    for key, value in declaration.items():
        print(f"  {key}: {value}")

    working_dir = (integration_dir / str(declaration.get("working_dir") or "assembly")).resolve()
    if not working_dir.is_dir():
        print(f"エラー: working_dir が存在しません: {working_dir}", file=sys.stderr)
        return 2
    if args.dry_run:
        return 0

    head = path_utils.get_head_commit(str(integration_dir))
    if not head:
        print("エラー: HEAD のコミットを取得できませんでした（git リポジトリ外？）", file=sys.stderr)
        return 2

    before = path_utils.parse_porcelain(path_utils.get_status_porcelain(str(integration_dir)))
    declared_test_ids = path_utils.extract_declared_interface_test_ids(
        run_verification.read_text(integration_path)
    )

    receipt: dict = {"commit": head}
    for key, slot in path_utils.VERIFICATION_COMMANDS.items():
        command = declaration.get(key)
        if not command:
            continue
        receipt[slot] = run_verification.run_command(slot, str(command), working_dir)

    run_verification.warn_about_generated_artifacts(before, integration_dir, root)

    junit_rel = declaration.get("junit_xml")
    if junit_rel and "test" in receipt:
        junit_path = (working_dir / str(junit_rel)).resolve()
        if not junit_path.exists():
            print(f"\n警告: junit_xml が生成されていません: {junit_path}", file=sys.stderr)
        else:
            try:
                summary = junit_utils.parse_junit_xml(junit_path)
            except Exception as e:  # noqa: BLE001
                print(f"\n警告: JUnit XML の解析に失敗しました: {e}", file=sys.stderr)
            else:
                receipt["test"].update(
                    {
                        "tests": summary["tests"],
                        "failures": summary["failures"],
                        "errors": summary["errors"],
                        "skipped": summary["skipped"],
                    }
                )
                print(
                    f"\nJUnit XML: tests={summary['tests']} failures={summary['failures']} "
                    f"errors={summary['errors']} skipped={summary['skipped']}"
                )
                if declared_test_ids:
                    receipt["traceability"] = run_verification.match_declared_tests(
                        declared_test_ids, summary["testcases"]
                    )

    run_verification.write_receipt(integration_path, receipt)
    print(f"\n受領書を書き込みました: {integration_path.relative_to(root)}")

    reason = path_utils.validate_verification_receipt(declaration, receipt, head, declared_test_ids)
    if reason:
        print(f"\nNG: この受領書では `state: INTEGRATED` にできません。\n{reason}", file=sys.stderr)
        return 1

    architecture_content = run_verification.read_text(arch_path) if arch_path.exists() else ""
    gaps = path_utils.interface_coverage_gaps(
        architecture_content, run_verification.read_text(integration_path)
    )
    if gaps:
        print(
            "\nNG: interfaces[] の一部が interface_coverage[] でカバーされていません:",
            file=sys.stderr,
        )
        for g in gaps:
            print(f"  - {g}", file=sys.stderr)
        return 1

    print(
        "\nOK: 宣言されたすべての検証コマンドが成功し、interfaces[] の全エッジが"
        "結合テストでカバーされています（`state: INTEGRATED` に進めます）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
