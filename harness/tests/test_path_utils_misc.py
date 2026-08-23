"""`path_utils` のうち Bash パース・状態遷移以外のヘルパーの回帰テスト。

いずれも Hook が「書き込み前の内容」と「書き込み後の内容」を判定するために使う、
決定論レイヤーの中核部分である。
"""
from __future__ import annotations

import json

import pytest

import path_utils


# --------------------------------------------------------------------------------------
# extract_structured_edit_paths
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "tool_name,tool_input,expected",
    [
        ("Write", {"file_path": "/repo/a.py"}, ["/repo/a.py"]),
        ("Edit", {"file_path": "/repo/a.py"}, ["/repo/a.py"]),
        ("MultiEdit", {"file_path": "/repo/a.py"}, ["/repo/a.py"]),
        ("NotebookEdit", {"notebook_path": "/repo/a.ipynb"}, ["/repo/a.ipynb"]),
        ("Bash", {"command": "ls"}, []),
        ("Read", {"file_path": "/repo/a.py"}, []),
        ("Write", {}, []),
    ],
)
def test_extract_structured_edit_paths(tool_name, tool_input, expected) -> None:
    assert path_utils.extract_structured_edit_paths(tool_name, tool_input) == expected


# --------------------------------------------------------------------------------------
# simulate_write_result（PreToolUse 時点での「書き込み後の内容」の再現）
# --------------------------------------------------------------------------------------

def test_simulate_write() -> None:
    assert path_utils.simulate_write_result("Write", {"content": "new"}, "old") == "new"


def test_simulate_edit_replaces_first_occurrence_only() -> None:
    result = path_utils.simulate_write_result(
        "Edit", {"old_string": "a", "new_string": "b"}, "aaa"
    )
    assert result == "baa"


def test_simulate_edit_replace_all() -> None:
    result = path_utils.simulate_write_result(
        "Edit", {"old_string": "a", "new_string": "b", "replace_all": True}, "aaa"
    )
    assert result == "bbb"


def test_simulate_multiedit_applies_edits_in_order() -> None:
    result = path_utils.simulate_write_result(
        "MultiEdit",
        {"edits": [{"old_string": "a", "new_string": "b"}, {"old_string": "b", "new_string": "c"}]},
        "ab",
    )
    assert result == "cb"


def test_simulate_unknown_tool_keeps_content() -> None:
    assert path_utils.simulate_write_result("Bash", {}, "same") == "same"


# --------------------------------------------------------------------------------------
# extract_scalar_field
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "content,key,expected",
    [
        ("state: TESTED\n", "state", "TESTED"),
        ('state: "TESTED"\n', "state", "TESTED"),
        ("state: 'TESTED'\n", "state", "TESTED"),
        ("  state: TESTED\n", "state", "TESTED"),
        ("version: 3\n", "version", "3"),
        ("state:\n", "state", None),
        ("other: 1\n", "state", None),
    ],
)
def test_extract_scalar_field(content, key, expected) -> None:
    assert path_utils.extract_scalar_field(content, key) == expected


def test_extract_scalar_field_takes_the_first_match() -> None:
    assert path_utils.extract_scalar_field("state: A\nstate: B\n", "state") == "A"


# --------------------------------------------------------------------------------------
# read_state_field（state / status のどちらでも拾う）
# --------------------------------------------------------------------------------------

def test_read_state_field(tmp_path) -> None:
    p = tmp_path / "status.yaml"
    p.write_text("feature_id: x\nstate: IMPLEMENTED\n", encoding="utf-8")
    assert path_utils.read_state_field(p) == "IMPLEMENTED"


def test_read_state_field_accepts_status_key(tmp_path) -> None:
    p = tmp_path / "architecture.machine.yaml"
    p.write_text("app_id: x\nstatus: APPROVED\n", encoding="utf-8")
    assert path_utils.read_state_field(p) == "APPROVED"


def test_read_state_field_missing_file_is_none(tmp_path) -> None:
    assert path_utils.read_state_field(tmp_path / "nope.yaml") is None


# --------------------------------------------------------------------------------------
# extract_required_skills（Rule 5）
# --------------------------------------------------------------------------------------

def test_extract_required_skills_empty_list() -> None:
    assert path_utils.extract_required_skills("required_skills: []\nnotes: ''\n") == []


def test_extract_required_skills_parses_entries() -> None:
    content = (
        "app_id: x\n"
        "required_skills:\n"
        '- name: "frontend-design"\n'
        '  plugin_ref: "frontend-design@claude-plugins-official"\n'
        '  purpose: "UI"\n'
        '- name: "other"\n'
        '  plugin_ref: "other@mp"\n'
        'notes: ""\n'
    )
    skills = path_utils.extract_required_skills(content)
    assert [s["name"] for s in skills] == ["frontend-design", "other"]
    assert skills[0]["plugin_ref"] == "frontend-design@claude-plugins-official"


def test_extract_required_skills_stops_at_the_next_top_level_key() -> None:
    """リスト項目 `- name:` を「次のトップレベルキー」と誤検知しないこと（実地で踏んだ不具合）。"""
    content = 'required_skills:\n- name: "a"\n  plugin_ref: "a@mp"\nnotes: "x"\n'
    skills = path_utils.extract_required_skills(content)
    assert len(skills) == 1 and skills[0]["name"] == "a"


def test_extract_required_skills_parses_applies_to() -> None:
    content = (
        "required_skills:\n"
        '- name: "frontend-design"\n'
        '  plugin_ref: "frontend-design@claude-plugins-official"\n'
        '  applies_to: ["bookmark-frontend"]\n'
        '- name: "other"\n'
        '  plugin_ref: "other@mp"\n'
        "notes: \"\"\n"
    )
    skills = path_utils.extract_required_skills(content)
    assert skills[0]["applies_to"] == ["bookmark-frontend"]
    assert "applies_to" not in skills[1]  # 省略時は全機能適用（キー自体が無い）


def test_extract_required_skills_applies_to_empty_list() -> None:
    content = 'required_skills:\n- name: "a"\n  plugin_ref: "a@mp"\n  applies_to: []\n'
    skills = path_utils.extract_required_skills(content)
    assert skills[0]["applies_to"] == []


# --------------------------------------------------------------------------------------
# extract_declared_interface_test_ids / interface_coverage_gaps（Rule 11）
# --------------------------------------------------------------------------------------

ARCH_TWO_EDGES = """
interfaces:
- producer_feature: "a"
  producer_output: "out1"
  consumer_feature: "b"
  consumer_input: "in1"
- producer_feature: "b"
  producer_output: "out2"
  consumer_feature: "c"
  consumer_input: "in2"
"""


def test_extract_declared_interface_test_ids_flattens_across_entries() -> None:
    content = (
        "interface_coverage:\n"
        '- producer_feature: "a"\n'
        '  producer_output: "out1"\n'
        '  consumer_feature: "b"\n'
        '  consumer_input: "in1"\n'
        "  test_ids:\n"
        '  - "t1"\n'
        '  - "t2"\n'
        '- producer_feature: "b"\n'
        '  producer_output: "out2"\n'
        '  consumer_feature: "c"\n'
        '  consumer_input: "in2"\n'
        "  test_ids:\n"
        '  - "t3"\n'
    )
    assert path_utils.extract_declared_interface_test_ids(content) == ["t1", "t2", "t3"]


def test_interface_coverage_gaps_none_when_fully_covered() -> None:
    integration = (
        "interface_coverage:\n"
        '- producer_feature: "a"\n'
        '  producer_output: "out1"\n'
        '  consumer_feature: "b"\n'
        '  consumer_input: "in1"\n'
        "  test_ids: [\"t1\"]\n"
        '- producer_feature: "b"\n'
        '  producer_output: "out2"\n'
        '  consumer_feature: "c"\n'
        '  consumer_input: "in2"\n'
        "  test_ids: [\"t2\"]\n"
    )
    assert path_utils.interface_coverage_gaps(ARCH_TWO_EDGES, integration) == []


def test_interface_coverage_gaps_reports_missing_edge() -> None:
    integration = (
        "interface_coverage:\n"
        '- producer_feature: "a"\n'
        '  producer_output: "out1"\n'
        '  consumer_feature: "b"\n'
        '  consumer_input: "in1"\n'
        "  test_ids: [\"t1\"]\n"
    )
    gaps = path_utils.interface_coverage_gaps(ARCH_TWO_EDGES, integration)
    assert len(gaps) == 1
    assert "b.out2 -> c.in2" in gaps[0]


def test_interface_coverage_gaps_entry_without_test_ids_does_not_count() -> None:
    """test_ids が空のエントリは「カバーした」とみなさない（宣言だけして検証していない状態を防ぐ）。"""
    integration = (
        "interface_coverage:\n"
        '- producer_feature: "a"\n'
        '  producer_output: "out1"\n'
        '  consumer_feature: "b"\n'
        '  consumer_input: "in1"\n'
        "  test_ids: []\n"
    )
    gaps = path_utils.interface_coverage_gaps(
        'interfaces:\n- producer_feature: "a"\n  producer_output: "out1"\n'
        '  consumer_feature: "b"\n  consumer_input: "in1"\n',
        integration,
    )
    assert len(gaps) == 1


# --------------------------------------------------------------------------------------
# get_enabled_plugins（Rule 5）
# --------------------------------------------------------------------------------------

def test_get_enabled_plugins_merges_both_settings_files(tmp_path) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        json.dumps({"enabledPlugins": {"a@mp": True, "disabled@mp": False}}), encoding="utf-8"
    )
    (claude_dir / "settings.local.json").write_text(
        json.dumps({"enabledPlugins": ["b@mp"]}), encoding="utf-8"
    )
    assert path_utils.get_enabled_plugins(str(tmp_path)) == {"a@mp", "b@mp"}


def test_get_enabled_plugins_tolerates_missing_and_broken_files(tmp_path) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("{ broken", encoding="utf-8")
    assert path_utils.get_enabled_plugins(str(tmp_path)) == set()


# --------------------------------------------------------------------------------------
# to_worktree_relative
# --------------------------------------------------------------------------------------

def test_to_worktree_relative_absolute() -> None:
    assert path_utils.to_worktree_relative("/repo/apps/a/x.py", "/repo") == "apps/a/x.py"


def test_to_worktree_relative_keeps_relative_paths() -> None:
    assert path_utils.to_worktree_relative("apps/a/x.py", "/repo") == "apps/a/x.py"
