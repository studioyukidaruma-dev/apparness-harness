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


def get_head_commit(cwd: str) -> str | None:
    """現在の HEAD のフル SHA を返す（Rule 10 で受領書の commit と照合する）。"""
    return _run_git(["rev-parse", "HEAD"], cwd=cwd)


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


def get_git_dir(cwd: str) -> str | None:
    """この worktree の .git ディレクトリの絶対パスを返す（スナップショットの置き場所）。"""
    return _run_git(["rev-parse", "--absolute-git-dir"], cwd=cwd)


def parse_porcelain(status_text: str | None) -> dict:
    """`git status --porcelain` の出力を {パス: 状態コード} に変換する。"""
    result: dict[str, str] = {}
    for line in (status_text or "").splitlines():
        if len(line) < 4:
            continue
        code, path_part = line[:2], line[3:]
        if " -> " in path_part:  # rename はリネーム後のパスを見る
            path_part = path_part.split(" -> ", 1)[1]
        path_part = path_part.strip().strip('"').replace("\\", "/")
        if path_part:
            result[path_part] = code
    return result


def revert_path(rel_path: str, cwd: str) -> bool:
    """1 つのパスを HEAD の状態へ巻き戻す。未追跡ファイルは削除する。成功なら True。"""
    import os

    if _run_git(["checkout", "HEAD", "--", rel_path], cwd=cwd) is not None:
        return True
    # HEAD に存在しない（新規追加された）ファイル。index から外して実体を消す
    _run_git(["rm", "-f", "--cached", "--", rel_path], cwd=cwd)
    target = os.path.join(cwd, rel_path)
    try:
        if os.path.isfile(target):
            os.remove(target)
        return True
    except OSError:
        return False


# 事後検証のスナップショットで内容まで保持する上限（1 ファイルあたり）。
# これを超えるファイルはハッシュだけ持ち、巻き戻しは HEAD へのフォールバックになる。
SNAPSHOT_MAX_CONTENT_BYTES = 1_000_000


def _file_digest(abs_path: str) -> str | None:
    """ファイル内容の SHA-1。読めなければ None（＝存在しない／読めない、として扱う）。"""
    import hashlib
    import os

    try:
        if not os.path.isfile(abs_path):
            return None
        with open(abs_path, "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()
    except OSError:
        return None


def capture_worktree_state(toplevel: str) -> dict | None:
    """未コミットの各パスについて `{code, sha, text}` を記録する。

    **状態コードではなく内容のハッシュで比較する**のが要点（F-050）。
    `git status --porcelain` の状態コードは `git add` でも ` M` → `M ` と変わるため、
    コードの変化を「ファイルが変更された」とみなすと、内容を変えていない `git add` が
    事後検証を誤発火させる。逆に、実行前から ` M` だったファイルをさらに書き換えても
    コードは ` M` のままなので、本当の変更を取りこぼす。内容ハッシュならどちらも起きない。

    `text` は巻き戻し先として使う。HEAD ではなく **Bash 実行直前の内容**へ戻すことで、
    実行前から未コミットだった変更（人間の編集など）を巻き添えで消さずに済む。
    """
    import os

    status = get_status_porcelain(toplevel)
    if status is None:
        return None
    state: dict = {}
    for rel_path, code in parse_porcelain(status).items():
        abs_path = os.path.join(toplevel, rel_path)
        entry: dict = {"code": code, "sha": _file_digest(abs_path)}
        try:
            if entry["sha"] and os.path.getsize(abs_path) <= SNAPSHOT_MAX_CONTENT_BYTES:
                with open(abs_path, "r", encoding="utf-8") as f:
                    entry["text"] = f.read()
        except (OSError, UnicodeDecodeError):
            pass  # バイナリ・巨大ファイルは内容を持たない（ハッシュだけで検知する）
        state[rel_path] = entry
    return state


def diff_worktree_state(before: dict, after: dict) -> list[str]:
    """スナップショット同士を比べ、**内容が実際に変わった**パスを返す。"""
    changed = []
    for rel_path, entry in after.items():
        prev = before.get(rel_path)
        if prev is None or prev.get("sha") != entry.get("sha"):
            changed.append(rel_path)
    return sorted(changed)


def restore_from_snapshot(rel_path: str, toplevel: str, entry: dict | None) -> bool:
    """Bash 実行直前の内容へ戻す。スナップショットに内容が無ければ HEAD へ戻す。"""
    import os

    if entry is None:
        return revert_path(rel_path, toplevel)  # 実行前に存在しなかった＝新規作成
    text = entry.get("text")
    if text is None:
        return revert_path(rel_path, toplevel)  # 内容を持てなかった（バイナリ・巨大ファイル）
    target = os.path.join(toplevel, rel_path)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    except OSError:
        return False


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


def resolve_write_target(target: str, cwd: str, toplevel: str) -> tuple[str, str]:
    """書き込み先を、**それが属するリポジトリのルート**からの相対パスに直す。

    従来は「セッションの worktree ルートからの相対パス」しか見ていなかったため、
    worktree の外を指すパス——メインリポジトリ側の絶対パスや `../../../../harness/...`——は
    `../` で始まる文字列になり、`^harness/` や `^apps/...` にアンカーされた
    **どの Rule にもマッチせず素通りしていた**（F-055。実測で本体側の
    `harness/CONVENTIONS.md` に書き込めた）。

    判定の基準点をセッションではなく**パスの所属先**に置くことで、worktree から外へ出る
    書き込みにも同じ Rule が同じ意味で効く。リポジトリの外（`/tmp` 等）は従来どおり対象外。

    相対パスは `cwd` を基準に解決する。セッションの cwd は worktree ルートとは限らない
    （機能ディレクトリで動いていることが多い）ため、toplevel 基準で解釈すると取り違える。
    """
    import os

    abs_target = target if os.path.isabs(target) else os.path.join(cwd, target)
    abs_target = os.path.normpath(abs_target)
    for root in (toplevel, find_main_repo_root(toplevel)):
        rel = os.path.relpath(abs_target, root).replace("\\", "/")
        if rel != ".." and not rel.startswith("../"):
            return rel, root
    return abs_target.replace("\\", "/"), toplevel


WORKTREE_PREFIX_RE = re.compile(r"^apps/[^/]+/\.worktrees/[^/]+/")


def resolve_worktree_scope(rel_path: str, toplevel: str) -> tuple[str, str]:
    """`apps/<app>/.worktrees/<feature-id>/` を通るパスを、その worktree を基準に読み替える。

    CONVENTIONS.md 4節のとおり、worktree の実体はメインリポジトリ配下の
    `apps/<app>/.worktrees/<feature-id>/` にあり、その中に同じ `apps/<app>/03-features/...`
    という相対パスが再び現れる。そのためメインの worktree から見た相対パスは接頭辞ぶんだけ深くなり、
    `^apps/.../03-features/...` にアンカーされた各 Rule の正規表現にマッチしない。
    結果として **メインセッションからは Rule 1・2・3・5・9・10 がまとめて素通りしていた**
    （ドッグフーディングで実証。受領書なしで `state: TESTED` を書き込めた）。

    接頭辞を剥がした相対パスと、その worktree のルートの組を返すことで、どのセッションから
    書き込んでも同じ Rule が同じ意味で効くようにする。単にパスを剥がすだけでは不十分で、
    各 Rule が `os.path.join(toplevel, rel_path)` で参照する status.yaml / contract.yaml /
    shared-kernel.yaml が別ファイルを指してしまうため、ルートのほうも合わせて読み替える。

    worktree の中から書いている場合は接頭辞が現れないので、この関数は恒等写像になる（既存動作を変えない）。
    """
    import os

    path = rel_path.replace("\\", "/")
    base = toplevel
    while True:
        m = WORKTREE_PREFIX_RE.match(path)
        if not m:
            return path, base
        base = os.path.join(base, *m.group(0).rstrip("/").split("/"))
        path = path[m.end():]


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


def extract_state_history(content: str) -> list:
    """`status.yaml` の `state_history[]` を取り出す（依存ゼロのパーサを使う）。"""
    data = parse_simple_yaml(content) if content else {}
    history = data.get("state_history") if isinstance(data, dict) else None
    return [e for e in history if isinstance(e, dict)] if isinstance(history, list) else []


def resolve_effective_previous_state(state_history: list | None) -> str | None:
    """`BLOCKED` の直前にあった実質的な状態を `state_history[]` から復元する。

    `at`（ISO-8601 の UTC 文字列）があればそれで昇順に並べ、無いエントリは記載順のまま先に置く
    （Python の sort は安定なので、`at` を持たない古い記録があっても順序が壊れない）。
    """
    entries = [
        e for e in (state_history or [])
        if isinstance(e, dict) and e.get("state") and e.get("state") != "BLOCKED"
    ]
    if not entries:
        return None
    entries = sorted(entries, key=lambda e: str(e.get("at") or ""))
    return str(entries[-1]["state"])


def validate_status_transition(
    old_state: str | None, new_state: str, state_history: list | None = None
) -> str | None:
    """status.yaml の `state` 遷移が CONVENTIONS.md 5節の状態機械に沿っているか判定する。
    妥当（または判定不能）なら None、不正なら拒否理由の文字列を返す。

    - `BLOCKED` はどの非終端状態からでも入れる「一時停止」として扱う。
      **`BLOCKED` から復帰するときは `state_history[]` を遡り、直前の非 `BLOCKED` 状態から
      の遷移として妥当性を判定する**（`state_history` を渡さない場合のみ、判定不能として通す）。
      これが無いと、`BLOCKED` を一度経由するだけで直線状態の飛び越しチェックをすり抜けられる。
    - `SUPERSEDED` はどの非終端状態からでも許可する（`diff-design` による置き換えはいつでも起こりうる）。
    - それ以外は `STATUS_LINEAR_ORDER` に沿った1段階前進のみ許可する。後退・複数段階の飛び越しは拒否する。
    """
    if not old_state or old_state == new_state:
        return None
    if new_state not in STATUS_ALL_STATES or old_state not in STATUS_ALL_STATES:
        return None  # 未知の値の妥当性は JSON Schema 側の責務。ここでは判定しない
    if old_state in STATUS_TERMINAL_STATES:
        return f"拒否: state は {old_state}（終端状態）から変更できません。"
    if new_state in ("SUPERSEDED", "BLOCKED"):
        return None
    if old_state == "BLOCKED":
        resumed_from = resolve_effective_previous_state(state_history)
        if resumed_from is None or resumed_from == new_state:
            return None  # 履歴が無ければ判定不能として通す（従来どおり）
        reason = validate_status_transition(resumed_from, new_state)
        if reason is None:
            return None
        return (
            f"{reason}\n"
            f"（`BLOCKED` の直前の状態は `state_history` によれば {resumed_from} です。"
            f"`BLOCKED` を経由しても飛び越しはできません。）"
        )

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


def _parse_inline_string_list(text: str) -> list[str]:
    """`["a", "b"]` / `[]` のようなインライン flow list だけを軽量パースする。"""
    text = text.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return []
    inner = text[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip('"\'') for item in inner.split(",") if item.strip()]


def extract_required_skills(content: str) -> list[dict]:
    """shared-kernel.yaml の `required_skills:` リストを軽量パースする。
    `- name: "..."` に続く `plugin_ref: "..."` / `purpose: "..."` / `applies_to: [...]` を
    同一エントリとして拾う。フルな YAML パーサーではなく、テンプレートで規定した書式のみを前提にする。
    `applies_to` はこの Skill を必須とする feature_id のインライン配列（省略・空なら全機能に適用）。
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
            for key in ("plugin_ref", "purpose", "kind"):
                field_m = re.match(rf"^\s*{key}\s*:\s*(.+?)\s*$", line)
                if field_m:
                    current[key] = field_m.group(1).strip().strip('"\'')
            applies_m = re.match(r"^\s*applies_to\s*:\s*(.+?)\s*$", line)
            if applies_m:
                current["applies_to"] = _parse_inline_string_list(applies_m.group(1))
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


# ======================================================================================
# 最小 YAML サブセットパーサ
# ======================================================================================
# hooks は **依存ゼロ**（PyYAML を使わない）を厳守するが、Rule 10（検証受領書）や Rule 9 の
# `state_history` 参照のように、単一行の正規表現抽出では足りない「入れ子のマッピング」を
# 読む必要が出てきた。そこでハーネスが自分で生成・規定している範囲の YAML
# （マッピング・リスト・フロー記法・コメント・引用符）だけを解釈する最小パーサを持つ。
#
# 意図的に**未対応**: アンカー/エイリアス、ブロックスカラー（`|` `>`）、複数ドキュメント、
# 複雑キー、タグ。未対応の記法に出会っても例外は投げず、その行を読み飛ばして先へ進む
# （Hook は「判定不能なら安全側＝許可に倒す」方針であり、パース失敗でツールを止めない）。
# 正確な検証は CI 側の JSON Schema（PyYAML でフルパース）が担う。

def _yaml_split_key(text: str):
    """`key: value` 行を (キー, 値) に分ける。マッピング行でなければ None。

    YAML ではキーの区切りは「空白か行末が続くコロン」だけである。単純な `^(.+?):(.*)$` だと
    `- "tests/test_todo.py::test_x"` のような**値の中にコロンを含む文字列**をマッピングと
    誤認識する（実際に契約の `test_ids` で踏んだ）。
    """
    if not text:
        return None
    n = len(text)
    if text[0] in ("'", '"'):
        quote = text[0]
        i = 1
        while i < n and text[i] != quote:
            if quote == '"' and text[i] == "\\":
                i += 1
            i += 1
        if i >= n:
            return None
        key = text[: i + 1]
        i += 1
        while i < n and text[i] in (" ", "\t"):
            i += 1
        if i < n and text[i] == ":" and (i + 1 >= n or text[i + 1] in (" ", "\t")):
            return key, text[i + 1:].strip()
        return None
    for i, ch in enumerate(text):
        if ch == ":" and (i + 1 >= n or text[i + 1] in (" ", "\t")):
            return text[:i].strip(), text[i + 1:].strip()
    return None


def _yaml_strip_comment(line: str) -> str:
    """引用符の外にある `#` 以降をコメントとして落とす。"""
    out: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if quote == '"' and ch == "\\" and i + 1 < len(line):
                out.append(line[i:i + 2])
                i += 2
                continue
            if ch == quote:
                quote = None
            out.append(ch)
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "#" and (i == 0 or line[i - 1] in (" ", "\t")):
            break
        out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _yaml_scalar(text: str):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    if text in ("", "null", "~", "Null", "NULL"):
        return None
    if text in ("true", "True", "TRUE"):
        return True
    if text in ("false", "False", "FALSE"):
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def _yaml_flow(text: str, pos: int = 0):
    """`{...}` / `[...]` のフロー記法を読む。(値, 次の位置) を返す。"""
    def skip_ws(i: int) -> int:
        while i < len(text) and text[i] in (" ", "\t"):
            i += 1
        return i

    def read_token(i: int, stop: str) -> tuple[str, int]:
        start = i
        quote: str | None = None
        while i < len(text):
            ch = text[i]
            if quote:
                if ch == quote:
                    quote = None
                i += 1
                continue
            if ch in ("'", '"'):
                quote = ch
                i += 1
                continue
            if ch in stop:
                break
            i += 1
        return text[start:i], i

    pos = skip_ws(pos)
    if pos >= len(text):
        return None, pos
    if text[pos] == "{":
        result: dict = {}
        pos += 1
        while True:
            pos = skip_ws(pos)
            if pos >= len(text) or text[pos] == "}":
                return result, pos + 1
            key_text, pos = read_token(pos, ":,}")
            key = _yaml_scalar(key_text)
            pos = skip_ws(pos)
            if pos < len(text) and text[pos] == ":":
                pos += 1
                pos = skip_ws(pos)
                if pos < len(text) and text[pos] in ("{", "["):
                    value, pos = _yaml_flow(text, pos)
                else:
                    value_text, pos = read_token(pos, ",}")
                    value = _yaml_scalar(value_text)
            else:
                value = None
            result[str(key)] = value
            pos = skip_ws(pos)
            if pos < len(text) and text[pos] == ",":
                pos += 1
    if text[pos] == "[":
        items: list = []
        pos += 1
        while True:
            pos = skip_ws(pos)
            if pos >= len(text) or text[pos] == "]":
                return items, pos + 1
            if text[pos] in ("{", "["):
                value, pos = _yaml_flow(text, pos)
            else:
                value_text, pos = read_token(pos, ",]")
                value = _yaml_scalar(value_text)
            items.append(value)
            pos = skip_ws(pos)
            if pos < len(text) and text[pos] == ",":
                pos += 1
    value_text, pos = read_token(pos, ",]}")
    return _yaml_scalar(value_text), pos


_YAML_BLOCK_SCALAR_MARKERS = {"|", ">", "|-", ">-", "|+", ">+"}


def _yaml_consume_block_scalar(lines: list[list], i: int, indent: int, marker: str):
    """ブロックスカラーの本体行（親キーより深いインデントの行）をまとめて読み飛ばす。"""
    body: list[str] = []
    while i < len(lines) and lines[i][0] > indent:
        body.append(lines[i][1])
        i += 1
    joiner = "\n" if marker.startswith("|") else " "
    return joiner.join(body), i


def _yaml_parse_block(lines: list[list], i: int, indent: int):
    """`lines`（(インデント, 本文) の列）の位置 `i` から、インデント `indent` のブロックを読む。"""
    if i < len(lines) and lines[i][1].startswith("-"):
        return _yaml_parse_sequence(lines, i, indent)
    return _yaml_parse_mapping(lines, i, indent)


def _yaml_parse_mapping(lines: list[list], i: int, indent: int):
    result: dict = {}
    while i < len(lines):
        line_indent, text = lines[i]
        if line_indent < indent:
            break
        if line_indent > indent:
            # 未対応の記法などで前の値の解析が本来消費すべき深い行を取りこぼした場合の保険。
            # 丸ごと break して後続の同階層キーを失うより、この行だけ読み飛ばして継続する
            # （Hook は判定不能なら安全側＝許可に倒す方針）。
            i += 1
            continue
        if text.startswith("- ") or text == "-":
            break
        split = _yaml_split_key(text)
        if not split:
            i += 1
            continue
        raw_key, rest = split
        key = str(_yaml_scalar(raw_key))
        if rest in _YAML_BLOCK_SCALAR_MARKERS:
            # ブロックスカラー（`|` / `>`）は正確には解釈しない（Hook の判定に必要な情報が
            # 入ることを想定していない）が、続く行を読み飛ばして後続キーの取りこぼしを防ぐ。
            value, i = _yaml_consume_block_scalar(lines, i + 1, indent, rest)
        elif rest:
            if rest[0] in ("{", "["):
                value, _ = _yaml_flow(rest)
            else:
                value = _yaml_scalar(rest)
            i += 1
        elif i + 1 < len(lines) and (
            lines[i + 1][0] > indent
            or (lines[i + 1][0] == indent and lines[i + 1][1].startswith("-"))
        ):
            value, i = _yaml_parse_block(lines, i + 1, lines[i + 1][0])
        else:
            value = None
            i += 1
        result[key] = value
    return result, i


def _yaml_parse_sequence(lines: list[list], i: int, indent: int):
    items: list = []
    while i < len(lines):
        line_indent, text = lines[i]
        if line_indent != indent or not text.startswith("-"):
            break
        body = text[1:]
        offset = 1 + (len(body) - len(body.lstrip(" ")))
        body = body.strip()
        if not body:
            i += 1
            if i < len(lines) and lines[i][0] > indent:
                value, i = _yaml_parse_block(lines, i, lines[i][0])
            else:
                value = None
            items.append(value)
            continue
        if body[0] in ("{", "["):
            value, _ = _yaml_flow(body)
            items.append(value)
            i += 1
            continue
        if body in _YAML_BLOCK_SCALAR_MARKERS:
            # `- >-` / `- |` のようにシーケンス項目自体がブロックスカラーの場合。
            # `_yaml_parse_mapping` がマッピング値で使うのと同じ読み飛ばしロジックを適用する。
            value, i = _yaml_consume_block_scalar(lines, i + 1, indent, body)
            items.append(value)
            continue
        if _yaml_split_key(body):
            # `- key: value` は「この位置から始まるマッピング」として読み直す
            lines[i] = [indent + offset, body]
            value, i = _yaml_parse_block(lines, i, indent + offset)
            items.append(value)
            continue
        items.append(_yaml_scalar(body))
        i += 1
    return items, i


def parse_simple_yaml(content: str):
    """ハーネスが規定する範囲の YAML を dict/list/スカラーに変換する（依存ゼロ）。
    解釈できない行は読み飛ばす。空なら `{}` を返す。
    """
    lines: list[list] = []
    for raw in content.splitlines():
        stripped = _yaml_strip_comment(raw)
        if not stripped.strip():
            continue
        if stripped.lstrip().startswith(("---", "...")):
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append([indent, stripped.strip()])
    if not lines:
        return {}
    value, _ = _yaml_parse_block(lines, 0, lines[0][0])
    return value


# ======================================================================================
# 検証コマンドの宣言と受領書（CONVENTIONS.md 12節 / Rule 10）
# ======================================================================================
# ハーネスは「どのコマンドを走らせるか」を**規定しない**。アプリ側が
# `shared-kernel.yaml` / `contract.yaml` の `verification:` ブロックで**宣言**し、
# `harness/scripts/run_verification.py` がそれを**解釈せずに実行**して、結果を
# `status.yaml` の `verification_receipt` に記録する。Hook は受領書だけを見る。
# これにより、アプリ非依存性を保ったまま「テストを実際に走らせて通したこと」を強制できる。

# 宣言キー → 受領書のスロット名
VERIFICATION_COMMANDS = {
    "test_command": "test",
    "build_command": "build",
    "typecheck_command": "typecheck",
    "lint_command": "lint",
}
DEFAULT_MAX_SKIP_RATIO = 0.2


def merge_verification_declaration(shared_kernel_content: str, contract_content: str) -> dict:
    """`shared-kernel.yaml`（全機能共通）に `contract.yaml`（機能個別）を上書きして解決する。
    値が null/空文字のキーは「宣言なし」として扱い、上書きにも使わない。
    """
    def _block(content: str) -> dict:
        data = parse_simple_yaml(content) if content else {}
        block = data.get("verification") if isinstance(data, dict) else None
        return block if isinstance(block, dict) else {}

    merged = dict(_block(shared_kernel_content))
    for key, value in _block(contract_content).items():
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        merged[key] = value
    return {k: v for k, v in merged.items() if not (v is None or (isinstance(v, str) and not v.strip()))}


def commits_match(receipt_commit: str | None, head_commit: str | None) -> bool:
    """受領書の commit と現在の HEAD が同一かを判定する。短縮 SHA も許容する。"""
    if not receipt_commit or not head_commit:
        return False
    a, b = str(receipt_commit).strip(), str(head_commit).strip()
    if len(a) < 7 or len(b) < 7:
        return False
    return a.startswith(b) or b.startswith(a)


def extract_declared_test_ids(contract_content: str) -> list[str]:
    """`contract.yaml` の `test_strategy.coverage[].test_ids` を平坦化して返す（⑤ トレーサビリティ）。"""
    data = parse_simple_yaml(contract_content) if contract_content else {}
    strategy = data.get("test_strategy") if isinstance(data, dict) else None
    if not isinstance(strategy, dict):
        return []
    ids: list[str] = []
    for entry in strategy.get("coverage") or []:
        if not isinstance(entry, dict):
            continue
        for test_id in entry.get("test_ids") or []:
            if isinstance(test_id, str) and test_id.strip():
                ids.append(test_id.strip())
    return ids


def extract_declared_interface_test_ids(integration_content: str) -> list[str]:
    """`integration.machine.yaml` の `interface_coverage[].test_ids` を平坦化して返す（Rule 11）。"""
    data = parse_simple_yaml(integration_content) if integration_content else {}
    ids: list[str] = []
    for entry in (data.get("interface_coverage") if isinstance(data, dict) else None) or []:
        if not isinstance(entry, dict):
            continue
        for test_id in entry.get("test_ids") or []:
            if isinstance(test_id, str) and test_id.strip():
                ids.append(test_id.strip())
    return ids


def interface_coverage_gaps(architecture_content: str, integration_content: str) -> list[str]:
    """`architecture.machine.yaml` の `interfaces[]` の各エッジが `integration.machine.yaml` の
    `interface_coverage[]` に1件以上の `test_ids` を伴って宣言されているかを判定する（Rule 11）。
    未宣言・エッジ不一致（producer/consumer の組が architecture 側に存在しない）を文字列で返す。
    """
    arch = parse_simple_yaml(architecture_content) if architecture_content else {}
    interfaces = (arch.get("interfaces") if isinstance(arch, dict) else None) or []

    def _key(entry: dict) -> tuple:
        return (
            entry.get("producer_feature"), entry.get("producer_output"),
            entry.get("consumer_feature"), entry.get("consumer_input"),
        )

    required = {_key(i) for i in interfaces if isinstance(i, dict)}

    record = parse_simple_yaml(integration_content) if integration_content else {}
    coverage = (record.get("interface_coverage") if isinstance(record, dict) else None) or []
    covered = {
        _key(c): c
        for c in coverage
        if isinstance(c, dict) and c.get("test_ids")
    }

    gaps = []
    for key in sorted(k for k in required if k not in covered):
        pf, po, cf, ci = key
        gaps.append(
            f"interfaces[] {pf}.{po} -> {cf}.{ci} が integration.machine.yaml の "
            f"interface_coverage[] に test_ids 付きで宣言されていません"
        )
    return gaps


def validate_verification_receipt(
    declaration: dict,
    receipt,
    head_commit: str | None,
    declared_test_ids: list | None = None,
    *,
    target_state: str = "TESTED",
    declaration_label: str = "`contract.yaml` の `test_strategy.coverage[]`",
    rerun_hint: str = (
        "`python3 harness/scripts/run_verification.py --app <app-id> --feature <feature-id>` を"
        "実行して受領書を作り直してください（受領書は手書きできません）。"
    ),
) -> str | None:
    """`state: <target_state>` を許可してよいかを、宣言と受領書と現在の HEAD から判定する。
    妥当なら None、拒否すべきなら理由の文字列を返す。`target_state`/`rerun_hint` は
    `run_integration_verification.py`（Rule 11）のように、宣言・受領書の置き場所や
    再実行コマンドが機能単位の TESTED ゲートと異なる呼び出し元向けの上書き。
    """
    hint = rerun_hint
    test_command = declaration.get("test_command")
    if not test_command:
        return (
            f"拒否: `verification.test_command` が宣言されていないため、{target_state} にできません。\n"
            "`01-foundation/shared-kernel.yaml`（全機能共通）か `contract.yaml`（機能個別）の\n"
            "`verification:` ブロックに、この機能のテストを実行するコマンドを宣言してください\n"
            "（ハーネスはコマンドの中身を解釈しません。終了コードだけを見ます）。"
        )
    if not isinstance(receipt, dict) or not receipt:
        return f"拒否: `verification_receipt` が無いため {target_state} にできません。\n{hint}"
    if not commits_match(receipt.get("commit"), head_commit):
        return (
            f"拒否: `verification_receipt.commit`（{receipt.get('commit')!r}）が現在の HEAD"
            f"（{head_commit!r}）と一致しません。\n"
            f"受領書は「そのコミットの状態で通った」という主張であり、実装が進めば無効になります。\n{hint}"
        )
    for key, slot in VERIFICATION_COMMANDS.items():
        if not declaration.get(key):
            continue
        entry = receipt.get(slot)
        if not isinstance(entry, dict):
            return f"拒否: `verification.{key}` が宣言されていますが、受領書に `{slot}` の記録がありません。\n{hint}"
        if entry.get("exit_code") != 0:
            return (
                f"拒否: `verification.{key}` の実行が失敗しています"
                f"（`{slot}.exit_code` = {entry.get('exit_code')!r}）。\n"
                f"原因を修正してから受領書を作り直してください。"
            )
    if declaration.get("junit_xml"):
        reason = validate_junit_summary(declaration, receipt.get("test") or {})
        if reason:
            return reason
        reason = validate_traceability(
            declared_test_ids, receipt.get("traceability"),
            target_state=target_state, declaration_label=declaration_label, rerun_hint=hint,
        )
        if reason:
            return reason
    return None


def validate_traceability(
    declared_test_ids: list | None,
    traceability,
    *,
    target_state: str = "TESTED",
    declaration_label: str = "`contract.yaml` の `test_strategy.coverage[]`",
    rerun_hint: str = (
        "`python3 harness/scripts/run_verification.py --app <app-id> --feature <feature-id>` を"
        "実行して受領書を作り直してください。"
    ),
) -> str | None:
    """宣言された対応づけ（要件↔テスト、または interfaces[] のエッジ↔テスト）が実在し、
    実際に成功したかを判定する（⑤）。1 件も宣言されていなければ何も要求しない
    （トレーサビリティは JUnit XML を宣言している場合のオプトイン）。
    """
    if not declared_test_ids:
        return None
    hint = rerun_hint
    if not isinstance(traceability, dict):
        return (
            f"拒否: {declaration_label} にテスト識別子が"
            f"{len(declared_test_ids)} 件宣言されていますが、受領書に突合結果"
            f"（`traceability`）がありません。\n{hint}"
        )
    missing = traceability.get("missing") or []
    failed = traceability.get("failed") or []
    if missing:
        return (
            f"拒否: 宣言された次のテストが JUnit XML に見つかりません: {', '.join(map(str, missing))}\n"
            f"対応づけたテストが実在しないまま {target_state} にはできません"
            f"（テストを書くか、`test_ids` の書き方を実際の出力に合わせてください。"
            f"`@pytest.mark.parametrize` 等のパラメータ化テストは JUnit XML 上の名前に"
            f"`test_x[param]` のように末尾 `[...]` が付くため要注意——`test_ids` 側は"
            f"パラメータなしの名前（`test_x`）で書いて構いません）。"
        )
    if failed:
        return (
            f"拒否: 宣言された次のテストが成功していません: {', '.join(map(str, failed))}"
        )
    if traceability.get("declared") != len(declared_test_ids):
        return (
            f"拒否: 受領書のトレーサビリティ件数（{traceability.get('declared')!r}）が宣言"
            f"（{len(declared_test_ids)} 件）と一致しません。変更したなら検証をやり直してください。\n{hint}"
        )
    return None


def validate_junit_summary(declaration: dict, test_entry: dict) -> str | None:
    """受領書に記録された JUnit XML の集計値を検証する（③: 空振り・スキップ率の検出）。
    JUnit XML は pytest/jest/vitest/go-test/cargo/JUnit/RSpec/PHPUnit がいずれも出力できる
    事実上のクロススタック標準であり、ハーネスは言語を知らずにこれらを判定できる。
    """
    tests = test_entry.get("tests")
    if not isinstance(tests, int):
        return (
            "拒否: `verification.junit_xml` が宣言されていますが、受領書にテスト件数"
            "（`test.tests`）が記録されていません。"
        )
    if tests <= 0:
        return (
            "拒否: テストが 1 件も実行されていません（`test.tests` = 0）。\n"
            "テストを 1 件も走らせずに TESTED を宣言することはできません"
            "（テストの収集条件やパスの指定を見直してください）。"
        )
    failures = test_entry.get("failures") or 0
    errors = test_entry.get("errors") or 0
    if failures or errors:
        return f"拒否: 失敗しているテストがあります（failures={failures}, errors={errors}）。"
    skipped = test_entry.get("skipped") or 0
    try:
        max_ratio = float(declaration.get("max_skip_ratio", DEFAULT_MAX_SKIP_RATIO))
    except (TypeError, ValueError):
        max_ratio = DEFAULT_MAX_SKIP_RATIO
    if tests and skipped / tests > max_ratio:
        return (
            f"拒否: スキップされたテストの割合が上限を超えています"
            f"（{skipped}/{tests} = {skipped / tests:.0%} > {max_ratio:.0%}）。\n"
            f"スキップを減らすか、`verification.max_skip_ratio` を設計時に見直してください。"
        )
    return None


# --- 承認記録の同時性（Rule 3 / Rule 7・CONVENTIONS.md 9節） ------------------

APPROVAL_FIELDS = ("approved_by", "approved_at")
_EMPTY_APPROVAL_SCALARS = {"", "null", "~", "none", "tbd", "todo"}


def approval_value_is_empty(value) -> bool:
    """承認者・承認日時が「実質空」かを判定する（`null` / 空文字 / プレースホルダ）。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().strip("\"'").lower() in _EMPTY_APPROVAL_SCALARS
    return False


def find_empty_approval_fields(data) -> list:
    """マッピングから、空のままの承認フィールド名を列挙する。"""
    if not isinstance(data, dict):
        return []
    return [k for k in APPROVAL_FIELDS if approval_value_is_empty(data.get(k))]


def validate_approval_record(content: str, doc_label: str, approved_value: str = "APPROVED") -> str | None:
    """`status: APPROVED` への書き込みが承認者の記録を伴っているかを判定する。

    9節は「APPROVED なら `approved_by`/`approved_at` が非 null」をスキーマで強制すると規定するが、
    スキーマ検査は誰かが明示的に走らせて初めて働くため、`status` だけを先に APPROVED にした
    中間状態が書き込み時点では素通りしていた（ドッグフーディング F-020）。書き込みのたびに
    同じ条件を強制することで、承認の痕跡を伴わない APPROVED を機械的に防ぐ。

    判定不能（パースできない・status がそもそも承認値でない）なら None を返す。
    """
    try:
        data = parse_simple_yaml(content) if content else {}
    except Exception:
        return None  # パースできない中間状態はブロックしない（安全側）
    if not isinstance(data, dict) or data.get("status") != approved_value:
        return None
    missing = find_empty_approval_fields(data)
    if not missing:
        return None
    return (
        f"拒否: {doc_label} を status: {approved_value} にしようとしていますが、"
        f"{' と '.join(missing)} が空のままです。\n"
        "承認は人間が行うものであり、承認者と承認日時の記録を伴わない承認は認められません"
        "（CONVENTIONS.md 9節）。status を変えるのと同じ書き込みで "
        "`approved_by`（承認した人間の識別子）と "
        "`approved_at`（`date -u +%Y-%m-%dT%H:%M:%SZ` で取得）を設定してください。"
    )


# ======================================================================================
# Rule 12: 危険操作フロア（CONVENTIONS.md 7節）
# ======================================================================================
# 他の Rule はすべて「工程の整合性」を守るもので、危険操作を止める規則は 1 件も無かった。
# AUTONOMOUS モードで長時間走らせる前提のハーネスとして、これは実運用上いちばん重い穴だった。
#
# 判定は**既存の Bash トークナイザ**（`_tokenize_bash_command` / `_BASH_SEGMENT_BREAKS`）を
# 再利用する。新しいパース系を増やすと、片方だけ直して検知が食い違う。
#
# **バイパス用の環境変数は用意しない**（INV-4）。AI 自身が解除できてしまえば決定論的強制の
# 目的そのものが崩れる。誤検知はこの検知ロジック自体を直して対応する。

def iter_bash_segments(command: str) -> list[list[str]]:
    """Bash コマンド文字列を「1 コマンド分」のトークン列に分割する。

    `extract_bash_candidate_paths` が内部で行っている分割を、書き込み先の抽出以外の判定
    （Rule 12）からも使えるように切り出したもの。両者は必ず同じトークン化を通る。
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
    return [s for s in segments if s]


# --- D-2: 秘密ファイル -----------------------------------------------------------------

SECRET_PATH_PATTERNS = (
    r"(^|/)\.env$",
    r"(^|/)\.env\.[^/]+$",
    r"\.pem$",
    r"\.key$",
    r"(^|/)[^/]*id_rsa[^/]*$",
    r"(^|/)[^/]*id_ed25519[^/]*$",
    r"(^|/)\.ssh(/|$)",
    r"(^|/)\.aws(/|$)",
    r"(^|/)\.npmrc$",
    r"(^|/)\.netrc$",
    r"(^|/)credentials\.json$",
)
# 秘密そのものではなく「秘密の書き方の見本」。実運用で必ず読む必要があるため除外する。
SECRET_PATH_EXEMPT_RE = re.compile(r"(^|/)\.env\.(example|sample|template|dist)$")
_SECRET_PATH_RE = re.compile("|".join(SECRET_PATH_PATTERNS))

# ファイルの中身を読み出す代表的なコマンド。ここに無いコマンドの引数に現れたパスは、
# 読み取りとは限らない（例: `echo ".env" >> .gitignore`）ので対象にしない。
SECRET_READ_COMMANDS = {
    "cat", "head", "tail", "less", "more", "bat", "nl", "od", "xxd", "strings",
    "base64", "cut", "tac", "readlink", "openssl",
}


def is_secret_path(path: str) -> bool:
    """秘密ファイルとみなすパスか。`.env.example` 等の見本は除外する。"""
    normalized = str(path).replace("\\", "/").strip().strip("\"'")
    if not normalized:
        return False
    if SECRET_PATH_EXEMPT_RE.search(normalized):
        return False
    return bool(_SECRET_PATH_RE.search(normalized))


# --- D-1: 再帰削除 ---------------------------------------------------------------------

# 綴りだけで拒否する削除対象。解決を試みるまでもなく、リポジトリ配下に留まる保証が無い。
_UNRESOLVABLE_TARGET_RE = re.compile(r"(^|/)\.\.(/|$)|\$|^~|^/$|^\.$|^\*")


def _is_flag(token: str) -> bool:
    return token.startswith("-") and token != "-"


def _recursive_delete_targets(tokens: list[str]) -> list[str]:
    """`rm -r` / `find ... -delete` の削除対象を返す（対象が無ければ空）。"""
    cmd, args = tokens[0], tokens[1:]
    if cmd == "rm":
        recursive = any(
            a == "--recursive" or (_is_flag(a) and not a.startswith("--") and ("r" in a or "R" in a))
            for a in args
        )
        if not recursive:
            return []
        return [a for a in args if not _is_flag(a)]
    if cmd == "find":
        if not any(a in ("-delete", "-exec", "-execdir") for a in args):
            return []
        targets = []
        for a in args:
            if _is_flag(a):
                break  # find の探索パスは述語（`-name` 等）より前にしか現れない
            targets.append(a)
        return targets or ["."]
    return []


# --- D-3 / D-4: 履歴の破壊と検証のスキップ ----------------------------------------------

_GIT_DESTRUCTIVE = {
    "push": (("--force", "-f", "--force-with-lease"), "リモート履歴の破壊"),
    "reset": (("--hard",), "作業ツリーと履歴の破棄"),
    "filter-branch": ((), "履歴の書き換え"),
}
_GIT_VERIFICATION_SKIP = ("--no-verify", "-n", "--no-gpg-sign")


def _git_subcommand(tokens: list[str]) -> tuple[str | None, list[str]]:
    """`git -C dir push --force` のような前置オプションを飛ばしてサブコマンドを返す。"""
    args = tokens[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"):
            i += 2
            continue
        if _is_flag(a):
            i += 1
            continue
        return a, args[i + 1:]
    return None, []


# --- D-5: 外部送信 ---------------------------------------------------------------------

_EGRESS_COMMANDS = {"curl", "wget", "nc", "ncat", "netcat", "socat"}
_EGRESS_UPLOAD_FLAGS = {
    "-d", "--data", "--data-binary", "--data-raw", "--data-urlencode",
    "-F", "--form", "-T", "--upload-file", "--post-data", "--post-file",
}
# ここへ到達できると、秘密や内部情報が匿名で外に出る。到達自体を拒否する。
_EGRESS_HOSTS = (
    "pastebin.com", "hastebin.com", "dpaste.", "paste.rs", "ix.io", "sprunge.us",
    "termbin.com", "transfer.sh", "0x0.st", "file.io", "gist.github.com",
    "webhook.site", "requestbin.", "ngrok.io", "ngrok-free.app", "bashupload.com",
    "oshi.at", "litterbox.catbox.moe", "catbox.moe",
)


def _is_upload(tokens: list[str]) -> str | None:
    cmd, args = tokens[0], tokens[1:]
    if cmd not in _EGRESS_COMMANDS:
        return None
    joined = " ".join(args)
    for host in _EGRESS_HOSTS:
        if host in joined:
            return f"{cmd} による {host} への到達"
    if cmd in ("nc", "ncat", "netcat", "socat"):
        return None  # ホスト名が上に無ければ、宛先が判定できない。綴りだけでは止めない
    for i, a in enumerate(args):
        # `--post-file=x` のような `=` 付きの綴りも同じ扱いにする
        flag = a.split("=", 1)[0]
        if flag in _EGRESS_UPLOAD_FLAGS or flag.startswith("--data"):
            return f"{cmd} によるデータ送信（{flag}）"
        if a in ("-X", "--request") and i + 1 < len(args) and args[i + 1].upper() in (
            "POST", "PUT", "PATCH", "DELETE"
        ):
            return f"{cmd} による {args[i + 1].upper()} リクエスト"
    return None


# --- 判定本体 ---------------------------------------------------------------------------

DANGEROUS_OPS_HINT = (
    "\nこの操作はハーネスが無条件に拒否します（CONVENTIONS.md 7節 Rule 12）。"
    "解除用の環境変数はありません。\n"
    "必要な操作なら、AI ではなく**人間が自分の手で**実行してください。"
    "誤検知だと考える場合は、検知ロジック（`path_utils` の Rule 12 節）を直して対応します。"
)


def detect_dangerous_bash_operation(
    command: str, cwd: str, toplevel: str, resolve=None
) -> str | None:
    """Bash コマンドが Rule 12 の禁止操作を含むなら、拒否理由を返す。

    `resolve` は `(target, cwd, toplevel) -> (rel_path, root)` の解決関数（既定は
    `resolve_write_target`）。テストから差し替えられるようにしてある。
    """
    resolve = resolve or resolve_write_target
    for tokens in iter_bash_segments(command):
        cmd = tokens[0]

        # D-6: sudo を伴う任意コマンド
        if cmd in ("sudo", "doas", "su"):
            return (
                f"拒否: `{cmd}` を伴うコマンドは実行できません（D-6）。\n"
                "権限昇格を伴う操作は、影響範囲がリポジトリの外に及びます。" + DANGEROUS_OPS_HINT
            )

        # D-1: リポジトリルート外への再帰削除
        for target in _recursive_delete_targets(tokens):
            if _UNRESOLVABLE_TARGET_RE.search(target):
                return (
                    f"拒否: 再帰削除の対象 {target!r} が、リポジトリ配下に留まると確認できません（D-1）。\n"
                    "`..` を含む綴り・未展開の変数・`/`・`.`・ワイルドカードの先頭指定は、"
                    "解決するまでもなく拒否します。削除したいパスを、リポジトリルートからの"
                    "相対パスで明示してください。" + DANGEROUS_OPS_HINT
                )
            rel, _root = resolve(target, cwd, toplevel)
            if rel.startswith("/") or rel.startswith("../") or rel == "..":
                return (
                    f"拒否: {target!r} はリポジトリの外を指しています。再帰削除はできません（D-1）。"
                    + DANGEROUS_OPS_HINT
                )

        # D-2: 秘密ファイルの読み取り
        if cmd in SECRET_READ_COMMANDS:
            for a in tokens[1:]:
                if not _is_flag(a) and is_secret_path(a):
                    return (
                        f"拒否: {a!r} は秘密情報を含みうるファイルです。読み取れません（D-2）。\n"
                        "設定値が必要なら、値そのものではなく `.env.example` などの見本を参照するか、"
                        "ユーザーに必要な項目名を尋ねてください。" + DANGEROUS_OPS_HINT
                    )

        # D-3 / D-4: 履歴の破壊と検証のスキップ
        if cmd == "git":
            sub, rest = _git_subcommand(tokens)
            if sub == "clean" and any(
                _is_flag(a) and not a.startswith("--") and "x" in a and "f" in a for a in rest
            ):
                return (
                    "拒否: `git clean -fdx` は無視されているファイルごと消します（D-3）。\n"
                    "消したい対象を個別に指定してください。" + DANGEROUS_OPS_HINT
                )
            if sub in _GIT_DESTRUCTIVE:
                flags, label = _GIT_DESTRUCTIVE[sub]
                if not flags or any(a in flags for a in rest):
                    return (
                        f"拒否: `git {sub}` による{label}はできません（D-3）。\n"
                        "履歴が壊れると、受領書（Rule 10）が指すコミットも辿れなくなります。"
                        "やり直しが必要なら、打ち消しコミットを積んでください。" + DANGEROUS_OPS_HINT
                    )
            if sub == "commit" and any(a in _GIT_VERIFICATION_SKIP for a in rest):
                return (
                    "拒否: 検証を飛ばすコミット（`--no-verify` 等）はできません（D-4）。\n"
                    "フックが止めているなら、止めている理由のほうを解消してください。"
                    + DANGEROUS_OPS_HINT
                )

        # D-5: 外部送信
        egress = _is_upload(tokens)
        if egress:
            return (
                f"拒否: {egress} はできません（D-5）。\n"
                "リポジトリの内容を外部に送る操作は、送り先と内容を人間が確認する必要があります。"
                + DANGEROUS_OPS_HINT
            )
    return None


def detect_dangerous_read(path: str) -> str | None:
    """Read ツールが秘密ファイルを開こうとしていないか（D-2 の構造化ツール側）。"""
    if not is_secret_path(path):
        return None
    return (
        f"拒否: {path!r} は秘密情報を含みうるファイルです。読み取れません（D-2）。\n"
        "設定値が必要なら、値そのものではなく `.env.example` などの見本を参照するか、"
        "ユーザーに必要な項目名を尋ねてください。" + DANGEROUS_OPS_HINT
    )
