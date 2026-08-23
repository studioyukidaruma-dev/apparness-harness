#!/usr/bin/env python3
"""宣言された検証コマンドを実行し、結果を `status.yaml` の `verification_receipt` に記録する。

**このスクリプトはアプリの技術スタックを一切解釈しない。** `shared-kernel.yaml`（全機能共通）
および `contract.yaml`（機能個別の上書き）の `verification:` ブロックに宣言されたコマンド文字列を
そのままシェルに渡して起動し、終了コードだけを見る。これによりハーネスは「どのコマンドを走らせるか」
を知らないまま、「走らせたこと」と「通ったこと」を強制できる（CONVENTIONS.md 12節）。

    verification:
      working_dir:       "src"
      test_command:      "pytest -q --junitxml=../.verify/junit.xml"
      build_command:     "python -m build"
      typecheck_command: "mypy src"
      lint_command:      "ruff check ."
      junit_xml:         "../.verify/junit.xml"
      max_skip_ratio:    0.2

生成される受領書（`status.yaml`）:

    verification_receipt:
      commit: "a1b2c3d..."          # 実行時の HEAD。実装が進めば受領書は無効になる
      test:      { exit_code: 0, at: "...", tests: 42, failures: 0, errors: 0, skipped: 0 }
      build:     { exit_code: 0, at: "..." }
      ...

`state: TESTED` への書き込みは、Rule 10（`pre_tool_use_guard.py`）と CI の項目 I が、
この受領書の存在・全コマンドの `exit_code: 0`・`commit` と現在の HEAD の一致を検証する。
**受領書を手書きすることはできない**（Rule 10 が `status.yaml` への Edit/Write による
`verification_receipt` の変更自体を拒否する）。

使い方:
    python3 harness/scripts/run_verification.py --app <app-id> --feature <feature-id>

exit code: 0 = 受領書が Rule 10 を満たす, 1 = 満たさない, 2 = 実行エラー
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402
import junit_utils  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "hooks" / "lib"))
import path_utils  # noqa: E402

RECEIPT_KEY = "verification_receipt"
RECEIPT_HEADER = (
    "# harness/scripts/run_verification.py が生成する。**手書き禁止**\n"
    "# （Rule 10 が Edit/Write によるこのブロックの変更を拒否する）。\n"
)
RECEIPT_BLOCK_RE = re.compile(
    rf"^{RECEIPT_KEY}\s*:.*?(?=^(?![ \t\-])\S|\Z)", re.MULTILINE | re.DOTALL
)


def read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def run_command(label: str, command: str, cwd: pathlib.Path) -> dict:
    print(f"\n--- {label}: {command}  (cwd={cwd}) ---", flush=True)
    started = _common.now_iso()
    try:
        result = subprocess.run(command, shell=True, cwd=str(cwd))
        exit_code = result.returncode
    except OSError as e:
        print(f"起動に失敗しました: {e}", file=sys.stderr)
        exit_code = 127
    print(f"--- {label}: exit_code={exit_code} ---", flush=True)
    return {"exit_code": exit_code, "at": started}


def match_declared_tests(declared_test_ids: list[str], testcases: list[dict]) -> dict:
    """契約で宣言されたテスト識別子を JUnit XML の `<testcase>` と突合する（⑤ トレーサビリティ）。

    「受入基準に対応するテストが実在し、実際に成功した」ところまでを機械検証するための材料を
    受領書に残す。識別子の書式はハーネスが規定せず、代表的な組み立て方すべてと照合する
    （`junit_utils.testcase_identifiers`）。
    """
    missing, failed, matched = [], [], 0
    for test_id in declared_test_ids:
        cases = junit_utils.find_matching_testcases(testcases, test_id)
        if not cases:
            missing.append(test_id)
        elif any(c["status"] != junit_utils.PASSED for c in cases):
            failed.append(test_id)
        else:
            matched += 1
    result = {"declared": len(declared_test_ids), "matched": matched}
    if missing:
        result["missing"] = missing
    if failed:
        result["failed"] = failed
    print(
        f"トレーサビリティ: 宣言 {len(declared_test_ids)} 件 / 実在して成功 {matched} 件"
        + (f" / 見つからない {missing}" if missing else "")
        + (f" / 失敗 {failed}" if failed else "")
    )
    return result


def warn_about_generated_artifacts(
    before: dict, feature_dir: pathlib.Path, root: pathlib.Path
) -> None:
    """検証コマンドが機能ディレクトリ内に生成したファイルを警告する。

    JUnit XML やキャッシュ（`__pycache__` 等）をコミットしてしまうと、受領書の commit より後に
    機能ディレクトリが変更されたことになり、CI の項目 I が不合格になる。生成物は `.gitignore` に
    入れること。どのファイルが生成物かはスタックごとに違うため、ハーネスは**判定せず報告だけ**する。
    """
    rel_feature_dir = feature_dir.relative_to(root).as_posix()
    after = path_utils.parse_porcelain(path_utils.get_status_porcelain(str(feature_dir)))
    created = sorted(
        path for path, code in after.items()
        if before.get(path) != code and path.startswith(rel_feature_dir)
        and not path.endswith("/status.yaml")
    )
    if not created:
        return
    print(
        "\n警告: 検証コマンドが機能ディレクトリ内にファイルを生成/変更しました。"
        "\nこれらをコミットすると、受領書より後に実装が変更されたとみなされ CI の項目 I が"
        "不合格になります。`.gitignore` に追加してください:",
        file=sys.stderr,
    )
    for path in created[:10]:
        print(f"  - {path}", file=sys.stderr)
    if len(created) > 10:
        print(f"  - ... ほか {len(created) - 10} 件", file=sys.stderr)


def write_receipt(status_path: pathlib.Path, receipt: dict) -> None:
    """`status.yaml` の他の内容（コメント含む）を壊さずに受領書ブロックだけを差し替える。"""
    import yaml

    text = read_text(status_path)
    text = RECEIPT_BLOCK_RE.sub("", text)
    # 見出しコメントはブロック正規表現にマッチしないため、明示的に取り除く。
    # これをしないと検証を回すたびに 2 行ずつ蓄積する（ドッグフーディングで実証。
    # 2 回実行で 2 組になり、実装者が手で掃除する羽目になった）。
    text = text.replace(RECEIPT_HEADER, "")
    if not text.endswith("\n"):
        text += "\n"
    block = yaml.safe_dump({RECEIPT_KEY: receipt}, allow_unicode=True, sort_keys=False, default_flow_style=False)
    status_path.write_text(text + RECEIPT_HEADER + block, encoding="utf-8")


def resolve_declaration_for_check(root: pathlib.Path, app_id: str, feature_id: str) -> dict:
    """worktree を作る前でも解決できる形で `verification:` 宣言を組み立てる。

    機能個別の上書きは、実装用の `03-features/<id>/contract.yaml` があればそれを、
    無ければ設計時ドラフト `02-design/features/<id>.contract.yaml` を使う。
    """
    shared_kernel_path = root / "apps" / app_id / "01-foundation" / "shared-kernel.yaml"
    contract_path = root / "apps" / app_id / "03-features" / feature_id / "contract.yaml"
    if not contract_path.exists():
        contract_path = root / "apps" / app_id / "02-design" / "features" / f"{feature_id}.contract.yaml"
    return path_utils.merge_verification_declaration(
        read_text(shared_kernel_path), read_text(contract_path)
    )


def check_only(root: pathlib.Path, app_id: str, feature_id: str | None) -> int:
    """設計フェーズで `verification:` の宣言を検査する（F-023）。

    `--dry-run` は `03-features/<id>/status.yaml` の存在を前提にするため、宣言する場所である
    設計フェーズ——worktree を作る前——では使えなかった。「宣言しっぱなしにするな」と要求される
    一方で試す道具が無く、`test_command` の書き漏らしは実装フェーズでは回復不能になる。
    """
    if feature_id:
        feature_ids = [feature_id]
    else:
        architecture_path = root / "apps" / app_id / "02-design" / "architecture.machine.yaml"
        try:
            architecture = _common.load_yaml(architecture_path) or {}
        except Exception as e:  # noqa: BLE001
            print(f"エラー: {architecture_path} を読めませんでした: {e}", file=sys.stderr)
            return 2
        feature_ids = [
            f["id"] for f in architecture.get("features") or [] if isinstance(f, dict) and f.get("id")
        ]
        if not feature_ids:
            print(f"エラー: {architecture_path} の features[] が空です", file=sys.stderr)
            return 2

    problems: list[str] = []
    for fid in feature_ids:
        declaration = resolve_declaration_for_check(root, app_id, fid)
        print(f"[{fid}] 解決された verification 宣言:")
        if not declaration:
            print("  (宣言なし)")
            problems.append(f"{fid}: `verification:` がどこにも宣言されていません")
            continue
        for key, value in declaration.items():
            print(f"  {key}: {value}")
        if not declaration.get("test_command"):
            problems.append(
                f"{fid}: `test_command` が宣言されていません"
                "（この機能は TESTED にできません。実装フェーズでは追加できないので、"
                "shared-kernel.yaml か契約でいま宣言してください）"
            )

    if problems:
        print(f"\nNG: {len(problems)} 件の問題があります:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("\nOK: すべての機能について test_command が解決できます")
    print("（コマンドが実際に動くかは、この検査では分かりません。"
          "手元で一度実行して終了コードを確かめてください）")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", required=True, help="app-id")
    parser.add_argument("--feature", help="feature-id（--check-only では省略すると全機能を検査）")
    parser.add_argument("--dry-run", action="store_true", help="コマンドを実行せず、解決された宣言だけを表示する")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="worktree を作る前（設計フェーズ）に verification 宣言だけを検査する",
    )
    args = parser.parse_args(argv[1:])

    root = _common.repo_root()
    if args.check_only:
        return check_only(root, args.app, args.feature)
    if not args.feature:
        parser.error("--feature は必須です（--check-only のときだけ省略できます）")

    feature_dir = root / "apps" / args.app / "03-features" / args.feature
    status_path = feature_dir / "status.yaml"
    contract_path = feature_dir / "contract.yaml"
    shared_kernel_path = root / "apps" / args.app / "01-foundation" / "shared-kernel.yaml"

    if not status_path.exists():
        print(f"エラー: {status_path} が見つかりません", file=sys.stderr)
        return 2

    declaration = path_utils.merge_verification_declaration(
        read_text(shared_kernel_path), read_text(contract_path)
    )
    if not declaration:
        print(
            "エラー: `verification:` ブロックがどこにも宣言されていません。\n"
            f"  {shared_kernel_path.relative_to(root)}（全機能共通）または\n"
            f"  {contract_path.relative_to(root)}（機能個別）に宣言してください。",
            file=sys.stderr,
        )
        return 2

    print("解決された verification 宣言:")
    for key, value in declaration.items():
        print(f"  {key}: {value}")

    working_dir = feature_dir / str(declaration.get("working_dir") or ".")
    working_dir = working_dir.resolve()
    if not working_dir.is_dir():
        print(f"エラー: working_dir が存在しません: {working_dir}", file=sys.stderr)
        return 2
    if args.dry_run:
        return 0

    head = path_utils.get_head_commit(str(feature_dir))
    if not head:
        print("エラー: HEAD のコミットを取得できませんでした（git リポジトリ外？）", file=sys.stderr)
        return 2

    before = path_utils.parse_porcelain(path_utils.get_status_porcelain(str(feature_dir)))

    receipt: dict = {"commit": head}
    for key, slot in path_utils.VERIFICATION_COMMANDS.items():
        command = declaration.get(key)
        if not command:
            continue
        receipt[slot] = run_command(slot, str(command), working_dir)

    warn_about_generated_artifacts(before, feature_dir, root)

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
                declared_test_ids = path_utils.extract_declared_test_ids(read_text(contract_path))
                if declared_test_ids:
                    receipt["traceability"] = match_declared_tests(
                        declared_test_ids, summary["testcases"]
                    )

    write_receipt(status_path, receipt)
    print(f"\n受領書を書き込みました: {status_path.relative_to(root)}")

    reason = path_utils.validate_verification_receipt(
        declaration, receipt, head, path_utils.extract_declared_test_ids(read_text(contract_path))
    )
    if reason:
        print(f"\nNG: この受領書では `state: TESTED` にできません。\n{reason}", file=sys.stderr)
        return 1
    print("\nOK: 宣言されたすべての検証コマンドが成功しました（`state: TESTED` に進めます）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
