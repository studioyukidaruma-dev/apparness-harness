# feature-build.md — 機能実装フェーズの手順

`feature-builder` が着手時に 1 回読む。**規範は書かない**（規範は `CONVENTIONS.md`、違反すれば
Hook が止め、そのエラーメッセージが直し方を示す）。ここにあるのは**順序**だけ——順序は
Hook のエラーメッセージでは伝わらないため、事前に読む価値がある唯一の情報である。

## 1. 着手

1. `SPEC.md` と `contract.yaml` を読む。
2. `status.yaml` を `state: IN_PROGRESS` にする（`state_history` の末尾、`review:` より前に追記）。
3. `harness/quality/security-baseline.md` を読む。UI を持つ機能なら `design-baseline.md` も。
4. `../../01-foundation/shared-kernel.yaml` の `required_skills[]` を確認する。
   `kind: stack-pack` があれば実装前に読む（`harness/quality/*.md` のベースラインが常に優先）。

## 2. 実装

5. `contract.yaml` の `inputs`/`outputs`/`error_cases`/`tech_stack` を満たすように `src/` と
   `tests/` を書く。**`test_strategy.coverage[]` の `test_ids` は、そのままの名前で実在させる**
   （検証時に JUnit XML と突合される）。契約に無い観点のテストを足すのは自由。
6. 契約の小さな穴に気づいたら `contract.yaml` の `open_issues[]` に**追記**する
   （`{ id, summary, found_at, found_by }`）。`SPEC.md` に書くだけでは機械検証に載らない。
   `summary` は「`integrator` が触れるのは `04-integration/` だけ」という前提で書く
   （結線側の吸収案か、再設計の要否が伝わる書き方にする）。
7. `state: IMPLEMENTED` にする。

## 3. `TESTED` にする前に、レビューを 2 つ通す

8. `code-review` skill を実行する。見つからなければユーザーに報告して先へ進んでよい。
   subagent 起動ができない場合は、skill 内の代替手順を自分のコンテキストで実施する
   （レビュー自体は飛ばさない）。
9. `git add -A && git commit` してから `gate-reviewer` subagent に依頼する
   （Task ツール / `subagent_type: gate-reviewer`）。先にコミットするのは、レビュー対象を
   確定させるためと、未コミットのまま subagent が停止すると Rule 8 に止められるため。
   - `NO-GO` なら指摘に対応して再依頼する。**契約やテストを都合よく書き換えて回避しない。**
   - 3 ラウンド続けて `NO-GO` ならユーザーにエスカレーションする。
   - 結果を `status.yaml` の `review` に記録する。`blockers`/`majors`/`minors` は
     **件数（整数）**。指摘の本文は `notes`（文字列 1 本）に入れる。

## 4. 検証 → `TESTED` は 1 コミットにまとめる（ここが唯一の罠）

```
実装をコミット            ← ここで HEAD が確定する
run_verification.py 実行  ← 受領書に「この HEAD で通した」と記録される
status.yaml を TESTED に  ← まだコミットしない
git add -A && git commit  ← 受領書と TESTED を一緒に記録する
```

`python3 harness/scripts/run_verification.py --app <app-id> --feature <feature-id>`

受領書を書いた `status.yaml` を**先にコミットすると HEAD が進み**、Rule 10 が `TESTED` を
拒否する。検証のやり直しになるので、**受領書を作ったらコミットせずに `TESTED` へ進め、
最後に 1 回だけコミットする**。

- 検証が**失敗**したら `TESTED` へは進まず、失敗した受領書ごとコミットしてよい。
  原因を直して再コミット → 検証をやり直す。
- 実装を直したら、コミットし直してから検証も実行し直す（受領書はコミットに紐づく）。
- 検証コマンドの生成物（JUnit XML・キャッシュ）は `.gitignore` に入れる。
- `verification:` が未宣言なら実装を止めて報告する（設計フェーズの事項で、ここでは直せない）。

10. 通ったら `state: TESTED` にする。`SPEC.md` に実装方針や既知の制約を追記してよい。

## 5. Bash の注意（worktree セッション固有）

- ファイルの作成・編集は Write/Edit を使う。ヒアドキュメントや `;` で繋いだ複合コマンドは
  拒否されることがある。
- **Bash の cwd は呼び出しをまたいで保持されない。** 毎回 `cd <絶対パス> && <単一コマンド>`
  の形で実行する（`&&` は可、`;` は不可）。
- 状態を進めるたびにコミットする。ただし **4 の受領書 → `TESTED` だけは 1 コミット**。
