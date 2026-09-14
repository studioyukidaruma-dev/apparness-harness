<div id="top"></div>

## 使用技術一覧

<p style="display: inline">
  <img src="https://img.shields.io/badge/-Python-F2C63C.svg?logo=python&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-pytest-0A9EDC.svg?logo=pytest&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-Claude%20Code-D97757.svg?logo=anthropic&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-YAML-CB171E.svg?logo=yaml&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-JSON%20Schema-000000.svg?logo=json&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-GitHub%20Actions-2088FF.svg?logo=github-actions&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-OSV--Scanner-4285F4.svg?logo=google&style=for-the-badge&logoColor=white">
</p>

## 目次

1. [プロジェクトについて](#プロジェクトについて)
2. [環境](#環境)
3. [導入](#導入)
4. [詳しい説明](#詳しい説明)

## プロジェクト名

apparness — Claude Code 駆動でアプリを自動生成するためのハーネス

## プロジェクトについて

**AI にアプリを作らせるときの工程管理と品質の下限を、機械が強制する仕組み**です。
一般的な開発ルールは「守りましょう」と書いてあるだけですが、apparness では
**規約に反する操作そのものが実行前に拒否されます**。

中心にあるのは 1 つの原則です。

> **AI の自己申告をゲートの根拠にしない。**

たとえば「テストを書いて通しました」は信じません。宣言されたテストコマンドをハーネスが
**実際に実行**し、終了コードと実行時のコミットを記録した**受領書**が無ければ、機能を `TESTED` に
進められません。アプリは「入出力さえわかれば内部を知らなくてよい最小機能単位」に分割され、
機能ごとに git worktree を切って並行実装できます。

| 特徴 | 内容 |
| --- | --- |
| 決定論的な強制 | Hook 13 ルール ＋ CI 17 項目。すべて機械判定 |
| 依存ゼロの強制レイヤ | `harness/hooks/**` は Python 標準ライブラリのみ。**縛る側のコードが読める** |
| 実行ベースの検証 | 受領書・JUnit XML・JSON Schema 突合。自己申告に頼らない |
| アプリ非依存 | 技術スタックを規定しない。検証コマンドはアプリ側が宣言する |
| AI と人間の文書を分離 | AI は実行物と規約だけから判断し、人間向けの説明は読まない |

<p align="right">(<a href="#top">トップへ</a>)</p>

## 環境

| 言語・ツール | バージョン | 用途 |
| --- | --- | --- |
| Python | 3.9 以上（CI は 3.12） | 強制レイヤ・スクリプト・インストーラ |
| Claude Code | Hook をサポートする版 | 実行ホスト |
| git | — | 導入先は git リポジトリであること（判定が git に依存するため） |
| PyYAML / jsonschema | `harness/requirements.txt` | `harness/scripts/**` のみ |

生成されるアプリ側の技術スタックはハーネスが規定しません。設計フェーズでアプリごとに決めます。

<p align="right">(<a href="#top">トップへ</a>)</p>

## 導入

**インストーラで、ハーネスを導入先のプロジェクトへコピーします。** リリースのタグを指定して取得してください。

```
git clone --branch v1.3.3 https://github.com/studioyukidaruma-dev/apparness-harness.git ~/apparness-harness
cd <導入先プロジェクト>                     # git リポジトリであること（新規なら先に git init）
python3 ~/apparness-harness/harness/scripts/install.py . --dry-run   # 何が起きるかを確認
python3 ~/apparness-harness/harness/scripts/install.py .
git add -A && git commit -m "apparness ハーネスを導入"
python3 -m pip install -r harness/requirements.txt                   # Claude Code が使う python3 に入れる
python3 harness/hooks/session_start_healthcheck.py < /dev/null       # コミット後に実行。無出力（exit 0）なら成功
```

**依存（PyYAML・jsonschema）は、Claude Code が使う `python3` に入れてください。** Hook によるダッシュボードの
再生成も、agent・skill が実行するスクリプトも、その `python3` で動きます。`pip` が使えない環境
（PEP 668 の管理下にある Ubuntu などの標準の Python）では、プロジェクトの外に仮想環境を作り、
**有効化したシェルから Claude Code を起動**します。

```
python3 -m venv ~/.venvs/apparness
~/.venvs/apparness/bin/pip install -r harness/requirements.txt
source ~/.venvs/apparness/bin/activate    # このシェルで動作確認を行い、Claude Code を起動する
```

依存が入っていなければ、動作確認とセッション開始時の自己診断が警告します。

導入されるのは `harness/`（`harness/docs/` を含む）、`.claude/agents/`・`.claude/skills/`、
`.github/workflows/harness-checks.yml` と、`.claude/settings.json` への Hook の登録、`.gitignore` の追記です。
既存の設定や、導入先が自分で置いたファイルは上書きしません。更新の手順は `harness/docs/USAGE.md` にあります。

<p align="right">(<a href="#top">トップへ</a>)</p>

## 詳しい説明

**この README は大まかな説明だけにとどめています。詳しい説明は `harness/docs/` の文書を読んでください。**

| 知りたいこと | 文書 |
| --- | --- |
| 使い方（セットアップ・更新・アプリを作る流れ・コマンド・トラブル対処） | [harness/docs/USAGE.md](harness/docs/USAGE.md) |
| しくみ（フェーズ・Hook の 13 ルール・CI・受領書・制約） | [harness/docs/GUIDE.md](harness/docs/GUIDE.md) |
| 図解のやさしい説明 | [harness/docs/flow/harness-flow-plain.html](harness/docs/flow/harness-flow-plain.html) |
| 変更履歴 | [harness/CHANGELOG.md](harness/CHANGELOG.md) |
| ハーネス自体を改修する人向け（設計意図・開発手順・改修計画） | [docs/INDEX.md](docs/INDEX.md) |

`harness/docs/` と `docs/` はどちらも**人間向けの文書**です。AI（Claude Code の agent・skill）は
これらを読まず、実行物と `harness/CONVENTIONS.md` から動作を判断します（Rule 13 が読み取りを拒否します）。

<p align="right">(<a href="#top">トップへ</a>)</p>
