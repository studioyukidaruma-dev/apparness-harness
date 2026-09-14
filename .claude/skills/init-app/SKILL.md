---
name: init-app
description: 新規アプリの作成を開始する。企画ブリーフ（briefs/<app-id>.brief.yaml）があればそれを起点にし、無ければ対話で要件を固める。app-id と app-name から雛形を生成し、要件定義フェーズ（requirements-analyst subagent）に引き継ぐ。「新しいアプリを作りたい」「アプリ作成を始めたい」と言われたら使う。
---

# init-app

新規アプリ作成の入り口です。以下の手順で進めてください。

1. `app_id`（kebab-case。例: `hello-world-todo`）と `app_name`（人間向けの名前）を、
   引数から読み取るかユーザーに確認する。app_id が未指定なら app_name から機械的に生成してよいが、
   必ずユーザーに確認する。
2. **企画ブリーフを探す**（下の「企画ブリーフ」節）。見つかれば、それが要件定義の出発点になる。
3. `apps/<app_id>/` が既に存在しないか確認する（存在すれば `diff-design` skill で仕様変更として
   扱うべきかユーザーに確認する）。
4. **`AskUserQuestion` で自動化モード (`autonomy_mode`) を確認する**（`harness/CONVENTIONS.md` 9 節参照）。
   選択肢は `MANUAL` / `SUPERVISED`（推奨・デフォルト） / `AUTONOMOUS`。ユーザーが即答しなければ
   `SUPERVISED` を既定として進めてよい。**このモードに関わらず要件定義の承認は常に人間必須**である
   ことを伝える。ブリーフの `autonomy_mode` に記入があれば、それを既定の選択肢として提示する。
5. **アプリ作成用のブランチを作る**（`CONVENTIONS.md` 3節）。既にそのブランチにいる場合は不要:
   ```
   git checkout -b app/<app_id>/bootstrap
   ```
   `main` に直接コミットしないこと。設計が承認され、機能実装に入る直前にこのブランチを
   `main` にマージする（`new-feature-worktree` は現在の HEAD から worktree を切るため、
   マージせずに進めても動作するが、複数人で分担するなら共有ブランチに載せてから切る）。
6. 以下を実行して雛形を生成する（ブリーフがあれば `--brief` を付ける。生成物の中に入力として
   残り、後から要件と突き合わせられる）:
   ```
   python3 harness/scripts/new_app_scaffold.py <app_id> "<app_name>" <autonomy_mode> [--brief briefs/<app_id>.brief.yaml]
   ```
7. コマンドの出力を確認し、`apps/<app_id>/00-requirements/` と `apps/<app_id>/AUTONOMY.yaml` が
   生成されたことを確認する。`git add -A && git commit` で雛形をコミットする。
8. `requirements-analyst` subagent に要件定義フェーズを引き継ぐ。**ブリーフがある場合は、
   subagent への指示に次の 3 点を必ず含める**:
   - ブリーフの取り込み先パス（`apps/<app_id>/00-requirements/brief.yaml`）
   - `check_brief.py` が報告した**未記入項目のリスト**（これが対話で確認すべき項目そのもの）
   - 記入済みの項目は聞き直さず、そのまま要件に写すこと

   subagent は `requirements.md` / `requirements.machine.yaml` を **`status: DRAFT` のまま**完成させ、
   承認用の要約を返して終了する。subagent が質問を返してきたら、あなたがユーザーに取り次ぎ、
   回答を添えて subagent を再開させる。
9. **要件の承認は、あなた（このセッション）が自分で確定させる。** subagent に委ねてはいけない:
   1. subagent が返した要約をユーザーに提示し、`AskUserQuestion` などで**明示的な承認**を得る。
      `AUTONOMY.yaml` の `mode` が `AUTONOMOUS` でも省略しない（`harness/CONVENTIONS.md` 9 節の
      固定ポリシー）。**ブリーフの記載は承認ではない**。ブリーフは入力であって、
      「この要件でよい」という判断はブリーフを書いた時点ではまだ行われていない。
   2. 承認が得られたら、あなた自身が `requirements.machine.yaml` を編集して
      `status: APPROVED` / `approved_by`（**承認したユーザーの識別子**。AI やエージェントの名前を
      書かない） / `approved_at`（`date -u +%Y-%m-%dT%H:%M:%SZ`）を**同じ編集で**設定する
      （`status` だけ先に APPROVED にする書き込みは Hook が拒否する）。
      `requirements.md` の記載も一致させる。
   3. `git add -A && git commit` する。

   subagent に承認を書かせると、AI が AI の伝聞を根拠に APPROVED を確定させることになり、
   「要件承認は常に人間必須」という固定ポリシーが形だけになる（ドッグフーディング F-010 で実証）。

要件定義が承認されたら、次は `solution-architect` subagent による設計フェーズであることを伝える。

## 企画ブリーフ（あれば使う。無ければ対話で決める）

ブリーフは、要件定義の前にユーザーが記入する固定フォーマットの YAML です。目的・必要な機能・
使ってほしい技術などを一度に渡せるので、対話で少しずつ引き出すより誤解が起きにくくなります。

### 探す順序

1. ユーザーが引数やメッセージでパスを指定していれば、それ
2. `briefs/<app_id>.brief.yaml`
3. `briefs/` 配下に 1 件しかブリーフが無く、`app_id` が未確定なら、それを候補としてユーザーに確認する

### 見つかった場合

```
python3 harness/scripts/check_brief.py <path>
```

- **exit 1（書き方の誤り）**: YAML として読めない（字下げのずれなど）か、項目名の綴り違いなどの
  書式違反。**勝手に解釈して進めない**。出力の行番号・項目と「よくある原因」をユーザーに伝え、
  直すか、その項目の内容を口頭で教えてもらう。
- **exit 0**: 出力の「記入済み」と「未記入」をそのまま次のフェーズに渡す。
  未記入項目のうち `MUST`（要件定義に不可欠）と `ASK` は、要件定義の対話で確認する対象。
  `FREE` は空欄のままでよい。

ブリーフに書かれた内容は**そのまま要件として扱う**。勝手に広げたり、書かれていない機能を
足したりしないこと。ブリーフの記述どうしが矛盾している場合は、推測で解決せずユーザーに確認する。

### 見つからなかった場合

従来どおり対話で要件を固めます。ただし着手前に一度だけ、ブリーフを書く選択肢を提示してください
（伝えたいことが多いユーザーには、対話より速いことがあります）:

```
python3 harness/scripts/new_brief.py <app_id> "<app_name>"
```

「対話で進めたい」と言われたら、それ以上勧めずに対話で進めます。
