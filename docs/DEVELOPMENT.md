# apparness ハーネス 開発・保守手順（保守者向け）

> **人間向けの文書です（ハーネスを保守する人向け）。** AI はこの文書を読みません（Rule 13）。
> 配布元リポジトリにだけあり、インストーラで導入先へはコピーされません。

ハーネス自身を改修・リリースする人のための手順書です。設計意図と既知の制約は [DESIGN.md](DESIGN.md) にあります。

## 目次

1. [開発環境](#1-開発環境)
2. [改修の流れ](#2-改修の流れ)
3. [リリース](#3-リリース)
4. [文書の役割分担](#4-文書の役割分担)
5. [ハーネス自身のテスト](#5-ハーネス自身のテスト)
6. [トラブルシューティング（保守時）](#6-トラブルシューティング保守時)

---

## 1. 開発環境

```
pip install -r harness/requirements-dev.txt
```

`harness/scripts/**` が PyYAML と jsonschema を、テストが pytest を使います。`pip` が使えない環境では:

```
uv run --with-requirements harness/requirements-dev.txt python3 -m pytest harness/tests -q
```

動作確認:

```
python3 -m pytest harness/tests -q
python3 harness/scripts/ci_check.py --branch "$(git branch --show-current)"
python3 harness/hooks/session_start_healthcheck.py < /dev/null
```

すべて緑（`passed` / `OK: すべてのチェックを通過しました` / 無出力で exit 0）なら成功です。
3 つ目は**強制レイヤ自身が健全か**の自己診断です。

エディタに「インポート "path_utils" を解決できませんでした」と出る場合は、エディタを再読み込み
してください。`harness/hooks/**` は実行時に `sys.path` を操作して `path_utils` を読むため静的解析が
追えず、`pyrightconfig.json` の `extraPaths` で解決しています。実行時の挙動には影響しません。

---

## 2. 改修の流れ

```
git switch -c harness/<topic>
```

1. **`harness/` で始まるブランチで作業します。** それ以外のブランチでは `harness/`・`.claude/`・`.github/`
   に書き込めず（Rule 1）、人間向け文書（`docs/`・`harness/docs/`）も読めません（Rule 13）。
2. 判定ロジックを変えるときは、先にテストを書いて緑にしてから進めます。
3. 規則を足したら `harness/CLAIMS.md` に「何を止めるか」と実証テストを追加します（CI 項目 P）。
4. `harness/CHANGELOG.md` の `## [Unreleased]` に変更を追記します（CI 項目 Q）。
5. テスト・CI チェック・自己診断を緑にしてから main へ fast-forward マージします。
6. 導入先への影響がある変更は、一時プロジェクトへ `harness/scripts/install.py` で導入して、
   導入先でもテスト・CI チェック・自己診断が通ることを確かめます。

---

## 3. リリース

main は常に配布できる状態に保ちます。利用者はタグから導入するので、リリースごとにタグを打ちます。

1. `harness/CHANGELOG.md` の `## [Unreleased]` の中身を `## [<版>] - <日付>` の節へ移します。
2. `harness/VERSION` を同じ版にします。版の上げ方は `harness/CHANGELOG.md` の冒頭の定義に従います
   （MAJOR: 既存アプリの作り直しが要る／MINOR: Rule・CI 項目・skill・agent の追加／PATCH: 強制の範囲を変えない修正）。
3. main へマージし、`git tag -a v<版> -m "apparness harness v<版>"` を打って、main とタグを push します。
4. ルートの `README.md` の導入コマンドにあるタグを新しい版にします。

---

## 4. 文書の役割分担

**同じことを 2 箇所に書かない**のが一貫した方針です（片方だけ直して食い違うため。CI 項目 M が検出）。
**AI が読む文書と人間が読む文書を混ぜない**ことも同じくらい重要です（背景は [DESIGN.md](DESIGN.md) 10節）。

| 書きたいこと | 置き場所 | 読む人 | 注意 |
| --- | --- | --- | --- |
| 機械が強制する規範 | `harness/CONVENTIONS.md` | AI | **15 節で凍結。** 新しい節は CI 項目 O が拒否。既存節へ追記する |
| フェーズ固有の手順 | agent/skill プロンプト、`harness/procedures/*.md` | AI | `procedures/` に置いたら `always-reads` の宣言が必須（CI 項目 L） |
| 品質の下限 | `harness/quality/*.md` | AI | 外部依存ゼロで常に効くこと |
| 技術ごとの流儀 | 外部スタックパック（形式は `harness/STACK_PACK.md`） | AI | **ハーネス本体には書かない** |
| 機械可読ファイルの形式 | `harness/schemas/*.schema.json` | 機械 | CI 項目 A が検証 |
| スクリプトの使い方 | 各スクリプトの `--help`（argparse） | AI・人間 | 引数の説明をほかの文書に複製しない |
| しくみの説明・使い方（利用者向け） | `harness/docs/` | アプリを作る人 | AI は読まない（Rule 13・CI 項目 R）。導入先にもコピーされる |
| 設計意図・背景・既知の制約 | `docs/DESIGN.md` | 保守者 | 制約は 4 点セット（症状／根本原因／緩和策／**再検討の条件**） |
| 改修の手順 | `docs/DEVELOPMENT.md`（この文書） | 保守者 | |
| 改修計画・実地で困ったこと | `docs/plans/`・`docs/maintenance/` | 保守者 | 深刻度 高・最高 の摩擦点は**再発防止テストなしでクローズ禁止** |
| 「これを止める」主張と証拠 | `harness/CLAIMS.md` | 保守者 | 規則を足したら必ず行を追加（CI 項目 P） |
| ハーネスの変更履歴 | `harness/CHANGELOG.md` / `harness/VERSION` | 利用者・保守者 | ハーネス本体を触ったら追記必須（CI 項目 Q） |
| 概要と導入方法 | `README.md` | 最初に見る人 | 大まかな説明だけ。詳細は `harness/docs/` に譲る |

迷ったら 4 つの質問で決まります。
**① 破ったら機械が止めるか** → `CONVENTIONS.md`　
**② AI が作業中に要るか** → agent/skill か `procedures/`（説明ではなく手順として書く）　
**③ 利用者が使い方を知るための説明か** → `harness/docs/`　
**④ 「なぜ」や経緯の話か** → `docs/DESIGN.md`

---

## 5. ハーネス自身のテスト

`ci_check.py` が検証するのは「ハーネスが**アプリに対して**課すルール」です。
「ハーネス自身の判定ロジックが正しいか」は `harness/tests/` の pytest が見ます
（`.github/workflows/harness-checks.yml` の `harness-selftest` ジョブ）。

主なテストファイル:

| ファイル | 対象 |
|---|---|
| `test_path_utils_bash.py` | Bash パース（`_classify_bash_lines`/`_normalize_bash_newlines`/`extract_bash_candidate_paths`）の実地シナリオ |
| `test_status_transition.py` | `validate_status_transition`。状態機械を**テスト側で独立に再実装**し、全状態の直積で突き合わせる |
| `test_pre_tool_use_guard.py` | Hook をサブプロセスとして起動する end-to-end 検証 |
| `test_post_tool_use_guard.py` | Bash の事後検証（検出・巻き戻し、実行前から dirty なパスを巻き戻さないこと） |
| `test_dangerous_ops.py` | Rule 12（危険操作フロア） |
| `test_human_docs.py` | Rule 13（人間向け文書の読み取り拒否）と CI 項目 R |
| `test_verification.py` / `test_integration_verification.py` | 検証受領書・統合受領書 |
| `test_interface_check.py` / `test_traceability.py` | `interfaces[]` の突合・要件トレーサビリティ |
| `test_context_budget.py` | コンテキスト予算と、**このリポジトリ自身が予算内に収まっていること** |
| `test_claims.py` | `CLAIMS.md` と Rule・CI 項目・テストの対応 |
| `test_versioning.py` | CI 項目 Q（版と変更履歴） |
| `test_install.py` | コピー型インストーラ |
| `test_schema_draft.py` | 要件・設計のスキーマ（DRAFT の空欄と承認後の必須項目） |

`test_install.py::test_the_real_repository_can_be_installed` は配布元でだけ実行され、導入先ではスキップされます。

---

## 6. トラブルシューティング（保守時）

### CONVENTIONS.md: 凍結中のため節の新設はできません

15 節で凍結されています（CI 項目 O）。既存の節の中に統合してください。規約の変更そのものにも
ユーザーの明示的な許可が必要です。

### harness/CHANGELOG.md: ハーネス本体に ... 変更がありますが、CHANGELOG.md が更新されていません

CI 項目 Q です。`harness/CHANGELOG.md` の `## [Unreleased]` に何を変えたかを箇条書きで追記してください。
リリースの場合は `harness/VERSION` を上げ、`## [<版>]` の節に移せば通ります。

### harness/CLAIMS.md: ... に ... が存在しません

CI 項目 P です。`CLAIMS.md` に書いたテスト名が `harness/tests/` に実在しません。
テストを書くか、表の記載を実体に合わせてください。

### 常時読み込みの合計が上限を超えています

CI 項目 L です。まず**説明・背景・設計意図を `docs/DESIGN.md` へ移して**ください。
手順を `harness/procedures/*.md` へ移す場合は `always-reads` の宣言が必要です。

### AI が読む文書から人間向け文書を参照しています

CI 項目 R です。agent・skill・手順書・`CONVENTIONS.md` などに `docs/` や `harness/docs/` への参照があります。
AI に要る内容なら規約・手順書・実行物へ移し、説明なら参照ごと削ってください。人間向け文書の扱いを
定める規範の行だけは、同じ行に「人間向け」と書けば許可されます。

### No module named pytest

開発用依存が入っていません。1節の手順で入れてください。
