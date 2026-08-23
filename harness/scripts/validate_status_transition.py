#!/usr/bin/env python3
"""status.yaml の state 遷移が CONVENTIONS.md 5節の状態機械に沿っているかを判定する CLI。

実体は `harness/hooks/lib/path_utils.py` の `validate_status_transition`（単一の実装）。
`pre_tool_use_guard.py`（Rule 9、7節）が Edit/Write/MultiEdit のたびに自動でこれを強制するため、
このスクリプトは人間や CI が手動で「この遷移は妥当か」を確認する補助用途。

`old_state` が `BLOCKED` の場合、`--status-file` で status.yaml を渡すと `state_history[]` を
遡って直前の実質的な状態を復元し、そこからの遷移として判定する（渡さなければ判定不能として通す）。

使い方:
    python3 harness/scripts/validate_status_transition.py <old_state> <new_state> [--status-file <path>]

exit code: 0=妥当な遷移, 1=不正な遷移, 2=実行エラー（引数不足等）
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hooks" / "lib"))
import path_utils  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("old_state")
    parser.add_argument("new_state")
    parser.add_argument("--status-file", help="state_history[] を読む status.yaml のパス")
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit:
        return 2

    history = []
    if args.status_file:
        try:
            history = path_utils.extract_state_history(
                pathlib.Path(args.status_file).read_text(encoding="utf-8")
            )
        except OSError as e:
            print(f"エラー: {args.status_file} を読めません: {e}", file=sys.stderr)
            return 2

    reason = path_utils.validate_status_transition(args.old_state, args.new_state, history)
    if reason:
        print(reason, file=sys.stderr)
        return 1

    print(f"OK: {args.old_state} -> {args.new_state} は妥当な遷移です")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
