#!/usr/bin/env python3
"""apps/<app_id>/03-features/*/status.yaml を集約し、
apps/<app_id>/PROGRESS.md（人間向け）と STATE.machine.yaml（機械向け）を再生成する。

このスクリプトの出力する2ファイルは手書き禁止。post_tool_use_sync.py から
status.yaml 更新時に自動で呼ばれるほか、`sync-progress` skill から手動でも呼べる。

`--html` を付けると、同じデータから非エンジニア向けの単一ファイル HTML
（apps/<app_id>/PROGRESS.html）も生成する。**入力は status.yaml / contract.yaml の
open_issues / VERSION / 強制レイヤの診断だけ**で、AI に作文させない（決定論を維持する）。
生成物は .gitignore 対象（派生物は判断の根拠にしない）。

使い方:
    python3 harness/scripts/render_progress.py --app <app_id> [--html]
    python3 harness/scripts/render_progress.py --all [--html]
"""
from __future__ import annotations

import argparse
import html
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402

STATE_LABEL = {
    "NOT_STARTED": "未着手",
    "CONTRACT_DRAFTED": "契約ドラフト中",
    "CONTRACT_APPROVED": "契約承認済み",
    "IN_PROGRESS": "実装中",
    "IMPLEMENTED": "実装完了",
    "TESTED": "テスト完了",
    "INTEGRATED": "統合済み",
    "BLOCKED": "ブロック中",
    "SUPERSEDED": "置き換え済み",
}

DONE_STATES = {"INTEGRATED", "SUPERSEDED"}


TIMESTAMP_LINE_RE = re.compile(r"^(生成日時|generated_at)\s*:.*$", re.MULTILINE)


def write_if_changed(path: pathlib.Path, new_text: str) -> None:
    """タイムスタンプ行以外に変化が無ければ書き込まない。

    毎回タイムスタンプだけが変わると、`status.yaml` を進めるたびに PROGRESS.md /
    STATE.machine.yaml が dirty になり、意味の無いコミットが要求される
    （Rule 8 が未コミットのまま停止することを拒否するため、実際に 1 コミット消費した）。
    `ci_check.py` の項目 G もこの行を無視して比較しているので、差分の本体だけを見て判断する。
    """
    try:
        old_text = path.read_text(encoding="utf-8")
    except OSError:
        old_text = None
    if old_text is not None:
        normalize = lambda s: TIMESTAMP_LINE_RE.sub("", s)  # noqa: E731
        if normalize(old_text) == normalize(new_text):
            return
    path.write_text(new_text, encoding="utf-8")


def _last_updated_at(status_path: pathlib.Path) -> str:
    try:
        return str(_common.load_yaml(status_path).get("last_updated_at") or "")
    except Exception:  # noqa: BLE001
        return ""


def _collect_status_paths(app_dir: pathlib.Path) -> list[pathlib.Path]:
    """feature_id ごとの status.yaml パスを集める。

    機能は実装が終わって main にマージされるまで、対応する worktree
    （apps/<app_id>/.worktrees/<feature_id>/apps/<app_id>/03-features/<feature_id>/）
    にしか存在しない。進捗を正しく横断表示するため、main 側 (03-features/) と
    各 worktree 側の両方を見て、feature_id が重なる場合は `last_updated_at` が新しい方
    （F-056: マージ直後は main 側が INTEGRATED に進んでいても worktree 側がまだ削除されて
    おらず古い状態のままのことがあるため、無条件の worktree 優先はしない）を採用する。
    どちらかの読み込みに失敗した、またはタイムスタンプが同値の場合は worktree 側を優先する
    （実装中は worktree にしか無いことが多いため）。
    """
    app_id = app_dir.name
    by_feature_id: dict[str, pathlib.Path] = {}

    features_dir = app_dir / "03-features"
    if features_dir.exists():
        for status_path in sorted(features_dir.glob("*/status.yaml")):
            by_feature_id[status_path.parent.name] = status_path

    worktrees_dir = app_dir / ".worktrees"
    if worktrees_dir.exists():
        pattern = f"*/apps/{app_id}/03-features/*/status.yaml"
        for status_path in sorted(worktrees_dir.glob(pattern)):
            feature_id = status_path.parent.name
            main_path = by_feature_id.get(feature_id)
            if main_path is None or _last_updated_at(status_path) >= _last_updated_at(main_path):
                by_feature_id[feature_id] = status_path
            # else: main 側の方が新しいので worktree 側で上書きしない

    return [by_feature_id[k] for k in sorted(by_feature_id)]


def render_app(app_dir: pathlib.Path, as_html: bool = False) -> None:
    app_id = app_dir.name
    statuses = []
    for status_path in _collect_status_paths(app_dir):
        try:
            statuses.append(_common.load_yaml(status_path))
        except Exception as e:  # noqa: BLE001
            print(f"警告: {status_path} の読み込みに失敗: {e}", file=sys.stderr)

    requirements_path = app_dir / "00-requirements" / "requirements.machine.yaml"
    architecture_path = app_dir / "02-design" / "architecture.machine.yaml"
    autonomy_path = app_dir / "AUTONOMY.yaml"
    req_status = "N/A"
    design_status = "N/A"
    autonomy_mode = "N/A"
    if requirements_path.exists():
        try:
            req_status = _common.load_yaml(requirements_path).get("status", "N/A")
        except Exception:  # noqa: BLE001
            pass
    if architecture_path.exists():
        try:
            design_status = _common.load_yaml(architecture_path).get("status", "N/A")
        except Exception:  # noqa: BLE001
            pass
    if autonomy_path.exists():
        try:
            autonomy_mode = _common.load_yaml(autonomy_path).get("mode", "N/A")
        except Exception:  # noqa: BLE001
            pass

    _write_progress_md(app_dir, app_id, req_status, design_status, autonomy_mode, statuses)
    _write_state_machine_yaml(app_dir, app_id, req_status, design_status, autonomy_mode, statuses)
    generated = [str(app_dir / "PROGRESS.md"), str(app_dir / "STATE.machine.yaml")]
    if as_html:
        _write_progress_html(app_dir, app_id, req_status, design_status, autonomy_mode, statuses)
        generated.append(str(app_dir / "PROGRESS.html"))
    print("再生成しました: " + ", ".join(generated))


def _write_progress_md(app_dir, app_id, req_status, design_status, autonomy_mode, statuses) -> None:
    lines = []
    lines.append(f"# 進捗ダッシュボード: {app_id}")
    lines.append("")
    lines.append("> **このファイルは自動生成です。手書きで編集しないでください。**")
    lines.append("> `harness/scripts/render_progress.py` が `03-features/*/status.yaml` から再生成します。")
    lines.append("")
    lines.append(f"生成日時: {_common.now_iso()}")
    lines.append("")
    lines.append(f"- 自動化モード (autonomy_mode): **{autonomy_mode}**"
                  f"（`AUTONOMY.yaml` 参照。要件定義の承認はモードに関わらず常に人間必須）")
    lines.append(f"- 要件定義 (00-requirements): **{req_status}**")
    lines.append(f"- 設計 (02-design): **{design_status}**")
    lines.append(_enforcement_line(app_dir))
    lines.append(_harness_version_line(app_dir))
    lines.append("")

    if not statuses:
        lines.append("機能はまだ登録されていません（`new-feature-worktree` skill で追加してください）。")
        lines.append("")  # 次の見出しの直前は必ず空行にする（Markdown が見出しとして解釈しない）
    else:
        done = sum(1 for s in statuses if s.get("state") in DONE_STATES)
        lines.append(f"## 機能一覧 ({done}/{len(statuses)} 完了)")
        lines.append("")
        lines.append("| feature_id | 状態 | 検証 | レビュー | 担当 | ブロッカー | 最終更新 |")
        lines.append("|---|---|---|---|---|---|---|")
        for s in statuses:
            state = s.get("state", "?")
            label = STATE_LABEL.get(state, state)
            assignee = s.get("assignee") or "-"
            blockers = ", ".join(s.get("blockers") or []) or "-"
            updated = s.get("last_updated_at", "-")
            lines.append(
                f"| {s.get('feature_id', '?')} | {label} ({state}) | {_verification_summary(s)} | "
                f"{_review_summary(s)} | {assignee} | {blockers} | {updated} |"
            )
        lines.append("")

        blocked = [s for s in statuses if s.get("state") == "BLOCKED"]
        if blocked:
            lines.append("## ブロック中の機能")
            lines.append("")
            for s in blocked:
                lines.append(f"- `{s.get('feature_id')}`: {', '.join(s.get('blockers') or ['(理由未記録)'])}")
            lines.append("")

    lines.append("## 次にすべきこと")
    lines.append("")
    not_started = [s for s in statuses if s.get("state") == "NOT_STARTED"]
    in_progress = [s for s in statuses if s.get("state") in ("CONTRACT_APPROVED", "IN_PROGRESS")]
    implemented = [s for s in statuses if s.get("state") in ("IMPLEMENTED", "TESTED")]
    if req_status != "APPROVED":
        lines.append("- 要件定義がまだ承認されていません。`requirements-analyst` subagent で完了させてください。")
    elif design_status != "APPROVED":
        lines.append("- 設計がまだ承認されていません。`solution-architect` subagent で完了させてください。")
    else:
        if not_started:
            ids = ", ".join(s["feature_id"] for s in not_started)
            lines.append(f"- 未着手の機能があります: {ids}。`new-feature-worktree` skill で着手してください。")
        if in_progress:
            ids = ", ".join(s["feature_id"] for s in in_progress)
            lines.append(f"- 実装中の機能があります: {ids}。")
        if implemented:
            ids = ", ".join(s["feature_id"] for s in implemented)
            lines.append(f"- 統合待ちの機能があります: {ids}。`integrator` subagent で組み上げてください。")
        if statuses and all(s.get("state") in DONE_STATES for s in statuses):
            lines.append("- 全機能が統合済みです。")
    lines.append("")

    write_if_changed(app_dir / "PROGRESS.md", "\n".join(lines))


def _harness_dir(app_dir: pathlib.Path) -> pathlib.Path:
    """このアプリを作っているハーネス本体のディレクトリ。

    `_common.harness_root()` は git 情報から**メインリポジトリ側**を返す（worktree の
    スナップショットと食い違わないため。F-049）。git 情報が取れない場所ではそれが
    `<app_dir>/harness` に退避してしまうので、`apps/<app-id>` という構造上の位置関係
    （CONVENTIONS.md 1節）からも解決を試みる。
    """
    candidate = _common.harness_root(app_dir)
    if candidate.is_dir():
        return candidate
    return app_dir.parent.parent / "harness"


def _harness_version_line(app_dir: pathlib.Path) -> str:
    """このアプリを作っているハーネスの版（`VERSION`）。

    どの版のハーネスで作られたアプリなのかが成果物から辿れないと、不具合報告と改修の
    対応が取れない（CI 項目 Q）。
    """
    try:
        version = (_harness_dir(app_dir).parent / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "- ハーネス版: **不明**（`VERSION` が読めません）"
    return f"- ハーネス版: **v{version}**"


def _enforcement_line(app_dir: pathlib.Path) -> str:
    """強制レイヤの健全性を 1 行で表示する（F-A2）。

    Hook が起動に失敗しても Claude Code はそれを「通過」として扱うため、強制が黙って
    無効化された状態が続きうる。ダッシュボードは人間が状況を確認する最終的な担保
    （CONVENTIONS.md 9節）なので、そこに状態を出す。

    実行環境（Python のバージョン等）に依存する判定は含めない。`PROGRESS.md` は
    コミットされる成果物で、CI の項目 G が再生成結果との一致を見るため、環境ごとに
    差分が出る値を混ぜると構造的に不合格になる。
    """
    try:
        harness = _harness_dir(app_dir)
        # hooks は依存ゼロで、scripts より後に読み込まれる。ここで初めて import することで、
        # hooks が欠けている環境でもダッシュボードの生成自体は止めない（止めると Rule 4 が
        # 連鎖して壊れ、進捗が見えなくなる ＝ 可視化したい状況で可視化が消える）。
        sys.path.insert(0, str(harness / "hooks"))
        import session_start_healthcheck  # noqa: PLC0415

        return session_start_healthcheck.progress_line(str(harness.parent))
    except Exception as exc:  # noqa: BLE001
        return f"- 強制レイヤ: **診断不能**（{type(exc).__name__}: {exc}）"


def _verification_summary(status: dict) -> str:
    """`verification_receipt` を人間向けに 1 セルへ要約する（CONVENTIONS.md 12節）。"""
    receipt = status.get("verification_receipt")
    if not isinstance(receipt, dict) or not receipt.get("commit"):
        return "未実行"
    failed = [
        slot for slot in ("test", "build", "typecheck", "lint")
        if isinstance(receipt.get(slot), dict) and receipt[slot].get("exit_code") != 0
    ]
    if failed:
        return f"失敗 ({', '.join(failed)})"
    test = receipt.get("test") or {}
    detail = f" {test['tests']}件" if isinstance(test.get("tests"), int) else ""
    skipped = test.get("skipped") or 0
    if skipped:
        detail += f"（skip {skipped}）"
    return f"OK{detail} @{str(receipt['commit'])[:7]}"


def _review_summary(status: dict) -> str:
    """`gate-reviewer` の審査結果を人間向けに 1 セルへ要約する（CONVENTIONS.md 10節）。
    **これは記録であって証明ではない**（受領書と違い実行の裏付けを持たない）。
    """
    review = status.get("review")
    if not isinstance(review, dict) or not review.get("verdict"):
        return "未実施"
    verdict = review["verdict"]
    rounds = review.get("rounds")
    suffix = f"（{rounds}R）" if rounds else ""
    blockers = review.get("blockers")
    if verdict == "NO-GO" and blockers:
        suffix = f"（{rounds}R / Blocker {blockers}）"
    return f"{verdict}{suffix}"


def _write_state_machine_yaml(app_dir, app_id, req_status, design_status, autonomy_mode, statuses) -> None:
    state = {
        "app_id": app_id,
        "generated_at": _common.now_iso(),
        "autonomy_mode": autonomy_mode,
        "requirements_status": req_status,
        "design_status": design_status,
        "features": [
            {
                "id": s.get("feature_id"),
                "state": s.get("state"),
                "assignee": s.get("assignee"),
                "branch": s.get("branch"),
                "worktree_path": s.get("worktree_path"),
                "blockers": s.get("blockers") or [],
                "superseded_by": s.get("superseded_by"),
                "verification": _verification_summary(s),
                "review": _review_summary(s),
                "last_updated_at": s.get("last_updated_at"),
            }
            for s in statuses
        ],
    }
    import yaml

    write_if_changed(
        app_dir / "STATE.machine.yaml",
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False),
    )


# --------------------------------------------------------------------------------------
# 非エンジニア向けの HTML 面（T-030 / F-A8）
#
# 新しい skill は増やさない（NG-3）。既に決定論的なレンダラがあるのだから、その出力形式を
# 1 つ足すだけでよい。**AI に作文させない**ことが要点で、入力は status.yaml と
# contract.yaml の open_issues、VERSION、強制レイヤの診断だけ。
# --------------------------------------------------------------------------------------

# 状態 → (表示ラベル, タグの色クラス)
_HTML_STATE_TAG = {
    "NOT_STARTED": "tag-idle",
    "CONTRACT_DRAFTED": "tag-idle",
    "CONTRACT_APPROVED": "tag-warn",
    "IN_PROGRESS": "tag-warn",
    "IMPLEMENTED": "tag-warn",
    "TESTED": "tag-ok",
    "INTEGRATED": "tag-ok",
    "BLOCKED": "tag-bad",
    "SUPERSEDED": "tag-idle",
}


def _tag(text: str, css_class: str) -> str:
    return f'<span class="tag {css_class}">{html.escape(str(text))}</span>'


def _verification_tag(status: dict) -> str:
    summary = _verification_summary(status)
    if summary.startswith("OK"):
        return _tag(summary, "tag-ok")
    if summary.startswith("失敗"):
        return _tag(summary, "tag-bad")
    return _tag(summary, "tag-idle")


def _review_tag(status: dict) -> str:
    summary = _review_summary(status)
    if summary.startswith("GO"):
        return _tag(summary, "tag-ok")
    if summary.startswith("NO-GO"):
        return _tag(summary, "tag-bad")
    return _tag(summary, "tag-idle")


def _collect_open_issues(app_dir: pathlib.Path, statuses: list) -> list[tuple[str, dict]]:
    """各機能の `contract.yaml` から未解決の `open_issues[]` を集める（CONVENTIONS.md 7節 Rule 3）。

    契約の穴は凍結後も追記だけが許されており、統合時に拾われるべき申し送りである。
    人間が見る面に出ないと、追記した意味が薄れる。
    """
    issues: list[tuple[str, dict]] = []
    for status_path in _collect_status_paths(app_dir):
        contract_path = status_path.parent / "contract.yaml"
        if not contract_path.exists():
            continue
        try:
            contract = _common.load_yaml(contract_path) or {}
        except Exception:  # noqa: BLE001
            continue
        feature_id = contract.get("feature_id") or status_path.parent.name
        for issue in contract.get("open_issues") or []:
            if isinstance(issue, dict) and str(issue.get("status", "")).upper() != "RESOLVED":
                issues.append((str(feature_id), issue))
    return issues


def _write_progress_html(app_dir, app_id, req_status, design_status, autonomy_mode, statuses) -> None:
    template_path = _harness_dir(app_dir) / "templates" / "progress.html.tmpl"
    try:
        template = template_path.read_text(encoding="utf-8")
    except OSError:
        print(f"警告: {template_path} が見つかりません。HTML の生成をスキップします", file=sys.stderr)
        return

    done = sum(1 for s in statuses if s.get("state") in DONE_STATES)
    total = len(statuses)
    percent = int(done * 100 / total) if total else 0
    # `_enforcement_line` は Markdown 用に `**` を含むので、HTML では落とす
    enforcement = _enforcement_line(app_dir).lstrip("- ").replace("**", "")
    enforcement_class = "tag-ok" if "OK" in enforcement else "tag-bad"

    cards = [
        _card("進捗", f"{done} / {total} 機能が完了",
              f'<div class="bar"><span style="width:{percent}%"></span></div>'),
        _card("要件定義", req_status, _status_tag_html(req_status)),
        _card("設計", design_status, _status_tag_html(design_status)),
        _card("自動化モード", autonomy_mode,
              '<div class="label">要件定義の承認はモードに関わらず常に人間必須</div>'),
        _card("強制レイヤ", "", _tag(enforcement, enforcement_class)),
    ]

    rows = []
    for s in statuses:
        state = s.get("state", "?")
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(s.get('feature_id', '?')))}</code></td>"
            f"<td>{_tag(f'{STATE_LABEL.get(state, state)}', _HTML_STATE_TAG.get(state, 'tag-idle'))}</td>"
            f"<td>{_verification_tag(s)}</td>"
            f"<td>{_review_tag(s)}</td>"
            f"<td>{html.escape(', '.join(s.get('blockers') or []) or '—')}</td>"
            f"<td>{html.escape(str(s.get('last_updated_at') or '—'))}</td>"
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="6">機能はまだ登録されていません。</td></tr>')

    issues = _collect_open_issues(app_dir, statuses)
    if issues:
        items = "".join(
            f"<li><code>{html.escape(feature_id)}</code> "
            f"{html.escape(str(issue.get('id') or ''))}: "
            f"{html.escape(str(issue.get('summary') or ''))}</li>"
            for feature_id, issue in issues
        )
        issues_html = f'<ul class="plain">{items}</ul>'
    else:
        issues_html = '<p class="empty">未解決の申し送りはありません。</p>'

    try:
        version = "v" + (_harness_dir(app_dir).parent / "VERSION").read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        version = "版不明"

    output = (
        template.replace("__APP_ID__", html.escape(str(app_id)))
        .replace("__GENERATED_AT__", html.escape(_common.now_iso()))
        .replace("__VERSION__", html.escape(version))
        .replace("__SUMMARY_CARDS__", "\n".join(cards))
        .replace("__FEATURE_ROWS__", "\n".join(rows))
        .replace("__OPEN_ISSUES__", issues_html)
    )
    write_if_changed(app_dir / "PROGRESS.html", output)


def _card(label: str, value: str, extra: str = "") -> str:
    value_html = f'<div class="value">{html.escape(str(value))}</div>' if value else ""
    return f'<div class="card"><div class="label">{html.escape(label)}</div>{value_html}{extra}</div>'


def _status_tag_html(status: str) -> str:
    if status == "APPROVED":
        return _tag("承認済み", "tag-ok")
    if status in ("N/A", None, ""):
        return _tag("未着手", "tag-idle")
    return _tag("未承認", "tag-warn")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--app", help="apps/<app_id> の app_id")
    group.add_argument("--all", action="store_true", help="apps/ 配下すべてを再生成")
    parser.add_argument(
        "--html",
        action="store_true",
        help="非エンジニア向けの単一ファイル HTML（PROGRESS.html）も生成する",
    )
    args = parser.parse_args(argv[1:])

    root = _common.repo_root()
    apps_dir = root / "apps"

    if args.all:
        if not apps_dir.exists():
            print("apps/ が存在しません。何もすることがありません。")
            return 0
        for app_dir in sorted(apps_dir.iterdir()):
            if app_dir.is_dir() and not app_dir.name.startswith("."):
                render_app(app_dir, as_html=args.html)
        return 0

    app_dir = apps_dir / args.app
    if not app_dir.exists():
        print(f"エラー: {app_dir} が存在しません", file=sys.stderr)
        return 2
    render_app(app_dir, as_html=args.html)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
