# 新しい判定モデル

OpenAI Decisions API / Liquid AI d1 / Cloudflare Clef。いずれも Jev と同じく選択肢の確率を返し、出力トークンは無課金。

公式ページは egress 制限で未読。検索結果の抜粋と GitHub の実装 PR から整理したので、数値・仕様は要検証（2026-10-07）。

| | OpenAI Decisions API | Liquid AI d1 | Cloudflare Clef / Clef-flash |
| --- | --- | --- | --- |
| 公開 | 2026-10-06（beta） | 2026-09-29 | 2026-10-01 |
| 形態 | API | API（重み非公開） | API（Workers AI）＋ open weight（Apache-2.0） |
| モデル | `gpt-6-luna` | `d1` | `clef`（27B）/ `clef-flash`（9B） |
| 形式 | 独自 | System One（Jev と同じ） | System One（URL と封筒が違う） |
| input / 1M tok | Luna の input 単価 | $0.04 | $0.24 / $0.09 |

## API

- **OpenAI**: `POST https://api.openai.com/v1/decisions`
  - `{"model", "input": <テキスト>, "questions": [{"type": "choice", "name": "label", "instructions", "choices": [{"value", "description"}]}]}`
  - 回答は `answers` 配列（`name` で引く）。質問タイプは `predicate`（= `noul`）/ `choice` / `score`
- **d1**: `POST https://api.liquid.ai/decisions/v1/systemone`。リクエスト・レスポンスとも Jev と同じ
- **Clef**: `POST https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/cloudflare/{clef,clef-flash}`
  - ボディは Jev と同じ。レスポンスは `{"result": {...}, "success": ...}` に包まれる
  - 重みは公開されているが専用の判定ヘッドが要り、vLLM 等では動かない

## 組み込み

| モデル | 作業 | 環境変数 |
| --- | --- | --- |
| d1 | `SystemOneClassifier` をそのまま使う | `LIQUID_API_KEY` |
| Clef | `SystemOneClassifier` を継承し URL と `result` の剥がしを上書き | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` |
| OpenAI | 新しい分類器（`criteria` → `choices` 配列） | `OPENAI_API_KEY` |

実装前に実 API でレスポンス（`usage` を含む）を確認する。

## 公表値の注意

- Clef の「Jev より 13 倍速い」は Jev p50 524 ms との比較。本リポジトリの Jev 実測は 162〜175 ms
