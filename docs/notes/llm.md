# LLM（比較対象）調査メモ

- 利用形態: API（Claude Haiku 4.5）/ ローカル（Qwen3 4B）の両方を比較対象にする（`docs/plan.md` の 2×2）
- 実装: `src/hellow_jev/classifiers/llm.py`（`backend = "api" | "local"`、`api_format = "anthropic" | "openai"`）
- 設定: `configs/llm_api.toml`, `configs/llm_local.toml`

## 位置づけ

- Jev / Laya は「判定専用・生成なし」のモデル。LLM は **生成で答える汎用モデル** としてのベースライン
- 比較の論点: 精度は LLM のほうが上か？ レイテンシ・コストで Jev / Laya がどれだけ有利か？

## 判断材料

| 観点 | API | ローカル |
| --- | --- | --- |
| 精度 | 同じ軽量クラスならローカルより大きいモデルを使える | モデルサイズ次第 |
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
- Qwen3 の思考モードの切り方（実サーバでは未検証）
  - vLLM: `chat_template_kwargs.enable_thinking=false`
  - Ollama: `/v1/chat/completions` に `reasoning_effort: "none"` → `think=false` に変換される（GitHub の ollama/docs/api/openai-compatibility.mdx で確認、2026-09-27）。古い版では /v1 で think 指定が無視されるという報告があるので、効かなければ Ollama を更新する
  - プロンプトに `/no_think` を書く方法もあるが、Qwen3 だけプロンプトが変わり公平性ルールに反するので使わない
  - 切れていないと `<think>` で max_tokens を使い切って invalid になる → `invalid_rate` で気づける

## 関連（参考）

- mini-jev: Qwen3-4B の logits で Jev 風のインターフェースを実現する試み
- Kev-9B: Apache-2.0 の Jev 代替（精度が Jev に近いと報告されている）

## ログ

- 2026-09-27: Jev / Laya の調査を踏まえて、位置づけと候補を整理
- 2026-09-27: API（Anthropic）/ ローカル（OpenAI 互換）の両方を実装。ダミーサーバでのみテスト済み
- 2026-09-27: Ollama の OpenAI 互換 API で思考を切る方法（`reasoning_effort: "none"`）を公式 docs で確認。config にコメントで追記
- 2026-09-28: 実 API（Haiku 4.5）で初回実行（`log_classification` 16 件、run `20260928T092426Z_llm_api`）。accuracy 16/16、invalid・エラー・リトライ 0
  - **ワークスペースに紐づかない（組織レベルの）API キーは 400 になる**（`anthropic-workspace-id` ヘッダが必須）。Console の Settings → Workspaces でワークスペースを選び、その中でキーを作れば不要（本リポジトリはこちらで対応し、ヘッダ送信は未実装）
  - usage: input ≈ 184 tok/件、output 4 tok/件（ラベル名だけ返り、stop_reason は全件 `end_turn`）
  - レイテンシ（ネットワーク込み）: p50 ≈ 657 ms / p95 ≈ 947 ms。同じ環境の Jev（p50 ≈ 162 ms）の約 4 倍
- 2026-09-28: Apple M1（8GB）に Ollama 0.34.4（Homebrew）を入れて `qwen3:4b` を試験
  - `qwen3:4b`（ID `359d7dd4bcda`、Q4_K_M、2.5GB）は **context 262144** で、`ollama show` の thinking は levels=true / default=true。コンテキスト長から、初代のハイブリッド版（40K）ではなく **2507 の Thinking 版**と見られる
  - **`reasoning_effort: "none"` では思考が止まらない**。思考文が `reasoning` 欄ではなく `content` にそのまま出るだけ（`<think>` タグも無い）で、max_tokens=32 を使い切る。指定しない場合は `reasoning` に思考が出て `content` は空
  - → `qwen3:4b` はこのベンチマーク（ラベル名だけ短く返させる）には使えない。思考なしの `qwen3:4b-instruct`（Instruct-2507）か、思考を切れる初代の `qwen3:4b-q4_K_M` に替える必要がある
  - **`qwen3:4b-instruct`（ID `0edcdef34593`）を採用**し、config の model を変更した。`ollama show` の Capabilities には thinking と出るが、実際には思考せずラベル名だけ返す（`finish_reason: stop`、2 tok）。extra_body は不要
- 2026-09-28: `qwen3:4b-instruct` で初回実行（`log_classification` 16 件、run `20260928T094556Z_llm_local`、M1 / Metal 100% GPU）。accuracy 14/16、invalid・エラー 0
  - レイテンシ: p50 ≈ 271 ms / p95 ≈ 418 ms。usage: input ≈ 170 tok/件、output 2 tok/件
  - メモリ: 実行中は Ollama 上で 3.2GB（context 4096）。システムの空きは 15% まで下がった → 8GB 機では他モデルと同時に動かさない
  - 誤り: s003（`login success` → auth。Jev・Laya と同じ）、s013（`brute force suspected` → auth、正解は security）
  - Ollama は既定で `127.0.0.1:11434` のみで待ち受ける。モデルはアクセスが無いと 5 分でメモリから外れる
