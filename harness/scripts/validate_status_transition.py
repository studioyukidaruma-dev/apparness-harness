#!/usr/bin/env python3
"""status.yaml の state 遷移が CONVENTIONS.md 5節の状態機械に沿っているかを判定する CLI。

実体は `harness/hooks/lib/path_utils.py` の `validate_status_transition`（単一の実装）。
`pre_tool_use_guard.py`（Rule 9、7節）が Edit/Write/MultiEdit のたびに自動でこれを強制するため、
このスクリプトは人間や CI が手動で「この遷移は妥当か」を確認する補助用途。

使い方:
    python3 harness/scripts/validate_status_transition.py <old_state> <new_state>

exit code: 0=妥当な遷移, 1=不正な遷移, 2=実行エラー（引数不足等）
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hooks" / "lib"))
import path_utils  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"使い方: {argv[0]} <old_state> <new_state>", file=sys.stderr)
        return 2

    old_state, new_state = argv[1], argv[2]
    reason = path_utils.validate_status_transition(old_state, new_state)
    if reason:
        print(reason, file=sys.stderr)
        return 1

    print(f"OK: {old_state} -> {new_state} は妥当な遷移です")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
