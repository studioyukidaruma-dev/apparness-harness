"""`path_utils` の Bash パース（Rule 1/2/3/5/6 を Bash 経由の間接書き込みにも効かせるための
検知ロジック）の回帰テスト。

ここに固定してあるシナリオは、`HARNESS_GUIDE.md` 11 節・`ROADMAP.md` に記録された
実地検証（真陽性 10 件・真陰性 4 件、および旧 `harness/fix-bash-guard-tokenizer` の
単一行シナリオ）をそのままテストコードに落としたものである。検知ロジックを触るときは、
このファイルが緑のままであることを必ず確認すること。

対象:
  - `_normalize_bash_newlines` / `_classify_bash_lines`（トークン化前の改行正規化）
  - `extract_bash_candidate_paths`（書き込み先候補の抽出）
"""
from __future__ import annotations

import pytest

import path_utils

GUARDED = "apps/todo/03-features/other/src/x.py"


def candidates(command: str) -> list[str]:
    return path_utils.extract_bash_candidate_paths(command)


# --------------------------------------------------------------------------------------
# 真陽性: 書き込み先として検知されなければならないもの
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "label,command,expected",
    [
        # --- 単一行（旧 harness/fix-bash-guard-tokenizer の回帰） ---
        ("redirect", f"echo hi > {GUARDED}", GUARDED),
        ("append", f"echo hi >> {GUARDED}", GUARDED),
        ("cp", f"cp a.py {GUARDED}", GUARDED),
        ("mv", f"mv a.py {GUARDED}", GUARDED),
        ("tee", f"tee {GUARDED}", GUARDED),
        ("sed -i", f"sed -i 's/a/b/' {GUARDED}", GUARDED),
        ("sed -i.bak", f"sed -i.bak 's/a/b/' {GUARDED}", GUARDED),
        ("cp with flags", f"cp -r -v src {GUARDED}", GUARDED),
        ("after &&", f"true && cp a.py {GUARDED}", GUARDED),
        ("after ;", f"true ; cp a.py {GUARDED}", GUARDED),
        ("after |", f"cat a.py | tee {GUARDED}", GUARDED),
        # --- 複数行（harness/fix-bash-guard-newline-segments で修正した検知漏れ） ---
        ("multiline cp", f"mkdir -p apps/todo/03-features/other/src\ncp a.py b.py {GUARDED}", GUARDED),
        ("multiline mv", f"echo start\nmv a.py {GUARDED}", GUARDED),
        ("multiline tee", f"echo start\ncat a.py | tee {GUARDED}", GUARDED),
        ("multiline sed -i", f"echo start\nsed -i 's/a/b/' {GUARDED}", GUARDED),
        ("multiline redirect", f"echo start\necho hi >> {GUARDED}", GUARDED),
        ("mixed && and newline", f"true && echo start\ncp a.py {GUARDED}", GUARDED),
        (
            "line continuation",
            "cp \\\n  a.py \\\n  " + GUARDED,
            GUARDED,
        ),
        (
            "command after heredoc",
            f"cat <<EOF > /tmp/note.txt\nhello\nEOF\ncp a.py {GUARDED}",
            GUARDED,
        ),
        (
            "quoted path containing a space",
            'cp a.py "apps/todo/03-features/other/src/my file.py"',
            "apps/todo/03-features/other/src/my file.py",
        ),
    ],
)
def test_true_positive(label: str, command: str, expected: str) -> None:
    assert expected in candidates(command), label


# --------------------------------------------------------------------------------------
# 真陰性: 書き込みではないため検知してはならないもの（誤検知の回帰）
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "label,command",
    [
        # --- 単一行（旧 harness/fix-bash-guard-tokenizer の回帰） ---
        ("quoted redirect operator", f'echo "hi >> {GUARDED}"'),
        ("quoted redirect operator (single)", f"echo 'hi >> {GUARDED}'"),
        ("read only", f"cat {GUARDED}"),
        ("grep only", f"grep -n foo {GUARDED}"),
        ("cp source only is not a target", f"cp {GUARDED} /tmp/out.py"),
        ("sed without -i", f"sed 's/a/b/' {GUARDED}"),
        ("here-string", f"grep foo <<< '{GUARDED}'"),
        ("git command mentioning the path", f"git log --oneline -- {GUARDED}"),
        # --- 複数行（harness/fix-bash-guard-newline-segments の回帰） ---
        (
            "fake command inside heredoc body",
            f"cat <<EOF\ncp a.py {GUARDED}\nEOF",
        ),
        (
            "fake command inside quoted heredoc body",
            f"cat <<'EOF'\nsed -i 's/a/b/' {GUARDED}\nEOF",
        ),
        (
            "fake string inside a multiline double-quoted string",
            f'echo "line1\ncp a.py {GUARDED}\nline3"',
        ),
        ("multiline read only", f"echo start\ncat {GUARDED}"),
    ],
)
def test_true_negative(label: str, command: str) -> None:
    assert GUARDED not in candidates(command), label


# --------------------------------------------------------------------------------------
# ガード対象外パスは検知されても構わないが、対象パスと混同されないこと
# --------------------------------------------------------------------------------------

def test_non_guarded_path_is_extracted_as_is() -> None:
    assert "/tmp/out.txt" in candidates("echo hi > /tmp/out.txt")


def test_unparsable_command_is_treated_as_undecidable() -> None:
    """クォート不整合でトークン化できない場合は空リスト（＝安全側＝許可）に倒す。"""
    assert candidates('echo "unterminated') == []


# --------------------------------------------------------------------------------------
# 改行分類そのもの（`_classify_bash_lines` / `_normalize_bash_newlines`）
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "label,command,expected",
    [
        ("plain newline becomes a separator", "echo a\necho b", "echo a;echo b"),
        ("line continuation becomes a space", "echo a \\\nb", "echo a  b"),
        (
            "heredoc body keeps its newlines",
            "cat <<EOF\nbody\nEOF\necho done",
            "cat <<EOF\nbody\nEOF;echo done",
        ),
        (
            "newline inside quotes is preserved",
            'echo "a\nb"\necho c',
            'echo "a\nb";echo c',
        ),
    ],
)
def test_normalize_bash_newlines(label: str, command: str, expected: str) -> None:
    assert path_utils._normalize_bash_newlines(command) == expected, label


def test_classify_bash_lines_marks_heredoc_terminator() -> None:
    classified = path_utils._classify_bash_lines("cat <<EOF\nbody\nEOF\necho done")
    assert [sep for _line, sep in classified] == ["\n", "\n", ";", ";"]
