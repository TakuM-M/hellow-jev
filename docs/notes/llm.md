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
- 料金 ✅ Haiku 4.5: input $1 / MTok、output $5 / MTok（2026-09-29 に [公式料金ページ](https://platform.claude.com/docs/en/about-claude/pricing) で確認。`configs/llm_api.toml` の `[pricing]` に反映）
  - この料金は Claude API 直の標準料金。Batch API は半額（$0.50 / $2.50）、キャッシュヒットは input の 0.1 倍。このベンチでは両方とも使っていない
  - Bedrock / Vertex AI は料金が別。リージョンを指定するエンドポイントは 1.1 倍

## 未確認

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
- 2026-09-29: jevbench タスク用に、LLM のプロンプトを jevbench と同じ形にした（system / user の 2 通 + JSON スキーマの enum 出力。`prompt.md` の `[system]` / `[user]`、task.toml の `llm_output = "json"`）
  - Anthropic API は `system` と `output_config: {format: {type: "json_schema", schema}}`、OpenAI 互換は system ロールと `response_format`（jevbench と同じ形）
  - Haiku 4.5 で確認（Banking77 5 件・AG News 3 件）: 全件 `{"label": ...}` の JSON で返り、stop_reason は `end_turn`。最長ラベル（`balance_not_updated_after_cheque_or_cash_deposit`、50 文字）で output 24 tok → max_tokens=32 で足りる
  - usage: Banking77 は input ≈ 2,220 tok/件（77 ラベルの説明が system に入るため）、AG News は ≈ 340 tok/件
- 2026-09-29: Ollama 0.34.4 + `qwen3:4b-instruct` で OpenAI 互換 API の `response_format`（json_schema）を確認
  - **制約は効く**（生成時に enum の中からしか選べない）。「hello とだけ答えよ」という system に対しても、enum `["zebra_alpha","yak_beta"]` を渡すと `{"label":"zebra_alpha"}` が返った。指示文で JSON を頼むだけ（`response_format` なし）だと、ラベル外の `positive` を返した
  - `json_object` はラベル外を防げない（JSON の形だけ）。jevbench と同じ `json_schema` を使う
  - max_tokens が足りないと JSON が途中で切れる（`finish_reason: length`）→ 読めないので invalid になる
  - パイプライン経由（Banking77 5 件・AG News 3 件、エラー・invalid 0）: 全件 `{"label": ...}` で `finish_reason: stop`。最長ラベルで output 16 tok（Qwen のトークナイザ）→ max_tokens=32 で足りる
  - Banking77 の入力は ≈ 1,150 tok/件（Claude の約半分。トークナイザの違い）。Ollama の context 4096 に収まり、ログにも `truncated = 0`
  - レイテンシ: p50 ≈ 850 ms（Banking77）/ 725 ms（AG News）。log_classification（テキスト出力）の 271 ms より遅いのは、プロンプトが長いため
- 2026-09-29: **LLM の出力を全タスクで JSON スキーマ（ラベル名の enum）に縛る方式に一本化**。`log_classification` も jevbench と同じ system / user の 2 通にした（指示文は残す）
  - 理由: Jev / Laya は選択肢から選ぶのでラベル外を出さない。LLM だけ自由記述だと、綴りの揺れなどで条件が不利になる
  - これに伴い **ラベル外率（`invalid_rate`）を指標から削除**。読めない答え（max_tokens で途中で切れた JSON など）は不正解に数えるだけ（混同行列では `<invalid>`）。テキスト出力の経路（`normalize`・`<think>` の除去）も削除
  - 9/28 の LLM の run 6 件（テキスト出力）は比較できないので削除対象とした
  - 再実行（`log_classification` 16 件、run `20260929T080714Z_llm_api` / `20260929T080735Z_llm_local`）:
    - Haiku 4.5: accuracy 16/16（前回 16/16）。input 184 → **373 tok/件**、p50 651 → 914 ms。system と user に分けたことに加え、structured outputs でスキーマ分の入力が API 側で足されているとみられる（jevbench の Banking77 でも 2,220 tok/件と Qwen の約 2 倍）
    - Qwen3-4B: accuracy 15/16（前回 14/16）。s013（brute force → security）が正解になり、s003（login success → auth）は引き続き誤り。input 170 → 179 tok/件、p50 268 → 546 ms（制約付き生成のぶん遅い）
- 2026-09-29: jevbench 4 タスク（各 500 件）を Haiku 4.5・Qwen3-4B で実行。エラー・リトライ 0。比較表は `docs/report.md`
  - Acc（Haiku / Qwen / 参考: jevbench の GPT-5-mini・Sonnet 5）: SST-2 0.960 / 0.940、AG News 旧 0.832 / 0.784（0.802・0.896）、新 0.850 / 0.766、Banking77 0.758 / 0.662（0.736・0.774）
  - Haiku は jevbench の GPT-5-mini と Sonnet 5 の間。Banking77 は Jev（0.768）とほぼ同じ
  - AG News の新ラベル説明は Haiku で +1.8pt、Qwen で −1.8pt（Jev +1.2、Laya −4.4）
  - レイテンシ p50: Haiku ≈ 750〜820 ms、Qwen ≈ 690〜1,420 ms（Banking77 が最も遅い。入力 ≈ 1,150 tok/件）。Jev・Laya の 4〜8 倍
  - コスト/1 万件: Haiku は Banking77 で $22.9（入力 ≈ 2,220 tok/件）。Jev は $0.83
  - 比較表の警告「タスク定義・プロンプト・コードが run 間で異なる」は想定内: Jev / Laya の run（`5f16e82`）以降の task.toml の変更はコメントのみ、`systemone.py` は無変更。プロンプトは LLM だけが使う
