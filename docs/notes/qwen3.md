# Qwen3-4B

- 利用形態: open weight（Ollama でローカル推論）
- 実装: `src/hellow_jev/classifiers/llm.py`（`backend = "local"`、`api_format = "openai"`。Claude Haiku 4.5 と共通）
- 設定: `configs/llm_local.toml` / 環境変数 `LLM_LOCAL_ENDPOINT`（既定 `http://localhost:11434/v1`）

## 概要

- Qwen3-4B-Instruct-2507。思考せずラベルだけ返す
- 出力の縛り方・temperature・max_tokens・リトライは Claude Haiku 4.5 と同じ（`claude_haiku.md`）

## API 仕様

- OpenAI 互換: `POST {base_url}/chat/completions`、system ロール + `response_format`（json_schema）
- `response_format` の json_schema は効く（生成時に enum 以外を選べない）。`json_object` は JSON の形だけでラベル外を防げない

## セットアップ（Apple M1 8GB で確認）

- Ollama 0.34.4（Homebrew）、Metal
- モデルは `qwen3:4b-instruct`（Instruct-2507、ID `0edcdef34593`、Q4_K_M）。vLLM なら `Qwen/Qwen3-4B-Instruct-2507`
  - `qwen3:4b` は Thinking-2507（context 262144）で、`reasoning_effort: "none"` でも思考が止まらず `content` に出るため使えない
  - 思考ありのモデルに替えるなら、vLLM は `chat_template_kwargs.enable_thinking=false`、Ollama は `reasoning_effort: "none"`（初代ハイブリッド版向け）。プロンプトの `/no_think` は公平性ルールに反するので使わない
- Banking77 の入力は ≈ 1,150 tok/件で、context 4096 に収まる（`truncated = 0`）
- メモリ: 実行中 3.2GB、システムの空きが 15% まで下がる → 8GB 機では他モデルと同時に動かさない
- Ollama は既定で `127.0.0.1` のみで待ち受け、アクセスが無いと 5 分でモデルをアンロードする

## 料金

- ローカル実行なので API 課金は無い（マシン代・電力は含まない）

## 実測（M1 8GB）

- p50: log_classification 546 ms、jevbench 690〜1,420 ms（Banking77 が最遅）
- 同じ M1 の Laya（149 ms）の約 4 倍。制約付き生成とプロンプト長のぶん遅くなる
- 精度は `docs/notes/dataset.md`

## 関連

- mini-jev: Qwen3-4B の logits で Jev 風のインターフェースを実現する試み
