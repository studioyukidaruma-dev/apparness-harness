# 進捗ダッシュボード: equipment-lending

> **このファイルは自動生成です。手書きで編集しないでください。**
> `harness/scripts/render_progress.py` が `03-features/*/status.yaml` から再生成します。

生成日時: 2026-09-13T08:24:12Z

- 自動化モード (autonomy_mode): **SUPERVISED**（`AUTONOMY.yaml` 参照。要件定義の承認はモードに関わらず常に人間必須）
- 要件定義 (00-requirements): **APPROVED**
- 設計 (02-design): **APPROVED**
- 強制レイヤ: **OK**（Hook 登録・import・主要関数がそろっています）
- ハーネス版: **v1.1.0**

## 機能一覧 (0/4 完了)

| feature_id | 状態 | 検証 | レビュー | 担当 | ブロッカー | 最終更新 |
|---|---|---|---|---|---|---|
| equipment-master | 実装完了 (IMPLEMENTED) | 未実行 | 未実施 | feature-builder | - | 2026-08-25T00:45:00Z |
| inventory-view | 契約承認済み (CONTRACT_APPROVED) | 未実行 | 未実施 | - | - | 2026-08-24T14:59:02Z |
| lending-registry | 契約承認済み (CONTRACT_APPROVED) | 未実行 | 未実施 | - | - | 2026-08-24T14:59:02Z |
| web-ui | 契約承認済み (CONTRACT_APPROVED) | 未実行 | 未実施 | - | - | 2026-08-24T14:59:03Z |

## 次にすべきこと

- 実装中の機能があります: inventory-view, lending-registry, web-ui。
- 統合待ちの機能があります: equipment-master。`integrator` subagent で組み上げてください。
