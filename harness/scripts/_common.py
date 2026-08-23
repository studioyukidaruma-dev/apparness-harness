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
    """**現在の作業ツリー**のルート。worktree の中なら worktree のルートを返す。

    アプリの生成物（`apps/**`）はこちらを基準にする。ハーネス本体の資源は
    `harness_root()` を使うこと（理由はそちらの docstring）。
    """
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return pathlib.Path(out.stdout.strip())


def main_repo_root(start: pathlib.Path | None = None) -> pathlib.Path:
    """git worktree の中から呼ばれても、**メインリポジトリ**のルートを返す。

    `start` を渡すとそのディレクトリを基準に判定する（省略時は cwd）。
    """
    base = pathlib.Path(start) if start else pathlib.Path.cwd()
    out = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=str(base),
        capture_output=True,
        text=True,
        check=True,
    )
    common = pathlib.Path(out.stdout.strip())
    if not common.is_absolute():
        common = base / common
    return common.resolve().parent


def harness_root(start: pathlib.Path | None = None) -> pathlib.Path:
    """ハーネス本体（スキーマ・テンプレート・規約）の置き場所。常にメインリポジトリ側。

    git worktree は追跡ファイルをそのまま複製するため、worktree の中にも `harness/` が現れる。
    しかしそれは **worktree を作った時点のスナップショット**であり、その後メイン側で
    ハーネスを改修しても追従しない。一方 Hook は `$CLAUDE_PROJECT_DIR/harness/hooks/...`＝
    常にメインリポジトリ側を実行する。

    このずれは実際に事故になった（F-049）: worktree 側の `feature-contract.schema.json` は
    `open_issues` を禁止したままで、Hook が許可した書き込みをローカル検証だけが不合格にし、
    「規約が嘘をついている」ように見える状態になった。**判定に使う定義は Hook と同じものに
    揃える**ため、ハーネス資源は必ずこちらから読む。

    git 情報が取れない場所（テストの一時ディレクトリ等）では `start / "harness"` に退避する。
    """
    base = pathlib.Path(start) if start else pathlib.Path.cwd()
    try:
        return main_repo_root(base) / "harness"
    except (subprocess.CalledProcessError, OSError):
        return base / "harness"


def resolve_harness_path(path: pathlib.Path) -> pathlib.Path:
    """`harness/` 配下を指すパスを、メインリポジトリ側の同じ相対位置へ読み替える。

    コマンドライン引数で `harness/schemas/...` を渡された場合、それは cwd 基準で解決され
    worktree 側のスナップショットを指してしまう。`harness_root()` と同じ理由で読み替える。
    """
    resolved = path.resolve()
    parts = resolved.parts
    if "harness" not in parts:
        return path
    index = len(parts) - 1 - parts[::-1].index("harness")
    remapped = harness_root().joinpath(*parts[index + 1:])
    return remapped if remapped.exists() else path


_REEXEC_MARKER = "APPARNESS_HARNESS_FROM_MAIN"


def reexec_from_main_repo_if_needed() -> None:
    """worktree 側の複製として起動されていたら、メインリポジトリ側の同名スクリプトで起動し直す。

    `harness_root()` がスキーマ等の**データ**のずれを直すのに対し、こちらは**コード**のずれを
    直す（F-049）。worktree の中の `harness/scripts/*.py` は作成時点のスナップショットなので、
    そのまま動かすと Hook が使う実装との食い違いに気づけない。

    作業ディレクトリは引き継ぐため、`repo_root()` は worktree のルートを返したままになる
    （＝**コードはメイン側、データは worktree 側**という本来の形になる）。
    この関数は import 時に一度だけ呼ばれ、`os.execve` でプロセスを置き換える。
    """
    import os

    if os.environ.get(_REEXEC_MARKER):
        return
    try:
        main = main_repo_root()
    except (subprocess.CalledProcessError, OSError):
        return  # git 情報が取れない場合は判定不能。何もしない（安全側）
    try:
        script = pathlib.Path(sys.argv[0]).resolve(strict=True)
    except (OSError, IndexError):
        return
    if script.is_relative_to(main):
        return  # 既にメインリポジトリ側で動いている
    candidate = main / "harness" / "scripts" / script.name
    if not candidate.is_file():
        return  # ハーネスのスクリプトではない（pytest 等から import された場合を含む）
    os.execve(
        sys.executable,
        [sys.executable, str(candidate), *sys.argv[1:]],
        {**os.environ, _REEXEC_MARKER: "1"},
    )


reexec_from_main_repo_if_needed()


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
