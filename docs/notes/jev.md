# Jev 調査メモ

- 利用形態: API
- 実装: `src/hellow_jev/classifiers/jev.py`
- 設定: `configs/jev.toml` / 環境変数 `JEV_API_KEY`, `JEV_API_BASE_URL`

## 概要（2026-09-27 調査）

- 提供元: **TypeSafe AI**。**クローズドな商用 API**（重みは非公開）
  - ⚠️ 「OSS の Jev」ではない。OSS なのは互換実装の Laya などの周辺プロジェクト
- 「System One model」と称する **判定専用モデル**。テキストを生成せず、
  typed な質問に対して **選択肢 / スコア / Yes-No 確率** を返す
- 観測されたモデル ID: `jev-1.13.0`（2026-09-21 時点の実 API レスポンス）。`jev-latest` 指定の例もあり
- ドキュメント: https://docs.typesafe.ai/api （※本環境からは egress ブロックで未読。下記は二次情報＋実レスポンスから確認）

## API 仕様

- `POST https://api.typesafe.ai/v1/systemone`
- `Authorization: Bearer <API_KEY>`、`Content-Type: application/json`
- `/chat/completions` 形式ではない（プロンプト文字列を渡す API ではない）

リクエスト（Laya の互換サーバ実装・Jev 実呼び出しコードで確認）:

```json
{
  "model": "jev-1.13.0",
  "state": { "body": "<ログ本文>" },
  "questions": {
    "label": {
      "type": "choice",
      "instructions": "Which category does this e-commerce log belong to?",
      "criteria": { "payment": "決済・課金…", "auth": "ログイン…", "normal": "…" }
    }
  }
}
```

- 質問タイプは 3 つ: `choice`（多クラス）/ `score`（順序尺度）/ `noul`（Yes/No 確率）
- `state` は文字列 or JSON オブジェクト

レスポンス（実例）:

```json
{
  "model": "jev-1.13.0",
  "answers": { "category": { "type": "choice", "choice": "valuable",
    "confidence": 1.0, "probabilities": { "noise": 0.0, "valuable": 1.0 } } },
  "usage": { "input_tokens": 786, "output_tokens": 47 }
}
```

→ 本タスクでは `choice` 1 問で分類し、`answers.label.choice` をラベル、`usage` をコストに使う。
ラベル外出力は構造上起きない（選択肢から選ぶため）。

## 性能・コスト（二次情報。要検証）

| 項目 | 値 | 出典 |
| --- | --- | --- |
| レイテンシ p50 | 約 236–276 ms（ネットワーク込み） | Laya BENCHMARKS.md（第三者計測） |
| レイテンシ 実測 | p50 ≈ 251 ms / p95 ≈ 317 ms（384 req, 直列） | Laya repo `research/benchmarks/feishu_zh` のアーカイブ |
| 料金 | $0.042 / 1M input tokens、output 無課金 | 比較ブログ記事（公式未確認） |
| 精度例 | AG News 0.910 / Banking77（77 クラス）0.870 / typed-decisions 0.727 | 同上（公表値） |
| 中国語業務判定 64 件 | 64/64 正解 | feishu_zh アーカイブ |

- 多クラス（77 ラベル）でも精度が落ちにくいのが Laya との差
- 較正（ECE）は 0.144〜0.246 と報告

## 調べること

- [x] リポジトリ / ドキュメントの URL
- [x] 認証方式・エンドポイント・リクエスト/レスポンス形式
- [x] 分類タスクに向いた使い方 → `choice` 質問を使う
- [ ] レート制限・料金（公式ドキュメントで確認）
- [ ] 入力トークン上限・選択肢数上限
- [x] ローカル実行の可否 → 不可（API のみ）。互換ローカル実装として Laya がある

## 実装方針メモ

- 標準ライブラリ（`urllib.request`）で実装可能
- **Laya の `laya-serve` と同じワイヤプロトコル** なので、
  `base_url` を差し替えるだけで Jev / Laya を同一クライアントで叩ける
- レイテンシはクライアント側の往復時間で計測（ネットワーク込み）

## 参考

- https://docs.typesafe.ai/api
- https://github.com/NandhaKishorM/laya （`laya/serve.py`, `research/benchmarks/feishu_zh/`）
- https://huggingface.co/blog/sora-2/jev-vs-laya-hosted-api-or-open-weights-2026-guide

## ログ

- 2026-09-27: 初回調査。API 形式を互換実装・実レスポンスから確認。公式 docs は未読（egress 制限）
- 2026-09-27: `classifiers/systemone.py` の共通クライアントで実装。state は `{"log": ...}`、質問 ID は `label`。ダミーサーバでのみテスト済み
