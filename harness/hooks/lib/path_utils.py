"""hooks/*.py が共有するヘルパー。**依存ゼロ**（標準ライブラリのみ）を厳守すること。
Hook はツール呼び出しのたびに毎回起動されるため、起動コストと信頼性を最優先する。
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys

MULTI_EDIT_FILE_FIELD = "file_path"
NOTEBOOK_EDIT_FIELD = "notebook_path"

# schemas/status.schema.json の state enum と対応。CONVENTIONS.md 5節の状態機械の単一情報源はここではなく
# CONVENTIONS.md 側だが、値の並びはこの定数と一致させること。
STATUS_LINEAR_ORDER = [
    "NOT_STARTED",
    "CONTRACT_DRAFTED",
    "CONTRACT_APPROVED",
    "IN_PROGRESS",
    "IMPLEMENTED",
    "TESTED",
    "INTEGRATED",
]
STATUS_TERMINAL_STATES = {"INTEGRATED", "SUPERSEDED"}
STATUS_ALL_STATES = set(STATUS_LINEAR_ORDER) | {"BLOCKED", "SUPERSEDED"}

# Bash からの間接書き込みを検知するためのトークン集合。shlex でクォートを尊重してトークン化した
# 上でこれらと突き合わせるため、クォート内の文字列（例: `echo "a >> b"` の `>>`）を演算子と
# 誤認識しない。`;`/`&&`/`||`/`|`/`&`/`(`/`)` は「1コマンド分」を区切るための境界として扱う。
_BASH_WRITE_REDIRECT_OPS = {">", ">>"}
_BASH_SEGMENT_BREAKS = {";", "&&", "||", "|", "&", "(", ")"}


def read_hook_input() -> dict:
    raw = sys.stdin.read()
    try:
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}


def _run_git(args: list[str], cwd: str | None = None) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=cwd, timeout=3
        )
        if out.returncode != 0:
            return None
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def get_worktree_toplevel(cwd: str) -> str | None:
    return _run_git(["rev-parse", "--show-toplevel"], cwd=cwd)


def get_current_branch(cwd: str) -> str | None:
    return _run_git(["branch", "--show-current"], cwd=cwd)


def get_status_porcelain(cwd: str) -> str | None:
    """`git status --porcelain` の生出力を返す。各行先頭の状態コード（例: ` M`）は
    先頭空白に意味があるため、`_run_git` の `strip()` は使わず改行のみを除去する。
    """
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            capture_output=True, text=True, cwd=cwd, timeout=3,
        )
        if out.returncode != 0:
            return None
        return out.stdout.rstrip("\n")
    except Exception:  # noqa: BLE001
        return None


def find_main_repo_root(worktree_toplevel: str) -> str:
    """git worktree のメインリポジトリのルートを返す（.git ファイルの gitdir 記載から辿る）。
    通常の（worktree でない）チェックアウトなら worktree_toplevel をそのまま返す。
    """
    import os

    git_path = os.path.join(worktree_toplevel, ".git")
    if os.path.isdir(git_path):
        return worktree_toplevel
    try:
        with open(git_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except OSError:
        return worktree_toplevel
    m = re.match(r"gitdir:\s*(.+)", content)
    if not m:
        return worktree_toplevel
    gitdir = m.group(1)
    # 例: <root>/.git/worktrees/<name> -> <root>
    marker = os.sep + ".git" + os.sep + "worktrees" + os.sep
    idx = gitdir.find(marker)
    if idx == -1:
        return worktree_toplevel
    return gitdir[:idx]


def extract_structured_edit_paths(tool_name: str, tool_input: dict) -> list[str]:
    """Edit/Write/MultiEdit/NotebookEdit の対象絶対パスを返す。"""
    if tool_name == "NotebookEdit":
        path = tool_input.get(NOTEBOOK_EDIT_FIELD)
        return [path] if path else []
    if tool_name in ("Edit", "Write", "MultiEdit"):
        path = tool_input.get(MULTI_EDIT_FILE_FIELD)
        return [path] if path else []
    return []


def _classify_bash_lines(command: str) -> list[tuple[str, str]]:
    """`command` を物理行に分け、各行の直後に置くべき区切り文字（`;`/`\\n`/` `）を判定する。

    shlex は改行を単なる空白として読み捨てるため、これに頼ると「改行だけで区切られた
    複数コマンド」（Claude Code の Bash ツールが渡す複数行スクリプトはこの形が非常に多い）が
    1つの巨大なセグメントに融合してしまい、`_extract_write_targets_from_segment` が
    セグメント先頭トークンだけを見て `cp`/`mv`/`tee`/`sed -i` を判定する仕組みが、
    先頭行以外にあるこれらのコマンドを一切検知できなくなる（実地で `mkdir ...\\ncp ... dst/`
    という2行スクリプトの `cp` が検知漏れすることを確認して発見した）。

    この関数は、クォート・行継続（末尾 `\\`）・ヒアドキュメント本体を考慮しながら
    「コマンドの区切りとして使ってよい改行」だけを `;` に変換できるよう分類する:
    - クォートを跨ぐ改行、ヒアドキュメント本体・終端子直前の改行 → `\\n`（そのまま保持）
    - 行継続（末尾が奇数個の `\\`）→ ` `（バックスラッシュと改行を単一空白に置換）
    - それ以外の、通常のコマンド行の末尾の改行 → `;`（区切りとして扱う）

    ヒアドキュメント（`<<EOF` 等）の本体をコマンド境界と誤認しないよう、本体行・終端子行の
    直後は区切りにしない。終端子行が最後に保留していたヒアドキュメントを閉じたら、その行の
    直後からは通常のコマンド境界判定を再開する。
    """
    lines = command.split("\n")
    result: list[tuple[str, str]] = []
    quote: str | None = None  # None / "'" / '"'
    heredoc_queue: list[str] = []  # 保留中のヒアドキュメント終端子（出現順、複数連結にも対応）

    for line in lines:
        if heredoc_queue:
            terminator = heredoc_queue[0]
            if line.strip() == terminator:
                heredoc_queue.pop(0)
                sep = ";" if not heredoc_queue else "\n"
            else:
                sep = "\n"
            result.append((line, sep))
            continue

        i, n = 0, len(line)
        found_heredoc = False
        while i < n:
            ch = line[i]
            if quote == "'":
                if ch == "'":
                    quote = None
                i += 1
                continue
            if quote == '"':
                if ch == "\\" and i + 1 < n:
                    i += 2
                    continue
                if ch == '"':
                    quote = None
                i += 1
                continue
            # クォート外
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch in ("'", '"'):
                quote = ch
                i += 1
                continue
            if ch == "<" and line[i:i + 2] == "<<":
                j = i + 2
                if j < n and line[j] == "-":
                    j += 1
                while j < n and line[j] in (" ", "\t"):
                    j += 1
                delim_quote = line[j] if j < n and line[j] in ("'", '"') else None
                if delim_quote:
                    j += 1
                start = j
                if delim_quote:
                    while j < n and line[j] != delim_quote:
                        j += 1
                    delimiter = line[start:j]
                    if j < n:
                        j += 1
                else:
                    while j < n and not line[j].isspace() and line[j] not in ("<", ">", "|", "&", ";"):
                        j += 1
                    delimiter = line[start:j]
                if delimiter:
                    heredoc_queue.append(delimiter)
                    found_heredoc = True
                i = j
                continue
            i += 1

        # 末尾の連続する `\` の個数が奇数なら行継続（最後の1つが改行をエスケープする）
        trailing = len(line) - len(line.rstrip("\\"))
        line_continuation = quote is None and trailing % 2 == 1

        if quote is not None:
            sep = "\n"
        elif line_continuation:
            line = line[:-1]  # 継続用のバックスラッシュを落とす
            sep = " "
        elif found_heredoc or heredoc_queue:
            sep = "\n"
        else:
            sep = ";"
        result.append((line, sep))

    return result


def _normalize_bash_newlines(command: str) -> str:
    """`_classify_bash_lines` の分類に従い、コマンド境界として扱ってよい改行だけを `;` に
    変換した文字列を返す（トークン化前の前処理）。"""
    classified = _classify_bash_lines(command)
    parts: list[str] = []
    for idx, (line, sep) in enumerate(classified):
        parts.append(line)
        if idx < len(classified) - 1:
            parts.append(sep)
    return "".join(parts)


def _tokenize_bash_command(command: str) -> list[str] | None:
    """command を shlex でクォートを尊重してトークン化する。posix モードなのでクォートは
    剥がされ、クォート内の記号（`>` 等）は独立したトークンにならず語の一部として扱われる。
    トークン化の前に `_normalize_bash_newlines` で改行をコマンド境界（`;`）に正規化するため、
    複数行スクリプトの各行が独立したセグメントとして扱われる。
    クォート不整合等でトークン化できない場合は None を返す（判定不能として安全側＝許可に倒す）。
    """
    try:
        normalized = _normalize_bash_newlines(command)
        lexer = shlex.shlex(normalized, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return None


def _extract_write_targets_from_segment(tokens: list[str]) -> list[str]:
    """1コマンド分のトークン列から、書き込み先になりうるパスを抽出する。"""
    targets: list[str] = []
    for i, tok in enumerate(tokens):
        if tok in _BASH_WRITE_REDIRECT_OPS and i + 1 < len(tokens):
            targets.append(tokens[i + 1])

    if not tokens:
        return targets
    cmd, args = tokens[0], tokens[1:]
    non_flag_args = [a for a in args if not a.startswith("-")]

    if cmd in ("cp", "mv") and non_flag_args:
        targets.append(non_flag_args[-1])
    elif cmd == "tee":
        targets.extend(non_flag_args)
    elif cmd == "sed" and non_flag_args and any(a == "-i" or a.startswith("-i") for a in args):
        targets.append(non_flag_args[-1])

    return targets


def extract_bash_candidate_paths(command: str) -> list[str]:
    """Bash コマンド文字列から、書き込み先になりうるパス候補を抽出する。
    クォートを尊重してトークン化してから判定するため、クォート内の文字列に `>` 等が
    含まれていても演算子と誤認識しない。それでも変数展開されたパス等の検知漏れは残る
    （完全な防御ではなく、意図しない/不注意な間接書き込みを止めるためのヒューリスティック）。
    """
    tokens = _tokenize_bash_command(command)
    if not tokens:
        return []

    segments: list[list[str]] = [[]]
    for tok in tokens:
        if tok in _BASH_SEGMENT_BREAKS:
            segments.append([])
        else:
            segments[-1].append(tok)

    candidates: list[str] = []
    for seg in segments:
        candidates.extend(_extract_write_targets_from_segment(seg))
    return candidates


def to_worktree_relative(abs_or_rel_path: str, toplevel: str) -> str:
    """worktree のルートからの相対パス（POSIX区切り）を返す。既に相対ならそのまま正規化する。"""
    import os

    if not os.path.isabs(abs_or_rel_path):
        return abs_or_rel_path.replace("\\", "/")
    try:
        rel = os.path.relpath(abs_or_rel_path, toplevel)
    except ValueError:
        return abs_or_rel_path.replace("\\", "/")
    return rel.replace("\\", "/")


def read_state_field(status_yaml_path) -> str | None:
    """status.yaml / architecture.machine.yaml から `state:`/`status:` 行だけを正規表現で軽量抽出する。
    hooks は PyYAML に依存しないため、フルパースはしない。
    """
    try:
        with open(status_yaml_path, "r", encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^\s*(state|status)\s*:\s*(\S+)", line)
                if m:
                    return m.group(2).strip('"\'')
    except OSError:
        return None
    return None


def simulate_write_result(tool_name: str, tool_input: dict, current_content: str) -> str:
    """PreToolUse 時点でまだ書き込まれていない、書き込み後のファイル内容をシミュレートする。
    Edit/MultiEdit はファイル全体を渡してこないため、Rule7 のような「書き込み後の内容」を
    見て判定するルールはこれで再現してから検査する。
    """
    if tool_name == "Write":
        return tool_input.get("content", "")
    if tool_name == "Edit":
        old = tool_input.get("old_string", "")
        new = tool_input.get("new_string", "")
        count = -1 if tool_input.get("replace_all") else 1
        return current_content.replace(old, new, count)
    if tool_name == "MultiEdit":
        content = current_content
        for edit in tool_input.get("edits", []) or []:
            old = edit.get("old_string", "")
            new = edit.get("new_string", "")
            if edit.get("replace_all"):
                content = content.replace(old, new)
            else:
                content = content.replace(old, new, 1)
        return content
    return current_content


def extract_scalar_field(content: str, key: str) -> str | None:
    """文字列コンテンツ（ファイルではなく）から `key: value` 形式の行を正規表現で軽量抽出する。"""
    m = re.search(rf"^\s*{re.escape(key)}\s*:\s*(\S.*?)\s*$", content, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip('"\'')


def validate_status_transition(old_state: str | None, new_state: str) -> str | None:
    """status.yaml の `state` 遷移が CONVENTIONS.md 5節の状態機械に沿っているか判定する。
    妥当（または判定不能）なら None、不正なら拒否理由の文字列を返す。

    - `BLOCKED` はどの非終端状態からでも／どの状態へでも自由に出入りできる「一時停止」として扱う
      （どのレベルで止まっていたかは `state_history` を遡れば分かるが、v1 ではそこまで検証しない。
      既知の簡略化として、`BLOCKED` を経由した skip はすり抜けうる）。
    - `SUPERSEDED` はどの非終端状態からでも許可する（`diff-design` による置き換えはいつでも起こりうる）。
    - それ以外は `STATUS_LINEAR_ORDER` に沿った1段階前進のみ許可する。後退・複数段階の飛び越しは拒否する。
    """
    if not old_state or old_state == new_state:
        return None
    if new_state not in STATUS_ALL_STATES or old_state not in STATUS_ALL_STATES:
        return None  # 未知の値の妥当性は JSON Schema 側の責務。ここでは判定しない
    if old_state in STATUS_TERMINAL_STATES:
        return f"拒否: state は {old_state}（終端状態）から変更できません。"
    if new_state in ("SUPERSEDED", "BLOCKED") or old_state == "BLOCKED":
        return None

    old_idx = STATUS_LINEAR_ORDER.index(old_state)
    new_idx = STATUS_LINEAR_ORDER.index(new_state)
    if new_idx == old_idx + 1:
        return None
    if new_idx <= old_idx:
        return f"拒否: state を {old_state} から {new_state} に後退させることはできません。"
    skipped = ", ".join(STATUS_LINEAR_ORDER[old_idx + 1:new_idx])
    return (
        f"拒否: state を {old_state} から {new_state} へ直接進めることはできません"
        f"（{skipped} を飛ばしています）。1段階ずつ進めてください"
        f"（`CONTRACT_APPROVED` へ進めない場合は `BLOCKED` にして `blockers[]` に理由を記録してください）。"
    )


def extract_required_skills(content: str) -> list[dict]:
    """shared-kernel.yaml の `required_skills:` リストを軽量パースする。
    `- name: "..."` に続く `plugin_ref: "..."` / `purpose: "..."` を同一エントリとして拾う。
    フルな YAML パーサーではなく、テンプレートで規定した書式のみを前提にする。
    """
    m = re.search(r"^required_skills\s*:\s*(\[\s*\])?\s*$", content, re.MULTILINE)
    if not m or m.group(1) is not None:
        return []
    start = m.end()
    # 次のトップレベルキー（インデントなしの `key:` 行）までを required_skills のブロックとみなす。
    # PyYAML のデフォルト出力はリスト項目 `- name: ...` をインデントせず親キーと同じ列に置くため、
    # `^\S` のような単純な判定だとリスト項目自体を「次のキー」と誤検知する。`- ` で始まる行は除外する。
    block_match = re.search(r"^(?!-\s)[A-Za-z_]\S*\s*:", content[start:], re.MULTILINE)
    block = content[start:start + block_match.start()] if block_match else content[start:]

    skills: list[dict] = []
    current: dict | None = None
    for line in block.splitlines():
        name_m = re.match(r"^\s*-\s*name\s*:\s*(.+?)\s*$", line)
        if name_m:
            if current:
                skills.append(current)
            current = {"name": name_m.group(1).strip().strip('"\'')}
            continue
        if current is not None:
            for key in ("plugin_ref", "purpose"):
                field_m = re.match(rf"^\s*{key}\s*:\s*(.+?)\s*$", line)
                if field_m:
                    current[key] = field_m.group(1).strip().strip('"\'')
    if current:
        skills.append(current)
    return skills


def get_enabled_plugins(repo_root: str) -> set[str]:
    """.claude/settings.json と .claude/settings.local.json の enabledPlugins をマージして返す。
    キー形式は "<plugin-name>@<marketplace>"。JSON 標準ライブラリのみ使用。
    """
    import os

    enabled: set[str] = set()
    for name in ("settings.json", "settings.local.json"):
        path = os.path.join(repo_root, ".claude", name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        plugins = data.get("enabledPlugins")
        if isinstance(plugins, dict):
            enabled.update(k for k, v in plugins.items() if v)
        elif isinstance(plugins, list):
            enabled.update(plugins)
    return enabled


def deny(reason: str) -> None:
    print(reason, file=sys.stderr)
    sys.exit(2)


def allow() -> None:
    sys.exit(0)
