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

現在の版は `VERSION` にある。`PROGRESS.md` の先頭にも表示される。

## [Unreleased]

### Added

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

### Documentation

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
