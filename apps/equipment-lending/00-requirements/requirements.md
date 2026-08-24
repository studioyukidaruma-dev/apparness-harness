# 要件定義: 備品貸出管理

> このファイルは人間向けです。機械向けの構造化データは `requirements.machine.yaml` を参照してください。
> 内容はこの2ファイルで常に一致させてください（`requirements-analyst` subagent が両方同時に更新します）。

- app_id: `equipment-lending`
- version: 1
- status: DRAFT

## 概要 (Summary)

{{SUMMARY}}

## 目的 (Goals)

- (箇条書きで記載)

## やらないこと (Non-Goals)

- (箇条書きで記載。スコープ外を明示することで後の議論を減らす)

## 想定ユーザー (Target Users)

- (箇条書きで記載)

## 機能要件 (Functional Requirements)

要件ごとに、受け入れ基準まで**この文書にも**書きます（`requirements.machine.yaml` の
`acceptance_criteria` と一字一句同じ文にしてください。契約の `coverage[]` はこの原文を
そのまま引用してテストと対応づけ、機械検証されます）。

### FR-1: (タイトル)

- 優先度: MUST
- 説明: (何ができるようになるか。実装方法ではなく、外から見た振る舞いで書く)
- 受け入れ基準:
  - (この条件を満たせば「できた」と言える、と検証可能な形で書く)

## 非機能要件 (Non-Functional Requirements)

- (性能・セキュリティ・可用性など)

## 制約 (Constraints)

- (技術的・組織的な制約)

## 未解決事項 (Open Questions)

- (承認前に解消すべき疑問点)

承認時点で未解決事項が無ければ、この節は箇条書きを消して「なし」の 1 行だけにしてください
（`requirements.machine.yaml` の `open_questions: []` と対応します）。
