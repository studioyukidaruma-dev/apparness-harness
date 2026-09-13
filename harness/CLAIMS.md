# CLAIMS.md — 主張と証跡の対応表

このハーネスが「これをブロックする」と主張している規則（Hook Rule / CI 項目）と、
**それが今も本当にブロックすることを実証しているテスト**の対応表。オンデマンド読み込み文書なので
コンテキスト予算（`CONVENTIONS.md` 15節）の対象外。

なぜ要るか: ドッグフーディングの F-029 / F-030 では、Rule 1・2・3・5・9・10 が
**まとめて空振りしていた**（`.worktrees/` 経由のパスがどの正規表現にもマッチしなかった）。
テストは 17 ファイル 3,800 行あったのに、「Rule N がブロックすること」を Rule 単位で追える索引が
無かったため、中核ルール群が丸ごと効かなくなっていても誰も気付けなかった。この表はその索引である。

**運用**: 規則を足したら、この表に行を足し、実証テストを書くまで完了扱いにしない。
`ci_check.py` の項目 P が、この表に書かれたテストが `harness/tests/` に実在することを検証する
（表と実体の drift 防止）。実証できない主張は「実証テスト」を `—` にして、
**「未実証の残余」列に、なぜ実証できないかを必ず書く**（空欄は項目 P が拒否する）。

テストの書式は `<ファイル名>::<テスト関数名>`。1 行に複数書いてよい。

---

## Hook Rule（`CONVENTIONS.md` 7節）

| 規則 | 何をブロックすると主張するか | 実証テスト | 最終実証日 | 未実証の残余 |
|---|---|---|---|---|
| Rule 1 | `harness/**`・`.claude/**`・`.github/**` への書き込み（`harness/` ブランチ以外） | `test_pre_tool_use_guard.py::test_rule1_blocks_harness_writes_outside_harness_branches` / `test_rule_coverage.py::test_rule1_blocks_harness_writes_through_a_worktree_path` | 2026-08-24 | `HARNESS_UNLOCK=1` による解除は意図的な緊急避難路（8節）であり、ブロック対象外 |
| Rule 2 | 担当外の機能ディレクトリへの書き込み | `test_worktree_scope.py::test_rule2_blocks_write_into_other_worktree_from_main` | 2026-08-24 | git 情報が取れない場合は判定不能として通す（`get_worktree_toplevel` が None） |
| Rule 3 | 凍結後の `contract.yaml` の変更（`open_issues[]` 追記を除く） | `test_pre_tool_use_guard.py::test_rule3_freezes_the_contract_after_approval` / `test_pre_tool_use_guard.py::test_rule3_rejects_contract_approved_without_approver` / `test_rule_coverage.py::test_rule3_blocks_a_frozen_contract_through_a_worktree_path` | 2026-08-24 | — |
| Rule 4 | （ブロックではなく実行）`status.yaml` 更新時のダッシュボード再生成 | `test_rule_coverage.py::test_rule4_regenerates_the_dashboard_when_status_changes` | 2026-08-24 | 非ブロッキング（PostToolUse）なので、失敗しても書き込み自体は成立する。これは仕様 |
| Rule 5 | 必須 Skill が未有効のまま `src/**` へ書き込むこと | `test_pre_tool_use_guard.py::test_rule5_blocks_the_feature_named_in_applies_to` / `test_rule_coverage.py::test_rule5_blocks_missing_required_skills_through_a_worktree_path` | 2026-08-24 | `enabledPlugins` に載っていても Skill が実際に動くかは検証できない（Claude Code 側の責務） |
| Rule 6 | feature worktree から上位文書（要件・共有基盤・設計）への書き込み | `test_rule_coverage.py::test_rule6_blocks_upstream_documents_from_a_feature_worktree` / `test_rule_coverage.py::test_rule6_judges_by_the_session_not_by_the_target_tree` | 2026-08-24 | — |
| Rule 7 | 承認記録を伴わない `status: APPROVED`／要件版の不一致 | `test_pre_tool_use_guard.py::test_rule7_rejects_architecture_approved_without_approver` / `test_pre_tool_use_guard.py::test_rule7_rejects_requirements_approved_without_approver` / `test_pre_tool_use_guard.py::test_rule7_still_checks_requirements_version_consistency` | 2026-08-24 | `approved_by` に書かれた識別子が**本当に人間か**は判定できない（9節・`docs/HARNESS_GUIDE.md` 18-4） |
| Rule 8 | フェーズ節目ファイルを未コミットのまま応答を終えること | `test_rule_coverage.py::test_rule8_blocks_stopping_with_an_uncommitted_status_yaml` / `test_rule_coverage.py::test_rule8_blocks_stopping_with_an_untracked_phase_marker` | 2026-08-24 | `stop_hook_active` が真のときは無限ループ回避のため通す（意図的な穴） |
| Rule 9 | 不正な `state` 遷移（後退・飛び越し・終端からの変更） | `test_pre_tool_use_guard.py::test_rule9_rejects_skipping_states` / `test_pre_tool_use_guard.py::test_rule9_blocks_skipping_through_blocked` / `test_worktree_scope.py::test_rule9_blocks_multi_step_jump_via_worktree_path` | 2026-08-24 | — |
| Rule 10 | 受領書なし／失敗／HEAD 不一致の `TESTED`、および受領書の手書き | `test_pre_tool_use_guard.py::test_rule10_rejects_tested_without_receipt` / `test_pre_tool_use_guard.py::test_rule10_rejects_a_receipt_from_another_commit` / `test_pre_tool_use_guard.py::test_rule10_rejects_handwritten_receipts` / `test_worktree_scope.py::test_rule10_blocks_tested_without_receipt_via_worktree_path` | 2026-08-24 | 宣言されたコマンドが**意味のあるテストか**は判定しない（ハーネスは規定しない。12節） |
| Rule 11 | 結線カバレッジ・受領書を欠いた `INTEGRATED` | `test_pre_tool_use_guard.py::test_rule11_blocks_integrated_without_integration_record` / `test_pre_tool_use_guard.py::test_rule11_blocks_integrated_with_a_coverage_gap` / `test_pre_tool_use_guard.py::test_rule11_rejects_handwritten_integration_receipt` | 2026-08-24 | — |
| Rule 12 | 危険操作（再帰削除・秘密ファイル読み取り・履歴破壊・検証スキップ・外部送信・sudo） | `test_dangerous_ops.py::test_d1_blocks_recursive_delete_outside_the_repository` / `test_dangerous_ops.py::test_d2_blocks_reading_secrets` / `test_dangerous_ops.py::test_d3_blocks_history_destruction` / `test_dangerous_ops.py::test_d4_blocks_skipping_verification` / `test_dangerous_ops.py::test_d5_blocks_external_upload` / `test_dangerous_ops.py::test_d6_blocks_sudo` / `test_dangerous_ops.py::test_rule12_has_no_bypass_environment_variable` | 2026-08-24 | 変数展開・エイリアス・自作スクリプト経由の間接実行は静的検知の原理的な限界。事後検証（`post_tool_use_guard.py`）は書き込みしか見ないため、読み取り・送信の事後検知は無い |

## Bash 経由の間接書き込み（7節末尾）

| 規則 | 何をブロックすると主張するか | 実証テスト | 最終実証日 | 未実証の残余 |
|---|---|---|---|---|
| 手段の制限 | 内容比較で判定するファイル（`status.yaml`・`requirements.machine.yaml`・`architecture.machine.yaml`・`integration.machine.yaml`）を、結果を再現できない手段（Bash・NotebookEdit 等）で書くこと | `test_pre_tool_use_guard.py::test_notebook_edit_cannot_write_content_judged_files` / `test_pre_tool_use_guard.py::test_bash_cannot_write_content_judged_files` / `test_pre_tool_use_guard.py::test_integration_receipt_cannot_be_handwritten_through_bash` / `test_pre_tool_use_guard.py::test_the_simulatable_tool_set_matches_simulate_write_result` | 2026-08-24 | 事後検証は実行主体を問わないため、この制限を掛けない（掛けると `run_verification.py` の受領書が巻き戻る）。その逃がしは `test_post_tool_use_guard.py::test_a_harness_script_writing_the_receipt_is_not_reverted` が固定 |
| 静的検知 | `sed -i`/`cp`/`mv`/`tee`/リダイレクトによるガード対象への書き込み | `test_pre_tool_use_guard.py::test_bash_indirect_write_to_a_guarded_path_is_blocked` / `test_pre_tool_use_guard.py::test_bash_cannot_write_files_judged_by_content_comparison` / `test_path_utils_bash.py::test_the_heredoc_redirect_target_is_still_detected` | 2026-08-24 | 変数展開されたパスは原理的に検知できない（だから事後検証がある）。ヒアドキュメント本体は**データ**として抽出対象から外している（T-020） |
| 事後検証 | 静的検知をすり抜けた書き込みの検出と巻き戻し | `test_post_tool_use_guard.py::test_variable_expanded_path_is_detected_and_reverted` / `test_post_tool_use_guard.py::test_write_through_a_script_is_detected_and_reverted` | 2026-08-24 | 実行そのものは止められない（PostToolUse なので事後）。巻き戻せるのはファイル内容だけ |

## CI 項目（`ci_check.py`）

| 規則 | 何をブロックすると主張するか | 実証テスト | 最終実証日 | 未実証の残余 |
|---|---|---|---|---|
| 項目 A | JSON Schema に違反する machine-readable YAML | `test_ci_items.py::test_item_a_rejects_a_status_yaml_violating_its_schema` / `test_schema_draft.py::test_non_draft_requirements_must_not_be_blank` / `test_schema_draft.py::test_non_draft_architecture_must_have_features` | 2026-08-24 | — |
| 項目 B | `harness/` ブランチ以外からのハーネス本体の変更 | `test_ci_items.py::test_item_b_rejects_harness_changes_from_a_feature_branch` | 2026-08-24 | `main` では判定しない（fast-forward マージ後は出自が git 上に残らない） |
| 項目 C | feature ブランチによる担当範囲外の変更 | `test_dogfooding_fixes.py::test_feature_branch_scope_still_blocks_other_features` | 2026-08-24 | — |
| 項目 D | 凍結後の contract.yaml の変更 | `test_dogfooding_fixes.py::test_contract_freeze_still_blocks_edit_after_approval` | 2026-08-24 | — |
| 項目 E | 要件の現在版を参照していない APPROVED な設計 | `test_ci_items.py::test_item_e_rejects_an_approved_design_pinned_to_an_old_requirements_version` | 2026-08-24 | — |
| 項目 F | コミット間の不正な state 遷移 | `test_ci_items.py::test_item_f_rejects_a_multi_step_jump_between_commits` | 2026-08-24 | 新規追加ファイルは旧状態が無いため判定不能（意図的） |
| 項目 G | 古い PROGRESS.md / STATE.machine.yaml | `test_ci_items.py::test_item_g_rejects_a_stale_dashboard` / `test_ci_items.py::test_item_g_does_not_leave_the_worktree_dirty` | 2026-08-24 | feature ブランチでは構造的に満たせないためスキップする（`test_dogfooding_fixes.py::test_progress_freshness_is_skipped_on_feature_branch`） |
| 項目 I | 受領書を欠く／検証後に実装が変わった TESTED・INTEGRATED | `test_ci_items.py::test_item_i_rejects_tested_without_a_receipt` / `test_ci_items.py::test_item_i_rejects_an_implementation_changed_after_verification` | 2026-08-24 | — |
| 項目 J | `interfaces[]` の両端の JSON Schema 不整合 | `test_interface_check.py::test_unknown_producer_feature` / `test_interface_check.py::test_unknown_output_name` | 2026-08-24 | `$ref` は解決しない（6節。だからインライン展開を規定している） |
| 項目 K | MUST 要件の取りこぼし・存在しない FR ID の参照 | `test_traceability.py::test_uncovered_must_requirement_is_detected` | 2026-08-24 | — |
| 項目 L | コンテキスト予算の超過と、別ファイルへの退避による空洞化 | `test_context_budget.py::test_oversized_conventions_is_detected` / `test_context_budget.py::test_oversized_agent_is_detected` / `test_context_budget.py::test_session_total_is_detected` / `test_context_budget.py::test_moving_the_prompt_into_a_procedure_does_not_dodge_the_budget` / `test_context_budget.py::test_undeclared_procedure_read_is_detected` | 2026-08-24 | 条件付きで読まれる文書（`quality/*.md`・`STACK_PACK.md`）は計上しない。読むかどうかが実行時の分岐に依存し、静的には決まらないため |
| 項目 M | CONVENTIONS.md と agent/skill プロンプトの二重管理 | `test_context_budget.py::test_near_verbatim_copy_into_an_agent_is_detected` / `test_context_budget.py::test_duplication_in_a_skill_is_detected_too` | 2026-08-24 | 言い換えを伴う重複は検出しない（閾値を上げると正当な具体化まで落ちるため。意図的） |
| 項目 N | `interfaces[]` のエッジが結合テストに対応づけられていないこと | `test_check_integration_traceability.py::test_partial_coverage_still_reports_gaps` | 2026-08-24 | — |
| 項目 O | CONVENTIONS.md への節の新設 | `test_conventions_frozen.py::test_new_section_is_rejected` | 2026-08-24 | 節の削除・既存節の変更は凍結の対象外（意図的） |
| 項目 P | この表に書かれた実証テストが実在しないこと | `test_claims.py::test_unknown_test_name_is_rejected` / `test_claims.py::test_missing_evidence_without_a_reason_is_rejected` | 2026-08-24 | この表に**行を足し忘れた**規則は検出できない（規則の追加は人間の判断） |
| 項目 Q | ハーネス本体の変更に CHANGELOG の追随が無いこと | `test_versioning.py::test_harness_change_without_a_changelog_entry_is_rejected` / `test_versioning.py::test_an_empty_unreleased_section_is_rejected` / `test_versioning.py::test_a_version_bump_without_its_section_is_rejected` | 2026-08-24 | CHANGELOG の内容が正しいかは判定しない（記述の有無だけを見る） |

## 脆弱性走査（`vuln_scan.py` / `vuln-scan` job）

| 規則 | 何をブロックすると主張するか | 実証テスト | 最終実証日 | 未実証の残余 |
|---|---|---|---|---|
| 検出 | `apps/**` の依存ライブラリに含まれる既知の脆弱性 | `test_vuln_scan.py::test_behaviour_is_unchanged_when_no_ignore_file_exists` / `test_vuln_scan.py::test_summarize_without_rules_reports_everything` | 2026-08-24 | `osv-scanner` バイナリが無ければスキップして exit 0（Layer 1.5 と同じ非致命的な位置づけ）。ブランチ保護は掛けていないため、マージを機械的には止めない |
| 抑制の規律 | 期限（`expires`）・理由（`reason`）を欠く抑制、書式が不正な日付、期限切れの抑制（`apps/<app-id>/.vuln-ignore`） | `test_vuln_scan.py::test_a_line_without_expires_is_rejected_with_its_line_number` / `test_vuln_scan.py::test_a_line_without_reason_is_rejected` / `test_vuln_scan.py::test_an_expired_line_is_rejected` / `test_vuln_scan.py::test_the_ignore_file_is_validated_before_the_scan_runs` | 2026-08-24 | 書かれた `reason` が妥当かは判定しない（記述の有無と期限だけを見る。CI 項目 Q と同じ立場） |
| 抑制の可視性 | （ブロックではなく報告）抑制した検出を黙って消すこと | `test_vuln_scan.py::test_a_valid_suppression_excludes_the_finding_and_says_so` / `test_vuln_scan.py::test_a_suppression_does_not_leak_into_another_app` | 2026-08-24 | — |

## 企画ブリーフ（`new_brief.py` / `check_brief.py`）

| 規則 | 何をブロックすると主張するか | 実証テスト | 最終実証日 | 未実証の残余 |
|---|---|---|---|---|
| 書式検証 | 項目名の綴り違い・未知の項目・不正な値が**黙って無視される**こと（「書いたのに伝わらない」を防ぐ） | `test_brief.py::test_a_misspelled_field_is_rejected` / `test_brief.py::test_a_must_feature_without_a_title_is_rejected` / `test_brief.py::test_an_unknown_autonomy_mode_is_rejected` | 2026-08-24 | 書かれた**内容**が正しいかは判定しない（要件として妥当かは人間の承認で決まる。9節） |
| 未記入の列挙 | （ブロックではなく報告）どの項目が空で、そのうちどれを対話で確認すべきかを機械的に確定させる | `test_brief.py::test_a_blank_brief_reports_the_essentials_as_must` / `test_brief.py::test_filled_fields_are_not_reported_as_missing` / `test_brief.py::test_a_must_feature_without_acceptance_is_reported_as_must` / `test_brief.py::test_whitespace_only_is_treated_as_blank` | 2026-08-24 | 記入済みを**聞き直さない**こと・空欄を**推測で埋めない**ことは AI の振る舞いであり機械的には強制できない（列挙までが機械の担保。指示は `requirements-analyst` に置く） |
| 雛形とスキーマの一致 | 生成される記入用フォーマットがスキーマから drift すること | `test_brief.py::test_the_generated_blank_brief_satisfies_the_schema` / `test_brief.py::test_ci_item_a_accepts_the_generated_brief` / `test_brief.py::test_new_brief_does_not_overwrite_without_force` | 2026-08-24 | — |
| 入力の記録 | ブリーフを渡したのに生成物に残らないこと・存在しないブリーフで雛形が中途半端に作られること | `test_brief.py::test_the_scaffold_copies_the_brief_into_the_app` / `test_brief.py::test_the_scaffold_stops_before_creating_anything_if_the_brief_is_missing` / `test_brief.py::test_the_scaffold_without_a_brief_creates_no_brief_file` | 2026-08-24 | 取り込んだ `brief.yaml` と最終的な要件の**内容の一致**は突合しない（要件は対話で補われ、ブリーフを超えるのが正常なため） |

## 強制レイヤ自体の健全性

| 規則 | 何をブロックすると主張するか | 実証テスト | 最終実証日 | 未実証の残余 |
|---|---|---|---|---|
| fail-closed | ガード本体で想定外の例外が起きたとき、通過ではなく拒否になること | `test_healthcheck.py::test_unexpected_exception_denies_instead_of_passing` / `test_healthcheck.py::test_the_guard_still_passes_normally_when_nothing_is_wrong` | 2026-08-24 | `python3` 自体が存在しない場合は Hook が起動できないため、ハーネスからは何もできない（SessionStart の自己診断と PROGRESS.md 表示で**可視化**するのが対策） |
| 入力の健全性 | hook の入力が JSON として読めない／書き込み先が入っていない場合に、通過させずに拒否すること（`pre_tool_use_guard.py`・`stop_commit_guard.py`） | `test_healthcheck.py::test_corrupt_hook_input_denies_instead_of_passing` / `test_healthcheck.py::test_a_structured_edit_without_a_path_denies_instead_of_passing` / `test_healthcheck.py::test_corrupt_stop_hook_input_denies_instead_of_passing` / `test_healthcheck.py::test_empty_hook_input_still_passes` | 2026-08-24 | 空の stdin は通す（ホストが payload 無しでイベントを呼ぶ経路を止めると通常運用が壊れるため。意図的な穴）。非ブロッキングな hook（`post_tool_use_sync.py`・`post_tool_use_guard.py`）は寛容版のまま |
| 劣化の可視化 | git 情報が取れず Rule 1・2・6・10・11 の判定が劣化していることを、セッション開始時に警告すること | `test_healthcheck.py::test_session_start_warns_when_git_is_unavailable` / `test_healthcheck.py::test_git_enforcement_degradation_is_reported_outside_a_repository` / `test_healthcheck.py::test_session_start_is_silent_when_healthy` | 2026-08-24 | 警告するだけで強制はしない（非 git 環境での正当な利用を壊さないため exit 0 のまま）。`PROGRESS.md` には出さない（実行環境依存の判定を混ぜると CI 項目 G が構造的に落ちる） |
| 自己診断 | 強制レイヤが壊れている状態を検出して報告すること | `test_healthcheck.py::test_broken_hook_import_is_reported` / `test_healthcheck.py::test_missing_hook_registration_is_reported` / `test_healthcheck.py::test_progress_line_reports_the_problem_when_broken` | 2026-08-24 | 検出できても Claude Code 側の Hook 実行を止める手段は無い（報告と可視化まで） |

## 深刻度 最高・高 の摩擦点 → 再発防止テスト

実地でアプリを作りながら記録した 77 件の摩擦点は、このハーネスが本当に壊れた記録であり、
いちばん価値の高い入力である。ところが**テストへの変換が場当たり**だった（改修計画 F-A10）。

**ルール: 深刻度が「最高」または「高」の摩擦点は、再発を検出するテストが無い状態でクローズしない。**
テストが書けないものは、この表の「未実証の残余」列に**なぜ書けないか**を書く（空欄は CI 項目 P が拒否する）。
中・低の摩擦点はこの表の対象外（テストがあれば書いてよいが、必須ではない）。

手順は `docs/maintenance/friction-to-test.md`（人間向け。ハーネスの実行には関与しない）。

| 規則 | 何が起きたか | 再発防止テスト | 最終実証日 | 未実証の残余（テスト不要の理由） |
|---|---|---|---|---|
| F-004（高） | subagent に `AskUserQuestion` が実際には渡らない | — | — | ハーネス外（どのツールを subagent に渡すかは Claude Code の挙動）。プロンプト側で「渡らない前提で書く」ことでしか対処できない |
| F-008（高） | 要件・設計の承認では `PROGRESS.md` が再生成されない | `test_dogfooding_fixes.py::test_progress_sync_triggers_on_approval_documents` | 2026-08-24 | — |
| F-010（高） | 承認の「人間性」が subagent 経由で構造的に失われる | `test_pre_tool_use_guard.py::test_rule7_rejects_requirements_approved_without_approver` | 2026-08-24 | 承認者が**本当に人間か**は機械的に判定できない（`docs/HARNESS_GUIDE.md` 11節 A-3）。テストで固定できるのは「承認記録を伴わない APPROVED を拒否する」ところまで |
| F-014（最高） | feature worktree が `main` から切られ、上位文書が入らない | `test_dogfooding_fixes.py::test_tracked_in_head_detects_documents_on_another_branch` / `test_dogfooding_fixes.py::test_tracked_in_head_is_false_for_uncommitted_file` | 2026-08-24 | — |
| F-015（高） | `check_traceability.py` が設計フェーズで実質何も検証しない（指示どおり実行すると偽の安心を得る） | `test_traceability.py::test_design_phase_drafts_are_loaded` / `test_traceability.py::test_design_phase_gap_is_detected_before_any_worktree_exists` | 2026-08-24 | — |
| F-016（高） | CI 項目 D が、設計フェーズを 1 ブランチで完結させると必ず不合格 | `test_dogfooding_fixes.py::test_contract_freeze_allows_draft_then_approve_in_one_branch` / `test_dogfooding_fixes.py::test_contract_freeze_still_blocks_edit_after_approval` | 2026-08-24 | — |
| F-021（高） | Bash 経由の書き込みが Rule 7・9・10 を回避できる | `test_pre_tool_use_guard.py::test_bash_cannot_write_files_judged_by_content_comparison` / `test_pre_tool_use_guard.py::test_bash_can_still_read_those_files` | 2026-08-24 | — |
| F-029（高） | `.worktrees/` を通るパスでは Rule 2・3・5・10 が一切発火しない | `test_worktree_scope.py::test_rule2_blocks_write_into_other_worktree_from_main` / `test_rule_coverage.py::test_rule3_blocks_a_frozen_contract_through_a_worktree_path` / `test_rule_coverage.py::test_rule5_blocks_missing_required_skills_through_a_worktree_path` | 2026-08-24 | — |
| F-030（最高） | 受領書なしで `state: TESTED` を書き込めた | `test_worktree_scope.py::test_rule10_blocks_tested_without_receipt_via_worktree_path` / `test_worktree_scope.py::test_rule9_blocks_multi_step_jump_via_worktree_path` | 2026-08-24 | — |
| F-031（高） | `feature-builder` を subagent として起動する経路が存在しない | — | — | 起動経路は Claude Code の Task ツールと agent 定義の問題で、ハーネスからは実行して確かめられない。`harness/procedures/feature-build.md` の手順で担保する |
| F-033（高） | 受領書とコミットの順序が罠になっており、Rule 8 と噛み合わない | `test_pre_tool_use_guard.py::test_rule10_rejects_a_receipt_from_another_commit` / `test_rule_coverage.py::test_rule8_blocks_stopping_with_an_uncommitted_status_yaml` | 2026-08-24 | 「正しい順序を踏むか」は手順の問題でテストできない。テストで固定できるのは、順序を間違えたときに**両方のルールが期待どおり拒否する**ことまで |
| F-036（高） | CI 項目 G と項目 C（Rule 2）が feature ブランチ上で両立しない | `test_dogfooding_fixes.py::test_progress_freshness_is_skipped_on_feature_branch` / `test_dogfooding_fixes.py::test_feature_branch_may_carry_regenerated_progress_files` | 2026-08-24 | — |
| F-048（高） | `CONVENTIONS.md` と agent プロンプトの二重管理 | `test_context_budget.py::test_near_verbatim_copy_into_an_agent_is_detected` / `test_context_budget.py::test_this_repository_has_no_duplication` | 2026-08-24 | 言い換えを伴う重複は検出しない（閾値を上げると正当な具体化まで落ちる） |
| F-049（高） | worktree 内の `harness/` と、実際に走る Hook の `harness/` がバージョンずれする | `test_dogfooding_fixes.py::test_harness_root_from_a_worktree_points_at_the_main_repo` / `test_dogfooding_fixes.py::test_resolve_harness_path_remaps_a_stale_worktree_copy` | 2026-08-24 | — |
| F-050（高） | `git add` が事後検証を誤発火させ、正当な `open_issues[]` 追記を巻き戻す | `test_post_tool_use_guard.py::test_git_add_alone_does_not_trigger_a_revert` / `test_post_tool_use_guard.py::test_further_change_to_an_already_dirty_path_is_detected` | 2026-08-24 | — |
| F-055（高） | worktree の外へ出る書き込みは、どの Rule にも掛からない | `test_dogfooding_fixes.py::test_writing_outside_the_worktree_is_blocked` / `test_dogfooding_fixes.py::test_writing_outside_the_worktree_through_a_relative_path_is_blocked` | 2026-08-24 | — |
| F-061（高） | `parse_simple_yaml` が `- >-` を解釈できず、以降のトップレベルキーが丸ごと消える | `test_yaml_parser.py::test_block_scalar_as_sequence_item_does_not_lose_following_keys` / `test_yaml_parser.py::test_literal_block_scalar_as_sequence_item` | 2026-08-24 | — |
| F-063（高） | セッションが自分から Agent/Skill をバックグラウンド起動すると cwd 追跡が失われる | — | — | ハーネス外（Claude Code のセッション管理）。ハーネスから観測も再現もできない。`harness/procedures/feature-build.md` の Bash 注意事項で回避する |
| F-073（高） | Rule 10/11 の commit 照合が worktree の HEAD ではなく生の cwd を見ていた | `test_worktree_scope.py::test_rule10_uses_worktree_head_not_session_cwd_head` | 2026-08-24 | — |
| F-074（高） | 統合カバレッジ判定の「統合前は許可する」免除が、scaffold の空テンプレートで機能していなかった | `test_check_integration_traceability.py::test_scaffolded_empty_template_is_treated_as_not_started` / `test_check_integration_traceability.py::test_partial_coverage_still_reports_gaps` | 2026-08-24 | — |
| F-080（高） | Bash の `cd` 誤操作で Edit/Write のツール cwd 追跡が復旧不能になった | — | — | ハーネス外（Claude Code の cwd 追跡）。F-063 と同根。回避手順は `harness/procedures/feature-build.md` |
