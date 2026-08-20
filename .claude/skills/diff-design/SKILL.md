---
name: diff-design
description: 仕様変更・要件追加が生じた際に、まず要件定義書を新しいバージョンとして書き直し、そのうえで旧設計との差分を機械的に明らかにして新しい設計書を起こす。変更が必要な機能だけを新規に作り直し、変更のない機能は既存の実装を再利用する。「仕様を変えたい」「機能を追加したい」と言われたら使う。
---

# diff-design

既存アプリ（`apps/<app_id>/` が既に存在する）に対する仕様変更・要件追加のための手順です。
`harness/CONVENTIONS.md` 11 節「上位文書優先の原則」を先に読んでください。**下位の文書（設計）だけを
直して上位の文書（要件定義）を古いまま放置することはありません。** 要件が変わったら、まず要件定義書
自体を新しいバージョンとして書き直します。

## 1. 要件定義書を新しいバージョンとして書き直す

1. `requirements-analyst` subagent で変更点をヒアリングする。
2. 変更前に、現在の `requirements.md`/`requirements.machine.yaml` を
   `00-requirements/history/requirements.v<旧バージョン>.{md,yaml}` としてコピー保存する
   （元の形をそのまま残す）。
3. 旧 `requirements.machine.yaml` を `status: SUPERSEDED`、`superseded_by: <新バージョン>` に更新する。
4. `requirements.machine.yaml`/`.md` の `version` をインクリメントし、`status: DRAFT` で新しい
   要件を書く。ユーザーの承認を得たら `status: APPROVED`、`approved_by`、`approved_at` を設定する
   （この承認は `AUTONOMY.yaml` のモードに関わらず常に人間必須）。

## 2. 設計を要件に追従させる

5. 現在の `apps/<app_id>/02-design/architecture.machine.yaml` を
   `02-design/history/architecture.v<旧バージョン>.yaml` としてコピー保存する。
6. `solution-architect` subagent で新しい `architecture.machine.yaml`
   （`design_version` をインクリメント、`based_on_requirements_version` を新しい要件 `version` に
   更新）を作成する。独立機能の原則（`harness/CONVENTIONS.md` 6 節）は変更時も維持する。
7. 新旧を比較して差分レポートを出す:
   ```
   python3 harness/scripts/diff_architecture.py apps/<app_id>/02-design/history/architecture.v<旧>.yaml apps/<app_id>/02-design/architecture.machine.yaml
   ```
8. レポートに従って:
   - **追加・変更された機能**: 新しい `feature_id`（例: `<old-id>-v2`）を採番し、
     `new-feature-worktree` skill で新規 worktree を作成する。旧 feature の `status.yaml` は
     `state: SUPERSEDED`、`superseded_by: <new-id>` に更新する。
   - **削除された機能**: 対応する `status.yaml` を `state: SUPERSEDED`（後継なし）にする。
   - **変更なしの機能**: 何もしない。既存の実装・worktree・status.yaml をそのまま再利用する。
9. ユーザーに差分レポートと対応方針を提示し、承認を得てから `architecture.machine.yaml` を
   `status: APPROVED` にする。**`based_on_requirements_version` が要件の現在の `version` と
   一致していないと Hook が拒否する**（`harness/CONVENTIONS.md` 7 節 Rule 7）。

この手順により、変更が必要な機能だけが新規プロジェクト化され、無関係な機能は無駄な作り直しをせず、
かつ要件定義書が常に設計の唯一の正しい根拠であり続けます。
