"""コンテキスト予算（改善提案⑪ / ci_check 項目 L）の検証。

`CONVENTIONS.md` と agent プロンプトは、全 subagent が起動時に読む**常時コスト**そのもの。
「気をつける」では守れないので機械的に上限を課している。ここでは判定ロジックと、
**現在のリポジトリが実際に予算内に収まっていること**の両方を確認する。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import ci_check  # noqa: E402
import print_conventions  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def build(tmp_path: pathlib.Path, conventions: int, agents: dict) -> pathlib.Path:
    (tmp_path / "harness").mkdir()
    (tmp_path / "harness" / "CONVENTIONS.md").write_bytes(b"x" * conventions)
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    for name, size in agents.items():
        (tmp_path / ".claude" / "agents" / name).write_bytes(b"x" * size)
    return tmp_path


def test_within_budget_passes(tmp_path) -> None:
    root = build(tmp_path, 1000, {"a.md": 1000, "b.md": 2000})
    assert ci_check.check_context_budget(root) == []


def test_oversized_conventions_is_detected(tmp_path) -> None:
    root = build(tmp_path, ci_check.CONTEXT_BUDGET_CONVENTIONS + 1, {"a.md": 10})
    violations = ci_check.check_context_budget(root)
    assert any("CONVENTIONS.md" in v and "上限" in v for v in violations)


def test_oversized_agent_is_detected(tmp_path) -> None:
    root = build(tmp_path, 100, {"big.md": ci_check.CONTEXT_BUDGET_AGENT + 1})
    violations = ci_check.check_context_budget(root)
    assert any("big.md" in v for v in violations)


def test_session_total_is_detected(tmp_path) -> None:
    """個別には収まっていても、合計（CONVENTIONS + 最大の agent）で超えるケース。"""
    conventions = ci_check.CONTEXT_BUDGET_SESSION - ci_check.CONTEXT_BUDGET_AGENT + 1
    assert conventions <= ci_check.CONTEXT_BUDGET_CONVENTIONS
    root = build(tmp_path, conventions, {"a.md": ci_check.CONTEXT_BUDGET_AGENT})
    violations = ci_check.check_context_budget(root)
    assert any("常時読み込みの合計" in v for v in violations)


def test_session_total_uses_the_largest_agent(tmp_path) -> None:
    root = build(tmp_path, 100, {"small.md": 10, "large.md": 5000})
    root_violations = ci_check.check_context_budget(root)
    assert root_violations == []


def test_missing_files_do_not_crash(tmp_path) -> None:
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    assert ci_check.check_context_budget(tmp_path) == []


# --------------------------------------------------------------------------------------
# `<!-- context-budget: conventions-sections=... -->` マーカー（F-047 の改修）
#
# `print_conventions.py --sections` で必要な節だけを読むエージェントは、CONVENTIONS.md
# 全体ではなくマーカーに書いた節の合計だけを予算に計上する。マーカーが無いエージェントは
# 従来どおり「まるごと読む」とみなして安全側に倒す（既存テスト群が固定している）。
# --------------------------------------------------------------------------------------

SECTIONED_CONVENTIONS = """# タイトル

## 1. 一節目

""" + ("a" * 1000) + """

## 2. 二節目

""" + ("b" * 3000) + """
"""


def build_sectioned(tmp_path: pathlib.Path, agents: dict) -> pathlib.Path:
    (tmp_path / "harness").mkdir()
    (tmp_path / "harness" / "CONVENTIONS.md").write_text(SECTIONED_CONVENTIONS, encoding="utf-8")
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    for name, text in agents.items():
        (tmp_path / ".claude" / "agents" / name).write_text(text, encoding="utf-8")
    return tmp_path


def test_marker_none_attributes_zero_bytes(tmp_path) -> None:
    text = "<!-- context-budget: conventions-sections=none -->\n" + "x" * 100
    assert ci_check.attributed_conventions_bytes(text, build_sectioned(tmp_path, {})) == 0


def test_marker_with_sections_attributes_only_those_sections(tmp_path) -> None:
    root = build_sectioned(tmp_path, {})
    text = "<!-- context-budget: conventions-sections=1 -->\n"
    attributed = ci_check.attributed_conventions_bytes(text, root)
    full_section_1 = dict(
        (n, b) for n, _h, b in print_conventions.parse_sections(SECTIONED_CONVENTIONS)
    )[1]
    assert attributed == len(full_section_1.encode("utf-8"))
    assert attributed < (root / "harness" / "CONVENTIONS.md").stat().st_size


def test_marker_with_multiple_sections_sums_them(tmp_path) -> None:
    root = build_sectioned(tmp_path, {})
    only_1 = ci_check.attributed_conventions_bytes(
        "<!-- context-budget: conventions-sections=1 -->", root
    )
    only_2 = ci_check.attributed_conventions_bytes(
        "<!-- context-budget: conventions-sections=2 -->", root
    )
    both = ci_check.attributed_conventions_bytes(
        "<!-- context-budget: conventions-sections=1,2 -->", root
    )
    assert both == only_1 + only_2


def test_marker_with_unknown_section_number_contributes_nothing_for_it(tmp_path) -> None:
    root = build_sectioned(tmp_path, {})
    only_1 = ci_check.attributed_conventions_bytes(
        "<!-- context-budget: conventions-sections=1 -->", root
    )
    with_bogus = ci_check.attributed_conventions_bytes(
        "<!-- context-budget: conventions-sections=1,99 -->", root
    )
    assert with_bogus == only_1


def test_no_marker_falls_back_to_the_full_file_size(tmp_path) -> None:
    """マーカーが無いエージェントは、記述内容に関わらず全体を読むとみなす（安全側）。"""
    root = build_sectioned(tmp_path, {})
    attributed = ci_check.attributed_conventions_bytes("普通のプロンプト文", root)
    assert attributed == (root / "harness" / "CONVENTIONS.md").stat().st_size


def test_session_budget_uses_the_marker_not_the_raw_agent_size(tmp_path) -> None:
    """マーカーで 1 節だけに絞ったエージェントは、CONVENTIONS.md 全体を計上したときには
    超過するはずの予算でも、実際の読み込み量（絞った節）で判定されて通ること。"""
    small_note = "<!-- context-budget: conventions-sections=1 -->\n" + "x" * 100
    root = build_sectioned(tmp_path, {"lean.md": small_note})
    assert ci_check.check_context_budget(root) == []


def test_session_budget_still_flags_an_agent_without_a_marker_reading_a_huge_file(tmp_path) -> None:
    root = tmp_path
    (root / "harness").mkdir()
    (root / "harness" / "CONVENTIONS.md").write_bytes(b"x" * (ci_check.CONTEXT_BUDGET_SESSION))
    (root / ".claude" / "agents").mkdir(parents=True)
    (root / ".claude" / "agents" / "no-marker.md").write_text("普通のプロンプト", encoding="utf-8")
    violations = ci_check.check_context_budget(root)
    assert any("常時読み込みの合計" in v for v in violations)


# --------------------------------------------------------------------------------------
# 実リポジトリが予算内に収まっていること（このテスト自体が予算の見張り番）
# --------------------------------------------------------------------------------------

def test_this_repository_is_within_budget() -> None:
    violations = ci_check.check_context_budget(REPO_ROOT)
    assert violations == [], "\n".join(violations)


# --------------------------------------------------------------------------------------
# 項目 M: 規範と手順の二重管理の検出（F-048）
#
# 同じ規範を CONVENTIONS.md と agent プロンプトの両方に書くと、片方だけ直して drift する。
# 実際に diff-design skill が「手順どおりに実行すると Hook に拒否される」状態になっていた。
# --------------------------------------------------------------------------------------

DUP_CONVENTIONS = """# CONVENTIONS

## 12. 検証コマンド

受領書を書いた `status.yaml` を先にコミットすると HEAD が進み、`受領書の commit != HEAD` に
なって Rule 10 が `TESTED` を拒否する（実地で発生した）。Rule 8 は「応答を終える時点」で
未コミットを見るため、この手順なら衝突しない。逆に、受領書を作った直後に応答を終えようとすると
Rule 8 に止められる。この 2 つのルールは順序を守って初めて噛み合う。
"""


def build_prompts(tmp_path: pathlib.Path, conventions: str, agents: dict, skills: dict = None):
    (tmp_path / "harness").mkdir(exist_ok=True)
    (tmp_path / "harness" / "CONVENTIONS.md").write_text(conventions, encoding="utf-8")
    (tmp_path / ".claude" / "agents").mkdir(parents=True, exist_ok=True)
    for name, text in agents.items():
        (tmp_path / ".claude" / "agents" / name).write_text(text, encoding="utf-8")
    for name, text in (skills or {}).items():
        d = tmp_path / ".claude" / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(text, encoding="utf-8")
    return tmp_path


def test_near_verbatim_copy_into_an_agent_is_detected(tmp_path) -> None:
    """ほぼ転記した段落は不合格。これを許すと片方だけ直して drift する。"""
    copied = """受領書を書いた `status.yaml` を**先にコミットしてしまうと HEAD が進み**、
`受領書の commit != HEAD` になって Rule 10 が `TESTED` を拒否する。
検証をやり直す羽目になるので、受領書を作ったらコミットせずに `TESTED` へ進め、
最後に 1 回だけコミットすること。Rule 8 は「応答を終える時点」で未コミットを見るので衝突しない。
"""
    root = build_prompts(tmp_path, DUP_CONVENTIONS, {"builder.md": copied})
    violations = ci_check.check_prompt_duplication(root)
    assert len(violations) == 1
    assert "builder.md" in violations[0] and "12節" in violations[0]


def test_duplication_in_a_skill_is_detected_too(tmp_path) -> None:
    """agent だけでなく skill も対象（実際に壊れたのは diff-design skill だった）。"""
    root = build_prompts(tmp_path, DUP_CONVENTIONS, {}, {"diff-design": DUP_CONVENTIONS})
    violations = ci_check.check_prompt_duplication(root)
    assert violations and "diff-design/SKILL.md" in violations[0]


def test_citing_a_section_number_is_not_duplication(tmp_path) -> None:
    """規範を参照するだけの書き方（あるべき姿）は通る。"""
    citing = """## 進め方

1. 実装をコミットしてから `run_verification.py` を実行する。
2. 受領書ができたらコミットせずに `TESTED` へ進め、最後に 1 回だけコミットする。
   この順序が要る理由と、Rule 8 との噛み合わせは `CONVENTIONS.md` 12節を参照。
3. 完了したらユーザーに報告する。担当範囲の外には触れないこと。
"""
    root = build_prompts(tmp_path, DUP_CONVENTIONS, {"builder.md": citing})
    assert ci_check.check_prompt_duplication(root) == []


def test_short_shared_snippets_are_not_flagged(tmp_path) -> None:
    """コマンド 1 行のような短い断片は、語彙が被るだけで二重管理ではない。"""
    conventions = "# C\n\n## 6. 設計\n\n```\npython3 harness/scripts/check_interfaces.py [--app <app-id>]\n```\n"
    agent = "```\npython3 harness/scripts/print_conventions.py --sections 6\n```\n"
    root = build_prompts(tmp_path, conventions, {"a.md": agent})
    assert ci_check.check_prompt_duplication(root) == []


def test_phase_specific_specialization_is_not_flagged(tmp_path) -> None:
    """一般則をフェーズ向けに具体化した記述は、重複ではなく正当な役割分担。"""
    conventions = """# C

## 9. 自動化の度合い

- `MANUAL`: 各フェーズの節目（要件承認・設計承認・各機能の完了・統合完了）ごとに毎回人間に確認する
- `SUPERVISED`（デフォルト）: それ以降は妥当と判断すれば自動で進めるが、技術スタック選定など
  重要な決定は都度提示する
- `AUTONOMOUS`: 明らかにブロッキングな疑問がない限り、最後まで確認なしで進める
"""
    agent = """## 自動化モードに応じた振る舞い

- `MANUAL`: 設計内容が固まるたびにユーザーに提示し、承認を得てから次に進む。
- `SUPERVISED`（デフォルト）: 機能分割案や全体構成は妥当と判断すれば自分で決めて進めてよいが、
  技術スタック選定（ライブラリ・フレームワークの採用）のような重要な決定は都度ユーザーに提示する。
  `status: APPROVED` にはせず、承認用の要約を返して終わる（承認は親が書く。手順 13）。
- `AUTONOMOUS`: 明らかにブロッキングな疑問（要件が矛盾している等）がない限り、確認なしで
  設計を完成させ `status: APPROVED` まで進めてよい。
"""
    root = build_prompts(tmp_path, conventions, {"architect.md": agent})
    assert ci_check.check_prompt_duplication(root) == []


def test_missing_conventions_does_not_crash(tmp_path) -> None:
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    assert ci_check.check_prompt_duplication(tmp_path) == []


def test_this_repository_has_no_duplication() -> None:
    """実リポジトリに二重管理が無いこと（このテスト自体が見張り番）。"""
    violations = ci_check.check_prompt_duplication(REPO_ROOT)
    assert violations == [], "\n".join(violations)


# --------------------------------------------------------------------------------------
# 「起動直後に読む手順書」を常時コストに計上する（予算の空洞化防止）
#
# プロンプト本文を別ファイルへ移して「起動直後にこれを読め」と書くと、agent の**ファイル
# サイズ**は減るのに実際にセッションへ載るバイト数は変わらない（導入文のぶんむしろ増える）。
# 測定値だけが良くなって実態が悪くなる、という最悪の形なので、機械的に塞ぐ。
# --------------------------------------------------------------------------------------

def build_with_procedure(tmp_path: pathlib.Path, agent_text: str, procedure_bytes: int):
    (tmp_path / "harness" / "procedures").mkdir(parents=True)
    (tmp_path / "harness" / "CONVENTIONS.md").write_bytes(b"x" * 100)
    (tmp_path / "harness" / "procedures" / "build.md").write_bytes(b"y" * procedure_bytes)
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / ".claude" / "agents" / "builder.md").write_text(agent_text, encoding="utf-8")
    return tmp_path


DECLARED = (
    "<!-- context-budget: conventions-sections=none -->\n"
    "<!-- context-budget: always-reads=harness/procedures/build.md -->\n"
    "着手時に harness/procedures/build.md を読んでください。\n"
)
UNDECLARED = (
    "<!-- context-budget: conventions-sections=none -->\n"
    "着手時に harness/procedures/build.md を読んでください。\n"
)


def test_declared_procedure_counts_toward_the_session_total(tmp_path) -> None:
    root = build_with_procedure(tmp_path, DECLARED, 5_000)
    text = (root / ".claude" / "agents" / "builder.md").read_text(encoding="utf-8")
    assert ci_check.always_read_bytes(text, root) == 5_000


def test_moving_the_prompt_into_a_procedure_does_not_dodge_the_budget(tmp_path) -> None:
    """本文を手順書へ移しても合計は減らない（＝逃げ道にならない）ことを固定する。"""
    root = build_with_procedure(tmp_path, DECLARED, ci_check.CONTEXT_BUDGET_SESSION + 1)
    violations = ci_check.check_context_budget(root)
    assert any("常時読み込みの合計" in v for v in violations), violations


def test_undeclared_procedure_read_is_detected(tmp_path) -> None:
    """宣言せずに読ませていたら不合格。宣言漏れを許すと上の検査が空振りする。"""
    root = build_with_procedure(tmp_path, UNDECLARED, 5_000)
    violations = ci_check.check_context_budget(root)
    assert any("always-reads" in v for v in violations), violations


def test_declaring_it_makes_the_undeclared_check_pass(tmp_path) -> None:
    root = build_with_procedure(tmp_path, DECLARED, 100)
    assert ci_check.check_context_budget(root) == []


def test_agents_without_a_procedure_are_unaffected(tmp_path) -> None:
    root = build_with_procedure(tmp_path, "<!-- context-budget: conventions-sections=none -->\n", 100)
    assert ci_check.check_context_budget(root) == []
    assert ci_check.always_read_bytes("普通のプロンプト", root) == 0


def test_multiple_declarations_are_summed(tmp_path) -> None:
    root = build_with_procedure(tmp_path, DECLARED, 100)
    (root / "harness" / "procedures" / "other.md").write_bytes(b"z" * 250)
    text = (
        "<!-- context-budget: always-reads=harness/procedures/build.md,"
        "harness/procedures/other.md -->\n"
    )
    assert ci_check.always_read_bytes(text, root) == 350


def test_a_missing_declared_file_does_not_crash(tmp_path) -> None:
    root = build_with_procedure(tmp_path, DECLARED, 100)
    text = "<!-- context-budget: always-reads=harness/procedures/ghost.md -->"
    assert ci_check.always_read_bytes(text, root) == 0


def test_this_repository_declares_every_procedure_it_reads() -> None:
    """実リポジトリに宣言漏れが無いこと（このテスト自体が見張り番）。"""
    for agent_path in sorted((REPO_ROOT / ".claude" / "agents").glob("*.md")):
        text = agent_path.read_text(encoding="utf-8")
        assert ci_check.check_undeclared_procedure_reads(agent_path, text) == []


def test_the_feature_builder_total_did_not_grow_when_the_procedure_was_split_out() -> None:
    """T-001 で手順書を切り出したときの実コスト（プロンプト + 手順書）が、
    切り出し前の 11,981 バイトを下回っていること。

    切り出しは**コンテキストを減らすため**に行った。合計が減っていないなら、
    やったのは「測定を逃れること」であって「減らすこと」ではない。
    """
    agent = REPO_ROOT / ".claude" / "agents" / "feature-builder.md"
    text = agent.read_text(encoding="utf-8")
    total = agent.stat().st_size + ci_check.always_read_bytes(text, REPO_ROOT)
    assert total < 11_981, f"切り出し前より増えている: {total} バイト"
