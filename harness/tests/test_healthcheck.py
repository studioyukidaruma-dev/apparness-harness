"""強制レイヤ自身の健全性診断（T-011 / F-A2）の検証。

Hook は exit != 2 で終わると Claude Code から「判断なし＝通過」として扱われる。
`python3` 不在・import 失敗・例外のいずれでも**全ルールが黙って無効化された状態で作業が続く**。
「効いていないのに効いているつもり」は、決定論的強制を掲げるハーネスにとって最悪の失敗の形なので、
(1) 例外時は通過ではなく拒否する（fail-closed）、(2) 壊れていることを可視化する、の 2 本で塞ぐ。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import time

import session_start_healthcheck as hc

HOOKS_DIR = pathlib.Path(__file__).resolve().parent.parent / "hooks"
REPO_ROOT = HOOKS_DIR.parent.parent
PRE_HOOK = HOOKS_DIR / "pre_tool_use_guard.py"

SETTINGS = {
    "hooks": {
        "SessionStart": [{"hooks": [{"type": "command", "command": "python3 harness/hooks/session_start_healthcheck.py"}]}],
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 harness/hooks/pre_tool_use_guard.py"}]}],
        "PostToolUse": [{"hooks": [
            {"type": "command", "command": "python3 harness/hooks/post_tool_use_sync.py"},
            {"type": "command", "command": "python3 harness/hooks/post_tool_use_guard.py"},
        ]}],
        "Stop": [{"hooks": [{"type": "command", "command": "python3 harness/hooks/stop_commit_guard.py"}]}],
        "SubagentStop": [{"hooks": [{"type": "command", "command": "python3 harness/hooks/stop_commit_guard.py"}]}],
    }
}


def build(tmp_path: pathlib.Path, settings: dict | None = SETTINGS) -> pathlib.Path:
    """本物の hooks を複製した、健全な状態の一時リポジトリ。"""
    root = tmp_path / "repo"
    shutil.copytree(HOOKS_DIR, root / "harness" / "hooks")
    (root / ".claude").mkdir(parents=True)
    if settings is not None:
        (root / ".claude" / "settings.json").write_text(
            json.dumps(settings, ensure_ascii=False), encoding="utf-8"
        )
    return root


# --------------------------------------------------------------------------------------
# 診断そのもの
# --------------------------------------------------------------------------------------

def test_a_healthy_repository_reports_no_problem(tmp_path) -> None:
    assert hc.diagnose(str(build(tmp_path))) == []


def test_broken_hook_import_is_reported(tmp_path) -> None:
    """import が壊れた Hook は、起動時に黙って exit != 2 になる＝全ルールが無効化される。"""
    root = build(tmp_path)
    (root / "harness" / "hooks" / "pre_tool_use_guard.py").write_text(
        "import a_module_that_does_not_exist\n", encoding="utf-8"
    )
    problems = hc.diagnose(str(root))
    assert any("pre_tool_use_guard.py" in p and "import" in p for p in problems), problems


def test_missing_hook_file_is_reported(tmp_path) -> None:
    root = build(tmp_path)
    (root / "harness" / "hooks" / "stop_commit_guard.py").unlink()
    problems = hc.diagnose(str(root))
    assert any("stop_commit_guard.py" in p and "存在しません" in p for p in problems), problems


def test_missing_path_utils_function_is_reported(tmp_path) -> None:
    """関数を消しただけでは何も起きず、実際に呼ばれるまで気付けない。それを起動時に捕まえる。"""
    root = build(tmp_path)
    lib = root / "harness" / "hooks" / "lib" / "path_utils.py"
    source = lib.read_text(encoding="utf-8")
    lib.write_text(
        source.replace("def detect_dangerous_read(", "def _removed_detect_dangerous_read("),
        encoding="utf-8",
    )
    problems = hc.diagnose(str(root))
    assert any("detect_dangerous_read" in p for p in problems), problems


def test_missing_hook_registration_is_reported(tmp_path) -> None:
    settings = json.loads(json.dumps(SETTINGS))
    del settings["hooks"]["Stop"]
    problems = hc.diagnose(str(build(tmp_path, settings)))
    assert any("Stop" in p and "Rule 8" in p for p in problems), problems


def test_missing_post_tool_use_guard_registration_is_reported(tmp_path) -> None:
    """事後検証が外れると、静的検知をすり抜けた Bash 書き込みが巻き戻されなくなる。"""
    settings = json.loads(json.dumps(SETTINGS))
    settings["hooks"]["PostToolUse"][0]["hooks"] = [
        {"type": "command", "command": "python3 harness/hooks/post_tool_use_sync.py"}
    ]
    problems = hc.diagnose(str(build(tmp_path, settings)))
    assert any("post_tool_use_guard.py" in p for p in problems), problems


def test_missing_settings_file_is_reported(tmp_path) -> None:
    problems = hc.diagnose(str(build(tmp_path, settings=None)))
    assert any("settings.json" in p for p in problems), problems


def test_runtime_checks_are_excluded_from_the_dashboard_view(tmp_path) -> None:
    """`PROGRESS.md` はコミットされる成果物なので、環境依存の判定を混ぜない（CI 項目 G）。"""
    root = str(build(tmp_path))
    assert hc.diagnose(root, include_runtime=False) == hc.diagnose(root, include_runtime=True)


# --------------------------------------------------------------------------------------
# PROGRESS.md への表示
# --------------------------------------------------------------------------------------

def test_progress_line_reports_ok_when_healthy(tmp_path) -> None:
    assert "OK" in hc.progress_line(str(build(tmp_path)))


def test_progress_line_reports_the_problem_when_broken(tmp_path) -> None:
    root = build(tmp_path)
    (root / "harness" / "hooks" / "pre_tool_use_guard.py").write_text("import nope\n", encoding="utf-8")
    line = hc.progress_line(str(root))
    assert "異常" in line and "pre_tool_use_guard.py" in line


def test_the_real_repository_dashboard_line_is_ok() -> None:
    """このリポジトリ自身の強制レイヤが健全であること（このテストが見張り番）。"""
    assert "OK" in hc.progress_line(str(REPO_ROOT))


# --------------------------------------------------------------------------------------
# SessionStart hook としての振る舞い
# --------------------------------------------------------------------------------------

def _run_session_start(root: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "harness" / "hooks" / "session_start_healthcheck.py")],
        input=json.dumps({"cwd": str(root)}),
        capture_output=True,
        text=True,
        cwd=root,
    )


def test_session_start_is_silent_when_healthy(tmp_path) -> None:
    result = _run_session_start(build(tmp_path))
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert result.stderr.strip() == ""


def test_session_start_warns_and_injects_context_when_broken(tmp_path) -> None:
    root = build(tmp_path)
    (root / "harness" / "hooks" / "post_tool_use_guard.py").unlink()
    result = _run_session_start(root)
    assert result.returncode == 0  # セッション開始自体は妨げない
    assert "警告" in result.stderr
    payload = json.loads(result.stdout)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "決定論的強制" in context and "post_tool_use_guard.py" in context


def test_session_start_overhead_is_under_a_second(tmp_path) -> None:
    root = build(tmp_path)
    started = time.monotonic()
    _run_session_start(root)
    assert time.monotonic() - started < 1.0


# --------------------------------------------------------------------------------------
# fail-closed: 想定外の例外で通過させない
# --------------------------------------------------------------------------------------

def test_unexpected_exception_denies_instead_of_passing(tmp_path, monkeypatch) -> None:
    """ガード本体が例外で判定できなかったとき、通過（exit 0）ではなく拒否（exit 2）になること。

    ここが通過だと、壊れた瞬間に全ルールが黙って無効化される。実際に例外を起こさせて確認する。
    """
    root = tmp_path / "repo"
    (root / "harness" / "hooks").mkdir(parents=True)
    shutil.copytree(HOOKS_DIR / "lib", root / "harness" / "hooks" / "lib")
    guard = root / "harness" / "hooks" / "pre_tool_use_guard.py"
    source = (HOOKS_DIR / "pre_tool_use_guard.py").read_text(encoding="utf-8")
    # main() の入口で必ず例外になるよう壊す（_fail_closed_main はそのまま使う）
    guard.write_text(
        source.replace(
            "def main() -> int:",
            "def main() -> int:\n    raise RuntimeError('壊れた強制レイヤ')",
            1,
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(guard)],
        input=json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(root / "x.txt")}}),
        capture_output=True,
        text=True,
        cwd=root,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "判定できませんでした" in result.stderr


def test_the_guard_still_passes_normally_when_nothing_is_wrong(tmp_path) -> None:
    """fail-closed 化で正常な書き込みまで止めていないこと。"""
    result = subprocess.run(
        [sys.executable, str(PRE_HOOK)],
        input=json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "x.txt"), "content": "x"},
            "cwd": str(tmp_path),
        }),
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr

