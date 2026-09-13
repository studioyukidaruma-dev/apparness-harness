"""コピー型インストーラ（`harness/scripts/install.py`）の検証。

導入先で Hook・agent・CI が「ハーネス本体のリポジトリと同じ配置」で動くことが要点。
導入先が自分で持っている設定やファイルを壊さないことも同じくらい重要なので、両方を見る。
"""
from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

import install

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

HOOKS = {
    "PreToolUse": [
        {"matcher": "Edit", "hooks": [{"type": "command", "command": "python3 guard.py"}]}
    ]
}


def git_init(path: pathlib.Path) -> pathlib.Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path


def fake_source(tmp_path: pathlib.Path, hooks: dict = HOOKS, version: str = "1.0.0") -> pathlib.Path:
    src = tmp_path / "src"
    for rel, text in {
        "harness/VERSION": version + "\n",
        "harness/CONVENTIONS.md": "規約\n",
        "harness/scripts/tool.py": "print('x')\n",
        ".claude/agents/builder.md": "agent\n",
        ".claude/skills/init-app/SKILL.md": "skill\n",
        ".github/workflows/harness-checks.yml": "name: harness-checks\n",
    }.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    (src / ".claude" / "settings.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    return src


def run(src: pathlib.Path, dst: pathlib.Path, force: bool = False) -> list[tuple[str, str]]:
    actions, contents = install.plan(src, dst, force)
    install.apply(src, dst, contents)
    return actions


def read_settings(dst: pathlib.Path) -> dict:
    return json.loads((dst / ".claude" / "settings.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------
# 新規導入
# --------------------------------------------------------------------------------------

def test_a_fresh_install_places_the_harness_at_the_project_root(tmp_path) -> None:
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    run(src, dst)
    for rel in (
        "harness/VERSION",
        "harness/scripts/tool.py",
        ".claude/agents/builder.md",
        ".claude/skills/init-app/SKILL.md",
        ".github/workflows/harness-checks.yml",
    ):
        assert (dst / rel).read_bytes() == (src / rel).read_bytes()
    assert read_settings(dst) == {"hooks": HOOKS}
    manifest = json.loads((dst / install.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["version"] == "1.0.0"
    assert "harness/scripts/tool.py" in manifest["files"]


def test_caches_are_not_copied(tmp_path) -> None:
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    (src / "harness" / "scripts" / "__pycache__").mkdir()
    (src / "harness" / "scripts" / "__pycache__" / "tool.cpython-312.pyc").write_bytes(b"x")
    (src / "harness" / "scripts" / "stray.pyc").write_bytes(b"x")
    run(src, dst)
    assert not (dst / "harness" / "scripts" / "__pycache__").exists()
    assert not (dst / "harness" / "scripts" / "stray.pyc").exists()


def test_the_executable_bit_is_preserved(tmp_path) -> None:
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    (src / "harness" / "scripts" / "tool.py").chmod(0o755)
    run(src, dst)
    assert (dst / "harness" / "scripts" / "tool.py").stat().st_mode & 0o111


def test_the_real_repository_can_be_installed(tmp_path) -> None:
    """本物のハーネスを導入すると、自己診断が見る Hook 登録と実体がそろう。"""
    dst = git_init(tmp_path / "dst")
    run(REPO_ROOT, dst)
    assert (dst / "harness" / "hooks" / "pre_tool_use_guard.py").is_file()
    assert (dst / "harness" / "CHANGELOG.md").is_file()
    expected = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert read_settings(dst)["hooks"] == expected["hooks"]
    assert not (dst / "docs").exists()


# --------------------------------------------------------------------------------------
# 導入先の既存資産を壊さない
# --------------------------------------------------------------------------------------

def test_existing_settings_are_kept_and_only_hooks_are_added(tmp_path) -> None:
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    own_hook = {"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]}
    (dst / ".claude").mkdir()
    (dst / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(ls)"]}, "hooks": {"PreToolUse": [own_hook]}}),
        encoding="utf-8",
    )
    run(src, dst)
    settings = read_settings(dst)
    assert settings["permissions"] == {"allow": ["Bash(ls)"]}
    assert settings["hooks"]["PreToolUse"] == [own_hook, *HOOKS["PreToolUse"]]


def test_reinstalling_does_not_duplicate_hooks_or_the_gitignore_block(tmp_path) -> None:
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    (dst / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    run(src, dst)
    first = ((dst / ".gitignore").read_text(encoding="utf-8"), read_settings(dst))
    actions = run(src, dst)
    assert ((dst / ".gitignore").read_text(encoding="utf-8"), read_settings(dst)) == first
    assert actions == []
    assert first[0].startswith("node_modules/\n")
    assert first[0].count(install.GITIGNORE_BEGIN) == 1


def test_a_differing_file_on_first_install_is_not_overwritten(tmp_path) -> None:
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    (dst / "harness").mkdir()
    (dst / "harness" / "CONVENTIONS.md").write_text("別物\n", encoding="utf-8")
    with pytest.raises(install.InstallError, match="harness/CONVENTIONS.md"):
        install.plan(src, dst, force=False)
    assert (dst / "harness" / "CONVENTIONS.md").read_text(encoding="utf-8") == "別物\n"
    assert not (dst / install.MANIFEST).exists()


def test_force_overwrites_a_differing_file(tmp_path) -> None:
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    (dst / "harness").mkdir()
    (dst / "harness" / "CONVENTIONS.md").write_text("別物\n", encoding="utf-8")
    run(src, dst, force=True)
    assert (dst / "harness" / "CONVENTIONS.md").read_text(encoding="utf-8") == "規約\n"


def test_an_update_does_not_overwrite_a_project_file_that_upstream_newly_adds(tmp_path) -> None:
    """導入先が自分で置いた agent と同名の agent が上流に増えても、黙って上書きしない。"""
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    run(src, dst)
    (dst / ".claude" / "agents" / "reviewer.md").write_text("導入先の agent\n", encoding="utf-8")
    (src / ".claude" / "agents" / "reviewer.md").write_text("上流の agent\n", encoding="utf-8")
    with pytest.raises(install.InstallError, match="reviewer.md"):
        install.plan(src, dst, force=False)


# --------------------------------------------------------------------------------------
# 更新
# --------------------------------------------------------------------------------------

def test_an_update_removes_files_dropped_upstream_but_keeps_project_files(tmp_path) -> None:
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    run(src, dst)
    (dst / ".claude" / "agents" / "own.md").write_text("導入先の agent\n", encoding="utf-8")
    (src / "harness" / "scripts" / "tool.py").unlink()
    actions = run(src, dst)
    assert ("削除", "harness/scripts/tool.py") in actions
    assert not (dst / "harness" / "scripts" / "tool.py").exists()
    assert (dst / ".claude" / "agents" / "own.md").exists()


def test_an_update_replaces_the_previous_hook_registration(tmp_path) -> None:
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    run(src, dst)
    new_hooks = {
        "PreToolUse": [
            {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "python3 guard.py"}]}
        ]
    }
    src2 = fake_source(tmp_path / "v2", hooks=new_hooks, version="1.1.0")
    run(src2, dst)
    assert read_settings(dst) == {"hooks": new_hooks}
    manifest = json.loads((dst / install.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["version"] == "1.1.0"


def test_local_edits_to_installed_files_are_overwritten_on_update(tmp_path) -> None:
    """導入先でハーネス本体を直接直した分は、更新で上流の内容に戻る（本体の改修は上流で行う）。"""
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    run(src, dst)
    (dst / "harness" / "CONVENTIONS.md").write_text("手元で改変\n", encoding="utf-8")
    run(src, dst)
    assert (dst / "harness" / "CONVENTIONS.md").read_text(encoding="utf-8") == "規約\n"


# --------------------------------------------------------------------------------------
# 前提条件
# --------------------------------------------------------------------------------------

def test_a_target_that_is_not_a_git_repository_is_rejected(tmp_path) -> None:
    src = fake_source(tmp_path)
    (tmp_path / "plain").mkdir()
    with pytest.raises(install.InstallError, match="git init"):
        install.plan(src, tmp_path / "plain", force=False)


def test_installing_into_the_source_itself_is_rejected(tmp_path) -> None:
    src = fake_source(tmp_path)
    git_init(src)
    with pytest.raises(install.InstallError, match="同じ"):
        install.plan(src, src, force=False)


def test_an_unreadable_settings_file_stops_the_install(tmp_path) -> None:
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    (dst / ".claude").mkdir()
    (dst / ".claude" / "settings.json").write_text("{壊れている", encoding="utf-8")
    with pytest.raises(install.InstallError, match="settings.json"):
        install.plan(src, dst, force=False)


def test_dry_run_writes_nothing(tmp_path, capsys, monkeypatch) -> None:
    src, dst = fake_source(tmp_path), git_init(tmp_path / "dst")
    monkeypatch.setattr(install, "source_root", lambda: src)
    assert install.main([str(dst), "--dry-run"]) == 0
    assert sorted(p.name for p in dst.iterdir()) == [".git"]
    assert "追加: harness/VERSION" in capsys.readouterr().out


# --------------------------------------------------------------------------------------
# 本体リポジトリとの drift
# --------------------------------------------------------------------------------------

def test_the_managed_gitignore_lines_match_this_repository() -> None:
    """導入先に配る無視指定は、本体リポジトリで実際に使っているものと一致させる。"""
    ours = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    missing = [line for line in install.GITIGNORE_LINES if line not in ours]
    assert missing == []
