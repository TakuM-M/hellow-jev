# LLM

- 利用形態: API（Claude Haiku 4.5）/ ローカル（Qwen3-4B-Instruct-2507）
- 実装: `src/hellow_jev/classifiers/llm.py`（`backend = "api" | "local"`、`api_format = "anthropic" | "openai"`）
- 設定: `configs/llm_api.toml`, `configs/llm_local.toml`

## 実装

- 全タスクで system / user の 2 通 + JSON スキーマ（ラベル名の enum）で出力を縛る（jevbench と同じ形）
  - Jev / Laya は選択肢から選ぶのでラベル外を出さない。LLM だけ自由記述だと不利になるため
  - 読めない答え（max_tokens で切れた JSON など）は不正解として数える（混同行列では `<invalid>`）
- Anthropic: `POST {base_url}/v1/messages`、`system` + `output_config.format`（json_schema）
- OpenAI 互換: `POST {base_url}/chat/completions`、system ロール + `response_format`（json_schema）
- temperature=0、max_tokens=32（最長ラベル 50 文字でも Claude 24 tok / Qwen 16 tok に収まる）
- 429 / 500 / 502 / 503 / 504 / 529 と接続エラーはリトライ（Jev / Laya と同条件）。待ち時間はレイテンシに乗る
- サーバ固有パラメータは config の `extra_body` で追加できる

## API: Claude Haiku 4.5

- モデル `claude-haiku-4-5-20251001`。キーは `LLM_API_KEY`、無ければ `ANTHROPIC_API_KEY`
- ワークスペースに紐づかない（組織レベルの）API キーは 400 になる。Console でワークスペースを選び、その中でキーを作る
- 料金: input $1 / MTok、output $5 / MTok（2026-09-29、[公式料金ページ](https://platform.claude.com/docs/en/about-claude/pricing)）。Batch・キャッシュは使っていない。Bedrock / Vertex AI は別料金
- structured outputs ではスキーマ分の入力トークンが API 側で足されるとみられる
  - log_classification: input ≈ 373 tok/件（テキスト出力時は 184）、Banking77: ≈ 2,220 tok/件（Qwen の約 2 倍）

## ローカル: Qwen3-4B（Ollama）

- Ollama 0.34.4（Homebrew）、Apple M1 8GB、Metal。既定 `http://localhost:11434/v1`
- モデルは `qwen3:4b-instruct`（Instruct-2507、ID `0edcdef34593`、Q4_K_M）。思考せずラベルだけ返す
  - `qwen3:4b` は Thinking-2507（context 262144）で、`reasoning_effort: "none"` でも思考が止まらず `content` に出るため使えない
  - 思考ありのモデルに替えるなら、vLLM は `chat_template_kwargs.enable_thinking=false`、Ollama は `reasoning_effort: "none"`（初代ハイブリッド版向け）。プロンプトの `/no_think` は公平性ルールに反するので使わない
- `response_format` の json_schema は効く（生成時に enum 以外を選べない）。`json_object` は JSON の形だけでラベル外を防げない
- Banking77 の入力は ≈ 1,150 tok/件で、context 4096 に収まる（`truncated = 0`）
- メモリ: 実行中 3.2GB、システムの空きが 15% まで下がる → 8GB 機では他モデルと同時に動かさない
- Ollama は既定で `127.0.0.1` のみで待ち受け、アクセスが無いと 5 分でモデルをアンロードする

## 実測

| | log_classification p50 | jevbench p50 |
| --- | --- | --- |
| Haiku 4.5 | 914 ms | 750〜820 ms |
| Qwen3-4B | 546 ms | 690〜1,420 ms（Banking77 が最遅） |

- Jev・Laya の 4〜8 倍。Qwen は制約付き生成とプロンプト長のぶん遅くなる
- 精度は `docs/notes/dataset.md`

## 関連

- mini-jev: Qwen3-4B の logits で Jev 風のインターフェースを実現する試み
- Kev-9B: Apache-2.0 の Jev 代替（精度が Jev に近いと報告あり）
