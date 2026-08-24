# feature-build.md — 機能実装フェーズの手順（オンデマンド読み込み）

`feature-builder` subagent が実装フェーズで従う詳細手順。**該当フェーズで初めて読まれる**文書なので
コンテキスト予算（`CONVENTIONS.md` 15節・CI 項目 L）の対象外。規範そのものは `CONVENTIONS.md` に
あり、ここにあるのは「誰が何をどの順で実行するか」だけ。

読むタイミング: `feature-builder` が実装に着手する前に 1 回。

## 1. 着手

1. `SPEC.md` と `contract.yaml` を読み、この機能が何をすべきか理解する。
2. `status.yaml` の `state` を確認する。`CONTRACT_APPROVED` であることを前提に実装を始めてよい。
   実装開始時に `state: IN_PROGRESS` に更新する（`state_history` の末尾、`review:` より前に追記）。
3. `harness/quality/security-baseline.md` を読み、実装全体で守る。この機能が UI を持つ場合は
   `harness/quality/design-baseline.md` も読む。
4. `../../01-foundation/shared-kernel.yaml` の `required_skills[]` を確認する。設計で必須と
   決められた Skill があれば使う。`kind: stack-pack` のエントリは**スタック固有の標準**
   （言語バージョン下限・禁止パターン・テスト規約など）なので、実装前に読んで従う。
   ただし `harness/quality/*.md` のベースラインと矛盾する場合は**ベースラインが優先する**
   （`harness/STACK_PACK.md`）。`src/` への最初の書き込み時に、各 `plugin_ref` が有効化されて
   いるか Hook が機械的に検証し、欠けていればその場でブロックしてインストール手順を提示する。

## 2. 実装

5. `contract.yaml` の `inputs`/`outputs`/`error_cases`/`tech_stack` を満たすように `src/` に実装し、
   `tests/` にテストを書く。`tech_stack` に指定されたライブラリ・バージョンを使う。
   **`test_strategy.coverage[]` に列挙されたテスト識別子（`test_ids`）は、そのままの名前で
   実在しなければならない。** 検証時に JUnit XML と突合され、見つからない・失敗している識別子が
   あると Rule 10 が `TESTED` を拒否する。契約に無い観点のテストを追加するのは自由。
6. `contract.yaml` は原則変更しない（承認済みの契約は凍結されており、Hook が書き込みをブロックする）。
   実装中にどうしても契約変更が必要だと分かった場合は、実装を止めてユーザーに報告する。
   **契約の小さな穴（曖昧さ・書き漏らし）で、実装を止めるほどではないものは
   `contract.yaml` の `open_issues[]` に追記する**（`{ id: "OI-1", summary, found_at, found_by }`。
   末尾への追記だけは凍結中も許可されている）。`SPEC.md` に書くだけでは機械検証の対象外なので、
   統合時に拾われる保証がない。
   `summary` は、これを読む `integrator` が触れられるのは `04-integration/` 配下だけであることを
   踏まえて書く（Rule 2 により他機能の `03-features/*/src/` は直接編集できない）。
   「integrator が直接直してほしい」ではなく、結線側の吸収案や再設計の要否が伝わる書き方にする。
7. 実装が終わったら `state: IMPLEMENTED` に更新する。

## 3. `TESTED` にする前の 2 つのレビュー

8. **`code-review` skill を実行し、指摘があれば対応する。** Skill が見つからず実行できない場合は、
   その旨をユーザーに報告したうえで先に進んでよい（`security-baseline.md` / `design-baseline.md` は
   既に守っているため、これは追加のチェックという位置づけ）。`code-review` が subagent を起動する
   構成で、その起動が方針上できない場合は、**skill 内の代替手順で同じ観点を自分のコンテキストで
   実施する**（レビュー自体は飛ばさない）。
9. **`gate-reviewer` subagent に審査を依頼する**（Task ツールで `subagent_type: gate-reviewer`、
   対象の app-id と feature-id を伝える）。**依頼の前に `git add -A && git commit` を済ませておく**
   （レビュー対象を確定させるため。また未コミットのフェーズ節目ファイルが残っていると Rule 8 が
   subagent の停止をブロックする）。自分で `code-review` を回すのは自己レビューであり作者バイアスが
   残るため、別コンテキストの審査を必ず通す。
   - `verdict: NO-GO`（`Blocker` が 1 件以上）なら、指摘に対応してから再度依頼する。
   - **`NO-GO` を回避するために契約やテストを都合よく書き換えてはいけない**（契約は凍結されており
     Hook が拒否する。テストの改変は次のレビューで指摘される）。
   - 3 ラウンド続けて `NO-GO` なら、対応を続けずユーザーにエスカレーションする
     （収束しない論点は設計か要件の側に問題があるサイン）。
   - 結果を `status.yaml` の `review`（`verdict`/`at`/`rounds`/`blockers`/`majors`/`minors`）に
     記録する。**`blockers`/`majors`/`minors` は指摘の件数（整数）**であり、指摘の本文を文字列配列
     として書いてはいけない（schema 違反）。本文は `notes`（文字列 1 本）にまとめる
     （例: `blockers: 0, majors: 1, notes: "Major: ..."`）。

## 4. 検証の実行と `TESTED`

10. **実装をコミットしたうえで検証を実行する**:
    `python3 harness/scripts/run_verification.py --app <app-id> --feature <feature-id>`
    設計時に宣言されたコマンド（テスト・ビルド・型チェック・Lint）が実行され、結果が
    `status.yaml` の `verification_receipt` に記録される。受領書を自分で書くことはできない。
    - 実装を修正したら、コミットし直してから検証も実行し直すこと（受領書はコミットに紐づく）。
    - 検証コマンドが生成するファイル（JUnit XML・キャッシュ等）は `.gitignore` に入れる。
    - `verification:` が宣言されていない場合は実装を止めてユーザーに報告する
      （設計フェーズで決めるべき事項であり、`feature-builder` は宣言を追加できない）。

11. **受領書 → `TESTED` は「1 コミットにまとめる」**。ここは順序を間違えると必ず詰まる:

    ```
    実装をコミット            ← ここで HEAD が確定する
    run_verification.py 実行  ← 受領書に「この HEAD で通した」と記録される
    status.yaml を TESTED に  ← まだコミットしない
    git add -A && git commit  ← 受領書と TESTED を一緒に記録する
    ```

    受領書を書いた `status.yaml` を**先にコミットしてしまうと HEAD が進み**、
    `受領書の commit != HEAD` になって Rule 10 が `TESTED` を拒否する。検証をやり直す羽目になるので、
    **受領書を作ったらコミットせずに `TESTED` へ進め、最後に 1 回だけコミットする**こと。
    Rule 8 は「応答を終える時点」で未コミットを見るので、この手順なら衝突しない。逆に受領書を
    作った直後に応答を終えようとすると Rule 8 に止められる。

    **検証が失敗した場合**は `TESTED` へは進まず（Rule 10 が拒否する）、失敗した受領書を含む
    `status.yaml` をそのままコミットしてよい（`state` は変えないので Rule 10 は関与しない）。
    その後、原因を直して実装を再コミット→検証をやり直し、受領書を作り直すこと。

12. 検証が通り `code-review` への対応も終わったら `state: TESTED` に更新する。
13. `SPEC.md` は人間向けの補足として、実装方針や既知の制約を追記してよい。

## 5. Bash 利用上の注意（worktree セッション固有）

14. **ファイルの作成・編集には Write/Edit ツールを使う**。worktree に隔離されたセッションでは、
    ヒアドキュメント（`cat > file <<'EOF'`）や `;` で繋いだ複合コマンドが
    「worktree の中に留まるか検証できない」として実行前に拒否されることがある。
    確認用の `git` コマンドも 1 コマンドずつ単純な形で実行すること
    （`git -C . ...` のような形も拒否される）。
15. **Bash の cwd は呼び出しをまたいで保持されない**（毎回 worktree ルートに戻る）。
    `cd <絶対パス> && <単一コマンド>` の形で毎回実行すること（`&&` は可、`;` は不可）。
16. 状態を進めるたびに `git add -A && git commit` してこの worktree のブランチに記録する
    （未コミットのままだと `integrator` が統合時に取り込めない）。
    ただし **手順 11 の受領書 → `TESTED` だけは 1 コミットにまとめる**（途中でコミットしない）。
