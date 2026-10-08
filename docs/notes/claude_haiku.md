# Claude Haiku 4.5

- 利用形態: API（Anthropic）
- 実装: `src/hellow_jev/classifiers/llm.py`（`backend = "api"`、`api_format = "anthropic"`。Qwen3-4B と共通）
- 設定: `configs/llm_api.toml` / 環境変数 `LLM_API_KEY`（無ければ `ANTHROPIC_API_KEY`）

## 実装（LLM 共通）

- 全タスクで system / user の 2 通 + JSON スキーマ（ラベル名の enum）で出力を縛る（jevbench と同じ形）
  - Jev / Laya は選択肢から選ぶのでラベル外を出さない。LLM だけ自由記述だと不利になるため
  - 読めない答え（max_tokens で切れた JSON など）は不正解として数える（混同行列では `<invalid>`）
- temperature=0、max_tokens=32（最長ラベル 50 文字でも Claude 24 tok / Qwen 16 tok に収まる）
- 429 / 500 / 502 / 503 / 504 / 529 と接続エラーはリトライ（Jev / Laya と同条件）。待ち時間はレイテンシに乗る
- サーバ固有パラメータは config の `extra_body` で追加できる
- OpenAI 互換 API の場合は `qwen3.md`

## API 仕様

- `POST {base_url}/v1/messages`、`system` + `output_config.format`（json_schema）
- モデル `claude-haiku-4-5-20251001`（再現性のため日付付きで固定）
- ワークスペースに紐づかない（組織レベルの）API キーは 400 になる。Console でワークスペースを選び、その中でキーを作る
- structured outputs ではスキーマ分の入力トークンが API 側で足されるとみられる
  - log_classification: input ≈ 373 tok/件（テキスト出力時は 184）、Banking77: ≈ 2,220 tok/件（Qwen の約 2 倍）

## 料金

- input $1 / MTok、output $5 / MTok（2026-09-29、[公式料金ページ](https://platform.claude.com/docs/en/about-claude/pricing)）。Batch・キャッシュは使っていない。Bedrock / Vertex AI は別料金

## 実測

- p50: log_classification 914 ms、jevbench 750〜820 ms
- Jev（162 ms）の約 5〜6 倍
- 精度は `docs/notes/dataset.md`
