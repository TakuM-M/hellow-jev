# LLM（比較対象）調査メモ

- 利用形態: API / ローカルの両方を実装（どちらを本命にするかは結果を見て決める）
- 実装: `src/hellow_jev/classifiers/llm.py`（`backend = "api" | "local"`、`api_format = "anthropic" | "openai"`）
- 設定: `configs/llm_api.toml`, `configs/llm_local.toml`

## 位置づけ

- Jev / Laya は「判定専用・生成なし」モデル。LLM は **生成で答える汎用モデル** のベースライン
- 比較の論点: 精度は LLM が上か？ レイテンシ・コストで Jev/Laya がどれだけ有利か？

## 判断材料

| 観点 | API | ローカル |
| --- | --- | --- |
| 精度 | 高性能モデルを使える | モデルサイズ次第 |
| コスト | 従量課金 | GPU 等の初期コスト |
| データ取り扱い | ログを外部送信する | 手元で完結 |
| 再現性 | モデル更新の影響あり | バージョン固定しやすい |
| レイテンシ | ネットワーク込み・生成分遅い | GPU 次第 |

## 候補モデル（案）

- API: 小型・高速クラスを優先（例: Claude Haiku 4.5 など各社の軽量モデル）
  - Jev と同じく「安くて速い」土俵で比べるため。精度上限の参考に上位モデルを 1 つ足すのも可
- ローカル: Qwen3 系 4B〜8B 程度を Ollama / vLLM の **OpenAI 互換 API** で
  - 実装を `/v1/chat/completions` 1 本にでき、標準ライブラリで書ける
- 料金・モデル ID は実装時に公式ドキュメントで確認する

## 実装メモ

- 共通プロンプト `tasks/log_classification/prompt.md` を使用、temperature=0、max_tokens 小さめ
- ラベル外出力は `normalize()` で fallback → **ラベル外出力率** も記録する
- レイテンシは TTFT ではなく **応答完了まで** の時間で比較（Jev/Laya と揃える）

## 実装（2026-09-27）

- 標準ライブラリ（urllib）のみ。SDK は入れない
- `api_format = "anthropic"`: `POST {base_url}/v1/messages`、`x-api-key` + `anthropic-version: 2023-06-01`
  - 既定モデル `claude-haiku-4-5-20251001`（日付付き ID で固定）。キーは `LLM_API_KEY` → `ANTHROPIC_API_KEY`
- `api_format = "openai"`: `POST {endpoint}/chat/completions`（Ollama / vLLM / llama.cpp server）
  - ローカル既定は Ollama `http://localhost:11434/v1`、モデル `qwen3:4b`
- 共通: temperature=0、max_tokens=16、プロンプトは `task.render_prompt()`（user 1 ターン、system なし）
- 出力は `<think>...</think>` を除去してから `normalize()`。ラベル外は `None`（invalid）
- usage は `input_tokens` / `output_tokens` に揃える（OpenAI 形式の prompt/completion_tokens を変換）
- 429 / 5xx / 529 は最大 `max_retries` 回リトライ（retry-after 優先）。**リトライ分はレイテンシに乗る**
- サーバ固有パラメータは config の `extra_body` で body に追加

## 未確認

- Haiku 4.5 の料金（config の `[pricing]` は $1 / $5 per MTok で仮置き。公式で要確認）
- Qwen3 の思考モードの切り方（vLLM は `chat_template_kwargs.enable_thinking=false`、Ollama の OpenAI 互換 API での指定方法は未確認）。
  切れていないと `<think>` で max_tokens を使い切り invalid になる → invalid_rate で気づける

## 関連（参考）

- mini-jev: Qwen3-4B の logits で Jev 風インターフェースを実現する試み
- Kev-9B: Apache-2.0 の Jev 代替（精度が Jev に近いと報告）

## ログ

- 2026-09-27: Jev / Laya 調査を踏まえ位置づけと候補を整理
