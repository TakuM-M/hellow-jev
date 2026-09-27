# Jev 調査メモ

- 利用形態: API
- 実装: `src/hellow_jev/classifiers/jev.py`（本体は Laya と共通の `classifiers/systemone.py`）
- 設定: `configs/jev.toml` / 環境変数 `JEV_API_KEY`, `JEV_API_BASE_URL`

## 概要（2026-09-27 調査）

- 提供元: **TypeSafe AI**。**クローズドな商用 API**（重みは非公開）
  - ⚠️ Jev 自体は OSS ではない。OSS なのは互換実装の Laya などの周辺プロジェクト
- 「System One model」と称する **判定専用モデル**。テキストは生成せず、
  型付きの質問に対して **選択肢 / スコア / Yes-No 確率** を返す
- 観測されたモデル ID: `jev-1.13.0`（2026-09-21 時点の実 API レスポンス）。`jev-latest` を指定する例もある
- ドキュメント: https://docs.typesafe.ai/api （本環境からは egress 制限で未読。以下は二次情報と実レスポンスから確認）

## API 仕様

- `POST https://api.typesafe.ai/v1/systemone`
- `Authorization: Bearer <API_KEY>`、`Content-Type: application/json`
- `/chat/completions` 形式ではない（プロンプト文字列を渡す API ではない）

リクエスト例（Laya の互換サーバ実装と、Jev を実際に呼んでいるコードで確認した形）:

```json
{
  "model": "jev-1.13.0",
  "state": { "body": "<ログ本文>" },
  "questions": {
    "label": {
      "type": "choice",
      "instructions": "Classify this e-commerce system log line into exactly one of the following categories.",
      "criteria": { "payment": "Payment, billing, or card authorization failures and anomalies", "auth": "Login, session, or token issues", "normal": "…" }
    }
  }
}
```

- 質問タイプは 3 つ: `choice`（多クラス）/ `score`（順序尺度）/ `noul`（Yes/No 確率）
- `state` は文字列でも JSON オブジェクトでもよい
- `questions` のキー（上の例では `label`）は質問 ID で、任意の名前を付けられる

レスポンス（実例。質問 ID が `category` の呼び出し）:

```json
{
  "model": "jev-1.13.0",
  "answers": { "category": { "type": "choice", "choice": "valuable",
    "confidence": 1.0, "probabilities": { "noise": 0.0, "valuable": 1.0 } } },
  "usage": { "input_tokens": 786, "output_tokens": 47 }
}
```

→ 本リポジトリでは `state = {"log": <ログ>}`、質問 ID `label` の `choice` 1 問で分類し、
`answers.label.choice` をラベル、`usage` をコスト計算に使う。
選択肢から選ぶ方式なので、ラベル外の出力は構造上起きない（念のためクライアントでも検証する）。
⚠️ 実例の state キーは `body`。`log` キーでの実 API 呼び出しはまだ試していない。

## 性能・コスト（二次情報。要検証）

| 項目 | 値 | 出典 |
| --- | --- | --- |
| レイテンシ p50 | 約 236–276 ms（ネットワーク込み） | Laya BENCHMARKS.md（第三者計測） |
| レイテンシ 実測 | p50 ≈ 251 ms / p95 ≈ 317 ms（384 req, 直列） | Laya repo `research/benchmarks/feishu_zh` のアーカイブ |
| 料金 | $0.042 / 1M input tokens、output は無課金 | 比較ブログ記事（公式未確認） |
| 精度例 | AG News 0.910 / Banking77（77 クラス）0.870 / typed-decisions 0.727 | 同上（公表値） |
| 中国語の業務判定 64 件 | 64/64 正解 | feishu_zh アーカイブ |

- 多クラス（77 ラベル）でも精度が落ちにくい点が Laya との大きな差
- 較正誤差（ECE）は 0.144〜0.246 と報告されている

## 調べること

- [x] リポジトリ / ドキュメントの URL
- [x] 認証方式・エンドポイント・リクエスト/レスポンス形式
- [x] 分類タスクに向いた使い方 → `choice` 質問を使う
- [ ] レート制限・料金（公式ドキュメントで確認）
- [ ] 入力トークン数・選択肢数の上限
- [x] ローカル実行の可否 → 不可（API のみ）。ローカルで動く互換実装として Laya がある

## 実装方針メモ

- 標準ライブラリだけで実装（HTTP は `classifiers/_http.py` の共通クライアント）
- **Laya の `laya-serve` と同じワイヤプロトコル** なので、
  接続先を差し替えるだけで Jev / Laya を同じクライアントで呼べる
- レイテンシはクライアント側の往復時間で計測する（ネットワーク込み）

## 参考

- https://docs.typesafe.ai/api
- https://github.com/NandhaKishorM/laya （`laya/serve.py`, `research/benchmarks/feishu_zh/`）
- https://huggingface.co/blog/sora-2/jev-vs-laya-hosted-api-or-open-weights-2026-guide

## ログ

- 2026-09-27: 初回調査。API 形式を互換実装と実レスポンスから確認。公式 docs は未読（egress 制限）
- 2026-09-27: `classifiers/systemone.py` の共通クライアントで実装。state は `{"log": ...}`、質問 ID は `label`。ダミーサーバでのみテスト済み
- 2026-09-27: jevbench（`tasks/JEVBENCH.md`）は Jev を OpenRouter の Decisions API（`POST https://openrouter.ai/api/alpha/decisions`、model `typesafe/jev-1.13`）経由で呼んでいる。`state` は文字列のまま、質問 ID は `label` で、公表値が出ているので文字列の state でも動く。本リポジトリはタスクの `state_format` で `{"log": ...}` と文字列を切り替えられるようにした
