# ドッグフーディング記録: md-todo-cli（ROADMAP ⑩ の実施ログ）

ハーネスを実際に使っておためしアプリを 1 本通し、ハーネス自身の問題点を洗い出すための記録。
**この文書はハーネス改修の入力であり、アプリの成果物ではない。**

- 題材: `apps/md-todo-cli`（Markdown ToDo CLI / Python / AUTONOMOUS）
- 方針: 通しの実行中は `harness/` を触らず摩擦点をここに溜め、通し切ってから
  `harness/<topic>` ブランチで一括改修する（ユーザー合意済み）

---

## ★ 未処理の摩擦点（2026-08-24 時点。この文書の先頭で必ず確認すること）

3 本完走してクローズ済みだが、**次の 3 件は未処理のまま残っている**。改修に着手する人は
まずここを見ること（全文は本文の該当節）。

| ID | 深刻度 | 状態 | 内容 |
|---|---|---|---|
| **F-059** | 低 | **未着手**（着手指示は出ているが未実施） | 依存機能の公開 API 名が `contract.yaml` に機械的な形で存在しない |
| **F-060** | 低 | **未改修**（記録のみ） | Rule 7 のエラーメッセージが、実際に機能する回避策を示していない |
| **F-064** | 中 | **対応不要と判断済み** | レビュー待機中に応答を終えようとすると Rule 8 に阻まれる |

F-076〜F-082 は改修見送り（理由は各項目に記載）。それ以外の F-001〜F-075 は改修済み。

## ★ 摩擦点をテストへ変換するルール（2026-08-24 追加）

**深刻度が「最高」または「高」の摩擦点は、再発を検出するテストが無い状態でクローズしない。**

- 対応表は `harness/CLAIMS.md` の「深刻度 最高・高 の摩擦点 → 再発防止テスト」。
  そこに書かれたテスト名が実在するかは CI 項目 P が機械的に検証する。
- テストが書けないものは、同じ表の「未実証の残余」列に**なぜ書けないか**を書く（空欄は CI が拒否）。
- 変換の手順は `friction-to-test.md`（同ディレクトリ）。
- 中・低の摩擦点はこのルールの対象外（テストを書いてもよいが、必須ではない）。

この文書（140KB の散文）自体を機械可読にして CI 判定する案は**過剰と判断して見送った**。
判断の記録は `friction-to-test.md`（同ディレクトリ） 末尾。

## ★ ドッグフーディング成果物の保全状況（2026-08-24 時点）

**結論: 3 アプリ（md-todo-cli / bookmark-vault / habit-tui）の成果物は、現時点で
どこからも辿れない。** 「3 本完走した」というこのハーネスの最重要の実績が、第三者にも将来の
自分にも追検証できない状態にある（改修計画の F-A6）。

### 何を探して、無かったか

| 探した先 | 結果 |
|---|---|
| このリポジトリ（`apparness-harness`）の `apps/` | 存在しない |
| このリポジトリの git 履歴 | `851f07a chore: harness-template を main (068363e) から再生成` の 1 コミットのみ。`apps/` を含むツリーは履歴上に存在しない |
| ローカルの `apparness` リポジトリ（`~/ghq/github.com/studioyukidaruma-dev/apparness`） | `apps/` は空。履歴上に現れるのは `todo-app` と `pomodoro-timer` のみで、3 アプリはいずれも無い |
| `apparness` の origin（GitHub） | `refs/heads/main` のみ。ローカル HEAD と同一で、3 アプリは含まれない |
| 本文が参照するコミット `ebd68d8`（bookmark-vault 完走）・`ac96c4e`（habit-tui 完走）・`068363e`（テンプレート再生成元） | いずれも到達可能なオブジェクトとして存在しない |

つまり、成果物は**このマシンから見えるどのリポジトリにも残っていない**。別のマシン・別の
クローン・別のリモートにしか存在しない可能性がある。

### 見つかったときに何を保全するか

全部をこのリポジトリに戻す必要はない。**完走を裏付けるのに要るのは次の 4 種類だけ**で、
これらはコードを含まないため軽量に保全できる:

1. `apps/<app-id>/03-features/*/status.yaml` — `state: INTEGRATED` と `verification_receipt`
   （どのコミットで、どのコマンドが `exit_code: 0` だったか）
2. `apps/<app-id>/04-integration/integration.machine.yaml` — 統合の受領書と `interface_coverage[]`
3. `apps/<app-id>/PROGRESS.md` / `STATE.machine.yaml` — 完走時点のダッシュボード
4. `apps/<app-id>/00-requirements/` `02-design/` の machine.yaml — 何を作ると宣言したか

受領書は `run_verification.py` / `run_integration_verification.py` だけが生成でき、手書きできない
（Rule 10 / Rule 11）。**受領書とその `commit` こそが完走の証拠**であり、実装コードそのものは
無くてもよい。

保全先をこのリポジトリに置く場合の推奨パスは `docs/dogfooding-artifacts/<app-id>/`
（`apps/` に置くと CI 項目 A・I・K・N が実在するアプリとして検証を始めてしまうため、
`apps/` の外に置く）。

### 保全した／保全先が決まったら

この節を書き換えて、**保全場所と、そこで何を確認できるか**を記録すること。
「どこかにあるはず」ではなく、**辿れるパスまたは URL** を書く。

---

## この文書の構成（追記が時系列なので、並びが前後している）

| 節 | 内容 |
|---|---|
| **再開手順** | **まずここを読む。** 現在地・次にやること・作業の型・地雷・F-047 |
| 摩擦点一覧 | F-001〜F-026（要件・設計フェーズで見つけたもの） |
| 設計フェーズで確認できた「ちゃんと動いたこと」 | 空振りしていない検査の記録 |
| 摩擦点（機能実装フェーズ） | F-027〜F-031。**F-029/F-030 が最も重い**（決定論的強制の中核が空振りしていた） |
| 改修記録 | F-029/F-030 の修正内容と、その後の第1〜3弾（21 件）の一覧 |
| 摩擦点（実装フェーズ: todo-file-store） | F-032〜F-046 |
| 改修記録（第4弾） | 残り 20 件の改修内容と検証方法。**F-001〜F-046 が処理済み** |
| 摩擦点（実装フェーズ: todo-markdown） | F-049〜F-054 ＋ 契約の穴 OI-1〜OI-8 |
| 改修記録（第5弾） | F-049・F-050 を改修（`todo-cli` の実装前に踏むため先行処理）|
| 摩擦点（ユーザーからの問いで発見） | F-055（worktree の外への書き込みが素通り）。改修済み |
| 摩擦点（統合フェーズ: integrator 初回実行） | F-056〜F-059。F-056 は改修済み、F-057〜F-059 は記録のみ |
| 摩擦点（2本目: bookmark-vault / 要件定義〜機能実装フェーズ） | F-060〜F-064。記録のみ（F-061は高・要改修候補） |
| 摩擦点（統合フェーズ: bookmark-vault integrator実行） | F-065〜F-067。F-065/F-066 は改修済み、F-067 は記録のみ。F-057 の再発も確認 |
| 両本完走後のまとめ改修 | ユーザー指摘による2件（`applies_to`・Rule 11）。F-065/F-066 の改修詳細もここに集約 |
| フェーズ1: 残る摩擦点の修正 | F-051・F-052・F-053・F-054・F-057・F-058・F-061・F-062・F-063・F-067 を改修（F-059/F-060/F-064 は未着手のまま） |

**摩擦点 ID は F-001〜F-067、および3本目(habit-tui)由来の F-073〜F-082 で通し番号。**
（F-068〜F-072 は欠番——採番せずに済んだ軽微な所感だったため）。深刻度は 最高 / 高 / 中 / 低。
F-047・F-048 は改修中／ユーザー指摘で見つかったもので、「再開手順」の末尾にある。
**2026-08-23 時点で3本すべて（md-todo-cli・bookmark-vault・habit-tui）が `INTEGRATED` まで
完走。フェーズ1〜3すべて完了し、ROADMAP⑩「異種スタックでのドッグフーディング」は
クローズ済み。`CONVENTIONS.md`はユーザーの明示的な許可を得て凍結済み（節の新設は
`ci_check.py`項目Oが拒否）。全10 worktree（bookmark-vault 4・habit-tui 3）を削除済み。
**ドッグフーディング（ROADMAP⑩）自体は完了。** ユーザーの指示により、次は
**F-059（下記）への着手**が次の再開ポイント（★次の再開ポイント参照）。**

---

## 再開手順（セッションが切れた場合はここから）

**この節だけ読めば再開できる。** 摩擦点の全文はこの下、改修済みの内訳は末尾の「改修記録」。

### 現在地（2026-08-23 時点。★ここが最新）

| 項目 | 状態 |
|---|---|
| ブランチ | `main`（フェーズ1〜3すべて `main` にマージ済み） |
| ハーネス自己テスト | **454 件が緑**（フェーズ2でF-073/F-074の回帰テスト5件、フェーズ3で凍結の回帰テスト6件を追加。443→448→454） |
| `ci_check.py` / `check_interfaces.py` | 全項目通過 |
| 摩擦点 | F-001〜F-058・F-061〜F-063・F-065〜F-067・F-073〜F-075 は改修済み。F-076〜F-082 は記録のみ（改修見送り、理由は各項目参照）。**未改修は F-059（大きめなので見送り候補、着手にはユーザー確認が要る）・F-060（低・記録のみ）・F-064（対応不要と判断済み）のみ** |
| 1本目 | `apps/md-todo-cli`（Python/AUTONOMOUS/CLI）。3機能すべて **INTEGRATED** で完走済み。worktree は `git worktree remove` 済み |
| 2本目 | `apps/bookmark-vault`（TypeScript/SUPERVISED/HTTP API+フロントエンド）。**4機能すべて `INTEGRATED` まで完走**（2026-08-23、コミット `ebd68d8`）。**worktree 4つが未削除のまま残っている**（`git worktree remove` は未実施。フェーズ3で対応） |
| 3本目 | `apps/habit-tui`（Go/MANUAL/TUI）。**3機能すべて `INTEGRATED` まで完走**（2026-08-23、コミット `ac96c4e`）。worktree 3つが未削除のまま残っている（フェーズ3で対応）。**これでROADMAP⑩の3本がすべて完走した** |
| まとめ改修 | `applies_to`（required_skills[]の機能単位絞り込み）・Rule 11（interfaces[]の実地カバレッジ機械検証）の2件を実施済み。**Rule 11 は habit-tui で初めて実地を通り、期待通り機能することを確認した**（F-081参照） |

`todo-cli` は TESTED（`46c843f`/`8dc2236`）を経て、`integrator` が3ブランチを merge
（`875cab1`/`777cb89`/`29566e4`）→ `interfaces[]` 5本を `04-integration/assembly/` に実装
→ 結合テスト15件＋単体テスト126件が全緑 → 手動でのCLI動作確認 → `state: INTEGRATED`
（`f3aa761`）まで完走した。F-056（`render_progress.py` の worktree優先順位バグ）は改修済み
（`harness/fix-render-progress-worktree-priority`）。

`bookmark-vault` は4ブランチを merge（`1d92355`/`bc6daae`/`39113ff`/`f227bb3`）→
`interfaces[]` 10本を `04-integration/assembly/` に実装 → 結合テスト13件＋単体テスト89件
（計102件）が全緑 → 実サーバー起動での手動確認 → `state: INTEGRATED`（`ebd68d8`）まで完走した
（詳細は `apps/bookmark-vault/04-integration/integration.md`、摩擦点は「摩擦点（統合フェーズ:
bookmark-vault integrator実行）」節の F-065〜F-067）。

`habit-tui` は3ブランチを merge（`4b7d4b2`/`bf04722`/`bf6ed61`）→ `interfaces[]` 5本を
`04-integration/assembly/`（第4の独立Goモジュール、`replace`ディレクティブで3機能を束ねる）
に実装 → 結合テスト5件＋単体テスト（habit-store 16件・habit-core 37件・habit-ui 15件、
計68件）が全緑 → `run_integration_verification.py`で受領書取得 → `state: INTEGRATED`
（`ac96c4e`）まで完走した（詳細は`apps/habit-tui/04-integration/integration.md`、摩擦点は
下記 F-073〜F-082）。**これで ROADMAP ⑩「異種スタックでのドッグフーディング」の3本すべてが
要件定義→設計→実装→統合まで完走した。**

### フェーズ1「残る摩擦点の修正」（2026-08-23 開始 → 2026-08-23 完了）

**全体計画（ユーザーと合意済み、2026-08-23）**:
1. **（完了）残る摩擦点を修正する**——結果は本節末尾の「フェーズ1完了後（フェーズ2）」および
   ファイル末尾の「フェーズ1: 残る摩擦点の修正（2026-08-23）」を参照。
2. 3本目のアプリを最初から通しで作り、これまでの改修（特に Rule 11・`applies_to`）が
   実地で機能するか、新たな摩擦点が無いかを洗い出す（**★ 次の再開ポイント。下記
   「フェーズ1完了後（フェーズ2）」節から着手する**）
3. その結果を踏まえて `CONVENTIONS.md` の凍結・ROADMAP ⑩ のクローズを判断する

**このフェーズはコンテキストをクリアしてから着手する運用（元セッションの残量が50%を切った
ため）。** そのため各項目について「何をどう直すか」の結論をここに書いておく——
再分析せずにこの節だけ読んで着手できるようにするのが目的。bookmark-vault の worktree
クリーンアップは、このフェーズの後（フェーズ3の直前）でよい。

#### 修正対象と方針（推奨着手順）

各項目の全文は下の「摩擦点一覧」/該当フェーズの節を参照（見出しの `### F-0XX` で検索）。

1. **F-051（中・実証済み）** JUnit識別子照合が `@pytest.mark.parametrize` と両立しない
   （`test_x[None]` が契約の `test_x` と一致せず、実在して成功しているテストが
   「見つからない」と誤判定される）。
   → `harness/scripts/junit_utils.py` の識別子候補生成（`testcase_identifiers`）に、
   `name` から末尾の `[...]` を落とした形も候補として追加する。あわせて
   `path_utils.validate_traceability` の「見つかりません」メッセージに
   「パラメータ化テストは `name` に `[...]` が付くため要注意」の一文を足す。
   回帰テストは `harness/tests/test_verification.py`（JUnit解析のテストがある方）に追加。

2. **F-053（中）** subagent スレッドでは Bash の cwd が呼び出しごとにリセットされる
   （ツールの説明文「Working directory persists between calls」と矛盾する実地の挙動）。
   → `.claude/agents/feature-builder.md` に「cwd は保持されないので毎回
   `cd <絶対パス> && <単一コマンド>` の形で実行する（`&&` は許容、`;` は不可）」と明記する。
   ドキュメントのみの修正（ハーネスのコード変更なし）。`integrator.md` にも同様の注意が
   要るか確認する（integrator はメイン worktree 固定で動くため影響が小さい可能性がある）。

3. **F-054（中）** 検証が失敗しても受領書は書き込まれるため、「NGだが受領書はある」
   未コミット状態が残り、応答を終えようとすると Rule 8（未コミット停止拒否）に阻まれる
   （失敗した受領書をコミットするのは筋が悪く、詰みかけている）。
   → 方針: 「失敗した受領書のコミットは許容される」ことを明示する
   （`state: TESTED` への昇格は Rule 10 が受領書の中身で別途止めるので、失敗記録を
   コミットしても安全）。`CONVENTIONS.md` 12節に一文追記し、`feature-builder.md` にも
   「検証失敗時はいったんコミットしてから原因を直し、受領書を作り直す」手順を明記する。
   **`CONVENTIONS.md` は 2026-08-23 時点で 35993/36000 バイト（残り 7 バイト）。**
   追記する場合は必ず同時にどこかを削るか `docs/HARNESS_GUIDE.md` へ移すこと
   （F-047 と同じ捻出作業が要る）。

4. **F-058（低）** `open_issues[]` の申し送り文が、integrator の実際の権限
   （Rule 2 により `03-features/*/src/` を直接編集できない）を考慮せずに書かれる
   （実例: 「integrator が直接直せる」前提の申し送りが実際の権限モデルと食い違っていた）。
   → `.claude/agents/feature-builder.md` の `open_issues[]` 記載ガイドに、
   「integrator が実際に触れられるのは `04-integration/` 配下だけ」という前提を
   踏まえた表現にすべきことを明記する。ドキュメントのみ。

5. **F-062（中・実証済み）** `status.schema.json` の `review.blockers`/`majors`/`minors`
   は整数（件数）だが、`feature-builder`・`gate-reviewer` とも指摘の本文をそのまま
   文字列配列として書いてしまい schema 違反になった（具体例が無いことが原因）。
   → `gate-reviewer`/`feature-builder` の agent 定義に、`review:` の正しい書式
   （3フィールドは整数、詳細は `notes` に1本の文字列で）を具体例つきで明記する。
   可能なら `new_feature_scaffold.py` が生成する `status.yaml` のコメントにも書式例を残す。

6. **F-061（高・実証済み・最優先）** `parse_simple_yaml` が `- >-`（シーケンス項目としての
   ブロックスカラー）を解釈できず、それ以降の全トップレベルキーの解析が丸ごと消える。
   `review.majors`/`minors` にこの書式を使うと、実在する `verification_receipt` が
   `{}` として読まれ、「受領書が無いため TESTED にできません」という**誤解を招くブロック**が
   起きる（実害が実証済みの最重要バグ）。
   → `harness/hooks/lib/path_utils.py` の `_yaml_parse_sequence` に `- >-`/`- |` の
   処理を追加する（`_yaml_parse_mapping` が使う `_yaml_consume_block_scalar` と同じ
   ロジックをシーケンス項目にも適用する）。最低限の保険として、認識できない行で
   丸ごと `break` するのではなく、その行だけスキップして後続キーの解析を継続する
   フォールバックも入れると再発防止になる。**この関数は Hook 本体が使う依存ゼロの
   軽量パーサーであり、影響範囲が広いので回帰テストを手厚く書くこと**
   （`harness/tests/test_yaml_parser.py` を使う）。

7. **F-067（低）** `04-integration/assembly` を新設する際、devDependency のバイナリ
   （`tsc`/`vitest` 等）が `npm install` 前には PATH に無い
   （`03-features/*` 側の「各コマンドの先頭で `npm install`」規約が、integrator が
   新設する `04-integration/assembly` 側には明記されていなかった）。
   → `.claude/agents/integrator.md` または `harness/templates/integration.machine.yaml.tmpl`
   のコメントに、「assembly 自身の npm スクリプトも各コマンドの先頭で `npm install` する」
   ことを明記する。ドキュメントのみ。

8. **F-052・F-057（中・対応不能なので明文化のみ）** `code-review`/`security-review` は
   **このリポジトリの `harness/` ではなく Claude Code 標準搭載の skill**
   （`.claude/skills/` 配下にファイルが無いことを確認済み。プロジェクト側からは中身を
   直せない）。integrator の小さな差分にスコープを絞れない・通知のたびに skill 全文が
   再注入される、という2つの症状は harness 側のコードでは直せない。
   → 実務的な対処（実地では毎回すでに行っている）を `integrator.md` の手順として
   明文化するだけに留める:「`code-review`/`security-review` にスコープを絞る引数を渡しても
   全履歴が対象になる既知の制約があるため、統合コード（`04-integration/assembly/` 等）に
   限定した手動レビューに最初から切り替えてよい」。改修ではなく運用手順の明記。

9. **F-063（高・ただしハーネス外の挙動）** cwd固定セッションが自分自身から
   Agent/Skill をバックグラウンド起動すると、以後のツール呼び出しの cwd 追跡が
   壊れることがある（Claude Code 側のエージェント実行基盤の挙動で、`harness/` の
   改修対象にはできないとすでに判断済み）。
   → ワークアラウンド（「レビュー/検証系のバックグラウンド起動は `src/` 編集が
   全部終わってから」）は今回のセッションで `integrator` への依頼文には都度書いていたが、
   **`.claude/agents/feature-builder.md`/`integrator.md` 自体にはまだ恒久的に明記していない**。
   このフェーズで両ファイルに1文ずつ追記しておくと、次回以降の依頼文で毎回書かずに済む。
   ドキュメントのみ。

10. **F-059（低・大きめなので今回は見送り候補）** 依存機能の公開API名が `contract.yaml`
    に機械可読な形で存在しない（`__all__` の目視確認に頼っている）。
    → `feature-contract.schema.json` への `public_api:` 的なフィールド追加と
    `check_interfaces.py` 側の突合ロジックが要る、スキーマ拡張を伴う大きめの変更。
    **このフェーズでは着手せず、着手するかどうかをユーザーに確認してから判断すること。**

11. **F-064（中・すでに見送り判断済み、対応不要）** レビュー待機中に応答を終えようとすると
    Rule 8 に阻まれる（F-054 と根は同じ）。低頻度・回避策確立済みのため記録のみで良いと
    すでに判断済み。**このフェーズでは何もしなくてよい**（F-054 を直せば実質的にも解消する）。

#### 修正の型（これまでと同じ）

各修正は `harness/<topic>` ブランチで行い、
`uv run --python 3.12 --with pytest --with pyyaml --with jsonschema python -m pytest harness/tests -q`
と `python3 harness/scripts/ci_check.py` を通してから `main` へ `--no-ff` マージする
（詳細は次の「作業の型」節）。1件ずつ別ブランチにする必要はなく、過去の「第4弾」「第5弾」の
ように複数件をまとめて1〜2本の `harness/<topic>` ブランチに収めてよい。**ドキュメントのみの
修正（F-053・F-058・F-062・F-067・F-052/F-057・F-063）とコード変更を伴う修正
（F-051・F-054・F-061）は分けたほうが、CONVENTIONS.md のバイト予算のやりくり
（項目3参照）も含めてレビューしやすい。**

修正が一通り終わったら、このファイルの「摩擦点一覧」側の該当する `### F-0XX` 見出しに
「→ **改修済み**」を追記し、末尾に改修記録を追記すること（これまでと同じ作法）。

#### フェーズ2完了：habit-tui は要件定義→設計→実装→統合まで完走した（2026-08-23）

3本目 `apps/habit-tui`（習慣トラッキングTUI／Go言語／TUI／`autonomy_mode: MANUAL`。
1本目Python/CLI/AUTONOMOUS・2本目TypeScript/HTTP API+フロントエンド/SUPERVISEDとは
異なる軸）が、3機能（`habit-store`/`habit-core`/`habit-ui`）すべて `state: INTEGRATED`
に到達した（コミット `ac96c4e`）。要件定義`84675e2`→設計`750e3d9`→3機能TESTED
（`72bc7e7`/`60dbe99`/`d659f78`）→統合`ac96c4e`。ハーネス自己テストは448件全緑、
`ci_check.py`もOK。**これで ROADMAP ⑩「異種スタックでのドッグフーディング」の3本すべてが
要件定義→設計→実装→統合まで完走した。**

途中で見つかった摩擦点は F-073〜F-082 として本文化済み（下記「摩擦点一覧」参照）。うち
F-073（Rule 10/11のHEAD取得バグ）・F-074（統合カバレッジ判定の免除ロジック不全）・F-075
（`state_history[]`追記位置の再発）の3件はその場で改修・`main`にマージ済み。残り
（F-076〜F-082）は記録のみ（改修見送り、理由は各項目参照）。

**次にやること（★ 次の再開ポイント：フェーズ3）**: 下記「フェーズ3」節を参照。
`CONVENTIONS.md`凍結判断・bookmark-vault worktreeクリーンアップ・ROADMAP⑩クローズの
3点をユーザーと確認する。

### F-073 【実証済み・高】Rule 10/11のcommit照合が、worktreeスコープ解決後のtoplevelではなく生のcwdでHEADを取得していた → **改修済み**

`pre_tool_use_guard.py` の `main()` は `.worktrees/` を通る書き込みパスを検知すると
`resolve_worktree_scope()` で対象 worktree のルート（`scope_top`）を解決し、`toplevel` として
各 Rule チェック関数に渡す（F-029/F-030の修正）。ところが `check_rule10_verification_receipt`
（316行目）と `check_rule11_integration_receipt`（403行目）だけは、`state: TESTED`/
`INTEGRATED` 昇格時の commit 照合に使う HEAD を `path_utils.get_head_commit(cwd)` ——
**セッションの生の cwd** から取得していた。

実害: `feature-builder` をオーケストレーター（親セッション）から `Agent` ツール経由で
起動すると、実プロセスの cwd が対象 worktree ではなくメインリポジトリのルートのまま
subagent に渡ることがある（`habit-tui`の`habit-core`実装で実証）。この場合 `toplevel`（＝
`scope_top`）は正しく worktree ルートに解決されているのに、`get_head_commit(cwd)` は
無関係なメインリポジトリの HEAD を返し続けるため、worktree 側でどれだけ正しい受領書
（正しい commit）を作っても一致判定が**構造的に常に失敗**し、`state: TESTED` に
絶対に進めない。`new-feature-worktree` skill は「cwdが固定されたsubagentはworktreeに
移れない」という別の既知の制約（F-031）は警告しているが、それを承知の上でオーケストレーター側が
`Agent`経由でfeature-builderを起動する運用が実際にあり得る以上、このバグは看過できない。

→ 改修（`harness/fix-verification-receipt-head-commit-cwd`）: 両関数の
`get_head_commit(cwd)` を `get_head_commit(toplevel)` に変更（`toplevel`は呼び出し元で
既に worktree スコープ解決済み）。不要になった `cwd` 引数は両関数のシグネチャおよび
呼び出し側から削除した。回帰テスト1件を `test_worktree_scope.py` に追加（セッションの
生cwdと対象worktreeの`get_head_commit`が異なる値を返すようモックし、修正前は拒否・
修正後は通過することを確認）。

### F-074 【実証済み・高】統合カバレッジ判定の「統合前は許可する」免除が、scaffoldの空テンプレートで機能していなかった → **改修済み**

`check_integration_traceability.check_app`（`ci_check.py` 項目N・Rule 11の宣言レベル版）は
「`04-integration/integration.machine.yaml` が**存在しない**なら統合前とみなし判定不能として
許可する」という免除ロジックを持っていた。しかし `new_app_scaffold.py` はこのファイルを
`interface_coverage: []` の空テンプレートとして**アプリ作成の scaffold 時点**から生成する
ため、ファイルは常に存在し、この免除は実質的に一度も発動しない死んだコードだった。

実害: `interfaces[]`（機能間結線）を持つアプリが1つでも `apps/` 配下に存在し、かつまだ
`state: INTEGRATED` に到達していない間（設計承認直後〜統合完了まで、今回は数時間〜1日規模）、
**そのアプリと無関係などの `harness/<topic>` ブランチをマージしようとしても
`ci_check.py` が常時 NG になる**。`habit-tui` の設計承認直後、F-073 の修正を
`ci_check.py` に通そうとした際に実際に踏んだ。

→ 改修（同ブランチ）: 免除の判定条件を「ファイルが存在しない」から「`interface_coverage[]`
の中身が空（1件も無い）」に変更（ファイル不存在時は従来どおり空リスト相当として扱われるので
既存動作は保たれる）。統合が実際に始まって1件でも `interface_coverage[]` が書かれれば、
そこから先は従来どおり取りこぼしを検出する。回帰テスト4件を新設の
`test_check_integration_traceability.py` に追加。

### F-075 （軽微・親セッションの作業ミス、記録として残す）ネストした `state_history[]` シーケンスへの追記位置を誤ると `parse_simple_yaml` が後続キーを解析できなくなる

`habit-core` の `status.yaml` に `state: TESTED` の履歴エントリを手動追記する際、
`review:` マッピングの**外側**（`assignee:` の直前）に `- state: TESTED\n  ...` を
挿入してしまい、`parse_simple_yaml` が `review:` 以降のトップレベルキー（`assignee`〜
`verification_receipt` まで）を一切解析できなくなった（Hookの`verification_receipt`
比較が`None != {...}`になり手書き扱いで拒否される形で発覚）。原因はAI（このセッション）の
YAML構造の見落としであり、パーサー自体のバグではない——実際に`state_history:`の**直後**に
正しく挿入し直すと問題なく解析できた（F-061の再発ではないことを確認済み）。とはいえ、
「ネストしたシーケンスの途中に別のトップレベルマッピング（`review:`）が挟まる」という
`status.yaml`のレイアウトはこの手のミスを誘発しやすい。**統合フェーズで`integrator`も
同じ誤りを踏んだため（下記参照）、見積もりより発生頻度が高いと判断し改修済み**
（`harness/docs-state-history-append-position`）: `feature-builder.md`・`integrator.md`
それぞれに「`state_history`への追記は最後の項目の直後、`review:`より前に」の一文を追加。
パーサー自体は変更していない（この構造はYAML的にも曖昧であり、パーサーを緩めると
別の取りこぼしを誘発するリスクの方が大きいと判断したため）。

### F-076 solution-architect: Go言語のJUnit XML出力に標準対応が無く、スタックパック不在ゆえ自力調査が必要だった（中）

Go標準の`go test`はJUnit XMLを出力できないため`gotest.tools/gotestsum`が必要で、かつ
Go 1.24の`tool`ディレクティブ（`go get -tool`相当）でバージョン固定する、という手順に
自力で辿り着く必要があった。`CONVENTIONS.md`/`STACK_PACK.md`はこの存在を教えてくれない
（Go向けスタックパックが存在しないため）。md-todo-cli(pytest)・bookmark-vault(vitest)は
標準でJUnit XML相当に対応しており、この穴は今回初めて顕在化した。改修は見送り
（スタックパックの新規作成はスコープ外。将来Go製アプリを再度扱う際は、この調査結果を
Go向けスタックパックとして書き起こす価値がある）。

### F-077 solution-architect: 単一バイナリ言語での「独立機能への分割」に必要なコツが文書化されていない（中）

Go等、全機能が最終的に1つのバイナリにコンパイルされる言語では、オーケストレーター
（`habit-ui`）が仲介する型を自分の`inputs[]`/`outputs[]`に載せない、という設計判断が
必要だが、これは1本目（md-todo-cli）の設計を読んで初めて気づいたパターンで、
`CONVENTIONS.md` 6節の説明（producerの出力がconsumerの入力になる、という抽象的な言い方）
だけでは自明ではない。改修は見送り（6節への追記は`CONVENTIONS.md`のバイト予算が
逼迫しているため見送り。`docs/HARNESS_GUIDE.md`側に具体例を足す余地はある）。

### F-078 solution-architect: `design-baseline.md`（Layer 1）がWeb/GUI前提で、TUI/非GUIアプリでは手動読み替えが必要（低）

`harness/quality/design-baseline.md`の記述がWeb/GUI前提であり、TUIアプリの設計では
趣旨を手動で読み替えるしかなかった（design.mdに読み替え結果を記録）。改修は見送り
（記録のみ。非GUIアプリ全般向けの節を追加するかはbaseline自体の対象読者を広げる
大きめの変更になるため、今回のスコープ外と判断）。

### F-079 親セッション: 承認の「同じ書き込みで」という規約文言が、Editツールの単一置換制約と噛み合わない（低）

Rule 7は`status`と`approved_by`/`approved_at`を「同じ書き込みで」設定することを要求するが、
`status: DRAFT`の行と`approved_by`/`approved_at`の行が離れた`requirements.machine.yaml`/
`architecture.machine.yaml`では、Editツールが1回の呼び出しで1つの`old_string→new_string`
しか置換できないため、文字どおり「同じ書き込み」では両方を変更できない。ワークアラウンド:
先に`approved_by`/`approved_at`をnullから値に変更するEdit（この時点で`status`はまだ
`DRAFT`なのでHookは素通りする）→続けて`status: DRAFT`→`APPROVED`のEdit（この時点で
`approved_by`/`approved_at`は既に埋まっているのでHookが通る）、の2回に分けると成功する。
Hookの意図（中間状態を許さない）自体は達成されているので実害はない。改修は見送り
（記録のみ。順序を変えれば通ることが分かっているため、実害がないミスと判断）。

### F-080 feature-builder: Bashの`cd`誤操作でEdit/Writeツールのcwd追跡が復旧不能になった（高・ただしharness外の可能性）

`habit-ui`のfeature-builderが`cd <worktree> && git commit`のつもりで誤って
`cd <メインリポジトリ> && git commit`を実行し、以後**そのセッション内ではEdit/Write系
ツール呼び出しのcwdがメインリポジトリに固定されたまま戻らなくなった**（Bash側は
明示`cd`チェーンで正しいworktreeに対して実行できたが、Edit/Writeのcwd追跡は別物で
復旧できなかった）。影響でRule 2（担当範囲外ガード）が`03-features/habit-ui/`配下への
追加編集を拒否し続け、gate-reviewerのMajor指摘1件（`Store.Load`失敗時のエラー表示テスト）
に対応できないまま`TESTED`にした（実装自体は契約どおりと判断し統合フェーズの結合テストで
実地対応・解消済み）。F-063（cwd追跡が壊れることがある、という既知の制約）の再発と
見られ、Claude Code側のエージェント実行基盤の挙動である可能性が高く、`harness/`では
改修できないと判断（F-063と同じ扱い）。ワークアラウンド（`src/`編集が全部終わってから
バックグラウンド起動する）は既にF-063として`feature-builder.md`/`integrator.md`に
明記済みだが、今回のトリガーは「バックグラウンド起動」ではなく「誤ったcdの一発」だった
点が新しい。改修は見送り（harness外と判断）。

### F-081 【実地確認・Rule 11初通過】interfaces[]実地カバレッジ機械検証はGo/TUIでも期待通り機能した（記録）

このアプリで初めて`state: INTEGRATED`遷移を通り、Rule 11（`interface_coverage[]`の
機械検証）が実地を通過した。`interface_coverage[]`の宣言自体は機械的で書きやすく
（`interfaces[]`の5行をそのままコピーして`test_ids`を足すだけ）、
`run_integration_verification.py`はGoのJUnit XMLの`classname`（パッケージimport path）と
契約側の識別子を末尾一致で正しく突合した。`check_interfaces.py`（静的な契約整合）が
パスするが実地結線で問題になる差異（F-065/F-066のパターン）はGoケースでは顕在化
しなかった——3機能の型定義がいずれも`shared-kernel.yaml`の共通型をほぼ一字一句
コピーして書かれており、フィールド名・型の食い違いが最初から起きなかったため
（Goのコンパイラは型が少しでも違えばビルドが通らないため、TS/Pythonの構造的/動的型付けより
むしろ安全側に働いた）。軽微な観察: 受領書の`commit`は「status.yaml編集時点のHEAD」に
固定されるため、統合フェーズのように直後にコミットが積み重なりやすい局面では、後から
見て「これは最新の受領書か？」と一瞬迷う（実害はない。他のTESTED受領書も同じ挙動なので
一貫している）。改修不要（想定通り機能した、という確認の記録）。

### F-082 integrator: Goの名前的型付けにより、3独立モジュールの結線コードがTS/Pythonのassembly組み立てより明確に手間が多かった（中）

`habit-store`/`habit-core`/`habit-ui`は別worktree・別`go.mod`（3つの独立したGoモジュール）
として実装されたため、`04-integration/assembly/`での結線では、フィールドは完全に同じだが
名前空間が異なる3組の型（`habitui.HabitRecord`・`habitcore.HabitRecord`・
`habitstore.HabitRecord`等）の間で、明示的な詰め替え関数を8個ほど手で書く必要があった。
TS/Python（bookmark-vault/md-todo-cli）の構造的・動的型付けなら「形が同じならそのまま
渡せる」場面で、Goでは型変換コードそのものが結線コードの主要な分量を占めた。
`go.mod`の`replace`ディレクティブでの3module束ねと、`go mod tidy`が`tool`宣言を
消してしまうため`gotestsum`を都度再宣言する手順も、Node/Pythonのworkspace機構
（npm workspaces・単一venv）より一手間多かった。一方、一度書ければ`go build`/`go vet`の
型検査がその場で全結線の整合性を保証してくれる安心感はTS/Pythonより強かった
（コンパイルが通れば型不整合は無い）。改修は見送り（言語特性そのものであり
harness側で緩和する余地は薄い。将来Go向けスタックパックを書く際に「assembly結線には
型変換ヘルパーの雛形を用意する」という知見として活かせる）。

#### ★ 次の再開ポイント：F-059 着手（2026-08-23、ユーザー指示）

ドッグフーディング（ROADMAP⑩）はクローズ済みだが、ユーザーの指示で残タスク F-059
（全文は本文の `### F-059`、検索で見つかる）に着手する。**まだ着手していない
（このセッションでは計画の言語化のみ）。**

**やること**: `harness/schemas/feature-contract.schema.json` に、その機能が実際に
公開する関数/クラス名を機械可読に書ける `public_api:`（文字列配列、または
`{name, signature}` の配列）フィールドを追加する。`harness/scripts/check_interfaces.py`
（または新設のチェックスクリプト）に、`public_api:` に列挙された名前が実装の
`__all__`（Python）等と一致するかを突合するロジックを追加する——ただしこれは
**スタック依存**の検査になりうる点に注意（Python の `__all__` に相当する概念が
無い言語もある）。まずはPython（`__all__`が既にある md-todo-cli）で最小実装し、
スタック非依存に保てるか（存在しない言語では単に検査をスキップする、等）を
設計段階で決めること。

**作業の型**: `harness/fix-public-api-declaration` 等のブランチ名で
`harness/<topic>` ブランチを切り、スキーマ変更 → チェックロジック追加 → 回帰テスト
（`harness/tests/`）→ `pytest`（454件が現在の緑の基準）→ `ci_check.py` → `main`へ
`--no-ff` マージ、という「作業の型」節の手順に従う。

**着手前の確認事項**: F-059は「大きめなので見送り候補」としてユーザー確認が必要と
されていたが、2026-08-23にユーザーから直接「F-059に着手する」という指示が出た
（このファイルの直前のやり取り）ため、着手の承認は既に得られている。設計の
詳細（`public_api:`の形式・スタック非依存性の担保方法）だけ、着手前に一度
方針をユーザーに確認するとよい（大きめの変更のため）。

#### フェーズ3 完了（2026-08-23）— ドッグフーディング（ROADMAP⑩）はクローズ済み

3項目ともユーザーに`AskUserQuestion`で確認の上、同日中に完了した。

1. **worktreeクリーンアップ**: bookmark-vault 4つ・habit-tui 3つ、計7つとも全ブランチが
   `main`にマージ済み・worktree内は未コミット物ゼロであることを確認してから
   `git worktree remove`で削除した。
2. **`CONVENTIONS.md` 凍結**: ユーザーが「3本目の改修中にCONVENTIONS.mdを編集していなければ
   凍結してよい」と条件付きで許可。`git log`で確認したところ、3本目（habit-tui）関連の
   作業中は一度も`CONVENTIONS.md`を編集していなかった（最後の編集はフェーズ1のF-051/F-054/
   F-061修正）ため、条件を満たすと判断し凍結を実行した（`harness/freeze-conventions`
   ブランチ、[[conventions-md-governance]]）。冒頭に凍結の注記を追加し、`ci_check.py`に
   項目O（節の新設を拒否。15節固定）を新設、回帰テスト6件を追加（448→454）。
3. **ROADMAP⑩クローズ**: 「特に確かめたいこと」4項目すべてに答えが出たことを確認して
   `ROADMAP.md`を更新（詳細は下記「実地で確かめられたこと」参照、および`ROADMAP.md`の
   ⑩の項目自体に集約）。

#### 実地で確かめられたこと（フェーズ2で決着）

- ~~**`SUPERVISED` モードでの設計承認の親セッション一本化**（F-010 の設計版）~~ → 実地で確認済み。
- ~~**`open_issues[]` の追記**（F-044）~~ → 実地で確認済み（`git add`誤発火はF-050で解消）。
- ~~**worktree 側の PROGRESS.md 再生成**（F-038）~~ → habit-tuiの通しで自然に更新される
  ことを確認済み（各`new_feature_scaffold.py`実行・各TESTED/INTEGRATED遷移のたびに
  `PROGRESS.md`が再生成されコミットされた）。
- ~~**`applies_to`（required_skills[] の機能単位絞り込み）**~~ → habit-tuiでは
  Go向け・TUI向けいずれのSkillも存在せず`required_skills[]`が空のままだったため、
  **実地では今回も使われずじまい**（bookmark-vaultの`frontend-design`が唯一の実例のまま）。
  引き続き実地未検証。
- ~~**Rule 11（interfaces[] の実地カバレッジ）**~~ → **habit-tuiで初めて実地を通過し、
  期待通り機能することを確認した**（F-081）。3言語目・TUIという新しいUI形態でも
  問題なく動作した。

---

### 作業の型（これを守れば事故らない）

#### ハーネスを直すとき
```
git checkout -b harness/<topic>          # Rule 1 により harness/ 配下は harness/ ブランチでしか触れない
（修正）
uv run --python 3.12 --with pytest --with pyyaml --with jsonschema python -m pytest harness/tests -q
python3 harness/scripts/ci_check.py      # ベースは自動解決される（--base は不要になった）
git add -A && git commit
git checkout main && git merge --no-ff harness/<topic>
```

- **`CONVENTIONS.md` は 36000 バイト上限**（項目 L）。2026-08-23 時点で 35993 バイトで
  **残り 7 バイトしかない**（Rule 11 追加時、`既知の限界` 節を `docs/HARNESS_GUIDE.md` 側の
  既存記述に一本化して捻出した）。
  追記するなら、同時に何かを `docs/HARNESS_GUIDE.md` か `harness/README.md` へ移すこと。
  超えると `ci_check.py` と `test_context_budget.py` が落ちる。
- **規約を追記する前に 15節「何をどこに書くか」を読む。** 手順は agent/skill 側、規範は
  `CONVENTIONS.md` 側。二重に書くと `ci_check.py` の項目 M が落ちる（F-048）。
- 判定ロジックを変えたら**必ず回帰テストを追加**する。追加先は
  `harness/tests/test_dogfooding_fixes.py`（ドッグフーディング由来）か
  `harness/tests/test_worktree_scope.py`（`.worktrees/` 経由のパス判定）。

#### 機能を実装させるとき（`feature-builder`）
1 セッションからは**逐次でしか回せない**（並行実装は機能ごとに別ターミナルが必要）。
```
EnterWorktree(path: "<repo>/apps/md-todo-cli/.worktrees/<feature-id>")
Agent(subagent_type: "feature-builder", ...)   ← cwd を継承して Rule 2 を通る
ExitWorktree(action: "keep")                    ← remove は絶対に使わない
```
- **メインセッションから直接 subagent を起動しても Rule 2 に弾かれる**（F-031）。
- 依頼文には必ず「最終報告の末尾に `## 摩擦点` を書く」ことを入れる。これが主成果物。
- **受け取ったらすぐこのファイルに追記する**（コンテキストリセットで失われるため）。

#### 統合させるとき（`integrator`）
メインの worktree（リポジトリ本体）で動かす。全機能が TESTED になってから。
`architecture.machine.yaml` の `interfaces[]` に基づいて結線する。

### 環境（この環境固有・重要）

- `python3` に **pip は無い**（Ubuntu system python / PEP 668）。`uv` を使う。
- ハーネス自己テスト:
  `uv run --python 3.12 --with pytest --with pyyaml --with jsonschema python -m pytest harness/tests -q`
- アプリのテスト（`todo-file-store` の例、feature ディレクトリで実行）:
  `PYTHONPATH=src uv run --python 3.12 --no-project --with 'pytest==9.1.*' python -m pytest tests -q`

### 踏んではいけない地雷（実際に踏んだもの）

1. **orphan ブランチを作らない。** `git checkout --orphan` + `git rm --cached .` をやると
   全ファイルが「変更」扱いになり、事後検証ガードが**全件巻き戻しを実行する**。
   実際に起こして `git checkout -f` で復旧した。ガードの挙動を試すなら
   **隔離した一時 git リポジトリ**（`tmp_path` に `git init`）で単体テストにする。
2. **worktree 隔離セッションでは複合 Bash コマンドが拒否される。**
   ヒアドキュメント（`cat > f <<'EOF'`）、`;` 連結、`git -C .` はすべて実行前に弾かれる。
   1 コマンドずつ単純な形にするか、Write/Edit ツールを使う。
3. **受領書 → `TESTED` は 1 コミットにまとめる。**
   実装をコミット → 検証 → **コミットせずに** `TESTED` → 最後に 1 回コミット。
   受領書を書いた `status.yaml` を先にコミットすると HEAD が進んで Rule 10 に弾かれる。
4. **feature worktree 3 つは、ハーネス改修より前の main から切られている。**
   worktree 内の `harness/scripts/*` は古い。`run_verification.py` 等は
   **リポジトリ本体側のパスで呼ぶ**か、先に worktree を現在の main にマージすること。

### subagent の報告を取りこぼしたときの回収方法

トランスクリプトは `<scratchpad>/tasks/<agentId>.output`（JSONL）。**全文を読むとコンテキストが溢れる。**
最後の assistant テキストだけを Python で抜き出し、「摩擦点」以降を表示する:

```python
import json, pathlib
last = None
for line in pathlib.Path(PATH).read_text(errors="replace").splitlines():
    try: o = json.loads(line)
    except Exception: continue
    m = o.get("message") or o
    if m.get("role") == "assistant" and isinstance(m.get("content"), list):
        txt = "".join(b.get("text","") for b in m["content"] if b.get("type")=="text")
        if txt.strip(): last = txt
i = last.find("摩擦点"); print(last[max(0,i-200):])
```

---

### F-047 コンテキスト予算が飽和していて、規約への追記が構造的に困難（中）→ **改修済み**

**今回の改修で最も時間を食ったのは、コードでもテストでもなく「規約を書く場所の捻出」だった。**

項目 L は `CONVENTIONS.md` 単体 36000 バイト、`CONVENTIONS.md + 各 agent 定義` 46000 バイトを
上限とする。改修前の時点で `CONVENTIONS.md`(35813) + `solution-architect.md`(10180) = 45993 で、
**上限まで残り 7 バイト**だった。Rule 3・Rule 7 に 1 文ずつ足すだけで、
7節の worktree 読み替えの段落・12節の背景説明・10節の設計意図などを `docs/HARNESS_GUIDE.md` へ
退避する作業が必要になった（今回の改修で計 8 箇所を圧縮・移設した）。

予算強制そのものは設計どおり働いている（前回の通しでも実証済み）。問題は**予算が飽和した状態から
先に進む道が用意されていない**ことだった。

**根本原因は「項目 L の計算モデルが古かった」こと。** `requirements-analyst`・`solution-architect`
は「`harness/CONVENTIONS.md` を最初に読み、規約を把握してください」という**全 15 節ブランケット
読み込み**の指示を持っていたが、実際に使うのはそのうち数節だけだった（`requirements-analyst` に
至っては、自分の手順書だけで完結しており **CONVENTIONS.md を一切必要としない**ことが判明した
——独立機能の設計原則（6節）・検証コマンド宣言（12節）等は明確に他フェーズの話）。
一方 `feature-builder`/`integrator`/`gate-reviewer` は元々ブランケット読み込みをしておらず
（本文中で `CONVENTIONS.md N節` と根拠を引用するだけ）、項目 L の計算式
`CONVENTIONS.md 全体 + 最大の agent プロンプト` はこの非対称を無視し、**全 agent が全文を
読む前提で一律に計算していた**——ユーザーからの指摘で発覚した。

→ 改修（ユーザー指摘・`harness/lean-context`）:
- `harness/scripts/print_conventions.py` を追加。`## N. 見出し` で節を切り出して表示する。
  `CONVENTIONS.md` は単一情報源のまま複製しない（1節冒頭の注意書きに従う）。
- `requirements-analyst`: ブランケット読み込みを撤去（自己完結のため 0 節）。
- `solution-architect`: `python3 harness/scripts/print_conventions.py --sections 6,9,10,11,12,13,14`
  に変更（15 節中 7 節だけ）。
- `diff-design` skill: 同様に 11 節だけを抜き出す形に変更。
- `feature-builder`/`gate-reviewer`/`integrator` はもともと全文読み込みをしていなかったが、
  項目 L の判定にその事実を伝える手段が無かったため、`none` マーカーを追加。
- 各 agent 定義の frontmatter 直後に `<!-- context-budget: conventions-sections=... -->`
  マーカーを追加し、`ci_check.py` の項目 L はこのマーカーを見て「実際に読む節」だけを
  計上するように変更（マーカーが無いエージェントは従来どおり全文読み込みとみなす安全側の
  フォールバック）。

**結果**: 各 agent の実効消費（自身のプロンプト + 読み込む CONVENTIONS.md 相当）が
`feature-builder` 45909→10743、`solution-architect` 46163→30050 バイトに縮小。
**最悪ケース（session 予算 46000 上限に対して）が 46163（超過）→ 30050 に下がり、
次の改修のための余裕が戻った。** 回帰テスト 9 件（`print_conventions.py`）+ 8 件
（マーカー判定ロジック）を追加。

### F-048 CONVENTIONS.md と agent プロンプトの二重管理（高）→ **改修済み**

**ユーザー指摘**:「CONVENTIONS.md と agents の指示文に重複が存在するなら保守性に問題がある。
どちらかに寄せるべきでは」。全 agent/skill を機械的に突き合わせた（文字 3-gram の
Jaccard 類似度）結果、重複は実在し、**既に実害が出ていた**。

**実証した drift**: F-011/F-020 の改修で Rule 7 に承認記録の同時性を足したとき、
`CONVENTIONS.md` 9節と `solution-architect` は直したが、同じ手順を複製していた
`diff-design` skill を直し忘れていた。その結果 **`diff-design` の手順9 のとおりに実行すると
Hook が exit 2 で拒否する**状態になっていた（隔離した一時 git リポジトリで実証。
修正後は exit 0 で通ることも確認）。二重管理が原因の典型的な drift。

**検出した重複**:

| 重複箇所 | 相手 | 類似度 |
|---|---|---|
| `feature-builder` 10.5（受領書→TESTED の順序。ASCII 図ごと） | 12節 | 0.88 |
| `diff-design` 手順 1〜9 | 11節 手順 1〜6 | 0.28〜0.36 |
| `solution-architect` 手順11（`required_skills[]` の記録） | 10節 Layer 2 | 0.24（目視で確認） |
| `requirements-analyst` の承認説明 | 9節 | 言い換えのため機械検出外 |

**採用した方針（`CONVENTIONS.md` 15節に明文化）**: 「どちらかに全部寄せる」ではなく
**内容の種類で切る**。規範（何が真であるべきか）と手順（誰がどの順でやるか）は別物で、
後者を `CONVENTIONS.md` に書いた結果が 11節×`diff-design` の二重管理だったため。

- Hook/CI が機械的に強制する規範 → `CONVENTIONS.md` だけ。agent は節番号で参照する
  （違反すれば Hook が止め、**そのエラーメッセージが直し方を示す**ので agent 側に写す必要がない）
- 機械では強制できない規範 → `CONVENTIONS.md` に宣言だけ置き、従わせる指示は agent に書く
- フェーズ固有の手順 → 実行する agent/skill だけ。`CONVENTIONS.md` には書かない

**再発防止**: `ci_check.py` に**項目 M**（二重管理の検出）を追加。`CONVENTIONS.md` と
agent/skill プロンプトの段落を突き合わせ、ほぼ同一なら不合格にする。閾値 0.28・正規化後
100 文字以上とし、コマンド 1 行のような短い断片と、一般則をフェーズ向けに具体化した記述
（`solution-architect` が `MANUAL`/`SUPERVISED` を設計フェーズの言葉で言い直す等＝正当な役割分担）
には掛からないよう調整した。**導入前に現リポジトリで 4 件を検出することを確認してから解消した**
（空振りでないことの実証）。

**意図的に残した重複**: `requirements-analyst` の「承認は親が確定させる」の理由説明。
この agent は `CONVENTIONS.md` を 1 節も読まない設計であり、かつこの規範は機械強制できない
（F-010 の再発は理由を理解しているかどうかに懸かる）。方針の「機械では強制できない規範は
agent に指示を書く」に合致するため残した。項目 M の閾値にも掛かっていない。

**残った検討事項**: 項目 M は近似コピー（言い換えを伴わない転記）しか捕まえられない。
言い換えられた意味的な重複は人間の判断が要る。閾値 0.24〜0.28 のグレーゾーンが存在する
ことは認識したうえで、ノイズで無効化されるより取りこぼす側に倒している。

---

## 摩擦点一覧

深刻度: 最高 / 高 / 中 / 低

### F-001 セットアップ手順が環境で成立しない（中）
`harness/README.md` は `pip install -r harness/requirements.txt` を案内するが、この環境の
python3 には pip が無く pytest が入らない。`uv run --with pytest ...` でなら通る（310 passed）。
→ README に uv / venv でのフォールバック手順を併記する。

### F-002 【実証済み】受領書ヘッダコメントが再実行のたびに増殖する（低〜中）
`run_verification.py:write_receipt()` は `RECEIPT_BLOCK_RE` で `verification_receipt:` ブロック
だけを削除して末尾に `header + block` を再追記する。header（`# ...手書き禁止` の 2 行コメント）は
行頭 `#` で始まりブロック正規表現にマッチしないため削除されず、**再実行のたびに 2 行ずつ蓄積する**。
`write_receipt()` を 3 回呼ぶとヘッダが 6 行になることを実証済み。
`harness/tests/test_verification.py` はこれを検出できていない（回帰テストの穴）。
→ header をブロックごと削除する正規表現にするか、YAML 全体を再構築する。

### F-003 アプリ用ブランチを誰も作らない（中）
`CONVENTIONS.md` 3節は `app/<app-id>/bootstrap` を規定するが、`init-app` skill にも
`new_app_scaffold.py` にもブランチ作成のステップが無い。main 直コミットで進んでしまう。
→ init-app skill にブランチ作成を明記するか、scaffold で確認・作成する。

### F-004 subagent に AskUserQuestion が実際には渡らない（高）
`requirements-analyst` の frontmatter は `AskUserQuestion` を宣言し本文もその使用を指示するが、
実行された subagent は「付与されたのは Read / Write / Edit / Bash のみ」と報告。
`solution-architect` の手順 11（required_skills の確認）も同じ前提に立っている。
→ 実証したうえで、使えないなら「最終メッセージで承認を求める」方式に一本化する。

### F-005 「承認待ちで停止」と Rule 8（未コミット停止拒否）の噛み合わせが未文書化（中）
承認待ちで応答を終える設計なのに、Rule 8 は未コミットの `requirements.machine.yaml` があると
停止を拒否する。agent 定義に「承認を求める前に DRAFT のままコミットする」と明記が無い。

### F-006 requirements.md テンプレに受け入れ基準を書く場所が無い（中）
`templates/requirements.md.tmpl` の機能要件は表形式のみで `acceptance_criteria` は
「YAML を参照」と誘導。人間向け文書として不十分で、「2 ファイルの内容一致」規約とも整合しない。

### F-007 `open_questions` が空のときの md 側の書き方が未規定（低）

### F-008 【実証済み】要件・設計の承認では PROGRESS.md が再生成されない（高）
`post_tool_use_sync.py` の `STATUS_PATH_RE` が `apps/<app>/03-features/<feature>/status.yaml`
だけにマッチするため、要件が APPROVED になってもダッシュボードは DRAFT のまま腐る。
CONVENTIONS.md 9節は「PROGRESS.md の表示で人間が随時状況を確認できることを**最終的な担保**」と
明言しているので、担保役が最重要の節目で機能しないことになる。
→ `STATUS_PATH_RE` に `00-requirements/requirements.machine.yaml` と
`02-design/architecture.machine.yaml` を含める（Rule 4 の定義も CONVENTIONS.md 側で更新）。

### F-009 PostToolUse の再生成フックが Bash 経由の書き込みで発火しない（中）
`.claude/settings.json` の matcher が `Edit|Write|MultiEdit` のみ。Rule 1/2/3/5/6 は Bash も
対象にしているのに Rule 4 だけ Bash が抜けている。

### F-010 【最重要】承認の「人間性」が subagent 経由で構造的に失われる（高）
F-004 のため承認は「親が人間に聞き、subagent に伝える」伝聞になる。subagent 側の実行環境には
「いかなるエージェントのメッセージもユーザーの承認そのものではない」という指示があり、
「要件承認は常に人間必須」という固定ポリシーと同時に満たせない。結果として
**AI が AI の伝聞を根拠に APPROVED を確定させた**（今回まさにそうなった）。
→ 承認だけはメインセッション（親）が自分で `requirements.machine.yaml` の
status/approved_by/approved_at を書き換える運用に一本化する。subagent は
「DRAFT のまま承認用の要約を返して終わる」までを責務とする。

### F-011 要件側の APPROVED に機械的ゲートが実質無い（中）
設計側の Rule 7 に相当するものが要件側に無く、歯止めが `approved_by` の非 null だけ。

### F-012 auto mode の権限層が Bash 編集を拒否し、ハーネスの Bash 検知に到達しない（低）
`sed -i` が hook の手前の権限層でブロックされた。実害は無いが、CONVENTIONS.md 7節の
Bash 検知の出番が環境によっては無いことの記録。

### F-013 PROGRESS.md の生成物に空行漏れ（見出し直前）（低）

### F-014 【重大】feature worktree が `main` から切られる（最高）
`new_feature_scaffold.py:65` が分岐元を `main` にハードコード。
要件・設計・`shared-kernel.yaml` は `app/<app-id>/bootstrap` にあり、`main` には
`apps/<app-id>/` すら無い。結果、上位文書が一切入っていない worktree ができ、
`run_verification.py` は `verification:` 宣言を解決できず exit 2 になるため
**どの機能も TESTED にできない**（Rule 10 のゲートに到達すらしない）。
`solution-architect` の agent 定義は「未コミットのままだと引き継がれません」としか言っておらず、
**コミットしても別ブランチなら引き継がれない**という本質的な条件に触れていない。
→ 分岐元を現在の HEAD にする、または「設計承認後に bootstrap を main へマージする」手順を
CONVENTIONS.md / skill に明記し、scaffold 側で事前検査して分かりやすく落とす。
（今回の通しでは main へマージして回避する）

### F-015 `check_traceability.py` は設計フェーズでは実質何も検証しない（高）
`load_contracts()` が `03-features/*/contract.yaml` しか読まないため、worktree 作成前は
契約が `None` 扱いでスキップされ、`coverage[]` が空でも「OK」と出る。
`check_interfaces.py` は `02-design/features/*.contract.yaml` も読む（両方読む実装が既にある）
のに非対称。agent 定義は設計フェーズでの実行を指示しているので、**指示どおりやると偽の安心を得る**。

### F-016 `ci_check.py` の項目 D が、設計フェーズを 1 ブランチで完結させると必ず不合格（高）
`check_contract_freeze()` が差分に `02-design/features/*.contract.yaml` を含むかを見て、
**現在の** `architecture.machine.yaml` が DRAFT でなければ違反にする。
「契約を書く → 承認する」を同一ブランチで行うのが正常フローなので false positive が必ず出る（再現済み）。
→ ベース時点の architecture の status で判定するか、承認コミットより前の変更を除外する。

### F-017 `ci_check.py` のベース解決が `origin/main` 固定でローカル運用と噛み合わない（中）
`resolve_base()` が `merge-base origin/main HEAD` を使うため、ローカル main が未 push だと
**自分が触っていない harness ファイル 38 件が Rule 1 違反として報告される**。
`--base main` で回避できるがその案内がどこにも無い。

### F-018 `shared-kernel.yaml` の `common_types` が実質的に飾りになる（中）
`check_interfaces.py` が JSON Schema の `$ref` を解決しないため、共通型を `$ref` で参照すると
機械検証が効かない。全契約に型をインライン展開してコピペする必要があり、
「共有カーネルに集約する」という 6節の主旨と実装が食い違う。テンプレにも注意書きが無い。

### F-019 受入基準が end-to-end 文なのに契約は機能単位で、分担ルールが無い（中）
1 つの受入基準が複数機能にまたがるのに、`coverage[]` は機能ごとに書く。
`check_traceability.py` は FR 単位で 1 件でもあれば通すため事実上ザル。
`04-integration` 側にトレーサビリティの受け皿が無いことも影響している。

### F-020 Rule 7 は `status: APPROVED` と `approved_by` の同時性を見ていない（中）
`status: DRAFT → APPROVED` だけを先に Edit した中間状態（`approved_by: null`）が Hook を素通りした。
9節は「スキーマレベルで強制する」と書くが、書き込み時点では強制されていない。

### F-021 Bash 経由の書き込みは Rule 7・9・10 を回避できる（高）
7節に明記されている既知の限界だが、auto モードのように**原則 Bash で書き込む運用**では
`sed -i` で `status: APPROVED` にすれば Rule 7 は一度も走らない。
決定論的強制を謳う以上、書き込み手段しだいで穴が開くのは設計上の弱点。

### F-022 PROGRESS.md / STATE.machine.yaml がタイムスタンプだけで毎回 dirty になる（中）
再生成のたびに `生成日時:` / `generated_at:` の 1 行だけが変わり、余分なコミットが要る
（実際 1 コミット消費した）。`ci_check.py` はこの行を無視して比較しているので、
そもそもファイルに書き出す必要が薄い。

### F-023 `verification:` を設計フェーズで試す手段が無い（中）
`run_verification.py --dry-run` は `03-features/<feature-id>/status.yaml` の存在を前提とするため、
worktree 作成前＝宣言する場所では使えない。「宣言しっぱなしにするな」と要求される一方、
試す道具が無い。→ `--check-only` 相当の入口が要る。

### F-024 `test_command` 未宣言の不可逆性が過小に読める（中）
テンプレと 12節は「TESTED にできない」とするが、実際は `feature-builder` は
`shared-kernel.yaml` を書き換えられない（Rule 6）ので**実装フェーズでは回復不能**。
CONVENTIONS.md 12節にその不可逆性まで書くべき。

### F-025 スタックパックの探し方が定義されていない（中）
`harness/STACK_PACK.md` は「あれば登録せよ」と規定するが**どこを探すか**が一切書かれていない。
存在しない `plugin_ref` を書くと Rule 5 が実装を完全にブロックするため、安全側の判断しかできず、
結果として 14節の仕組みは事実上使われないまま終わる。

### F-026 テンプレの `lint_command: "ruff check ."` は地雷（軽微）
ruff 0.16 で既定の有効ルールが 59 → 413 に激増しており、素朴に宣言するとランナー更新で
ゲートの意味が勝手に変わる。→ 例示を `--select` で明示的に絞った形にする。

---

## 設計フェーズで確認できた「ちゃんと動いたこと」

- `check_interfaces.py`: OK。一時コピーで `required` と `enum` を意図的に壊すと検出されることも
  確認済み（空振りでないことの確認が取れている）
- `verification:` の 2 コマンドを probe ディレクトリで実際に実行して exit 0 を確認。
  JUnit XML も生成され、`junit_utils` が `tests/test_x.py::test_y` 形式の宣言と照合できることも確認
- 実行時のサードパーティ依存は 0 件（標準ライブラリのみ）、`required_skills: []`
- `validate_yaml.py`・スキーマ・書き込みガードは指示どおり動作した

---

## 摩擦点（機能実装フェーズ / 2026-08-22 追記）

### F-027 【実証済み】ハーネス自身の scaffold が、ハーネス自身が禁じる状態遷移を記録する（中）
`new_feature_scaffold.py` が生成する `status.yaml` の `state_history[]` は
`NOT_STARTED` → `CONTRACT_APPROVED` の 2 段飛ばしになっている（`CONTRACT_DRAFTED` を飛ばす）。
これは CONVENTIONS.md 5節「直線状態は1段階前進のみ許可」に反しており、実際
`validate_status_transition.py NOT_STARTED CONTRACT_APPROVED` は exit 1 で拒否する。
Rule 9 は Edit/Write の前後比較でしか働かないため、Python スクリプトからの書き込みは素通りする。
→ scaffold が `CONTRACT_DRAFTED` を経由した履歴を書くか、5節に「scaffold による初期化は例外」と
明記する。**規約と実装のどちらが正なのかが決まっていないのが問題。**

### F-028 `new_feature_scaffold.py` はダッシュボードを再生成しない（中）
`new_app_scaffold.py` は `render_progress.py` を呼ぶのに、`new_feature_scaffold.py` は呼ばない。
Rule 4 は Edit/Write でしか発火しない（F-009）ので、worktree を 3 つ作っても
`PROGRESS.md` は「機能はまだ登録されていません」のまま。手動で再生成が必要だった。
→ scaffold の最後で `render_progress.py` を呼ぶ。

### F-029 【実証済み・重大】`.worktrees/` を通るパスでは Rule 2・3・5・10 が一切発火しない（高）
`pre_tool_use_guard.py:29` の
`FEATURE_SCOPE_RE = ^apps/([^/]+)/03-features/([^/]+)/(.*)$`
は **worktree 相対パスの先頭にアンカーされている**。ところがハーネス自身が規定する worktree の
実体パスは `apps/<app>/.worktrees/<feature-id>/apps/<app>/03-features/<feature-id>/...` であり、
メインの worktree から見るとこの正規表現に**一度もマッチしない**。

実証: メインリポジトリのルート（worktree ルート basename = `apparness`）から
```
echo probe > apps/md-todo-cli/.worktrees/todo-file-store/apps/md-todo-cli/03-features/todo-file-store/src/__probe__.py
```
が **exit 0 で成功した**。Rule 2（担当外ガード）は「worktree ルートの basename が feature-id と
一致しない限り拒否」と規定しているので、本来は拒否されるはずの書き込みである。

同じアンカーを共有する `FEATURE_CONTRACT_RE`（Rule 3 契約凍結）・`FEATURE_SRC_RE`（Rule 5 必須Skill）・
`STATUS_YAML_RE`（Rule 9/10 状態遷移・検証受領書ゲート）も同様に発火しない。
つまり **メインセッションからは、どの機能の契約でも status.yaml でも自由に書き換えられ、
`state: TESTED` すら受領書なしで書ける**（未実証だが同じ経路）。

さらに `post_tool_use_guard.py` の事後検証も、`.worktrees/` がメインリポジトリの
`.gitignore` 対象であるため `git status` に現れず、巻き戻しが働かない。
**静的検知と事後検証の二段構えが、どちらもこの経路では機能しない。**

→ 改修案: worktree 相対パスではなく「`03-features/<feature-id>/` を含むか」で判定する
（`^(?:.*/)?apps/([^/]+)/03-features/([^/]+)/(.*)$` 相当）。あるいは書き込み先の絶対パスから
実際の worktree ルートを解決し直して basename を突き合わせる。

**この 1 件だけで、ハーネスが最も強く主張している「決定論的強制」の中核が空振りしている。**
ドッグフーディング以外では絶対に見つからない種類の欠陥（`apps/` が空なら `.worktrees/` も存在しない）。

### F-030 【実証済み・最高】受領書なしで `state: TESTED` を書き込めた
F-029 の帰結を、ハーネスが最も強く主張しているゲートで直接確認した。

メインセッション（worktree ルート = リポジトリ本体）から **Edit ツール**で
`apps/md-todo-cli/.worktrees/todo-file-store/.../status.yaml` の
`state: CONTRACT_APPROVED` を `state: TESTED` に書き換えたところ、**そのまま成功した**。

本来は 2 つの Rule が独立に拒否するはずだった:
- **Rule 9**（状態遷移）: `CONTRACT_APPROVED` → `TESTED` は `IN_PROGRESS`・`IMPLEMENTED` を
  飛ばす 3 段飛ばしで、`validate_status_transition.py` は同じ遷移を exit 1 で拒否する
- **Rule 10**（検証受領書ゲート）: `verification_receipt` が存在しないので拒否されるはず

どちらも発火しなかった。原因は F-029 のパスアンカー（`STATUS_YAML_RE` が
`.worktrees/` を通るパスにマッチしない）。Bash 経由ではなく**構造化ツール呼び出しでの実証**なので、
「Rule 7・9・10 は Edit/Write の前後比較に依存する」という 7節の但し書きでは説明がつかない、
**純粋な実装バグ**である。

CONVENTIONS.md 12節は「**`commit` の一致条件が本質**——これが無ければ実装を書き換えた後も
過去の成功記録を使い回せる」と書いているが、実際には受領書そのものが無くても通る。
README の「AI の自己申告には頼っていません」という主張も、この経路では成立していない。

（実証後、`status.yaml` はバックアップから復旧済み。worktree はクリーン。）

---

## 改修記録

### F-029 / F-030 — 修正済み（`harness/fix-worktree-path-guard`）
`path_utils.resolve_worktree_scope` を追加し、`.worktrees/` を通るパスを
**パスとルートの両方**その worktree 基準に読み替えてから Rule に掛けるようにした
（パスを剥がすだけでは、各 Rule が参照する status.yaml / contract.yaml / shared-kernel.yaml が
別ファイルを指してしまうため）。適用先は `pre_tool_use_guard`（Bash・構造化ツールの両経路）・
`post_tool_use_guard`（判定は読み替え後、巻き戻しは元のパス）・`post_tool_use_sync`。
worktree の中から書いている場合は恒等写像になるため、既存の動作は変わらない。

修正後、同じ攻撃経路を再実行して次を確認した:
- メインセッションから他機能の `src/` への Bash 書き込み → **Rule 2 が拒否**
- `CONTRACT_APPROVED` → `TESTED` の3段飛ばし → **Rule 9 が拒否**
- 正規に `IMPLEMENTED` まで進めてから `TESTED` → **Rule 10 が「`verification_receipt` が無い」で拒否**

回帰テスト 10 件を `harness/tests/test_worktree_scope.py` に追加（合計 320 件が緑）。
CONVENTIONS.md 7節にも読み替えの規定を追記した。

### F-031 【実証済み】`feature-builder` を subagent として起動する経路が存在しない（高）
ハーネスは機能ごとに worktree を切り、`feature-builder` を **subagent** として定義している
（`.claude/agents/feature-builder.md`）。しかし Rule 2（担当外ガード）は
「セッションの worktree ルートの basename が feature-id と一致すること」を要求するため、
メインセッションから起動した subagent（cwd = リポジトリルート）は**どの機能も実装できない**。
F-029 の修正でガードが正しく効くようになった結果、この齟齬が表面化した。

subagent 側から `EnterWorktree` で worktree に移れるかを実地で検証したところ、拒否された。
エラー全文:
```
Cannot enter worktree: the current working directory <repo root> is the repository root,
not an isolated worktree — switching is only available to sessions whose working directory
is inside a worktree of this repository.
```
拒否理由は worktree の**置き場所ではなく、起動時の cwd がリポジトリルートであること**。
`apps/<app>/.worktrees/` に置いているからではないので、置き場所を変えても解決しない。

残る経路は「メインセッション自身が `EnterWorktree` で worktree に入ってから subagent を起動し、
subagent に worktree の cwd を継承させる」のみ（メインセッションからの初回入場は成功する）。
ただしセッションは同時に 1 つの worktree にしか入れないため、**3 機能の並行実装は
1 セッションからは不可能**で、機能ごとに逐次実行するか、`new-feature-worktree` skill が案内する
とおり人間が機能ごとに別ターミナルでセッションを起動するしかない。

→ 改修案: (a) `feature-builder` を「subagent」ではなく「worktree で起動する専用セッションの
役割」として文書上も位置づけ直す、(b) `new-feature-worktree` skill の案内を
「別セッションが必須である」と明示的にする（現状は「案内する」に留まり、subagent でも
できるかのように読める）、(c) 1 セッションで回したい場合の手順（EnterWorktree で入ってから
逐次実行）を CONVENTIONS.md に明記する。

---

## 摩擦点（実装フェーズ: todo-file-store / 2026-08-22）

**前提の確認**: メインセッションが `EnterWorktree` で worktree に入ってから `feature-builder`
subagent を起動すると、Rule 2 を通って実装できることを実証した（F-031 の唯一の回避経路）。
機能は `TESTED` まで到達。受領書は test/lint とも exit 0、テスト 38 件・スキップ 0、
宣言テスト識別子 7/7 が JUnit XML と一致。親セッションが独立にテストを再実行しても 38 passed。
受領書以降に変わったのは `status.yaml` のみで、CI 項目 I の等価条件も満たしている。
**ハーネスの検証ゲートは、正しい経路で使えば主張どおりに機能する**ことがここで初めて実証された。

### F-032 【実証済み】worktree 隔離セッションで複合 Bash コマンドが拒否される（中）
`cat > path <<'PY' ... PY` や、`;` で複数コマンドを繋いだだけの単純な確認コマンドが
```
This session is isolated in the worktree ..., but this command is too complex to verify
that it stays inside the worktree. Refusing to run it
```
で拒否される。`git -C . branch --show-current` すら「実行時に計算されるディレクトリを指している」
として拒否された（`-C .` は自分自身なのに）。親セッションでも再現した。
Claude Code 側の機構でハーネスの問題ではないが、**「Bash を優先せよ」という運用方針と正面から
衝突する**ため、worktree で作業する前提のハーネスとしては影響を受ける。
→ agent 定義に「worktree 内では Write/Edit ツールを使う」と明記しておくのが現実的。

### F-033 【重要】受領書とコミットの順序が罠になっており、Rule 8 と噛み合わない（高）
agent 定義は「実装をコミットしたうえで検証を実行」としか書いていない。しかし受領書を書いた
`status.yaml` をコミットすると HEAD が進み、`receipt.commit != HEAD` になって Rule 10 に弾かれる。
正しい順序は「実装をコミット → 検証 → **コミットせずに** `TESTED` へ変更 → 最後に一括コミット」。
素直に読むと 1 往復無駄になる（実際に無駄にした）。
さらに **Rule 8（Stop 時に `status.yaml` の未コミットを拒否）があるため「コミットせず保持したまま
応答を終える」ことができず、両ルールが構造的に噛み合っていない**。
→ CONVENTIONS.md 12節に正しい順序を明記し、agent 定義にも書く。Rule 8 との関係も整理する。

### F-034 F-002 の実地再現（受領書ヘッダの重複）（低〜中）
コード読みで見つけた F-002 が実運用でも発生。2 回実行で「手書き禁止」ヘッダが 2 組になり、
実装者が手で 1 組に戻す作業が発生した。

### F-035 `ci_check.py` の項目 G が、実行するだけでワークツリーを汚す（中）
`check_progress_freshness` が `render_progress.py` を実行して `PROGRESS.md`/`STATE.machine.yaml` を
**その場で書き換え**、比較後に元へ戻さない。feature ブランチでは項目 C（担当範囲外）に該当する
ファイルが未コミットで残り、`git checkout HEAD --` での復旧が必要だった。
→ 一時ディレクトリに生成して比較する。

### F-036 【重要】項目 G と項目 C（Rule 2）が feature ブランチ上で両立しない（高）
`status.yaml` を進めるたびに `PROGRESS.md`/`STATE.machine.yaml` の再生成が必要（項目 G）だが、
feature ブランチがそれをコミットすると項目 C で「担当範囲外」になる。
つまり **feature ブランチの HEAD は構造的に項目 G を満たせない**。
→ 項目 G を feature ブランチでは判定しないか、integrator が直す前提を CONVENTIONS に明記する。

### F-037 F-017 の実地再現（`ci_check.py` のベースが `origin/main` 固定）（中）
ローカルの `origin/main` が古いため、main 側の harness コミットが全部
「このブランチが `harness/**` を変更した」と誤検出された（今回 71 ファイル・数十件）。
**本物の違反が埋もれるので、feature-builder の自己チェックには使えなかった。**
`--base` に merge-base を渡せば回避できるが docstring から読み取れない。

### F-038 Rule 4 の進捗再生成が worktree 側に反映されない（中）
フックは `find_main_repo_root` で**メインリポジトリ側**の `PROGRESS.md` を再生成するため、
worktree 内の `PROGRESS.md`/`STATE.machine.yaml` は scaffold 直後のまま（`features: []`）。
担当者が自分の worktree で進捗を見ても何も映らない。しかもメイン側に出た差分は
feature ブランチからは範囲外で誰もコミットできない状態で残る。

### F-039 feature 契約に承認者の強制が無い（中）
`contract.yaml` が `approved_at: null` / `approved_by: null` のまま `status.yaml` は
`CONTRACT_APPROVED`。requirements / architecture はスキーマで「APPROVED なら承認者必須」を
強制しているのに feature 契約にはその強制が無く、**Rule 3（契約凍結）の根拠が機械的に確かめられない**。

### F-040 `status.yaml` の `contract_version` を誰がいつ埋めるのか未定義（低）
scaffold 時 `null` のままで、CONVENTIONS にも agent 定義にも記述が無い。実装者が自己判断で埋めた。

### F-041 補助スクリプトの引数体系が不揃いでエラーが不親切（中）
`validate_yaml.py` だけ `--app` ではなく位置引数 2 つ。`--app md-todo-cli` を渡すと
`エラー: --app が存在しません`（＝ファイル名として解釈）という原因の分かりにくいメッセージが出る。
`validate_status_transition.py` も、CONVENTIONS 5節の説明からは位置引数
`old_state new_state` が必須だと読み取れない。

### F-042 CONVENTIONS 4節の cwd 規約と実際のセッションがずれている（低）
規約は `.worktrees/<fid>/apps/<app>/03-features/<fid>/` を cwd にせよと書くが、
実際のセッションは worktree ルートで始まる（どちらでも動作はする）。

### F-043 `max_skip_ratio: 0.0` と環境依存テストの相性が悪い（中）
「権限が無くて読めない」ケースは root では再現できないが、`pytest.skip` を使うと
スキップ率 0 の宣言に触れて `TESTED` に進めなくなる。結果、テスト内に
「root なら errno を注入する」分岐を持たせることになった。この副作用はどこにも書かれていない。

### F-044 凍結された契約の小さな穴を記録する場所が無い（中）
gate-reviewer の Major 指摘 2 件はどちらも契約側でしか閉じられず、実装者は `SPEC.md` に
書くしかない。`SPEC.md` は機械検証の対象外なので統合時に拾われる保証が無い。
→ 契約に追記だけ許す `open_issues[]` のような欄があるとよい。

### F-045 `code-review` skill と「subagent を勝手に起動しない」方針が衝突する（中）
`code-review` skill は 8 つの subagent 起動を前提にしているが、実行側の方針は
「ユーザーが明示的に求めない限り subagent を起動しない」。今回は skill 内の代替手順に従って
8 観点を自分のコンテキストで実施した。agent 定義が `code-review` の実行を必須にしている以上、
どちらの運用を期待するのか明記が要る。

### F-046 `.ruff_cache` が `.gitignore` に無い（低）
ruff 自身が `.ruff_cache/.gitignore` に `*` を書くため今回は実害ゼロだったが、
`.verify/` `.pytest_cache/` `__pycache__/` を明示しているのにここだけ抜けている。

### 第1〜3弾（`harness/dogfooding-fixes`）— 18 件を改修

| ID | 内容 | 検証方法 |
|---|---|---|
| F-014 | worktree の分岐元を `main` 固定から HEAD に。上位文書 3 点が分岐元のコミットに含まれるか `git ls-tree` で事前検査し、欠けていれば worktree を作らず停止 | 隔離した一時 git リポジトリでの単体テスト 2 件 |
| F-027 | scaffold が記録する状態遷移に `CONTRACT_DRAFTED` を経由させる | 既存の遷移検証で担保 |
| F-028 | scaffold が `render_progress` を呼ぶ | — |
| F-008 | Rule 4 のトリガに `requirements.machine.yaml` / `architecture.machine.yaml` を追加 | 正例 3・負例 5 のパラメタライズドテスト |
| F-009 | Rule 4 の matcher に Bash を追加 | 同上 |
| F-022 | 進捗ファイルはタイムスタンプ行を無視して比較し、実質差分が無ければ書かない | 実地: 2 回再生成して差分ゼロを確認 |
| F-002 | 受領書の見出しコメントを明示的に除去してから書き直す | 3 回実行してヘッダ 1 組・無関係コメント保持を確認 |
| F-003 | init-app skill にアプリ用ブランチ作成を追加 | — |
| F-031 | new-feature-worktree skill に「別セッションが必須」「1 セッションで回す場合の EnterWorktree 手順」「並行実装はできない」を明記 | — |
| F-017 | `ci_check.py` のベースを `origin/main` 固定から、`origin/main` とローカル `main` のマージベースの新しいほうへ | 実地: 誤検出 71 件 → 0 件 |
| F-016 | 項目 D をベース時点の architecture の status で判定 | 正常フローが通ること・承認後の追記は拒否されることの 2 件 |
| F-035 | 項目 G が書き換えたファイルを判定後に必ず戻す | 実地: `ci_check.py` 実行後にワークツリーが汚れないことを確認 |
| F-036 | 項目 G を feature ブランチではスキップ | スキップ条件が広すぎないことを含め 2 件 |
| F-015 | `check_traceability.py` が設計時ドラフトも読む | 実地: 契約 3 件・coverage 25 件を読めることを確認 |
| F-033 | 受領書 → `TESTED` の順序を CONVENTIONS.md 12節と feature-builder に明記（Rule 8 との噛み合わせを含む） | — |
| F-032 | worktree では Write/Edit を使うことを feature-builder に明記 | — |
| F-024 | `test_command` 未宣言が実装フェーズで回復不能であることを明記 | — |
| F-018 | `common_types` を `$ref` で参照しないことを明記 | — |
| F-041 | 補助スクリプトの引数体系の一覧を README に追加 | — |
| F-001 | README に uv でのセットアップ手順を併記 | — |
| F-046 | `.ruff_cache/` を `.gitignore` に追加 | — |

回帰テストは 310 → **335 件**（+25）。`ci_check.py` は全項目通過。

**副産物**: CONVENTIONS.md への追記が項目 L（コンテキスト予算 36000 バイト）に一度弾かれた。
参照用の引数表を README へ移して収めた。**ハーネスの予算強制が設計どおり働いている**ことの実証。

**探索中の事故と復旧**: F-014 の事前検査を実地で試すため orphan ブランチを作ったところ、
全ファイルが「変更」扱いになり事後検証ガードが全件巻き戻しを実行した。改修コミット 3 件は
無事で、`git checkout -f` で完全復旧（自己テスト 335 件・worktree 3 つとも健全）。
**破壊的な実地探索ではなく、隔離した一時 git リポジトリでの単体テストに切り替えた。**

### 第4弾（`harness/approval-gates` / 2026-08-22）— 残り 20 件を改修

| ID | 内容 | 検証方法 |
|---|---|---|
| F-010 / F-004 | 要件承認の確定を親セッションに一本化。`requirements-analyst` は DRAFT のまま承認用の要約を返して終わる責務に限定し、`init-app` skill の手順 8 に親が `status`/`approved_by`/`approved_at` を書く手順を明記。`solution-architect` も `MANUAL`/`SUPERVISED` では同じ扱い（`AUTONOMOUS` のみ自分の役割名で承認可）。`AskUserQuestion` が渡らない環境がある前提で、質問は最終メッセージ経由に統一 | — |
| F-011 / F-020 | Rule 7 を「承認ゲート」に拡張。要件・設計とも `status: APPROVED` と `approved_by`/`approved_at` の**同時性**を書き込み時点で強制。スキーマの `if/then` にも `required` を足し、キーごと欠落した場合の素通りを塞いだ | Hook をサブプロセス起動する end-to-end テスト 5 件 |
| F-039 | `CONTRACT_APPROVED` への遷移時に `contract.yaml` の承認記録を要求。`new_feature_scaffold.py` が設計承認（architecture の `approved_by`/`approved_at`）を契約ドラフトへ引き継ぐ | end-to-end 3 件＋継承ロジックの単体 4 件 |
| F-021 | `status.yaml`/`requirements.machine.yaml`/`architecture.machine.yaml` への **Bash 経由の書き込みを一律拒否**し、構造化ツールを要求。ハーネス自身のスクリプト経由（`run_verification.py` 等）はコマンド文字列にパスが現れないため掛からない | `sed -i`/リダイレクト/`cp` の 4 パターン＋読み取りが通ること＋受領書生成が通ること |
| F-019 | 受入基準の分担ルールを「その FR を覆う全機能の `coverage[]` を合算して `acceptance_criteria` を全て覆う」と定め、AC 単位で検証。要件に無い文言での対応づけも検出 | 4 件（未カバー検出・複数機能での分担・typo 検出・設計途中は判定しない） |
| F-044 | `contract.yaml` に `open_issues[]` を追加し、凍結中も**末尾への追記のみ**許可。`feature-builder` が追記し、`gate-reviewer` が契約側でしか閉じられない指摘を明示し、`integrator` が統合時に読んで対応を記録する | 追記可・凍結部の改変不可・過去項目の書き換え不可・Bash 不可の 4 件 |
| F-023 | `run_verification.py --check-only` を追加。worktree を作る前に shared-kernel と設計時ドラフト契約から宣言を解決し、`test_command` の有無まで検査する（`--feature` 省略で全機能） | 4 件＋ md-todo-cli で実地実行（3 機能とも解決） |
| F-025 | STACK_PACK.md に探索順序（`enabledPlugins` → `/plugin` → marketplace → 登録しない）を明記 | — |
| F-038 | Rule 4 の再生成をメイン側と worktree 側の両方で実行。再生成物を `ci_check` 項目 C の対象から除外 | 実地: worktree の PROGRESS.md が `features: []` から実データに変わることを確認＋項目 C の例外テスト 2 件 |
| F-040 | `contract_version` を scaffold が契約から埋める | — |
| F-006 / F-007 | requirements.md テンプレに受入基準の記入欄（機械側と一字一句一致させる旨つき）と、`open_questions` が空のときの書き方を追加 | — |
| F-026 | `lint_command` の例を `--select` でルールを明示した形に。既定ルールセット任せの危険を注意書き | — |
| F-042 | 4節の cwd 規約を実態（worktree ルートでもよい）に合わせた | — |
| F-013 | 機能 0 件のときの PROGRESS.md の見出し直前の空行漏れを修正 | 「見出しの直前は必ず空行」を全行に対して検査 |
| F-043 | `max_skip_ratio: 0.0` の副作用（環境依存 skip が 1 件でもあると TESTED にできない）をテンプレに明記 | — |
| F-045 | `code-review` が subagent を起動できない環境では skill 内の代替手順で実施する、と `feature-builder` に明記 | — |
| F-005 | 「承認を求める前に DRAFT のままコミットする」を `requirements-analyst` に明記（Rule 8 との噛み合わせ） | — |

回帰テストは 335 → **376 件**（+41）。`ci_check.py` は全項目通過。

**残り 3 件の扱い**: F-034 は F-002 の、F-037 は F-017 の実地再現なので、元の改修で解消済み。
F-012（auto mode の権限層が Bash 編集を hook の手前で拒否する）は Claude Code 側の挙動の記録であり、
ハーネス側で直すものではない。

**この弾で判明した新しい摩擦点が F-047**（コンテキスト予算の飽和）。上の「再開手順」に詳細。

---

## 摩擦点（実装フェーズ: todo-markdown / 2026-08-22）

`feature-builder` が `todo-markdown` を `CONTRACT_APPROVED` → `TESTED` まで通したときの記録。
結果は 52 tests / lint OK / トレーサビリティ 24 件成功、`gate-reviewer` は `GO`（Blocker 0 /
Major 1 / Minor 4）。受領書 `dd74611`、`TESTED` コミット `284f555`。

### F-049 【実証済み・重大】worktree 内の `harness/` と、実際に走る Hook の `harness/` がバージョンずれする（高）

`.claude/settings.json` の hook は `$CLAUDE_PROJECT_DIR/harness/hooks/...`＝**メインリポジトリ側**を
実行するが、worktree の中の `harness/` は **worktree 作成時点のスナップショット**である。
今回は実際に食い違った:

| | worktree 側（`5fba7bf` 時点） | main 側（実際に走る） |
|---|---|---|
| `feature-contract.schema.json` | `open_issues` を `additionalProperties: false` で**禁止** | F-044 で対応済み |
| `pre_tool_use_guard.py` | `open_issues[]` の追記例外を**持たない** | 例外あり |

実装者は worktree 側のスキーマでローカル検証したため「CI が落ちる」と誤判断し、
いったん `open_issues[]` の追記を revert して書き直す往復が発生した。

派生: `feature-builder` プロンプトは「`open_issues[]` の末尾追記だけは凍結中も許可されている」と
書いているが、worktree に入っている guard/schema は許可していない。AI 側からは
**「規約が嘘をついている」ように見え、判断が揺れる**。

→ 改修案: (a) ローカル検証にどちらの `harness/` を使うのかを規約で明示する、
(b) `new_feature_scaffold.py` が worktree に `harness/` のスナップショットを持ち込まない
（あるいは持ち込むなら「これは検証に使わない」と明示する）、
(c) 検証系スクリプトを常に `$CLAUDE_PROJECT_DIR` 側から実行させる。

### F-050 【実証済み・重大】`git add` が事後検証を誤発火させ、正当な `open_issues[]` 追記を巻き戻す（高）

`post_tool_use_guard.py` は Bash 前後の `git status --porcelain` を比較し、
**ステータスコードが変わったパス**を「変更された」とみなす:

```python
changed = [path for path, code in after.items() if before.get(path) != code]
```

`git add` はファイル内容を変えないが ` M` → `M ` とコードが変わるため、`contract.yaml` が
「Bash によって変更された」と誤検知される。さらに再判定を

```python
reason = pre_tool_use_guard.run_checks(scope_rel, cwd, scope_top)   # post_tool_use_guard.py:69
```

と **`tool_name`/`tool_input` を渡さずに**呼ぶため、`check_rule3_contract_freeze` の
`if tool_name in ("Edit", "Write", "MultiEdit")` に入れず、**F-044 で入れた
`is_open_issue_append` の例外が効かない**。結果 Rule 3 が拒否を返し、`revert_path` が
**Edit で正当に書いた追記を実際に消した**。

エラーメッセージは「直前の Bash コマンドが、ガード対象のパスを実際に変更しました…
**変更は巻き戻しました**」で、真因（`git add` でステータスコードが変わっただけ）は読み取れない。

実装者が見つけた回避策は「`git add` を使わず `git commit -a` で 1 発コミットする」
（コミット後は status から消えるので誤検知しない）だが、**これはどこにも書かれていない暗黙知**。

→ 改修案: (a) `changed` の判定を「ステータスコードの変化」ではなく**内容ハッシュの変化**にする
（`git add` は内容を変えないので誤検知しなくなる）、(b) それが重いなら少なくとも
`run_checks` に `tool_name`/`tool_input` 相当を渡せる形にして例外を効かせる、
(c) 巻き戻しメッセージに「`git add` によるステージ操作でも発火しうる」ことを書く。
**(a) が本筋**——(b)(c) は誤検知そのものを残す。

### F-051 【実証済み】トレーサビリティ照合が `@pytest.mark.parametrize` と両立しない（中）→ **改修済み（2026-08-23）**

parametrize すると JUnit XML の `name` が `test_x[None]` になり、契約の
`tests/test_markdown.py::test_x` と一致しない。`junit_utils.testcase_identifiers` は
`name` をそのまま使った完全一致／末尾一致しか持たないため、**テストは実在して成功しているのに
「JUnit XML に見つかりません」と言われる**。メッセージは
「テストを書くか、`test_ids` の書き方を実際の出力に合わせてください」で、
parametrize が原因だとは分からない。

契約は凍結されていて `test_ids` 側は直せないため、実装側が parametrize を諦めるしかなく、
宣言済み 3 件をループに書き換えた（テストの表現力を規約が削っている）。

→ 改修案: `testcase_identifiers` に `[...]` を落とした候補を加える（`test_x[None]` → `test_x` も
候補にする）。加えて、照合に失敗したときのメッセージに「パラメータ化されたテストは
`name` に `[...]` が付くため一致しない」旨を足す。

### F-052 `code-review` skill の subagent 前提と実行方針の矛盾（F-045 の再発）＋通知ごとの再注入（中）→ **運用手順として明記済み（2026-08-23、改修は不能と判断済み）**

F-045 で「subagent を起動できない環境では skill 内の代替手順で実施する」と `feature-builder` に
明記したが、**skill 側は依然 8 つの finder angle を Agent tool で並列起動する前提**であり、
どちらが優先かは実行時に読み取れない。今回も fallback で自分のコンテキストで実施した。

新しく分かった点: **バックグラウンドタスクの完了通知が届くたびに `code-review` skill の全文が
再注入され（3 回）、そのつど「レビューを実行せよ」という指示が入る**。既に実施済みでも
繰り返し要求されるため、コンテキストの浪費とノイズになる。

### F-053 エージェントスレッドで Bash の作業ディレクトリが毎回リセットされる（中）→ **ドキュメントに明記済み（2026-08-23）**

Bash ツールの説明は「Working directory persists between calls」だが、subagent のスレッドでは
毎回リセットされ、`PYTHONPATH=src ... pytest tests` が
`ERROR: file or directory not found: tests` で落ちた。毎回 `cd <絶対パス> && ...` が必要になるが、
`feature-builder` プロンプトは「`;` で繋いだ複合コマンドは拒否される」とも言っており、
**どこまでが許容される形なのか実行前に判断できない**。

→ 改修案: `feature-builder` プロンプトの項目 14 に「cwd は保持されないので毎回
`cd <絶対パス> && <単一コマンド>` の形で実行する」と明記する（`&&` は許容、`;` は不可、という
線が引かれていることを書く）。

### F-054 検証が失敗しても受領書が書き込まれ、Rule 8 と噛み合う導線が残る（中）→ **改修済み（2026-08-23）**

トレーサビリティ NG のときも `verification_receipt` は `status.yaml` に書かれ、
「NG だが受領書はある」未コミット状態が残る。今回はそのまま修正して進めたので実害は無かったが、
**この状態で応答を終えると Rule 8（未コミット検出）が停止を拒否する**——かといって
失敗した受領書をコミットするのも筋が悪い。導線として詰みかけている。

→ 改修案: 失敗時は受領書を書かない、または「失敗した受領書のコミットは許容される」ことを
明示する（`TESTED` は Rule 10 が別途止めるので、失敗記録をコミットしても安全）。

### 契約の穴（`open_issues[]` に記録済み。統合時に `integrator` が拾う）

`todo-markdown` の `contract.yaml` に OI-1〜OI-8 を追記済み。実装者の判断も併記されている。

| ID | 穴 | 実装者の判断 |
|---|---|---|
| OI-1 | `add` の `title` に改行・制御文字がある場合が未定義 | Cc を空白に置換して 1 行に畳む（空なら `EMPTY_TITLE`） |
| OI-2 | `done` の `index` が整数でない場合のエラーコードが未定義（FR-3 の受入基準と `error_cases` が不整合） | 型違反・範囲外をすべて `TASK_NOT_FOUND` に集約 |
| OI-3 | `- [ ]` の後ろが空白だけの行をタスクに数えるか未定義（数えると `title` の `minLength: 1` に違反） | 数えず、行はそのまま保持 |
| OI-4 | 「末尾の改行の有無を変えない」と「最後のタスク行の直後に追加する」が、末尾に改行が無い文書で両立しない | その最終行にだけ改行を足し、新しい行の後ろには付けない |
| OI-5 | `todo-cli` から呼ぶモジュール名・関数名が未決（契約がデータの形しか定めていない） | `mdtodo_markdown.parse_tasks` / `apply_command` を公開 API とする |
| OI-6 | **（gate-reviewer 指摘・Major）** `inputs[].json_schema` 違反時の応答形が未定義 | `ValueError`。**統合時に `todo-cli` 側の捕捉責務を決めないと、未捕捉例外のトレースバックが利用者に出る** |
| OI-7 | `document.exists` の意味が未定義 | 参照も検証もしていない |
| OI-8 | 文書から読み取った `title` に制御文字がある場合のサニタイズ責務が未定義 | この機能では素通し（表示は `todo-cli` の責務） |

**OI-5 と OI-6 は `todo-cli` の実装前に決める必要がある**（結線の前提になるため）。

---

## 改修記録（第5弾 `harness/fix-postguard-false-revert` / 2026-08-22）

`todo-cli` の実装前に踏むことが確実な 2 件だけを先に改修した。

| 摩擦点 | 改修内容 | 回帰テスト |
|---|---|---|
| F-050 | 事後検証の比較基準を `git status` の**状態コード**から**内容の SHA-1** に変更。`git add` は内容を変えずコードだけ変えるため誤検知していた。あわせて巻き戻し先を HEAD から**実行直前の内容**に変更し、実行前からの未コミット変更を巻き添えにしないようにした。副産物として、実行前から dirty だったファイルへの追加変更（コードが変わらないため従来は素通り）も検知できるようになった | 4 件（うち 3 件は旧実装で落ちることを確認済み） |
| F-049 | ハーネス資源の読み込み先を**常にメインリポジトリ側**に固定（`_common.harness_root()` / `resolve_harness_path()`）。加えて worktree 側の複製として起動されたスクリプトは、メイン側の同名スクリプトで自動的に起動し直す（`reexec_from_main_repo_if_needed()`）。**コードはメイン側、データは worktree 側**という形になり、Hook が使う定義とローカル検証の定義が一致する | 4 件 |

回帰テストは 403 → **407 件**。`ci_check.py` は全項目通過。
`CONVENTIONS.md` 7節の事後検証の記述を実装に合わせた（35,924 / 36,000 バイト。**残枠 76 バイト**）。

### F-049 の改修には bootstrap の限界がある（重要）

再実行の仕組みは worktree 側の `_common.py` に書かれているため、**この改修より前に作られた
worktree には効かない**（古い `_common.py` には再実行のコードが無い）。今ある 3 つの worktree が
それに当たる。

**既存の worktree を追従させるには、その worktree で `git merge main` する。**
事後検証は未コミットの差分だけを見るため、merge（コミットまで済む）は巻き戻されない
——実地で確認済み。`todo-cli` の実装前に必ず実行すること。

### 検証中に分かったこと（記録のみ、改修対象ではない）

事後検証は**未コミットの差分**を比較するため、Bash が書き込みと `git commit` を同時に行うと
検知範囲から外れる。ただし CI の項目 A（ハーネス非侵襲性）がコミット後の差分を見るため、
サーバ側では捕まる。二段構えの想定どおりの分担であり、穴として扱わない。

---

## 摩擦点（ユーザーからの問いで発見 / 2026-08-22）

### F-055 【実証済み・重大】worktree の外へ出る書き込みは、どの Rule にも掛からない（高）

「worktree に入っていれば他所を触れないのか」というユーザーの問いを確かめる過程で見つけた。

Hook は書き込み先を **`to_worktree_relative()` でセッションの worktree ルートからの相対パスに
直してから** 各 Rule の正規表現（`^harness/`、`^apps/<app>/03-features/...` 等）に掛ける。
worktree の外を指すパスは `../../../../harness/CONVENTIONS.md` のような形になり、
**どの正規表現にもマッチしないため素通りする**。

実測（`todo-markdown` の worktree をセッションとして、実際に hook へ payload を渡した結果）:

| 書き込み先 | 結果 |
|---|---|
| worktree 内の他機能 `03-features/todo-cli/src/x.py` | **拒否**（Rule 2） |
| **本体側の** `harness/CONVENTIONS.md`（絶対パス・Write） | **通る** |
| **本体側の** `harness/CONVENTIONS.md`（`../../../../` 経由・Bash） | **通る** |

事後検証も助けにならない。`post_tool_use_guard.py` は**セッションの worktree の**
`git status` を見るため、メインリポジトリ側の作業ツリーの変更はそもそも一覧に現れない。

つまり **Rule 1（ハーネス非侵襲性）・Rule 2（担当外ガード）・Rule 6（上位文書ガード）は、
いずれも「worktree の中に留まっている」ことを暗黙の前提にしている**。この前提は
`.worktrees/` を通るパスについては F-029 の改修で読み替えを入れて塞いだが、
**逆向き（worktree から外へ出る）は手当てされていない**。

→ **改修済み**（`harness/record-f055`）。「`../` なら一律拒否」ではなく、
**判定の基準点を「セッションの worktree」から「そのパスが属するリポジトリ」に移した**
（`path_utils.resolve_write_target`）。単に拒否するのではなく、外を指すパスにも
本来の Rule が本来の意味で当たるようになる。相対パスは `cwd` を基準に解決する
（セッションの cwd は worktree ルートとは限らないため）。

Rule 6 だけは追加の手当てが要った。「feature 用 worktree からの書き込みか」の判定に
**書き込み先**のツリーを使っていたため、本体側の上位文書を狙うと（そちらのルートには
`.worktrees/` が現れず）素通りしていた。**セッションの cwd** で判定するよう変更。

リポジトリの外（`/tmp` 等）は対象外のまま。過剰にブロックしないため。
回帰テスト 9 件（うち 7 件が旧実装で落ちることを確認済み）。416 件が緑。

**独立性の担保との関係**: 「他機能の内部を知らずに実装できる」ほうはブランチによって
構造的に担保されている（feature の実装は各 feature ブランチにあり、他機能の worktree には
**そもそも存在しない**——実測で確認）。壊れているのは「他所を壊さない」ほうだけである。

---

## 摩擦点（統合フェーズ: integrator 初回実行 / 2026-08-22）

`md-todo-cli` の3機能（`todo-file-store` / `todo-markdown` / `todo-cli`）を初めて `integrator` に
統合させたときの記録。3 ブランチを `main` へ merge → `interfaces[]` 5本を
`04-integration/assembly/` に実装 → 結合テスト15件・単体テスト126件が全緑 → 手動での
add/list/done 動作確認 → `state: INTEGRATED` へ更新、まで完走（コミット `875cab1` /
`777cb89` / `29566e4` / `f3aa761`）。

### F-056 【実証済み・中】`render_progress.py` の「worktree 優先」が統合直後に逆転する（中）

`_collect_status_paths()`（`harness/scripts/render_progress.py`）は feature_id が main 側と
worktree 側の両方にあるとき、**無条件に worktree 側を優先**する。これは「実装中は worktree にしか
状態が無い」時期を想定した設計だが、**統合直後**（feature ブランチを merge して main の
`status.yaml` を `INTEGRATED` に更新した後、対応する feature worktree をまだ `git worktree remove`
していない間）は前提が逆転する。古い `TESTED` のままの worktree 側が優先されてしまい、
`PROGRESS.md` / `STATE.machine.yaml` の再生成結果が統合完了を反映しない。

→ 改修方針: 両者の `last_updated_at` を比較し、新しい方を採用する（無条件の worktree 優先をやめる）。
下の「改修記録」で対応。

### F-057 `code-review` / `security-review` skill が integrator の小さな差分にスコープを絞れない（中）→ **運用手順として明記済み（2026-08-23、改修は不能と判断済み）**

両 skill のテンプレートは既定で `git diff @{upstream}...HEAD` 相当の**全履歴**を対象にする。
integrator は「マージ＋数百行の結線コード」という小さな差分を都度レビューしたいが、対象を
絞り込む引数が効かず、今回はドッグフーディング全体（84 コミット分）が対象になってしまうため、
integrator が実装した結線コードだけを狙った手動レビューで代替した。integrator 側の手順に
「レビュー対象のコミット範囲を明示的に伝える」定型文を用意するか、skill 側に範囲指定オプションが
要る。ハーネス側のスクリプトではなく Claude Code 標準 skill の挙動のため、改修は次回以降の検討事項
として記録に留める（未改修）。

### F-058 `open_issues[]` の申し送り文が、integrator の実際の権限（Rule 2）を考慮せずに書かれる（低）→ **ドキュメントに明記済み（2026-08-23）**

`todo-cli` の契約 `open_issues[]`（OI-9）は「実装が異なる名前なら **integrator が
`default_ports()` だけを実際の名前に合わせること**」と申し送っていたが、`integrator` はメイン
worktree で動くため Rule 2（担当外ガード）により `03-features/todo-cli/src/` を編集できない。
今回は `04-integration/assembly/` 側で `Ports` を明示的に組み立てて注入することで実害なく回避
できたが、申し送り文の前提（「integrator が直接直せる」）が実際の権限モデルと食い違っていた。
feature-builder が open_issues にこの種の申し送りを書く際は、integrator が触れられる場所が
`04-integration/` 配下に限られることを踏まえた表現にすべき。低頻度・実害なしのため未改修。

### F-059 依存機能の公開 API 名が `contract.yaml` に機械的な形で存在しない（低）

`open_issues[]` に書かれた公開 API 名の申し送り（OI-5, OI-9）が実装と一致しているかは、
integrator がソースの `__all__` を目視で確認するしかなかった。今回はズレ（OI-9）を発見できたが、
`contract.yaml` に `public_api:` のような機械可読フィールドが無く、`check_interfaces.py` 等で
突合する手段が無いため、見落としのリスクは構造的に残る。スキーマ拡張が要る大きめの変更のため、
バックログとして記録に留める（未改修）。

---

## 摩擦点（2本目: bookmark-vault / 要件定義フェーズ / 2026-08-22）

TypeScript・`SUPERVISED`・HTTP API という1本目と異なる軸で2本目のドッグフーディングを開始。
`init-app` → `requirements-analyst` → 親セッションによる要件承認、までの記録。

### F-060 Rule 7 のエラーメッセージ「同じ書き込みで」が、実際に機能する回避策を示していない（低）
`pre_tool_use_guard.py` は `status: APPROVED` への変更を検知すると、その Edit/Write 呼び出し
**単独の差分**に `approved_by`/`approved_at` が非 null で含まれているかを見ている。ところが
`status` と `approved_by`/`approved_at` はテンプレート上ファイル内で離れた位置にあり
（`requirements.machine.yaml` は 6行目と138〜139行目）、Edit ツールは1回の呼び出しで1箇所の
連続範囲しか置換できないため、素直に「1回の Edit で3フィールドを同時に変える」ことは
やろうとすると巨大な `old_string` が必要になり非実用的。

実際に機能する回避策は、**エラーメッセージの文言が示唆する「同じ書き込み」を素直に信じない**こと。
`status` を `APPROVED` 以外の値のままにしておいて先に `approved_by`/`approved_at` を Edit で埋め、
**その後** `status` だけを `APPROVED` に変える Edit を別呼び出しで行えば通る（Guard は
「`status` を `APPROVED` に変える tool call の時点で両方が非 null か」を見ているだけで、
「1回の呼び出しで3行とも変える」ことまでは要求していない）。今回この順序に気づくまで
`status: DRAFT → APPROVED` の直接 Edit を2回試して拒否された。
→ エラーメッセージを「`approved_by`/`approved_at` を先に埋めてから `status` を変えてください」
という、実際に機能する順序ベースの案内に変える。低頻度（要件・設計の承認時のみ）だが
毎回同じ回り道をする可能性があるため記録。


---

## 摩擦点（2本目: bookmark-vault / 機能実装フェーズ / 2026-08-22）

`bookmark-core`・`bookmark-store`・`bookmark-api` の3機能を実装した際に見つかったもの。

### F-061 【実証済み・重大】`parse_simple_yaml` が `- >-`（シーケンス項目としてのブロックスカラー）を解釈できず、それ以降のトップレベルキーの解析が丸ごと消える（高）→ **改修済み（2026-08-23）**

`harness/hooks/lib/path_utils.py` の `_yaml_parse_sequence` は、シーケンス項目が
`- key: value` マッピング／`- {...}`／`- [...]`／単純スカラーの各形は扱うが、
**`- >-`（項目自体がブロックスカラー）は想定されていない**。実際に `status.yaml` の
`review.majors`/`review.minors` に
```yaml
majors:
- >-
  1行目
  2行目
```
と書いたところ、`>-` という**文字列そのもの**が唯一の項目として読まれ（`['>-']`）、
続く字下げされた本文行はどの規則にもマッチせず、`_yaml_parse_sequence` のループが
`break` する。呼び出し元の `_yaml_parse_mapping`（`review:` および外側のトップレベル
マッピング）も同じ字下げ不一致でそのまま `break` するため、**`review:` より後ろに書かれた
全てのトップレベルキー（`superseded_by`/`last_updated_at`/`updated_by`/
`verification_receipt` 等）が丸ごと消失した状態で解析される**（実測: `verification_receipt`
が実際にはファイルに存在するのに `{}` として読まれた）。

これが `check_rule10_verification_receipt` の「`verification_receipt` が無いため TESTED に
できません」という**誤解を招くエラー**の直接原因だった（受領書は実在するのに、パーサが
そこまで到達できていないだけ）。さらに悪いことに、一度この状態になると、`review.majors`の
書式を直そうとする Edit 自体が Rule 10 の「受領書の手書き検知」（旧内容の受領書=`{}` と
新内容の受領書=正しい値、が不一致）に**別の理由でブロックされる**という二重の罠になる
（詳細は改修記録参照）。

`- >-` はYAMLとして正当な記法であり、`key: >-`（マッピングの値としてのブロックスカラー）は
同じファイル内の `state_history[].note` で問題なく使われている。**シーケンス項目としての
ブロックスカラーだけが未対応**という非対称な欠落。

→ 改修方針: `_yaml_parse_sequence` に `- >-`/`- |` の処理を追加する（`_yaml_parse_mapping`
の `_yaml_consume_block_scalar` 呼び出しと同様のロジックを、シーケンス項目にも適用する）。
最低限、パースが字下げ不一致で丸ごと `break` する代わりに、認識できない行をスキップして
後続キーの解析を継続する保険的な挙動にするだけでも実害を減らせる。

### F-062 【実証済み・中】`status.schema.json` の `review.blockers`/`majors`/`minors` は整数（件数）だが、実例は一貫して文字列配列を書いている（中）→ **ドキュメントに明記済み（2026-08-23）**

スキーマは以下の形（件数のみ、詳細文は任意の `notes` 文字列1本にまとめる想定）を要求する:
```json
"blockers": {"type": "integer"}, "majors": {"type": "integer"}, "minors": {"type": "integer"}
```
しかし今回、feature-builder（1ラウンド目）・gate-reviewer（2ラウンド目、`status.yaml` への
反映案として提示したYAML）とも、**指摘の本文をそのまま文字列配列として** `blockers`/
`majors`/`minors` に書いた（`validate_yaml.py` で実際に schema 不合格を確認）。
`gate-reviewer` agent定義・`CONVENTIONS.md` 10節のどちらにも、この3フィールドが
「件数」であり詳細は `notes` に書く、という具体例が無いことが原因と見られる。

→ 改修方針: `gate-reviewer`/`feature-builder` の agent定義に、`review:` フィールドの
正しい書式（`blockers`/`majors`/`minors` は整数、詳細は `notes` に1本の文字列で）を
具体例つきで明記する。可能なら `new_feature_scaffold.py` が生成する `status.yaml` の
コメントにも書式例を残す。

### F-063 cwd固定されたセッションが自分自身からさらに Agent/Skill をバックグラウンド起動すると、以後のツール呼び出しの cwd 追跡が失われる（高・ハーネスの外側の挙動）→ **ドキュメントに明記済み（2026-08-23）**

2つの独立した観測がある:

1. `feature-builder` subagent（`EnterWorktree` 経由で worktree に固定されたセッションから
   起動）が、実装の途中で `code-review` skill（fork）と `gate-reviewer` subagent（Agent）を
   起動した**直後から**、以後の `Write`/`Edit` 呼び出しが Rule 2（担当外ガード）に拒否される
   ようになった。本人による標準入力ベースの再現（`pre_tool_use_guard.check_rule2_feature_scope`
   を実際の cwd を渡して直接呼び出す）で、リジェクトメッセージが再現することを確認済み。
   `Bash` の `cd` は次の別の `Bash` 呼び出しには引き継がれないことも確認している。
2. 親セッション（本セッション）自身も、`EnterWorktree(bookmark-core)` で worktree に入った
   状態から `Agent(gate-reviewer)` を起動したところ、その後 `ExitWorktree` を呼ぶと
   「no active EnterWorktree session」と返され、**ツール側の worktree 追跡情報が失われて
   いた**。ただし実際のシェル `cwd`（`pwd`）や `Edit`/`Bash` の書き込み先解決は最後まで
   正しく worktree 内を指し続けており、実害は無かった。

2点目は「実際の cwd 解決」と「`EnterWorktree`/hookが参照する cwd 追跡」が別経路である
可能性を示唆する。1点目（subagent）ではその追跡がハーネスのアクセス制御に直結して実害が
出たが、2点目（親セッション）では実害が出なかった——subagentのcwdは起動時に固定された
静的な値である一方、親セッションは実シェルの `cwd` を都度報告している、という違いが
原因ではないかと推測する（未確定）。

いずれにせよ**これはハーネス（apparness）のコードの問題ではなく、Claude Code側の
エージェント実行基盤の挙動**と考えられるため、`harness/` の改修対象にはしない。運用上の
回避策として: `feature-builder` は `gate-reviewer`/`code-review` の起動を**実装の最後
（それ以上 `src/` を編集する必要がなくなった後）に限定**し、レビュー起動後に追加の
Write/Edit が必要になった場合は、親セッションが `EnterWorktree` で入り直して代行する
（本セッションで実際にこの回避策を使い、`bookmark-core` の Blocker 修正を完了させた）。

### F-064 レビュー待機中に応答を終えようとすると Rule 8（未コミット停止拒否）に阻まれる（中）

`bookmark-api` の `feature-builder` が `gate-reviewer` をバックグラウンド起動（Task/Agent）した
まま応答を終えて通知を待とうとしたところ、`stop_commit_guard.py`（Rule 8）が
「フェーズの節目のファイルが未コミット」として停止を拒否した。`status.yaml` を
`IMPLEMENTED` + 受領書の状態で一旦コミットしてから `gate-reviewer` の結果を待ち、
指摘対応後に受領書を作り直す（HEAD が進むため）、という回り道が必要だった。

F-033（受領書とコミットの順序の罠）と根は同じで、「非同期のレビュー待ちの間、何かを
未コミットのまま応答を終える」という状態そのものが Rule 8 と構造的に噛み合わない。
今回は実害なく回避できた（bookmark-store・bookmark-apiともTESTEDまで到達）ので、
`feature-builder` の手順として「gate-reviewer 起動前に区切りのコミットを打つ」ことを
明記しておくと今後も安定する。低頻度・回避策確立済みのため改修は見送り、記録のみ。

### 改修記録（bookmark-core, 2026-08-22）

`feature-builder` が `gate-reviewer` 1ラウンド目の NO-GO（Blocker: `validateAndNormalize` が
不正入力で例外を投げる／tagsを文字列で渡すと1文字ずつタグ化する）への対応中に F-063 でブロック
されたため、親セッションが `EnterWorktree` で正しく worktree に入り直し、直接修正を完了させた:
`unknown` 受け取り化＋実行時型ガード（`isPlainObject`/`isStringArray`）、境界値テスト9件追加、
`contract.yaml` の `open_issues[]` に OI-1/OI-2/OI-3 を追記（凍結後の追記のみ）。
`gate-reviewer` 2ラウンド目は `GO`（Blocker 0・Major 1・Minor 1）。Major（`filterBookmarks` が
`search_criteria` の形状を検証していない）も同様に修正。最終的に F-061/F-062 のバグを踏み抜き
ながらも `run_verification.py` で受領書を再生成し、`state: TESTED` まで到達
（コミット `e846b7f`）。回帰テスト等ハーネス自体の改修はまだ行っていない
（通しを優先し、改修は完走後にまとめて行う既定方針どおり）。

### bookmark-store・bookmark-api・bookmark-frontend も TESTED まで到達（2026-08-22〜23）

残り3機能も `feature-builder` に実装させ、依頼文に「`gate-reviewer`/`code-review` 起動は
`src/` 編集が全部終わってから」（F-063対策）「`review` の `blockers`/`majors`/`minors` は
整数（F-062対策）」を明記した結果:

- **bookmark-store**: `gate-reviewer` 1ラウンド目 `GO`（Major 2件はその場で対応: `deleteById`
  が契約の `bookmark_id` 型でなく生の `id` 文字列を受けていた／エラーメッセージに絶対パスが
  漏れていた）。`state: TESTED`（コミット `3a8cddf`）。F-063 は再発しなかった
  （レビュー起動を最後にした対策が有効だったとみられる）。
- **bookmark-api**: `gate-reviewer` 1ラウンド目 `GO`（Major 1件: DELETE 204レスポンスに
  `Content-Type` ヘッダが欠けていた→対応）。Ports パターン（`createServer(ports)`）で
  bookmark-core/bookmark-store への依存を注入可能にする設計を feature-builder 自身が採用し、
  統合時の結線を見据えた設計ができていた。`state: TESTED`（コミット `35c6eee`）。
  非同期の `gate-reviewer` 起動と Rule 8（停止拒否）が衝突する新たな摩擦点 F-064 をここで発見。
- **bookmark-frontend**: `gate-reviewer` 1ラウンド目は `NO-GO`（Blocker: API応答を型
  アサーションのみで信頼し実行時形状検証が無かった／Major: 登録フォーム送信中のローディング状態・
  二重送信防止が無かった）。`feature-builder` は指示どおり追加編集を試みず停止し、親セッションが
  引き継いで修正（`isBookmark`等の実行時ガード追加、`setFormBusy()` による送信中UI）。
  2ラウンド目は `GO`（Blocker 0・Major 0・Minor 1）。`state: TESTED`（コミット `a668ce2`）。
  `frontend-design` skill の有効化は結局 auto mode 分類器の一時的な拒否だったとみられ、
  日を跨いで再試行したところ問題なく成功した。

**4機能すべてが `TESTED` に到達（2026-08-22〜23）。次は `integrator` フェーズ。**

---

## 摩擦点（統合フェーズ: bookmark-vault integrator実行 / 2026-08-23）

`bookmark-vault` の4機能（`bookmark-core`/`bookmark-store`/`bookmark-api`/`bookmark-frontend`）を
`integrator` に統合させた記録。4ブランチを `main` へ `--no-ff` merge（`1d92355`/`bc6daae`/
`39113ff`/`f227bb3`）→ `interfaces[]` 10本を `04-integration/assembly/` に実装 → 結合テスト13件・
単体テスト89件（計102件）が全緑 → 実サーバー起動での手動確認 → `state: INTEGRATED` へ更新
（コミット `ebd68d8`）まで完走。詳細は `apps/bookmark-vault/04-integration/integration.md`。

**F-057（`code-review`/`security-review` skill がスコープを絞れない）が再発した**（md-todo-cli
統合時と全く同じ症状。手動レビューへの切替で回避）。TypeScript スタックでも再現したことで、
アプリのスタックに依存しない skill 側の一般的な欠陥であることが裏付けられた。改修は引き続き
未着手（Claude Code 標準 skill の挙動のため）。

### F-065 【実証済み・中】機能内部で定義された DI インターフェース（`Ports` 等）の形状差は `check_interfaces.py` の検証対象外（中）→ **改修済み（2026-08-23）**

`interfaces[]` の機械検証は producer/consumer の `outputs[]`/`inputs[]` の JSON Schema しか
見ない。`bookmark-api` が実装都合で定義した `Ports` 型（`03-features/bookmark-api/src/ports.ts`）
は `architecture.machine.yaml` に一切現れないため検証の対象外で、実際に4機能の実装を読んで
初めて次の3点の形状差が判明した（いずれも結線コード `assembly/src/ports.ts` で吸収）:

- `filterBookmarks`: bookmark-core は `{ bookmarks: Bookmark[] }` を要求するが `Ports.filterBookmarks`
  は生の `Bookmark[]` を渡す
- `listAll`: bookmark-store は `{ bookmarks: Bookmark[] }` を返すが `Ports.listAll` は生の
  `Bookmark[]` を期待する
- `deleteById`: bookmark-store は存在しないIDで `NotFoundError` を**例外として投げる**が、
  `Ports.deleteById` は**返り値** `{ deleted: false }` を期待する

機能数が増えるほど「integrator が全機能の実装を読んで目視確認する」以外に検出手段が無いことの
見落としリスクが上がる。

→ **改修**（ユーザー指摘・`harness/deterministic-integration-interfaces`）: 契約の形の宣言を
増やす方向ではなく、「`interfaces[]` の全エッジを、実装同士を実際に繋いだ結合テストで検証した
ことを機械的に強制する」方向で解決した（F-066 とまとめて改修。詳細は F-066 側の改修記録を参照）。
`Ports` の形状そのものを静的に照合するわけではないが、実際に繋いで動かすテストが通っている限り
形状差は実行時エラーとして必ず顕在化するため、実地には等価な保証になる。

### F-066 【実証済み・中】HTTPクエリ文字列のエンコーディングは `interfaces[]`/`contract.yaml` の JSON Schema で表現されず、実際に不一致が起きた（中）→ **改修済み（2026-08-23）**

`bookmark-frontend` の契約 `open_issues[]`（OI-1）で「未確認」と申し送られていた懸念が、
統合時に**実際に不一致だと判明した**実例。`list_query`/`search_criteria` の型は両契約とも
`tags: string[]` で完全に一致しているのに、HTTP上のエンコーディングが食い違っていた
（`bookmark-frontend` は `?tags=a&tags=b` の繰り返しパラメータ、`bookmark-api` は
`url.searchParams.get("tags")` で最初の1件のみ取得しカンマ区切りとして分割）。繰り返し
パラメータでは2件目以降が黙って無視され、**FR-4 の複数タグAND絞り込みが実際に壊れていた**。
`bookmark-api.contract.yaml` の説明文には「カンマ区切り」と書かれていたが、`bookmark-frontend`
側の実装時にそこまで読まれなかった。

これは ROADMAP ⑩「`interfaces[]` の JSON Schema 突合が、実際の食い違いを実地で捕まえるか」への
実地での答えでもある: **型レベルの突合はできるが、HTTPエンコーディングのようなプロトコル
レベルの約束事は原理的にすり抜ける。** 結線コード `assembly/src/query-normalize.ts` で吸収済み、
回帰テストあり。

→ **改修**（ユーザー指摘・`harness/deterministic-integration-interfaces`、2026-08-23）:
「JSON Schema による静的な契約照合をどれだけ精緻化するか」ではなく、**「`interfaces[]` の
全エッジについて、実装同士を実際に繋いだ結合テストが存在し成功したことを機械的に強制する」**
方向で解決した。新設した `apps/<app>/04-integration/integration.machine.yaml` に、
`interfaces[]` の各エッジ（producer/consumer の組）へ対応する結合テストの識別子
（`interface_coverage[].test_ids`）を宣言し、`run_integration_verification.py` が
`test_strategy.coverage[]`（Rule 10）と同じ「宣言 → 実行 → JUnit XML と突合 → 受領書」の
仕組みで検証する。新設した Rule 11（`pre_tool_use_guard.py`）が、受領書が無い・古い・
未カバーのエッジが残っている場合に `status.yaml` を `state: INTEGRATED` にする書き込みを
拒否する（`check_integration_traceability.py` が CI 項目 N として宣言レベルの取りこぼしも
再検証する）。契約の JSON Schema をどれだけ精緻にしても HTTP エンコーディングのような
プロトコルレベルの約束事は原理的に表現しきれないため、「型を照合する」のではなく
「実際に繋いで動かした結果を強制する」ことで、F-065（DIインターフェースの形状差）とあわせて
同じ仕組みで塞げることが分かった。回帰テスト: `path_utils` の単体テスト、Rule 11 の
hook 経由 end-to-end テスト、`run_integration_verification.py` の実サブプロセス経由
end-to-end テストを追加（ハーネス自己テスト 418→436件）。

### F-067 `file:` 依存の npm ワークスペースで、`04-integration/assembly` 側が新規に npm パッケージを作ると devDependency のバイナリ（`tsc`/`vitest` 等）が `npm install` 前には PATH に無い（低）→ **ドキュメントに明記済み（2026-08-23）**

`03-features/*` 側は各 feature-builder が自分のパッケージで `npm install` 済みという前提で
「各コマンドの先頭で `npm install` する」規約（`shared-kernel.yaml` の verification 節）に従える
が、`04-integration/assembly/` は integrator が新規に作る npm パッケージであり、同じ注意点が
明記されているのは `03-features` 側のみだった。`build:features` で各機能をビルドした直後に
assembly 自身の `tsc` を呼ぶ設計にしたところ `node_modules` 未生成で `sh: 1: tsc: not found` に
なり、`npm run build`/`typecheck` の先頭に `npm install` を追加して解決した。低頻度・実害小さい
（1回踏めば分かる）ため改修は見送り、記録のみ。TypeScript スタックで integrator が npm パッケージ
を新設するケースの雛形やガイドがあると再発を防げる。

### 改修記録（bookmark-vault 統合, 2026-08-23）

`code-review` skill（scoped, high effort）が実際に指摘した1件（`normalizeTagsQuery` が
try/catch の外で同期的に呼ばれ、不正な `req.url`（absolute-form request-target）で未捕捉例外→
プロセスクラッシュ）は、手動セキュリティレビューの過程で先に気づき修正済みだったものと一致した。
具体的な repro で例外を実証し回帰テストを追加。もう1件（`prepare-static.mjs` の静的ファイル
コピーが非再帰的で将来のサブディレクトリを取りこぼす潜在バグ）も修正済み。いずれもハーネス側の
改修ではなく `apps/bookmark-vault/04-integration/assembly/` 内で完結する対応のため、
ハーネス自体の改修は無し（通しを優先し、ハーネス改修は完走後にまとめて行う既定方針どおり）。

**bookmark-vault（2本目）が `INTEGRATED` まで完走（2026-08-23、コミット `ebd68d8`）。
ハーネス自己テスト418件緑・`ci_check.py` 通過・`check_interfaces.py` 通過を維持したまま到達。**

---

## 両本完走後のまとめ改修（ユーザー指摘、2026-08-23）

両本目が `INTEGRATED` まで完走したのを受け、ユーザーから2件の改修指示があった
（「順序は任せる」との指示で、この場で両方着手・完了させた）。

### 改修1: `required_skills[]` の機能単位絞り込み（`harness/scope-required-skills-per-feature`）

**ユーザー指摘**: 設計書がどの機能にどの Skill/ライブラリが要るかを示していないため、
無関係な機能の実装にまで不要な Skill が要求される状態になっている、との報告を受けた。

調べると、**ライブラリ側は元々問題が無かった**（`contract.yaml` の `tech_stack.libraries[]`
は各機能が自己完結した npm/pip パッケージとして独立宣言しており、bookmark-vault でも実際に
機能ごとに別々のライブラリ一覧になっていた）。問題は **Skill 側**: `shared-kernel.yaml` の
`required_skills[]` はアプリ全体に一律適用され、Rule 5（`check_rule5_required_skills`）が
`feature_id` を区別せず全機能の `src/**` 書き込みへ同じ Skill 群を要求していた。bookmark-vault
では `frontend-design` が `bookmark-core`/`bookmark-store`/`bookmark-api` にまで（無関係にも
関わらず構造上は）要求されうる状態だった。

→ 改修: `required_skills[]` の各エントリに任意の `applies_to`（feature_id の配列）を追加し、
Rule 5 がこの feature_id を含むエントリだけを要求するようにした。省略・空配列なら従来どおり
全機能適用（後方互換）。`solution-architect` にも、Skill が一部機能にしか関係しない場合は
`applies_to` を書くよう指示を追加。回帰テスト4件追加。

### 改修2: `interfaces[]` の実地カバレッジを機械検証する Rule 11（`harness/deterministic-integration-interfaces`）

**ユーザー指摘**: interfaces[] の整合確認は決定論的に判断できる領域なので、AI の目視に
委ねず機械的に照合してほしい。可能なら統合前（各機能の作成段階）でも確認してほしい。

F-065/F-066（本ファイル該当節）で判明した「`check_interfaces.py` は契約の JSON Schema
同士の静的な整合しか見ないため、機能内部の DI インターフェース（`Ports` 等）の形状差や
HTTP エンコーディングの不一致のような、契約の JSON Schema には現れない差異をすり抜ける」
という限界に対する本格改修。詳細な設計・実装内容は F-066 の改修記録を参照。要点:
`04-integration/integration.machine.yaml`（新設）に `interfaces[]` の全エッジへ対応する
結合テストの識別子を宣言し、`run_integration_verification.py` が JUnit XML と突合して
受領書を作り、Rule 11 が受領書と全エッジカバレッジが揃うまで `state: INTEGRATED` を拒否する
（`test_strategy.coverage[]`/Rule 10 と同じ「宣言 → 実行 → 受領書」の型を統合フェーズに
そのまま適用）。「各機能の作成段階での確認」は、DI インターフェースの形状が他機能の実装が
無いと確定しない性質上、機能単位では原理的に不可能と判断し（設計時点では相手の契約の
JSON Schema しか無く、それは既に `check_interfaces.py` が検証している）、統合時点での
実行結果ベースの強制に一本化した。ハーネス自己テスト 418→436件。

**両改修とも `main` にマージ済み（コミット `6749206`・`bca41b1`）。次にアプリを1本通して
このまとめ改修が実地で機能することを確認するまでは、Rule 11 は「実装したが未検証」の状態
であることに注意（bookmark-vault は Rule 11 導入前に完走したため、この仕組みそのものは
まだどのアプリでも実地を通っていない）。**

---

## フェーズ1: 残る摩擦点の修正（2026-08-23）

両本完走後にユーザーと合意した3フェーズ計画の1番目。「★ 次の再開ポイント：フェーズ1」節に
確定していた方針どおり、コード変更を伴う3件と、ドキュメントのみの6件をそれぞれ別ブランチで
処理した。

### コード変更 3件（`harness/dogfooding-phase1-code`、コミット `4dc0e2a`→`main` へ `1c7bf68`）

- **F-061（最高）**: `parse_simple_yaml` の `_yaml_parse_sequence` が `- >-`/`- |`
  （シーケンス項目自体のブロックスカラー）を解釈できず、それ以降の全トップレベルキーの解析が
  丸ごと消えるバグを修正。`_yaml_parse_mapping` が使う `_yaml_consume_block_scalar` と同じ
  読み飛ばしロジックをシーケンス項目にも適用した。あわせて `_yaml_parse_mapping` に、
  想定より深いインデントの行に出会っても丸ごと `break` せずその行だけ読み飛ばして継続する
  フォールバックを追加（未知の記法による同種の取りこぼしへの保険）。
- **F-051（中・実証済み）**: JUnit識別子照合が `@pytest.mark.parametrize` と両立しない
  問題を修正。`junit_utils.testcase_identifiers` に、`name` から末尾の `[...]` を落とした
  形も候補として追加。`validate_traceability` の「見つかりません」メッセージにも
  パラメータ化テストへの注意を追記。
- **F-054（中）**: 検証が失敗しても受領書付き `status.yaml` をコミットして構わないことを
  `CONVENTIONS.md` 12節・`feature-builder.md` に明記（`state: TESTED` への昇格は Rule 10 が
  受領書の中身で別途止めるため安全）。`CONVENTIONS.md` は改修前 35993/36000 バイトで
  残り 7 バイトしか無かったため、Rule 10/Rule 8 の順序の詳細説明を `docs/HARNESS_GUIDE.md` 14節へ
  移設して捻出した（改修後 35943 バイト）。

回帰テスト7件を追加（`test_yaml_parser.py` に F-061 用3件、`test_verification.py` に
F-051 用4件）。ハーネス自己テスト 436→443件。

### ドキュメントのみ 6件（`harness/dogfooding-phase1-docs`）

いずれもハーネスのコード変更を伴わない、agent 定義への手順明記のみ。

- **F-053（中・実証済み）**: `feature-builder.md` に「Bash の cwd はツール呼び出しをまたいで
  保持されないため、毎回 `cd <絶対パス> && <単一コマンド>` の形で実行する」ことを明記。
  `integrator.md` も検討の結果、同じ理由（同じく subagent として起動される）で影響すると
  判断し、`04-integration/assembly` でのコマンド実行手順に同内容を追記した。
- **F-058（低）**: `feature-builder.md` の `open_issues[]` 記載ガイドに、「`integrator` が
  実際に触れられるのは `04-integration/` 配下だけ（Rule 2 により他機能の `src/` は直接編集
  できない）」という前提を踏まえた書き方をすべきことを明記。
- **F-062（中・実証済み）**: `feature-builder.md` の `review:` 記録手順に、
  `blockers`/`majors`/`minors` は指摘件数の整数であり本文は `notes` にまとめることを、
  具体的な YAML 例つきで明記。
- **F-067（低）**: `integrator.md` に、`04-integration/assembly` 新設直後は devDependency
  のバイナリが PATH に無いため、`assembly` 自身の npm スクリプトも各コマンドの先頭で
  `npm install` することを明記。
- **F-052/F-057（中・対応不能と判断済み）**: `code-review`/`security-review` skill は
  Claude Code 標準搭載でこのリポジトリの `harness/` からは調整できないため、統合コードに
  スコープを絞った手動レビューへ最初から切り替えてよいことを `integrator.md` に運用手順
  として明記（改修ではなく既存の実務対処の明文化）。
- **F-063（高・ハーネス外の挙動）**: `integrator.md` に、レビュー/検証系のバックグラウンド
  起動は `src/` 相当の編集がすべて終わってから行うことをワークアラウンドとして明記
  （Claude Code 側の実行基盤の挙動でハーネス側では改修不能と判断済み）。

**F-059** は見送り候補のままユーザー確認待ち、**F-064** は対応不要と判断済みのため
このフェーズでは何もしていない（いずれも「★ 次の再開ポイント：フェーズ1」節の判断を踏襲）。

**次の再開ポイント（フェーズ2）**: 3本目のアプリを最初から通しで作る。1本目（Python/CLI/
AUTONOMOUS）・2本目（TypeScript/HTTP API+フロントエンド/SUPERVISED）と違う軸を選び、
Rule 11・`applies_to` を含むこれまでの改修が実地で機能するかを確認する
（詳細は本ファイル冒頭の「再開手順」節を参照）。
