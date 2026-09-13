# docs/ — ハーネスを保守する人のための文書（索引）

> **人間向けの文書です（ハーネスを保守する人向け）。** AI はこの配下を読みません（Rule 13）。
> 配布元リポジトリにだけあり、インストーラで導入先へはコピーされません。

アプリを作る人向けの説明（しくみ・使い方）は `../harness/docs/` にあります。ここには、
ハーネス自身を直す・リリースする・経緯をたどるための文書だけを置きます。

## 目的別の入口

| 知りたいこと | 読むもの |
|---|---|
| **ハーネスをどう改修・リリースするか**、文書をどこに書くか | [DEVELOPMENT.md](DEVELOPMENT.md) |
| **なぜこの設計なのか**（設計意図・経緯・既知の制約と再検討条件） | [DESIGN.md](DESIGN.md) |
| **どう判定しているのか**（監査・実装者向け。実測値と再検証手順つき） | [flow/harness-flow-technical.html](flow/harness-flow-technical.html) |
| **これから何を直すのか** | [plans/](plans/) |
| **実地で何が壊れたのか**、それをどうテストに変えるか | [maintenance/](maintenance/) |
| **なぜ今の形に落ち着いたのか**（役目を終えた調査） | [archive/](archive/) |

規約そのもの（機械が強制する規範）は `../harness/CONVENTIONS.md`、変更履歴は `../harness/CHANGELOG.md` です。

## 中身

### `DESIGN.md` / `DEVELOPMENT.md`

`CONVENTIONS.md` は規範だけを持ち、「なぜ」は `DESIGN.md` に寄せます。`ci_check.py` の項目 L が
「上限に当たったら説明・背景・設計意図を移せ」と案内する先も `DESIGN.md` です。
`DEVELOPMENT.md` は開発環境・改修の流れ・リリース・文書の役割分担をまとめた手順書です。

### `flow/harness-flow-technical.html`

Hook の exit code 契約、Rule の判定仕様、CI 項目、実測値と再検証手順を書いた監査・保守者向けの説明書です。
ブラウザで直接開けます。作成時点のスナップショットなので、数値は末尾の再検証手順で確かめてください。
非エンジニア向けのやさしい版は、利用者向けとして `../harness/docs/flow/harness-flow-plain.html` にあります。

### `plans/` — 改修計画と改修指示書

| ファイル | 何か |
|---|---|
| `IMPROVEMENT-PLAN.machine.yaml` | 別ハーネスとの比較から導いた改修計画。`tasks[]` に `status` 付き |
| `IMPROVEMENT-PLAN.md` | 上の人間向けの双子 |
| `REPAIR-ORDER.machine.yaml` | 実際に動かして見つかった残存欠陥の改修指示書 |
| `REPAIR-ORDER.md` | 上の人間向けの双子 |

`.machine.yaml` は、保守者が「このファイルを読んで改修してください」と指示したときに実行計画として
読ませる書式です。読ませるときは `harness/<topic>` ブランチで作業してください（Rule 13）。
2 つは併存し、`invariants[]` と `non_goals[]` は常に `IMPROVEMENT-PLAN` 側が優先します。

### `maintenance/` — 実地の記録と手順

| ファイル | 何か |
|---|---|
| `DOGFOODING-LOG.md` | 実地でアプリを 3 本作りながら記録した摩擦点 77 件（F-001〜F-082） |
| `friction-to-test.md` | 摩擦点を再発防止テストへ変換する手順。深刻度 最高・高 はテスト無しでクローズしない |

ハーネス本体はこの 2 つを参照しません。ハーネス側に残っているのは摩擦点 ID（`F-047` など）だけで、
深刻度 最高・高 のものは `../harness/CLAIMS.md` の表から引けます（CI 項目 P が検証）。

### `archive/` — 役目を終えた調査資料

`harness-comparison-plain.html` / `harness-comparison-technical.html` は、apparness と
claude-code-harness を比較した調査報告です。`plans/IMPROVEMENT-PLAN.*` の根拠として残しています。

## 過去の記録に出てくる古いパス

`plans/`・`maintenance/`・`archive/` と `harness/CHANGELOG.md` の過去の版は、書かれた時点のパスのまま残しています。

| 過去の記録での名前 | 現在の場所 |
|---|---|
| `docs/HARNESS_GUIDE.md`（完全ガイド 18 節） | 利用者向けの節は `harness/docs/GUIDE.md`、6・11・18 節と各節の経緯は `docs/DESIGN.md` |
| `harness/README.md` | 使い方は `harness/docs/USAGE.md`、改修手順は `docs/DEVELOPMENT.md` |
| `docs/README.md` | この `docs/INDEX.md` |
| `docs/flow/harness-flow-plain.html` | `harness/docs/flow/harness-flow-plain.html` |
