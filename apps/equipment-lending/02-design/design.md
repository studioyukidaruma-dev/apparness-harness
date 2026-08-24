# 設計書: 備品貸出管理

> このファイルは人間向けです。機械向けの構造化データは `architecture.machine.yaml` と
> `features/<feature-id>.contract.yaml` を参照してください。

- app_id: `equipment-lending`
- design_version: 1
- based_on_requirements_version: 1
- status: DRAFT（`AUTONOMY.yaml` は `SUPERVISED`。技術スタックの承認後に親セッションが APPROVED を書く）

## 全体アーキテクチャ概要

社内サーバで Node.js のプロセスを 1 つ動かし、同じ SQLite ファイルを 3 つのサーバ側機能が
読み書きします。作業員はスマホのブラウザから静的な画面（`web-ui`）を開き、2 つの API を叩きます。

```
        [スマホのブラウザ]
              │  (fetch)
   ┌──────────┴──────────┐
   │       web-ui        │  区画タイル・検索・貸出フォーム・貸出中一覧（描画は純関数）
   └──┬───────────────┬──┘
      │ inventory_query│ lending_registration_request / return_registration_request
      ▼                ▼
 ┌───────────────┐   ┌────────────────────┐
 │ inventory-view│◀──│  lending-registry  │   active_lending_counts（備品ごとの貸出中数量）
 │  GET /api/    │   │  POST /api/lendings│
 │  inventory    │   │  GET  /api/lendings│
 └───────▲───────┘   └─────────▲──────────┘
         │ equipment_master_records │
         └────────┬─────────────────┘
                  │
          ┌───────────────┐
          │equipment-master│ スキーマ作成＋シード JSON 取り込み（CREATE を許された唯一の機能）
          └───────────────┘
                  │
            SQLite（equipment / lending / schema_version）
```

- 在庫の残数は保存しません。`available_quantity = equipment.total_quantity −（返却されていない貸出の数量合計）`
  として毎回計算します。これにより「返却したら在庫が戻る」（FR-3）が、更新漏れの起きない形で成立します。
- 機能どうしはコードを共有しません。共有するのは `shared-kernel.yaml` に書いたテーブル定義と
  JSON の語彙だけで、各機能は自分の SQL・自分の検証を持ちます（`depends_on` は作らない。CONVENTIONS 6節）。

## 共有基盤 (Shared Kernel)

全機能が依存してよい最小限の共有契約。詳細は `../01-foundation/shared-kernel.yaml`。

| 置いたもの | なぜ全機能共通なのか |
|---|---|
| `common_types`（EquipmentId / LocationCode / LendingId / BorrowerName / Quantity / IsoTimestamp / ErrorResponse） | 4 機能が同じ JSON をやり取りするため、ID の形・時刻の形・エラーの形が一致していないと統合時に噛み合わない |
| `data_store`（SQLite のテーブル定義・不変条件・接続方針） | 3 つのサーバ側機能が同じファイルを読み書きするため、テーブル定義は 1 か所にしか置けない |
| `auth`（認証なし・ネットワーク境界・個人情報の扱い） | アプリ全体で 1 つしかない方針。要件の非機能要件そのもの |
| `http_api`（`/api` 配下・エラー本体・ハンドラの形） | 統合時に 1 つの HTTP サーバへ束ねるため、束ね方を先に決めておく必要がある |
| `ui_conventions`（コントラスト・タップ領域・文字サイズ・テーマ） | 要件の非機能要件の数値。今は `web-ui` だけが使うが、画面が増えても揺らしてはいけない値 |
| `verification`（テストコマンド） | 全機能が同じ Node 標準ランナーで検証する |

**あえて置かなかったもの**: 在庫の算出式の実装、区画タイルの見せ方、貸出の検証規則、
共通ユーティリティのコード。これらは特定機能の関心事なので、各 `contract.yaml` の側に置きました。

## 機能一覧 (Features)

| ID | 名前 | 概要 | 覆う要件 | 技術スタック | 契約ファイル |
|---|---|---|---|---|---|
| `equipment-master` | 備品マスタ管理 | SQLite のスキーマ作成と、シード JSON からの備品マスタ取り込み・更新・読み出し。CLI とモジュールのみ（画面・HTTP なし） | FR-1 | Node.js 24 / node:sqlite / node:fs | `features/equipment-master.contract.yaml` |
| `inventory-view` | 区画別在庫照会 | 区画ごとの備品名・総数・貸出中数・残数を組み立てて返す読み取り専用 API。備品名の部分一致検索も担う | FR-1, FR-3, FR-4 | Node.js 24 / node:http / node:sqlite | `features/inventory-view.contract.yaml` |
| `lending-registry` | 貸出・返却登録 | 貸出登録・返却登録・貸出中一覧の API。在庫超過と二重返却を拒否し、備品ごとの貸出中数量を提供する | FR-2, FR-3, FR-5 | Node.js 24 / node:http / node:sqlite / node:crypto | `features/lending-registry.contract.yaml` |
| `web-ui` | スマホ向け画面 | 区画タイル・検索・貸出フォーム・貸出中一覧。描画は「JSON → HTML 文字列」の純関数に閉じる | FR-1〜FR-5 | ブラウザ ES Modules / HTML / CSS（ビルド工程なし） | `features/web-ui.contract.yaml` |

分割の意図: 「**書く人**（equipment-master・lending-registry）」と「**読む人**（inventory-view）」と
「**見せる人**（web-ui）」を分けました。書き込みを 2 つに割ったのは、更新頻度も権限の重みも
まったく違うためです（マスタは管理者が月に数回、貸出は作業員が毎日）。
どの機能も、他機能の内部を知らずに入出力だけで実装できます。

SHOULD の FR-4（検索）と FR-5（貸出中一覧）はどちらも落としていません。FR-4 は `inventory-view` に、
FR-5 は `lending-registry` に、それぞれ MUST の機能と同じ責務の中で収まる小さな追加として含めました。

## 機能間のつながり (Interfaces)

| 出力元機能 | 出力 | 入力先機能 | 入力 | 何が流れるか |
|---|---|---|---|---|
| `equipment-master` | `equipment_master_records` | `inventory-view` | `equipment_master_records` | 区画・備品名・総数（タイルの中身） |
| `equipment-master` | `equipment_master_records` | `lending-registry` | `equipment_master_records` | 備品の実在確認・在庫上限・一覧に出す備品名 |
| `lending-registry` | `active_lending_counts` | `inventory-view` | `active_lending_counts` | 備品ごとの貸出中数量（残数の減算項） |
| `inventory-view` | `location_inventory_view` | `web-ui` | `location_inventory_view` | 区画タイルの表示データ |
| `lending-registry` | `active_lending_list` | `web-ui` | `active_lending_list` | 貸出中一覧の表示データ |
| `web-ui` | `inventory_query` | `inventory-view` | `inventory_query` | 検索キーワード |
| `web-ui` | `lending_registration_request` | `lending-registry` | `lending_registration_request` | 貸出フォームの送信内容 |
| `web-ui` | `return_registration_request` | `lending-registry` | `return_registration_request` | 返却ボタンの送信内容 |

機能同士は上表の入出力接続でのみ結合します。`depends_on` のような直接依存は持たせません
（`harness/CONVENTIONS.md` 6節）。両端の JSON Schema は
`python3 harness/scripts/check_interfaces.py --app equipment-lending` で機械検証済みです。

## 技術スタック選定の根拠

### 前提として置いた制約

1. 有償ライセンスのライブラリは使用不可（要件の制約）。
2. 実行環境で確実に動くのは `node v24.15.0` / `npm 11.12.1` / `python3 3.12.3` / `docker` のみ。
   `pip3`・`sqlite3` コマンド・pnpm・deno・bun は無い。
3. ネットワークからのパッケージ取得の可否が未確認。**依存を増やすほど詰まる**。
4. 利用規模は同時数名・備品は数百件規模。性能要件は緩い。

この 4 つを同時に満たす答えは「**サードパーティ依存ゼロ・Node.js 標準ライブラリだけで作る**」でした。
以下、採用した「ライブラリ」はすべて Node.js 本体に同梱されているものです（追加取得が一切発生しません）。

| 採用 | 用途 | ライセンス | 保守状況 | 既知の脆弱性・注意点 |
|---|---|---|---|---|
| Node.js 24 (`v24.15.0`) | 実行環境全体 | MIT | Active LTS。サポート期限 2028-04-30 | 本体のセキュリティ更新は Node 側で継続提供される。運用時は LTS の更新を当てる |
| `node:sqlite`（`DatabaseSync`） | データ保存 | Node.js 本体（MIT）。同梱される SQLite は Public Domain | Node 22.5 で導入、24 以降は Stability 1.2（Release Candidate）。フラグ不要で利用可 | まだ RC のため、将来のメジャー更新で API が変わりうる。**利用箇所を 1 ファイル（DB アダプタ）に閉じる**ことで影響範囲を限定する方針を各契約に書いた |
| `node:http` | HTTP サーバ | MIT | 安定 API | 追加のルータを使わないため、パス解決とボディ長制限（64KB）を自前で明示的に書く |
| `node:crypto`（`randomUUID`） | 貸出 ID の採番 | MIT | 安定 API | 連番を避けることで、ID の推測による他人の貸出の操作を防ぐ |
| `node:test` + `--test-reporter=junit` | 単体テストと JUnit XML 出力 | MIT | Node 20 以降で安定。24 に標準搭載 | 追加のテストランナー（jest/vitest）は npm 取得が必要なため採用しない |

不採用にしたものと理由:

- **better-sqlite3 / sqlite3（npm）**: 高品質だがネイティブビルドが必要で、パッケージ取得が
  できない環境では詰む。`node:sqlite` で要求を満たせるため不採用。
- **Express / Fastify**: 依存ツリーが増える。今回のエンドポイントは 4 本しかなく、`node:http` で足りる。
- **React / Vue + バンドラ**: 画面は 1 枚で、状態はサーバにしかありません。ビルド工程を足すと
  「取得できないかもしれない依存」が増えるだけです。素の ES Modules で要件を満たせます。
- **JSON ファイルへの保存**: 追加依存ゼロという点では同じですが、同時に数名が書き込むため、
  ファイルの読み書き競合を自前で正しく扱う必要が出ます。SQLite のトランザクションに任せるほうが安全です。
- **TypeScript / ESLint**: どちらも npm からの取得が前提になり、取れなかった場合に
  「宣言したのに実行できない検証コマンド」が残ります（それは Rule 10 により全機能を TESTED に
  できない状態を意味します）。今回は宣言しません（下記）。

### セキュリティ・ベースラインとの対応（`harness/quality/security-baseline.md`）

- **入力の不信**: 各契約の `inputs[].json_schema` を実装の入口で検証し、外れたら `error_cases[]` の
  コードで拒否する、と全契約に明記しました。
- **インジェクション**: `data_store.policy` で「SQL はプリペアドステートメントのみ・文字列連結禁止」を
  全機能共通の方針として固定しました。検索キーワードも同様です。OS コマンドは実行しません。
- **秘密情報**: 認証が無いためトークン・鍵をそもそも持ちません。DB のパスだけを環境変数で受けます。
- **権限チェックはサーバ側**: 在庫超過・二重返却の判定を `lending-registry` の登録処理の入口で行うと
  契約に書き、画面側の disabled は補助でしかないと明記しました。
- **エラーで内部情報を漏らさない**: `http_api.error_message_policy` で、スタックトレース・SQL・
  ファイルパス・借用者名を message に含めないことを共通ルールにしました。
- **個人情報**: 借用者名はログにもエラーにも出さない、を `auth.pii_handling` に置きました。
  ネットワーク境界（待受は既定 127.0.0.1、社内 LAN のみ）で社外からの到達を断ちます。
- **依存の脆弱性**: サードパーティ依存が 0 件のため lockfile が生成されません。CI の `vuln-scan` が
  走っても対象がない状態になります。**実装中に npm パッケージを足したくなったら設計に戻ること**
  （`diff-design`）を申し送りとします。

### デザインの方針（`harness/quality/design-baseline.md` の上積み）

- テーマは「屋外の現場で、手袋のまま、明るい日差しの下で使う」。基調色は現場の標識に通じる
  濃紺 `#0B3D6B`、状態色は在庫あり `#15803D`／貸出中 `#B45309`／エラー `#B91C1C`。
  ベースラインが名指しで避けるよう求めている「クリーム背景＋テラコッタ」は使いません。
- 数値（コントラスト 4.5:1 以上・タップ領域 44px 以上・間隔 8px 以上・本文 16px 以上・
  ボタン 18px 以上）は要件の非機能要件そのままで、`shared-kernel.yaml` の `ui_conventions` に固定しました。
- 区画は「タイル」として並べ、1 タイル＝1 区画・タイル内に備品名と残数を出します（FR-1 の受入基準）。
- loading / empty / error の 3 状態を必ず持たせることを `web-ui` の契約に書きました。
- 追加インストールが必要なデザイン系 Skill（`frontend-design`）は**必須依存として登録しません**
  （要件の制約に基づく合意）。この環境では `enabledPlugins` が空のため、登録すると Rule 5 が
  `src/**` への書き込みを全面的に止めてしまいます。UI 品質は Layer 1 の `design-baseline.md` と
  上記の数値で担保します。

## 検証コマンドの宣言（`shared-kernel.yaml` の `verification:`）

```
working_dir:    "."
test_command:   mkdir -p .verify && node --test --test-reporter=junit --test-reporter-destination=.verify/junit.xml 'tests/**/*.test.js'
junit_xml:      ".verify/junit.xml"
max_skip_ratio: 0.2
```

- 実際にこの環境（`node v24.15.0`）で実行し、終了コード 0 と JUnit XML の生成、
  および契約に書いた `test_ids`（`tests/<file>.test.js::<テスト名>` 形式）が
  `harness/scripts/junit_utils.py` の照合に掛かることを確認済みです。
- `.verify/` は生成物なので `apps/equipment-lending/.gitignore` に追加しました
  （コミットすると受領書より後の変更と見なされ CI 項目 I が落ちるため）。
- `mkdir -p` を前置しているのは、`--test-reporter-destination` の出力先ディレクトリを
  Node が自動作成せず ENOENT で落ちるためです（実測）。
- glob をシングルクォートで囲むのは、シェルではなく Node 自身に `**` を展開させるためです。
- `lint_command` / `typecheck_command` / `build_command` は**宣言しません**。理由は
  (a) ESLint・TypeScript は npm 取得が前提で、取得できない環境では検証ゲート全体が止まる、
  (b) ビルド工程を持たない構成なので build は無い、の 2 点です。宣言しなかったキーは
  検証対象になりません（終了コードによるテストのゲートはそのまま効きます）。
- `max_skip_ratio` は既定の 0.2 のままにしました（0.0 にすると環境依存の skip を 1 件書いた
  時点で TESTED にできなくなるため）。

## 実装フェーズへの申し送り

1. 各機能ディレクトリ直下に `package.json`（`{"name": "<feature-id>", "private": true, "type": "module"}`、
   `dependencies` は空）を置いてください。ESM で `import` を書くために必要です。npm install は不要です。
2. `node:sqlite` を触るのは各機能 1 ファイル（DB アダプタ）に閉じ、ドメインロジックは
   純関数として書いてください。テストは `:memory:` の DB と純関数で完結します。
3. テストのファイル名は `tests/<name>.test.js`、テスト名は契約の `test_ids` の `::` 以降と
   完全に一致させてください（JUnit XML と機械照合されます）。
4. サーバ由来の文字列を `innerHTML` に直接入れないでください（借用者名は自由入力です）。
5. npm パッケージを足したくなったら、実装を止めて `diff-design` で設計に戻ってください
   （`shared-kernel.yaml` は `feature-builder` からは変更できません）。

## 未決事項（親セッション経由でユーザーに確認したいこと）

1. 技術スタック（Node.js 24 標準ライブラリのみ・SQLite・素の ES Modules）の採否。
2. 備品マスタの初期登録を「サーバ上の JSON ファイルを管理者が編集し、CLI で取り込む」方式とした点。
   画面から備品を追加・編集したい場合は要件（FR）の追加になります。
3. 貸出は「1 件の貸出をまとめて返す」方式（部分返却なし）とした点。
4. 貸出時の数量指定を可能にした点（省略時 1）。

## 進捗

進捗そのものはここに手書きしない。`apps/equipment-lending/PROGRESS.md`（自動生成）を参照。
