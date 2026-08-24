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
  テストを追加（454 → 629 テスト）。

### Changed

- **`pre_tool_use_guard.py` を fail-closed 化**: 想定外の例外を握りつぶさず、通過ではなく
  拒否（exit 2 ＋ 理由）で止まる。
- **`.claude/settings.json`**: `PreToolUse` の matcher に `Read`/`NotebookRead` を追加
  （Rule 12 D-2）。`SessionStart` フックを追加。
- **コンテキスト予算の再配分**: `harness/CONVENTIONS.md` から設計意図・背景・経緯を
  `HARNESS_GUIDE.md` 18節へ移設（35,891 → 約 29,900 バイト）。
  `.claude/agents/feature-builder.md` の手順を `harness/procedures/feature-build.md` へ切り出し
  （11,981 → 3,599 バイト）。

### Documentation

- `DOGFOODING-LOG.md` の冒頭に「未処理の摩擦点（F-059 / F-060 / F-064）」と
  「ドッグフーディング成果物の保全状況」を追加。3 アプリの成果物がどこからも辿れないこと、
  何を探して無かったか、見つかったときに何を保全すべきかを記録した。

### Fixed

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
  79 件の摩擦点を `DOGFOODING-LOG.md` に記録。
