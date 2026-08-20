# apparness

様々なアプリを Claude Code 駆動で自動生成するためのハーネス。

- `harness/` と `.claude/` — ハーネス本体（テンプレート）。アプリ作成中は書き込みが Hooks で保護されます。
  使い方は `harness/README.md`、規約は `harness/CONVENTIONS.md` を参照してください。
- `apps/<app-id>/` — 個々のアプリ作成で生成される成果物。`init-app` skill で新規作成します。

アプリは「入出力さえわかれば内部を知らなくてよい最小機能単位」に分割され、機能ごとに
git worktree を切って並行実装できます。中断しても `apps/<app-id>/STATE.machine.yaml`
（機械向け）と `PROGRESS.md`（人間向け、自動生成）を見ればすぐに再開できます。
