#!/usr/bin/env python3
"""SessionStart hook: 強制レイヤ自身が健全かを診断し、壊れていたら**可視化**する。

Hook は exit != 2 で終わると Claude Code から「判断なし＝通過」として扱われる。つまり
`python3` が見つからない・`import` に失敗する・タイムアウトする、のいずれでも
**全ルールが黙って無効化された状態で作業が続く**（F-A2）。決定論的強制を掲げるハーネスに
とって、これは「効いていないのに効いているつもり」という最悪の失敗の形である。

Hook の起動そのものは Claude Code 側の責務なので、ハーネスから止めることはできない。
できるのは「壊れていることを人間に見せる」ことだけであり、この Hook はそれを担う:

  1. セッション開始時に stderr へ明示的な警告を出す
  2. `additionalContext` として「このセッションでは決定論的強制が効いていない」ことを注入する
  3. `render_progress.py` が `PROGRESS.md` の先頭に同じ診断結果を表示する（`diagnose`）

同じ理由で、**git 情報が取れないために Rule の判定が劣化している**ことも警告する
（`diagnose_git_enforcement`）。判定はすべて git（作業ツリー・ブランチ・HEAD）に依存しており、
取れない場合は誤爆を避けるため通過側に倒れる。その劣化が不可視だと、強制が丸ごと効いていない
状態のまま作業が進む（F-029/F-030 と同型の失敗モード）。倒し方を変えるのではなく、見せる。

**依存ゼロ**（標準ライブラリのみ）。exit 0 固定（セッション開始自体は妨げない）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HOOKS_DIR, "lib"))

MIN_PYTHON = (3, 9)

# `.claude/settings.json` に登録されていなければならない Hook。
# ここが欠けると、そのイベントに紐づく Rule がまるごと効かなくなる。
REQUIRED_HOOKS = {
    "PreToolUse": ("pre_tool_use_guard.py", "Rule 1・2・3・5・6・7・9・10・11・12"),
    "PostToolUse": ("post_tool_use_sync.py", "Rule 4"),
    "Stop": ("stop_commit_guard.py", "Rule 8"),
    "SubagentStop": ("stop_commit_guard.py", "Rule 8（subagent）"),
}
# PostToolUse には事後検証ももう 1 本要る（Bash 経由の書き込みの巻き戻し）
REQUIRED_EXTRA_HOOKS = {"PostToolUse": ("post_tool_use_guard.py", "Bash 経由書き込みの事後検証")}

HOOK_MODULES = (
    "pre_tool_use_guard.py",
    "post_tool_use_guard.py",
    "post_tool_use_sync.py",
    "stop_commit_guard.py",
)

# `path_utils` が失っていてはいけない関数。ここが欠けると、呼び出し側の Rule は
# 例外で落ちるか（fail-closed 化前は）黙って通していた。
REQUIRED_PATH_UTILS = (
    "resolve_worktree_scope",
    "resolve_write_target",
    "extract_bash_candidate_paths",
    "validate_status_transition",
    "validate_verification_receipt",
    "detect_dangerous_bash_operation",
    "detect_dangerous_read",
    "capture_worktree_state",
)


def _repo_root(start: str) -> str:
    """`.claude/settings.json` を持つ最も近い上位ディレクトリ（git に依存しない）。"""
    current = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(current, ".claude", "settings.json")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.path.abspath(start)
        current = parent


def _import_hook_module(path: str):
    spec = importlib.util.spec_from_file_location(
        "healthcheck_probe_" + re.sub(r"\W", "_", os.path.basename(path)), path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"{path} の spec を作成できません")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def diagnose(repo_root: str, include_runtime: bool = True) -> list[str]:
    """強制レイヤの異常を列挙する。健全なら空リスト。

    `include_runtime=False` のときは**リポジトリの内容だけ**から判定できる項目に絞る。
    `PROGRESS.md` はコミットされる成果物であり、CI の項目 G が「再生成した結果と一致するか」を
    見るため、実行環境（Python のバージョン等）に依存する判定を混ぜると環境ごとに差分が出て
    構造的に不合格になる。実行環境の問題はセッション開始時の警告だけで伝える。
    """
    problems: list[str] = []
    hooks_dir = os.path.join(repo_root, "harness", "hooks")

    if include_runtime and sys.version_info < MIN_PYTHON:
        problems.append(
            f"Python が {'.'.join(map(str, sys.version_info[:3]))} です"
            f"（{'.'.join(map(str, MIN_PYTHON))} 以上が必要）"
        )

    # 1. hooks が import できるか（構文エラー・依存の混入・import 失敗を検出）
    for name in HOOK_MODULES:
        path = os.path.join(hooks_dir, name)
        if not os.path.isfile(path):
            problems.append(f"harness/hooks/{name} が存在しません")
            continue
        try:
            _import_hook_module(path)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"harness/hooks/{name} を import できません: {type(exc).__name__}: {exc}")

    # 2. path_utils の主要関数がそろっているか
    path_utils_path = os.path.join(hooks_dir, "lib", "path_utils.py")
    if not os.path.isfile(path_utils_path):
        problems.append("harness/hooks/lib/path_utils.py が存在しません")
    else:
        try:
            module = _import_hook_module(path_utils_path)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"path_utils を import できません: {type(exc).__name__}: {exc}")
        else:
            missing = [fn for fn in REQUIRED_PATH_UTILS if not callable(getattr(module, fn, None))]
            if missing:
                problems.append(f"path_utils に必要な関数がありません: {', '.join(missing)}")

    # 3. settings.json の hook 登録がそろっているか
    problems += _diagnose_settings(repo_root)
    return problems


def _diagnose_settings(repo_root: str) -> list[str]:
    settings_path = os.path.join(repo_root, ".claude", "settings.json")
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return [f".claude/settings.json を読めません（{type(exc).__name__}）。Hook は 1 つも登録されていません"]

    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return [".claude/settings.json に hooks が定義されていません。強制は一切効きません"]

    problems = []
    for event, (script, covered) in list(REQUIRED_HOOKS.items()) + list(REQUIRED_EXTRA_HOOKS.items()):
        registered = json.dumps(hooks.get(event, []), ensure_ascii=False)
        if script not in registered:
            problems.append(f"{event} に {script} が登録されていません（{covered} が効きません）")
    return problems


# git 情報が取れないときに判定が劣化する Rule。`(関数名, 取れないもの, 劣化の中身)`。
# 「通過に倒れる」ものと「拒否に倒れる」ものが混在するため、どちらに倒れるかまで書く。
GIT_ENFORCEMENT_CHECKS = (
    (
        "get_worktree_toplevel",
        "作業ツリーの位置",
        "Rule 2（担当範囲外の機能ディレクトリ）と Rule 6（feature worktree からの上位文書）が"
        "判定不能になり、**通過**します",
    ),
    (
        "get_current_branch",
        "現在のブランチ",
        "Rule 1 が `harness/` ブランチかどうかを判定できず、ハーネス本体への書き込みを"
        "一律**拒否**します",
    ),
    (
        "get_head_commit",
        "HEAD のコミット",
        "Rule 10・11 の受領書とコミットの照合が判定不能になり、**通過**します",
    ),
)


def diagnose_git_enforcement(cwd: str) -> list[str]:
    """git 情報が取れず、Rule の判定が劣化している項目を列挙する。健全なら空リスト。

    `diagnose()` とは別関数にしている。あちらは `PROGRESS.md`（コミットされる成果物）にも
    出るため、実行環境に依存する判定を混ぜられない（CI 項目 G）。git が使えるかどうかは
    まさにその実行環境の話なので、セッション開始時の警告だけで伝える。
    """
    try:
        import path_utils  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return []  # path_utils 自体の異常は diagnose() が報告する（二重に出さない）

    degraded: list[str] = []
    for fn_name, subject, effect in GIT_ENFORCEMENT_CHECKS:
        fn = getattr(path_utils, fn_name, None)
        if not callable(fn):
            continue  # 関数の欠落も diagnose() の担当
        try:
            value = fn(cwd)
        except Exception:  # noqa: BLE001
            value = None
        if not value:
            degraded.append(f"{subject}を特定できません → {effect}")
    return degraded


GIT_WARNING_HINT = (
    "次の一手: git リポジトリの中（`git init` 済みで、コミットが 1 件以上あるディレクトリ）で"
    "セッションを開始してください。git を使わない場所での作業は妨げませんが、"
    "上記の Rule は効いていません。"
)


HEALTHY_LINE = "強制レイヤ: **OK**（Hook 登録・import・主要関数がそろっています）"


def progress_line(repo_root: str) -> str:
    """`PROGRESS.md` の先頭に出す 1 行（`render_progress.py` から呼ばれる）。"""
    problems = diagnose(repo_root, include_runtime=False)
    if not problems:
        return f"- {HEALTHY_LINE}"
    detail = " / ".join(problems)
    return (
        f"- 強制レイヤ: **異常**（決定論的な強制が効いていない可能性があります）: {detail}"
    )


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    cwd = payload.get("cwd") or os.getcwd()
    repo_root = _repo_root(cwd)

    degraded = diagnose_git_enforcement(cwd)
    if degraded:
        print(
            "警告: git 情報を取得できないため、このセッションでは一部の Rule が判定不能です"
            "（判定不能なものは誤爆を避けるため通過側に倒れます。意図的な設計ですが、"
            "強制が効いていないことに変わりはありません）:\n"
            + "\n".join(f"  - {d}" for d in degraded)
            + "\n"
            + GIT_WARNING_HINT,
            file=sys.stderr,
        )

    problems = diagnose(repo_root)
    if not problems:
        return 0

    message = (
        "警告: ハーネスの強制レイヤが健全ではありません。"
        "このセッションでは決定論的強制が効いていない可能性があります:\n"
        + "\n".join(f"  - {p}" for p in problems)
        + "\n直してからセッションをやり直してください"
        "（`python3 harness/hooks/session_start_healthcheck.py < /dev/null` で再確認できます）。"
    )
    print(message, file=sys.stderr)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "【重要】このセッションではハーネスの決定論的強制（CONVENTIONS.md 7節 Rule 1-12）が"
                "効いていない可能性があります。検出された異常:\n"
                + "\n".join(f"- {p}" for p in problems)
                + "\nハーネス本体の修復を最優先し、それが済むまでアプリの作業を進めないでください。"
                "Hook が止めないからといって、規約に反する書き込みが許可されたわけではありません。"
            ),
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
