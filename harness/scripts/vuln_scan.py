#!/usr/bin/env python3
"""apps/ 配下の依存ライブラリを OSV-Scanner で走査し、既知の脆弱性を検出する。

## なぜ npm audit / pip-audit ではなく OSV-Scanner か

ROADMAP.md では「npm audit/pip-audit/OSV等」を候補として挙げていたが、npm audit・pip-audit は
それぞれ npm・pip という特定のパッケージマネージャの CLI に同梱された、エコシステム固有のツールで
ある。このハーネスは「どんなアプリでも作れる」ことを前提にしており（HARNESS_GUIDE.md 12節）、
solution-architect がどの言語・パッケージマネージャを選ぶかは実行時にしか決まらない。
エコシステムごとに `npm audit` / `pip-audit` / `cargo audit` / `govulncheck` ... を出し分ける
ロジックを自前で持つと、対応エコシステットを増やすたびにハーネス側の保守が必要になる。

OSV-Scanner（https://github.com/google/osv-scanner）は「ディレクトリを再帰的に走査し、見つかった
lockfile の種類（package-lock.json / requirements.txt / poetry.lock / Cargo.lock / go.sum 等）を
自動判別して OSV データベースに問い合わせる」という、まさにこの用途のために作られた単一のツールで
あり、ハーネス側がエコシステムを列挙する必要がない。したがって v1 ではこれ一本を採用する。

## なぜ Hook ではなく CI に置くか

`harness/hooks/*.py` は「依存ゼロの標準ライブラリのみ」（CONVENTIONS.md 1節・HARNESS_GUIDE.md 5節）
で、ツール呼び出しのたびに毎回起動される。OSV-Scanner は外部バイナリであり、かつ既定では OSV.dev
への問い合わせにネットワークアクセスを要する。これを PreToolUse Hook に組み込むと、Edit/Write の
たびにネットワーク越しの脆弱性DB照会が走ることになり、決定論的・低コストであるべき Hook 層の
前提を壊す。そのため v1 では CI（`.github/workflows/harness-checks.yml`）でのみ実行する
（12節と同じ「ローカル Hook では検証できない範囲は CI に置く」という判断）。

## 位置づけ（品質保証の二層構造との関係、CONVENTIONS.md 10節）

`security-review`/`code-review` bundled skill（Layer 1.5）と同様、「入っていれば使う、入って
いなければ報告して続行する」という非致命的な位置づけにする。OSV-Scanner バイナリが PATH に
無ければエラーにはせず、その旨を報告して exit 0 で抜ける。CI ワークフロー側では常にインストール
してから本スクリプトを呼ぶため、CI 上では実質的に必ず実行される。ローカルで開発者が
`osv-scanner` を任意にインストールしていれば、このスクリプトはそのままローカルでも動く
（`ci_check.py`/`validate_status_transition.py` と同じ「人間/CI 両対応」の設計）。

## スコープ

`apps/` 配下（既定）または `--app <app-id>` で指定した単一アプリ配下を再帰的に走査する。
ハーネス自身が使う Python 依存（`harness/requirements.txt` の pyyaml/jsonschema）は対象外
（このスクリプトが検査するのは「生成されるアプリ」の依存であり、ハーネス自体の保守用依存では
ないため）。機能ごとに独立した worktree（03-features/<id>/）でも、統合後の 04-integration/assembly/
でも、lockfile さえあれば feature 境界を意識せず横断的に検出される。

exit code: 0 = 脆弱性なし（またはツール未導入/apps/ 未作成でスキップ）, 1 = 脆弱性あり,
2 = 実行エラー（OSV-Scanner 自体の異常終了など）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402

BINARY_NAME = "osv-scanner"


def find_binary() -> str | None:
    return shutil.which(BINARY_NAME)


def run_scan(binary: str, target: pathlib.Path) -> tuple[int, dict | None, str]:
    """OSV-Scanner を実行する。戻り値は (returncode, パース済みJSON or None, stderr)。"""
    result = subprocess.run(
        [
            binary,
            "scan",
            "source",
            "--recursive",
            "--allow-no-lockfiles",
            "--format",
            "json",
            str(target),
        ],
        capture_output=True,
        text=True,
    )
    # returncode: 0 = 脆弱性なし, 1 = 脆弱性あり（どちらも stdout に妥当な JSON が乗る）。
    # それ以外は OSV-Scanner 自体の実行エラー。
    if result.returncode not in (0, 1):
        return result.returncode, None, result.stderr
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else {"results": None}
    except json.JSONDecodeError as e:
        return result.returncode, None, f"OSV-Scanner の出力(JSON)の解析に失敗しました: {e}\n{result.stderr}"
    return result.returncode, data, result.stderr


def summarize(data: dict, root: pathlib.Path) -> list[str]:
    lines: list[str] = []
    for entry in data.get("results") or []:
        source_path = entry.get("source", {}).get("path", "?")
        try:
            rel = pathlib.Path(source_path).relative_to(root)
        except ValueError:
            rel = pathlib.Path(source_path)
        for pkg in entry.get("packages") or []:
            info = pkg.get("package", {})
            name = info.get("name", "?")
            version = info.get("version", "?")
            ecosystem = info.get("ecosystem", "?")
            for group in pkg.get("groups") or []:
                ids = ", ".join(group.get("aliases") or group.get("ids") or [])
                severity = group.get("max_severity") or "不明"
                lines.append(
                    f"{rel}: {name}@{version} ({ecosystem}) に既知の脆弱性 [{ids}] "
                    f"(CVSS概算: {severity})"
                )
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", help="apps/<app-id> のみを走査する（省略時は apps/ 全体）")
    args = parser.parse_args(argv[1:])

    root = _common.repo_root()
    apps_dir = root / "apps"
    target = (apps_dir / args.app) if args.app else apps_dir

    if not target.exists():
        print(f"{target.relative_to(root)} が存在しないためスキップします。")
        return 0

    binary = find_binary()
    if binary is None:
        print(
            f"警告: `{BINARY_NAME}` が見つかりません。脆弱性スキャンをスキップします "
            f"（https://github.com/google/osv-scanner からインストールしてください）。",
            file=sys.stderr,
        )
        return 0

    returncode, data, stderr_text = run_scan(binary, target)
    if data is None:
        print(f"OSV-Scanner の実行に失敗しました（exit={returncode}）:\n{stderr_text}", file=sys.stderr)
        return 2

    violations = summarize(data, root)
    if violations:
        print(f"NG: {len(violations)} 件の既知の脆弱性が見つかりました:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(f"OK: {target.relative_to(root)} 配下の依存ライブラリに既知の脆弱性は見つかりませんでした")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
