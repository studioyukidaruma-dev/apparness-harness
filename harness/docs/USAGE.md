# apparness ハーネス 使い方

> **人間向けの文書です。** AI（Claude Code の agent・skill）はこの文書を読みません（Rule 13）。

アプリを作る人のための手順書です。しくみの説明は [GUIDE.md](GUIDE.md)、図解のやさしい説明は
[flow/harness-flow-plain.html](flow/harness-flow-plain.html) にあります。

## 目次

1. [導入後のセットアップ](#1-導入後のセットアップ)
2. [ハーネスの更新](#2-ハーネスの更新)
3. [アプリを 1 本作る流れ](#3-アプリを-1-本作る流れ)
4. [コマンド一覧](#4-コマンド一覧)
5. [トラブルシューティング](#5-トラブルシューティング)

---

## 1. 導入後のセットアップ

ハーネスの導入方法は、配布元リポジトリの `README.md` にあります。導入したら、スクリプトが使う
依存を入れて、強制レイヤが健全かを確認します。

```
pip install -r harness/requirements.txt
python3 harness/hooks/session_start_healthcheck.py < /dev/null   # 無出力（exit 0）なら成功
```

`harness/hooks/` は依存ゼロ（標準ライブラリのみ）で動きます。`harness/scripts/` は PyYAML と
jsonschema を使います。`pip` が使えない環境（PEP 668 の管理下にある system python など）では、
仮想環境か [uv](https://docs.astral.sh/uv/) を使ってください。

```
uv run --with-requirements harness/requirements.txt python3 harness/scripts/<script>.py ...
```

---

## 2. ハーネスの更新

導入に使ったハーネスのリポジトリで、導入したい版のタグに切り替え、インストーラをもう一度実行します。

```
git -C <ハーネスのリポジトリ> fetch --tags
git -C <ハーネスのリポジトリ> checkout v<版>
python3 <ハーネスのリポジトリ>/harness/scripts/install.py <導入先プロジェクト> --dry-run
python3 <ハーネスのリポジトリ>/harness/scripts/install.py <導入先プロジェクト>
```

- **必ずリリースのタグ（`v<版>`）から導入してください。** main にはリリース前の変更が含まれることがあり、
  その状態を導入すると版番号は同じでも中身が違うため、CI 項目 Q が不合格になります（インストーラも警告します）。
  各版の変更点は [`../CHANGELOG.md`](../CHANGELOG.md) にあります。
- 前回導入したファイルは上流の内容で上書きされます。**導入先でハーネス本体を直接直した分は元に戻ります。**
- 上流で無くなったファイルは削除されます。導入先が自分で足した agent や skill には触れません。
- ハーネスが導入していないファイルと同じ場所に内容の違うファイルを置こうとすると、**何も書き込まずに止まります。**
  上書きしてよいときだけ `--force` を付けてください。
- 既存のアプリがある場合は、更新後に `python3 harness/scripts/render_progress.py --all` でダッシュボードを
  再生成してからコミットしてください。`PROGRESS.md` はハーネスの版を表示するため、再生成しないと CI 項目 G が不合格になります。
- 更新は `harness/<topic>` ブランチか main で行ってコミットしてください（CI 項目 B はそれ以外のブランチでの
  ハーネス本体の変更を拒否します）。

---

## 3. アプリを 1 本作る流れ

| # | フェーズ | 動くもの | 機械が止めるところ |
| --- | --- | --- | --- |
| 1 | 要件定義 | skill `init-app` → agent `requirements-analyst` | 承認は**モードに関わらず常に人間必須**。承認者・日時なしの `APPROVED` は Rule 7 が拒否 |
| 2 | 土台・設計 | agent `solution-architect` | 要件の版とズレた設計は承認できない（Rule 7）。検証コマンドの宣言もここで必須 |
| 3 | 機能実装 | skill `new-feature-worktree` → agent `feature-builder` | 担当外は書けない（Rule 2）。契約は凍結（Rule 3）。状態の飛び越し不可（Rule 9） |
| 4 | レビュー | skill `code-review` → agent `gate-reviewer` | verdict は深刻度の機械集計（`Blocker` ≥ 1 → `NO-GO`）。レビューアは書き換えられない |
| 5 | 検証 | `run_verification.py` | **受領書なしで `TESTED` にできない**（Rule 10） |
| 6 | 組み上げ | agent `integrator` | つなぎ目を全部テストしないと `INTEGRATED` にできない（Rule 11） |

状態は 1 段ずつしか進みません。

```
NOT_STARTED → CONTRACT_DRAFTED → CONTRACT_APPROVED → IN_PROGRESS → IMPLEMENTED → TESTED → INTEGRATED
```

いつ中断しても、`apps/<app-id>/PROGRESS.md`（人間向け）と `STATE.machine.yaml`（機械向け）を見れば
どこまで終わっているか・次に何をすべきかが分かります。どちらも自動生成なので手書きしないでください。
仕様変更・要件追加が生じたら、`diff-design` skill を使います。

### 先に要件を書いて渡す（企画ブリーフ・任意）

対話で少しずつ引き出すのではなく、目的・必要な機能・使ってほしい技術を**一度にまとめて**渡したい
場合は、`init-app` の前にブリーフを書きます。

```
python3 harness/scripts/new_brief.py <app-id> "<app-name>"   # briefs/<app-id>.brief.yaml を生成
# 分かるところだけ埋める（空欄のままでよい）
python3 harness/scripts/check_brief.py briefs/<app-id>.brief.yaml
```

`init-app` は `briefs/<app-id>.brief.yaml` を自動で探します。あれば要件定義の出発点になり、
**記入済みの項目は聞き直されず、空欄だけが対話で確認されます**。項目名を綴り間違えると
`check_brief.py` が exit 1 で落ちます。ブリーフはあくまで**入力**であり、要件の承認は人間が明示的に行います。

---

## 4. コマンド一覧

引数の詳細は、各スクリプトの `--help` で確認できます。

| コマンド | 実行する処理 |
| --- | --- |
| `python3 harness/hooks/session_start_healthcheck.py < /dev/null` | 強制レイヤの健全性診断 |
| `python3 harness/scripts/ci_check.py --branch <name>` | 規約の決定論チェック（CI と同じ） |
| `python3 harness/scripts/render_progress.py --app <app-id>` | ダッシュボード再生成 |
| `python3 harness/scripts/render_progress.py --app <app-id> --html` | 非エンジニア向け HTML も生成 |
| `python3 harness/scripts/run_verification.py --app <app-id> --feature <id>` | 検証を実行して受領書を作る（`--dry-run` 可） |
| `python3 harness/scripts/run_integration_verification.py --app <app-id>` | 統合検証を実行して受領書を作る（`--feature` は取らない。`--dry-run` 可） |
| `python3 harness/scripts/check_interfaces.py [--app <app-id>]` | `interfaces[]` 両端の JSON Schema 突合 |
| `python3 harness/scripts/check_traceability.py [--app <app-id>]` | 要件→機能→テストの対応検証 |
| `python3 harness/scripts/check_integration_traceability.py [--app <app-id>]` | 結線カバレッジの検証 |
| `python3 harness/scripts/validate_yaml.py <yaml> <schema>` | 機械可読ファイルのスキーマ検証（**位置引数 2 つ**。`--app` は取らない） |
| `python3 harness/scripts/validate_status_transition.py <old_state> <new_state> [--status-file <path>]` | 状態遷移の妥当性を手動確認（**位置引数 2 つ**） |
| `python3 harness/scripts/diff_architecture.py <old> <new>` | 設計の差分を機械的に算出 |
| `python3 harness/scripts/vuln_scan.py [--app <app-id>]` | 依存ライブラリの脆弱性スキャン（`osv-scanner` が必要） |
| `python3 harness/scripts/new_brief.py <app-id> [app-name]` | 企画ブリーフの記入用フォーマットを生成 |
| `python3 harness/scripts/check_brief.py <brief.yaml> [--json]` | ブリーフの書式検証と未記入項目の列挙 |
| `python3 harness/scripts/new_app_scaffold.py <app-id> <app-name> [mode] [--brief <path>]` | アプリ雛形の生成（通常は skill 経由） |
| `python3 harness/scripts/new_feature_scaffold.py <app-id> <feature-id>` | 機能 worktree の生成（通常は skill 経由） |

---

## 5. トラブルシューティング

### 拒否: `verification_receipt.commit` が現在の HEAD と一致しません

**いちばん多い詰まりどころです。** 受領書は「そのコミットで通った」という主張なので、
受領書を作ったあとにコミットすると HEAD が進んで無効になります。正しい順序はこれです。

```
実装をコミット            ← ここで HEAD が確定する
run_verification.py 実行  ← 受領書に「この HEAD で通した」と記録される
status.yaml を TESTED に  ← まだコミットしない
git add -A && git commit  ← 受領書と TESTED を一緒に記録する
```

### 拒否: ... への Bash / NotebookEdit 経由の書き込みは受け付けません

`status.yaml`・`requirements.machine.yaml`・`architecture.machine.yaml`・`integration.machine.yaml`
は**書き込み前後の内容比較**で判定するため、結果を予測できない手段では書けません。
Edit / Write / MultiEdit を使ってください。

### 拒否: ... はハーネス本体です

`harness/`・`.claude/`・`.github/` は `harness/` で始まるブランチでのみ書き込めます（Rule 1）。
アプリ作成中にハーネス本体を直す必要はありません。ハーネスの更新は 2節の手順で行います。

### 拒否: ... は人間向けの文書です（Rule 13）

AI が `harness/docs/` の文書を読もうとしたときの拒否です。**正常な動作です。** AI は実行物と
`harness/CONVENTIONS.md` から動作を判断します。文書の内容を AI に伝えたい場合は、必要な部分を
会話で直接伝えてください。

### 拒否: ... はリポジトリの外を指しています（D-1）

Rule 12 の危険操作フロアです。リポジトリ配下に留まると確認できない再帰削除は拒否されます
（`..` を含む綴り・未展開の変数・`/`・`.`・先頭ワイルドカードは、解決するまでもなく拒否）。
必要な操作なら AI ではなく**人間が自分の手で**実行してください。

### PROGRESS.md の先頭に「強制レイヤ: 異常」と出る

**そのセッションでは決定論的な強制が効いていない可能性があります。**
次のコマンドで理由を確認し、直してからセッションをやり直してください。

```
python3 harness/hooks/session_start_healthcheck.py < /dev/null
```

### No module named 'yaml' / 'jsonschema'

`harness/scripts/` の依存が入っていません。1節のセットアップを行ってください。
