"""脆弱性走査の抑制機構（R-020 / F-R3）の検証。

抑制が無いと、上流に fix が出ていない脆弱性を 1 件踏んだだけでそのアプリは CI を通せなくなる。
逃げ道が無い検査は最終的に無視される運用に倒れ、形骸化する。かといって「とりあえず無視」を
恒久化できる形にすると、それはそれで検査が意味を失う。だから**期限と理由を必須**にし、
欠落・期限切れは走査結果に関わらず不合格にする。ここではその両側を固定する。
"""
from __future__ import annotations

import datetime
import pathlib

import vuln_scan

# 固定日付にすると、その日を過ぎた瞬間にテストが壊れる（`main()` は実行日を見る）。
# 実行日からの相対で作り、時間経過で意味が変わらないようにする。
TODAY = datetime.date.today()
FUTURE = (TODAY + datetime.timedelta(days=365)).isoformat()
PAST = (TODAY - datetime.timedelta(days=1)).isoformat()


def build(tmp_path: pathlib.Path, ignore_text: str | None = None, app_id: str = "demo") -> pathlib.Path:
    """`apps/<app_id>/` を持つ一時リポジトリ。`ignore_text` があれば `.vuln-ignore` を置く。"""
    app_dir = tmp_path / "apps" / app_id
    app_dir.mkdir(parents=True)
    if ignore_text is not None:
        (app_dir / vuln_scan.IGNORE_FILENAME).write_text(ignore_text, encoding="utf-8")
    return tmp_path


def scan_result(root: pathlib.Path, vuln_id: str = "GHSA-aaaa-bbbb-cccc", app_id: str = "demo") -> dict:
    """OSV-Scanner の出力を模した最小の JSON。"""
    return {
        "results": [
            {
                "source": {"path": str(root / "apps" / app_id / "package-lock.json")},
                "packages": [
                    {
                        "package": {"name": "left-pad", "version": "1.0.0", "ecosystem": "npm"},
                        "groups": [{"ids": [vuln_id], "max_severity": "7.5"}],
                    }
                ],
            }
        ]
    }


def run_main(monkeypatch, root: pathlib.Path, data: dict | None = None, argv: list[str] | None = None) -> int:
    """`osv-scanner` バイナリ無しで main() を通す（走査結果は差し替える）。"""
    monkeypatch.setattr(vuln_scan._common, "repo_root", lambda: root)
    if data is None:
        monkeypatch.setattr(vuln_scan, "find_binary", lambda: None)
    else:
        monkeypatch.setattr(vuln_scan, "find_binary", lambda: "/usr/bin/osv-scanner")
        monkeypatch.setattr(vuln_scan, "run_scan", lambda binary, target: (1, data, ""))
    return vuln_scan.main(argv or ["vuln_scan.py"])


# --------------------------------------------------------------------------------------
# 抑制ファイルの検証（適用より先に走る）
# --------------------------------------------------------------------------------------

def test_a_line_without_expires_is_rejected_with_its_line_number(tmp_path, monkeypatch, capsys) -> None:
    root = build(tmp_path, "# 先頭はコメント\n\nGHSA-aaaa-bbbb-cccc  reason=上流に fix 未提供\n")
    assert run_main(monkeypatch, root) == 1
    err = capsys.readouterr().err
    assert "expires" in err
    assert ":3" in err, err  # 行番号（コメント・空行を飛ばして 3 行目）


def test_a_line_without_reason_is_rejected(tmp_path, monkeypatch, capsys) -> None:
    root = build(tmp_path, f"GHSA-aaaa-bbbb-cccc  expires={FUTURE}\n")
    assert run_main(monkeypatch, root) == 1
    assert "reason" in capsys.readouterr().err


def test_an_expired_line_is_rejected(tmp_path, monkeypatch, capsys) -> None:
    """期限切れの抑制が黙って効き続けると、抑制機構が「無視するための穴」に退化する。"""
    root = build(tmp_path, f"GHSA-aaaa-bbbb-cccc  expires={PAST}  reason=上流に fix 未提供\n")
    assert run_main(monkeypatch, root) == 1
    assert "期限が切れています" in capsys.readouterr().err


def test_a_malformed_date_is_rejected(tmp_path) -> None:
    root = build(tmp_path, "GHSA-aaaa-bbbb-cccc  expires=2026/12/31  reason=x\n")
    rules, errors = vuln_scan.load_ignore_rules(root / "apps", None, root, TODAY)
    assert rules == []
    assert any("書式が不正" in e for e in errors), errors


def test_a_nonexistent_date_is_rejected(tmp_path) -> None:
    root = build(tmp_path, "GHSA-aaaa-bbbb-cccc  expires=2026-02-30  reason=x\n")
    rules, errors = vuln_scan.load_ignore_rules(root / "apps", None, root, TODAY)
    assert rules == []
    assert any("実在しない日付" in e for e in errors), errors


def test_the_ignore_file_is_validated_before_the_scan_runs(tmp_path, monkeypatch, capsys) -> None:
    """検出が 0 件でも、抑制ファイルの不備だけで不合格になること（走査結果に関わらず）。"""
    root = build(tmp_path, "GHSA-aaaa-bbbb-cccc  reason=期限なし\n")
    assert run_main(monkeypatch, root, data={"results": []}) == 1
    assert "expires" in capsys.readouterr().err


def test_a_reason_may_contain_a_url_with_a_hash(tmp_path) -> None:
    """`reason` に URL（`#` を含む）が入るため、行内コメントには対応しない。"""
    root = build(
        tmp_path,
        f"GHSA-aaaa-bbbb-cccc  expires={FUTURE}  reason=追跡: https://example.com/issues/1#c2\n",
    )
    rules, errors = vuln_scan.load_ignore_rules(root / "apps", None, root, TODAY)
    assert errors == []
    assert rules[0].reason.endswith("#c2")


def test_comments_and_blank_lines_are_ignored(tmp_path) -> None:
    root = build(tmp_path, f"# コメント\n\n   \nGHSA-aaaa-bbbb-cccc  expires={FUTURE}  reason=x\n")
    rules, errors = vuln_scan.load_ignore_rules(root / "apps", None, root, TODAY)
    assert errors == []
    assert len(rules) == 1


# --------------------------------------------------------------------------------------
# 抑制の適用
# --------------------------------------------------------------------------------------

def test_a_valid_suppression_excludes_the_finding_and_says_so(tmp_path, monkeypatch, capsys) -> None:
    root = build(tmp_path, f"GHSA-aaaa-bbbb-cccc  expires={FUTURE}  reason=上流に fix 未提供\n")
    assert run_main(monkeypatch, root, data=scan_result(root)) == 0
    out = capsys.readouterr().out
    assert "抑制中の検出が 1 件" in out
    assert "GHSA-aaaa-bbbb-cccc" in out and FUTURE in out  # 黙って消さない


def test_a_suppression_does_not_cover_a_different_id(tmp_path, monkeypatch) -> None:
    root = build(tmp_path, f"GHSA-aaaa-bbbb-cccc  expires={FUTURE}  reason=x\n")
    assert run_main(monkeypatch, root, data=scan_result(root, vuln_id="CVE-2026-0001")) == 1


def test_a_suppression_does_not_leak_into_another_app(tmp_path, monkeypatch) -> None:
    """抑制はアプリ側の受容判断なので、別アプリの検出まで消してはならない。"""
    root = build(tmp_path, f"GHSA-aaaa-bbbb-cccc  expires={FUTURE}  reason=x\n", app_id="demo")
    (root / "apps" / "other").mkdir(parents=True)
    assert run_main(monkeypatch, root, data=scan_result(root, app_id="other")) == 1


def test_an_alias_also_matches(tmp_path) -> None:
    """OSV の group は `ids` か `aliases` のどちらかで ID を持つ。どちらでも一致すること。"""
    root = build(tmp_path)
    rules = [
        vuln_scan.IgnoreRule(
            "CVE-2026-0001", TODAY + datetime.timedelta(days=365), "x", "origin",
            (root / "apps" / "demo").resolve(),
        )
    ]
    data = {
        "results": [
            {
                "source": {"path": str(root / "apps" / "demo" / "package-lock.json")},
                "packages": [
                    {
                        "package": {"name": "left-pad", "version": "1.0.0", "ecosystem": "npm"},
                        "groups": [{"aliases": ["CVE-2026-0001"], "max_severity": "7.5"}],
                    }
                ],
            }
        ]
    }
    violations, suppressed = vuln_scan.summarize(data, root, rules)
    assert violations == [] and len(suppressed) == 1


# --------------------------------------------------------------------------------------
# 後方互換
# --------------------------------------------------------------------------------------

def test_behaviour_is_unchanged_when_no_ignore_file_exists(tmp_path, monkeypatch, capsys) -> None:
    root = build(tmp_path)  # `.vuln-ignore` なし
    assert run_main(monkeypatch, root, data=scan_result(root)) == 1
    captured = capsys.readouterr()
    assert "1 件の既知の脆弱性" in captured.err
    assert "抑制" not in captured.out


def test_summarize_without_rules_reports_everything(tmp_path) -> None:
    root = build(tmp_path)
    violations, suppressed = vuln_scan.summarize(scan_result(root), root)
    assert len(violations) == 1 and suppressed == []


def test_a_clean_scan_still_passes(tmp_path, monkeypatch, capsys) -> None:
    root = build(tmp_path, f"GHSA-aaaa-bbbb-cccc  expires={FUTURE}  reason=x\n")
    assert run_main(monkeypatch, root, data={"results": []}) == 0
    assert "OK" in capsys.readouterr().out
