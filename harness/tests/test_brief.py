"""企画ブリーフ（`new_brief.py` / `check_brief.py` / `--brief` 取り込み）の検証。

ブリーフは要件定義の**入力**である。ここで固定したい主張は 4 つ:

1. 記入用フォーマットは常にスキーマを満たす（雛形とスキーマが drift しない）
2. 項目名の綴り違いは**黙って無視されず**、書式違反として落ちる
   （黙って無視すると「書いたのに伝わらない」という最悪の失敗になる）
3. 記入済みの項目は「未記入」に現れない＝対話で聞き直されない
4. 記入者が記号の扱いで迷わない（空欄に消すべき記号を置かない・「書き方の例」を真似れば書式を満たす・
   読み取れない書き方は行番号つきで案内する）
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import ci_check  # noqa: E402

HARNESS_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


@pytest.fixture()
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """ハーネス資源（schemas/scripts/templates）を持つ、git 管理下の一時リポジトリ。"""
    root = tmp_path / "repo"
    (root / "harness").mkdir(parents=True)
    for name in ("schemas", "scripts", "templates"):
        shutil.copytree(HARNESS_ROOT / name, root / "harness" / name)
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "tester"],
    ):
        _git(root, *args)
    return root


def run(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args], cwd=repo, capture_output=True, text=True
    )


def new_brief(repo: pathlib.Path, app_id: str = "demo-app", *extra: str) -> pathlib.Path:
    result = run(repo, "harness/scripts/new_brief.py", app_id, "デモ", *extra)
    assert result.returncode == 0, result.stderr
    return repo / "briefs" / f"{app_id}.brief.yaml"


def check_brief(repo: pathlib.Path, path: pathlib.Path) -> subprocess.CompletedProcess:
    return run(repo, "harness/scripts/check_brief.py", str(path), "--json")


def report(repo: pathlib.Path, path: pathlib.Path) -> dict:
    result = check_brief(repo, path)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# 1. 雛形とスキーマが drift しない
# ---------------------------------------------------------------------------


def test_the_generated_blank_brief_satisfies_the_schema(repo: pathlib.Path) -> None:
    brief = new_brief(repo)
    assert brief.exists()
    result = check_brief(repo, brief)
    assert result.returncode == 0, result.stderr


def test_new_brief_does_not_overwrite_without_force(repo: pathlib.Path) -> None:
    brief = new_brief(repo)
    brief.write_text(brief.read_text(encoding="utf-8") + "\n# 手を入れた\n", encoding="utf-8")
    again = run(repo, "harness/scripts/new_brief.py", "demo-app", "デモ")
    assert again.returncode == 2
    assert "既に存在します" in again.stderr
    assert "手を入れた" in brief.read_text(encoding="utf-8")


def test_new_brief_rejects_a_non_kebab_app_id(repo: pathlib.Path) -> None:
    result = run(repo, "harness/scripts/new_brief.py", "Demo_App")
    assert result.returncode == 2
    assert not (repo / "briefs").exists()


def test_the_generated_blank_brief_leaves_no_symbols_to_remove(repo: pathlib.Path) -> None:
    """記入欄に `[]` や `""` や `|` を置かない。記入者が「消すのか、中に書くのか」で迷わないようにする。"""
    import yaml

    brief = new_brief(repo)
    data = yaml.safe_load(brief.read_text(encoding="utf-8"))
    generated = {"brief_version", "app_id", "app_name", "created_at"}

    def blank_leaves(node, prefix=""):
        for key, value in node.items():
            path = f"{prefix}{key}"
            if isinstance(value, dict):
                yield from blank_leaves(value, f"{path}.")
            else:
                yield path, value

    leaves = [(p, v) for p, v in blank_leaves(data) if p not in generated]
    assert leaves
    assert [(p, v) for p, v in leaves if v is not None] == []


def _writing_examples(template: str) -> list[str]:
    """テンプレート中の「書き方の例:」ブロックを、コメント記号を外した YAML 片として取り出す。"""
    lines = template.splitlines()
    blocks: list[str] = []
    for index, line in enumerate(lines):
        if line != "# 書き方の例:":
            continue
        body = []
        for following in lines[index + 1 :]:
            if not following.startswith("#   "):
                break
            body.append(following[4:])
        blocks.append("\n".join(body) + "\n")
    return blocks


def test_every_writing_example_in_the_template_is_valid_and_counts_as_filled(
    repo: pathlib.Path,
) -> None:
    """テンプレートの「書き方の例」を真似て書けば、そのまま書式を満たし記入済みになる。"""
    template = (HARNESS_ROOT / "templates" / "brief.yaml.tmpl").read_text(encoding="utf-8")
    examples = _writing_examples(template)
    assert len(examples) >= 15
    for number, example in enumerate(examples):
        brief = repo / f"example-{number}.yaml"
        brief.write_text("brief_version: 1\n" + example, encoding="utf-8")
        result = check_brief(repo, brief)
        assert result.returncode == 0, f"{example}\n{result.stdout}{result.stderr}"
        data = json.loads(result.stdout)
        key = example.split(":", 1)[0]
        assert any(p == key or p.startswith(f"{key}.") for p in data["filled"]), example


def test_legacy_empty_markers_are_still_valid_and_blank(repo: pathlib.Path) -> None:
    brief = repo / "brief.yaml"
    brief.write_text(
        'brief_version: 1\nauthor: ""\ngoals: []\ntech:\n  preferred: []\nautonomy_mode: ""\n',
        encoding="utf-8",
    )
    data = report(repo, brief)
    missing = {m["path"] for m in data["missing"]}
    assert {"author", "goals", "tech.preferred", "autonomy_mode"} <= missing


# ---------------------------------------------------------------------------
# 2. 綴り違いを黙って無視しない
# ---------------------------------------------------------------------------


def test_a_misspelled_field_is_rejected(repo: pathlib.Path) -> None:
    brief = repo / "brief.yaml"
    brief.write_text(
        "brief_version: 1\npurpose: 何か作りたい\ntechs:\n  preferred: [\"Python\"]\n",
        encoding="utf-8",
    )
    result = check_brief(repo, brief)
    assert result.returncode == 1
    assert "techs" in result.stdout


def test_a_must_feature_without_a_title_is_rejected(repo: pathlib.Path) -> None:
    brief = repo / "brief.yaml"
    brief.write_text(
        "brief_version: 1\nmust_features:\n  - detail: タイトルが無い\n",
        encoding="utf-8",
    )
    assert check_brief(repo, brief).returncode == 1


def test_an_unknown_autonomy_mode_is_rejected(repo: pathlib.Path) -> None:
    brief = repo / "brief.yaml"
    brief.write_text("brief_version: 1\nautonomy_mode: FULLAUTO\n", encoding="utf-8")
    assert check_brief(repo, brief).returncode == 1


# ---------------------------------------------------------------------------
# 3. 記入済みは聞き直さない / 未記入は勝手に埋めない
# ---------------------------------------------------------------------------


def test_a_blank_brief_reports_the_essentials_as_must(repo: pathlib.Path) -> None:
    data = report(repo, new_brief(repo))
    must = {m["path"] for m in data["missing"] if m["level"] == "MUST"}
    assert must == {"purpose", "target_users", "goals", "must_features"}


def test_filled_fields_are_not_reported_as_missing(repo: pathlib.Path) -> None:
    brief = repo / "brief.yaml"
    brief.write_text(
        "brief_version: 1\n"
        "purpose: 備品の貸出を Excel から脱却させる\n"
        "target_users:\n  - 総務担当\n"
        "goals:\n  - 貸出状況をその場で確認できる\n"
        "tech:\n  preferred: [\"TypeScript\"]\n"
        "must_features:\n"
        "  - title: 貸出登録\n"
        "    detail: 誰がいつ何を借りたか記録する\n"
        "    acceptance: 登録すると一覧に借用者名と日時が表示される\n",
        encoding="utf-8",
    )
    data = report(repo, brief)
    missing = {m["path"] for m in data["missing"]}
    assert {"purpose", "target_users", "goals", "must_features", "tech.preferred"} <= set(
        data["filled"]
    )
    assert not any(p.startswith("must_features[0]") for p in missing)
    assert "tech.preferred" not in missing


def test_a_must_feature_without_acceptance_is_reported_as_must(repo: pathlib.Path) -> None:
    brief = repo / "brief.yaml"
    brief.write_text(
        "brief_version: 1\nmust_features:\n  - title: 貸出登録\n    detail: 記録する\n",
        encoding="utf-8",
    )
    data = report(repo, brief)
    rows = {m["path"]: m for m in data["missing"]}
    assert rows["must_features[0].acceptance"]["level"] == "MUST"
    assert "貸出登録" in rows["must_features[0].acceptance"]["label"]


def test_whitespace_only_is_treated_as_blank(repo: pathlib.Path) -> None:
    brief = repo / "brief.yaml"
    brief.write_text('brief_version: 1\npurpose: "   "\n', encoding="utf-8")
    data = report(repo, brief)
    assert "purpose" in {m["path"] for m in data["missing"]}


def test_a_list_with_only_empty_items_is_treated_as_blank(repo: pathlib.Path) -> None:
    brief = repo / "brief.yaml"
    brief.write_text("brief_version: 1\ngoals:\n  -\n  -\n", encoding="utf-8")
    data = report(repo, brief)
    assert "goals" in {m["path"] for m in data["missing"]}


def test_a_yaml_syntax_error_is_a_writing_error_with_the_line(repo: pathlib.Path) -> None:
    """YAML として読めない書き方は、記入者が直す誤りとして行番号つきで報告する（実行エラーにしない）。"""
    brief = repo / "brief.yaml"
    brief.write_text(
        "brief_version: 1\npurpose:\n  貸出を記録したい\n goals:\n  - 字下げがずれた項目名\n",
        encoding="utf-8",
    )
    result = check_brief(repo, brief)
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert "行目付近" in data["errors"][0]
    assert data["hints"]


def test_a_missing_brief_file_is_an_execution_error(repo: pathlib.Path) -> None:
    result = check_brief(repo, repo / "no-such.yaml")
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# 4. 雛形生成への取り込み
# ---------------------------------------------------------------------------


def test_the_scaffold_copies_the_brief_into_the_app(repo: pathlib.Path) -> None:
    brief = new_brief(repo, "demo-app")
    result = run(
        repo,
        "harness/scripts/new_app_scaffold.py",
        "demo-app",
        "デモアプリ",
        "SUPERVISED",
        "--brief",
        "briefs/demo-app.brief.yaml",
    )
    assert result.returncode == 0, result.stderr
    copied = repo / "apps" / "demo-app" / "00-requirements" / "brief.yaml"
    assert copied.read_text(encoding="utf-8") == brief.read_text(encoding="utf-8")


def test_the_scaffold_without_a_brief_creates_no_brief_file(repo: pathlib.Path) -> None:
    result = run(repo, "harness/scripts/new_app_scaffold.py", "demo-app", "デモアプリ")
    assert result.returncode == 0, result.stderr
    assert not (repo / "apps" / "demo-app" / "00-requirements" / "brief.yaml").exists()


def test_the_scaffold_stops_before_creating_anything_if_the_brief_is_missing(
    repo: pathlib.Path,
) -> None:
    result = run(
        repo,
        "harness/scripts/new_app_scaffold.py",
        "demo-app",
        "デモアプリ",
        "SUPERVISED",
        "--brief",
        "briefs/no-such.brief.yaml",
    )
    assert result.returncode == 2
    assert not (repo / "apps" / "demo-app").exists()


# ---------------------------------------------------------------------------
# 5. CI 項目 A の対象になっている
# ---------------------------------------------------------------------------


def test_ci_item_a_validates_briefs(repo: pathlib.Path) -> None:
    (repo / "briefs").mkdir()
    (repo / "briefs" / "demo-app.brief.yaml").write_text(
        "brief_version: 1\ntechs: []\n", encoding="utf-8"
    )
    violations = ci_check.check_schema(repo)
    assert any("brief" in v for v in violations)


def test_ci_item_a_accepts_the_generated_brief(repo: pathlib.Path) -> None:
    new_brief(repo)
    assert ci_check.check_schema(repo) == []
