#!/usr/bin/env python3
"""apparness ハーネスを別のプロジェクトへコピーして導入・更新する。

使い方（ハーネスを clone したディレクトリから、導入先の git リポジトリを指定する）:

    python3 <apparness-harness>/harness/scripts/install.py <導入先> [--dry-run] [--force]

コピーではなく参照（git submodule・symlink）にしない理由:
ハーネスは `.claude/` と `harness/` が**導入先のルート直下に実体として**あることを前提にする。
Claude Code は直下の `.claude/` しか読まず、Hook は `$CLAUDE_PROJECT_DIR/harness/hooks/` を
起動し、Rule 1 は `harness/...` というパスで本体を保護する。さらに機能ごとの git worktree は
submodule の中身を持たない。参照型ではこのいずれかが崩れる（worktree 内でリンク切れ、
実体パス経由で Rule 1 をすり抜け）ことを実測で確認している。

導入するもの:
  - `harness/**`（キャッシュを除く）
  - `.claude/agents/**` と `.claude/skills/**`
  - `.github/workflows/harness-checks.yml`
  - `.claude/settings.json` の `hooks`（既存の設定には Hook の登録だけを足す）
  - `.gitignore` の管理ブロック

導入したファイルの一覧は `harness/install-manifest.json` に記録し、更新時は上流で消えた
ファイルだけを削除する。導入先が自分で足した agent や skill には触れない。

`harness/scripts/_common.py` を import しない。あちらは PyYAML を要求し、import 時に
メインリポジトリ側のスクリプトで起動し直すため、導入前のプロジェクトでは動かない。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

MANIFEST = "harness/install-manifest.json"
SETTINGS = ".claude/settings.json"
GITIGNORE = ".gitignore"
COPY_TREES = ("harness", ".claude/agents", ".claude/skills")
COPY_FILES = (".github/workflows/harness-checks.yml",)
EXCLUDED_DIR_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc"}

GITIGNORE_BEGIN = "# >>> apparness-harness（install.py が管理。手で編集しない）"
GITIGNORE_END = "# <<< apparness-harness"
GITIGNORE_LINES = (
    "apps/*/.worktrees/",
    "apps/*/PROGRESS.html",
    ".verify/",
    "__pycache__/",
    "*.pyc",
    ".pytest_cache/",
    ".claude/scheduled_tasks.lock",
    ".claude/settings.local.json",
)


class InstallError(Exception):
    pass


def source_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent.parent


def collect_files(src: pathlib.Path) -> list[str]:
    """導入対象のファイルを、ルートからの相対パス（`/` 区切り）で返す。"""
    files: list[str] = []
    for tree in COPY_TREES:
        base = src / tree
        if not base.is_dir():
            raise InstallError(f"導入元に {tree}/ がありません: {src}")
        for path in sorted(base.rglob("*")):
            rel = path.relative_to(src)
            if not path.is_file() or any(part in EXCLUDED_DIR_NAMES for part in rel.parts):
                continue
            if path.suffix in EXCLUDED_SUFFIXES or rel.as_posix() == MANIFEST:
                continue
            files.append(rel.as_posix())
    for name in COPY_FILES:
        if not (src / name).is_file():
            raise InstallError(f"導入元に {name} がありません: {src}")
        files.append(name)
    return files


def load_json(path: pathlib.Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"{label} を JSON として読めません（{exc}）") from exc
    if not isinstance(data, dict):
        raise InstallError(f"{label} の中身が JSON オブジェクトではありません")
    return data


def merge_hooks(settings: dict, remove: dict, add: dict) -> dict:
    """前回導入した Hook 登録を外し、今回の Hook 登録を足す。それ以外の設定には触れない。"""
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        raise InstallError(f"{SETTINGS} の hooks が JSON オブジェクトではありません")
    merged = {event: list(groups) for event, groups in hooks.items()}
    for event, groups in remove.items():
        merged[event] = [g for g in merged.get(event, []) if g not in groups]
    for event, groups in add.items():
        current = merged.setdefault(event, [])
        current.extend(g for g in groups if g not in current)
    return {**settings, "hooks": {event: groups for event, groups in merged.items() if groups}}


def render_gitignore(existing: str) -> str:
    block = "\n".join((GITIGNORE_BEGIN, *GITIGNORE_LINES, GITIGNORE_END)) + "\n"
    start = existing.find(GITIGNORE_BEGIN)
    end = existing.find(GITIGNORE_END)
    if start != -1 and end != -1 and start < end:
        tail = existing[end + len(GITIGNORE_END):]
        return existing[:start] + block + tail.lstrip("\n")
    if existing and not existing.endswith("\n"):
        existing += "\n"
    return existing + ("\n" if existing else "") + block


def has_unreleased_changes(src: pathlib.Path) -> bool:
    """導入元の CHANGELOG の `## [Unreleased]` に項目があるか（＝リリースされていない状態か）。

    未リリースの状態を導入すると、版は同じなのに中身が違うものが入り、導入先の CI 項目 Q が
    「ハーネス本体の変更に記録が無い」として落ちる。
    """
    try:
        text = (src / "harness" / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError:
        return False
    in_unreleased = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_unreleased = line[3:].strip().strip("[]").lower() == "unreleased"
        elif in_unreleased and line.strip().startswith("- "):
            return True
    return False


def plan(src: pathlib.Path, dst: pathlib.Path, force: bool) -> tuple[list[tuple[str, str]], dict]:
    """(操作, パス) の一覧と、書き込む内容を返す。ファイルシステムは変更しない。"""
    if not dst.is_dir():
        raise InstallError(f"導入先が存在しないか、ディレクトリではありません: {dst}")
    if not (dst / ".git").exists():
        raise InstallError(
            f"導入先が git リポジトリのルートではありません: {dst}\n"
            "ハーネスの判定は git に依存します。先に `git init` してください"
        )
    if dst.resolve() == src.resolve():
        raise InstallError("導入元と導入先が同じです")

    version_path = src / "harness" / "VERSION"
    try:
        version = version_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise InstallError(f"導入元の harness/VERSION を読めません: {exc}") from exc

    source_settings = load_json(src / SETTINGS, f"導入元の {SETTINGS}")
    if set(source_settings) != {"hooks"}:
        raise InstallError(f"導入元の {SETTINGS} に hooks 以外のキーがあります。合成方法が未定義です")

    manifest_path = dst / MANIFEST
    previous = load_json(manifest_path, MANIFEST) if manifest_path.exists() else None
    previous_files = set(previous.get("files", [])) if previous else set()

    files = collect_files(src)
    actions: list[tuple[str, str]] = []
    conflicts: list[str] = []
    for rel in files:
        target = dst / rel
        if not target.exists():
            actions.append(("追加", rel))
            continue
        if target.read_bytes() == (src / rel).read_bytes():
            continue
        if rel not in previous_files and not force:
            conflicts.append(rel)
        actions.append(("更新", rel))
    if conflicts:
        listed = "\n".join(f"  - {c}" for c in conflicts)
        raise InstallError(
            "導入先に、ハーネスと同じ場所で内容の異なるファイルがあります（上書きしません）:\n"
            f"{listed}\n上書きしてよい場合は --force を付けてください"
        )
    for rel in sorted(previous_files - set(files)):
        if (dst / rel).exists():
            actions.append(("削除", rel))

    settings_path = dst / SETTINGS
    current_settings = load_json(settings_path, SETTINGS) if settings_path.exists() else {}
    new_settings = merge_hooks(
        current_settings,
        remove=previous.get("settings_hooks", {}) if previous else {},
        add=source_settings["hooks"],
    )
    if new_settings != current_settings:
        actions.append(("更新" if settings_path.exists() else "追加", SETTINGS))

    gitignore_path = dst / GITIGNORE
    current_gitignore = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    new_gitignore = render_gitignore(current_gitignore)
    if new_gitignore != current_gitignore:
        actions.append(("更新" if gitignore_path.exists() else "追加", GITIGNORE))

    manifest = {
        "version": version,
        "files": files,
        "settings_hooks": source_settings["hooks"],
    }
    return actions, {
        "files": files,
        "remove": [rel for op, rel in actions if op == "削除"],
        "settings": new_settings,
        "gitignore": new_gitignore,
        "manifest": manifest,
        "previous_version": previous.get("version") if previous else None,
    }


def apply(src: pathlib.Path, dst: pathlib.Path, contents: dict) -> None:
    for rel in contents["files"]:
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((src / rel).read_bytes())
        target.chmod((src / rel).stat().st_mode & 0o777)
    for rel in contents["remove"]:
        (dst / rel).unlink()
    (dst / SETTINGS).write_text(
        json.dumps(contents["settings"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (dst / GITIGNORE).write_text(contents["gitignore"], encoding="utf-8")
    (dst / MANIFEST).write_text(
        json.dumps(contents["manifest"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="apparness ハーネスを別のプロジェクトへ導入・更新する")
    parser.add_argument("target", help="導入先の git リポジトリのルート")
    parser.add_argument("--dry-run", action="store_true", help="何をするかを表示するだけで書き込まない")
    parser.add_argument(
        "--force",
        action="store_true",
        help="前回ハーネスが導入していない、同じ場所にある内容の異なるファイルも上書きする",
    )
    args = parser.parse_args(argv)

    src = source_root()
    dst = pathlib.Path(args.target).resolve()
    try:
        actions, contents = plan(src, dst, args.force)
    except InstallError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1

    before = contents["previous_version"]
    after = contents["manifest"]["version"]
    header = f"v{before} → v{after}" if before else f"v{after} を新規導入"
    print(f"apparness ハーネス: {header}（導入先: {dst}）")
    if has_unreleased_changes(src):
        print(
            f"警告: 導入元に未リリースの変更があります（harness/CHANGELOG.md の Unreleased）。\n"
            f"  v{after} と同じ中身ではないため、導入先の CI 項目 Q が不合格になります。\n"
            f"  リリースのタグ（例: git -C {src} checkout v{after}）から導入してください",
            file=sys.stderr,
        )
    for op, rel in actions:
        print(f"  {op}: {rel}")
    if not actions:
        print("  変更はありません")

    if args.dry_run:
        print("--dry-run のため書き込んでいません")
        return 0

    apply(src, dst, contents)
    print("\n" + next_steps(dst))
    return 0


def next_steps(dst: pathlib.Path) -> str:
    steps = [
        "依存を入れる: pip install -r harness/requirements.txt",
        "動作確認: python3 harness/hooks/session_start_healthcheck.py < /dev/null",
    ]
    if any((dst / "apps").glob("*/PROGRESS.md")):
        # PROGRESS.md はハーネスの版を表示するため、版が変わると CI 項目 G（鮮度）が不合格になる。
        steps.append("既存アプリのダッシュボードを再生成する: python3 harness/scripts/render_progress.py --all")
    steps.append("変更をコミットする（ハーネス本体の変更なので harness/<topic> ブランチか main で行う）")
    return "次の手順:\n" + "\n".join(f"  {i}. {s}" for i, s in enumerate(steps, 1))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
