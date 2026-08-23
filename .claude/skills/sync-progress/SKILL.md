---
name: sync-progress
description: apps/<app-id>/03-features/*/status.yaml から PROGRESS.md と STATE.machine.yaml を手動で再生成する。通常は status.yaml 更新時に hook が自動実行するが、強制的にリフレッシュしたい時や複数アプリを一括更新したい時に使う。
---

# sync-progress

1. 対象を確認する。特定アプリなら:
   ```
   python3 harness/scripts/render_progress.py --app <app_id>
   ```
   すべてのアプリを一括更新するなら:
   ```
   python3 harness/scripts/render_progress.py --all
   ```
2. 出力された `apps/<app_id>/PROGRESS.md` の内容をユーザーに要約して伝える
   （どの機能が完了していて、次に何をすべきか）。
