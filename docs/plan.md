# 調査計画

## 目的

TypeSafe AI の判定特化 API **Jev** を手元から呼び出し、EC などのログ分類タスクで
**Laya（open weight）** や **汎用 LLM** と比べて、精度・速度・コスト・運用性を評価する。

## 比較対象

| 対象 | 利用形態 | ステータス |
| --- | --- | --- |
| Jev | API（TypeSafe AI・クローズド） | 実装済み（API 形式は `POST /v1/systemone` と判明。ダミーサーバでのみテスト） |
| Laya | open weight（`laya-serve` で Jev 互換 HTTP） | 実装済み（`laya-serve` 経由。実サーバは未実行） |
| LLM | API（Claude Haiku 4.5）/ ローカル（Qwen3 を OpenAI 互換 API で） | 実装済み（ダミーサーバでのみテスト。実 API は未実行） |

## 比較対象の選定基準

問い: **「EC ログ分類で Jev を選ぶ価値はあるか」**。比較対象は Jev の代わりに実際に採用されうる選択肢から選ぶ。

### 軸: 2×2 を 1 つずつ埋める

| | API | ローカル |
| --- | --- | --- |
| 判定専用 | Jev | Laya |
| 汎用 LLM | Claude Haiku 4.5 | Qwen3 4B |

- 「判定専用 vs 汎用 LLM」と「API vs ローカル」のどちらが効いているかを切り分けられるようにする
- 1 マスに 1 モデルを基本にする（増やすのは下の「任意」の場合だけ）

### 必須条件

1. **同じ価格帯・速度帯**: Jev は安くて速いのが売りなので、比べる相手は各系統の軽量モデルにする（大型モデルと比べて精度で負けても結論にならない）
2. **現実に採用できる**: 一般に利用でき、保守されていて、商用利用できるライセンスであること
3. **バージョンを固定できる**: 日付付き ID、固定バージョン、重みの固定（ローカルはタグが差し替わることがあるので digest も記録する）
4. **同じ入力で動く**: 英語の指示文 + 7 ラベルの説明 + ログ 1 行が入力上限に収まること（Laya english は 512 tok）
5. **手元で回せる**: ローカルは用意できるハードウェア（CPU / 単体 GPU）で動き、API はデータセット 1 周分の料金が予算内に収まること

### 除外・注意の基準

- 思考モードが既定で有効なモデルは、切れることを確認してから使う（切れないとレイテンシが膨らみ、ラベル外出力も増える）
- ファインチューニングはしない。まずは全モデル zero-shot で揃える

### 任意（結果を解釈するための基準点）

- **上限の参考**: 上位の LLM を 1 つ（例: 同じ系列の上位モデル）。「軽量モデルでどれだけ精度を失うか」が分かる
- **下限の参考**: 多数派クラスのみ / キーワードのルール（標準ライブラリで実装できる）。「そもそもモデルが要るか」が分かる
- **Jev の直接の代替**: Kev-9B・mini-jev など（`docs/notes/llm.md`）。判定専用×ローカルの 2 つ目の候補（未調査）

### 現在の選定の評価

- 2×2 はすべて埋まっていて、必須条件 1〜4 は満たしている
- 未確認: Haiku 4.5 の料金（条件 5）、Qwen3 の思考モードの切り方（除外・注意の基準）
- 欠けているもの: 上限・下限の基準点（任意）

## 評価観点

1. **精度**: Accuracy / Macro-F1 / クラス別 P・R、混同行列
2. **速度**: 1 件あたりのレイテンシ、スループット
3. **コスト**: API 料金・トークン数 / ローカルなら GPU・メモリ要件
4. **運用性**: 出力の安定性（ラベル外出力率・エラー率）、再現性

## 調査で分かった前提（2026-09-27）

- Jev / Laya は **プロンプト文字列を受け取らない**。`state`（ログ）と `choice` 質問（`criteria` = ラベル定義）で判定する
- そのため「同じプロンプト」ではなく、**同じ指示文と同じラベル定義**（`tasks/log_classification/task.toml` の `instructions` / `description`）で条件を揃える
  - Jev / Laya: `instructions` = 指示文、`criteria` = `{ラベル名: description}`
  - LLM: `prompt.md` に同じ指示文と description を埋め込む
  - 差分: LLM のプロンプトには役割文（"You are a log classifier…"）と回答形式（"Answer with the label name only."）が加わる。生成モデルに出力形式を伝えるための最小限の差で、Jev / Laya にはこれに当たる入力がない
- Laya の `laya-serve` は Jev とワイヤ互換 → **同じクライアント**で接続先だけ切り替えられる
- 詳細は `docs/notes/{jev,laya,llm}.md`

## 最終出力（比較表）

`results/` の run を集計し、`docs/report.md` に表を出す（`uv run hellow-jev-report --out docs/report.md`）。
config ごとに最新の完走 run を 1 行にまとめる。

| model | n | Acc | Macro-F1 | ラベル外率 | エラー率 | p50 ms | p95 ms | 件/秒 | サーバ p50 ms | 入力tok/件 | コスト/1万件 | 実行環境 | run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| jev | | | | 0 | | | | | - | | | API | |
| laya | | | | 0 | | | | | | | - | CPU/GPU | |
| llm_api | | | | | | | | | - | | | API | |
| llm_local | | | | | | | | | - | | - | GPU | |

レイテンシ計測のルール:

- 1 件ずつ直列に投げ、最初の数件（config の `warmup`）は空打ちとして除外する。**p50 / p95 / 平均**を `metrics.json` の `latency` に出す
- クライアント側の往復時間で揃える（API はネットワーク込みと明記）
- Laya は `X-Inference-Time-Ms` ヘッダで純推論時間も併記できる（GitHub main 版のみ。詳細は `docs/notes/laya.md`）
- 実行マシン（CPU/GPU）を結果に残す（`meta.json` の `host`、config の `hardware`）

## 実験条件を揃えるルール

- 指示文・ラベル定義は `tasks/log_classification/task.toml` で一元管理し、モデル別 config には書かない
- LLM のプロンプトは `tasks/log_classification/prompt.md` を共通で使う
- 全モデルで同じデータセットを使う
- temperature などのサンプリング設定は config に明記する
- 実行結果は `results/<timestamp>_<name>/` に config / meta / metrics / predictions として保存する

## マイルストーン

- [x] ブランチ初期化・ディレクトリ構成・共通パイプライン
- [x] 各モデルの初回調査（`docs/notes/`）
- [x] Jev の API 仕様を調べて `classifiers/jev.py` を実装（ダミーサーバでのみテスト。実 API は未実行）
- [x] LLM を実装（api: Anthropic Messages API / local: OpenAI 互換。両方の config を用意）
- [x] Laya の推論方法を決めて実装（`laya-serve` 経由。実サーバは未実行）
- [x] metrics に p50/p95・ラベル外率を追加し、比較表の集計スクリプトを用意
- [ ] LLM API キーを設定して疎通確認し、料金を公式で確認
- [ ] ローカル LLM サーバを立てて疎通確認（Qwen3 の思考モードを切る方法も確認）
- [ ] Jev API キーを設定して実 API で疎通確認し、料金を `[pricing]` に記入
- [ ] laya-serve を立てて疎通確認
- [ ] 評価用データセットの用意（実ログ or 公開データ）とラベル付け
- [ ] 本評価の実行と結果のまとめ（`docs/report.md`）
