# harness/ — apparness ハーネス本体

このディレクトリと、リポジトリルート直下の `.claude/`（agents/skills/hooks 設定）が
「apparness ハーネス」の本体です。**アプリ作成作業中はこれらへの書き込みが Hooks で保護されます**
（`harness/<topic>` ブランチでの意図的な変更か、`HARNESS_UNLOCK=1` を設定した場合のみ可能）。

個々のアプリの成果物は `apps/<app-id>/` に生成されます。ハーネス自体はテンプレートとして、
どのアプリ作成でも繰り返し使われることを想定しています。詳しい規約は `CONVENTIONS.md` を参照してください。

## セットアップ

```
pip install -r harness/requirements.txt
```

（`harness/hooks/` 配下は依存ゼロで動くよう作られていますが、`harness/scripts/` 配下は
PyYAML / jsonschema を使います。）

## 全体フロー

```
0. init-app skill        → autonomy_mode を確認、00-requirements/ の雛形生成 +
                              requirements-analyst へ引き継ぎ
1. requirements-analyst   → requirements.md / requirements.machine.yaml を作成・承認
                              （この承認だけは autonomy_mode に関わらず常に人間必須）
2. solution-architect      → shared-kernel.yaml / architecture.machine.yaml / 各 feature の
                              contract ドラフトを作成・承認（独立機能への分割はここで行う）
3. new-feature-worktree skill（機能ごとに繰り返す）
                            → git worktree 作成 + SPEC.md/contract.yaml/status.yaml 雛形生成
4. feature-builder          → 各 worktree 内で機能を実装（担当者ごと・並行可能）
5. integrator                → 全機能 TESTED 後、merge して結線し、結合テストコードを書いて
                              04-integration/ に残す
```

いつ中断しても、`apps/<app-id>/STATE.machine.yaml`（機械向け）と `PROGRESS.md`（人間向け）を見れば
どこまで終わっているか・次に何をすべきかが分かります。この 2 ファイルは自動生成なので手書きしないでください。
`PROGRESS.md` には現在の `autonomy_mode` も表示されます。

## 自動化の度合い

各アプリは `AUTONOMY.yaml` で `MANUAL` / `SUPERVISED`（デフォルト） / `AUTONOMOUS` のいずれかの
モードを持ちます。詳細は `CONVENTIONS.md` 9 節。要件定義の承認だけはモードに関わらず常に人間必須です。

## 仕様変更・要件追加が生じたら

`diff-design` skill を使ってください。旧設計との差分を機械的に算出し、変更が必要な機能だけを
新規に作り直し、変更のない機能はそのまま再利用します。

## ディレクトリの見取り図

詳細は `CONVENTIONS.md` 1 節を参照。要点だけ書くと:

- `.claude/` — hooks/agents/skills の実効設定（リポジトリルート直下。worktree にも自動複製される）
- `harness/hooks/` — 決定論的ガード（依存ゼロの Python）
- `harness/templates/` — 各種ドキュメントのひな形
- `harness/schemas/` — machine-readable ファイルの JSON Schema
- `harness/scripts/` — scaffold 生成・進捗再生成・設計差分計算などの決定論ロジック
- `harness/quality/` — セキュリティ・デザインの最低ラインを定めるベースライン文書

## 品質保証（セキュリティ・デザイン）

外部Skillの有無で品質が変わってしまわないよう、二層構造にしています。詳細は `CONVENTIONS.md` 10 節。

1. `harness/quality/security-baseline.md` / `design-baseline.md` — 何もインストールしなくても
   常に効く最低ライン。該当フェーズで各 subagent が都度読む。
2. Claude Code 標準搭載の `security-review` / `code-review` skill — `integrator` と
   `feature-builder` が必須ステップとして実行する。
3. `required_skills[]`（`shared-kernel.yaml`） — デザイン系 Skill（`frontend-design` 等）や
   `find-skills` 経由の専門ルール集を使うと決めたら `solution-architect` がここに記録する。
   「あれば使う」ではなく「設計で決めたら実装フェーズの必須要件」で、Hook が実装開始前に
   機械的に検証し、欠けていればブロックする（無指定なら 1・2 のみで進む）。

## 上位文書優先の原則

要件定義 > 設計 > 機能契約の順で重要度が高く、下位の文書は上位の文書と常に整合している必要が
あります。詳細は `CONVENTIONS.md` 11 節。要件が変わったら `diff-design` skill で要件定義書自体を
新しいバージョンとして書き直し（旧バージョンは `00-requirements/history/` に退避）、設計の
`based_on_requirements_version` が要件の現在の `version` と一致しない限り、設計を承認済みにする
ことは Hook が拒否します（Rule 7）。

## Hooks が強制する約束事項

`CONVENTIONS.md` 7 節を参照。ハーネス非侵襲性・担当外ガード・契約凍結・進捗自動再生成・
必須Skillの充足ゲート・上位文書ガード・要件↔設計の整合性ゲート・フェーズ節目のコミット強制・
状態遷移の妥当性チェックの 9 つを Claude Code の PreToolUse / PostToolUse / Stop / SubagentStop
hooks で強制しています。Bash 経由の間接的な書き込みも対象範囲内でブロックします。AI の自己申告には
頼っていません。

## CI 連携

`.github/workflows/harness-checks.yml` が、上記 Hook のうち Claude Code のセッション外
（人間が直接 `git commit` する等）でもすり抜けられては困るものを、push/PR のたびに
`harness/scripts/ci_check.py` でサーバーサイド再検証します。詳細は `HARNESS_GUIDE.md` 12節。

## 既知の制約

- 状態遷移チェックは `BLOCKED` を経由した遷移までは検証しません。
- Bash 経由の書き込み検知は変数展開されたパス等の検知漏れが残ります（誤検知はクォート考慮の
  トークン化で解消済み）。
- CI はアプリの技術スタックに依存しない範囲のみが対象で、feature-builder/integrator が書く
  アプリ固有のテスト実行は含みません。
- ライブラリの脆弱性スキャンは自動化されておらず、`solution-architect` の調査と `security-review`
  skill（利用可能な場合）に依存しています。

これらは実際にアプリを 1 本作ってみてから、必要に応じて拡張してください。
