# OpenAI Decisions API

- 利用形態: API（public beta）
- 実装: 未実装（形式が違うので新しい分類器が要る）
- 環境変数: `OPENAI_API_KEY`

## 概要

- OpenAI、2026-10-06 公開。テキスト・画像入力
- モデルは `gpt-6-luna` のみ

## API 仕様

`POST https://api.openai.com/v1/decisions`

```json
{
  "model": "gpt-6-luna",
  "input": "<テキスト>",
  "questions": [{
    "type": "choice",
    "name": "label",
    "instructions": "...",
    "choices": [{"value": "auth", "description": "Login, session, or token issues"}]
  }]
}
```

- Jev との差: `state` でなく `input`、`questions` と `answers` が配列（`name` で引く）、選択肢が `criteria` でなく `choices` 配列
- 質問タイプ: `predicate`（= Jev の `noul`）/ `choice` / `score`

## 料金

- GPT-6 Luna の input 単価のみ。output は無課金

公式ページは egress 制限で未読。上記は検索結果の抜粋と LiteLLM の実装 PR によるもので、実装前に実 API で確認する（2026-10-07）。
