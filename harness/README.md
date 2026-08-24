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

`pip` が使えない環境（Ubuntu の system python など PEP 668 の管理下）では、仮想環境か
[uv](https://docs.astral.sh/uv/) を使ってください。インストールせずに実行するなら:

```
uv run --python 3.12 --with pyyaml --with jsonschema python harness/scripts/<script>.py ...
```

（`harness/hooks/` 配下は依存ゼロで動くよう作られていますが、`harness/scripts/` 配下は
PyYAML / jsonschema を使います。）

ハーネス自身を保守する場合は、テストも実行できるようにしてください。

```
pip install -r harness/requirements-dev.txt
python3 -m pytest harness/tests -q
```

`pip` が使えない環境なら:

```
uv run --python 3.12 --with pytest --with pyyaml --with jsonschema python -m pytest harness/tests -q
```

`harness/tests/` はハーネスの決定論ロジック（Bash パース・状態遷移判定・受領書検証など）の
回帰テストです。CI の `harness-selftest` ジョブでも実行されます。**判定ロジックを変更するときは
必ず先にここを緑にしてください。**

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
4. feature-builder          → 各 worktree 内で機能を実装（担当者ごと・並行可能。ただし
                              並行させるには **機能ごとに別セッション**が要る。1 つの
                              セッションから起動した subagent は Rule 2 に弾かれる）
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
- `harness/quality/` — セキュリティ・デザインの最低ラインと、レビューの判断基準
  （`review-rubric.md`）を定める文書
- `harness/tests/` — ハーネス自身の決定論ロジックの pytest（CI の `harness-selftest` ジョブ）
- `harness/procedures/` — フェーズ固有の長い手順（オンデマンド読み込み。コンテキスト予算の対象外）
- `harness/CLAIMS.md` — **主張と証跡の対応表。** 「何をブロックすると主張するか」と
  「それを実証しているテスト」の対応。CI の項目 P が表と実体の drift を機械的に見張る
- `harness/STACK_PACK.md` — スタック固有の標準を外部プラグインとして接続するための仕様
- `VERSION` / `CHANGELOG.md`（リポジトリルート）— ハーネスの版と変更履歴。CI の項目 Q が、
  ハーネス本体を触ったコミットで CHANGELOG が更新されていることを要求する
- `pyrightconfig.json`（リポジトリルート）— 型チェッカ（Pyright / VS Code の Pylance）向けの設定。
  `hooks` は `sys.path` を実行時に足して `path_utils` を読むため、`extraPaths` を宣言しないと
  エディタ上で「インポートを解決できません」が出て、そこから型不明のエラーが大量に派生する
  （実測 210 件）。実行には一切影響しない

## 品質保証（セキュリティ・デザイン）

外部Skillの有無で品質が変わらないよう、また実装者が自分で自分を通さないよう、多層構造にしています。詳細は `CONVENTIONS.md` 10 節。

1. `harness/quality/security-baseline.md` / `design-baseline.md` — 何もインストールしなくても
   常に効く最低ライン。該当フェーズで各 subagent が都度読む。
2. Claude Code 標準搭載の `security-review` / `code-review` skill — `integrator` と
   `feature-builder` が必須ステップとして実行する。
2.5. `gate-reviewer` subagent — 実装者とは別コンテキストで動く独立レビューア。
   `state: TESTED` の前に契約準拠・テスト十分性を審査する。判断基準は
   `harness/quality/review-rubric.md` だけで、verdict は深刻度の集計から機械的に決まる
   （Blocker が 1 件以上なら NO-GO）。レビューアは `Write`/`Edit` を持たない。
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
状態遷移の妥当性チェック・**検証受領書ゲート**・統合の受領書ゲート・**危険操作フロア**の
12 個を Claude Code の SessionStart / PreToolUse / PostToolUse / Stop / SubagentStop hooks で
強制しています。Bash 経由の間接的な書き込みは、静的検知でブロックしたうえ、すり抜けた場合も
**実行後の内容ハッシュ比較で検出して巻き戻します**。AI の自己申告には頼っていません。

強制レイヤ自身が壊れていないかは、セッション開始時に
`harness/hooks/session_start_healthcheck.py` が自己診断し、異常があれば警告と
`PROGRESS.md` の表示で知らせます（Hook が起動に失敗すると Claude Code はそれを「通過」として
扱うため、黙って無効化されることを防ぐ）。手動で確認するには:

```
python3 harness/hooks/session_start_healthcheck.py < /dev/null
```

## テストを実際に走らせたことの強制（検証受領書）

`shared-kernel.yaml` / `contract.yaml` の `verification:` にテスト・ビルド・型チェック・Lint の
コマンドを**宣言**すると、`run_verification.py` がそれを**解釈せずに実行**し、結果を
`status.yaml` の `verification_receipt` に記録します。`state: TESTED` にできるのは、
受領書の全コマンドが成功していて、かつ受領書の `commit` が現在の HEAD と一致するときだけです
（Rule 10）。**ハーネスはコマンドの中身を知らない**ので、どんな技術スタックでも成立します。
詳細は `CONVENTIONS.md` 12 節・`HARNESS_GUIDE.md` 14 節。

同じ仕組みを統合フェーズにも適用したのが `run_integration_verification.py`（Rule 11）です。
`04-integration/integration.machine.yaml` の `verification:` に assembly の検証コマンドを、
`interface_coverage[]` に `interfaces[]` の各エッジを検証する結合テストの識別子を宣言すると、
実行後に受領書が記録され、全エッジがカバーされ受領書が HEAD と一致するまで各機能の
`status.yaml` を `state: INTEGRATED` にできません。`check_interfaces.py`（下記）が契約同士の
静的な整合しか見ないのに対し、こちらは実装同士を実際に繋いだ結合テストの結果を見ます。

## 契約と要件の機械検証

```
python3 harness/scripts/check_interfaces.py             [--app <app-id>]   # 機能間の入出力の食い違い
python3 harness/scripts/check_traceability.py           [--app <app-id>]   # 要件 → 機能 → テスト
python3 harness/scripts/check_integration_traceability.py [--app <app-id>] # interfaces[] → 結合テスト
```

1つ目は `interfaces[]` の両端の JSON Schema を突合し、並行実装した機能同士の食い違いを
**統合前に**検出します。2つ目は MUST 要件の取りこぼしと、受入基準に対応するテストの不在を
検出します。3つ目は `interfaces[]` の全エッジが `04-integration/integration.machine.yaml` の
`interface_coverage[]` に対応づけられているか（宣言レベル）を検出します。いずれも
CI（項目 J・K・N）でも再検証されます。

## 補助スクリプトの引数体系（不揃いなので注意）

| スクリプト | 呼び出し方 |
|---|---|
| `check_interfaces.py` / `check_traceability.py` / `check_integration_traceability.py` / `render_progress.py` / `run_verification.py` | `--app <app-id>`（`run_verification.py` は `--feature` も必須） |
| `run_integration_verification.py` | `--app <app-id>`（`--feature` は取らない。統合はどの機能にも属さないため） |
| `validate_yaml.py` | **位置引数 2 つ**: `<yaml ファイル> <schema ファイル>`（`--app` は取らない） |
| `validate_status_transition.py` | **位置引数 2 つ**: `<old_state> <new_state>`（`--status-file` は任意） |
| `ci_check.py` | `--base` / `--head` / `--branch`（いずれも任意。省略時は自動解決） |
| `diff_architecture.py` | 新旧の `architecture.machine.yaml` を位置引数で 2 つ |

## CI 連携

`.github/workflows/harness-checks.yml` が、上記 Hook のうち Claude Code のセッション外
（人間が直接 `git commit` する等）でもすり抜けられては困るものを、push/PR のたびに
`harness/scripts/ci_check.py` でサーバーサイド再検証します。詳細は `HARNESS_GUIDE.md` 12節。

## 既知の制約

- 状態遷移チェックは `state_history[]` が正しく追記されていることを前提にします
  （`BLOCKED` からの復帰時に履歴を遡って直前の状態を復元するため）。
- Bash 経由の書き込みは、静的検知（未然防止）ですり抜けた場合でも事後検証
  （実行後の `git status` 比較）で検出・巻き戻しされますが、書き込み自体を阻止はできません。
- CI 上でアプリのテストを実際に実行する構成にはしていません（検証は各機能の worktree で
  `run_verification.py` が実行し、CI はその受領書を検証します）。Claude Code を経由しない
  編集では受領書を偽造できます。
- `gate-reviewer` の審査結果（`status.yaml` の `review`）は記録であって証明ではありません。
- **アプリ非依存性は異なる 2 スタックで実証済みです**。Python CLI（`apps/md-todo-cli`）と
  TypeScript の HTTP API + フロントエンド（`apps/bookmark-vault`）の両方で、要件 → 設計 →
  実装 → 統合 → `INTEGRATED` までを完走し、`verification:` の宣言・JUnit XML の突合・
  `interfaces[]` の JSON Schema 突合が機能することを確認しました。ただし
  `interfaces[]` の JSON Schema 突合は、機能内部の DI インターフェースの形状差や HTTP
  エンコーディングの不一致のような、契約の JSON Schema には現れない差異までは捕まえられない
  ことも実地で判明しています（Rule 11 はこの隙間を実行結果ベースで塞ぎます）。
- 並行実装は「機能ごとに別セッションを立てられる」ことが前提です。1 つのセッションから
  `feature-builder` を subagent として複数起動して並行させることはできません
  （Rule 2 がセッションの worktree ルートを見るため）。

これらは実際にアプリを作ってみながら、必要に応じて拡張してください。
