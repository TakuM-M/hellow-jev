# 新しい判定モデル（2026-09 末〜10 月）

OpenAI Decisions API / Liquid AI d1 / Cloudflare Clef の調査メモ（2026-10-07）。

- 公式ページ（developers.openai.com, docs.liquid.ai, blog.cloudflare.com, huggingface.co など）は egress 制限で未読。検索結果の抜粋と GitHub 上の実装 PR / issue で照合した。数値・仕様はすべて要検証
- どれも Jev と同じく「テキストを生成せず、型付きの質問に確率を返す」判定モデル。出力トークンは無課金

## 一覧

| | OpenAI Decisions API | Liquid AI d1 | Cloudflare Clef / Clef-flash |
| --- | --- | --- | --- |
| 公開日 | 2026-10-06（DevDay、public beta） | 2026-09-29 | 2026-10-01 |
| 利用形態 | API のみ | API のみ（重み非公開） | Workers AI の API ＋ open weight（Apache-2.0） |
| モデル | `gpt-6-luna`（唯一） | `d1`（無料枠 `d1:free`） | `@cf/cloudflare/clef`（27B）/ `@cf/cloudflare/clef-flash`（9B） |
| ベース | GPT-6 Luna（推論モデル） | 非公開 | Qwen3.8-27B / Qwen3.5-9B（凍結）＋ LoRA ＋ 判定ヘッド |
| コンテキスト | 不明 | 32K（66K とする記事もあり、食い違い） | 64K（65,535） |
| 入力 | テキスト・画像 | テキスト・画像 | テキスト・画像 |
| ワイヤ形式 | **独自**（下記） | **System One 互換**（Jev と同じ） | **System One 互換**（URL と封筒が違う） |
| 料金 input / 1M tok | Luna の標準 input 単価（$0.10 とする抜粋あり） | $0.04 | Clef $0.24 / Clef-flash $0.09 |
| 参考: Jev | | | $0.042（`configs/jev.toml`） |

## OpenAI Decisions API

`POST https://api.openai.com/v1/decisions`、`Authorization: Bearer $OPENAI_API_KEY`。

```json
{
  "model": "gpt-6-luna",
  "input": "<テキスト>",
  "questions": [{
    "type": "choice",
    "name": "label",
    "instructions": "Classify this e-commerce system log line ...",
    "choices": [
      {"value": "payment", "description": "Payment, billing, ..."},
      {"value": "auth", "description": "Login, session, or token issues"}
    ]
  }]
}
```

```json
{
  "model": "gpt-6-luna",
  "answers": [{"type": "choice", "name": "label", "choice": "auth",
               "confidence": 0.9, "probabilities": [{"value": "auth", "probability": 0.93}, "…"]}],
  "usage": {"input_tokens": 387, "output_tokens": 0}
}
```

- 質問タイプ: `predicate`（Jev の `noul` 相当、0〜1 の確率）/ `choice` / `score`（`levels: [{label, description}]`、確率加重平均を返す）
- `input` は文字列か、Responses API と同じ `[{role, content: [{type: "input_text" | 画像, ...}]}]`
- Jev との差: `questions` が配列で `name` を持つ、選択肢が `criteria`（dict）でなく `choices`（配列）、回答も配列。`state` ではなく `input`
- 「Responses API で同じ Luna を呼ぶより最大 10 倍速い」「25 ms 未満」とする記事あり（後者は二次情報）
- Vercel AI Gateway、LiteLLM（PR #45026）も対応

## Liquid AI d1

`POST https://api.liquid.ai/decisions/v1/systemone`（Jev の `/v1/systemone` と同じ形）。

- 公式に「TypeSafe-compatible System One API」。`model` + `state`（文字列 or JSON）+ `questions`（`choice` は `criteria` に名前 → 説明）
- 1 リクエスト最大 200 問
- Liquid API・Vercel AI Gateway・OpenRouter（`liquid/d1`）で利用可
- Hugging Face の Decision Index 0.2.1 で 58.9（Jev 1.13.0 は 57.91）。Liquid の自己申告で、知識推論系は Jev に劣るとの報道
  - 同指数では Fastino の GLiDE が 64.81 との報告もある
- LFM 系は open weight だが d1 は重み非公開

## Cloudflare Clef / Clef-flash

`POST https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/cloudflare/{clef,clef-flash}`、`Authorization: Bearer <CF API トークン>`。

- ボディは System One 形式（`state` + `questions`、`noul` / `choice` / `score`）。`model` は省略可（指定するなら URL と一致させる）。`temperature` は 422
- レスポンスは Cloudflare v4 の封筒に包まれる: `{"result": {"model", "answers", "usage"}, "success": true, "errors": [], "messages": []}`
- 制限: choice の選択肢 2〜255、score 2〜10 段階、質問 64 問まで
- Workers AI の課金は neuron（$0.011 / 1,000 neurons）。無料枠 10,000 neurons/日 ≈ Clef で 45 万 input tok/日
- 公表値（Cloudflare 計測、43 回の実行）

| | BANKING77 macro-F1 | CLINC150+OOS macro-F1 | BFCL | p50 | p95 |
| --- | --- | --- | --- | --- | --- |
| Clef | 94.20 | 97.43 | 98.47 | 209.3 ms | 238.6 ms |
| Clef-flash | 90.93 | 66.77 | 98.76 | 38.8 ms | 122.4 ms |
| Jev | — | — | — | 524.1 ms | 536.0 ms |

  - Jev の p50 524 ms は本リポジトリの実測（162〜175 ms、`docs/notes/jev.md`）の約 3 倍。計測地点の差とみられ、レイテンシ比較の「Jev の 13 倍速」はそのまま使えない
  - 判定系（judgment）では Jev に負けるとの第三者記事あり
- open weight: Hugging Face `Cloudflare/clef` ほか（GGUF / MLX 4bit / FP8 の派生も既にある）
  - 判定には専用の joint schema head と `systemone` ヘルパーが必要。vLLM / llama.cpp の通常のチャット推論では判定ヘッドが効かない（GGUF / MLX 版が判定に使えるかは不明）
  - 27B / 9B なので M1 8GB でのローカル実行は現実的でない → まずは Workers AI 経由
- RL ファインチューニング基盤（RLCD）も同時発表

## このリポジトリへの組み込み見込み

| モデル | 必要な作業 |
| --- | --- |
| d1 | `SystemOneClassifier` をそのまま使える見込み。`base_url = "https://api.liquid.ai/decisions"`、キーは `LIQUID_API_KEY` |
| Clef | `SystemOneClassifier` を継承し、URL（アカウント ID 入り）と `result` 封筒の剥がしだけ上書き。キーは `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID` |
| OpenAI | ワイヤ形式が違うので新しい分類器が要る。`criteria` → `choices` 配列、`answers` 配列から `name == "label"` を拾う。キーは `OPENAI_API_KEY` |

- 3 つとも同じ指示文・ラベル（`instructions` + 選択肢の説明）をそのまま渡せる形なので、公平性ルールは満たせる
- 実装前に確認すること（CLAUDE.md: 仕様が不明なら推測で実装しない）
  - d1: `criteria` 付き `choice` と `usage` の実レスポンス、`state_format` の両方が通るか
  - Clef: 実レスポンスの封筒と `usage` の有無、レイテンシにアカウント側の差が出るか
  - OpenAI: `confidence` の定義、`usage`、レート制限、beta ヘッダの要否、`input` を文字列で渡せるか

## 参考

- OpenAI: https://developers.openai.com/api/docs/guides/decisions 、https://developers.openai.com/api/reference/resources/decisions/methods/create 、https://github.com/BerriAI/litellm/pull/45026
- d1: https://www.liquid.ai/blog/d1-decision-model 、https://docs.liquid.ai/guides/decision-model-guide 、https://openrouter.ai/liquid/d1 、https://www.marktechpost.com/2026/09/29/liquid-ai-releases-d1-a-decision-model-that-returns-calibrated-probabilities-with-zero-output-tokens/
- Clef: https://blog.cloudflare.com/clef-decision-models/ 、https://developers.cloudflare.com/changelog/post/2026-10-01-clef-workers-ai/ 、https://huggingface.co/Cloudflare/clef 、https://github.com/pydantic/pydantic-ai/issues/9765 、https://github.com/MemberJunction/MJ/pull/4983 、https://www.eesel.ai/blog/cloudflare-clef-pricing
