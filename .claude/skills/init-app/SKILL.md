---
name: init-app
description: 新規アプリの作成を開始する。app-id と app-name から雛形を生成し、要件定義フェーズ（requirements-analyst subagent）に引き継ぐ。「新しいアプリを作りたい」「アプリ作成を始めたい」と言われたら使う。
---

# init-app

新規アプリ作成の入り口です。以下の手順で進めてください。

1. `app_id`（kebab-case。例: `hello-world-todo`）と `app_name`（人間向けの名前）を、
   引数から読み取るかユーザーに確認する。app_id が未指定なら app_name から機械的に生成してよいが、
   必ずユーザーに確認する。
2. `apps/<app_id>/` が既に存在しないか確認する（存在すれば `diff-design` skill で仕様変更として
   扱うべきかユーザーに確認する）。
3. **`AskUserQuestion` で自動化モード (`autonomy_mode`) を確認する**（`harness/CONVENTIONS.md` 9 節参照）。
   選択肢は `MANUAL` / `SUPERVISED`（推奨・デフォルト） / `AUTONOMOUS`。ユーザーが即答しなければ
   `SUPERVISED` を既定として進めてよい。**このモードに関わらず要件定義の承認は常に人間必須**である
   ことを伝える。
4. **アプリ作成用のブランチを作る**（`CONVENTIONS.md` 3節）。既にそのブランチにいる場合は不要:
   ```
   git checkout -b app/<app_id>/bootstrap
   ```
   `main` に直接コミットしないこと。設計が承認され、機能実装に入る直前にこのブランチを
   `main` にマージする（`new-feature-worktree` は現在の HEAD から worktree を切るため、
   マージせずに進めても動作するが、複数人で分担するなら共有ブランチに載せてから切る）。
5. 以下を実行して雛形を生成する:
   ```
   python3 harness/scripts/new_app_scaffold.py <app_id> "<app_name>" <autonomy_mode>
   ```
6. コマンドの出力を確認し、`apps/<app_id>/00-requirements/` と `apps/<app_id>/AUTONOMY.yaml` が
   生成されたことを確認する。`git add -A && git commit` で雛形をコミットする。
7. `requirements-analyst` subagent に要件定義フェーズを引き継ぐ。subagent は
   `requirements.md` / `requirements.machine.yaml` を **`status: DRAFT` のまま**完成させ、
   承認用の要約を返して終了する。subagent が質問を返してきたら、あなたがユーザーに取り次ぎ、
   回答を添えて subagent を再開させる。
8. **要件の承認は、あなた（このセッション）が自分で確定させる。** subagent に委ねてはいけない:
   1. subagent が返した要約をユーザーに提示し、`AskUserQuestion` などで**明示的な承認**を得る。
      `AUTONOMY.yaml` の `mode` が `AUTONOMOUS` でも省略しない（`harness/CONVENTIONS.md` 9 節の
      固定ポリシー）。
   2. 承認が得られたら、あなた自身が `requirements.machine.yaml` を編集して
      `status: APPROVED` / `approved_by`（**承認したユーザーの識別子**。AI やエージェントの名前を
      書かない） / `approved_at`（`date -u +%Y-%m-%dT%H:%M:%SZ`）を**同じ編集で**設定する
      （`status` だけ先に APPROVED にする書き込みは Hook が拒否する）。
      `requirements.md` の記載も一致させる。
   3. `git add -A && git commit` する。

   subagent に承認を書かせると、AI が AI の伝聞を根拠に APPROVED を確定させることになり、
   「要件承認は常に人間必須」という固定ポリシーが形だけになる（ドッグフーディング F-010 で実証）。

要件定義が承認されたら、次は `solution-architect` subagent による設計フェーズであることを伝える。
