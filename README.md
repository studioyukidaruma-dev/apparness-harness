<div id="top"></div>

## 使用技術一覧

<p style="display: inline">
  <!-- 強制レイヤ・スクリプト -->
  <img src="https://img.shields.io/badge/-Python-F2C63C.svg?logo=python&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-pytest-0A9EDC.svg?logo=pytest&style=for-the-badge&logoColor=white">
  <!-- 実行ホスト -->
  <img src="https://img.shields.io/badge/-Claude%20Code-D97757.svg?logo=anthropic&style=for-the-badge&logoColor=white">
  <!-- 機械可読な契約 -->
  <img src="https://img.shields.io/badge/-YAML-CB171E.svg?logo=yaml&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-JSON%20Schema-000000.svg?logo=json&style=for-the-badge&logoColor=white">
  <!-- CI -->
  <img src="https://img.shields.io/badge/-GitHub%20Actions-2088FF.svg?logo=github-actions&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-OSV--Scanner-4285F4.svg?logo=google&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-Git-F05032.svg?logo=git&style=for-the-badge&logoColor=white">
</p>

## 目次

1. [プロジェクトについて](#プロジェクトについて)
2. [環境](#環境)
3. [ディレクトリ構成](#ディレクトリ構成)
4. [開発環境構築](#開発環境構築)
5. [他プロジェクトへの導入](#他プロジェクトへの導入)
6. [アプリを 1 本作る流れ](#アプリを-1-本作る流れ)
7. [機械が強制すること](#機械が強制すること)
8. [コマンド一覧](#コマンド一覧)
9. [文書の役割分担](#文書の役割分担)
10. [トラブルシューティング](#トラブルシューティング)

<br />
<div align="right">
    <a href="./docs/flow/harness-flow-plain.html"><strong>しくみ案内（やさしい版・HTML） »</strong></a>
</div>
<br />
<div align="right">
    <a href="./docs/flow/harness-flow-technical.html"><strong>実行フロー精査書（技術版・HTML） »</strong></a>
</div>
<br />

## プロジェクト名

apparness — Claude Code 駆動でアプリを自動生成するためのハーネス

<!-- プロジェクトについて -->

## プロジェクトについて

**AI にアプリを作らせるときの工程管理と品質の下限を、機械が強制する仕組み**です。
一般的な開発ルールは「守りましょう」と書いてあるだけですが、apparness では
**規約に反する操作そのものが実行前に拒否されます**。

中心にあるのは 1 つの原則です。

> **AI の自己申告をゲートの根拠にしない。**

たとえば「テストを書いて通しました」は信じません。代わりに、宣言されたテストコマンドを
ハーネスが**実際に実行**し、終了コードと実行時のコミットを記録した**受領書**を作ります。
受領書が無ければ `TESTED` に進めず、受領書は人にも AI にも手書きできません
（書き換えようとすると Hook が拒否します）。

アプリは「入出力さえわかれば内部を知らなくてよい最小機能単位」に分割され、機能ごとに
git worktree を切って並行実装できます。中断しても `apps/<app-id>/STATE.machine.yaml`
（機械向け）と `PROGRESS.md`（人間向け・自動生成）を見ればすぐ再開できます。

| 特徴 | 内容 |
| --- | --- |
| 決定論的な強制 | Hook 12 ルール ＋ CI 16 項目。すべて機械判定 |
| 依存ゼロの強制レイヤ | `harness/hooks/**` は Python 標準ライブラリのみ。**縛る側のコードが読める** |
| 実行ベースの検証 | 受領書・JUnit XML・JSON Schema 突合。自己申告に頼らない |
| アプリ非依存 | 技術スタックを規定しない。検証コマンドはアプリ側が宣言する |
| 自己テスト | 702 件（`harness/tests/`）。CI で毎回実行 |

<p align="right">(<a href="#top">トップへ</a>)</p>

## 環境

| 言語・ツール | バージョン | 用途 |
| --- | --- | --- |
| Python | 3.9 以上（CI は 3.12） | 強制レイヤ・スクリプト |
| Claude Code | Hook をサポートする版 | 実行ホスト。Hook の起動元 |
| PyYAML | >= 6.0 | `harness/scripts/**` のみ |
| jsonschema | >= 4.20 | `harness/scripts/**` のみ |
| pytest | >= 8.0 | ハーネス自身のテスト |
| OSV-Scanner | v2.5.1（CI で SHA256 検証） | 依存ライブラリの脆弱性スキャン |

**`harness/hooks/**` は依存ゼロ（標準ライブラリのみ）です。** Hook はツール呼び出しのたびに
起動されるため、起動コストと信頼性を最優先し、外部パッケージを一切使いません。
これは監査可能性のためでもあります（強制の実体が数千行の読める Python に収まっている）。

生成されるアプリ側の技術スタックはハーネスが規定しません。設計フェーズでアプリごとに決めます。

<p align="right">(<a href="#top">トップへ</a>)</p>

## ディレクトリ構成

```
.
├── .claude/                         ← 実効設定。git worktree に自動複製される
│   ├── agents/                      ← subagent 5 種
│   │   ├── requirements-analyst.md      要件定義
│   │   ├── solution-architect.md        土台・設計
│   │   ├── feature-builder.md           機能実装
│   │   ├── gate-reviewer.md             独立レビュー（Write/Edit を持たない）
│   │   └── integrator.md                組み上げ
│   ├── skills/                      ← skill 4 種
│   │   ├── init-app/                    アプリ作成の開始
│   │   ├── new-feature-worktree/        機能用 worktree の作成
│   │   ├── sync-progress/               ダッシュボード再生成（--html 可）
│   │   └── diff-design/                 仕様変更の再設計
│   └── settings.json                ← Hook 登録（SessionStart / PreToolUse / PostToolUse / Stop / SubagentStop）
├── .github/workflows/
│   └── harness-checks.yml           ← selftest / ci-check / vuln-scan の 3 ジョブ
├── harness/                         ← ハーネス本体。harness/ ブランチでのみ書き込める
│   ├── CONVENTIONS.md               ← 規範の単一情報源（15 節で凍結）
│   ├── CLAIMS.md                    ← 主張と証跡の対応表（CI 項目 P が検証）
│   ├── README.md                    ← ハーネスの使い方
│   ├── STACK_PACK.md                ← スタック固有標準の外部化仕様
│   ├── hooks/                       ← 決定論的ガード（依存ゼロ）
│   │   ├── lib/path_utils.py            判定ロジックの本体
│   │   ├── pre_tool_use_guard.py        Rule 1-3,5-7,9-12
│   │   ├── post_tool_use_guard.py       Bash の事後検証・巻き戻し
│   │   ├── post_tool_use_sync.py        Rule 4（ダッシュボード再生成）
│   │   ├── stop_commit_guard.py         Rule 8（未コミットで停止拒否）
│   │   └── session_start_healthcheck.py 強制レイヤの自己診断
│   ├── procedures/                  ← フェーズ固有の手順（読む agent は always-reads 宣言が必須。CI 項目 L が計上）
│   ├── quality/                     ← セキュリティ・デザイン・レビュー基準
│   ├── schemas/                     ← 機械可読ファイルの JSON Schema（8 種）
│   ├── scripts/                     ← 決定論ロジック（18 本）
│   ├── templates/                   ← 各種ひな形（13 種）
│   └── tests/                       ← ハーネス自身の pytest（702 件）
├── briefs/<app-id>.brief.yaml       ← 企画ブリーフ（任意）。要件定義の前に人間が記入する入力
├── apps/<app-id>/                   ← 生成物。init-app skill が都度生成する（未生成）
├── docs/                            ← **人間専用。** アプリ作成中の subagent は読まない
│   ├── README.md                        どこに何があるかの索引
│   ├── HARNESS_GUIDE.md                 設計意図・背景・既知の制約（4 点セット）
│   ├── flow/                            しくみの説明書（やさしい版 / 技術版の HTML）
│   ├── plans/                           改修計画・改修指示書（機械可読 ＋ 人間向けの双子）
│   ├── maintenance/                     実地の摩擦点 77 件と、それをテストへ変える手順
│   └── archive/                         役目を終えた調査資料（他ハーネスとの比較）
├── VERSION                          ← ハーネスの版（セマンティックバージョニング）
├── CHANGELOG.md                     ← 変更履歴（CI 項目 Q が追随を要求）
├── README.md
└── pyrightconfig.json               ← 型チェッカ設定（実行には影響しない）
```

ルート直下に残しているのは 4 つだけです。**実行物がパスとして解決するもの**
（`VERSION` / `CHANGELOG.md` — `ci_check.py` と `render_progress.py` がルート基準で開きます）、
**入口**（`README.md`）、**ツール設定**（`pyrightconfig.json`）。
説明のための文書はすべて `docs/` にあり、**ハーネス内部（`harness/**`・`.claude/**`）から
`docs/` 配下を名指しする箇所は 1 件もありません**（`docs/HARNESS_GUIDE.md` への出典注記を除く）。

<p align="right">(<a href="#top">トップへ</a>)</p>

## 開発環境構築

**ハーネスを使うだけならインストールは不要です。** `harness/hooks/**` は依存ゼロで動きます。
以下はハーネス自身を保守・改修する場合の手順です。

### 依存のインストール

```
pip install -r harness/requirements-dev.txt
```

`harness/scripts/**`（CI チェック・進捗生成・検証実行）が PyYAML と jsonschema を、
テストが pytest を使います。

### 動作確認

```
python3 -m pytest harness/tests -q
python3 harness/scripts/ci_check.py --branch $(git branch --show-current)
python3 harness/hooks/session_start_healthcheck.py < /dev/null
```

`702 passed` / `OK: すべてのチェックを通過しました` / 無出力（exit 0）なら成功です。
3 つ目は**強制レイヤ自身が健全か**の自己診断で、異常があればここに理由が出ます。

### ハーネスを改修するとき

```
git switch -c harness/<topic>
```

**`harness/` で始まるブランチでないと `harness/`・`.claude/`・`.github/` に書き込めません**
（Rule 1 が実行前に拒否します）。改修したら `CHANGELOG.md` の `## [Unreleased]` への追記も
必須です（CI 項目 Q が要求します）。

<p align="right">(<a href="#top">トップへ</a>)</p>

## 他プロジェクトへの導入

**既存プロジェクトからこのハーネスを使う場合は git submodule として取り込み、
`.claude/` と `harness/` を利用側プロジェクトのルートへ symlink してください。**

```
git submodule add https://github.com/studioyukidaruma-dev/apparness-harness.git vendor/apparness-harness
ln -s vendor/apparness-harness/.claude .claude
ln -s vendor/apparness-harness/harness harness
```

### なぜ symlink が要るのか

`.claude/settings.json` の Hook は `$CLAUDE_PROJECT_DIR/harness/hooks/...` を直接参照します。
`$CLAUDE_PROJECT_DIR` は Claude Code が**利用側プロジェクトのルート**に対して設定する環境変数
なので、`harness/` がそのルート直下に見えないと Hook は起動しません。サブモジュールを
`vendor/` 配下に置いただけでは動かないのはこのためです。同じ理由で `.claude/agents` /
`.claude/skills` も Claude Code がプロジェクトルート直下の `.claude/` から読むため、symlink
（または同等のコピー）が必要です。

### 利用時の構成

```
<利用側プロジェクトのルート>/
├── .claude -> vendor/apparness-harness/.claude
├── harness -> vendor/apparness-harness/harness
├── vendor/apparness-harness/         ← submodule 本体
├── apps/<app-id>/                    ← init-app skill が利用側に生成する
└── briefs/<app-id>.brief.yaml        ← 任意。利用側で記入する
```

`apps/` と `briefs/` は利用側プロジェクト固有の生成物です。サブモジュール（ハーネス本体）
には含めません。

### 更新の追従

```
git submodule update --remote vendor/apparness-harness
```

symlink をサポートしない環境では、`ln -s` の代わりにディレクトリをコピーしてください。
その場合、更新の追従は手動での再コピーになります。

<p align="right">(<a href="#top">トップへ</a>)</p>

## アプリを 1 本作る流れ

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

### 先に要件を書いて渡す（企画ブリーフ・任意）

対話で少しずつ引き出すのではなく、目的・必要な機能・使ってほしい技術を**一度にまとめて**渡したい
場合は、`init-app` の前にブリーフを書きます。

```
python3 harness/scripts/new_brief.py <app-id> "<app-name>"   # briefs/<app-id>.brief.yaml を生成
# 分かるところだけ埋める（空欄のままでよい）
python3 harness/scripts/check_brief.py briefs/<app-id>.brief.yaml
```

`init-app` は `briefs/<app-id>.brief.yaml` を自動で探します。あれば要件定義の出発点になり、
**記入済みの項目は聞き直されず、空欄だけが対話で確認されます**。ブリーフが無ければ従来どおり
全て対話で決めます。項目名を綴り間違えると `check_brief.py` が exit 1 で落ちます（黙って
無視されて「書いたのに伝わらない」状態になるのを防ぐため）。ブリーフはあくまで**入力**であり、
要件の承認は従来どおり人間が明示的に行います。

<p align="right">(<a href="#top">トップへ</a>)</p>

## 機械が強制すること

### Hook（実行前・Claude Code のセッション内）

| Rule | 内容 |
| --- | --- |
| 1 | ハーネス本体は `harness/` ブランチでのみ書き込める（唯一の緊急避難路 `HARNESS_UNLOCK=1` あり。使うと警告が出る） |
| 2 | 担当外の機能ディレクトリは書けない |
| 3 | 承認済みの契約は凍結（`open_issues[]` への追記のみ可） |
| 4 | `status.yaml` 更新でダッシュボードを再生成（非ブロッキング） |
| 5 | 設計で必須と決めた Skill が無ければ `src/**` を書けない |
| 6 | 機能実装用 worktree から上位文書は書けない |
| 7 | 承認記録を伴わない `APPROVED`／要件の版とズレた設計を拒否 |
| 8 | フェーズ節目ファイルを未コミットのまま応答を終えられない |
| 9 | 状態の後退・飛び越しを拒否（`BLOCKED` 経由の抜け道も塞ぎ済み） |
| 10 | 受領書なし・失敗・HEAD 不一致の `TESTED` を拒否。受領書の手書きも拒否 |
| 11 | 結線カバレッジと統合受領書を欠いた `INTEGRATED` を拒否 |
| 12 | **危険操作フロア** — 再帰削除・秘密ファイル読み取り・履歴破壊・検証スキップ・外部送信・`sudo` を無条件で拒否 |

Rule 12 は **確認（ask）ではなく拒否（deny）** です。自動で最後まで進めるモードでは AI が
自分で確認に答えてしまうため、確認は歯止めになりません。Rule 12 と Bash 経由の間接書き込み検知には
バイパス用の環境変数を **意図的に持ちません**（AI が自分で解除できたら決定論的強制の意味が
消えるため）。解除路があるのは Rule 1 の `HARNESS_UNLOCK=1` だけです。

判定できないときは通しません。ブロックする hook（`pre_tool_use_guard.py` /
`stop_commit_guard.py`）は、想定外の例外でも、入力そのものを解釈できない場合でも、
通過ではなく **exit 2 ＋ 理由** で止まります（fail-closed）。逆に git 情報が取れず
Rule の判定が劣化している場合は止めずに、`SessionStart` の診断が影響する Rule を名指しして
警告します。

### CI（push 後・サーバーサイド再検証）

`harness/scripts/ci_check.py` が 16 項目（A〜G, I〜Q）を再検証します。Hook は Claude Code の
セッション内でしか効かないため、人間の直接コミットや別ツールでの編集はここで弾きます。

| 項目 | 内容 | 項目 | 内容 |
| --- | --- | --- | --- |
| A | JSON Schema 検証 | K | 要件→機能→テストのトレーサビリティ |
| B | ハーネス本体の変更ブランチ | L | コンテキスト予算 |
| C | feature ブランチの担当範囲 | M | 規範と手順の二重管理 |
| D | 契約の凍結 | N | 結線カバレッジ |
| E | 要件と設計の版整合 | O | `CONVENTIONS.md` の節新設拒否 |
| F | 状態遷移の妥当性 | P | `CLAIMS.md` と実体の drift |
| G | ダッシュボードの鮮度 | Q | `VERSION` / `CHANGELOG` の追随 |
| I | 受領書の有効性 | | |

### 決定論と AI 判断の切り分け

| 判定 | 誰が決めるか |
| --- | --- |
| 書き込み先・状態遷移・テストの成否・契約の整合・危険操作 | **機械のみ** |
| 実装品質のレビュー | AI が指摘 → **機械が集計**（`Blocker` ≥ 1 → `NO-GO`） |
| 機能の分け方・要件の内容 | AI（意図的に据え置き。要件承認は人間必須） |
| 承認者が本当に人間か | **判定不能。**「承認者名と日時が空でない」までしか機械化できない |

<p align="right">(<a href="#top">トップへ</a>)</p>

## コマンド一覧

| コマンド | 実行する処理 |
| --- | --- |
| `python3 -m pytest harness/tests -q` | ハーネス自身のテスト（702 件） |
| `python3 harness/scripts/ci_check.py --branch <name>` | 規約の決定論チェック 16 項目 |
| `python3 harness/hooks/session_start_healthcheck.py < /dev/null` | 強制レイヤの健全性診断 |
| `python3 harness/scripts/render_progress.py --app <app-id>` | ダッシュボード再生成 |
| `python3 harness/scripts/render_progress.py --app <app-id> --html` | 非エンジニア向け HTML も生成 |
| `python3 harness/scripts/run_verification.py --app <app-id> [--feature <id>]` | 検証を実行して受領書を作る（`--dry-run` 可） |
| `python3 harness/scripts/run_integration_verification.py --app <app-id>` | 統合検証を実行して受領書を作る（`--dry-run` 可） |
| `python3 harness/scripts/check_interfaces.py [--app <app-id>]` | `interfaces[]` 両端の JSON Schema 突合 |
| `python3 harness/scripts/check_traceability.py [--app <app-id>]` | 要件→機能→テストの対応検証 |
| `python3 harness/scripts/check_integration_traceability.py [--app <app-id>]` | 結線カバレッジの検証 |
| `python3 harness/scripts/validate_yaml.py <yaml> <schema>` | 機械可読ファイルのスキーマ検証 |
| `python3 harness/scripts/validate_status_transition.py <old_state> <new_state> [--status-file <path>]` | 状態遷移の妥当性を手動確認（状態は**位置引数で 2 つ必須**） |
| `python3 harness/scripts/print_conventions.py --sections 6,9,13` | 規約の必要な節だけを出力 |
| `python3 harness/scripts/diff_architecture.py <old> <new>` | 設計の差分を機械的に算出 |
| `python3 harness/scripts/vuln_scan.py [--app <app-id>]` | 依存ライブラリの脆弱性スキャン |
| `python3 harness/scripts/new_brief.py <app-id> [app-name]` | 企画ブリーフの記入用フォーマットを生成 |
| `python3 harness/scripts/check_brief.py <brief.yaml> [--json]` | ブリーフの書式検証と未記入項目の列挙 |
| `python3 harness/scripts/new_app_scaffold.py <app-id> <app-name> [mode] [--brief <path>]` | アプリ雛形の生成（通常は skill 経由） |
| `python3 harness/scripts/new_feature_scaffold.py <app-id> <feature-id>` | 機能 worktree の生成（通常は skill 経由） |

<p align="right">(<a href="#top">トップへ</a>)</p>

## 文書の役割分担

**同じことを 2 箇所に書かない**のが一貫した方針です（片方だけ直して食い違うため。CI 項目 M が検出）。
追記するときは次の表で置き場所を決めてください。

| 書きたいこと | 置き場所 | 注意 |
| --- | --- | --- |
| 機械が強制する規範 | `harness/CONVENTIONS.md` | **15 節で凍結。**新しい節は CI 項目 O が拒否。既存節へ追記する |
| 設計意図・背景・既知の制約 | `docs/HARNESS_GUIDE.md` | 制約は 4 点セット（症状／根本原因／緩和策／**再検討の条件**） |
| 人間が理解するための説明全般 | `docs/` 配下 | **アプリ作成中の subagent は読まない**（`CONVENTIONS.md` 15節）。agent/skill から読ませてはいけない。読ませたい内容は規範なので `CONVENTIONS.md` か `procedures/` へ |
| フェーズ固有の手順 | agent/skill プロンプト、`harness/procedures/*.md` | `procedures/` に置いたら `always-reads` の宣言が必須（CI 項目 L） |
| 品質の下限 | `harness/quality/*.md` | 外部依存ゼロで常に効くこと |
| 「これを止める」主張と証拠 | `harness/CLAIMS.md` | 規則を足したら必ず行を追加（CI 項目 P がテスト名の実在を検証） |
| 技術ごとの流儀 | 外部スタックパック（形式は `harness/STACK_PACK.md`） | **ハーネス本体には書かない** |
| 機械可読ファイルの形式 | `harness/schemas/*.schema.json` | CI 項目 A が検証 |
| 実地で困ったこと | `docs/maintenance/DOGFOODING-LOG.md` | 深刻度 高・最高 は**再発防止テストなしでクローズ禁止**（手順は同ディレクトリの `friction-to-test.md`）。ハーネス本体からは参照しない |
| ハーネスの変更履歴 | `CHANGELOG.md` / `VERSION` | ハーネス本体を触ったら追記必須（CI 項目 Q） |

迷ったら 3 つの質問で決まります。
**① 破ったら機械が止めるか** → `CONVENTIONS.md`　
**② 「なぜ」の話か** → `docs/HARNESS_GUIDE.md`　
**③ 特定の担当者の手順か** → その指示書か `procedures/`

<p align="right">(<a href="#top">トップへ</a>)</p>

## トラブルシューティング

### 拒否: ... はハーネス本体です

`harness/`・`.claude/`・`.github/` は `harness/` で始まるブランチでのみ書き込めます（Rule 1）。

```
git switch -c harness/<topic>
```

### 拒否: `verification_receipt.commit` が現在の HEAD と一致しません

**いちばん多い詰まりどころです。**受領書は「そのコミットで通った」という主張なので、
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

### 拒否: ... はリポジトリの外を指しています（D-1）

Rule 12 の危険操作フロアです。リポジトリ配下に留まると確認できない再帰削除は拒否されます
（`..` を含む綴り・未展開の変数・`/`・`.`・先頭ワイルドカードは、解決するまでもなく拒否）。
必要な操作なら AI ではなく**人間が自分の手で**実行してください。

### CONVENTIONS.md: 凍結中のため節の新設はできません

15 節で凍結されています（CI 項目 O）。既存の節の中に統合してください。

### CHANGELOG.md: ハーネス本体に ... 変更がありますが、CHANGELOG.md が更新されていません

CI 項目 Q です。`## [Unreleased]` に何を変えたかを箇条書きで追記してください。

### harness/CLAIMS.md: ... に ... が存在しません

CI 項目 P です。`CLAIMS.md` に書いたテスト名が `harness/tests/` に実在しません。
テストを書くか、表の記載を実体に合わせてください。

### 常時読み込みの合計が上限 46,000 バイトを超えています

CI 項目 L です。まず**説明・背景・設計意図を `docs/HARNESS_GUIDE.md` へ移して**ください。
手順を `harness/procedures/*.md` へ移す場合は `always-reads` の宣言が必要です
（宣言しないと計上を逃れられてしまうため、CI が別途拒否します）。

### PROGRESS.md の先頭に「強制レイヤ: 異常」と出る

**そのセッションでは決定論的な強制が効いていない可能性があります。**
次のコマンドで理由を確認し、直してからセッションをやり直してください。

```
python3 harness/hooks/session_start_healthcheck.py < /dev/null
```

### No module named pytest

ハーネス自身のテストには開発用依存が必要です。

```
pip install -r harness/requirements-dev.txt
```

### エディタに「インポート "path_utils" を解決できませんでした」と出る

`harness/hooks/**` は実行時に `sys.path` を操作して `path_utils` を読むため、静的解析が
追えません。`pyrightconfig.json` が `extraPaths` を宣言しているので、**エディタを再読み込み
すれば消えます**。実行時の挙動には一切影響しません。

<p align="right">(<a href="#top">トップへ</a>)</p>
