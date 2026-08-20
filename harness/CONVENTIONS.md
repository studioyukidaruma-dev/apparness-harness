# CONVENTIONS.md — ハーネス規約の単一情報源

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
担当者はこのさらに深い階層（`apps/<app-id>/.worktrees/<feature-id>/apps/<app-id>/03-features/<feature-id>/`）を
cwd としてセッションを開始してください（`new-feature-worktree` skill が起動コマンドを案内します）。

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
- `BLOCKED` への／からの遷移はどの非終端状態からでも／どの状態へでも自由に許可する
  （どのレベルで止まっていたかによらない「一時停止」として扱う。**既知の簡略化**として、
  `BLOCKED` を経由すれば直線状態の飛び越しチェックをすり抜けられる。厳密な検証には
  `state_history[]` を遡って直前の実質的な状態を復元する必要があるが、v1 ではそこまでは行わない）。
- `SUPERSEDED` への遷移はどの非終端状態からでも許可する（`diff-design` による置き換えはいつでも
  起こりうるため）。

判定の実体は `harness/hooks/lib/path_utils.py` の `validate_status_transition`。
`harness/scripts/validate_status_transition.py` は同じロジックを呼ぶ、人間/CI向けの手動確認 CLI。

## 6. 「独立機能」の設計原則

`architecture.machine.yaml` の `features[]` は互いへの `depends_on` を持ちません。
機能間のつながりは `interfaces[]`（`producer_feature` の `producer_output` を
`consumer_feature` の `consumer_input` として渡す、という宣言）でのみ表現します。
これにより「入出力さえわかれば内部を知らなくてよい」という独立性を構造的に強制します。

全機能が共通で依存してよいものは `01-foundation/shared-kernel.yaml`
（DDD でいう Shared Kernel）に限定し、機能ごとの `contract.yaml` から参照します。

## 7. Hooks が強制する 9 ルール（詳細は `harness/hooks/pre_tool_use_guard.py`・`stop_commit_guard.py` 参照）

1. **ハーネス非侵襲性**: `harness/**`・`.claude/**`・`.github/**`（いずれもリポジトリルート直下。
   `.github/workflows/` は CI 設定であり、これも「ハーネス本体」の一部として保護する）への書き込みは、
   現在のブランチが `harness/` プレフィックスでない限り拒否する。ただし `.claude/settings.local.json`
   （gitignore 対象の個人ローカル設定。`/plugin install <name> --scope local` 等が書き込む）は
   チームに共有されないため対象外とする。Skill を「プロジェクト全体に強制する」のではなく
   「自分の環境でだけ使えるようにする」場合はこのファイル（`--scope local`）を使うこと。
   `--scope project` は `.claude/settings.json`（git管理・チーム共有）を書き換えるため、
   Layer 2（10節）が想定する「アプリごとに選べる」という前提を壊す。
2. **担当外ガード**: `apps/<app-id>/03-features/<feature-id>/**`（`status.yaml` を除く）への書き込みは、
   現在の worktree ルートの basename が `<feature-id>` と一致しない限り拒否する。
3. **契約凍結**: `contract.yaml` への書き込みは、対応する `status.yaml` の `state` が
   `NOT_STARTED` または `CONTRACT_DRAFTED` でない限り拒否する。
4. **進捗自動再生成**: `status.yaml` が更新されたら `harness/scripts/render_progress.py` を実行し、
   `PROGRESS.md` / `STATE.machine.yaml` を再生成する（非ブロッキング）。
5. **必須 Skill の充足ゲート**: `apps/<app-id>/03-features/<feature-id>/src/**` への書き込みは、
   `shared-kernel.yaml` の `required_skills[]` に列挙された各 `plugin_ref` が
   `.claude/settings.json`/`.claude/settings.local.json` の `enabledPlugins` に存在しない限り拒否する
   （10節）。設計で使うと決めた Skill を欠いたまま実装が進むことを防ぐ。
6. **上位文書ガード**: feature 用 worktree（パスに `.worktrees/` を含む）から
   `apps/<app-id>/00-requirements/**`・`01-foundation/**`・`02-design/**` への書き込みは常に拒否する。
   feature-builder は要件・共有基盤・設計を変更できない。実装中に変更が必要だと気づいたら、
   実装を止めて `diff-design` skill での再設計に回すこと（このルールはメインの worktree からの
   `solution-architect`/`diff-design` の書き込みには適用されない）。
7. **要件↔設計の整合性ゲート**: `architecture.machine.yaml` を `status: APPROVED` にする書き込みは、
   その `based_on_requirements_version` が `requirements.machine.yaml` の現在の `version` と
   一致しない限り拒否する（11節）。要件が変更されたのに設計が追従していない状態で承認させない。
8. **フェーズ節目のコミット強制**（`Stop`/`SubagentStop` フックで実行、`PreToolUse` ではない）:
   `status.yaml` / `requirements.machine.yaml` / `architecture.machine.yaml` のいずれかに
   未コミットの変更（`git status --porcelain --untracked-files=all` で検出。新規追加もこの
   コミット漏れの対象に含める）が残ったまま応答を終えようとした場合、停止を拒否する。
   各 subagent のプロンプトは「状態を進めるたびに `git add -A && git commit` する」と指示しているが、
   実地テストでコミット漏れが実際に発生したため、決定論的に強制する。無限ループ回避のため、
   Claude Code が渡す `stop_hook_active` が真の場合は判定をスキップして通す。
9. **状態遷移の妥当性チェック**: `status.yaml` への書き込みは、書き込み後の `state` が
   書き込み前の `state` から見て妥当な遷移でない限り拒否する（5節）。`NOT_STARTED` からいきなり
   `INTEGRATED` にする、`CONTRACT_APPROVED` から `NOT_STARTED` に後退させる、といった書き込みを
   機械的に防ぐ。判定ロジックは `path_utils.validate_status_transition`。

Edit/Write/MultiEdit/NotebookEdit という構造化ツール呼び出しに加え、`Bash` 経由の間接的な書き込み
（`sed -i` / `cp` / `mv` / `tee` / リダイレクト等、`path_utils.extract_bash_candidate_paths` が
検知できる範囲）についても、Rule 1・2・3・5・6（`tool_name`/`tool_input` を要求しない Rule のみ。
Rule 7・9 は Edit/Write/MultiEdit の書き込み前後内容比較に依存するため対象外）に違反する場合は
同様にブロックします（v1）。

検知は `shlex`（標準ライブラリ、依存ゼロ）でコマンド文字列をクォートを尊重してトークン化した上で
判定します。クォートで囲われた文字列は1トークンとして扱われるため、`echo "a >> b"` のような
「`>>` を含む文字列を扱っているだけのコマンド」を演算子と誤認識することはありません
（正規表現の単純な文字列マッチだった旧実装ではこれが誤検知していたことを実地で確認して修正した）。
それでも変数展開されたパス（例: `>> "$VAR"`）等の**検知漏れ（false negative）**は残りますが、これは
「完全な防御ではなく、意図しない/不注意な間接書き込みを止める」という目的上許容します。

トークン化の前段では、クォート・行継続（末尾 `\`）・ヒアドキュメント本体を考慮しながら、
「コマンドの区切りとして扱ってよい改行」だけを `;` に正規化してからセグメント分割します
（`path_utils._normalize_bash_newlines`）。Claude Code の Bash ツールは複数行スクリプトを
1回の `command` 文字列として渡すことが多く、`shlex` は改行を単なる空白として読み捨てるため、
この正規化を入れないと「改行だけで区切られた複数コマンド」が1つの巨大なセグメントに融合し、
`cp`/`mv`/`tee`/`sed -i` がセグメント先頭以外（例: 2行目以降）にある場合に検知漏れが起きます
（実地で `mkdir -p apps/.../src\ncp a b apps/.../src/` という2行スクリプトの `cp` が
すり抜けることを確認して修正した）。ヒアドキュメント本体・終端子行の直前の改行は区切りに
変換しない（本体中の文字列がコマンドの先頭トークンと誤認識されないようにするため）。

**この Bash 検知にバイパス用の環境変数は意図的に用意しません。** ブロックされた際に AI 自身が
環境変数を設定して解除できてしまうと、決定論的強制という目的そのものが崩れるためです
（`HARNESS_UNLOCK=1` は Rule 1 専用の既存の緊急避難路であり、意図的な例外として残していますが、
Bash 検知全体を無効化するような汎用の解除路は設けません）。誤検知を発見した場合は、検知ロジック
（`path_utils.extract_bash_candidate_paths` 等）自体を修正して対応してください。

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
   `approved_by` / `approved_at` が非 null であることをスキーマレベルで強制する
   （空欄のまま無断で承認済みにすることを防ぐ）。
2. `render_progress.py` が生成する `PROGRESS.md` に、現在の `autonomy_mode` を常に表示する。

モードを変更する場合は、無断で緩めず必ずユーザーに確認してください。

## 10. 品質保証の二層構造（セキュリティ・デザイン）

「専門的な外部Skillが入っていない環境では品質が保証されない」という状態を避けるため、
セキュリティとデザインの品質保証は次の二層構造にします。

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

**Layer 2（`required_skills[]` — 設計で決めたら実装フェーズの必須要件になる）**

技術スタック（どの言語・フレームワーク・ライブラリを使うか）は設計フェーズで確定させ、それに
反した実装を許さない、という原則をプラグイン系 Skill にも適用します。「あれば使う、無くても
黙ってスキップ」という完全オプションの層は置きません。

- `solution-architect` が、デザイン系（`frontend-design` 等）・専門的なルール集
  （`find-skills` 経由で見つかる `vercel-react-best-practices` 等）を使うと決めたら、
  必ず `01-foundation/shared-kernel.yaml` の `required_skills[]` に
  `{ name, plugin_ref, purpose }` として記録する（`AskUserQuestion` で確認してから追加する）。
  Claude Code 標準搭載の `security-review`/`code-review`（Layer 1.5）はここに含めない。
- ここに列挙された Skill は、以後**実装フェーズの必須要件**になる。`feature-builder` が
  `src/**` に実装を書き込もうとするたびに、Rule 5（7節）が各 `plugin_ref` の有効化状況
  （`.claude/settings.json`/`.claude/settings.local.json` の `enabledPlugins`）を機械的に検証し、
  一つでも欠けていれば実装そのものをブロックする。担当者は指示された
  `/plugin install <plugin_ref> --scope local` でインストールしてから再開する。
- `feature-builder` は `shared-kernel.yaml` を書き換えられない（Rule 6）。実装中に
  「このSkillが必要そうだ」と気づいても独断で `required_skills[]` に追加することはできず、
  実装を止めてユーザーに報告し、`diff-design` skill で設計からやり直す。
- `required_skills[]` が空の場合、Layer 1 のみで進める。

## 11. 上位文書優先の原則（要件 → 設計 → 機能）

重要度は 要件定義 (`00-requirements`) > 設計 (`02-design`) > 機能契約 (`03-features/*/contract.yaml`)
の順であり、下位の文書は常に上位の文書と整合していなければなりません。`01-foundation/shared-kernel.yaml`
と `02-design/architecture.machine.yaml` は、機能一覧が固まって初めて共通部分が見えてくることが
多いため、どちらかを先に確定させる逐次作業ではなく、両者を行き来しながら収束させる反復作業として
扱います（`solution-architect` のプロンプト参照）。

**要件が変わったら、要件定義書を必ず新しいバージョンとして書き直す。** `diff-design` skill は
以下の順で進める。下位の文書だけを直して上位の文書を古いまま放置することを許さない。

1. `requirements-analyst` が変更点をヒアリングする。
2. 変更前に、現在の `requirements.md`/`requirements.machine.yaml` を
   `00-requirements/history/requirements.v<旧バージョン>.{md,yaml}` として複製・退避する。
   旧 `requirements.machine.yaml` は `status: SUPERSEDED`、`superseded_by: <新バージョン>` にする。
3. `requirements.machine.yaml`/`.md` の `version` をインクリメントして新しい要件を書く。
   `status` は `APPROVED` に戻るまで `DRAFT`。
4. 要件が承認されたら、`solution-architect` が新しい `architecture.machine.yaml`
   （`design_version` をインクリメント、`based_on_requirements_version` を新しい要件 version に
   更新）を作る。旧 `architecture.machine.yaml` は `02-design/history/` に退避する。
5. **Rule 7（7節）が、`based_on_requirements_version` と `requirements.machine.yaml` の
   現在の `version` が一致しない限り、architecture を `status: APPROVED` にすることを機械的に拒否する。**
   これにより「要件は変わったのに設計が追従していない」状態のまま先に進むことを構造的に防ぐ。
6. `diff_architecture.py` で新旧 `architecture.machine.yaml` の機能差分を算出し、変更・追加された
   機能のみ新しい feature-id で `new-feature-worktree` を実行する。変更のない機能は再利用する。
