"""`run_integration_verification.py` の end-to-end 経路（宣言→実行→受領書→ゲート）の検証。

Rule 10（`run_verification.py`）と同じ「宣言を実行して受領書に記録し、機械的にゲートする」
仕組みを `04-integration/` に適用したもの（Rule 11）。実際にサブプロセスを起動し、生成された
JUnit XML から `interface_coverage[]` のトレーサビリティまで一気通貫で検証する。
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import _common  # noqa: E402
import run_integration_verification as riv  # noqa: E402

JUNIT_OK = (
    '<testsuite name="assembly" tests="1" failures="0" errors="0" skipped="0">'
    '<testcase classname="assembly" name="wiring_a_to_b"/></testsuite>'
)
JUNIT_FAILING = (
    '<testsuite name="assembly" tests="1" failures="1" errors="0" skipped="0">'
    '<testcase classname="assembly" name="wiring_a_to_b"><failure message="boom"/></testcase>'
    '</testsuite>'
)

ARCH = (
    'app_id: "demo"\n'
    "interfaces:\n"
    '- producer_feature: "a"\n'
    '  producer_output: "out1"\n'
    '  consumer_feature: "b"\n'
    '  consumer_input: "in1"\n'
)


def integration_yaml(test_ids: str = '  - "wiring_a_to_b"\n') -> str:
    return (
        'app_id: "demo"\n'
        "interface_coverage:\n"
        '- producer_feature: "a"\n'
        '  producer_output: "out1"\n'
        '  consumer_feature: "b"\n'
        '  consumer_input: "in1"\n'
        "  test_ids:\n"
        f"{test_ids}"
        "verification:\n"
        '  working_dir: "assembly"\n'
        f'  test_command: "{sys.executable} run_tests.py"\n'
        '  junit_xml: ".verify/junit.xml"\n'
    )


def _init_repo(root: pathlib.Path) -> None:
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "tester"],
    ):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _commit_all(root: pathlib.Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True, capture_output=True)


def _build_app(root: pathlib.Path, integration_content: str, junit_xml: str) -> None:
    app = root / "apps" / "demo"
    (app / "04-integration" / "assembly").mkdir(parents=True)
    (app / "02-design").mkdir(parents=True)
    (app / "02-design" / "architecture.machine.yaml").write_text(ARCH, encoding="utf-8")
    (app / "04-integration" / "integration.machine.yaml").write_text(integration_content, encoding="utf-8")
    script = app / "04-integration" / "assembly" / "run_tests.py"
    script.write_text(
        "import pathlib\n"
        "pathlib.Path('.verify').mkdir(exist_ok=True)\n"
        f"pathlib.Path('.verify/junit.xml').write_text({junit_xml!r})\n",
        encoding="utf-8",
    )


def test_end_to_end_writes_a_passing_receipt_and_gates_open(tmp_path, monkeypatch, capsys) -> None:
    _init_repo(tmp_path)
    _build_app(tmp_path, integration_yaml(), JUNIT_OK)
    _commit_all(tmp_path)
    monkeypatch.setattr(_common, "repo_root", lambda: tmp_path)

    exit_code = riv.main(["run_integration_verification.py", "--app", "demo"])
    assert exit_code == 0, capsys.readouterr().err

    data = _common.load_yaml(tmp_path / "apps/demo/04-integration/integration.machine.yaml")
    receipt = data["verification_receipt"]
    assert receipt["test"]["exit_code"] == 0
    assert receipt["test"]["tests"] == 1
    assert receipt["traceability"] == {"declared": 1, "matched": 1}


def test_end_to_end_rejects_a_failing_test(tmp_path, monkeypatch, capsys) -> None:
    _init_repo(tmp_path)
    _build_app(tmp_path, integration_yaml(), JUNIT_FAILING)
    _commit_all(tmp_path)
    monkeypatch.setattr(_common, "repo_root", lambda: tmp_path)

    exit_code = riv.main(["run_integration_verification.py", "--app", "demo"])
    assert exit_code == 1
    assert "失敗しているテスト" in capsys.readouterr().err


def test_end_to_end_rejects_an_uncovered_interface_edge(tmp_path, monkeypatch, capsys) -> None:
    """宣言された test_ids は実在して成功しているが、architecture.machine.yaml のもう1本の
    エッジ（今回は存在しないので producer/consumer を変えて再現する）がカバーされていない場合。
    """
    _init_repo(tmp_path)
    integration_content = (
        'app_id: "demo"\n'
        "interface_coverage:\n"
        '- producer_feature: "x"\n'
        '  producer_output: "other"\n'
        '  consumer_feature: "y"\n'
        '  consumer_input: "other"\n'
        "  test_ids:\n"
        '  - "wiring_a_to_b"\n'
        "verification:\n"
        '  working_dir: "assembly"\n'
        f'  test_command: "{sys.executable} run_tests.py"\n'
        '  junit_xml: ".verify/junit.xml"\n'
    )
    _build_app(tmp_path, integration_content, JUNIT_OK)
    _commit_all(tmp_path)
    monkeypatch.setattr(_common, "repo_root", lambda: tmp_path)

    exit_code = riv.main(["run_integration_verification.py", "--app", "demo"])
    assert exit_code == 1
    assert "a.out1 -> b.in1" in capsys.readouterr().err


def test_missing_test_command_is_a_setup_error(tmp_path, monkeypatch, capsys) -> None:
    app = tmp_path / "apps" / "demo"
    (app / "04-integration").mkdir(parents=True)
    (app / "04-integration" / "integration.machine.yaml").write_text(
        'app_id: "demo"\ninterface_coverage: []\nverification: {}\n', encoding="utf-8"
    )
    monkeypatch.setattr(_common, "repo_root", lambda: tmp_path)

    exit_code = riv.main(["run_integration_verification.py", "--app", "demo"])
    assert exit_code == 2
    assert "test_command" in capsys.readouterr().err
