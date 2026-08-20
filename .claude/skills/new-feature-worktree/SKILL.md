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
   - `git worktree add apps/<app_id>/.worktrees/<feature_id> -b feature/<app_id>/<feature_id> main`
   - worktree 内に `SPEC.md` / `contract.yaml`（設計時点のドラフトがあれば引き継ぐ）/ `status.yaml`
     （`state: CONTRACT_APPROVED`）/ `src/` / `tests/` / `.claude/` を生成し、初期コミットする
   - 既に worktree が存在する場合は冪等にスキップする
3. コマンド出力に含まれる起動コマンド（`cd apps/<app_id>/.worktrees/<feature_id>/... && claude`）を
   ユーザーに案内する。担当者はそのディレクトリで新しいセッションを開始し、`feature-builder` subagent
   として実装を進める。

複数の機能を並行して進める場合は、機能ごとにこの skill を実行して別々の worktree を用意し、
それぞれ別のセッション（別ターミナル、または別の担当者）から起動する。
