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
| Rule 7 | 承認記録を伴わない `status: APPROVED`／要件版の不一致 | `test_pre_tool_use_guard.py::test_rule7_rejects_architecture_approved_without_approver` / `test_pre_tool_use_guard.py::test_rule7_rejects_requirements_approved_without_approver` / `test_pre_tool_use_guard.py::test_rule7_still_checks_requirements_version_consistency` | 2026-08-24 | `approved_by` に書かれた識別子が**本当に人間か**は判定できない（9節・`HARNESS_GUIDE.md` 18-4） |
| Rule 8 | フェーズ節目ファイルを未コミットのまま応答を終えること | `test_rule_coverage.py::test_rule8_blocks_stopping_with_an_uncommitted_status_yaml` / `test_rule_coverage.py::test_rule8_blocks_stopping_with_an_untracked_phase_marker` | 2026-08-24 | `stop_hook_active` が真のときは無限ループ回避のため通す（意図的な穴） |
| Rule 9 | 不正な `state` 遷移（後退・飛び越し・終端からの変更） | `test_pre_tool_use_guard.py::test_rule9_rejects_skipping_states` / `test_pre_tool_use_guard.py::test_rule9_blocks_skipping_through_blocked` / `test_worktree_scope.py::test_rule9_blocks_multi_step_jump_via_worktree_path` | 2026-08-24 | — |
| Rule 10 | 受領書なし／失敗／HEAD 不一致の `TESTED`、および受領書の手書き | `test_pre_tool_use_guard.py::test_rule10_rejects_tested_without_receipt` / `test_pre_tool_use_guard.py::test_rule10_rejects_a_receipt_from_another_commit` / `test_pre_tool_use_guard.py::test_rule10_rejects_handwritten_receipts` / `test_worktree_scope.py::test_rule10_blocks_tested_without_receipt_via_worktree_path` | 2026-08-24 | 宣言されたコマンドが**意味のあるテストか**は判定しない（ハーネスは規定しない。12節） |
| Rule 11 | 結線カバレッジ・受領書を欠いた `INTEGRATED` | `test_pre_tool_use_guard.py::test_rule11_blocks_integrated_without_integration_record` / `test_pre_tool_use_guard.py::test_rule11_blocks_integrated_with_a_coverage_gap` / `test_pre_tool_use_guard.py::test_rule11_rejects_handwritten_integration_receipt` | 2026-08-24 | — |
| Rule 12 | 危険操作（再帰削除・秘密ファイル読み取り・履歴破壊・検証スキップ・外部送信・sudo） | `test_dangerous_ops.py::test_d1_blocks_recursive_delete_outside_the_repository` / `test_dangerous_ops.py::test_d2_blocks_reading_secrets` / `test_dangerous_ops.py::test_d3_blocks_history_destruction` / `test_dangerous_ops.py::test_d4_blocks_skipping_verification` / `test_dangerous_ops.py::test_d5_blocks_external_upload` / `test_dangerous_ops.py::test_d6_blocks_sudo` / `test_dangerous_ops.py::test_rule12_has_no_bypass_environment_variable` | 2026-08-24 | 変数展開・エイリアス・自作スクリプト経由の間接実行は静的検知の原理的な限界。事後検証（`post_tool_use_guard.py`）は書き込みしか見ないため、読み取り・送信の事後検知は無い |

## Bash 経由の間接書き込み（7節末尾）

| 規則 | 何をブロックすると主張するか | 実証テスト | 最終実証日 | 未実証の残余 |
|---|---|---|---|---|
| 静的検知 | `sed -i`/`cp`/`mv`/`tee`/リダイレクトによるガード対象への書き込み | `test_pre_tool_use_guard.py::test_bash_indirect_write_to_a_guarded_path_is_blocked` / `test_pre_tool_use_guard.py::test_bash_cannot_write_files_judged_by_content_comparison` | 2026-08-24 | 変数展開されたパスは原理的に検知できない（だから事後検証がある） |
| 事後検証 | 静的検知をすり抜けた書き込みの検出と巻き戻し | `test_post_tool_use_guard.py::test_variable_expanded_path_is_detected_and_reverted` / `test_post_tool_use_guard.py::test_write_through_a_script_is_detected_and_reverted` | 2026-08-24 | 実行そのものは止められない（PostToolUse なので事後）。巻き戻せるのはファイル内容だけ |

## CI 項目（`ci_check.py`）

| 規則 | 何をブロックすると主張するか | 実証テスト | 最終実証日 | 未実証の残余 |
|---|---|---|---|---|
| 項目 A | JSON Schema に違反する machine-readable YAML | `test_ci_items.py::test_item_a_rejects_a_status_yaml_violating_its_schema` | 2026-08-24 | — |
| 項目 B | `harness/` ブランチ以外からのハーネス本体の変更 | `test_ci_items.py::test_item_b_rejects_harness_changes_from_a_feature_branch` | 2026-08-24 | `main` では判定しない（fast-forward マージ後は出自が git 上に残らない） |
| 項目 C | feature ブランチによる担当範囲外の変更 | `test_dogfooding_fixes.py::test_feature_branch_scope_still_blocks_other_features` | 2026-08-24 | — |
| 項目 D | 凍結後の contract.yaml の変更 | `test_dogfooding_fixes.py::test_contract_freeze_still_blocks_edit_after_approval` | 2026-08-24 | — |
| 項目 E | 要件の現在版を参照していない APPROVED な設計 | `test_ci_items.py::test_item_e_rejects_an_approved_design_pinned_to_an_old_requirements_version` | 2026-08-24 | — |
| 項目 F | コミット間の不正な state 遷移 | `test_ci_items.py::test_item_f_rejects_a_multi_step_jump_between_commits` | 2026-08-24 | 新規追加ファイルは旧状態が無いため判定不能（意図的） |
| 項目 G | 古い PROGRESS.md / STATE.machine.yaml | `test_ci_items.py::test_item_g_rejects_a_stale_dashboard` / `test_ci_items.py::test_item_g_does_not_leave_the_worktree_dirty` | 2026-08-24 | feature ブランチでは構造的に満たせないためスキップする（`test_dogfooding_fixes.py::test_progress_freshness_is_skipped_on_feature_branch`） |
| 項目 I | 受領書を欠く／検証後に実装が変わった TESTED・INTEGRATED | `test_ci_items.py::test_item_i_rejects_tested_without_a_receipt` / `test_ci_items.py::test_item_i_rejects_an_implementation_changed_after_verification` | 2026-08-24 | — |
| 項目 J | `interfaces[]` の両端の JSON Schema 不整合 | `test_interface_check.py::test_unknown_producer_feature` / `test_interface_check.py::test_unknown_output_name` | 2026-08-24 | `$ref` は解決しない（6節。だからインライン展開を規定している） |
| 項目 K | MUST 要件の取りこぼし・存在しない FR ID の参照 | `test_traceability.py::test_uncovered_must_requirement_is_detected` | 2026-08-24 | — |
| 項目 L | コンテキスト予算の超過 | `test_context_budget.py::test_oversized_conventions_is_detected` / `test_context_budget.py::test_oversized_agent_is_detected` / `test_context_budget.py::test_session_total_is_detected` | 2026-08-24 | — |
| 項目 M | CONVENTIONS.md と agent/skill プロンプトの二重管理 | `test_context_budget.py::test_near_verbatim_copy_into_an_agent_is_detected` / `test_context_budget.py::test_duplication_in_a_skill_is_detected_too` | 2026-08-24 | 言い換えを伴う重複は検出しない（閾値を上げると正当な具体化まで落ちるため。意図的） |
| 項目 N | `interfaces[]` のエッジが結合テストに対応づけられていないこと | `test_check_integration_traceability.py::test_partial_coverage_still_reports_gaps` | 2026-08-24 | — |
| 項目 O | CONVENTIONS.md への節の新設 | `test_conventions_frozen.py::test_new_section_is_rejected` | 2026-08-24 | 節の削除・既存節の変更は凍結の対象外（意図的） |
| 項目 P | この表に書かれた実証テストが実在しないこと | `test_claims.py::test_unknown_test_name_is_rejected` / `test_claims.py::test_missing_evidence_without_a_reason_is_rejected` | 2026-08-24 | この表に**行を足し忘れた**規則は検出できない（規則の追加は人間の判断） |

## 強制レイヤ自体の健全性

| 規則 | 何をブロックすると主張するか | 実証テスト | 最終実証日 | 未実証の残余 |
|---|---|---|---|---|
| fail-closed | ガード本体で想定外の例外が起きたとき、通過ではなく拒否になること | `test_healthcheck.py::test_unexpected_exception_denies_instead_of_passing` / `test_healthcheck.py::test_the_guard_still_passes_normally_when_nothing_is_wrong` | 2026-08-24 | `python3` 自体が存在しない場合は Hook が起動できないため、ハーネスからは何もできない（SessionStart の自己診断と PROGRESS.md 表示で**可視化**するのが対策） |
| 自己診断 | 強制レイヤが壊れている状態を検出して報告すること | `test_healthcheck.py::test_broken_hook_import_is_reported` / `test_healthcheck.py::test_missing_hook_registration_is_reported` / `test_healthcheck.py::test_progress_line_reports_the_problem_when_broken` | 2026-08-24 | 検出できても Claude Code 側の Hook 実行を止める手段は無い（報告と可視化まで） |
