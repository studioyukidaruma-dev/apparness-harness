"""harness/scripts/* が共有するヘルパー。hooks/ からは呼ばれない（hooks は依存ゼロを保つ）。"""
from __future__ import annotations

import datetime
import pathlib
import subprocess
import sys

try:
    import yaml
except ImportError:
    print(
        "PyYAML が見つかりません。`pip install -r harness/requirements.txt` を実行してください。",
        file=sys.stderr,
    )
    raise


def repo_root() -> pathlib.Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return pathlib.Path(out.stdout.strip())


def load_yaml(path: pathlib.Path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(data, path: pathlib.Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def validate_against_schema(instance, schema: dict) -> list[str]:
    """エラーメッセージのリストを返す。空リストなら妥当。"""
    try:
        import jsonschema
    except ImportError:
        print(
            "jsonschema が見つかりません。`pip install -r harness/requirements.txt` を実行してください。",
            file=sys.stderr,
        )
        raise
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_template(template_text: str, values: dict[str, str]) -> str:
    """{{KEY}} 形式のプレースホルダを置換する。"""
    result = template_text
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", value)
    return result
