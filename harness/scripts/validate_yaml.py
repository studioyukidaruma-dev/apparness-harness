#!/usr/bin/env python3
"""YAML ファイルを JSON Schema で検証する汎用 CLI。

使い方:
    python3 harness/scripts/validate_yaml.py <yaml_file> <schema_file>

exit code: 0=妥当, 1=スキーマ違反, 2=実行エラー（ファイルなし等）
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"使い方: {argv[0]} <yaml_file> <schema_file>", file=sys.stderr)
        return 2

    yaml_path = pathlib.Path(argv[1])
    schema_path = pathlib.Path(argv[2])

    if not yaml_path.exists():
        print(f"エラー: {yaml_path} が存在しません", file=sys.stderr)
        return 2
    if not schema_path.exists():
        print(f"エラー: {schema_path} が存在しません", file=sys.stderr)
        return 2

    try:
        instance = _common.load_yaml(yaml_path)
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"エラー: 読み込みに失敗しました: {e}", file=sys.stderr)
        return 2

    errors = _common.validate_against_schema(instance, schema)
    if errors:
        print(f"NG: {yaml_path} は {schema_path} を満たしていません:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"OK: {yaml_path} は {schema_path} を満たしています")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
