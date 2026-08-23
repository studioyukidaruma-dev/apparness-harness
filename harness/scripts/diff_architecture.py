#!/usr/bin/env python3
"""新旧の architecture.machine.yaml を比較し、追加・削除・変更された機能を機械的に算出する。
`diff-design` skill から呼ばれる。判定は features[] の内容（name/description/tech_stack/contract_ref）
に基づく。変更なしの機能は再利用でき、新規 worktree を作る必要がない。

使い方:
    python3 harness/scripts/diff_architecture.py <old_yaml> <new_yaml>
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402

COMPARE_FIELDS = ("name", "description", "tech_stack", "contract_ref")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"使い方: {argv[0]} <old_yaml> <new_yaml>", file=sys.stderr)
        return 2

    old_path, new_path = pathlib.Path(argv[1]), pathlib.Path(argv[2])
    if not old_path.exists() or not new_path.exists():
        print("エラー: 指定されたファイルが存在しません", file=sys.stderr)
        return 2

    old_arch = _common.load_yaml(old_path)
    new_arch = _common.load_yaml(new_path)

    old_features = {f["id"]: f for f in old_arch.get("features", [])}
    new_features = {f["id"]: f for f in new_arch.get("features", [])}

    added = sorted(set(new_features) - set(old_features))
    removed = sorted(set(old_features) - set(new_features))
    common = sorted(set(old_features) & set(new_features))

    changed = []
    unchanged = []
    for fid in common:
        old_f, new_f = old_features[fid], new_features[fid]
        if any(old_f.get(field) != new_f.get(field) for field in COMPARE_FIELDS):
            changed.append(fid)
        else:
            unchanged.append(fid)

    print(f"# 設計差分: {old_path.name} (v{old_arch.get('design_version')}) -> "
          f"{new_path.name} (v{new_arch.get('design_version')})")
    print()
    print(f"- 追加された機能 ({len(added)}): {', '.join(added) or 'なし'}")
    print(f"- 削除された機能 ({len(removed)}): {', '.join(removed) or 'なし'}")
    print(f"- 変更された機能 ({len(changed)}): {', '.join(changed) or 'なし'}")
    print(f"- 変更なし・再利用可能 ({len(unchanged)}): {', '.join(unchanged) or 'なし'}")
    print()
    print("追加・変更された機能は新しい feature-id（例: `<id>-v2`）を採番し、"
          "`new-feature-worktree` skill で新規 worktree を作成してください。")
    print("削除された機能は該当 status.yaml に `state: SUPERSEDED` を設定してください。")
    print("変更なしの機能はそのまま再利用し、新規 worktree を作らないでください。")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
