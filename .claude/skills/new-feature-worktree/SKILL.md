---
name: new-feature-worktree
description: 承認済みの設計 (architecture.machine.yaml) から、指定した機能用の git worktree と雛形 (SPEC.md/contract.yaml/status.yaml) を作成する。機能の実装に着手する際に使う。
---

# new-feature-worktree

1. `app_id` と `feature_id` を引数またはユーザーから確認する。
   `feature_id` は `apps/<app_id>/02-design/architecture.machine.yaml` の `features[]` に
   存在している必要がある（無ければ先に `solution-architect` で設計を完成させる）。
2. 以下を実行する:
   ```
   python3 harness/scripts/new_feature_scaffold.py <app_id> <feature_id>
   ```
   このスクリプトが行うこと:
   - `architecture.machine.yaml` が `status: APPROVED` であることを確認
   - **現在の HEAD** から `git worktree add apps/<app_id>/.worktrees/<feature_id> -b feature/<app_id>/<feature_id> HEAD`
     （`main` 固定ではない。アプリ作成は `app/<app-id>/bootstrap` ブランチで行うため、
     `main` から切ると要件・設計・shared-kernel が入らない worktree ができてしまう）
   - 分岐元のコミットに要件・shared-kernel・設計が含まれているかを事前検査し、
     欠けていれば worktree を作らずにエラーで止まる
   - worktree 内に `SPEC.md` / `contract.yaml`（設計時点のドラフトがあれば引き継ぐ）/ `status.yaml`
     （`state: CONTRACT_APPROVED`）/ `src/` / `tests/` / `.claude/` を生成し、初期コミットする
   - 既に worktree が存在する場合は冪等にスキップする
3. コマンド出力に含まれる起動コマンド（`cd apps/<app_id>/.worktrees/<feature_id>/... && claude`）を
   ユーザーに案内する。**担当者はそのディレクトリで新しいセッションを開始する必要がある。**
   Rule 2（担当外ガード）はセッションの worktree ルートの basename が `feature_id` と
   一致することを要求するため、リポジトリルートで動いているセッションから `feature-builder`
   subagent を起動しても、書き込みはすべて拒否される（cwd が固定された subagent は
   `EnterWorktree` でも worktree に移れない）。
   1 つのセッションで複数機能を回す場合は、`EnterWorktree` でその worktree に入ってから
   `feature-builder` を起動し、終わったら `ExitWorktree`（`keep`）で戻る、を機能ごとに
   繰り返す。**この方式では並行実装はできない**（セッションは同時に 1 つの worktree にしか入れない）。

複数の機能を並行して進める場合は、機能ごとにこの skill を実行して別々の worktree を用意し、
それぞれ別のセッション（別ターミナル、または別の担当者）から起動する。
