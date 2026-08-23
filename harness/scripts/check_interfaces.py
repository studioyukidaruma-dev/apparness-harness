#!/usr/bin/env python3
"""`architecture.machine.yaml` の `interfaces[]` を、両端の `contract.yaml` の JSON Schema で突合する。

apparness は機能ごとに独立した worktree で**並行実装**することを前提にしている
（CONVENTIONS.md 6節）。そのため「機能 A の出力」と「機能 B の入力」の食い違いは、現状
`integrator` が merge して初めて露見する。並行作業の規模が大きいほど手戻りが増える構造であり、
**統合前に機械検出できることの価値が大きい。**

`interfaces[]` は `producer_feature`/`producer_output` → `consumer_feature`/`consumer_input` を
宣言しており、両端の実体は各 `contract.yaml` の `outputs[].json_schema` と
`inputs[].json_schema` である。JSON Schema の構造比較は**完全にスタック非依存**であり、
追加のスキーマ変更なしに今すぐ機械検証できる。

判定内容:
  1. `interfaces[]` の 4 つの端点が実在するか（機能・出力名・入力名）
  2. 型の一致（producer が出しうる型を consumer が受け付けるか）
  3. 必須項目の包含関係（producer が出さない／出すとは限らない項目を consumer が required に
     していないか）
  4. `enum` の包含関係（producer が出しうる値を consumer が受け付けるか）

使い方:
    python3 harness/scripts/check_interfaces.py [--app <app-id>]

exit code: 0 = 問題なし, 1 = 不整合あり, 2 = 実行エラー
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402

# 比較を行わない（＝どんな値でも受け付ける）とみなすスキーマ
_ANY_SCHEMA = ({}, True, None)


def _types_of(schema: dict) -> set[str] | None:
    t = schema.get("type")
    if t is None:
        return None
    return set(t) if isinstance(t, list) else {t}


def compare_schemas(producer: dict, consumer: dict, path: str = "") -> list[str]:
    """producer が出す値を consumer が受け付けられるかを比較し、問題の一覧を返す。

    「producer の値域 ⊆ consumer の受入範囲」であることを確認する（共変な向き）。
    どちらかが制約を書いていない箇所は判定不能として何も言わない
    （過検出でハーネスが信用されなくなるほうが害が大きいため）。
    """
    where = f"（{path}）" if path else ""
    if not isinstance(producer, dict) or not isinstance(consumer, dict):
        return []
    if producer in _ANY_SCHEMA or consumer in _ANY_SCHEMA:
        return []

    issues: list[str] = []

    p_types, c_types = _types_of(producer), _types_of(consumer)
    if p_types and c_types and not p_types <= c_types:
        issues.append(
            f"型が一致しません{where}: producer は {sorted(p_types)} を出しうるが、"
            f"consumer は {sorted(c_types)} しか受け付けない"
        )

    p_enum, c_enum = producer.get("enum"), consumer.get("enum")
    if isinstance(p_enum, list) and isinstance(c_enum, list):
        extra = [v for v in p_enum if v not in c_enum]
        if extra:
            issues.append(
                f"enum の包含関係が成り立ちません{where}: producer が出しうる {extra} を "
                f"consumer が受け付けない（consumer の enum: {c_enum}）"
            )

    p_props = producer.get("properties") if isinstance(producer.get("properties"), dict) else {}
    c_props = consumer.get("properties") if isinstance(consumer.get("properties"), dict) else {}
    p_required = producer.get("required") if isinstance(producer.get("required"), list) else None
    c_required = consumer.get("required") if isinstance(consumer.get("required"), list) else []

    if p_props or c_props:
        for name in c_required:
            child = f"{path}.{name}" if path else name
            if p_props and name not in p_props:
                issues.append(
                    f"必須項目の包含関係が成り立ちません（{child}）: consumer が required に"
                    f"していますが、producer の出力に存在しません"
                )
            elif p_required is not None and name not in p_required:
                issues.append(
                    f"必須項目の包含関係が成り立ちません（{child}）: consumer が required に"
                    f"していますが、producer 側では必須ではない（出力されない場合がある）"
                )
        for name, c_child in c_props.items():
            if name in p_props:
                issues += compare_schemas(p_props[name], c_child, f"{path}.{name}" if path else name)

    p_items, c_items = producer.get("items"), consumer.get("items")
    if isinstance(p_items, dict) and isinstance(c_items, dict):
        issues += compare_schemas(p_items, c_items, f"{path}[]" if path else "[]")

    return issues


def _named(entries, name: str) -> dict | None:
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == name:
            return entry
    return None


def check_interfaces(architecture: dict, contracts: dict) -> list[str]:
    """`interfaces[]` 全体を検証する。`contracts` は feature_id → contract の dict。"""
    if not isinstance(architecture, dict):
        return []
    feature_ids = {
        f.get("id") for f in architecture.get("features") or [] if isinstance(f, dict)
    }
    violations: list[str] = []
    for index, iface in enumerate(architecture.get("interfaces") or []):
        if not isinstance(iface, dict):
            continue
        pf, po = iface.get("producer_feature"), iface.get("producer_output")
        cf, ci = iface.get("consumer_feature"), iface.get("consumer_input")
        label = f"interfaces[{index}] {pf}.{po} -> {cf}.{ci}"

        missing_endpoint = False
        for role, fid in (("producer_feature", pf), ("consumer_feature", cf)):
            if fid not in feature_ids:
                violations.append(f"{label}: {role}={fid!r} が features[] に存在しません")
                missing_endpoint = True
            elif fid not in contracts:
                violations.append(f"{label}: {fid!r} の contract.yaml が見つかりません")
                missing_endpoint = True
        if missing_endpoint:
            continue

        output = _named(contracts[pf].get("outputs"), po)
        input_ = _named(contracts[cf].get("inputs"), ci)
        if output is None:
            violations.append(f"{label}: {pf!r} の outputs[] に {po!r} がありません")
        if input_ is None:
            violations.append(f"{label}: {cf!r} の inputs[] に {ci!r} がありません")
        if output is None or input_ is None:
            continue

        for issue in compare_schemas(output.get("json_schema") or {}, input_.get("json_schema") or {}):
            violations.append(f"{label}: {issue}")
    return violations


def load_contracts(root: pathlib.Path, app_id: str) -> dict:
    """機能ごとの契約を読む。実装中の `03-features/` を優先し、無ければ設計時のドラフトを使う。"""
    contracts: dict = {}
    design_dir = root / "apps" / app_id / "02-design" / "features"
    if design_dir.is_dir():
        for path in sorted(design_dir.glob("*.contract.yaml")):
            try:
                contracts[path.name[: -len(".contract.yaml")]] = _common.load_yaml(path) or {}
            except Exception:  # noqa: BLE001
                continue
    for path in sorted((root / "apps" / app_id / "03-features").glob("*/contract.yaml")):
        try:
            contracts[path.parent.name] = _common.load_yaml(path) or {}
        except Exception:  # noqa: BLE001
            continue
    return contracts


def check_app(root: pathlib.Path, app_id: str) -> list[str]:
    arch_path = root / "apps" / app_id / "02-design" / "architecture.machine.yaml"
    if not arch_path.exists():
        return []
    try:
        architecture = _common.load_yaml(arch_path) or {}
    except Exception as e:  # noqa: BLE001
        return [f"apps/{app_id}/02-design/architecture.machine.yaml: 読み込みに失敗しました: {e}"]
    return [
        f"apps/{app_id}: {v}" for v in check_interfaces(architecture, load_contracts(root, app_id))
    ]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", help="app-id（省略時は apps/ 配下の全アプリ）")
    args = parser.parse_args(argv[1:])

    root = _common.repo_root()
    apps_dir = root / "apps"
    if not apps_dir.exists():
        print("apps/ がまだ存在しません。チェックをスキップします")
        return 0
    app_ids = [args.app] if args.app else [d.name for d in sorted(apps_dir.iterdir()) if d.is_dir()]

    violations: list[str] = []
    for app_id in app_ids:
        violations += check_app(root, app_id)

    if violations:
        print(f"NG: {len(violations)} 件の不整合が見つかりました:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("OK: interfaces[] の両端の契約は整合しています")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
