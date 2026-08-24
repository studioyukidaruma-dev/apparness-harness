#!/usr/bin/env python3
"""企画ブリーフ（`briefs/<app-id>.brief.yaml`）を検証し、未記入項目を列挙する。

ブリーフは要件定義の**入力**であって承認物ではないため、未記入があること自体は正常
（exit 0）。この CLI の役目は 2 つ:

1. 書式の検証（`harness/schemas/brief.schema.json`）。項目名の綴り間違いをここで落とす。
   誤った項目名を黙って無視すると、「書いたのに伝わらない」という最悪の失敗になる。
2. **未記入項目の列挙**。要件定義フェーズが「何を対話で聞くべきか」を機械的に決めるための
   リストを出す。埋まっている項目を聞き直さない／空欄を勝手に埋めない、の両方をこれで担保する。

使い方:
    python3 harness/scripts/check_brief.py <brief.yaml> [--json]

exit code: 0=書式が妥当（未記入の有無は問わない）, 1=スキーマ違反, 2=実行エラー
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402

SCHEMA_REL = pathlib.Path("harness/schemas/brief.schema.json")

# level の意味:
#   MUST … 要件定義に不可欠。未記入なら必ず対話で確認する
#   ASK  … 未記入なら対話で確認する（「なし」で済ませられることもある）
#   FREE … 未記入でも確認不要（書きたい人だけが書く欄）
MUST, ASK, FREE = "MUST", "ASK", "FREE"

FIELD_SPECS: list[tuple[str, str, str]] = [
    ("app_name", "アプリ名", ASK),
    ("author", "記入者（要件の承認者になる人）", ASK),
    ("purpose", "何のためのアプリか（解決したい課題）", MUST),
    ("background", "現状の運用・作る動機", ASK),
    ("target_users", "想定ユーザー（役割と利用場面）", MUST),
    ("goals", "達成したいこと", MUST),
    ("non_goals", "あえてやらないこと", ASK),
    ("must_features", "必須機能", MUST),
    ("nice_to_have", "あると嬉しい機能", ASK),
    ("tech.preferred", "使ってほしい技術", ASK),
    ("tech.forbidden", "使ってほしくない技術", ASK),
    ("tech.reasons", "技術指定の理由", FREE),
    ("tech.existing_assets", "流用したい既存資産", FREE),
    ("ui.form", "UI の形態（CLI / Web / デスクトップなど）", ASK),
    ("ui.notes", "操作・見た目の要望", ASK),
    ("ui.references", "参考にしたい既存アプリ・画面", FREE),
    ("data.handles", "扱うデータ", ASK),
    ("data.persistence", "永続化の要否", ASK),
    ("data.personal_information", "個人情報・機微情報の有無", ASK),
    ("data.volume", "想定データ量", FREE),
    ("integrations", "外部サービス連携", ASK),
    ("environment.runtime", "実行環境", ASK),
    ("environment.deployment", "どこに配置して動かすか", ASK),
    ("environment.offline", "オフライン動作の要否", FREE),
    ("environment.users_scale", "想定利用規模", ASK),
    ("non_functional_requirements", "非機能要件（性能・セキュリティなど）", ASK),
    ("constraints", "制約（期限・予算・ライセンスなど）", ASK),
    ("acceptance_overall", "全体としての完成条件", ASK),
    ("autonomy_mode", "自動化の度合い", ASK),
    ("references", "参考資料", FREE),
    ("open_points", "決めきれていないこと", FREE),
    ("notes", "その他伝えておきたいこと", FREE),
]

# リスト要素の中の欄（`must_features[0].acceptance` のように報告する）
ITEM_SPECS: dict[str, list[tuple[str, str, str]]] = {
    "must_features": [
        ("detail", "この機能の説明", ASK),
        ("acceptance", "受け入れ基準（何ができたら完成か）", MUST),
    ],
    "nice_to_have": [("detail", "この機能の説明", FREE)],
    "integrations": [
        ("purpose", "連携の目的", ASK),
        ("credentials", "認証情報を用意できるか", ASK),
    ],
}

LEVEL_ORDER = {MUST: 0, ASK: 1, FREE: 2}
LEVEL_LABEL = {
    MUST: "未記入 — 要件定義に不可欠（対話で必ず確認する）",
    ASK: "未記入 — 対話で確認する",
    FREE: "未記入 — 任意（確認は不要）",
}


def is_blank(value) -> bool:
    """未記入とみなす値かどうか。空文字・空白のみ・空リスト・空辞書・None を未記入とする。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def get_path(data: dict, dotted: str):
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def collect(data: dict) -> tuple[list[dict], list[str]]:
    """(未記入項目のリスト, 記入済み項目のパスのリスト) を返す。"""
    missing: list[dict] = []
    filled: list[str] = []

    for dotted, label, level in FIELD_SPECS:
        value = get_path(data, dotted)
        if is_blank(value):
            missing.append({"path": dotted, "label": label, "level": level})
        else:
            filled.append(dotted)

    for list_name, item_specs in ITEM_SPECS.items():
        items = get_path(data, list_name)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            for key, label, level in item_specs:
                path = f"{list_name}[{index}].{key}"
                title = str(item.get("title") or item.get("name") or "").strip()
                if is_blank(item.get(key)):
                    missing.append(
                        {
                            "path": path,
                            "label": f"{label}" + (f"（{title}）" if title else ""),
                            "level": level,
                        }
                    )
                else:
                    filled.append(path)

    missing.sort(key=lambda m: (LEVEL_ORDER[m["level"]], m["path"]))
    return missing, filled


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="企画ブリーフの書式検証と未記入項目の列挙")
    parser.add_argument("brief", help="ブリーフの YAML ファイル")
    parser.add_argument("--json", action="store_true", help="結果を JSON で出力する")
    args = parser.parse_args(argv[1:])

    brief_path = pathlib.Path(args.brief)
    if not brief_path.exists():
        print(f"エラー: {brief_path} が存在しません", file=sys.stderr)
        return 2

    schema_path = _common.resolve_harness_path(SCHEMA_REL)
    if not schema_path.exists():
        print(f"エラー: {schema_path} が存在しません", file=sys.stderr)
        return 2

    try:
        data = _common.load_yaml(brief_path)
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"エラー: 読み込みに失敗しました: {e}", file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        print(f"NG: {brief_path} はマッピング（key: value の並び）ではありません", file=sys.stderr)
        return 1

    errors = _common.validate_against_schema(data, schema)
    if errors:
        if args.json:
            print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        else:
            print(f"NG: {brief_path} は書式を満たしていません:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            print(
                "  ヒント: 項目名の綴り違いもここで落ちます。"
                f"雛形は `python3 harness/scripts/new_brief.py <app_id>` で作れます。",
                file=sys.stderr,
            )
        return 1

    missing, filled = collect(data)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "brief": str(brief_path),
                    "app_id": data.get("app_id") or "",
                    "app_name": data.get("app_name") or "",
                    "filled": filled,
                    "missing": missing,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"OK: {brief_path} は書式を満たしています")
    print(f"記入済み: {len(filled)} 項目 / 未記入: {len(missing)} 項目")
    print("")
    if filled:
        print("記入済み（対話で聞き直さないこと）:")
        for path in filled:
            print(f"  - {path}")
        print("")
    for level in (MUST, ASK, FREE):
        rows = [m for m in missing if m["level"] == level]
        if not rows:
            continue
        print(f"{LEVEL_LABEL[level]}: {len(rows)} 項目")
        for row in rows:
            print(f"  - {row['path']}: {row['label']}")
        print("")
    if not missing:
        print("未記入項目はありません。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
