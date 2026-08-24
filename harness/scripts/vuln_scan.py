#!/usr/bin/env python3
"""apps/ 配下の依存ライブラリを OSV-Scanner で走査し、既知の脆弱性を検出する。

## なぜ npm audit / pip-audit ではなく OSV-Scanner か

初期のロードマップ（このリポジトリには残っていない）では「npm audit/pip-audit/OSV等」を候補として
挙げていたが、npm audit・pip-audit は
それぞれ npm・pip という特定のパッケージマネージャの CLI に同梱された、エコシステム固有のツールで
ある。このハーネスは「どんなアプリでも作れる」ことを前提にしており（docs/HARNESS_GUIDE.md 12節）、
solution-architect がどの言語・パッケージマネージャを選ぶかは実行時にしか決まらない。
エコシステムごとに `npm audit` / `pip-audit` / `cargo audit` / `govulncheck` ... を出し分ける
ロジックを自前で持つと、対応エコシステットを増やすたびにハーネス側の保守が必要になる。

OSV-Scanner（https://github.com/google/osv-scanner）は「ディレクトリを再帰的に走査し、見つかった
lockfile の種類（package-lock.json / requirements.txt / poetry.lock / Cargo.lock / go.sum 等）を
自動判別して OSV データベースに問い合わせる」という、まさにこの用途のために作られた単一のツールで
あり、ハーネス側がエコシステムを列挙する必要がない。したがって v1 ではこれ一本を採用する。

## なぜ Hook ではなく CI に置くか

`harness/hooks/*.py` は「依存ゼロの標準ライブラリのみ」（CONVENTIONS.md 1節・docs/HARNESS_GUIDE.md 5節）
で、ツール呼び出しのたびに毎回起動される。OSV-Scanner は外部バイナリであり、かつ既定では OSV.dev
への問い合わせにネットワークアクセスを要する。これを PreToolUse Hook に組み込むと、Edit/Write の
たびにネットワーク越しの脆弱性DB照会が走ることになり、決定論的・低コストであるべき Hook 層の
前提を壊す。そのため v1 では CI（`.github/workflows/harness-checks.yml`）でのみ実行する
（12節と同じ「ローカル Hook では検証できない範囲は CI に置く」という判断）。

## 位置づけ（品質保証の多層構造との関係、CONVENTIONS.md 10節）

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

## 抑制（`apps/<app-id>/.vuln-ignore`）

上流に修正が出ていない脆弱性を 1 件踏むと、そのアプリは CI を通せなくなる。逃げ道が無いと
運用側は最終的に job 自体を外す方向に倒れ、検査そのものが形骸化する。そこで抑制を用意するが、
「とりあえず無視」を恒久化させないため、**期限と理由を必須**にする。

    # 行頭 # はコメント、空行は無視
    GHSA-xxxx-yyyy-zzzz  expires=2026-12-31  reason=上流に fix 未提供。追跡: https://...

`expires` か `reason` を欠く行、日付の書式が不正な行、`expires` が実行日より過去の行が
1 件でもあれば、**走査結果に関わらず** exit 1 とし、ファイル名・行番号・理由を stderr に出す。
検証は抑制の適用より先に行う（期限切れの抑制が黙って効き続けることを防ぐ）。
`reason` には URL（`#` を含みうる）が入るため、行内コメントには対応しない。
抑制が効いた検出は黙って消さず、除外した ID と `expires` を標準出力に列挙する。

置き場所をハーネス本体ではなく `apps/<app-id>/` にしているのは、これがハーネスの規範ではなく
**アプリ側の受容判断**だからである。ID は OSV の文字列として扱うだけで、エコシステムごとの
分岐は持たない（このスクリプトが単一ツールに寄せている理由と同じ）。

exit code: 0 = 脆弱性なし（またはツール未導入/apps/ 未作成でスキップ）, 1 = 脆弱性あり
（または `.vuln-ignore` の不備）, 2 = 実行エラー（OSV-Scanner 自体の異常終了など）
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import shutil
import subprocess
import sys
from typing import NamedTuple

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


IGNORE_FILENAME = ".vuln-ignore"
# `<ID>  expires=YYYY-MM-DD  reason=<任意文字列>`。reason は行末まで（URL の `#` を含みうるため
# 行内コメントには対応しない）。順序は固定にして、書式違反を曖昧さなく指摘できるようにする。
IGNORE_LINE_RE = re.compile(
    r"^(?P<id>\S+)\s+expires=(?P<expires>\S+)\s+reason=(?P<reason>.+)$"
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class IgnoreRule(NamedTuple):
    """1 行の抑制指定。`scope` はこの抑制が及ぶディレクトリ（アプリのルート）。"""

    vuln_id: str
    expires: datetime.date
    reason: str
    origin: str  # "apps/<app-id>/.vuln-ignore:12"
    scope: pathlib.Path


def find_ignore_files(apps_dir: pathlib.Path, app_id: str | None) -> list[pathlib.Path]:
    """走査対象に含まれるアプリの `.vuln-ignore` を列挙する（アプリ直下のみ）。"""
    if app_id:
        app_dirs = [apps_dir / app_id]
    else:
        app_dirs = sorted(d for d in apps_dir.iterdir() if d.is_dir())
    return [d / IGNORE_FILENAME for d in app_dirs if (d / IGNORE_FILENAME).is_file()]


def parse_ignore_file(
    path: pathlib.Path, root: pathlib.Path, today: datetime.date
) -> tuple[list[IgnoreRule], list[str]]:
    """`.vuln-ignore` を 1 本読む。戻り値は (有効な抑制, 不備の説明)。

    不備は**握りつぶさずに呼び出し元へ返す**。期限切れや理由なしの抑制が黙って効き続けると、
    抑制機構そのものが「無視するための穴」に退化する。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [], [f"{_rel(path, root)}: 読み取れません（{type(exc).__name__}: {exc}）"]

    rules: list[IgnoreRule] = []
    errors: list[str] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        where = f"{_rel(path, root)}:{lineno}"
        m = IGNORE_LINE_RE.match(line)
        if m is None:
            if "expires=" not in line:
                errors.append(f"{where}: `expires=YYYY-MM-DD` がありません: {line}")
            elif "reason=" not in line:
                errors.append(f"{where}: `reason=<理由と追跡先>` がありません: {line}")
            else:
                errors.append(
                    f"{where}: 書式が不正です。"
                    f"`<ID>  expires=YYYY-MM-DD  reason=<理由>` の順で書いてください: {line}"
                )
            continue
        reason = m.group("reason").strip()
        if not reason:
            errors.append(f"{where}: `reason=` が空です（なぜ受容するのかと追跡先を書いてください）")
            continue
        expires_text = m.group("expires")
        if not DATE_RE.match(expires_text):
            errors.append(f"{where}: `expires` の書式が不正です（YYYY-MM-DD）: {expires_text}")
            continue
        try:
            expires = datetime.date.fromisoformat(expires_text)
        except ValueError:
            errors.append(f"{where}: `expires` が実在しない日付です: {expires_text}")
            continue
        if expires < today:
            errors.append(
                f"{where}: 抑制の期限が切れています（expires={expires_text}, 本日={today}）。"
                f"対応するか、根拠を書き直して期限を延ばしてください: {m.group('id')}"
            )
            continue
        rules.append(
            IgnoreRule(m.group("id"), expires, reason, where, path.parent.resolve())
        )
    return rules, errors


def load_ignore_rules(
    apps_dir: pathlib.Path, app_id: str | None, root: pathlib.Path, today: datetime.date
) -> tuple[list[IgnoreRule], list[str]]:
    rules: list[IgnoreRule] = []
    errors: list[str] = []
    for path in find_ignore_files(apps_dir, app_id):
        file_rules, file_errors = parse_ignore_file(path, root, today)
        rules += file_rules
        errors += file_errors
    return rules, errors


def _rel(path: pathlib.Path, root: pathlib.Path) -> pathlib.Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return path


def _matching_rule(
    rules: list[IgnoreRule], source_path: pathlib.Path, ids: list[str]
) -> IgnoreRule | None:
    """検出元のパスが抑制の scope 配下にあり、ID のどれかが一致する最初の抑制を返す。"""
    resolved = source_path.resolve()
    for rule in rules:
        if rule.vuln_id not in ids:
            continue
        try:
            resolved.relative_to(rule.scope)
        except ValueError:
            continue
        return rule
    return None


def summarize(
    data: dict, root: pathlib.Path, rules: list[IgnoreRule] | None = None
) -> tuple[list[str], list[str]]:
    """戻り値は (違反として報告する行, 抑制により除外した行)。

    `rules` を渡さなければ抑制は一切効かず、従来と同じ結果になる（後方互換）。
    """
    rules = rules or []
    violations: list[str] = []
    suppressed: list[str] = []
    for entry in data.get("results") or []:
        source_path = entry.get("source", {}).get("path", "?")
        source = pathlib.Path(source_path)
        try:
            rel = source.relative_to(root)
        except ValueError:
            rel = source
        for pkg in entry.get("packages") or []:
            info = pkg.get("package", {})
            name = info.get("name", "?")
            version = info.get("version", "?")
            ecosystem = info.get("ecosystem", "?")
            for group in pkg.get("groups") or []:
                id_list = list(group.get("aliases") or group.get("ids") or [])
                ids = ", ".join(id_list)
                severity = group.get("max_severity") or "不明"
                rule = _matching_rule(rules, source, id_list)
                if rule is not None:
                    suppressed.append(
                        f"{rel}: {name}@{version} ({ecosystem}) [{ids}] "
                        f"— expires={rule.expires.isoformat()} reason={rule.reason} "
                        f"（{rule.origin}）"
                    )
                    continue
                violations.append(
                    f"{rel}: {name}@{version} ({ecosystem}) に既知の脆弱性 [{ids}] "
                    f"(CVSS概算: {severity})"
                )
    return violations, suppressed


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

    # 抑制ファイルの検証は、走査より先・抑制の適用より先に行う。走査結果に関わらず不合格にする
    # （期限切れの抑制が「たまたま検出が無かった」ために見逃されることを防ぐ）。
    today = datetime.date.today()
    rules, ignore_errors = load_ignore_rules(apps_dir, args.app, root, today)
    if ignore_errors:
        print(
            f"NG: 抑制ファイル（{IGNORE_FILENAME}）に {len(ignore_errors)} 件の不備があります:",
            file=sys.stderr,
        )
        for e in ignore_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

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

    violations, suppressed = summarize(data, root, rules)
    if suppressed:
        # 黙って消さない。抑制されている限り、その事実は毎回目に入るところに出す。
        print(f"抑制中の検出が {len(suppressed)} 件あります（{IGNORE_FILENAME} により除外）:")
        for entry in suppressed:
            print(f"  - {entry}")

    if violations:
        print(f"NG: {len(violations)} 件の既知の脆弱性が見つかりました:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(f"OK: {target.relative_to(root)} 配下の依存ライブラリに既知の脆弱性は見つかりませんでした")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
