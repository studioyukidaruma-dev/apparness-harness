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

exit code: 0=書式が妥当（未記入の有無は問わない）, 1=書き方の誤り（YAML として読めない・スキーマ違反）,
2=実行エラー

書き方の誤りは記入者が直すものなので、どこをどう直せばよいかが分かる言葉で報告する
（字下げのずれ・文中の半角「: 」など、YAML に不慣れな人が踏みやすい原因を添える）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _common  # noqa: E402
import yaml  # noqa: E402

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
    """未記入とみなす値かどうか。

    None（コロンの後に何もない）・空文字・空白のみ・空辞書、および要素がすべて未記入のリスト
    （中身を書かずに `- ` だけ置いた箇条書きなど）を未記入とする。
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return all(is_blank(item) for item in value)
    if isinstance(value, dict):
        return len(value) == 0
    return False


YAML_HINTS = [
    "字下げ（行頭の空白）の幅が、同じ項目の中で揃っていない",
    "字下げにタブを使っている（空白を使ってください）",
    "文中に半角の「: 」（コロンと空白）がある（全角の「：」にしてください）",
    "箇条書きの「-」の後に空白が無い（「- 項目」のように空白を 1 つ入れてください）",
    "項目名の行（`goals:` など）を消した、または項目名の後のコロンを消した",
]

SCHEMA_HINTS = [
    "項目名の綴り違い（テンプレートにある項目名だけが使えます）",
    "箇条書きの項目（`goals` など）を 1 行の文章で書いた、またはその逆"
    "（各項目の上にある「書き方の例」と同じ形にしてください）",
    "数字や yes / no だけを書いた（「10 人」「不要」のように言葉を添えてください）",
]


def describe_yaml_error(error: Exception) -> str:
    """YAML の構文エラーを、記入者が直す場所の分かる一文にする。"""
    mark = getattr(error, "problem_mark", None) or getattr(error, "context_mark", None)
    where = f"{mark.line + 1} 行目付近" if mark is not None else "どこか"
    return f"{where}の書き方が読み取れません"


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
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"エラー: スキーマの読み込みに失敗しました: {e}", file=sys.stderr)
        return 2

    try:
        data = _common.load_yaml(brief_path)
    except yaml.YAMLError as e:
        message = describe_yaml_error(e)
        if args.json:
            print(json.dumps({"ok": False, "errors": [message], "hints": YAML_HINTS}, ensure_ascii=False, indent=2))
        else:
            print(f"NG: {brief_path} の{message}。", file=sys.stderr)
            print("  よくある原因:", file=sys.stderr)
            for hint in YAML_HINTS:
                print(f"    - {hint}", file=sys.stderr)
            print(f"  詳細: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"エラー: 読み込みに失敗しました: {e}", file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        print(f"NG: {brief_path} はマッピング（key: value の並び）ではありません", file=sys.stderr)
        return 1

    errors = _common.validate_against_schema(data, schema)
    if errors:
        if args.json:
            print(json.dumps({"ok": False, "errors": errors, "hints": SCHEMA_HINTS}, ensure_ascii=False, indent=2))
        else:
            print(f"NG: {brief_path} は書式を満たしていません:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            print("  よくある原因:", file=sys.stderr)
            for hint in SCHEMA_HINTS:
                print(f"    - {hint}", file=sys.stderr)
            print(
                "  雛形は `python3 harness/scripts/new_brief.py <app_id>` で作れます。",
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
