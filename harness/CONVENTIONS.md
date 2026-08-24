# CONVENTIONS.md — ハーネス規約の単一情報源

> **凍結中（2026-08-23〜）。変更はユーザーの明示的許可が必要。節の新設は項目Oが拒否（15節固定）。**

このファイルは `harness/` 配下の hooks / scripts / templates / schemas と、
`.claude/agents` / `.claude/skills` のすべてが前提とする命名規則・パス規則・状態機械の定義です。
これらを変更する場合は、必ずこのファイルを先に更新してから、参照している他のファイルを揃えてください。

対象読者は「機械（hooks/scripts/agents/skills）」と「ハーネスを保守する人間」です。
個々のアプリの進捗を見るための文書ではありません（それは `apps/<app-name>/PROGRESS.md` です）。

## 1. ディレクトリ構造

```
/.claude/                     ← 実効設定。git worktree で全 worktree に自動複製される
  settings.json               ← hooks 登録
  agents/*.md                 ← ハーネス共通 subagent
  skills/*/SKILL.md           ← ハーネス共通 skill
/harness/                     ← ハーネス本体。書き込みガード対象（Rule 1）
  README.md / CONVENTIONS.md / CLAIMS.md
  hooks/ templates/ schemas/ scripts/
  quality/                    ← セキュリティ・デザインの最低ライン（10節）
  procedures/                 ← フェーズ固有の長い手順（オンデマンド読み込み。15節）
/apps/<app-id>/                ← 生成物。init-app skill が都度生成する
  AUTONOMY.yaml               ← 自動化の度合い（9節）
  00-requirements/  requirements.md / requirements.machine.yaml / history/
  01-foundation/    shared-kernel.yaml  ← 全機能が依存する共有契約（10節）
  02-design/        design.md / architecture.machine.yaml / history/
                    features/<feature-id>.contract.yaml  ← 契約ドラフト（設計時点）
  03-features/<feature-id>/    ← 1 機能 = 1 プロジェクト = 1 git worktree
    SPEC.md                    ← 人間向け機能仕様（このディレクトリ内で完結）
    contract.yaml / status.yaml / src/ / tests/
    .claude/                   ← この機能限定の追加 skill/agent（任意）
  04-integration/   integration.md / integration.machine.yaml / assembly/
  PROGRESS.md                  ← 人間向け進捗ダッシュボード。**自動生成・手書き禁止**
  STATE.machine.yaml           ← 機械向け全体状態。**自動生成・手書き禁止**
  .worktrees/<feature-id>/     ← git worktree の実体（.gitignore 対象）
```

機械可読ファイルはすべて `harness/schemas/*.schema.json` で検証される（CI 項目 A）。

## 2. ID・命名規則

- `app-id`: kebab-case。例 `hello-world-todo`
- `feature-id`: kebab-case。同一 app 内で一意。例 `user-signup`, `todo-list-api`
- 仕様変更で機能を置き換える場合、新 ID は `<old-id>-v2`, `<old-id>-v3`... とする

## 3. ブランチ命名規則

| 用途 | 形式 | 例 |
|---|---|---|
| アプリ雛形作成 | `app/<app-id>/bootstrap` | `app/hello-world-todo/bootstrap` |
| 機能実装 | `feature/<app-id>/<feature-id>` | `feature/hello-world-todo/todo-list-api` |
| ハーネス保守 | `harness/<topic>` | `harness/fix-progress-renderer` |
| 統合作業（任意） | `integration/<app-id>` | `integration/hello-world-todo` |

## 4. worktree パス規則

```
apps/<app-id>/.worktrees/<feature-id>/
```
git worktree の実体は同一リポジトリの追跡ファイルをそのままチェックアウトするため、
このパスの中にも `apps/<app-id>/03-features/<feature-id>/` という同一の相対パスが現れます。
セッションの cwd は worktree ルート（上のパス）でも機能ディレクトリでも構いません。Rule 2 が見るのは
cwd ではなく worktree ルートの basename です（`new-feature-worktree` skill が起動コマンドを案内します）。

## 5. 状態機械（`status.yaml` の `state` フィールド）

```
NOT_STARTED → CONTRACT_DRAFTED → CONTRACT_APPROVED → IN_PROGRESS → IMPLEMENTED → TESTED → INTEGRATED
```

追加で許容する状態:
- `BLOCKED`: 作業が止まっている（`blockers[]` に理由を記録）
- `SUPERSEDED`: 仕様変更で後継の feature-id に置き換えられた（`superseded_by` に後継 ID）

状態遷移は `PreToolUse` フック（7節 Rule 9）が機械的に強制する。

- 直線状態は1段階前進のみ許可。後退・複数段階の飛び越しは拒否する。
- `INTEGRATED`/`SUPERSEDED` は終端状態で、そこからの変更は一切拒否する。
- `BLOCKED` へはどの非終端状態からでも入れる（「一時停止」として扱う）。
  **`BLOCKED` から復帰するときは `state_history[]` を時刻順に遡って直前の非 `BLOCKED` 状態を
  復元し、そこからの遷移として妥当性を判定する**（履歴に非 `BLOCKED` のエントリが 1 つも無い
  場合のみ、判定不能として通す）。`state_history[]` を正しく追記することが判定の前提。
- `SUPERSEDED` への遷移はどの非終端状態からでも許可する。

判定の実体は `path_utils.validate_status_transition`（`BLOCKED` からの復帰は
`resolve_effective_previous_state` が履歴を遡る）。`validate_status_transition.py` は同じ
ロジックを呼ぶ、人間/CI向けの手動確認 CLI。

## 6. 「独立機能」の設計原則

`architecture.machine.yaml` の `features[]` は互いへの `depends_on` を持ちません。
機能間のつながりは `interfaces[]`（`producer_feature` の `producer_output` を
`consumer_feature` の `consumer_input` として渡す、という宣言）でのみ表現します。

全機能が共通で依存してよいものは `01-foundation/shared-kernel.yaml`
（DDD でいう Shared Kernel）に限定し、機能ごとの `contract.yaml` から参照します。

**`shared-kernel.yaml` の `common_types` を `$ref` で参照しないこと。** 共通型は各
`contract.yaml` に**インライン展開**して書き、`common_types` は「何を共通とみなすか」の
単一の情報源として人間が参照するために使う（理由は `HARNESS_GUIDE.md` 15節）。

**`interfaces[]` の両端は機械検証されます。** `producer_output` の実体は producer の
`contract.yaml` の `outputs[].json_schema`、`consumer_input` の実体は consumer の
`inputs[].json_schema` です。`harness/scripts/check_interfaces.py`（CI の項目 J）が、
端点の実在・型の一致・必須項目の包含関係・`enum` の包含関係を突合します。

```
python3 harness/scripts/check_interfaces.py [--app <app-id>]
```

## 7. Hooks が強制する 12 ルール（実装は `harness/hooks/` 配下）

各ルールの経緯・実証・設計意図は `HARNESS_GUIDE.md` 5節にある。ここには規範だけを置く。

1. **ハーネス非侵襲性**: `harness/**`・`.claude/**`・`.github/**`（いずれもリポジトリルート直下。
   `.github/workflows/` も「ハーネス本体」の一部として保護する）への書き込みは、現在のブランチが
   `harness/` プレフィックスでない限り拒否する。ただし `.claude/settings.local.json`
   （gitignore 対象の個人ローカル設定）はチームに共有されないため対象外とする。
2. **担当外ガード**: `apps/<app-id>/03-features/<feature-id>/**`（`status.yaml` を除く）への書き込みは、
   現在の worktree ルートの basename が `<feature-id>` と一致しない限り拒否する。
3. **契約凍結**: `contract.yaml` への書き込みは、対応する `status.yaml` の `state` が
   `NOT_STARTED` または `CONTRACT_DRAFTED` でない限り拒否する。凍結が始まる
   `CONTRACT_APPROVED` への遷移も、`contract.yaml` に `approved_by`/`approved_at` が
   無ければ拒否する（9節）。凍結後に見つかった契約の穴は `open_issues[]` への**追記のみ**許す
   （既存項目の書き換え・削除と Bash 経由は不可）。
4. **進捗自動再生成**: `status.yaml` が更新されたら `render_progress.py` を実行し、
   `PROGRESS.md` / `STATE.machine.yaml` を再生成する（非ブロッキング）。
5. **必須 Skill の充足ゲート**: `apps/<app-id>/03-features/<feature-id>/src/**` への書き込みは、
   `shared-kernel.yaml` の `required_skills[]` のうち `applies_to`（省略時は全機能）にこの
   `feature-id` を含むものについて、各 `plugin_ref` が `.claude/settings.json`/
   `.claude/settings.local.json` の `enabledPlugins` に存在しない限り拒否する（10節）。
6. **上位文書ガード**: feature 用 worktree（パスに `.worktrees/` を含む）から
   `apps/<app-id>/00-requirements/**`・`01-foundation/**`・`02-design/**` への書き込みは常に拒否する
   （メインの worktree からの `solution-architect`/`diff-design` の書き込みには適用されない）。
7. **承認ゲート**: `architecture.machine.yaml` を `status: APPROVED` にする書き込みは、その
   `based_on_requirements_version` が `requirements.machine.yaml` の現在の `version` と一致しない限り
   拒否する（11節）。加えて要件・設計とも、`status: APPROVED` と同じ書き込みで
   `approved_by`/`approved_at` が埋まっていなければ拒否する（9節）。
8. **フェーズ節目のコミット強制**（`Stop`/`SubagentStop` フックで実行、`PreToolUse` ではない）:
   `status.yaml` / `requirements.machine.yaml` / `architecture.machine.yaml` のいずれかに
   未コミットの変更（`git status --porcelain --untracked-files=all` で検出。新規追加も含む）が
   残ったまま応答を終えようとした場合、停止を拒否する。無限ループ回避のため、
   `stop_hook_active` が真の場合は判定をスキップして通す。
9. **状態遷移の妥当性チェック**: `status.yaml` への書き込みは、書き込み後の `state` が
   書き込み前の `state` から見て妥当な遷移（5節）でない限り拒否する。判定ロジックは
   `path_utils.validate_status_transition`。
10. **検証受領書ゲート**: `status.yaml` を `state: TESTED` にする書き込みは、
    `verification_receipt` が存在し、`verification:` で宣言されたすべてのコマンドが
    `exit_code: 0` であり、`commit` が現在の `HEAD` と一致しない限り拒否する（12節）。
    加えて、`verification_receipt` そのものを Edit/Write で書き換えることも常に拒否する。
11. **統合の受領書ゲート**: `status.yaml` を `state: INTEGRATED` にする書き込みは、
    `04-integration/integration.machine.yaml` に `interfaces[]` の全エッジをカバーする
    `interface_coverage[]` と有効な受領書（`run_integration_verification.py` 生成）が無い限り
    拒否する（13節）。

12. **危険操作フロア**: 次の操作は、他の Rule が許可していても**無条件に拒否する**
    （Rule 12 は他 Rule と独立に判定し、deny が勝つ）。確認を求めるのではなく拒否する——
    `AUTONOMOUS` では AI 自身が確認に答えてしまうため。
    - D-1: リポジトリルート外への再帰削除（`rm -r` / `find ... -delete`）。`..` を含む綴り・
      未展開の変数・`/`・`.`・先頭ワイルドカードは、解決するまでもなく拒否する。
    - D-2: 秘密ファイルの読み取り（`.env`/`.env.*`/`*.pem`/`*.key`/`*id_rsa*`/`*id_ed25519*`/
      `.ssh/**`/`.aws/**`/`.npmrc`/`.netrc`）。`.env.example`・`.env.sample` 等の見本は除外。
      `Read` ツールと Bash の読み出しコマンドの両方を対象にする。
    - D-3: 履歴の破壊（`git push --force`/`--force-with-lease`、`git reset --hard`、
      `git clean -fdx`、`git filter-branch`）。
    - D-4: 検証のスキップ（`git commit --no-verify`/`-n`/`--no-gpg-sign`）。
    - D-5: 外部送信（`curl`/`wget`/`nc` による POST/PUT/アップロード、および paste 系ホストへの到達）。
    - D-6: `sudo`/`doas`/`su` を伴う任意コマンド。

    **この Rule にバイパス用の環境変数は用意しない。** 誤検知は検知ロジック自体を修正して
    対応する（判定は `path_utils.detect_dangerous_bash_operation` / `detect_dangerous_read`）。

**判定対象のパスは、`.worktrees/` を通る場合その worktree を基準に読み替えてから Rule に掛けます**
（`path_utils.resolve_worktree_scope`）。書き込み先は**それが属するリポジトリのルート**を基準に
相対化してから Rule に掛けます（`path_utils.resolve_write_target`）。リポジトリの外は対象外です。

構造化ツール呼び出しに加え、`Bash` 経由の間接的な書き込み（検知範囲は
`path_utils.extract_bash_candidate_paths`）も Rule 1・2・3・5・6 でブロックします。
Rule 7・9・10 は書き込み前後の内容比較に依存し Bash では判定できないため、`status.yaml`・
`requirements.machine.yaml`・`architecture.machine.yaml` への Bash 経由の書き込みは**一律拒否**します。
検知は静的検知（実行前）と事後検証（`post_tool_use_guard.py`。内容ハッシュ比較で巻き戻す）の
2 段構えです。

**強制レイヤ自身の健全性は起動時に自己診断します。** `SessionStart` フック
（`session_start_healthcheck.py`）が、hooks の import 可否・`path_utils` の主要関数・
`.claude/settings.json` の Hook 登録を検査し、異常があれば警告とセッションへの追加コンテキストで
知らせます。`PROGRESS.md` の先頭にも同じ診断結果が出ます。`PreToolUse` ガードは想定外の例外を
握りつぶさず **fail-closed**（exit 2 ＋ 理由）で止まります——判定できない状態で通すと、
全ルールが黙って無効化されたまま作業が続くためです（`HARNESS_GUIDE.md` 5節）。

**この Bash 検知にバイパス用の環境変数は意図的に用意しません**（`HARNESS_UNLOCK=1` は Rule 1
専用の既存の緊急避難路として残します）。誤検知を見つけたら、検知ロジック自体を修正して
対応してください。

## 8. 緊急避難

Rule 1（ハーネス非侵襲性）を意図的に解除したい場合のみ、環境変数 `HARNESS_UNLOCK=1` を設定して
ください。解除時は stderr に警告が出ます。恒常的な運用には使わないでください。

## 9. 自動化の度合い (`AUTONOMY.yaml`)

`apps/<app-id>/AUTONOMY.yaml`（`schemas/autonomy.schema.json`）が、このアプリでどこまで
人間の承認を必須とするかを定める単一の情報源です。全 subagent は作業開始時にこれを読み、
`mode` に応じて振る舞いを変えます。

- `MANUAL`: 各フェーズの節目（要件承認・設計承認・各機能の完了・統合完了）ごとに毎回人間に確認する
- `SUPERVISED`（デフォルト）: それ以降は妥当と判断すれば自動で進めるが、技術スタック選定など
  重要な決定は都度提示する
- `AUTONOMOUS`: 明らかにブロッキングな疑問がない限り、最後まで確認なしで進める

**モードに関わらず、要件定義 (`00-requirements`) の承認だけは常に人間の明示的な承認が必須です。**

「本当に人間が承認したか」を Hook が決定論的に強制することはできません（`HARNESS_GUIDE.md` 10節）。
機械的に強制するのは次の 2 点だけです。

1. `requirements.schema.json` / `architecture.schema.json` は `status: APPROVED` のとき
   `approved_by` / `approved_at` が非 null であることを強制し、Rule 7 が書き込みの時点でも
   同じ条件を課す。
2. `render_progress.py` が生成する `PROGRESS.md` に、現在の `autonomy_mode` と、機能ごとの
   検証受領書（12節）・レビュー結果（10節 Layer 1.6）の要約を常に表示する。

**承認の書き込み（`status: APPROVED` / `approved_by` / `approved_at`）は、要件・設計とも
subagent ではなく親セッションが行います**（設計は `AUTONOMOUS` の場合に限り subagent が
自分の役割名で承認してよい）。`approved_by` には承認した人間の識別子を書きます。

モードを変更する場合は、無断で緩めず必ずユーザーに確認してください。

## 10. 品質保証の多層構造（セキュリティ・デザイン・レビュー）

「専門的な外部 Skill が入っていない環境では品質が保証されない」状態と、「実装者が自分で自分を
通す」ことを避けるため、品質保証は次の多層構造にします（設計意図は `HARNESS_GUIDE.md` 9節）。

**Layer 1（必須・ハーネス内蔵・外部依存ゼロ）**
- `harness/quality/security-baseline.md`: `feature-builder` の実装時・`solution-architect` の
  技術選定時・`integrator` の結線時に必ず読む、最低限のセキュリティ原則。
- `harness/quality/design-baseline.md`: UI を持つ機能の実装時・結線時に必ず読む、
  最低限のデザイン原則。
- どちらも「何もインストールしなくても常に効く」ことが前提。該当フェーズで初めて Read される。

**Layer 1.5（準必須・Claude Code 標準搭載の bundled skill）**
- `integrator` は統合前に `security-review` と `code-review` を、`feature-builder` は `TESTED`
  にする前に `code-review` を実行する。Skill が見つからない場合はユーザーに報告し手動レビューを
  促す（Layer 1 は常に効くため最低ラインは保たれる）。

**Layer 1.6（必須・独立レビューア `gate-reviewer`）**

`state: TESTED` の前に、実装者とは**別のコンテキスト**で動く `gate-reviewer` subagent が
審査する（設計意図は `HARNESS_GUIDE.md` 16節）。

- 判断基準は `harness/quality/review-rubric.md` **だけ**。rubric 外の指摘は無効。
- **verdict は深刻度の集計から機械的に決まる**（`Blocker` ≥ 1 → `NO-GO`、0 → `GO`）。
- 1 ラウンドの指摘は最大 5 件。3 ラウンド `NO-GO` が続いたら人間へエスカレーションする。
- **レビューアに `Write`/`Edit` を与えない。** 直すのは実装者の責務。
- 結果は `status.yaml` の `review` に記録する。**記録であって証明ではない**
  （実行の裏付けを持たないため、機械的ゲートにはしない）。

**Layer 2（`required_skills[]`）**

- 必須とする Skill は `01-foundation/shared-kernel.yaml` の `required_skills[]` に
  `{ name, plugin_ref, purpose }`（＋任意で `kind`／`applies_to`）で宣言する。標準搭載の
  `security-review`/`code-review` は対象外。
- ここに列挙された Skill は**実装フェーズの必須要件**になる。`src/**` への書き込みのたびに
  Rule 5（7節）が `enabledPlugins` と突き合わせ、欠けていれば実装をブロックする。
- `feature-builder` は `shared-kernel.yaml` を書き換えられない（Rule 6）ため、実装中に
  独断で追加することはできない。必要になったら実装を止めて `diff-design` でやり直す。
- `required_skills[]` が空の場合、Layer 1 のみで進める。

## 11. 上位文書優先の原則（要件 → 設計 → 機能）

重要度は 要件定義 (`00-requirements`) > 設計 (`02-design`) > 機能契約 (`03-features/*/contract.yaml`)
の順であり、下位の文書は常に上位の文書と整合していなければなりません。
`shared-kernel.yaml` と `architecture.machine.yaml` は、どちらかを先に確定させる逐次作業ではなく、
両者を行き来しながら収束させる反復作業として扱います。

**要件が変わったら、要件定義書を必ず新しいバージョンとして書き直す。** 下位の文書だけを直して
上位の文書を古いまま放置することを許さない。旧版は `history/` に退避し、旧 `requirements.machine.yaml`
は `status: SUPERSEDED`・`superseded_by: <新バージョン>` にする。

**Rule 7（7節）が、`based_on_requirements_version` と `requirements.machine.yaml` の現在の
`version` が一致しない限り、architecture を `status: APPROVED` にすることを機械的に拒否する。**

改訂を実行する手順は `diff-design` skill が持ちます（15節）。

## 12. 検証コマンドの宣言・実行・受領書（Rule 10）

「テストを書いて通した」を AI の自己申告に委ねないための仕組み。**ハーネスは「どのコマンドを
走らせるか」を規定せず、アプリ側の宣言を解釈せずに実行し、終了コードだけを見る**。
設計意図は `HARNESS_GUIDE.md` 14節。

**宣言**（`shared-kernel.yaml` に全機能共通、`contract.yaml` でキー単位に上書き）:

```yaml
verification:
  working_dir:       "src"     # 機能ディレクトリからの相対。既定は "."
  test_command:      "pytest -q --junitxml=../.verify/junit.xml"   # 必須
  build_command:     "python -m build"                             # 以下は任意
  typecheck_command: "mypy src"
  lint_command:      "ruff check --select E,F,I ."
  junit_xml:         "../.verify/junit.xml"
  max_skip_ratio:    0.2       # 既定 0.2
```

- `test_command` が宣言されていなければ、どの機能も `TESTED` にできない。宣言するのは
  `solution-architect` の責務であり、**実装フェーズでは回復不能**（Rule 6 により
  `feature-builder` は `shared-kernel.yaml` を書き換えられない）。設計フェーズで必ず埋めること。
- 任意のキーは宣言した場合のみ検証対象になる。

**実行**: `python3 harness/scripts/run_verification.py --app <app-id> --feature <feature-id>`
が宣言されたコマンドを順に起動し、`status.yaml` の `verification_receipt` に結果と実行時の
HEAD を書き込む。**受領書は手書きできない**（Rule 10 が Edit/Write による変更を拒否する）。
検証コマンドが生成するファイルは**必ず `.gitignore` に入れる**こと（コミットすると受領書より
後に機能ディレクトリが変更されたことになり CI の項目 I が不合格になる）。

**ゲート（Rule 10）**: `state: TESTED` への書き込みは、受領書があり、宣言された全コマンドが
`exit_code: 0` で、`commit` が現在の HEAD と一致する場合のみ許可する。
**`commit` の一致条件が本質**——これが無ければ実装を書き換えた後も過去の成功記録を使い回せる。
CI（項目 I）は等価条件で再検証する（受領書の `commit` が HEAD の祖先 ＋ そのコミット以降に
機能ディレクトリが未変更）。Rule 10 と Rule 8 の噛み合わせは `HARNESS_GUIDE.md` 14節。

**JUnit XML（任意）**: `junit_xml` を宣言すると、空振り（`tests="0"`）・失敗・スキップ率が
言語非依存に機械判定される。出力できない技術なら宣言しなければよい。

## 13. 要件 → 機能 → テスト のトレーサビリティ

`functional_requirements[].id`（`^FR-[0-9]+$`）を軸に、上位文書優先の原則（11節）を
機械検証可能な形で貫く。ID 体系はスキーマで固定済みなので、判定はスタック非依存。

```
requirements.machine.yaml      architecture.machine.yaml       contract.yaml
functional_requirements[].id ← features[].covers_requirements  test_strategy.coverage[]
                                                                 .requirement
                                                                 .acceptance_criterion
                                                                 .test_ids → JUnit XML と突合
```

- `features[]` の **`covers_requirements` は必須**（この機能が満たす FR の ID）。
- `contract.yaml` の `test_strategy` は文字列ではなく、`approach` と
  `coverage[]`（`requirement`/`acceptance_criterion`/`test_ids`）を持つオブジェクト。
- `test_ids` の**書式はハーネスが規定しない**。JUnit XML の `<testcase>` の
  `classname`/`name`/`file` から組み立てられる代表的な形のいずれかと一致すれば通る。

| どこで | 何を判定するか |
|---|---|
| `check_traceability.py`（CI 項目 K） | MUST 要件の取りこぼし／存在しない FR ID／受入基準の取りこぼし |
| `run_verification.py` | 宣言された識別子が JUnit XML に実在し成功したか（受領書の `traceability`） |
| Rule 10 | 受領書の `traceability` に `missing`/`failed` が残っていれば `TESTED` を拒否 |

```
python3 harness/scripts/check_traceability.py [--app <app-id>]
```

同じ考え方を `interfaces[]` に適用したのが Rule 11（CI 項目 N）。

**受入基準の分担ルール**: 1 つの受入基準が複数機能にまたがってよいが、その FR を覆うと宣言した
全機能の `coverage[]` を**合算して、`acceptance_criteria` を全て覆う**こと（項目 K が検証する）。

## 14. スタックパック（スタック固有の標準の外部化）

特定の技術スタックをハーネス本体に規定することは制約違反として扱う。一方で「Python ではこう書く」
という実務知見が無ければ実装の質は担保できない。この 2 つは**スタック固有の標準を外部プラグイン
（スタックパック）として接続する**ことで両立する。ハーネスが規定するのは**パックの形式**だけで、
**中身は規定しない**（設計意図は `HARNESS_GUIDE.md` 17節）。

強制機構は既存のもので足りる。`solution-architect` が `shared-kernel.yaml` の `required_skills[]`
に `kind: stack-pack` として記録し、**Rule 5** が `src/**` への最初の書き込み時に有効化状況を
機械検証してブロックし、**Rule 6** が `feature-builder` による `shared-kernel.yaml` の書き換えを禁じる。

パックが満たすべきインターフェース（命名規約・必須の記載項目 5 つ・優先関係）は
`harness/STACK_PACK.md` に定義する。要点:

- **`harness/quality/*.md` のベースラインが常に優先する。** パックは追加であって置き換えではない。
- `gate-reviewer` はパックを**読まない**（レビューの軸は `review-rubric.md` だけに固定する）。
- `required_skills[]` が空でも Layer 1 と Rule 10 は効く。パックは**上積み**であって下限ではない。

## 15. コンテキスト予算

agent プロンプトと、その agent が読み込む `CONVENTIONS.md` の節は、**そのセッションで常時
効き続けるコンテキスト**である。「気をつける」では守れないので、`ci_check.py` の項目 L が
機械的に上限を強制する。

**`CONVENTIONS.md` を全文読む agent はいない。** 各 agent は自分のフェーズに要る節だけを
下記のマーカーで宣言し、`print_conventions.py` で読み込む（宣言が `none` の agent は読まない。
その場合でも本文中に「7節 Rule 7」のような**出典の注記**は書いてよい）。

| 対象 | 上限 |
|---|---|
| `harness/CONVENTIONS.md` | 36,000 バイト |
| `.claude/agents/*.md` 各ファイル | 12,000 バイト |
| 1 セッションの常時コスト＝ agent プロンプト ＋ その agent が読む節（最も重い agent で判定） | 46,000 バイト |

上限に当たったら、まず**説明・背景・設計意図を `HARNESS_GUIDE.md` へ移す**こと。
`harness/quality/*.md`・`harness/STACK_PACK.md`・`harness/procedures/*.md`・`harness/CLAIMS.md`
のように**該当フェーズで初めて読まれる**文書は常時コストではないため、この予算の対象外とする。

### 何をどこに書くか（規範と手順の分担）

**同じことを 2 箇所に書かない。** 片方だけ直して drift する（実例: F-048）。

| 書くもの | 置き場所 |
|---|---|
| Hook/CI が機械的に強制する規範 | **`CONVENTIONS.md` だけ。** agent は節番号で参照する |
| 機械では強制できない規範 | `CONVENTIONS.md` に**宣言だけ**置き、指示は agent プロンプトに書く |
| フェーズ固有の手順 | **agent/skill と `harness/procedures/*.md` だけ。** ここには書かない |

agent が実行時に規約の本文を要るときは、必要な節だけを読み込む:

```
python3 harness/scripts/print_conventions.py --sections 6,9,13
```

各 agent プロンプトの冒頭には、読み込む節を宣言するマーカーを置く（項目 L がこれを見て常時
コストを計算する。`none` は「CONVENTIONS.md を読まない」の意）:

```
<!-- context-budget: conventions-sections=6,9,13 -->
```

この分担は `ci_check.py` の項目 M が機械的に見張る（`CONVENTIONS.md` と agent/skill プロンプトの
間に、ほぼ同一の段落があれば不合格）。検出されたら、規範なら `CONVENTIONS.md` に残して参照へ、
手順なら agent/skill に一本化して `CONVENTIONS.md` 側を削ること。

