# スタックパック仕様 — スタック固有の標準を外部から接続する

このファイルが規定するのは**パックの形式**であって、**パックの中身ではありません**。
apparness は「どんなアプリでも作れる」ことを存在理由とするため、
**特定の技術スタックをハーネス本体に規定することは制約違反**として扱います。
「Python ではこう書く」「React ではこう書く」という濃い実務知見は、ハーネス本体を汚さずに
**外部プラグインとして接続**します。

## 強制機構は既に完成している

新しい仕組みは要りません。既存の受け口をそのまま使います。

1. `solution-architect` が技術スタックを決め、対応するスタックパックを
   `01-foundation/shared-kernel.yaml` の `required_skills[]` に記録する
   （`kind: stack-pack` を付ける）。
2. **Rule 5**（`CONVENTIONS.md` 7節）が、`feature-builder` の `src/**` への最初の書き込み時に
   各 `plugin_ref` の有効化状況を機械検証し、欠けていれば**実装そのものをブロック**する。
3. **Rule 6** により `feature-builder` は `shared-kernel.yaml` を書き換えられないため、
   実装中に独断でパックを外すことも追加することもできない。

```yaml
# apps/<app-id>/01-foundation/shared-kernel.yaml
required_skills:
  - name: "python-stack-pack"
    plugin_ref: "python-stack-pack@your-marketplace"
    purpose: "Python + FastAPI の標準（バージョン下限・禁止パターン・テスト規約）"
    kind: "stack-pack"        # 省略時は "skill"
```

`kind` は人間と `solution-architect` のための区別であり、Rule 5 の判定は
`kind` によらず `plugin_ref` の有効化状況だけを見ます。

## パックが満たすべきインターフェース

### 命名

- スキル名・プラグイン名は `<stack-id>-stack-pack`（例: `python-stack-pack`,
  `typescript-web-stack-pack`）。
- 1 パック = 1 スタック。「Python と Go の両方」のような複合パックは作らない
  （機能ごとに異なるスタックを選べる、という apparness の前提を壊すため）。

### 必須の記載項目

パックの `SKILL.md`（または同等の入口文書）は、次の 5 つを**すべて**含むこと。
どれかを欠くパックは `required_skills[]` に登録しない。

| # | 項目 | 内容 |
|---|---|---|
| 1 | **言語・ランタイムのバージョン下限とその根拠** | 「3.11 以上」だけでなく「なぜそれ未満を切るのか」（EOL・必要な言語機能・既知の脆弱性）まで書く |
| 2 | **禁止パターン** | そのスタックで実際に事故が起きた書き方と、代わりに何を使うか。抽象的な注意喚起ではなく、実際に手を動かせる指示にする |
| 3 | **`verification.*_command` の推奨値** | `shared-kernel.yaml` の `verification:`（`CONVENTIONS.md` 12節）にそのまま書ける具体的なコマンド列。JUnit XML を出せるなら、その出力方法と `junit_xml` の値も示す |
| 4 | **テスト規約** | テストの置き場所・命名・テスト ID の書式（`test_strategy.coverage[].test_ids` に何と書けば JUnit XML と一致するか） |
| 5 | **ライブラリ選定の指針** | そのエコシステムで推奨/非推奨のライブラリと理由（保守状況・ライセンス・既知の脆弱性） |

### `harness/quality/*.md` との優先関係

**ハーネス内蔵のベースラインが常に優先します。** スタックパックはそれに**追加**するもので
あって、置き換えるものではありません。

| 競合したとき | どちらが勝つか |
|---|---|
| `harness/quality/security-baseline.md` と矛盾する内容 | **ベースラインが勝つ**。パック側の記述は無効 |
| `harness/quality/design-baseline.md` と矛盾する内容 | **ベースラインが勝つ** |
| `harness/quality/review-rubric.md` に無い観点 | `gate-reviewer` の指摘としては**無効**（パックの内容はレビューの軸にならない） |
| ベースラインが触れていない領域 | **パックが埋める**（これがパックの存在意義） |

`gate-reviewer` はスタックパックを読みません。レビューの軸を rubric だけに固定するためです
（スタック固有の流儀まで verdict の材料にすると、何ラウンドで終わるか誰にも分からなくなる）。
パックは**実装時に `feature-builder` が従う指針**であって、**通過判定の基準ではありません**。

### ハーネス本体に置いてはいけないもの

- 特定言語のバージョン・ライブラリ名・フレームワーク名を含む規約
- 特定のテストランナーを前提にしたコマンド
- 特定のディレクトリ構成（`src/`・`tests/` という粒度までがハーネスの規定範囲）

これらが `harness/` 配下に現れたら、それはパックへ切り出すべき内容です。

## どこを探すか（登録する前に必ず実在を確かめる）

**存在しない `plugin_ref` を書くと Rule 5 が実装を完全にブロックします。** 一方でこの文書は
長らく「どこを探すか」を書いていなかったため、`solution-architect` は安全側に倒して
`required_skills[]` を空のまま進めるしかありませんでした（ドッグフーディング F-025）。
探す順序を次のとおり定めます。

1. **そのセッションで既に有効なプラグイン**: `.claude/settings.json` /
   `.claude/settings.local.json` の `enabledPlugins` を読む。ここにあるものは確実に使える。
2. **インストール済みだが未有効のもの**: `/plugin` の一覧（人間に確認してもらう）。
3. **マーケットプレイス**: `/plugin marketplace` に登録済みのマーケットプレイスを検索する。
   採用したいものが見つかったら、`plugin_ref` の綴り（`<name>@<marketplace>`）を
   **そのまま写して**ユーザーにインストールを依頼する。
4. 見つからなければ**登録しない**。`required_skills[]` を空にして Layer 1 だけで進める。

`solution-architect` は自分ではインストールできません（Rule 1）。**必ずユーザーに確認し、
インストールされたことを `enabledPlugins` で確かめてから**登録してください。綴りを推測で書いたり、
「あとで作られるはず」の名前を先に書いたりしないこと。

## パックを作らない場合

`required_skills[]` が空でも、`harness/quality/*.md`（Layer 1）と Rule 10 の検証受領書は
そのまま効きます。スタックパックは**品質の上積み**であって、下限を担保するものではありません。
