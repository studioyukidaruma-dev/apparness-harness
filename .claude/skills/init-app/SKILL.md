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
4. 以下を実行して雛形を生成する:
   ```
   python3 harness/scripts/new_app_scaffold.py <app_id> "<app_name>" <autonomy_mode>
   ```
5. コマンドの出力を確認し、`apps/<app_id>/00-requirements/` と `apps/<app_id>/AUTONOMY.yaml` が
   生成されたことを確認する。`git add -A && git commit` で雛形をコミットする。
6. `requirements-analyst` subagent に要件定義フェーズを引き継ぐ。ユーザーとの対話を通じて
   `requirements.md` / `requirements.machine.yaml` を完成させ、承認まで導く。

要件定義が承認されたら、次は `solution-architect` subagent による設計フェーズであることを伝える。
