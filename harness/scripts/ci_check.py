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
     （と任意 feature の status.yaml）以外を変更してはいけない
  D. Rule 3 相当: contract.yaml の変更は、対応する状態が凍結ライン未満のときのみ許可
  E. Rule 7 相当: architecture.machine.yaml が status: APPROVED のとき、
     based_on_requirements_version が requirements.machine.yaml の現在の version と一致
  F. Rule 9 相当: status.yaml の state 遷移が妥当
  G. PROGRESS.md / STATE.machine.yaml が render_progress.py の出力と一致している（鮮度）

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

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "hooks" / "lib"))
import path_utils  # noqa: E402

EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
DEFAULT_BRANCHES = {"main", "master"}

SCHEMA_MAP = [
    ("apps/*/AUTONOMY.yaml", "autonomy.schema.json"),
    ("apps/*/00-requirements/requirements.machine.yaml", "requirements.schema.json"),
    ("apps/*/02-design/architecture.machine.yaml", "architecture.schema.json"),
    ("apps/*/02-design/features/*.contract.yaml", "feature-contract.schema.json"),
    ("apps/*/03-features/*/contract.yaml", "feature-contract.schema.json"),
    ("apps/*/03-features/*/status.yaml", "status.schema.json"),
]

FEATURE_BRANCH_RE = re.compile(r"^feature/([^/]+)/([^/]+)$")
CONTRACT_RE = re.compile(r"^apps/([^/]+)/03-features/([^/]+)/contract\.yaml$")
DESIGN_CONTRACT_RE = re.compile(r"^apps/([^/]+)/02-design/features/([^/]+)\.contract\.yaml$")
STATUS_RE = re.compile(r"^apps/([^/]+)/03-features/([^/]+)/status\.yaml$")
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


def resolve_base(root: pathlib.Path, head: str) -> str:
    out = _run_git(["merge-base", "origin/main", head], root)
    if out:
        return out.strip()
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
        schema_path = root / "harness" / "schemas" / schema_name
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
        if not path.startswith("apps/"):
            continue  # apps/ 以外（harness/等）は check_harness_immutability の管轄
        violations.append(f"{path}: `{branch}` ブランチの担当範囲外です（担当: {feature_id}）")
    return violations


def check_contract_freeze(changed: list[tuple[str, str]], root: pathlib.Path) -> list[str]:
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
            arch_path = root / "apps" / m.group(1) / "02-design" / "architecture.machine.yaml"
            arch_status = path_utils.read_state_field(arch_path)
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
        reason = path_utils.validate_status_transition(old_state, new_state)
        if reason:
            violations.append(f"{path}: {reason}")
    return violations


def _strip_timestamp(text: str) -> str:
    return TIMESTAMP_LINE_RE.sub("", text)


def check_progress_freshness(root: pathlib.Path) -> list[str]:
    apps_dir = root / "apps"
    if not apps_dir.exists():
        return []
    render_script = root / "harness" / "scripts" / "render_progress.py"
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
    violations += check_contract_freeze(changed, root)
    violations += check_requirements_architecture_consistency(root)
    violations += check_status_transitions(base, changed, root)
    violations += check_progress_freshness(root)

    if violations:
        print(f"\nNG: {len(violations)} 件の違反が見つかりました:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print("\nOK: すべてのチェックを通過しました")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
