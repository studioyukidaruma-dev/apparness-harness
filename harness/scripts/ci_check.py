#!/usr/bin/env python3
"""CI（GitHub Actions 等）から呼ばれる、ハーネス規約の決定論的チェックの再検証スクリプト。

`harness/hooks/*.py` の Hook は Claude Code のセッション内でのみ効く。人間が直接 `git commit`
したり、Claude Code を経由しない別ツールで編集した場合はすり抜けられる。このスクリプトは
git リポジトリの最終状態（および比較対象コミットとの差分）に対して、Hook が課しているルールの
うち **アプリの技術スタックに依存しない範囲**を再検証する（サーバーサイドでの二重チェック）。

feature-builder/integrator が書く単体・結合テストの自動実行はアプリごとの技術スタックに
依存するため、このスクリプトの対象外（各アプリ側で用意する）。

チェック内容（対応する CONVENTIONS.md 7節の Hook Rule 番号）:
  A. machine-readable YAML の JSON Schema 検証
  B. Rule 1 相当: harness/**・.claude/**・.github/** への変更は `harness/<topic>` ブランチでのみ許可
  C. Rule 2/6 相当: `feature/<app>/<feature-id>` ブランチは自分の機能ディレクトリ
     （と任意 feature の status.yaml、Rule 4 が再生成する PROGRESS.md /
     STATE.machine.yaml）以外を変更してはいけない
  D. Rule 3 相当: contract.yaml の変更は、対応する状態が凍結ライン未満のときのみ許可
  E. Rule 7 相当: architecture.machine.yaml が status: APPROVED のとき、
     based_on_requirements_version が requirements.machine.yaml の現在の version と一致
  F. Rule 9 相当: status.yaml の state 遷移が妥当
  G. PROGRESS.md / STATE.machine.yaml が render_progress.py の出力と一致している（鮮度）
  I. Rule 10 相当: state が TESTED/INTEGRATED の機能に妥当な verification_receipt があり、
     検証を実行したコミット以降に実装が変更されていない
  J. interfaces[] の両端（producer の outputs[].json_schema / consumer の inputs[].json_schema）が
     構造的に整合している（型・必須項目の包含・enum の包含）
  K. 要件 → 機能 → テストのトレーサビリティ（MUST 要件の取りこぼし、存在しない FR ID の参照、
     覆うと宣言した要件に対応するテストが test_strategy.coverage[] にあるか）
  L. コンテキスト予算（CONVENTIONS.md と各 agent プロンプトの常時読み込みサイズの上限）
  M. 規範と手順の二重管理（CONVENTIONS.md と agent/skill プロンプトのほぼ同一な段落）
  N. Rule 11 相当: interfaces[] の全エッジが 04-integration/integration.machine.yaml の
     interface_coverage[] に結合テストとして対応づけられているか（宣言レベル。実行結果の
     真偽は run_integration_verification.py が JUnit XML と突合する）
  O. CONVENTIONS.md 凍結中の節新設拒否（15節で固定。凍結の経緯は DOGFOODING-LOG.md 参照）
  P. harness/CLAIMS.md（主張と証跡の対応表）に書かれた実証テストが harness/tests/ に実在し、
     実証テストが無い行には「なぜ実証できないか」が書かれている（表と実体の drift 防止）

Rule 5（必須Skillの充足）は CI に実行環境の Skill 有効化状態が存在しないため、
Rule 8（フェーズ節目のコミット強制）は push された時点で既にコミット済みであるため、
それぞれ対象外（再検証しても意味がない）。

B は `main`/`master` ブランチでは判定しない（DEFAULT_BRANCHES）。このハーネスは
`harness/<topic>` で作業して main へ fast-forward マージする運用が前提であり、fast-forward
マージは履歴が線形になるため、push 時点で「このコミットが元々どのブランチで作られたか」は
git 上から判別できない（正当な ff マージと、main への直接コミットが diff 上で区別できない）。
実地で main への push 時にこの誤検知が発生したため、この対応を入れた。B は `feature/**` 等の
非デフォルトブランチからの push・PR でのみ意味を持つ。

使い方:
    python3 harness/scripts/ci_check.py [--base <commit-ish>] [--head <commit-ish>] [--branch <name>]

exit code: 0 = 全チェック通過, 1 = 違反あり, 2 = 実行エラー
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402
import print_conventions  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "hooks" / "lib"))
import path_utils  # noqa: E402

EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
DEFAULT_BRANCHES = {"main", "master"}

SCHEMA_MAP = [
    ("apps/*/AUTONOMY.yaml", "autonomy.schema.json"),
    ("apps/*/00-requirements/requirements.machine.yaml", "requirements.schema.json"),
    ("apps/*/01-foundation/shared-kernel.yaml", "shared-kernel.schema.json"),
    ("apps/*/02-design/architecture.machine.yaml", "architecture.schema.json"),
    ("apps/*/02-design/features/*.contract.yaml", "feature-contract.schema.json"),
    ("apps/*/03-features/*/contract.yaml", "feature-contract.schema.json"),
    ("apps/*/03-features/*/status.yaml", "status.schema.json"),
    ("apps/*/04-integration/integration.machine.yaml", "integration.schema.json"),
]

FEATURE_BRANCH_RE = re.compile(r"^feature/([^/]+)/([^/]+)$")
CONTRACT_RE = re.compile(r"^apps/([^/]+)/03-features/([^/]+)/contract\.yaml$")
DESIGN_CONTRACT_RE = re.compile(r"^apps/([^/]+)/02-design/features/([^/]+)\.contract\.yaml$")
STATUS_RE = re.compile(r"^apps/([^/]+)/03-features/([^/]+)/status\.yaml$")
PROGRESS_ARTIFACT_RE = re.compile(r"^apps/([^/]+)/(PROGRESS\.md|STATE\.machine\.yaml)$")
TIMESTAMP_LINE_RE = re.compile(r"^(生成日時:|generated_at:).*$", re.MULTILINE)


def _run_git(args: list[str], cwd: pathlib.Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=cwd, timeout=15
        )
        if out.returncode != 0:
            return None
        return out.stdout
    except Exception:  # noqa: BLE001
        return None


def resolve_branch(root: pathlib.Path) -> str | None:
    out = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    if out is None:
        return None
    branch = out.strip()
    return None if branch == "HEAD" else branch  # detached HEAD


BASE_REF_CANDIDATES = ("origin/main", "main")


def resolve_base(root: pathlib.Path, head: str) -> str:
    """`head` と比較すべきベースを決める。

    `origin/main` 固定だと、ローカルの `origin/main` が古い（未 push で main が進んでいる）環境で
    **自分が触っていない main 側のコミットまで差分に含まれ**、`harness/**` を変更したという
    偽の違反が大量に出る（ドッグフーディングで 71 ファイル・数十件の誤検出を確認した。
    本物の違反がその中に埋もれるため、ローカルでの自己チェックに使えなかった）。

    そこで `origin/main` と ローカル `main` の両方からマージベースを求め、**より新しいほう**
    （他方の子孫であるほう）を選ぶ。どちらも解決できなければ従来どおり HEAD^ → 空ツリーへ落ちる。
    """
    bases = []
    for ref in BASE_REF_CANDIDATES:
        out = _run_git(["merge-base", ref, head], root)
        if out and out.strip():
            bases.append(out.strip())
    if bases:
        newest = bases[0]
        for candidate in bases[1:]:
            # newest が candidate の祖先なら、candidate のほうが新しい
            if _run_git(["merge-base", "--is-ancestor", newest, candidate], root) is not None:
                newest = candidate
        return newest
    out = _run_git(["rev-parse", f"{head}^"], root)
    if out:
        return out.strip()
    return EMPTY_TREE_SHA


def git_diff_files(base: str, head: str, root: pathlib.Path) -> list[tuple[str, str]]:
    """(status, path) のリストを返す。status は 'A'/'M'/'D'/'R100' 等。rename はリネーム後のパスを使う。"""
    out = _run_git(["diff", "--name-status", "--find-renames", base, head], root)
    if out is None:
        return []
    result = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        path = parts[-1]
        result.append((status, path))
    return result


def git_show(ref: str, path: str, root: pathlib.Path) -> str | None:
    return _run_git(["show", f"{ref}:{path}"], root)


def check_schema(root: pathlib.Path) -> list[str]:
    import json

    violations = []
    for pattern, schema_name in SCHEMA_MAP:
        schema_path = _common.harness_root(root) / "schemas" / schema_name
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except OSError:
            violations.append(f"{schema_path}: スキーマファイルが見つかりません")
            continue
        for yaml_path in sorted(root.glob(pattern)):
            try:
                instance = _common.load_yaml(yaml_path)
            except Exception as e:  # noqa: BLE001
                violations.append(f"{yaml_path.relative_to(root)}: YAML の読み込みに失敗しました: {e}")
                continue
            errors = _common.validate_against_schema(instance, schema)
            rel = yaml_path.relative_to(root)
            for err in errors:
                violations.append(f"{rel}: スキーマ違反 ({schema_name}): {err}")
    return violations


def check_harness_immutability(branch: str | None, changed: list[tuple[str, str]]) -> list[str]:
    if not branch or branch.startswith("harness/") or branch in DEFAULT_BRANCHES:
        # DEFAULT_BRANCHES を除外する理由: このハーネスは `harness/<topic>` ブランチで作業して
        # from main へ fast-forward マージする運用を前提にしている（8節）。fast-forward マージは
        # 履歴が線形になるため、push 時点で「このコミットが元々どのブランチで作られたか」という
        # 情報は git 上に残らない（main 上の押し込みも、正当な harness/<topic> の ff マージも、
        # diff 上は区別がつかない）。そのためこのチェックは push 時点の branch が実際に
        # `feature/**` 等の非デフォルトブランチである場合にのみ意味を持つ（feature-builder が
        # ローカル Hook をすり抜けて harness/ を直接触った場合はここで検知できる）。
        return []
    violations = []
    for _status, path in changed:
        if path == ".claude/settings.local.json":
            continue
        if path.startswith("harness/") or path.startswith(".claude/") or path.startswith(".github/"):
            violations.append(
                f"{path}: harness/.claude/.github 配下の変更は `harness/<topic>` ブランチでのみ"
                f"許可されています（現在のブランチ: {branch!r}）"
            )
    return violations


def check_feature_branch_scope(branch: str | None, changed: list[tuple[str, str]]) -> list[str]:
    if not branch:
        return []
    m = FEATURE_BRANCH_RE.match(branch)
    if not m:
        return []
    app_id, feature_id = m.groups()
    own_prefix = f"apps/{app_id}/03-features/{feature_id}/"
    violations = []
    for _status, path in changed:
        if path.startswith(own_prefix):
            continue
        if STATUS_RE.match(path):
            continue  # Rule2 の例外: 任意 feature の status.yaml は許可
        if PROGRESS_ARTIFACT_RE.match(path):
            # 自動生成のダッシュボード。status.yaml を進めるたびに Rule 4 が再生成するので、
            # feature ブランチで変更が出ること自体が正常（担当者が意図して書いたものではない）。
            continue
        if not path.startswith("apps/"):
            continue  # apps/ 以外（harness/等）は check_harness_immutability の管轄
        violations.append(f"{path}: `{branch}` ブランチの担当範囲外です（担当: {feature_id}）")
    return violations


def _status_field_at(rev: str, rel_path: str, root: pathlib.Path) -> str | None:
    """指定リビジョン時点の `status:`/`state:` を読む（ファイルが無ければ None）。"""
    out = _run_git(["show", f"{rev}:{rel_path}"], root)
    if out is None:
        return None
    for line in out.splitlines():
        m = re.match(r"^\s*(state|status)\s*:\s*(\S+)", line)
        if m:
            return m.group(2).strip("\"'")
    return None


def check_contract_freeze(base: str, changed: list[tuple[str, str]], root: pathlib.Path) -> list[str]:
    violations = []
    for _status, path in changed:
        m = CONTRACT_RE.match(path)
        if m:
            status_path = root / "apps" / m.group(1) / "03-features" / m.group(2) / "status.yaml"
            state = path_utils.read_state_field(status_path)
            if state is not None and state not in ("NOT_STARTED", "CONTRACT_DRAFTED"):
                violations.append(f"{path}: 対応する status.yaml が state={state} のため凍結されています")
            continue
        m = DESIGN_CONTRACT_RE.match(path)
        if m:
            # **ベース時点**の status で判定する。現在の status で判定すると、
            # 「契約を書く → 設計を承認する」を同一ブランチで行う正常フロー
            # （solution-architect の標準手順）が必ず不合格になる。
            # 凍結が意味を持つのは「承認済みの設計に後から契約を足す」場合だけで、
            # それはベース時点で既に APPROVED だったかどうかで区別できる。
            arch_rel = f"apps/{m.group(1)}/02-design/architecture.machine.yaml"
            arch_status = _status_field_at(base, arch_rel, root)
            if arch_status is not None and arch_status != "DRAFT":
                violations.append(
                    f"{path}: architecture.machine.yaml が status={arch_status} のため凍結されています"
                )
    return violations


def check_requirements_architecture_consistency(root: pathlib.Path) -> list[str]:
    apps_dir = root / "apps"
    if not apps_dir.exists():
        return []
    violations = []
    for app_dir in sorted(apps_dir.iterdir()):
        if not app_dir.is_dir():
            continue
        arch_path = app_dir / "02-design" / "architecture.machine.yaml"
        req_path = app_dir / "00-requirements" / "requirements.machine.yaml"
        if not arch_path.exists() or not req_path.exists():
            continue
        arch_content = arch_path.read_text(encoding="utf-8")
        status = path_utils.extract_scalar_field(arch_content, "status")
        if status != "APPROVED":
            continue
        based_on = path_utils.extract_scalar_field(arch_content, "based_on_requirements_version")
        req_version = path_utils.extract_scalar_field(req_path.read_text(encoding="utf-8"), "version")
        if req_version is not None and based_on != req_version:
            rel = arch_path.relative_to(root)
            violations.append(
                f"{rel}: based_on_requirements_version={based_on!r} が requirements の"
                f"現在の version={req_version!r} と不一致です"
            )
    return violations


def check_status_transitions(base: str, changed: list[tuple[str, str]], root: pathlib.Path) -> list[str]:
    violations = []
    for status_code, path in changed:
        if not STATUS_RE.match(path):
            continue
        if status_code.startswith("A"):
            continue  # 新規追加ファイルは旧状態がないので判定不能
        if status_code.startswith("D"):
            continue  # 削除は対象外
        old_content = git_show(base, path, root)
        old_state = path_utils.extract_scalar_field(old_content, "state") if old_content else None
        new_path = root / path
        if not new_path.exists():
            continue
        new_content = new_path.read_text(encoding="utf-8")
        new_state = path_utils.extract_scalar_field(new_content, "state")
        if new_state is None:
            continue
        old_history = path_utils.extract_state_history(old_content) if old_content else []
        reason = path_utils.validate_status_transition(old_state, new_state, old_history)
        if reason:
            violations.append(f"{path}: {reason}")
    return violations


def check_verification_receipts(root: pathlib.Path, head: str) -> list[str]:
    """項目 I: Rule 10（検証受領書ゲート）のサーバーサイド再検証。

    Hook（Rule 10）は「受領書の `commit` が書き込み時点の HEAD と一致すること」を要求するが、
    CI の時点では `state: TESTED` への変更自体が既にコミットされており HEAD は先に進んでいる。
    そのため CI では等価な条件に置き換えて判定する:

      1. 受領書の `commit` が HEAD の祖先であること（履歴に実在する検証であること）
      2. 受領書の `commit` から HEAD までの間に、その機能ディレクトリの中身
         （`status.yaml` を除く）が変更されていないこと
         ＝ 検証したあとに実装を書き換えていないこと
      3. 宣言されたすべてのコマンドが `exit_code: 0` であること、JUnit XML の集計値
         （空振り・失敗・スキップ率）が閾値を満たすこと

    2 が Hook 側の「commit 一致」条件に対応する本質的な部分である。
    """
    apps_dir = root / "apps"
    if not apps_dir.exists():
        return []
    violations = []
    for status_path in sorted(apps_dir.glob("*/03-features/*/status.yaml")):
        feature_dir = status_path.parent
        app_id = feature_dir.parent.parent.name
        rel_feature_dir = feature_dir.relative_to(root).as_posix()
        try:
            status = _common.load_yaml(status_path) or {}
        except Exception:  # noqa: BLE001
            continue  # YAML 自体の不正は項目 A の管轄
        state = status.get("state")
        if state not in ("TESTED", "INTEGRATED"):
            continue
        rel_status = status_path.relative_to(root).as_posix()

        shared_kernel_path = root / "apps" / app_id / "01-foundation" / "shared-kernel.yaml"
        contract_path = feature_dir / "contract.yaml"
        declaration = path_utils.merge_verification_declaration(
            shared_kernel_path.read_text(encoding="utf-8") if shared_kernel_path.exists() else "",
            contract_path.read_text(encoding="utf-8") if contract_path.exists() else "",
        )
        receipt = status.get("verification_receipt")
        if not declaration.get("test_command"):
            violations.append(
                f"{rel_status}: state={state} ですが `verification.test_command` がどこにも"
                f"宣言されていません（shared-kernel.yaml か contract.yaml に宣言してください）"
            )
            continue
        if not isinstance(receipt, dict) or not receipt.get("commit"):
            violations.append(f"{rel_status}: state={state} ですが `verification_receipt` がありません")
            continue

        commit = str(receipt["commit"])
        if _run_git(["merge-base", "--is-ancestor", commit, head], root) is None:
            violations.append(
                f"{rel_status}: `verification_receipt.commit`={commit!r} が HEAD の履歴に存在しません"
            )
            continue
        changed_since = _run_git(
            ["diff", "--name-only", commit, head, "--", rel_feature_dir], root
        )
        if changed_since:
            dirty = [
                line for line in changed_since.splitlines()
                if line.strip() and not line.strip().endswith("/status.yaml")
            ]
            if dirty:
                violations.append(
                    f"{rel_status}: 検証を実行したコミット({commit[:7]})より後に実装が変更されています"
                    f"（{', '.join(dirty[:3])}{' ほか' if len(dirty) > 3 else ''}）。"
                    f"run_verification.py を実行し直してください"
                )
                continue

        # 3: 宣言されたコマンドの終了コードと JUnit 集計値（HEAD 非依存の部分）
        for key, slot in path_utils.VERIFICATION_COMMANDS.items():
            if not declaration.get(key):
                continue
            entry = receipt.get(slot)
            if not isinstance(entry, dict):
                violations.append(f"{rel_status}: `verification.{key}` の実行記録（`{slot}`）が受領書にありません")
            elif entry.get("exit_code") != 0:
                violations.append(
                    f"{rel_status}: `{slot}.exit_code`={entry.get('exit_code')!r}（0 ではありません）"
                )
        if declaration.get("junit_xml"):
            reason = path_utils.validate_junit_summary(declaration, receipt.get("test") or {})
            if reason:
                violations.append(f"{rel_status}: {reason.splitlines()[0]}")
    return violations


def check_interface_schemas(root: pathlib.Path) -> list[str]:
    """項目 J: `interfaces[]` の両端の JSON Schema 突合（`check_interfaces.py` を再利用）。

    機能ごとに独立した worktree で並行実装するため、機能 A の出力と機能 B の入力の食い違いは
    統合時まで露見しない。JSON Schema の構造比較はスタック非依存なので、統合前に CI で検出できる。
    """
    import check_interfaces

    apps_dir = root / "apps"
    if not apps_dir.exists():
        return []
    violations = []
    for app_dir in sorted(apps_dir.iterdir()):
        if app_dir.is_dir():
            violations += check_interfaces.check_app(root, app_dir.name)
    return violations


def check_requirements_traceability(root: pathlib.Path) -> list[str]:
    """項目 K: 要件 → 機能 → テストのトレーサビリティ（`check_traceability.py` を再利用）。"""
    import check_traceability

    apps_dir = root / "apps"
    if not apps_dir.exists():
        return []
    violations = []
    for app_dir in sorted(apps_dir.iterdir()):
        if app_dir.is_dir():
            violations += check_traceability.check_app(root, app_dir.name)
    return violations


def check_integration_interface_coverage(root: pathlib.Path) -> list[str]:
    """項目 N: `interfaces[]` の全エッジが結合テストに対応づけられているか
    （`check_integration_traceability.py` を再利用。Rule 11）。"""
    import check_integration_traceability

    apps_dir = root / "apps"
    if not apps_dir.exists():
        return []
    violations = []
    for app_dir in sorted(apps_dir.iterdir()):
        if app_dir.is_dir():
            violations += check_integration_traceability.check_app(root, app_dir.name)
    return violations


CONVENTIONS_FROZEN_SECTION_COUNT = 15


def check_conventions_frozen_section_count(root: pathlib.Path) -> list[str]:
    """項目 O: `CONVENTIONS.md` は凍結中（15節で固定）。新しい節（16節以降）の追加を拒否する。

    凍結の経緯は `DOGFOODING-LOG.md`・memory `conventions-md-governance` を参照。「新しい節を
    立てるべきか」という最も主観の入る判断そのものを機械的に消すための強制（節を削る／既存の
    節の中身を直すことは妨げない。凍結が禁じるのは節の新設のみ）。
    """
    conventions_path = _common.harness_root(root) / "CONVENTIONS.md"
    if not conventions_path.exists():
        return []
    sections = print_conventions.parse_sections(conventions_path.read_text(encoding="utf-8"))
    if len(sections) > CONVENTIONS_FROZEN_SECTION_COUNT:
        numbers = ", ".join(str(n) for n, _h, _b in sections[CONVENTIONS_FROZEN_SECTION_COUNT:])
        return [
            f"CONVENTIONS.md: 凍結中のため節の新設はできません（{numbers} 節が追加されています）。"
            "既存の節の中に統合するか、ユーザーの明示的な許可を得て凍結を解除してください。"
        ]
    return []


# 項目 L: コンテキスト予算（CONVENTIONS.md 15節が単一の情報源。数値を変えるときは両方揃える）
CONTEXT_BUDGET_CONVENTIONS = 36_000
CONTEXT_BUDGET_AGENT = 12_000
CONTEXT_BUDGET_SESSION = 46_000


CONTEXT_BUDGET_MARKER_RE = re.compile(
    r"<!--\s*context-budget:\s*conventions-sections=([^\s>]*)\s*-->"
)


def attributed_conventions_bytes(agent_text: str, root: pathlib.Path) -> int:
    """このエージェントが実際に読み込む CONVENTIONS.md 相当のバイト数を見積もる。

    `<!-- context-budget: conventions-sections=6,9,13 -->`（`none` なら 0）というマーカーが
    あれば、そこに書かれた節だけを数える（`print_conventions.py --sections` で必要な節だけを
    読み込むよう絞り込んでいるエージェント向け。DOGFOODING-LOG.md F-047）。
    マーカーが無いエージェントは「`CONVENTIONS.md` をまるごと読む」とみなし、ファイル全体の
    サイズを安全側で計上する（マーカー導入前の全エージェントと同じ、従来の挙動）。
    存在しない節番号が書かれていた場合はその節を 0 バイトとして扱う（他のチェック対象ではない）。
    """
    conventions_path = _common.harness_root(root) / "CONVENTIONS.md"
    m = CONTEXT_BUDGET_MARKER_RE.search(agent_text)
    if not m:
        return conventions_path.stat().st_size if conventions_path.exists() else 0
    raw = m.group(1).strip()
    if raw in ("", "none"):
        return 0
    try:
        text = conventions_path.read_text(encoding="utf-8")
    except OSError:
        return 0
    sections = {n: body for n, _heading, body in print_conventions.parse_sections(text)}
    total = 0
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            number = int(token)
        except ValueError:
            continue
        total += len(sections.get(number, "").encode("utf-8"))
    return total


def check_context_budget(root: pathlib.Path) -> list[str]:
    """項目 L: 常時読み込まれるコンテキストの総量に上限を課す（CONVENTIONS.md 15節）。

    `CONVENTIONS.md`（の全部または一部）と agent プロンプトは、subagent が起動時に読み、
    そのセッションの間ずっと効き続ける。ここが太ると実際の作業に使える文脈と注意力が削られる。
    「気をつける」では守れないので機械的に強制する。該当フェーズで初めて読まれる文書
    （`harness/quality/*.md`・`harness/STACK_PACK.md` 等）は常時コストではないため対象外。
    """
    violations = []
    conventions = _common.harness_root(root) / "CONVENTIONS.md"
    conventions_size = conventions.stat().st_size if conventions.exists() else 0
    if conventions_size > CONTEXT_BUDGET_CONVENTIONS:
        violations.append(
            f"harness/CONVENTIONS.md: {conventions_size} バイトで上限 "
            f"{CONTEXT_BUDGET_CONVENTIONS} バイトを超えています。説明・背景・設計意図を "
            f"HARNESS_GUIDE.md へ移してください（CONVENTIONS.md 15節）"
        )

    worst_agent, worst_total = None, 0
    for agent_path in sorted((root / ".claude" / "agents").glob("*.md")):
        size = agent_path.stat().st_size
        if size > CONTEXT_BUDGET_AGENT:
            violations.append(
                f".claude/agents/{agent_path.name}: {size} バイトで上限 "
                f"{CONTEXT_BUDGET_AGENT} バイトを超えています（CONVENTIONS.md 15節）"
            )
        try:
            agent_text = agent_path.read_text(encoding="utf-8")
        except OSError:
            agent_text = ""
        total = size + attributed_conventions_bytes(agent_text, root)
        if total > worst_total:
            worst_agent, worst_total = agent_path.name, total

    if worst_total > CONTEXT_BUDGET_SESSION:
        violations.append(
            f"常時読み込みの合計（{worst_agent} が読む CONVENTIONS.md 相当 + 自身のプロンプト）が "
            f"{worst_total} バイトで上限 {CONTEXT_BUDGET_SESSION} バイトを超えています"
            f"（CONVENTIONS.md 15節）"
        )
    return violations


# 項目 M: 規範と手順の二重管理の検出（CONVENTIONS.md 15節が方針の単一の情報源）
DUPLICATION_SIMILARITY_THRESHOLD = 0.28
DUPLICATION_MIN_LENGTH = 100  # 正規化後の文字数。短い断片（コマンド1行等）は語彙が被るだけで別物
_DUPLICATION_NOISE_RE = re.compile(r"[\s`*\-—:：。、（）()「」\[\]#|]")


def _duplication_paragraphs(text: str) -> list[str]:
    """段落（空行区切り）に分割する。コードブロックも 1 段落として扱う。

    ASCII 図の丸ごとコピーが実際の drift 源だったため、散文だけを見るのでは足りない。
    """
    return [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]


def _duplication_grams(text: str, n: int = 3) -> set:
    """記号・空白を落とした文字 n-gram の集合。日本語なので単語分割はしない。"""
    s = _DUPLICATION_NOISE_RE.sub("", text)
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def _duplication_normalized_length(text: str) -> int:
    return len(_DUPLICATION_NOISE_RE.sub("", text))


def check_prompt_duplication(root: pathlib.Path) -> list[str]:
    """項目 M: `CONVENTIONS.md` と agent/skill プロンプトの二重管理を検出する（15節）。

    同じ規範を 2 箇所に書くと、片方だけ直して drift する。実際に起きた:
    Rule 7 に承認記録の同時性を足したとき `CONVENTIONS.md` 9節と `solution-architect` は
    直したが、同じ手順を持っていた `diff-design` skill を直し忘れ、**手順どおりに実行すると
    Hook に拒否される**状態になっていた（ドッグフーディング F-048）。

    15節の分担（規範は `CONVENTIONS.md`、手順は agent/skill、参照は節番号で）を守れば
    ほぼ一致する段落は生まれない。「気をつける」では守れないので機械的に検出する。

    近似コピー（言い換えを伴わない転記）だけを対象にする。一般則をフェーズ向けに具体化した
    記述（`solution-architect` が `MANUAL`/`SUPERVISED` を設計フェーズの言葉で言い直す等）は
    正当な役割分担なので、閾値と最小長でそこには掛からないようにしている。
    """
    conventions_path = _common.harness_root(root) / "CONVENTIONS.md"
    if not conventions_path.exists():
        return []
    conventions_text = conventions_path.read_text(encoding="utf-8")
    conventions_paragraphs = [
        (number, paragraph)
        for number, _heading, body in print_conventions.parse_sections(conventions_text)
        for paragraph in _duplication_paragraphs(body)
        if _duplication_normalized_length(paragraph) >= DUPLICATION_MIN_LENGTH
    ]
    if not conventions_paragraphs:
        return []
    conventions_grams = [(n, p, _duplication_grams(p)) for n, p in conventions_paragraphs]

    prompt_paths = sorted((root / ".claude" / "agents").glob("*.md")) + sorted(
        (root / ".claude" / "skills").glob("*/SKILL.md")
    )

    violations = []
    for prompt_path in prompt_paths:
        try:
            prompt_text = prompt_path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = prompt_path.relative_to(root)
        for paragraph in _duplication_paragraphs(prompt_text):
            if _duplication_normalized_length(paragraph) < DUPLICATION_MIN_LENGTH:
                continue
            grams = _duplication_grams(paragraph)
            if not grams:
                continue
            best_score, best_section = 0.0, None
            for number, _conv_paragraph, conv_grams in conventions_grams:
                score = len(grams & conv_grams) / len(grams | conv_grams)
                if score > best_score:
                    best_score, best_section = score, number
            if best_score >= DUPLICATION_SIMILARITY_THRESHOLD:
                excerpt = " ".join(paragraph.split())[:60]
                violations.append(
                    f"{rel}: CONVENTIONS.md {best_section}節とほぼ同じ内容を書いています"
                    f"（類似度 {best_score:.2f}）: 「{excerpt}…」\n"
                    f"    規範なら CONVENTIONS.md に残して節番号で参照し、手順ならこちらに一本化して"
                    f"CONVENTIONS.md 側を削ってください（15節）"
                )
    return violations


# 項目 P: 主張と証跡の対応表（harness/CLAIMS.md）と実体の drift 検出
CLAIMS_TEST_REF_RE = re.compile(r"([A-Za-z0-9_]+\.py)::([A-Za-z0-9_]+)")
CLAIMS_EMPTY_CELLS = {"", "—", "-", "–", "なし", "N/A"}


def _claims_table_rows(text: str) -> list[list[str]]:
    """Markdown の表の行（ヘッダ・区切り行を除く）をセルの配列にして返す。"""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [c.strip() for c in line[1:-1].split("|")]
        if len(cells) < 5:
            continue
        if cells[0] == "規則":
            continue  # ヘッダ
        if all(re.fullmatch(r"[-: ]+", c) for c in cells):
            continue  # 区切り
        rows.append(cells)
    return rows


def check_claims_coverage(root: pathlib.Path) -> list[str]:
    """項目 P: `harness/CLAIMS.md` の表が実体と食い違っていないことを検証する。

    この表は「ハーネスが何をブロックすると主張しているか」と「それを実証しているテスト」の
    対応表である（F-029/F-030 では中核ルール群が丸ごと空振りしていても気付けなかった）。
    表が実体から drift すれば索引としての価値が消えるので、機械的に見張る:

      1. 表に書かれた `<file>.py::<test>` が `harness/tests/` に実在すること
      2. 実証テストが空（`—` 等）の行には、「未実証の残余」が書かれていること
         （実証できない主張を、理由を書かずに置くことを許さない）
    """
    claims_path = _common.harness_root(root) / "CLAIMS.md"
    if not claims_path.exists():
        return []
    text = claims_path.read_text(encoding="utf-8")
    tests_dir = _common.harness_root(root) / "tests"

    violations = []
    sources: dict[str, str | None] = {}
    for file_name, test_name in CLAIMS_TEST_REF_RE.findall(text):
        if file_name not in sources:
            path = tests_dir / file_name
            sources[file_name] = path.read_text(encoding="utf-8") if path.is_file() else None
        source = sources[file_name]
        if source is None:
            violations.append(
                f"harness/CLAIMS.md: 実証テストのファイル harness/tests/{file_name} が存在しません"
            )
            continue
        if not re.search(rf"^def {re.escape(test_name)}\s*\(", source, re.MULTILINE):
            violations.append(
                f"harness/CLAIMS.md: harness/tests/{file_name} に {test_name} が存在しません"
                f"（テストを書くか、表の記載を実体に合わせてください）"
            )

    for cells in _claims_table_rows(text):
        rule, evidence, residual = cells[0], cells[2], cells[4]
        if evidence.strip("` ") in CLAIMS_EMPTY_CELLS and residual in CLAIMS_EMPTY_CELLS:
            violations.append(
                f"harness/CLAIMS.md: 「{rule}」に実証テストが無いのに、なぜ実証できないかが"
                f"書かれていません（「未実証の残余」列を埋めてください）"
            )
    return violations


def _strip_timestamp(text: str) -> str:
    return TIMESTAMP_LINE_RE.sub("", text)


def check_progress_freshness(root: pathlib.Path, branch: str | None = None) -> list[str]:
    # feature ブランチでは判定しない。`status.yaml` を進めるたびに PROGRESS.md /
    # STATE.machine.yaml の再生成が必要になるが、feature ブランチがそれをコミットすると
    # 項目 C（担当範囲外）に該当してしまう。つまり feature ブランチの HEAD は
    # **構造的に**この項目を満たせない。ダッシュボードの更新は integrator の責務とする。
    if branch and branch.startswith("feature/"):
        print("項目 G: feature ブランチのためスキップ（ダッシュボードの更新は integrator の責務）")
        return []
    apps_dir = root / "apps"
    if not apps_dir.exists():
        return []
    render_script = _common.harness_root(root) / "scripts" / "render_progress.py"
    violations = []
    for app_dir in sorted(apps_dir.iterdir()):
        if not app_dir.is_dir():
            continue
        progress_path = app_dir / "PROGRESS.md"
        state_path = app_dir / "STATE.machine.yaml"
        if not progress_path.exists() and not state_path.exists():
            continue  # まだ一度も生成されていない段階のアプリは対象外
        before_progress = progress_path.read_text(encoding="utf-8") if progress_path.exists() else ""
        before_state = state_path.read_text(encoding="utf-8") if state_path.exists() else ""

        result = subprocess.run(
            [sys.executable, str(render_script), "--app", app_dir.name],
            capture_output=True, text=True, cwd=root,
        )
        if result.returncode != 0:
            violations.append(f"{app_dir.name}: render_progress.py の実行に失敗しました: {result.stderr.strip()}")
            continue

        after_progress = progress_path.read_text(encoding="utf-8") if progress_path.exists() else ""
        after_state = state_path.read_text(encoding="utf-8") if state_path.exists() else ""
        # 判定のために実行した副作用を必ず戻す。戻さないとチェックを走らせただけで
        # ワークツリーが汚れ、feature ブランチでは項目 C に引っかかるファイルが残る。
        if progress_path.exists() and after_progress != before_progress:
            progress_path.write_text(before_progress, encoding="utf-8")
        if state_path.exists() and after_state != before_state:
            state_path.write_text(before_state, encoding="utf-8")
        if _strip_timestamp(before_progress) != _strip_timestamp(after_progress):
            violations.append(
                f"apps/{app_dir.name}/PROGRESS.md: status.yaml 群の内容と一致していません。"
                f"`python3 harness/scripts/render_progress.py --app {app_dir.name}` を実行してコミットしてください"
            )
        if _strip_timestamp(before_state) != _strip_timestamp(after_state):
            violations.append(
                f"apps/{app_dir.name}/STATE.machine.yaml: status.yaml 群の内容と一致していません。"
                f"`python3 harness/scripts/render_progress.py --app {app_dir.name}` を実行してコミットしてください"
            )
    return violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", help="比較対象のベース commit-ish（省略時は origin/main とのマージベース、"
                                        "それも無理なら HEAD^、それも無理なら空ツリー）")
    parser.add_argument("--head", default="HEAD", help="比較対象の HEAD commit-ish（既定: HEAD）")
    parser.add_argument("--branch", help="現在のブランチ名（省略時は git から推定。"
                                          "CI の detached HEAD では自動推定できないため明示指定を推奨）")
    args = parser.parse_args(argv[1:])

    root = _common.repo_root()
    base = args.base or resolve_base(root, args.head)
    branch = args.branch or resolve_branch(root)
    changed = git_diff_files(base, args.head, root)

    print(f"比較対象: base={base} head={args.head} branch={branch!r}")
    print(f"変更ファイル数: {len(changed)}")

    violations: list[str] = []
    violations += check_schema(root)
    violations += check_harness_immutability(branch, changed)
    violations += check_feature_branch_scope(branch, changed)
    violations += check_contract_freeze(base, changed, root)
    violations += check_requirements_architecture_consistency(root)
    violations += check_status_transitions(base, changed, root)
    violations += check_verification_receipts(root, args.head)
    violations += check_interface_schemas(root)
    violations += check_requirements_traceability(root)
    violations += check_integration_interface_coverage(root)
    violations += check_context_budget(root)
    violations += check_prompt_duplication(root)
    violations += check_progress_freshness(root, branch)
    violations += check_conventions_frozen_section_count(root)
    violations += check_claims_coverage(root)

    if violations:
        print(f"\nNG: {len(violations)} 件の違反が見つかりました:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print("\nOK: すべてのチェックを通過しました")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
