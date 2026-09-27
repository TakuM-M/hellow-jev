# LLM（比較対象）調査メモ

- 利用形態: API / ローカルの両方を実装（どちらを本命にするかは結果を見て決める）
- 実装: `src/hellow_jev/classifiers/llm.py`（`backend = "api" | "local"`、`api_format = "anthropic" | "openai"`）
- 設定: `configs/llm_api.toml`, `configs/llm_local.toml`

## 位置づけ

- Jev / Laya は「判定専用・生成なし」のモデル。LLM は **生成で答える汎用モデル** としてのベースライン
- 比較の論点: 精度は LLM のほうが上か？ レイテンシ・コストで Jev / Laya がどれだけ有利か？

## 判断材料

| 観点 | API | ローカル |
| --- | --- | --- |
| 精度 | 高性能モデルを使える | モデルサイズ次第 |
| コスト | 従量課金 | GPU などの初期コスト |
| データの扱い | ログを外部に送る | 手元で完結 |
| 再現性 | モデル更新の影響を受ける | バージョンを固定しやすい |
| レイテンシ | ネットワーク込み・生成の分だけ遅い | GPU 次第 |

## 候補モデル（案）

- API: 小型・高速クラスを優先（例: Claude Haiku 4.5 など各社の軽量モデル）
  - Jev と同じ「安くて速い」土俵で比べるため。精度の上限を見る参考に、上位モデルを 1 つ足してもよい
- ローカル: Qwen3 系の 4B〜8B 程度を、Ollama / vLLM の **OpenAI 互換 API** で動かす
  - 実装を `/v1/chat/completions` 1 本にでき、標準ライブラリだけで書ける
- 料金・モデル ID は実装時に公式ドキュメントで確認する

## 実装方針

- 共通プロンプト `tasks/log_classification/prompt.md` を使い、temperature=0、max_tokens は小さめにする
- ラベル外の出力は既定ラベルに寄せず `None` とし、**ラベル外出力率**（`invalid_rate`）として記録する
- レイテンシは TTFT ではなく **応答完了まで** の時間で比べる（Jev / Laya と揃える）

## 実装（2026-09-27）

- 標準ライブラリのみ。SDK は入れない（HTTP は `classifiers/_http.py` の共通クライアント）
- `api_format = "anthropic"`: `POST {base_url}/v1/messages`、`x-api-key` + `anthropic-version: 2023-06-01`
  - 既定モデルは `claude-haiku-4-5-20251001`（日付付き ID で固定）。キーは `LLM_API_KEY`、無ければ `ANTHROPIC_API_KEY`
- `api_format = "openai"`: `POST {endpoint}/chat/completions`（Ollama / vLLM / llama.cpp server）
  - ローカルの既定は Ollama の `http://localhost:11434/v1`、モデルは `qwen3:4b`
- 共通: temperature=0、max_tokens=16、プロンプトは `task.render_prompt()`（user 1 ターン、system なし）
- 出力から `<think>...</think>` を除いてから `normalize()` にかける。ラベル外は `None`（invalid）
- usage は `input_tokens` / `output_tokens` に揃える（OpenAI 形式の prompt_tokens / completion_tokens を変換）
- 429 / 500 / 502 / 503 / 504 / 529 と接続エラーは、最大 `max_retries` 回リトライする（Retry-After を優先。Jev / Laya と同じ条件）。**リトライの待ち時間はレイテンシに乗る**
- サーバ固有のパラメータは config の `extra_body` で body に追加できる

## 未確認

- Haiku 4.5 の料金（config の `[pricing]` は $1 / $5 per MTok で仮置き。公式で要確認）
- Qwen3 の思考モードの切り方（vLLM は `chat_template_kwargs.enable_thinking=false`。Ollama の OpenAI 互換 API での指定方法は未確認）
  - 切れていないと `<think>` で max_tokens を使い切って invalid になる → `invalid_rate` で気づける

## 関連（参考）

- mini-jev: Qwen3-4B の logits で Jev 風のインターフェースを実現する試み
- Kev-9B: Apache-2.0 の Jev 代替（精度が Jev に近いと報告されている）

## ログ

- 2026-09-27: Jev / Laya の調査を踏まえて、位置づけと候補を整理
- 2026-09-27: API（Anthropic）/ ローカル（OpenAI 互換）の両方を実装。ダミーサーバでのみテスト済み
