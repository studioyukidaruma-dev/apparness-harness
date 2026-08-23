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
/harness/                     ← ハーネス本体。アプリ作成中は書き込みガード対象（Rule 1）
  README.md / CONVENTIONS.md
  hooks/                      ← .claude/settings.json から呼ばれる実行スクリプト
  templates/                  ← 各種ドキュメントのひな形
  schemas/                    ← JSON Schema（machine-readable ファイルの検証用）
  scripts/                    ← hooks/skills から呼ばれる決定論ロジック
  quality/                    ← セキュリティ・デザインの最低ラインを定めるベースライン文書（10節）
/apps/<app-id>/                ← 生成物。init-app skill が都度生成する
  AUTONOMY.yaml               ← 自動化の度合い（schemas/autonomy.schema.json。9節参照）
  00-requirements/
    requirements.md            ← 人間向け要件定義書
    requirements.machine.yaml  ← 機械向け構造化要件（schemas/requirements.schema.json）
    history/                   ← 旧バージョンの requirements.machine.yaml/.md を退避（11節）
  01-foundation/
    shared-kernel.yaml         ← 全機能が依存する共有契約（型・認証方式・DB方針・required_skills など。10節）
  02-design/
    design.md                  ← 人間向け設計書
    architecture.machine.yaml  ← 機械向け設計（schemas/architecture.schema.json）
    features/<feature-id>.contract.yaml  ← 各機能の I/O 契約ドラフト（設計時点）
    history/                   ← 旧バージョンの architecture.machine.yaml を退避（11節）
  03-features/<feature-id>/    ← 1 機能 = 1 プロジェクト = 1 git worktree
    SPEC.md                    ← 人間向け機能仕様（このディレクトリ内で完結）
    contract.yaml              ← 機械向け I/O 契約（schemas/feature-contract.schema.json）
    status.yaml                ← 機械向け進捗状態（schemas/status.schema.json）
    src/ tests/
    .claude/                   ← この機能限定の追加 skill/agent（任意、harness 本体を汚さない）
  04-integration/
    integration.md             ← 組み上げ記録
    assembly/                  ← 組み上げコード
  PROGRESS.md                  ← 人間向け進捗ダッシュボード。**自動生成・手書き禁止**
  STATE.machine.yaml           ← 機械向け全体状態。**自動生成・手書き禁止**
  .worktrees/<feature-id>/     ← git worktree の実体（.gitignore 対象）
```

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
- `BLOCKED`: 何らかの理由で作業が止まっている（`blockers[]` に理由を記録）
- `SUPERSEDED`: 仕様変更により後継の feature-id に置き換えられた（`superseded_by` に後継 ID を記録）

状態遷移は基本的に前進のみを許可し、`PreToolUse` フック（7節 Rule 9）が機械的に強制します
（例: `NOT_STARTED` からいきなり `INTEGRATED` にする、`CONTRACT_APPROVED` から `NOT_STARTED` に
後退させる、といった書き込みは拒否されます）。

- 直線状態（上記の矢印の並び）は1段階前進のみ許可。後退・複数段階の飛び越しは拒否する。
- `INTEGRATED`/`SUPERSEDED` は終端状態で、そこからの変更は一切拒否する。
- `BLOCKED` へはどの非終端状態からでも自由に入れる（「一時停止」として扱う）。
  **`BLOCKED` から復帰するときは `state_history[]` を時刻順に遡って直前の非 `BLOCKED` 状態を
  復元し、そこからの遷移として妥当性を判定する。** これにより「一度 `BLOCKED` にしてから
  好きな状態へ飛ぶ」という抜け穴は塞がれている（履歴に非 `BLOCKED` のエントリが 1 つも無い
  場合のみ、判定不能として通す）。`state_history[]` を正しく追記することが、この判定の前提。
- `SUPERSEDED` への遷移はどの非終端状態からでも許可する（`diff-design` による置き換えはいつでも
  起こりうるため）。

判定の実体は `harness/hooks/lib/path_utils.py` の `validate_status_transition`
（`BLOCKED` からの復帰は `resolve_effective_previous_state` が履歴を遡る）。
`validate_status_transition.py` は同じロジックを呼ぶ、人間/CI向けの手動確認 CLI
（`--status-file` に `status.yaml` を渡すと履歴も踏まえて判定する）。

## 6. 「独立機能」の設計原則

`architecture.machine.yaml` の `features[]` は互いへの `depends_on` を持ちません。
機能間のつながりは `interfaces[]`（`producer_feature` の `producer_output` を
`consumer_feature` の `consumer_input` として渡す、という宣言）でのみ表現します。
これにより「入出力さえわかれば内部を知らなくてよい」という独立性を構造的に強制します。

全機能が共通で依存してよいものは `01-foundation/shared-kernel.yaml`
（DDD でいう Shared Kernel）に限定し、機能ごとの `contract.yaml` から参照します。

**`shared-kernel.yaml` の `common_types` を `$ref` で参照しないこと。**
`check_interfaces.py` は JSON Schema の `$ref` を解決しないため、参照で書くと端点の突合が
効かなくなる（共通型に集約したつもりが機械検証を失う）。共通型は各 `contract.yaml` に
**インライン展開**して書き、`common_types` は「何を共通とみなすか」の単一の情報源として
人間が参照するために使う。

**`interfaces[]` の両端は機械検証されます。** `producer_output` の実体は producer の
`contract.yaml` の `outputs[].json_schema`、`consumer_input` の実体は consumer の
`inputs[].json_schema` です。`harness/scripts/check_interfaces.py`（CI の項目 J）が、
端点の実在・型の一致・必須項目の包含関係（producer が出さない／出すとは限らない項目を
consumer が `required` にしていないか）・`enum` の包含関係を突合します。JSON Schema の
構造比較はスタック非依存なので、**並行実装中の機能間の食い違いを統合前に検出できます**。

```
python3 harness/scripts/check_interfaces.py [--app <app-id>]
```

## 7. Hooks が強制する 11 ルール（実装は `harness/hooks/` 配下）

1. **ハーネス非侵襲性**: `harness/**`・`.claude/**`・`.github/**`（いずれもリポジトリルート直下。
   `.github/workflows/` は CI 設定であり、これも「ハーネス本体」の一部として保護する）への書き込みは、
   現在のブランチが `harness/` プレフィックスでない限り拒否する。ただし `.claude/settings.local.json`
   （gitignore 対象の個人ローカル設定。`/plugin install <name> --scope local` 等が書き込む）は
   チームに共有されないため対象外とする（Skill を自分の環境でだけ使うなら `--scope local`。
   `--scope project` は `.claude/settings.json` を書き換え、10節 Layer 2 の前提を壊す）。
2. **担当外ガード**: `apps/<app-id>/03-features/<feature-id>/**`（`status.yaml` を除く）への書き込みは、
   現在の worktree ルートの basename が `<feature-id>` と一致しない限り拒否する。
3. **契約凍結**: `contract.yaml` への書き込みは、対応する `status.yaml` の `state` が
   `NOT_STARTED` または `CONTRACT_DRAFTED` でない限り拒否する。凍結が始まる
   `CONTRACT_APPROVED` への遷移も、`contract.yaml` に `approved_by`/`approved_at` が
   無ければ拒否する（凍結の根拠を機械的に確かめるため。9節）。凍結後に見つかった契約の穴は
   `open_issues[]` への**追記のみ**許す（既存項目の書き換え・削除と Bash 経由は不可）。
4. **進捗自動再生成**: `status.yaml` が更新されたら `render_progress.py` を実行し、
   `PROGRESS.md` / `STATE.machine.yaml` を再生成する（非ブロッキング）。
5. **必須 Skill の充足ゲート**: `apps/<app-id>/03-features/<feature-id>/src/**` への書き込みは、
   `shared-kernel.yaml` の `required_skills[]` のうち `applies_to`（省略時は全機能）にこの
   `feature-id` を含むものについて、各 `plugin_ref` が `.claude/settings.json`/
   `.claude/settings.local.json` の `enabledPlugins` に存在しない限り拒否する（10節）。設計で
   使うと決めた Skill を欠いたまま実装が進むことを防ぐ。
6. **上位文書ガード**: feature 用 worktree（パスに `.worktrees/` を含む）から
   `apps/<app-id>/00-requirements/**`・`01-foundation/**`・`02-design/**` への書き込みは常に拒否する。
   実装中に変更が必要だと気づいたら、実装を止めて `diff-design` skill での再設計に回すこと
   （このルールはメインの worktree からの
   `solution-architect`/`diff-design` の書き込みには適用されない）。
7. **承認ゲート**: `architecture.machine.yaml` を `status: APPROVED` にする書き込みは、その
   `based_on_requirements_version` が `requirements.machine.yaml` の現在の `version` と一致しない限り
   拒否する（11節。要件が変更されたのに設計が追従していない状態で承認させない）。加えて要件・設計とも、
   `status: APPROVED` と同じ書き込みで `approved_by`/`approved_at` が埋まっていなければ拒否する
   （9節。`status` だけ先に APPROVED にした中間状態を塞ぐ）。
8. **フェーズ節目のコミット強制**（`Stop`/`SubagentStop` フックで実行、`PreToolUse` ではない）:
   `status.yaml` / `requirements.machine.yaml` / `architecture.machine.yaml` のいずれかに
   未コミットの変更（`git status --porcelain --untracked-files=all` で検出。新規追加もこの
   コミット漏れの対象に含める）が残ったまま応答を終えようとした場合、停止を拒否する。
   無限ループ回避のため、`stop_hook_active` が真の場合は判定をスキップして通す。
9. **状態遷移の妥当性チェック**: `status.yaml` への書き込みは、書き込み後の `state` が
   書き込み前の `state` から見て妥当な遷移でない限り拒否する（5節）。`NOT_STARTED` からいきなり
   `INTEGRATED` にする、`CONTRACT_APPROVED` から `NOT_STARTED` に後退させる、といった書き込みを
   機械的に防ぐ。判定ロジックは `path_utils.validate_status_transition`。

10. **検証受領書ゲート**: `status.yaml` を `state: TESTED` にする書き込みは、
    `verification_receipt` が存在し、`verification:` で宣言されたすべてのコマンドが
    `exit_code: 0` であり、`commit` が現在の `HEAD` と一致しない限り拒否する（12節）。
    加えて、`verification_receipt` そのものを Edit/Write で書き換えることも常に拒否する
    （受領書は `run_verification.py` が実際にコマンドを実行して生成する記録であり、
    手書きできてしまえば「実行した」という主張の裏付けにならない）。

11. **統合の受領書ゲート**: `status.yaml` を `state: INTEGRATED` にする書き込みは、
    `04-integration/integration.machine.yaml` に `interfaces[]` の全エッジをカバーする
    `interface_coverage[]` と有効な受領書（`run_integration_verification.py` 生成）が無い限り
    拒否する（13節。項目 J をすり抜ける実装差異を実行結果で塞ぐ）。

**判定対象のパスは、`.worktrees/` を通る場合その worktree を基準に読み替えてから Rule に掛けます**
（`path_utils.resolve_worktree_scope`）。読み替えないと `^apps/.../03-features/...` にアンカーされた
Rule 1・2・3・5・9・10 がまとめて素通りします（経緯と実証は `HARNESS_GUIDE.md` 5節）。

書き込み先は**それが属するリポジトリのルート**を基準に相対化してから Rule に掛けます
（`path_utils.resolve_write_target`）。worktree は隔離機構ではなく、隔離しているのは Hook です
（`HARNESS_GUIDE.md` 8節）。リポジトリの外（`/tmp` 等）は対象外です。

構造化ツール呼び出しに加え、`Bash` 経由の間接的な書き込み（`sed -i`/`cp`/`mv`/`tee`/リダイレクト等。
検知範囲は `path_utils.extract_bash_candidate_paths`）も Rule 1・2・3・5・6 でブロックします。Rule 7・9・10 は書き込み前後の内容比較に依存し Bash では判定できないため、
`status.yaml`・`requirements.machine.yaml`・`architecture.machine.yaml` への**Bash 経由の書き込みは
一律拒否**し、構造化ツールを要求します（ハーネス自身のスクリプト経由の書き込みは、コマンド文字列に
パスが現れないため掛かりません）。

検知は 2 段構えです。**静的検知**（`extract_bash_candidate_paths`）は未然に止めるが
変数展開されたパス等の検知漏れが原理的に残り、**事後検証**（`post_tool_use_guard.py`）が
実行前後のスナップショットを**内容のハッシュ**で比較して確実に捕まえ、違反は実行直前の内容へ
巻き戻します。静的検知は削除しません（仕組みと経緯は `HARNESS_GUIDE.md` 5節・11節）。

**この Bash 検知にバイパス用の環境変数は意図的に用意しません。** ブロックされた際に AI 自身が
環境変数を設定して解除できてしまうと、決定論的強制という目的そのものが崩れるためです
（`HARNESS_UNLOCK=1` は Rule 1 専用の既存の緊急避難路として残します）。誤検知を見つけたら、
検知ロジック自体を修正して対応してください。

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
これはアプリの目的そのものを AI だけで確定させないための、ハーネス全体の固定ポリシーです。

「本当に人間が承認したか」という意味論的な判定を Hook が完全に決定論的に強制することはできません
（Hook が見られるのはファイルパスと内容だけで、対話の意味までは判定できないため）。そのため、
機械的に強制できる範囲は次の 2 点に限定しています。過信せず、`PROGRESS.md` の
`autonomy_mode` 表示で人間が随時状況を確認できることを最終的な担保としてください。

1. `requirements.schema.json` / `architecture.schema.json` は `status: APPROVED` のとき
   `approved_by` / `approved_at` が非 null であることをスキーマレベルで強制し、Rule 7 が
   書き込みの時点でも同じ条件を課す（空欄のまま無断で承認済みにすることを防ぐ）。
2. `render_progress.py` が生成する `PROGRESS.md` に、現在の `autonomy_mode` と、機能ごとの
   検証受領書（12節）・レビュー結果（10節 Layer 1.6）の要約を常に表示する。

**承認の書き込み（`status: APPROVED` / `approved_by` / `approved_at`）は、要件・設計とも
subagent ではなく親セッションが行います。** subagent にはユーザーの承認が親エージェントからの
伝聞としてしか届かず、人間が承認したことを確かめようがないためです（設計は `AUTONOMOUS` の場合に
限り subagent が自分の役割名で承認してよい）。`approved_by` には承認した人間の識別子を書きます。

モードを変更する場合は、無断で緩めず必ずユーザーに確認してください。

## 10. 品質保証の多層構造（セキュリティ・デザイン・レビュー）

「専門的な外部Skillが入っていない環境では品質が保証されない」という状態を避けるため、
また「実装者が自分で自分を通す」ことを避けるため、品質保証は次の多層構造にします。

**Layer 1（必須・ハーネス内蔵・外部依存ゼロ）**
- `harness/quality/security-baseline.md`: `feature-builder` の実装時・`solution-architect` の
  技術選定時・`integrator` の結線時に必ず読む、最低限のセキュリティ原則。
- `harness/quality/design-baseline.md`: UI を持つ機能を `feature-builder` が実装するとき・
  `integrator` が結線するときに必ず読む、最低限のデザイン原則。
- どちらも「何もインストールしなくても常に効く」ことが前提。CONVENTIONS.md 本体には内容を
  埋め込まず、該当フェーズで初めて Read される（コンテキストは必要なときだけ消費する）。

**Layer 1.5（準必須・Claude Code 標準搭載の bundled skill）**
- `security-review` / `code-review` は Claude Code の bundled skill で、追加インストールなしに
  基本的に利用できる。`integrator` は統合前に両方を、`feature-builder` は `TESTED` にする前に
  `code-review` を実行する。
- 実行を試みて Skill が見つからない場合は、その旨をユーザーに報告し手動レビューを促す
  （Layer 1 は常に効くため、これが失敗しても最低ラインは保たれる）。

**Layer 1.6（必須・独立レビューア `gate-reviewer`）**

`state: TESTED` の前に、実装者とは**別のコンテキスト**で動く `gate-reviewer` subagent が
審査する（自己レビューには作者バイアスが残るため。設計意図は `HARNESS_GUIDE.md` 16節）。

- 判断基準は `harness/quality/review-rubric.md` **だけ**。rubric 外の指摘は無効。
  軸はすべてスタック非依存（スタック固有の標準は外部スタックパック（14節）の領分）。
- **verdict は深刻度の集計から機械的に決まる**（`Blocker` ≥ 1 → `NO-GO`、0 → `GO`）。
- 1 ラウンドの指摘は最大 5 件。3 ラウンド `NO-GO` が続いたら人間へエスカレーションする。
- **レビューアに `Write`/`Edit` を与えない。** 直すのは実装者の責務。
- 結果は `status.yaml` の `review` に記録する。**記録であって証明ではない**
  （受領書（12節）と違い実行の裏付けを持たないため、機械的ゲートにはしない）。

**Layer 2（`required_skills[]` — 設計で決めたら実装フェーズの必須要件になる）**

技術スタックは設計フェーズで確定させ、それに反した実装を許さない、という原則を
プラグイン系 Skill にも適用します。「あれば使う、無ければ黙ってスキップ」という
完全オプションの層は置きません。

- 必須とする Skill は `01-foundation/shared-kernel.yaml` の `required_skills[]` に
  `{ name, plugin_ref, purpose }`（＋任意で `kind`／特定機能だけに絞る `applies_to`）で宣言する。標準搭載の
  `security-review`/`code-review` は対象外（選定手順は `solution-architect` が持つ。15節）。
- ここに列挙された Skill は**実装フェーズの必須要件**になる。`src/**` への書き込みのたびに
  Rule 5（7節）が `enabledPlugins` と突き合わせ、欠けていれば実装をブロックする。
  担当者は `/plugin install <plugin_ref> --scope local` を実行してから再開する。
- `feature-builder` は `shared-kernel.yaml` を書き換えられない（Rule 6）ため、実装中に
  独断で追加することはできない。必要になったら実装を止めて `diff-design` で設計からやり直す。
- `required_skills[]` が空の場合、Layer 1 のみで進める。

## 11. 上位文書優先の原則（要件 → 設計 → 機能）

重要度は 要件定義 (`00-requirements`) > 設計 (`02-design`) > 機能契約 (`03-features/*/contract.yaml`)
の順であり、下位の文書は常に上位の文書と整合していなければなりません。`01-foundation/shared-kernel.yaml`
と `02-design/architecture.machine.yaml` は、機能一覧が固まって初めて共通部分が見えてくることが
多いため、どちらかを先に確定させる逐次作業ではなく、両者を行き来しながら収束させる反復作業として
扱います（`solution-architect` のプロンプト参照）。

**要件が変わったら、要件定義書を必ず新しいバージョンとして書き直す。** 下位の文書だけを直して
上位の文書を古いまま放置することを許さない。旧版は `history/` に退避し、旧 `requirements.machine.yaml`
は `status: SUPERSEDED`・`superseded_by: <新バージョン>` にする。

**Rule 7（7節）が、`based_on_requirements_version` と `requirements.machine.yaml` の現在の
`version` が一致しない限り、architecture を `status: APPROVED` にすることを機械的に拒否する。**
これにより「要件は変わったのに設計が追従していない」状態のまま先に進むことを構造的に防ぐ。

改訂を実行する手順は `diff-design` skill が持ちます（15節）。

## 12. 検証コマンドの宣言・実行・受領書（Rule 10）

「テストを書いて通した」を AI の自己申告に委ねないための仕組み。**ハーネスは「どのコマンドを
走らせるか」を規定せず、アプリ側の宣言を解釈せずに実行し、終了コードだけを見る**（規定 prescribe は
しない。要求 require と実行 execute だけを行う）。これによりアプリ非依存性を保ったまま
実行ベースの検証が成立する。設計意図の説明は `HARNESS_GUIDE.md` 14節。

**宣言**（`01-foundation/shared-kernel.yaml` に全機能共通、`contract.yaml` でキー単位に上書き）:

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
  `solution-architect` の責務（技術スタックを決めるのと同じ場所で検証手順も決める）。
  **これは実装フェーズでは回復不能である**——`feature-builder` は Rule 6 により
  `shared-kernel.yaml` を書き換えられないため、宣言し忘れた場合は実装を止めて
  `diff-design` で設計からやり直すしかない。設計フェーズで必ず埋めること。
- 任意のキーは宣言した場合のみ検証対象になる。

**実行**: `python3 harness/scripts/run_verification.py --app <app-id> --feature <feature-id>`
が宣言されたコマンドを順に起動し、`status.yaml` の `verification_receipt` に結果と実行時の
HEAD を書き込む。**受領書は手書きできない**（Rule 10 が Edit/Write による変更を拒否する）。

検証コマンドが生成するファイル（JUnit XML・各種キャッシュ）は**必ず `.gitignore` に入れる**こと。
コミットしてしまうと、受領書より後に機能ディレクトリが変更されたことになり CI の項目 I が
不合格になる。`run_verification.py` は生成物を検出したら警告する（何が生成物かはスタックごとに
違うため、ハーネスは判定せず報告だけする）。

**Rule 10 と Rule 8 は順序を守って初めて噛み合います**（詳細は `HARNESS_GUIDE.md` 14節）。
実行する側の手順は `feature-builder` のプロンプトが持ちます（15節）。
検証が失敗した受領書もコミットして構いません（`TESTED` への昇格は Rule 10 が別途止めます）。

**ゲート（Rule 10）**: `state: TESTED` への書き込みは、受領書があり、宣言された全コマンドが
`exit_code: 0` で、`commit` が現在の HEAD と一致する場合のみ許可する。
**`commit` の一致条件が本質**——これが無ければ実装を書き換えた後も過去の成功記録を使い回せる。
CI（`ci_check.py` 項目 I）は HEAD が先に進んでいるため等価条件で再検証する
（受領書の `commit` が HEAD の祖先 ＋ そのコミット以降に機能ディレクトリが未変更）。

**JUnit XML（任意）**: `junit_xml` を宣言すると、空振り（`tests="0"`）・失敗・スキップ率が
言語非依存に機械判定される。出力できない技術なら宣言しなければよく、終了コードによる
ゲートはそのまま効き続ける。

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
| `check_traceability.py`（CI 項目 K） | MUST 要件の取りこぼし／存在しない FR ID の参照／覆うと宣言した要件が `coverage[]` に無い／受入基準の取りこぼし |
| `run_verification.py` → 受領書の `traceability` | 宣言されたテスト識別子が JUnit XML に実在し、成功したか |
| Rule 10 | 受領書の `traceability` に `missing`/`failed` が残っていれば `TESTED` を拒否 |

```
python3 harness/scripts/check_traceability.py [--app <app-id>]
```

同じ考え方を `interfaces[]` に適用したのが Rule 11（`integration.machine.yaml` の
`interface_coverage[]`・CI 項目 N）。

**受入基準の分担ルール**: 1 つの受入基準が複数機能にまたがってよいが、その FR を覆うと宣言した
全機能の `coverage[]` を**合算して、`acceptance_criteria` を全て覆う**こと（項目 K が検証する）。

## 14. スタックパック（スタック固有の標準の外部化）

特定の技術スタックをハーネス本体に規定することは制約違反として扱う。一方で
「Python ではこう書く」という実務知見が無ければ実装の質は担保できない。この 2 つは
**スタック固有の標準を外部プラグイン（スタックパック）として接続する**ことで両立する。
ハーネスが規定するのは**パックの形式**だけで、**中身は規定しない**。

強制機構は既存のもので足りる。`solution-architect` が `shared-kernel.yaml` の
`required_skills[]` に `kind: stack-pack` として記録し、**Rule 5** が `src/**` への最初の
書き込み時に有効化状況を機械検証してブロックし、**Rule 6** が `feature-builder` による
`shared-kernel.yaml` の書き換えを禁じる。

パックが満たすべきインターフェース（命名規約・必須の記載項目 5 つ・優先関係）は
`harness/STACK_PACK.md` に定義する。要点:

- **`harness/quality/*.md` のベースラインが常に優先する。** パックは追加であって置き換えではない。
- `gate-reviewer` はパックを**読まない**（レビューの軸は `review-rubric.md` だけに固定する）。
  パックは**実装時の指針**であって**通過判定の基準ではない**。
- `required_skills[]` が空でも Layer 1 と Rule 10 は効く。パックは**上積み**であって下限ではない。

## 15. コンテキスト予算

agent プロンプトと、その agent が読み込む `CONVENTIONS.md` の節は、**そのセッションで常時
効き続けるコンテキスト**である。ここが太ると、実際の作業に使える文脈と注意力が削られる。
「気をつける」では守れないので、`ci_check.py` の項目 L が機械的に上限を強制する。

**`CONVENTIONS.md` を全文読む agent はいない。** 各 agent は自分のフェーズに要る節だけを
下記のマーカーで宣言し、`print_conventions.py` で読み込む（宣言が `none` の agent は読まない。
その場合でも本文中に「7節 Rule 7」のような**出典の注記**は書いてよい——読みに行けという指示ではなく、
規約を保守する人間がたどるための手がかりである）。

| 対象 | 上限 |
|---|---|
| `harness/CONVENTIONS.md` | 36,000 バイト |
| `.claude/agents/*.md` 各ファイル | 12,000 バイト |
| 1 セッションの常時コスト＝ agent プロンプト ＋ その agent が読む節（最も重い agent で判定） | 46,000 バイト |

上限は「ここまでなら使ってよい」という許可ではなく、**超えるときに意識的な判断を強制する**
ための線です。上限に当たったら、まず**説明・背景・設計意図を `HARNESS_GUIDE.md` へ移す**こと
（上限の数値を上げるのは、移せるものを移し切ってから）。
`harness/quality/*.md` や `harness/STACK_PACK.md` のように**該当フェーズで初めて読まれる**
文書は常時コストではないため、この予算の対象外とする。

### 何をどこに書くか（規範と手順の分担）

**同じことを 2 箇所に書かない。** 片方だけ直して drift する（実例: F-048。詳細は
`DOGFOODING-LOG.md`）。

| 書くもの | 置き場所 |
|---|---|
| Hook/CI が機械的に強制する規範 | **`CONVENTIONS.md` だけ。** agent は「7節 Rule 7」のように節番号で参照する。違反すれば Hook が止め、そのエラーメッセージが直し方を示す |
| 機械では強制できない規範（要件承認は人間必須、独立機能への分割など） | `CONVENTIONS.md` に**宣言だけ**置き、従わせるための指示は agent プロンプトに書く |
| フェーズ固有の手順（誰が何をどの順で実行するか） | **その手順を実行する agent/skill だけ。** `CONVENTIONS.md` には書かない |

agent が実行時に規約の本文を要るときは、必要な節だけを読み込む:

```
python3 harness/scripts/print_conventions.py --sections 6,9,13
```

各 agent プロンプトの冒頭には、読み込む節を宣言するマーカーを置く（項目 L がこれを見て、
その agent の実際の常時コストを計算する。`none` は「CONVENTIONS.md を読まない」の意）:

```
<!-- context-budget: conventions-sections=6,9,13 -->
```

この分担は `ci_check.py` の項目 M が機械的に見張る（`CONVENTIONS.md` と agent/skill プロンプトの
間に、ほぼ同一の段落があれば不合格）。検出されたら、規範なら `CONVENTIONS.md` に残して参照へ、
手順なら agent/skill に一本化して `CONVENTIONS.md` 側を削ること。
