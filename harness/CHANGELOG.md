# CHANGELOG

このリポジトリ（apparness ハーネス本体）の変更履歴。形式は
[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に、版番号は
[セマンティック バージョニング](https://semver.org/lang/ja/) に従う。

版番号の意味（ハーネスにおける互換性の定義）:

- **MAJOR**: 既存アプリの `apps/<app-id>/**` が作り直しになる変更（ディレクトリ構造・状態機械・
  スキーマの後方非互換な変更）。
- **MINOR**: 新しい Rule・CI 項目・skill・agent の追加など、既存アプリはそのまま動くが
  強制の範囲が広がる変更。
- **PATCH**: 誤検知の修正・文言の修正・内部実装の整理など、強制の範囲を変えない変更。

現在の版は `harness/VERSION` にある。`PROGRESS.md` の先頭にも表示される。

## [Unreleased]

## [1.3.0] - 2026-09-13

### Added

- **Rule 13（人間向け文書の読み取り拒否）**: AI が読む文書と人間が読む文書を明確に分け、AI は実行物と
  `CONVENTIONS.md` だけから動作を判断する方針を Hook で強制する。人間向け文書（配布元では `docs/**` と
  `harness/docs/**`、導入先（`harness/install-manifest.json` がある）では `harness/docs/**` だけ）の
  読み取りを、`Read`/`NotebookRead`/`Grep` と Bash の読み出しコマンド（`cat`・`grep`・`sed` 等）について
  `harness/<topic>` ブランチ以外で拒否する。文書の保守には Edit の前の Read が要るため保守ブランチでは許可する。
  範囲を絞らない検索に混ざる行・作業ディレクトリ移動後の読み取り・スクリプト経由の読み取りは止めない
  （`CLAIMS.md` に残余として明記）。`.claude/settings.json` の `PreToolUse` の matcher に `Grep` を追加した。
  テストは `harness/tests/test_human_docs.py`。
- **CI 項目 R**: AI が読む文書（agent・skill・手順書・`CONVENTIONS.md`・`quality/`・`STACK_PACK.md`）から
  人間向け文書への参照を不合格にする。Hook はセッション外で効かないため、「そこを読めば分かる」という
  誘導の側も見張る。規範が対象を名指しする行は、同じ行に「人間向け」とあれば許可する。
- **`harness/docs/`（利用者向けの人間向け文書）**: `USAGE.md`（使い方）・`GUIDE.md`（しくみ）・
  `flow/harness-flow-plain.html`（図解）。`harness/` の中にあるので導入先にもコピーされる。
- **`docs/DESIGN.md`・`docs/DEVELOPMENT.md`（保守者向け）**: 設計意図・経緯・既知の制約と、改修・リリースの手順。

### Changed

- **文書を「読む人」で再編した。** ルートの `README.md` は概要と導入方法だけにし、詳細は `harness/docs/` に譲る。
  `docs/` にはアプリ作成に必要のない保守者向けの文書だけを残した。
  - `docs/HARNESS_GUIDE.md` を分割した。利用者向けの節は `harness/docs/GUIDE.md` へ、保守者向けの
    6節（コンテキスト消費マップ）・11節（既知の制約）・18節（規約から移した設計意図）と、各節に混ざっていた
    経緯・「なぜ」の説明は `docs/DESIGN.md` へ移した。
  - `docs/flow/harness-flow-plain.html` → `harness/docs/flow/harness-flow-plain.html`。
    技術版（監査・保守者向け）は `docs/flow/` に残した。
  - `docs/README.md` → `docs/INDEX.md`（README をルートの 1 つにするため）。過去の記録に出てくる古いパスとの対応表を置いた。
- **`CONVENTIONS.md` から人間向け文書への出典の注記をすべて外した。** AI が読む文書から人間向け文書への導線を
  なくし、常時コストも減らす。AI の作業に要る内容だった「Rule 10 と Rule 8 の順序」は 12節の本文に移した。
  15節の「`docs/` は人間専用」を、`docs/` と `harness/docs/` の両方を対象にした方針へ書き直し、
  1節のディレクトリ構造を更新した。7節は 13 ルールになった（節の数は 15 のまま）。
- `solution-architect` の「引数は `harness/README.md` 参照」を「`--help` で確認」に変えた。
- `session_start_healthcheck.py` の git 劣化警告に、ブランチが取れないと Rule 13 も拒否に倒れることを加えた。

### Fixed

- **ハーネスを更新すると、既存アプリの `PROGRESS.md` が古くなり CI 項目 G が不合格になることを案内していなかった。**
  `PROGRESS.md` はハーネスの版を表示するため、版が変わると再生成が要る。`install.py` は導入先にアプリがあるとき、
  次の手順に `render_progress.py --all` を出すようにした（インストーラは標準ライブラリだけで動かすため、
  PyYAML を要する再生成そのものは実行しない）。`harness/docs/USAGE.md` の更新手順にも追記した。

### Removed

- **`harness/README.md`**。人間向けの内容は `harness/docs/USAGE.md` に統合し、スクリプトの引数の説明は
  各スクリプトの `--help` を唯一の情報源にした。

## [1.2.1] - 2026-09-13

### Fixed

- **雛形を生成してコミットしたブランチを push すると、CI 項目 A が必ず不合格になっていた。**
  `new_app_scaffold.py` は要件（`requirements.machine.yaml`）と設計（`architecture.machine.yaml`）を
  空の `DRAFT` として生成し、`init-app` はそれをコミットするが、スキーマが `DRAFT` でも
  `summary` / `goals` / `functional_requirements` / `features` が空でないことを要求していた。
  空でないことの要求を `APPROVED` / `SUPERSEDED` のときだけに移した（承認時の要求は従来と同じ）。
  書いた機能要件・機能の書式（`id` の形式や受け入れ基準の有無など）は `DRAFT` でも従来どおり検証する。
  テストは `harness/tests/test_schema_draft.py`（雛形を実際に生成して項目 A を通す回帰テストを含む）。

## [1.2.0] - 2026-09-13

### Removed

- **`apps/equipment-lending` と `briefs/equipment-lending.brief.yaml` を削除した。**
  ハーネス改修中の動作確認用に作成したドッグフーディング用アプリで、継続開発の予定はない。
  関連する feature ブランチおよび worktree も削除した。`apps/` `briefs/` はどちらも
  `.gitkeep` のみを残し、生成物が存在しない状態に戻した。
- 一時的に `README.md` に書いていた git submodule + symlink による導入手順を削除した（未リリース）。
  実測で、①機能ごとの git worktree の中では submodule の中身が空になり `.claude/` と `harness/` の
  リンクが切れる、②実体のパス（`vendor/.../harness/...`）を指定すると Rule 1 の保護を
  すり抜けられる、の 2 点を確認したため。

### Added

- **コピー型インストーラ（`harness/scripts/install.py`）**: 別のプロジェクトへ `harness/`・
  `.claude/agents/`・`.claude/skills/`・`.github/workflows/harness-checks.yml` をコピーし、
  `.claude/settings.json` には Hook の登録だけを合成し、`.gitignore` に管理ブロックを足す。
  標準ライブラリのみで動く。導入した版とファイルの一覧を `harness/install-manifest.json` に
  記録し、再実行で更新する（上流で消えたファイルだけを削除し、導入先が自分で置いた agent・skill
  には触れない）。ハーネスが導入していない場所にある内容の異なるファイルは、`--force` が無い限り
  上書きせずに止まる。`--dry-run` あり。導入元に未リリースの変更（Unreleased の項目）があると警告する。
  テストは `harness/tests/test_install.py`。
- **リリースは git タグ（`v<版>`）で配布する。** 導入手順はタグを指定して取得する形にした。
- `README.md` に「他プロジェクトへの導入」節を追加した。

### Changed

- **`VERSION` / `CHANGELOG.md` をリポジトリ直下から `harness/` へ移した。** 導入先のプロジェクトが
  持つ同名ファイルと衝突させないため。ハーネスが導入先へ持ち込むものが `harness/`・`.claude/`・
  `.github/` にそろう。`ci_check.py`（項目 Q）・`render_progress.py`・関連文書の参照を更新した。

### Fixed

- **CI 項目 Q がリリースのコミットを誤って不合格にしていた。** リリースでは Unreleased を版の節へ
  移すので空になり、ハーネス本体の差分を含むと「Unreleased に項目が無い」で落ちていた。
  `harness/VERSION` が変更され、CHANGELOG にその版の `## [<版>]` 節があれば記録として認める。
  `install.py` で導入・更新したプロジェクトのコミットも同じ形になる。`harness/VERSION` と
  `harness/CHANGELOG.md` 自体の変更は「ハーネス本体の変更」に数えない。

## [1.1.0] - 2026-09-13

### Added

- **企画ブリーフ（`briefs/<app-id>.brief.yaml`）**: 要件定義の前に、目的・必要な機能・
  使ってほしい技術などを固定フォーマットに一度に書いて渡せるようにした。`new_brief.py` が
  記入用フォーマットを生成し、`check_brief.py` が書式（`schemas/brief.schema.json`）を検証して
  **未記入項目を `MUST` / `ASK` / `FREE` に分類して列挙**する。`init-app` は
  `briefs/<app-id>.brief.yaml` を自動で探し、あれば要件定義の出発点にし、無ければ従来どおり
  対話で決める。記入済みの項目は聞き直さず、空欄だけを対話で補う。項目名の綴り違いは黙って
  無視されず exit 1 で落ちる。`new_app_scaffold.py --brief` が入力の記録として
  `apps/<app-id>/00-requirements/brief.yaml` に取り込む。ブリーフは入力であって承認物ではなく、
  要件承認が人間必須である点は変わらない。

- **脆弱性走査の抑制機構（`apps/<app-id>/.vuln-ignore`）**: 上流に fix が無い検出を、
  **期限（`expires=YYYY-MM-DD`）と理由（`reason=`）を必須**として受容できるようにした。
  期限・理由の欠落、日付の書式違反、期限切れは**走査結果に関わらず** exit 1（行番号つきで報告）。
  検証は抑制の適用より先に走る。抑制した検出は黙って消さず標準出力に列挙する。
  抑制ファイルが無い場合の挙動は従来と完全に同一。運用手順は `docs/HARNESS_GUIDE.md` 13節。
- **git 情報が取れない環境での強制の劣化を可視化**: `SessionStart` フックが、作業ツリー・
  ブランチ・HEAD のいずれかを取得できない場合に、影響を受ける Rule（1・2・6・10・11）と
  倒れる向き（通過／拒否）を名指しして stderr に警告する。exit 0 は維持し、強制は追加しない。
- **Rule 12（危険操作フロア）**: 再帰削除（リポジトリ外）・秘密ファイルの読み取り・履歴の破壊・
  検証のスキップ・外部送信・`sudo` を無条件で拒否する。確認（ask）ではなく拒否（deny）。
  バイパス用の環境変数は用意しない。
- **強制レイヤの健全性自己診断**: `SessionStart` フック
  （`harness/hooks/session_start_healthcheck.py`）が hooks の import 可否・`path_utils` の
  主要関数・`.claude/settings.json` の Hook 登録を検査し、異常を警告とセッションへの追加
  コンテキストで知らせる。`PROGRESS.md` の先頭にも状態を表示する。
- **`harness/CLAIMS.md`**: 「何をブロックすると主張するか」と「それを実証するテスト」の対応表。
- **CI 項目 P**: `CLAIMS.md` に書かれた実証テストが `harness/tests/` に実在すること、
  実証テストが無い行に理由が書かれていることを検証する。
- **CI 項目 Q**: ハーネス本体に差分があるコミットで、`CHANGELOG.md` の Unreleased セクションが
  更新されていることを検証する。
- **`VERSION` / `CHANGELOG.md`**: 導入されたハーネスの版を機械的に特定できるようにした。
- **`harness/procedures/feature-build.md`**: `feature-builder` の実装フェーズ手順（オンデマンド
  読み込み。コンテキスト予算の対象外）。
- **`render_progress.py --html`**: 同じデータから非エンジニア向けの単一ファイル HTML
  （`apps/<app-id>/PROGRESS.html`）を生成する。入力は `status.yaml` / `contract.yaml` の
  `open_issues` / `VERSION` / 強制レイヤの診断だけで、AI に作文させない。生成物は
  `.gitignore` 対象。skill / subagent は増やしていない。
- 実証が無かった Rule 4・6・8 と、worktree 経由での Rule 1・3・5、CI 項目 A・B・E・F・G・I の
  テストを追加（454 → 656 テスト）。

### Changed

- **`pre_tool_use_guard.py` を fail-closed 化**: 想定外の例外を握りつぶさず、通過ではなく
  拒否（exit 2 ＋ 理由）で止まる。
- **hook 入力の破損も fail-closed の対象にした**: `path_utils.read_hook_input_strict()` を追加し、
  ブロックする hook（`pre_tool_use_guard.py` / `stop_commit_guard.py`）で使う。内容があるのに
  JSON オブジェクトとして読めない入力、および書き込み先が入っていない構造化編集は exit 2。
  空の stdin は従来どおり通す。非ブロッキングな hook（`post_tool_use_sync.py` /
  `post_tool_use_guard.py`）は寛容版のまま。
- **`new_feature_scaffold.py` の git 失敗の出し方**: `git worktree add` / `git add` / `git commit`
  の `check=True` を外し、`エラー: …` ＋ git の出力 ＋ 次の一手（`user.name` / `user.email` の
  設定コマンド）を stderr に出して非 0 で終わるようにした。traceback は出さない。
- **`pre_tool_use_guard.py` の冒頭 docstring**: 「バイパス用の環境変数は用意しない」の適用範囲が
  Bash 間接書き込み検知であることを明示し、Rule 1 の `HARNESS_UNLOCK=1` が意図的な緊急避難路で
  あること、他の Rule には解除路が無いことを明記した（強制の実体は変更なし）。
- **`.claude/settings.json`**: `PreToolUse` の matcher に `Read`/`NotebookRead` を追加
  （Rule 12 D-2）。`SessionStart` フックを追加。
- **コンテキスト予算の再配分**: `harness/CONVENTIONS.md` から設計意図・背景・経緯を
  `docs/HARNESS_GUIDE.md` 18節へ移設（35,891 → 約 29,900 バイト）。
  `.claude/agents/feature-builder.md` の手順を `harness/procedures/feature-build.md` へ切り出し
  （11,981 → 3,599 バイト）。

- **`docs/maintenance/friction-to-test.md`**: 摩擦点を再発防止テストへ変換する手順。
  深刻度 最高・高 の摩擦点は、再発を検出するテストが無い状態でクローズしない、というルールを置いた。
  対応表は `harness/CLAIMS.md` に置き、CI 項目 P で表と実体の drift を機械的に塞ぐ
  （`docs/maintenance/DOGFOODING-LOG.md` を機械可読にする案は過剰と判断して見送り。判断は手順書の末尾に記録）。

### Changed（文書配置）

- **`docs/` を新設し、人間向けの文書をルートから移した。** ルート直下に残すのは、実行物が
  パスとして解決するもの（`VERSION` / `CHANGELOG.md`）・入口（`README.md`）・ツール設定
  （`pyrightconfig.json`）・ハーネス内部から名前で参照される実地記録（`docs/maintenance/DOGFOODING-LOG.md`）だけ。
  - `HARNESS_GUIDE.md` → `docs/HARNESS_GUIDE.md`
  - `harness-flow-{plain,technical}.html` → `docs/flow/`
  - `IMPROVEMENT-PLAN.{md,machine.yaml}` / `REPAIR-ORDER.{md,machine.yaml}` → `docs/plans/`
  - `harness-comparison-{plain,technical}.html` → `docs/archive/`
  - `docs/README.md`（索引）を新規追加
- **`docs/` は人間専用、という規範を追加した**（`CONVENTIONS.md` 15節）。agent / skill の
  プロンプトから `docs/` を読ませない。ハーネス内部から `docs/` を指してよいのは**出典の注記**
  としてだけで、読めという指示ではない（本文では「人間向け」と添える）。`docs/` へ出してよいのは
  「ハーネス内部にあるが実は人間向けで、AI が参照する必要のない記述」だけ。判定ロジック・規範・
  手順は出さない。読まれないのでコンテキスト予算の対象外。背景は `docs/HARNESS_GUIDE.md` 6節。
- 移動に伴い、ハーネス内部 6 ファイル（`CONVENTIONS.md` / `CLAIMS.md` / `harness/README.md` /
  `ci_check.py` / `vuln_scan.py` / `test_path_utils_bash.py`）の `HARNESS_GUIDE.md` への参照を
  `docs/HARNESS_GUIDE.md` へ更新。`CONVENTIONS.md` の 1節（ディレクトリ構造）に `docs/` を追加。
  AI が読む節（6・9・10・12・14）にある参照には「人間向け」の印を付けた。

### Changed（ハーネスからの参照の切断）

- **ハーネス本体から `DOGFOODING-LOG.md` への参照を全廃した（12 件 → 0 件）。** これは
  ハーネス改修のための記録であって、ハーネス自身が参照するものではない。
  - 散文 9 件は、文書名を出さずに単体で意味が通る形へ書き換えた（`ci_check.py` 3 件・
    `print_conventions.py`・`CLAIMS.md`・`harness/README.md`・テスト docstring 3 件）。
    たとえば項目 O の「凍結の経緯は `DOGFOODING-LOG.md` 参照」は、凍結の事実そのもの
    （実地 3 本完走後の 2026-08-23 にユーザーの明示的許可で凍結）を docstring に直接書いた。
  - 残る 3 件は `harness/procedures/friction-to-test.md` の中にあり、その文書の存在理由その
    ものだった。どの agent も `always-reads` に宣言しておらず、保守者しか読まない文書なので、
    記録本体と一緒に `docs/maintenance/` へ移した（`CONVENTIONS.md` 15節の「`docs/` へ出して
    よいのは、ハーネス内部にあるが実は人間向けで AI が参照する必要のない記述」に該当する）。
  - `DOGFOODING-LOG.md` → `docs/maintenance/DOGFOODING-LOG.md`
  - `harness/procedures/friction-to-test.md` → `docs/maintenance/friction-to-test.md`
    （`harness/procedures/` に残るのは `feature-build.md` のみ）
- **残された依存**: ハーネス内部には摩擦点 ID（`F-047` など）が 39 種類残っている。うち
  深刻度 最高・高 の 20 種類は `harness/CLAIMS.md` の表から引ける（CI 項目 P が検証）。
  残り 19 種類はハーネス内部からは解決できない不透明な識別子だが、文書への参照ではないので
  そのままにした。意味を持たせたい箇所は、ID ではなく事実を直接書く方針とする。

### Removed

- **`HARNESS_GUIDE.pdf`**（1.4MB）。作成日 2026-08-19 で、Rule 8〜12・`gate-reviewer`・
  `CLAIMS.md`・`VERSION` が存在しない時代の 16 ページのスナップショット。どこからも参照されておらず、
  現行の `docs/HARNESS_GUIDE.md`（18節）とは別物になっていた。
- **`claude-code-harness-main/` と同 `.zip`**（合計 105MB、git 管理外）。比較調査の対象だった
  他プロジェクトの複製で、調査は完了しており apparness 側からの参照は 0 件だった。調査結果は
  `docs/archive/harness-comparison-*.html` に残る。`.gitignore` の無視指定は、再取得時に誤って
  コミットしないよう残してある。

### Fixed（文書）

- `docs/plans/REPAIR-ORDER.{md,machine.yaml}` が根拠に挙げる
  `harness-verdict-2026-08-24-*.html` は**このリポジトリに存在しない**。所在不明であることを
  明記し、根拠の実体が `findings[].evidence[]` にあることを示した。

### Documentation

- **実行物と説明文書の突き合わせ監査を行い、乖離 21 件を修正した**（実体側は変更していない。
  `docs/HARNESS_GUIDE.md` / `README.md` / `harness/README.md` / `harness/CONVENTIONS.md` /
  `.claude/agents/solution-architect.md` / フロー説明書 2 版）。主なもの:
  - `docs/HARNESS_GUIDE.md` 5節: 見出しは「12のルール」なのに表が Rule 1〜10 しか無かった。
    Rule 11・12 を追加し、hook 5 本と担当イベントの一覧、`PreToolUse` の matcher を明記。
    「Bash 経由では Rule 7・9・10 は判定対象外」という記述は誤り（現在は
    `check_requires_simulatable_tool` が**手段そのものを拒否**する）なので書き直した。
  - `docs/HARNESS_GUIDE.md` 6節: 「`CONVENTIONS.md` は全 subagent が起動時に読む」は実装と逆
    （全文を読む agent はおらず、節を宣言するのは `solution-architect` だけで残り 4 つは `none`）。
    表・図・行数（約230行 → 440行）を実測に合わせ、予算の 3 行目が「読むと宣言した節 ＋
    always-reads」であること、`procedures/` が予算の**対象**であることを明記。
  - `docs/HARNESS_GUIDE.md` 12節: CI チェック内容の表に M・N・O・P・Q が無く 11 項目しか無かった
    （実装は 16 項目）。5 行を追加し、L の判定方法を現在の実装に更新。H が欠番であることも明記。
  - `docs/HARNESS_GUIDE.md` 7節 対照表: Rule 11・Rule 12・書き込み手段の制限・強制レイヤの
    健全性・git 劣化の警告の 5 行が欠けていたので追加。
  - `docs/HARNESS_GUIDE.md` 2節: 「4つのsubagent」→ 5 つ。`procedures/` / `CLAIMS.md` / `tests/` /
    `VERSION` をマップに追加。
  - `docs/HARNESS_GUIDE.md` 11節: A-1 の緩和策を現在の fail-closed 実装に合わせ、
    **A-6（git 情報が取れない場所での判定劣化）** を 4 点セットで追加。
  - `docs/HARNESS_GUIDE.md` 冒頭: 更新日 2026-08-21 → 2026-08-24。追加済み一覧に Rule 11・12・
    自己診断・`CLAIMS.md`・`VERSION`/`CHANGELOG` を反映。存在しない `ROADMAP.md` への
    案内を実在する文書（`docs/plans/IMPROVEMENT-PLAN.machine.yaml` / 11節）へ差し替え。
  - `harness/README.md`: `procedures/` を「コンテキスト予算の対象外」と書いていたが実装は逆
    （always-reads として項目 L が計上する）。ドッグフーディング成果物が現存せず追検証できない
    ことも明記した。
  - `README.md`: 自己テスト件数 656 → 685。`validate_status_transition.py` の呼び出し方
    （`old_state` / `new_state` は**位置引数で必須**）を修正。Hook 登録に `SubagentStop` を追加。
    Rule 1 の `HARNESS_UNLOCK=1` と fail-closed の範囲を明記。
  - `harness/CONVENTIONS.md` 7節: fail-closed の範囲に「入力そのものを解釈できない場合」と
    `stop_commit_guard.py` を追加。git 劣化の警告に言及。`<app-name>` → `<app-id>`。
  - `.claude/agents/solution-architect.md`: テスト実在の機械検証の参照先を 14節 → **13節**
    （14節はスタックパック）。
  - `ROADMAP.md`（存在しない）への参照を `vuln_scan.py` と `test_path_utils_bash.py` の
    docstring からも除去。

- `README.md` を全面的に書き直した。プロジェクト概要・環境・ディレクトリ構成・開発環境構築・
  アプリ作成の流れ・機械が強制すること（Rule 12 と CI 16 項目）・コマンド一覧・文書の役割分担・
  トラブルシューティングを収録。記載したコマンドの引数は全スクリプトの `--help` と突き合わせて検証した。
- フロー説明書 2 版の数値を最新化（`CONVENTIONS.md` 31,975 バイト / 7節 9,034 バイト /
  685 テスト）し、`pyrightconfig.json` を文書の役割分担表に追加した。
- **摩擦点の件数を 79 → 77 に訂正した。** 実数は F-001〜F-067（67 件）＋ F-073〜F-082（10 件）＝ 77 件。
  比較調査 HTML の算術誤りが改修計画へ、さらに CLAIMS.md・README へ引き写されていた。出所ごと修正。

- `docs/flow/harness-flow-plain.html` / `docs/flow/harness-flow-technical.html` を全面改訂。Rule 12・SessionStart
  自己診断・CI 項目 P/Q・`CLAIMS.md` / `procedures/` / `VERSION` の追加を反映し、
  「いつ何が動くか」「誰がどの文書をどれだけ読むか（実測値）」「文書の役割分担と追記先」
  「ブランチ規約と保護」「ゲート判定の書式と決定性」を追記した。
  コンテキスト予算の既知の過小評価（`quality/*.md` を計上していないこと）も明記。
- 上記の記載内容を実行物（settings.json・ci_check.py の AST・path_utils の定数・schemas・
  scaffold スクリプト・agent frontmatter）から再抽出して照合し、実装にしか存在しなかった
  2 つの性質を追記した: **①判定不能時は allow に倒れる 10 条件**、
  **②Rule ごとのツール適用範囲の差**（Rule 7・9・10・11 は Edit/Write/MultiEdit のみ、
  NotebookEdit には適用されない）。両版に出典と再検証手順の節も追加。

- `harness/README.md` を 12 ルール・SessionStart 自己診断・`CLAIMS.md` / `procedures/` /
  `VERSION` の追加に追随させた。

- `docs/HARNESS_GUIDE.md` 11節（既知の制約）を **4 点セット**（症状 / 根本原因 / 適用中の緩和策 /
  再検討の条件）に統一し、「ハーネスの制御外に根本原因があるもの（A-1〜A-5）」と
  「apparness 側で直せるもの（B-1〜B-5）」に分けた。B は改修計画の `tasks[]` に昇格させ、
  条件付きタスク T-040（Rule 12 の読み取り・送信の事後検知）を追加した。
- `docs/maintenance/DOGFOODING-LOG.md` の冒頭に「未処理の摩擦点（F-059 / F-060 / F-064）」と
  「ドッグフーディング成果物の保全状況」を追加。3 アプリの成果物がどこからも辿れないこと、
  何を探して無かったか、見つかったときに何を保全すべきかを記録した。

### Fixed

- **エディタ上の型チェックエラー 210 件を解消した**（実行時の挙動は不変）。根本原因は 1 つで、
  `hooks` が `sys.path` を実行時に操作して `path_utils` を読むため、Pyright/Pylance が
  インポートを解決できず、そこから「型が不明」の指摘が 166 件派生していた。
  - `pyrightconfig.json` を追加し、`harness/hooks` / `harness/scripts` / `harness/tests` の
    `extraPaths` を宣言した。
  - `harness/hooks/**` の素のジェネリック注釈（`dict` / `list`）28 件に型引数を付けた。
    このとき `_classify_bash_lines` の戻り値注釈が T-020 の 3-tuple 化に追随しておらず
    2-tuple のままだったことも判明し、あわせて修正した。
  - 注釈が無かった 6 つのシグネチャ（`parse_simple_yaml` / `_yaml_scalar` / `_yaml_flow` /
    `_yaml_split_key` / `read_state_field` / `detect_dangerous_bash_operation` の `resolve`）を
    埋めた。
  - `path_utils` の関数内 `import os` 9 件をモジュール先頭へ集約した。
  - すべて注釈と import 位置の変更のみで、`from __future__ import annotations` により実行時には
    評価されない。656 テスト・CI 全項目・Hook の実地動作で無変更を確認済み。

- **内容比較ゲート（Rule 3・7・9・10・11）の迂回経路 3 件を塞いだ**（実測で再現して確認）。
  判定を「Bash かどうか」ではなく「`simulate_write_result()` が書き込み後の内容を再現できる手段か」
  に一般化した（`check_requires_simulatable_tool`）。`CONTENT_JUDGED_RES` に
  `integration.machine.yaml` を追加。
  - `NotebookEdit` で受領書なしの `state: TESTED` を書き込めた（`simulate_write_result()` が
    NotebookEdit を扱えず、書き込み後の内容として変更前の内容がそのまま返るため、
    Rule 9・10 から見れば「何も変わっていない」状態になっていた）。
  - `Bash` で `integration.machine.yaml` を書き換えられた ＝ **統合受領書を手書きできた**（INV-2 違反）。
  - `NotebookEdit` でも同上。
  - 事後検証（`post_tool_use_guard.py`）にはこの制限を掛けない。掛けると `run_verification.py` が
    書き込んだ受領書が巻き戻り、`TESTED` へ永久に進めなくなる。この逃がしも回帰テストで固定した。

- **コンテキスト予算の空洞化を塞いだ**: プロンプト本文を `harness/procedures/*.md` へ移して
  「起動直後にこれを読め」と書くと、agent のファイルサイズは減るのにセッションに載るバイト数は
  変わらない（導入文のぶん増える）。項目 L に `always-reads` マーカーを導入し、宣言された
  手順書の実サイズを常時コストに計上するようにした。宣言せずに `harness/procedures/*.md` を
  読ませていたら不合格。`feature-build.md` 自体も 9,290 → 4,701 バイトに圧縮し、
  `feature-builder` の実コストを 11,981 → 8,397 バイト（-30%）にした。

- **ヒアドキュメント本体の誤検知**（F-A4）: `cat > x.html <<'EOF' ... EOF` で文書を書き出す際、
  本文の HTML に含まれる `>` がリダイレクト演算子として解釈され、直後の `harness/...` が
  書き込み先とみなされて Rule 1 が発火していた。本体はデータとして抽出対象から外した。

## [1.0.0] - 2026-08-23

### Added

- 初版。Hook が強制する 11 ルール、CI 項目 A-O、5 つの subagent、4 つの skill、
  検証受領書（Rule 10）と統合受領書（Rule 11）、契約の機械検証（`interfaces[]` 突合・
  要件トレーサビリティ）、コンテキスト予算（項目 L）、二重管理検出（項目 M）、
  `CONVENTIONS.md` の 15 節凍結（項目 O）。
- ドッグフーディングで 3 アプリ（md-todo-cli / bookmark-vault / habit-tui）を完走し、
  77 件の摩擦点を `docs/maintenance/DOGFOODING-LOG.md` に記録。
