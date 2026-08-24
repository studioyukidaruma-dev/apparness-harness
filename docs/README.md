# docs/ — 人間がハーネスを理解するための文書

> **この配下は人間専用です。アプリ作成中の subagent はここを読みません。**
> 規範として定めてあります（`../harness/CONVENTIONS.md` 15節「`docs/` は人間専用」）。
> 読ませたい内容が出てきたら、それは規範なので `CONVENTIONS.md` か
> `harness/procedures/*.md` に置いてください。ここへ出してよいのは
> 「ハーネス内部にあるが実は人間向けで、AI が参照する必要のない記述」だけです。

読まれない場所なので、どれだけ厚くなってもセッションの常時コスト（CI 項目 L の
コンテキスト予算）は 1 バイトも増えません。

## 目的別の入口

| 知りたいこと | 読むもの |
|---|---|
| **なぜこの設計なのか**（思想・設計意図・既知の制約と再検討条件） | [HARNESS_GUIDE.md](HARNESS_GUIDE.md) |
| **何がいつ動くのか**（非エンジニア向け） | [flow/harness-flow-plain.html](flow/harness-flow-plain.html) |
| **どう判定しているのか**（監査・実装者向け） | [flow/harness-flow-technical.html](flow/harness-flow-technical.html) |
| **これから何を直すのか** | [plans/](plans/) |
| **実地で何が壊れたのか**、それをどうテストに変えるか | [maintenance/](maintenance/) |
| **なぜ今の形に落ち着いたのか**（役目を終えた調査） | [archive/](archive/) |

規約そのもの（機械が強制する規範）は、ここではなく `../harness/CONVENTIONS.md` にあります。
ハーネスの変更履歴は `../CHANGELOG.md` です。

## 中身

### `HARNESS_GUIDE.md` — 完全ガイド（18節）

設計意図・背景・既知の制約の単一の置き場所。`CONVENTIONS.md` は規範だけを持ち、
「なぜ」はすべてこちらに寄せてあります（18節は `CONVENTIONS.md` から実際に移設した分）。
`ci_check.py` の項目 L が「上限に当たったら説明・背景・設計意図をここへ移せ」と案内する先も
このファイルです。

### `flow/` — しくみの説明書

| ファイル | 対象読者 | 中身 |
|---|---|---|
| `harness-flow-plain.html` | 非エンジニア | 何をする仕組みか、いつ何が動くか、用語の言いかえ表 |
| `harness-flow-technical.html` | 監査・保守する人 | Hook の exit code 契約、Rule 1–12 の判定仕様、CI 項目 A–Q、実測値と再検証手順 |

どちらもブラウザで直接開けます（外部リソースに依存しない単一ファイル）。
実行物（`settings.json`・`ci_check.py`・`path_utils.py`・schemas）から数値を再抽出して
書かれており、末尾に再検証手順が付いています。

### `plans/` — 改修計画と改修指示書

| ファイル | 何か |
|---|---|
| `IMPROVEMENT-PLAN.machine.yaml` | 別ハーネスとの比較から導いた改修計画。`tasks[]` に `status` 付き |
| `IMPROVEMENT-PLAN.md` | 上の人間向けの双子 |
| `REPAIR-ORDER.machine.yaml` | 実際に動かして見つかった残存欠陥の改修指示書 |
| `REPAIR-ORDER.md` | 上の人間向けの双子 |

`.machine.yaml` は「このファイルを読んで改修してください」と指示されたときに、そのまま
実行計画として読まれることを想定した機械向けの書式です（アプリ作成時には読まれません）。
2 つは併存し、`invariants[]` と `non_goals[]` は常に `IMPROVEMENT-PLAN` 側が優先します。

### `maintenance/` — ハーネスを保守する人のための記録と手順

| ファイル | 何か |
|---|---|
| `DOGFOODING-LOG.md` | 実地でアプリを 3 本作りながら記録した摩擦点 77 件（F-001〜F-082）。ハーネスが本当に壊れた記録 |
| `friction-to-test.md` | その摩擦点を再発防止テストへ変換する手順。深刻度 最高・高 はテスト無しでクローズしない |

**ハーネス本体はこの 2 つを一切参照しません。** もとは `DOGFOODING-LOG.md` がリポジトリルートに、
`friction-to-test.md` が `harness/procedures/` にあり、`CONVENTIONS.md` やテストの docstring から
名前で参照されていましたが、ハーネス改修のための記録をハーネス自身が参照する筋合いはないため、
参照を断ち切ってここへ集めました。ハーネス側に残っているのは摩擦点 ID（`F-047` など）だけで、
深刻度 最高・高 のものは `../harness/CLAIMS.md` の表から引けます（CI 項目 P が検証）。

### `archive/` — 役目を終えた調査資料

`harness-comparison-plain.html` / `harness-comparison-technical.html` は、apparness と
claude-code-harness を比較した調査報告です。`plans/IMPROVEMENT-PLAN.*` の根拠なので、
計画の出典を辿るために残しています。比較対象だった claude-code-harness の複製そのものは
削除済みです（105MB、この調査以外に用途が無かったため）。
