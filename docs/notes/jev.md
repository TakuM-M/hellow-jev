# Jev

- 利用形態: API（ローカル実行は不可）
- 実装: `src/hellow_jev/classifiers/jev.py`（本体は Laya と共通の `systemone.py`）
- 設定: `configs/jev.toml` / 環境変数 `JEV_API_KEY`, `JEV_API_BASE_URL`

## 概要

- TypeSafe AI のクローズドな商用 API（重みは非公開。OSS なのは互換実装の Laya など）
- 判定専用の「System One model」。テキストを生成せず、型付きの質問に選択肢 / スコア / Yes-No 確率を返す
- モデル ID: `jev-1.13.0`（実 API で確認）。`jev-latest` の指定例もある
- 公式ドキュメント（https://docs.typesafe.ai/api ）は egress 制限で未読。仕様は Laya の互換実装と実レスポンスで確認

## API 仕様

`POST https://api.typesafe.ai/v1/systemone`、`Authorization: Bearer <API_KEY>`。プロンプトを渡す `/chat/completions` 形式ではない。

```json
{
  "model": "jev-1.13.0",
  "state": { "log": "<テキスト>" },
  "questions": {
    "label": {
      "type": "choice",
      "instructions": "Classify this e-commerce system log line into exactly one of the following categories.",
      "criteria": { "payment": "Payment, billing, or card authorization failures and anomalies", "auth": "Login, session, or token issues", "normal": "…" }
    }
  }
}
```

```json
{
  "model": "jev-1.13.0",
  "answers": { "label": { "type": "choice", "choice": "auth",
    "confidence": 0.91, "probabilities": { "auth": 0.93, "…": "…" } } },
  "usage": { "input_tokens": "…", "output_tokens": 66 }
}
```

- 質問タイプ: `choice`（多クラス）/ `score`（順序尺度）/ `noul`（Yes/No 確率）
- 質問 ID（`label`）は任意の名前。`state` は文字列でも JSON オブジェクトでもよい
- 本リポジトリは `choice` 1 問で分類し、`answers.label.choice` をラベル、`usage` をコストに使う。ラベル外は構造上出ない
- `state` の形はタスクの `state_format` で切り替える（`object` = `{"log": ...}`、`string` = テキストそのまま）。どちらも実 API で動作確認済み
- jevbench は OpenRouter の Decisions API（`POST https://openrouter.ai/api/alpha/decisions`、model `typesafe/jev-1.13`）経由で、`state` は文字列

## 料金

- input $0.042 / 1M tokens、output は無課金（2026-09-28 確認。`configs/jev.toml` の `[pricing]`）

## 実測（TypeSafe 直）

- `X-Inference-Time-Ms` ヘッダは返らない → レイテンシはネットワーク込みの往復時間のみ
- p50: log_classification ≈ 162 ms / p95 ≈ 186 ms、jevbench 165〜175 ms
- keep-alive が効く（warmup 後の新規接続 0）
- usage（log_classification）: input ≈ 476 tok/件、output は入力によらず 66 tok で一定
- `confidence` は最大の probability と一致しないことがある（例: 0.91 / 0.93）。定義は未確認
- 精度は `docs/notes/dataset.md`

## 二次情報（要検証）

| 項目 | 値 | 出典 |
| --- | --- | --- |
| レイテンシ p50 | 約 236–276 ms（ネットワーク込み） | Laya BENCHMARKS.md |
| 精度 | AG News 0.910 / Banking77 0.870 / typed-decisions 0.727 | 比較ブログ記事 |
| 中国語の業務判定 64 件 | 64/64 | Laya `research/benchmarks/feishu_zh` |
| ECE | 0.144〜0.246 | 同上 |


## 参考

- https://docs.typesafe.ai/api
- https://github.com/NandhaKishorM/laya （`laya/serve.py`, `research/benchmarks/feishu_zh/`）
- https://huggingface.co/blog/sora-2/jev-vs-laya-hosted-api-or-open-weights-2026-guide
